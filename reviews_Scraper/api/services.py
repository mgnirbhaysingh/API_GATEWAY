"""
Service layer for scraping operations
Wraps existing scrapers and integrates with database for status tracking
"""

import re
import sys
import os
import logging
from datetime import datetime
from typing import Callable, List, Dict, Any, Optional
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("SCRAPER_SERVICE")

# Add parent directory to import existing scrapers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.models import ScrapingJob, ScrapedReview, JobStatus, ScraperType
from api.database import SessionLocal


def get_background_db():
    """Get a new database session for background tasks.
    Background tasks need their own session since the request session is closed.
    """
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def extract_asin_from_url(url: str) -> Optional[str]:
    """Extract ASIN from Amazon product URL."""
    try:
        # Try /dp/ pattern
        match = re.search(r'/dp/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        # Try /gp/product/ pattern
        match = re.search(r'/gp/product/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        # Try /product-reviews/ pattern
        match = re.search(r'/product-reviews/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        return None
    except Exception:
        return None


def update_job_status(
    db: Session,
    job_id: str,
    status: str,
    progress_message: str = None,
    progress_percentage: float = None,
    reviews_scraped: int = None,
    total_reviews_found: int = None,
    error_message: str = None,
    result_data: dict = None
):
    """Update job status in database"""
    job = db.query(ScrapingJob).filter(ScrapingJob.job_id == job_id).first()
    if job:
        job.status = status
        if progress_message is not None:
            job.progress_message = progress_message
        if progress_percentage is not None:
            job.progress_percentage = progress_percentage
        if reviews_scraped is not None:
            job.reviews_scraped = reviews_scraped
        if total_reviews_found is not None:
            job.total_reviews_found = total_reviews_found
        if error_message is not None:
            job.error_message = error_message
        if result_data is not None:
            job.result_data = result_data

        if status == JobStatus.IN_PROGRESS.value and job.started_at is None:
            job.started_at = datetime.utcnow()
        elif status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
            job.completed_at = datetime.utcnow()

        db.commit()


def save_reviews_to_db(
    db: Session,
    job_id: str,
    reviews: List[Dict[str, Any]],
    source: str,
    product_url: str,
    asin: str = None
):
    """Save scraped reviews to database"""
    for review in reviews:
        db_review = ScrapedReview(
            job_id=job_id,
            source=source,
            product_url=product_url,
            asin=asin,
            review_id=review.get('review_id', ''),
            author=review.get('author', ''),
            rating=review.get('rating'),
            title=review.get('title', ''),
            review_text=review.get('review_text', ''),
            review_date=review.get('review_date', ''),
            verified_purchase=str(review.get('verified_purchase', '')),
            helpful_votes=review.get('helpful_votes', 0),
            star_filter=review.get('star_filter', ''),
            keyword=review.get('keyword', ''),
            image_count=review.get('image_count', 0),
            image_urls=review.get('image_urls', ''),
            city=review.get('city', ''),
            upvotes=review.get('upvotes', 0),
            downvotes=review.get('downvotes', 0)
        )
        db.add(db_review)

    db.commit()


class AmazonReviewsService:
    """Service for Amazon reviews scraping"""

    @staticmethod
    def run_scraper(
        job_id: str,
        url: str,
        max_reviews: int = 500,
        use_keyword_strategy: bool = False
    ):
        """Run the Amazon reviews scraper"""
        # Create a new database session for this background task
        db = get_background_db()
        logger.info("=" * 60)
        logger.info(f"[AMAZON_REVIEWS] Starting scraper for job_id={job_id}")
        logger.info(f"[AMAZON_REVIEWS] URL: {url}")
        logger.info(f"[AMAZON_REVIEWS] max_reviews={max_reviews}, use_keyword_strategy={use_keyword_strategy}")
        logger.info(f"[AMAZON_REVIEWS] Database session created: {db}")
        logger.info("=" * 60)

        try:
            logger.debug("[AMAZON_REVIEWS] Importing scraper modules...")
            from scrapers.amazon_reviews import (
                get_csrf_token_from_page,
                fetch_reviews_ajax,
                extract_asin_from_url as amazon_extract_asin
            )
            logger.debug("[AMAZON_REVIEWS] Scraper modules imported successfully")
        except Exception as import_err:
            logger.error(f"[AMAZON_REVIEWS] Failed to import scraper modules: {import_err}")
            update_job_status(db, job_id, JobStatus.FAILED.value, error_message=f"Import error: {import_err}")
            return

        try:
            # Update status to in_progress
            update_job_status(db, job_id, JobStatus.IN_PROGRESS.value, "Starting scraper...")

            # Extract ASIN
            logger.debug(f"[AMAZON_REVIEWS] Extracting ASIN from URL...")
            asin = amazon_extract_asin(url)
            if not asin:
                logger.error(f"[AMAZON_REVIEWS] Failed to extract ASIN from URL: {url}")
                update_job_status(
                    db, job_id, JobStatus.FAILED.value,
                    error_message="Failed to extract ASIN from URL"
                )
                return
            logger.info(f"[AMAZON_REVIEWS] Extracted ASIN: {asin}")

            # Get CSRF token
            logger.debug(f"[AMAZON_REVIEWS] Getting CSRF token...")
            update_job_status(db, job_id, JobStatus.IN_PROGRESS.value, "Getting CSRF token...")
            csrf_token = get_csrf_token_from_page(asin)
            logger.info(f"[AMAZON_REVIEWS] Got CSRF token: {csrf_token[:30]}...")

            star_filters = ['five_star', 'four_star', 'three_star', 'two_star', 'one_star']
            all_reviews = []
            seen_ids = set()

            logger.info(f"[AMAZON_REVIEWS] Starting to scrape reviews by star rating...")

            for star_filter in star_filters:
                if max_reviews > 0 and len(all_reviews) >= max_reviews:
                    logger.info(f"[AMAZON_REVIEWS] Reached max_reviews limit ({max_reviews}), stopping")
                    break

                logger.info(f"[AMAZON_REVIEWS] Processing {star_filter}...")
                update_job_status(
                    db, job_id, JobStatus.IN_PROGRESS.value,
                    f"Scraping {star_filter} reviews...",
                    progress_percentage=(star_filters.index(star_filter) / len(star_filters)) * 100,
                    reviews_scraped=len(all_reviews)
                )

                page = 1
                consecutive_empty = 0

                while consecutive_empty < 3 and page <= 15:
                    if max_reviews > 0 and len(all_reviews) >= max_reviews:
                        break

                    logger.debug(f"[AMAZON_REVIEWS] Fetching {star_filter} page {page}...")
                    reviews_batch, total_count = fetch_reviews_ajax(
                        asin, page, csrf_token, filter_by_star=star_filter
                    )
                    logger.debug(f"[AMAZON_REVIEWS] Got {len(reviews_batch) if reviews_batch else 0} reviews, total_count={total_count}")

                    if page == 1 and total_count > 0:
                        logger.info(f"[AMAZON_REVIEWS] Total reviews available for {star_filter}: {total_count}")
                        update_job_status(
                            db, job_id, JobStatus.IN_PROGRESS.value,
                            total_reviews_found=total_count
                        )

                    if reviews_batch:
                        consecutive_empty = 0
                        new_count = 0
                        for review in reviews_batch:
                            review_id = review.get('review_id', '')
                            if review_id and review_id not in seen_ids:
                                seen_ids.add(review_id)
                                review['star_filter'] = star_filter
                                all_reviews.append(review)
                                new_count += 1
                        logger.debug(f"[AMAZON_REVIEWS] Added {new_count} new reviews (total: {len(all_reviews)})")
                    else:
                        consecutive_empty += 1
                        logger.debug(f"[AMAZON_REVIEWS] Empty batch, consecutive_empty={consecutive_empty}")

                    page += 1

                logger.info(f"[AMAZON_REVIEWS] Finished {star_filter}: {len(all_reviews)} total reviews so far")

            # Save reviews to database
            logger.info(f"[AMAZON_REVIEWS] Saving {len(all_reviews)} reviews to database...")
            save_reviews_to_db(db, job_id, all_reviews, 'amazon', url, asin)
            logger.info(f"[AMAZON_REVIEWS] Reviews saved successfully!")

            # Update final status
            logger.info("=" * 60)
            logger.info(f"[AMAZON_REVIEWS] JOB COMPLETED: {len(all_reviews)} reviews scraped")
            logger.info("=" * 60)
            update_job_status(
                db, job_id, JobStatus.COMPLETED.value,
                f"Completed! Scraped {len(all_reviews)} reviews",
                progress_percentage=100.0,
                reviews_scraped=len(all_reviews),
                result_data={"reviews": all_reviews}
            )

        except Exception as e:
            logger.error(f"[AMAZON_REVIEWS] JOB FAILED: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            update_job_status(
                db, job_id, JobStatus.FAILED.value,
                error_message=str(e)
            )
        finally:
            logger.debug("[AMAZON_REVIEWS] Closing database session")
            db.close()


class AmazonAdvancedService:
    """Service for Amazon advanced scraping (keyword-based pagination bypass)"""

    @staticmethod
    def run_scraper(
        job_id: str,
        url: str,
        max_reviews: int = 0
    ):
        """Run the Amazon advanced scraper"""
        # Create a new database session for this background task
        db = get_background_db()
        logger.info("=" * 60)
        logger.info(f"[AMAZON_ADVANCED] Starting scraper for job_id={job_id}")
        logger.info(f"[AMAZON_ADVANCED] URL: {url}, max_reviews={max_reviews}")
        logger.info("=" * 60)

        try:
            from scrapers.amazon_reviews import get_csrf_token_from_page, extract_asin_from_url as amazon_extract_asin
            from scrapers.amazon_review_counter import get_total_review_count
            from scrapers.amazon_advanced_scraper import scrape_amazon_reviews_advanced

            update_job_status(db, job_id, JobStatus.IN_PROGRESS.value, "Starting advanced scraper...")

            # Extract ASIN
            asin = amazon_extract_asin(url)
            if not asin:
                update_job_status(
                    db, job_id, JobStatus.FAILED.value,
                    error_message="Failed to extract ASIN from URL"
                )
                return

            # Get total review count
            update_job_status(db, job_id, JobStatus.IN_PROGRESS.value, "Getting total review count...")
            total_count, status_msg = get_total_review_count(asin)

            if total_count == 0:
                update_job_status(
                    db, job_id, JobStatus.FAILED.value,
                    error_message=f"Could not get review count: {status_msg}"
                )
                return

            update_job_status(
                db, job_id, JobStatus.IN_PROGRESS.value,
                f"Found {total_count} total reviews",
                total_reviews_found=total_count
            )

            # Get CSRF token
            csrf_token = get_csrf_token_from_page(asin)

            # Progress callback
            def progress_callback(msg: str, count: int):
                update_job_status(
                    db, job_id, JobStatus.IN_PROGRESS.value,
                    progress_message=msg,
                    reviews_scraped=count
                )

            # Run advanced scraper
            reviews = scrape_amazon_reviews_advanced(
                asin, csrf_token, max_reviews, total_count, progress_callback
            )

            # Save reviews to database
            save_reviews_to_db(db, job_id, reviews, 'amazon', url, asin)

            # Update final status
            percentage = (len(reviews) / total_count * 100) if total_count > 0 else 0
            update_job_status(
                db, job_id, JobStatus.COMPLETED.value,
                f"Completed! Scraped {len(reviews)}/{total_count} ({percentage:.1f}%)",
                progress_percentage=100.0,
                reviews_scraped=len(reviews),
                result_data={"reviews": reviews}
            )

        except Exception as e:
            logger.error(f"[AMAZON_ADVANCED] JOB FAILED: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            update_job_status(
                db, job_id, JobStatus.FAILED.value,
                error_message=str(e)
            )
        finally:
            logger.debug("[AMAZON_ADVANCED] Closing database session")
            db.close()


class AmazonCounterService:
    """Service for Amazon review counting"""

    @staticmethod
    def run_counter(
        job_id: str,
        url: str
    ):
        """Run the Amazon review counter"""
        # Create a new database session for this background task
        db = get_background_db()
        logger.info(f"[AMAZON_COUNTER] Starting counter for job_id={job_id}, URL={url}")

        try:
            from scrapers.amazon_review_counter import get_total_review_count, extract_asin_from_url as counter_extract_asin

            update_job_status(db, job_id, JobStatus.IN_PROGRESS.value, "Counting reviews...")

            # Extract ASIN
            asin = counter_extract_asin(url)
            if not asin:
                update_job_status(
                    db, job_id, JobStatus.FAILED.value,
                    error_message="Failed to extract ASIN from URL"
                )
                return

            # Get total review count
            total_count, status_msg = get_total_review_count(asin)

            # Update final status
            update_job_status(
                db, job_id, JobStatus.COMPLETED.value,
                f"Found {total_count} reviews",
                progress_percentage=100.0,
                total_reviews_found=total_count,
                result_data={"total_reviews": total_count, "status": status_msg}
            )

        except Exception as e:
            logger.error(f"[AMAZON_COUNTER] JOB FAILED: {str(e)}")
            update_job_status(
                db, job_id, JobStatus.FAILED.value,
                error_message=str(e)
            )
        finally:
            logger.debug("[AMAZON_COUNTER] Closing database session")
            db.close()


class FlipkartReviewsService:
    """Service for Flipkart reviews scraping"""

    @staticmethod
    def run_scraper(
        job_id: str,
        url: str
    ):
        """Run the Flipkart reviews scraper"""
        # Create a new database session for this background task
        db = get_background_db()
        logger.info("=" * 60)
        logger.info(f"[FLIPKART] Starting scraper for job_id={job_id}")
        logger.info(f"[FLIPKART] URL: {url}")
        logger.info(f"[FLIPKART] Database session created: {db}")
        logger.info("=" * 60)

        try:
            logger.debug("[FLIPKART] Importing scraper modules...")
            from scrapers.flipkart_product_reviews import (
                clean_product_url,
                build_page_uri,
                extract_reviews_from_response,
                API_URL,
                HEADERS
            )
            import requests
            logger.debug(f"[FLIPKART] Scraper modules imported successfully")
            logger.debug(f"[FLIPKART] API_URL: {API_URL}")
        except Exception as import_err:
            logger.error(f"[FLIPKART] Failed to import scraper modules: {import_err}")
            update_job_status(db, job_id, JobStatus.FAILED.value, error_message=f"Import error: {import_err}")
            return

        try:
            update_job_status(db, job_id, JobStatus.IN_PROGRESS.value, "Starting Flipkart scraper...")

            logger.debug(f"[FLIPKART] Cleaning product URL...")
            review_base = clean_product_url(url)
            if not review_base:
                logger.error(f"[FLIPKART] Could not parse product URL: {url}")
                update_job_status(
                    db, job_id, JobStatus.FAILED.value,
                    error_message="Could not parse product URL"
                )
                return
            logger.info(f"[FLIPKART] Review base URL: {review_base}")

            all_reviews = []
            seen_ids = set()
            page = 1
            consecutive_empty = 0
            max_empty = 40
            abs_max_pages = 500

            logger.info(f"[FLIPKART] Starting pagination (max {abs_max_pages} pages, stop after {max_empty} empty)")

            while page <= abs_max_pages and consecutive_empty < max_empty:
                if page % 10 == 1:  # Log every 10 pages
                    logger.info(f"[FLIPKART] Processing page {page}... (total reviews: {len(all_reviews)})")

                update_job_status(
                    db, job_id, JobStatus.IN_PROGRESS.value,
                    f"Scraping page {page}...",
                    reviews_scraped=len(all_reviews)
                )

                page_uri = build_page_uri(review_base, page)
                from urllib.parse import urlparse
                parsed = urlparse(page_uri)
                payload = {
                    "pageUri": parsed.path + ("?" + parsed.query if parsed.query else ""),
                    "pageContext": {"fetchSeoData": True}
                }

                try:
                    logger.debug(f"[FLIPKART] Page {page}: Sending POST to API...")
                    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
                    logger.debug(f"[FLIPKART] Page {page}: Response status={resp.status_code}")

                    if resp.status_code != 200:
                        logger.warning(f"[FLIPKART] Page {page}: Non-200 response ({resp.status_code})")
                        consecutive_empty += 1
                        page += 1
                        continue

                    data = resp.json()
                    reviews, total_pages = extract_reviews_from_response(data, page_uri)
                    logger.debug(f"[FLIPKART] Page {page}: Got {len(reviews) if reviews else 0} reviews, total_pages={total_pages}")

                    if reviews:
                        consecutive_empty = 0
                        new_count = 0
                        for review in reviews:
                            rid = review.get('review_id') or review.get('review_url')
                            if rid and rid not in seen_ids:
                                seen_ids.add(rid)
                                new_count += 1
                                all_reviews.append({
                                    'review_id': rid,
                                    'author': review.get('author', ''),
                                    'rating': review.get('rating'),
                                    'title': review.get('title', ''),
                                    'review_text': review.get('review_text', ''),
                                    'review_date': review.get('created_date', ''),
                                    'helpful_votes': review.get('helpful_count', 0),
                                    'upvotes': review.get('upvotes', 0),
                                    'downvotes': review.get('downvotes', 0),
                                    'city': review.get('city', ''),
                                    'image_count': review.get('image_count', 0),
                                    'image_urls': review.get('review_image_url', '')
                                })
                        logger.debug(f"[FLIPKART] Page {page}: Added {new_count} new reviews")
                    else:
                        consecutive_empty += 1
                        logger.debug(f"[FLIPKART] Page {page}: Empty, consecutive_empty={consecutive_empty}")

                    if total_pages and page >= total_pages:
                        logger.info(f"[FLIPKART] Reached last page ({total_pages})")
                        break

                except Exception as e:
                    logger.warning(f"[FLIPKART] Page {page}: Error - {str(e)}")
                    consecutive_empty += 1

                page += 1

            # Save reviews to database
            logger.info(f"[FLIPKART] Saving {len(all_reviews)} reviews to database...")
            save_reviews_to_db(db, job_id, all_reviews, 'flipkart', url)
            logger.info(f"[FLIPKART] Reviews saved successfully!")

            # Update final status
            logger.info("=" * 60)
            logger.info(f"[FLIPKART] JOB COMPLETED: {len(all_reviews)} reviews scraped")
            logger.info("=" * 60)
            update_job_status(
                db, job_id, JobStatus.COMPLETED.value,
                f"Completed! Scraped {len(all_reviews)} reviews",
                progress_percentage=100.0,
                reviews_scraped=len(all_reviews),
                result_data={"reviews": all_reviews}
            )

        except Exception as e:
            logger.error(f"[FLIPKART] JOB FAILED: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            update_job_status(
                db, job_id, JobStatus.FAILED.value,
                error_message=str(e)
            )
        finally:
            logger.debug("[FLIPKART] Closing database session")
            db.close()
