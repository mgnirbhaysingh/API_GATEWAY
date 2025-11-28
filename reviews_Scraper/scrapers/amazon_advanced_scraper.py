"""
Advanced Amazon Review Scraper with Keyword-based Pagination Bypass
Uses multiple keywords and star filters to scrape beyond the 100-review limit
"""

import os
import requests
from typing import Set, List, Dict, Any, Callable
from .amazon_reviews import fetch_reviews_ajax
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

# Basic keywords that work across all product types
BASIC_KEYWORDS = [
    "good", "bad", "great", "excellent", "poor", "amazing", "terrible",
    "worst", "best", "love", "hate", "quality", "price", "value",
    "disappointed", "satisfied", "recommend", "waste", "perfect", "awful"
]


def generate_keywords_with_gemini(
    product_name: str,
    used_keywords: List[str],
    star_rating: str,
    count: int = 20
) -> List[str]:
    """
    Generate new keywords using Gemini AI based on product type and previously used keywords

    Args:
        product_name: Name/description of the product
        used_keywords: Keywords already tried
        star_rating: Star rating (e.g., "five_star", "one_star")
        count: Number of keywords to generate

    Returns:
        List of new keywords
    """
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("Warning: GEMINI_API_KEY not found, cannot generate more keywords")
        return []

    # Convert star_rating to number for context
    star_map = {
        "five_star": "5-star (positive)",
        "four_star": "4-star (mostly positive)",
        "three_star": "3-star (neutral/mixed)",
        "two_star": "2-star (mostly negative)",
        "one_star": "1-star (negative)"
    }
    star_context = star_map.get(star_rating, star_rating)

    prompt = f"""You are analyzing Amazon reviews for: {product_name}

Task: Generate {count} VERY BASIC, SIMPLE keywords that commonly appear in {star_context} Amazon reviews for this type of product.

Already used keywords (DO NOT repeat these):
{', '.join(used_keywords)}

Requirements:
1. Use ONLY very basic, simple, common words that everyday people use in reviews
2. Keywords should be actual words that appear IN THE REVIEW TEXT itself (not technical jargon)
3. Prefer single common words over phrases (e.g., "battery", "price", "quality", "sound", "fast", "slow")
4. Include both positive and negative sentiment words appropriate for {star_context} reviews
5. Focus on words specific to this product category but keep them SIMPLE
6. Make them diverse - cover different aspects (features, quality, price, performance, delivery, packaging, etc.)
7. DO NOT repeat any keywords from the "already used" list above
8. Think like a regular customer writing a review, not a professional reviewer

Examples of GOOD keywords: "battery", "fast", "slow", "quality", "price", "sound", "comfortable", "broken", "works", "easy"
Examples of BAD keywords: "ergonomic", "durability", "functionality", "aesthetics"

Return ONLY a JSON array of {count} keywords, nothing else.

IMPORTANT: Return ONLY the JSON array with NO markdown formatting, no code blocks, no additional text."""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 500
        }
    }

    api_url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            print(f"Gemini API error {response.status_code}: {response.text}")
            return []

        response_data = response.json()
        text = ""
        if "candidates" in response_data and len(response_data["candidates"]) > 0:
            candidate = response_data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "text" in part:
                        text += part["text"]

        # Clean up the text
        text = text.strip()
        import re
        import json

        # Remove markdown code blocks if present
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        # Try to find JSON array
        json_match = re.search(r'\[[\s\S]*\]', text)
        if json_match:
            keywords = json.loads(json_match.group(0))
            if isinstance(keywords, list):
                return [k.lower() for k in keywords if k.lower() not in used_keywords]

        return []

    except Exception as e:
        print(f"Error generating keywords with Gemini: {e}")
        return []


def scrape_keyword_star_combination(
    asin: str,
    csrf_token: str,
    keyword: str,
    star_filter: str
) -> List[Dict[str, Any]]:
    """
    Scrape reviews for a specific keyword + star filter combination (10 pages)
    Thread-safe helper function for parallel execution
    """
    reviews = []
    for page in range(1, 11):  # 10 pages
        reviews_batch, _ = fetch_reviews_ajax(
            asin, page, csrf_token,
            filter_by_star=star_filter,
            keyword=keyword
        )

        if not reviews_batch:
            break

        reviews.extend(reviews_batch)

    return reviews


def scrape_amazon_reviews_advanced(
    asin: str,
    csrf_token: str,
    max_reviews: int,
    total_review_count: int,
    progress_callback: Callable[[str, int], None] = None
) -> List[Dict[str, Any]]:
    """
    Advanced scraping that uses keywords to bypass Amazon's pagination limits

    Args:
        asin: Amazon product ASIN
        csrf_token: CSRF token for API requests
        max_reviews: Maximum number of reviews to scrape (0 = try to get 90% of total)
        total_review_count: Total number of reviews for the product
        progress_callback: Optional callback function(progress_msg, reviews_count)

    Returns:
        List of unique reviews
    """
    print(f"\n[AMAZON_ADVANCED] ========== scrape_amazon_reviews_advanced START ==========")
    print(f"[AMAZON_ADVANCED] ASIN: {asin}")
    print(f"[AMAZON_ADVANCED] CSRF Token: {csrf_token[:20]}...")
    print(f"[AMAZON_ADVANCED] Max Reviews: {max_reviews}")
    print(f"[AMAZON_ADVANCED] Total Review Count: {total_review_count}")

    def update_progress(msg: str, count: int):
        print(f"[AMAZON_ADVANCED] Progress: {msg} - Reviews: {count}")
        if progress_callback:
            progress_callback(msg, count)
        else:
            print(f"{msg} - Reviews: {count}")

    # Determine target review count
    if max_reviews == 0:
        target_count = int(total_review_count * 0.9)  # 90% of total
    else:
        target_count = min(max_reviews, int(total_review_count * 0.9))

    print(f"[AMAZON_ADVANCED] Target count: {target_count} ({('90% of total' if max_reviews == 0 else f'min({max_reviews}, 90% of {total_review_count})')})")
    update_progress(f"Target: {target_count} reviews (90% of {total_review_count})", 0)

    all_reviews = []
    seen_ids = set()

    # Track which star ratings we should continue scraping
    star_filters = {
        'five_star': {'exhausted': False, 'initial_count': 0, 'no_new_count': 0},
        'four_star': {'exhausted': False, 'initial_count': 0, 'no_new_count': 0},
        'three_star': {'exhausted': False, 'initial_count': 0, 'no_new_count': 0},
        'two_star': {'exhausted': False, 'initial_count': 0, 'no_new_count': 0},
        'one_star': {'exhausted': False, 'initial_count': 0, 'no_new_count': 0}
    }

    # Phase 1: Scrape without keywords (up to 100 reviews per star)
    print(f"\n[AMAZON_ADVANCED] ===== PHASE 1: Scraping without keywords =====")
    update_progress("Phase 1: Scraping without keywords", len(all_reviews))

    for star_filter in star_filters.keys():
        if len(all_reviews) >= target_count:
            print(f"[AMAZON_ADVANCED] Target reached, stopping Phase 1")
            break

        print(f"[AMAZON_ADVANCED] Processing {star_filter}...")
        update_progress(f"Scraping {star_filter} (no keyword)", len(all_reviews))

        pages_scraped = 0
        for page in range(1, 11):  # Up to 10 pages = ~100 reviews (10 reviews per page)
            print(f"[AMAZON_ADVANCED] Fetching {star_filter} page {page}...")
            reviews_batch, _ = fetch_reviews_ajax(asin, page, csrf_token, filter_by_star=star_filter)

            if not reviews_batch:
                print(f"[AMAZON_ADVANCED] No reviews in page {page}, stopping {star_filter}")
                break

            pages_scraped = page
            print(f"[AMAZON_ADVANCED] Got {len(reviews_batch)} reviews from page {page}")

            for review in reviews_batch:
                review_id = review.get('review_id', '')
                if review_id and review_id not in seen_ids:
                    seen_ids.add(review_id)
                    all_reviews.append(review)

        # Map star filter to rating value
        star_map = {'five_star': 5, 'four_star': 4, 'three_star': 3, 'two_star': 2, 'one_star': 1}
        rating_value = star_map.get(star_filter, 0)

        star_filters[star_filter]['initial_count'] = sum(
            1 for r in all_reviews if r.get('rating') == rating_value
        )

        print(f"[AMAZON_ADVANCED] {star_filter}: scraped {pages_scraped} pages, {star_filters[star_filter]['initial_count']} reviews")

        # Only mark as exhausted if we didn't reach 10 pages (hit end of available reviews)
        if pages_scraped < 10:
            star_filters[star_filter]['exhausted'] = True
            print(f"[AMAZON_ADVANCED] {star_filter} marked as exhausted (only {pages_scraped} pages)")
            update_progress(f"{star_filter} exhausted (only {pages_scraped} pages available)", len(all_reviews))

    print(f"[AMAZON_ADVANCED] Phase 1 complete: {len(all_reviews)} total reviews")

    # Check if we've reached target
    if len(all_reviews) >= target_count:
        print(f"[AMAZON_ADVANCED] ✅ Target reached in Phase 1!")
        update_progress(f"Target reached in Phase 1!", len(all_reviews))
        return all_reviews

    # Phase 2: Use basic keywords for non-exhausted star ratings (PARALLEL)
    update_progress("Phase 2: Using basic keywords (parallel execution)", len(all_reviews))

    used_keywords = set()
    lock = threading.Lock()  # Thread-safe lock for updating shared state

    for keyword in BASIC_KEYWORDS:
        if len(all_reviews) >= target_count:
            break

        used_keywords.add(keyword)

        # Prepare tasks for parallel execution (keyword + star combinations)
        tasks = []
        for star_filter, info in star_filters.items():
            if not info['exhausted']:
                tasks.append((keyword, star_filter))

        if not tasks:
            continue

        update_progress(f"Scraping keyword '{keyword}' across {len(tasks)} star filters (parallel)", len(all_reviews))

        # Execute tasks in parallel (max 5 workers to avoid overwhelming Amazon)
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_task = {
                executor.submit(scrape_keyword_star_combination, asin, csrf_token, kw, star): (kw, star)
                for kw, star in tasks
            }

            for future in as_completed(future_to_task):
                kw, star_filter = future_to_task[future]
                try:
                    reviews_batch = future.result()

                    # Thread-safe update
                    with lock:
                        star_map = {'five_star': 5, 'four_star': 4, 'three_star': 3, 'two_star': 2, 'one_star': 1}
                        rating_value = star_map.get(star_filter, 0)
                        initial_star_count = sum(1 for r in all_reviews if r.get('rating') == rating_value)

                        new_count = 0
                        for review in reviews_batch:
                            review_id = review.get('review_id', '')
                            if review_id and review_id not in seen_ids:
                                seen_ids.add(review_id)
                                all_reviews.append(review)
                                new_count += 1

                        # Check if we got any new reviews for this star rating
                        new_star_count = sum(1 for r in all_reviews if r.get('rating') == rating_value)
                        if new_star_count == initial_star_count:
                            star_filters[star_filter]['no_new_count'] += 1
                            if star_filters[star_filter]['no_new_count'] >= 5:
                                star_filters[star_filter]['exhausted'] = True
                                update_progress(f"{star_filter} exhausted (5 keywords yielded no new reviews)", len(all_reviews))
                        else:
                            star_filters[star_filter]['no_new_count'] = 0

                except Exception as e:
                    print(f"Error scraping keyword '{kw}' with {star_filter}: {e}")

    # Check if we've reached target
    if len(all_reviews) >= target_count:
        update_progress(f"Target reached in Phase 2!", len(all_reviews))
        return all_reviews

    # Phase 3: Use Gemini-generated keywords (up to 10 iterations, PARALLEL)
    update_progress("Phase 3: Using AI-generated keywords (parallel execution)", len(all_reviews))

    product_name = asin  # Ideally we'd have the product name, but ASIN works
    max_gemini_iterations = 10

    for iteration in range(max_gemini_iterations):
        if len(all_reviews) >= target_count:
            break

        # Check if all star ratings are exhausted
        if all(info['exhausted'] for info in star_filters.values()):
            update_progress("All star ratings exhausted", len(all_reviews))
            break

        update_progress(f"Gemini iteration {iteration + 1}/{max_gemini_iterations}", len(all_reviews))

        # Collect all AI keywords for all non-exhausted star ratings
        all_tasks = []
        for star_filter, info in star_filters.items():
            if info['exhausted'] or len(all_reviews) >= target_count:
                continue

            new_keywords = generate_keywords_with_gemini(
                product_name,
                list(used_keywords),
                star_filter,
                count=5  # Generate 5 keywords per iteration
            )

            if new_keywords:
                for keyword in new_keywords:
                    used_keywords.add(keyword)
                    all_tasks.append((keyword, star_filter))

        if not all_tasks:
            continue

        update_progress(f"Scraping {len(all_tasks)} AI keyword+star combinations (parallel)", len(all_reviews))

        # Execute AI keyword tasks in parallel (max 5 workers)
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_task = {
                executor.submit(scrape_keyword_star_combination, asin, csrf_token, kw, star): (kw, star)
                for kw, star in all_tasks
            }

            for future in as_completed(future_to_task):
                kw, star_filter = future_to_task[future]
                try:
                    reviews_batch = future.result()

                    # Thread-safe update
                    with lock:
                        star_map = {'five_star': 5, 'four_star': 4, 'three_star': 3, 'two_star': 2, 'one_star': 1}
                        rating_value = star_map.get(star_filter, 0)
                        initial_star_count = sum(1 for r in all_reviews if r.get('rating') == rating_value)

                        new_count = 0
                        for review in reviews_batch:
                            review_id = review.get('review_id', '')
                            if review_id and review_id not in seen_ids:
                                seen_ids.add(review_id)
                                all_reviews.append(review)
                                new_count += 1

                        # Check if we got new reviews
                        new_star_count = sum(1 for r in all_reviews if r.get('rating') == rating_value)
                        if new_star_count == initial_star_count:
                            star_filters[star_filter]['no_new_count'] += 1
                            if star_filters[star_filter]['no_new_count'] >= 5:
                                star_filters[star_filter]['exhausted'] = True
                                update_progress(f"{star_filter} exhausted (5 AI keywords yielded no new reviews)", len(all_reviews))
                        else:
                            star_filters[star_filter]['no_new_count'] = 0

                except Exception as e:
                    print(f"Error scraping AI keyword '{kw}' with {star_filter}: {e}")

    # Final status
    percentage = (len(all_reviews) / total_review_count * 100) if total_review_count > 0 else 0
    print(f"\n[AMAZON_ADVANCED] ========== SCRAPING COMPLETE ==========")
    print(f"[AMAZON_ADVANCED] Total reviews scraped: {len(all_reviews)}")
    print(f"[AMAZON_ADVANCED] Total available: {total_review_count}")
    print(f"[AMAZON_ADVANCED] Percentage: {percentage:.1f}%")
    print(f"[AMAZON_ADVANCED] Target was: {target_count}")
    print(f"[AMAZON_ADVANCED] ========================================")
    update_progress(f"Scraping complete! {len(all_reviews)}/{total_review_count} ({percentage:.1f}%)", len(all_reviews))

    return all_reviews
