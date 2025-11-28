"""
Pydantic schemas for API request/response validation
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class JobStatusEnum(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScraperTypeEnum(str, Enum):
    AMAZON_REVIEWS = "amazon_reviews"
    AMAZON_COUNTER = "amazon_counter"
    FLIPKART_REVIEWS = "flipkart_reviews"


# ============== Request Schemas ==============

class AmazonReviewsRequest(BaseModel):
    """Request schema for Amazon reviews scraper"""
    url: str = Field(..., description="Amazon product URL")
    max_reviews: Optional[int] = Field(500, description="Maximum number of reviews to scrape (0 for 90% of total)")
    use_keyword_strategy: Optional[bool] = Field(False, description="Use keyword strategy for >100 reviews")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.amazon.in/dp/B08N5WRWNW",
                "max_reviews": 500,
                "use_keyword_strategy": False
            }
        }


class AmazonCounterRequest(BaseModel):
    """Request schema for Amazon review counter"""
    url: str = Field(..., description="Amazon product URL")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.amazon.in/dp/B08N5WRWNW"
            }
        }


class FlipkartReviewsRequest(BaseModel):
    """Request schema for Flipkart reviews scraper"""
    url: str = Field(..., description="Flipkart product URL")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.flipkart.com/samsung-galaxy-m34-5g/p/itm123456"
            }
        }


# ============== Response Schemas ==============

class JobCreatedResponse(BaseModel):
    """Response when a scraping job is created"""
    job_id: str
    status: JobStatusEnum
    message: str
    url: str
    scraper_type: str

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "message": "Scraping job created successfully",
                "url": "https://www.amazon.in/dp/B08N5WRWNW",
                "scraper_type": "amazon_reviews"
            }
        }


class JobStatusResponse(BaseModel):
    """Response for job status query"""
    job_id: str
    status: JobStatusEnum
    scraper_type: str
    url: str
    asin: Optional[str] = None
    progress_message: Optional[str] = None
    progress_percentage: float = 0.0
    total_reviews_found: int = 0
    reviews_scraped: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewData(BaseModel):
    """Schema for individual review data"""
    review_id: str
    author: Optional[str] = None
    rating: Optional[float] = None
    title: Optional[str] = None
    review_text: Optional[str] = None
    review_date: Optional[str] = None
    verified_purchase: Optional[bool] = None
    helpful_votes: Optional[int] = 0
    image_count: Optional[int] = 0


class JobResultResponse(BaseModel):
    """Response containing job results"""
    job_id: str
    status: JobStatusEnum
    scraper_type: str
    url: str
    total_reviews: int
    reviews: List[Dict[str, Any]]


class AmazonCounterResponse(BaseModel):
    """Response for Amazon review counter"""
    job_id: str
    url: str
    asin: str
    total_reviews: int
    status: str
    message: str


class AllJobsResponse(BaseModel):
    """Response for listing all jobs"""
    total_jobs: int
    jobs: List[JobStatusResponse]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    database: str
    message: str
