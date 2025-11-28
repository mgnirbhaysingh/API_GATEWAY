"""
Database models for scraping jobs
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Enum, Float
from sqlalchemy.sql import func
from api.database import Base
import enum
import uuid


class JobStatus(str, enum.Enum):
    """Enum for job status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScraperType(str, enum.Enum):
    """Enum for scraper types"""
    AMAZON_REVIEWS = "amazon_reviews"
    AMAZON_COUNTER = "amazon_counter"
    FLIPKART_REVIEWS = "flipkart_reviews"


class ScrapingJob(Base):
    """Model for storing scraping job information"""
    __tablename__ = "scraping_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    # Scraper configuration
    scraper_type = Column(String(50), nullable=False)
    url = Column(Text, nullable=False)
    asin = Column(String(20), nullable=True)  # For Amazon products

    # Job status
    status = Column(String(20), default=JobStatus.PENDING.value)
    progress_message = Column(Text, nullable=True)
    progress_percentage = Column(Float, default=0.0)

    # Results
    total_reviews_found = Column(Integer, default=0)
    reviews_scraped = Column(Integer, default=0)
    result_data = Column(JSON, nullable=True)  # Store scraped data as JSON
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<ScrapingJob(job_id={self.job_id}, type={self.scraper_type}, status={self.status})>"


class ScrapedReview(Base):
    """Model for storing individual scraped reviews"""
    __tablename__ = "scraped_reviews"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), index=True, nullable=False)

    # Source info
    source = Column(String(20), nullable=False)  # 'amazon' or 'flipkart'
    product_url = Column(Text, nullable=True)
    asin = Column(String(20), nullable=True)  # For Amazon

    # Review data
    review_id = Column(String(100), index=True)
    author = Column(String(255), nullable=True)
    rating = Column(Float, nullable=True)
    title = Column(Text, nullable=True)
    review_text = Column(Text, nullable=True)
    review_date = Column(String(100), nullable=True)
    verified_purchase = Column(String(10), nullable=True)
    helpful_votes = Column(Integer, default=0)

    # Additional metadata
    star_filter = Column(String(20), nullable=True)
    keyword = Column(String(100), nullable=True)
    image_count = Column(Integer, default=0)
    image_urls = Column(Text, nullable=True)

    # Flipkart specific
    city = Column(String(100), nullable=True)
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ScrapedReview(review_id={self.review_id}, source={self.source})>"
