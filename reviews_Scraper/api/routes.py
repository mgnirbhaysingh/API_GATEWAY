"""
API Routes for scraping operations
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from api.database import get_db
from api.models import ScrapingJob, ScrapedReview, JobStatus, ScraperType
from api.schemas import (
    AmazonReviewsRequest,
    AmazonCounterRequest,
    FlipkartReviewsRequest,
    JobCreatedResponse,
    JobStatusResponse,
    JobResultResponse,
    AmazonCounterResponse,
    AllJobsResponse
)
from api.services import (
    AmazonReviewsService,
    AmazonCounterService,
    FlipkartReviewsService,
    extract_asin_from_url
)

router = APIRouter()


# ============== Amazon Reviews Routes ==============

@router.post("/amazon/reviews", response_model=JobCreatedResponse, tags=["Amazon"])
async def scrape_amazon_reviews(
    request: AmazonReviewsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start Amazon reviews scraping job.

    This endpoint initiates a background scraping job for Amazon product reviews.
    Returns a job_id that can be used to track progress and fetch results.
    """
    # Extract ASIN from URL
    asin = extract_asin_from_url(request.url)

    # Create job record
    job = ScrapingJob(
        job_id=str(uuid.uuid4()),
        scraper_type=ScraperType.AMAZON_REVIEWS.value,
        url=request.url,
        asin=asin,
        status=JobStatus.PENDING.value
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Start background task (service creates its own db session)
    background_tasks.add_task(
        AmazonReviewsService.run_scraper,
        job.job_id,
        request.url,
        request.max_reviews,
        request.use_keyword_strategy
    )

    return JobCreatedResponse(
        job_id=job.job_id,
        status=JobStatus.PENDING,
        message="Amazon reviews scraping job created successfully",
        url=request.url,
        scraper_type=ScraperType.AMAZON_REVIEWS.value
    )


@router.post("/amazon/count", response_model=JobCreatedResponse, tags=["Amazon"])
async def count_amazon_reviews(
    request: AmazonCounterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Get total review count for an Amazon product.

    This is a quick operation that only fetches the total number of reviews
    available for the product without scraping the actual reviews.
    """
    asin = extract_asin_from_url(request.url)

    job = ScrapingJob(
        job_id=str(uuid.uuid4()),
        scraper_type=ScraperType.AMAZON_COUNTER.value,
        url=request.url,
        asin=asin,
        status=JobStatus.PENDING.value
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        AmazonCounterService.run_counter,
        job.job_id,
        request.url
    )

    return JobCreatedResponse(
        job_id=job.job_id,
        status=JobStatus.PENDING,
        message="Amazon review count job created successfully",
        url=request.url,
        scraper_type=ScraperType.AMAZON_COUNTER.value
    )


# ============== Flipkart Reviews Routes ==============

@router.post("/flipkart/reviews", response_model=JobCreatedResponse, tags=["Flipkart"])
async def scrape_flipkart_reviews(
    request: FlipkartReviewsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start Flipkart reviews scraping job.

    This endpoint initiates a background scraping job for Flipkart product reviews.
    Returns a job_id that can be used to track progress and fetch results.
    """
    job = ScrapingJob(
        job_id=str(uuid.uuid4()),
        scraper_type=ScraperType.FLIPKART_REVIEWS.value,
        url=request.url,
        status=JobStatus.PENDING.value
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        FlipkartReviewsService.run_scraper,
        job.job_id,
        request.url
    )

    return JobCreatedResponse(
        job_id=job.job_id,
        status=JobStatus.PENDING,
        message="Flipkart reviews scraping job created successfully",
        url=request.url,
        scraper_type=ScraperType.FLIPKART_REVIEWS.value
    )


# ============== Job Status Routes ==============

@router.get("/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Get status of a scraping job by job_id.

    Returns current status, progress, and any error messages.
    """
    job = db.query(ScrapingJob).filter(ScrapingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        scraper_type=job.scraper_type,
        url=job.url,
        asin=job.asin,
        progress_message=job.progress_message,
        progress_percentage=job.progress_percentage or 0.0,
        total_reviews_found=job.total_reviews_found or 0,
        reviews_scraped=job.reviews_scraped or 0,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at
    )


@router.get("/jobs/{job_id}/results", response_model=JobResultResponse, tags=["Jobs"])
async def get_job_results(job_id: str, db: Session = Depends(get_db)):
    """
    Get results of a completed scraping job.

    Returns all scraped reviews for the job. Only available for completed jobs.
    """
    job = db.query(ScrapingJob).filter(ScrapingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed. Current status: {job.status}"
        )

    # Get reviews from database
    reviews = db.query(ScrapedReview).filter(ScrapedReview.job_id == job_id).all()

    return JobResultResponse(
        job_id=job.job_id,
        status=job.status,
        scraper_type=job.scraper_type,
        url=job.url,
        total_reviews=len(reviews),
        reviews=[{
            "review_id": r.review_id,
            "author": r.author,
            "rating": r.rating,
            "title": r.title,
            "review_text": r.review_text,
            "review_date": r.review_date,
            "verified_purchase": r.verified_purchase,
            "helpful_votes": r.helpful_votes,
            "star_filter": r.star_filter,
            "keyword": r.keyword,
            "image_count": r.image_count,
            "city": r.city,
            "upvotes": r.upvotes,
            "downvotes": r.downvotes
        } for r in reviews]
    )


@router.get("/jobs", response_model=AllJobsResponse, tags=["Jobs"])
async def list_all_jobs(
    status: Optional[str] = None,
    scraper_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List all scraping jobs with optional filtering.

    Can filter by status (pending, in_progress, completed, failed) and scraper_type.
    """
    query = db.query(ScrapingJob)

    if status:
        query = query.filter(ScrapingJob.status == status)
    if scraper_type:
        query = query.filter(ScrapingJob.scraper_type == scraper_type)

    total = query.count()
    jobs = query.order_by(ScrapingJob.created_at.desc()).offset(offset).limit(limit).all()

    return AllJobsResponse(
        total_jobs=total,
        jobs=[JobStatusResponse(
            job_id=j.job_id,
            status=j.status,
            scraper_type=j.scraper_type,
            url=j.url,
            asin=j.asin,
            progress_message=j.progress_message,
            progress_percentage=j.progress_percentage or 0.0,
            total_reviews_found=j.total_reviews_found or 0,
            reviews_scraped=j.reviews_scraped or 0,
            error_message=j.error_message,
            created_at=j.created_at,
            started_at=j.started_at,
            completed_at=j.completed_at
        ) for j in jobs]
    )


@router.delete("/jobs/{job_id}", tags=["Jobs"])
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """
    Cancel a pending or in-progress scraping job.

    Note: Already running scraper tasks may not stop immediately.
    """
    job = db.query(ScrapingJob).filter(ScrapingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel a {job.status} job"
        )

    job.status = JobStatus.CANCELLED.value
    db.commit()

    return {"message": f"Job {job_id} cancelled successfully"}


