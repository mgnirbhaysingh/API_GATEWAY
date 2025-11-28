#!/usr/bin/env python3
"""
FastAPI Application for Review Scrapers
Main entry point for the API server

Run with: python main.py
Or: uvicorn main:app --reload
"""

import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time

from api.database import init_db, engine
from api.routes import router
from api.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("=" * 60)
    print("Review Scraper API Starting...")
    print("=" * 60)
    print("Initializing database...")
    init_db()
    print("Database initialized successfully!")
    print("=" * 60)
    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title="Review Scraper API",
    description="""
## API for scraping product reviews from Amazon and Flipkart

This API provides endpoints for:
- **Amazon Reviews**: Scrape reviews with optional keyword strategy
- **Amazon Advanced**: Use AI-powered keyword generation to bypass pagination limits
- **Amazon Counter**: Quickly get total review count for a product
- **Flipkart Reviews**: Scrape reviews from Flipkart products

### Job Management
All scraping operations are asynchronous. You'll receive a `job_id` which can be used to:
- Track progress via `/api/v1/jobs/{job_id}`
- Fetch results via `/api/v1/jobs/{job_id}/results`

### Batch Operations
Use `/api/v1/batch/scrape` to scrape multiple URLs at once.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Include routes
app.include_router(router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Review Scraper API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "amazon_reviews": "/api/v1/amazon/reviews",
            "amazon_advanced": "/api/v1/amazon/advanced",
            "amazon_counter": "/api/v1/amazon/count",
            "flipkart_reviews": "/api/v1/flipkart/reviews",
            "job_status": "/api/v1/jobs/{job_id}",
            "job_results": "/api/v1/jobs/{job_id}/results",
            "all_jobs": "/api/v1/jobs",
            "batch_scrape": "/api/v1/batch/scrape"
        }
    }


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        database=db_status,
        message="API is running"
    )


# Debug endpoint to test scraper imports
@app.get("/debug/scrapers", tags=["Debug"])
async def debug_scrapers():
    """
    Test if all scrapers can be imported correctly.
    Use this to debug import issues.
    """
    results = {
        "amazon_reviews": {"status": "unknown", "error": None},
        "amazon_review_counter": {"status": "unknown", "error": None},
        "amazon_advanced_scraper": {"status": "unknown", "error": None},
        "flipkart_product_reviews": {"status": "unknown", "error": None}
    }

    # Test Amazon Reviews
    try:
        from scrapers.amazon_reviews import fetch_reviews_ajax, get_csrf_token_from_page, extract_asin_from_url
        results["amazon_reviews"] = {
            "status": "ok",
            "functions": ["fetch_reviews_ajax", "get_csrf_token_from_page", "extract_asin_from_url"]
        }
    except Exception as e:
        results["amazon_reviews"] = {"status": "error", "error": str(e)}

    # Test Amazon Review Counter
    try:
        from scrapers.amazon_review_counter import get_total_review_count
        results["amazon_review_counter"] = {
            "status": "ok",
            "functions": ["get_total_review_count"]
        }
    except Exception as e:
        results["amazon_review_counter"] = {"status": "error", "error": str(e)}

    # Test Amazon Advanced Scraper
    try:
        from scrapers.amazon_advanced_scraper import scrape_amazon_reviews_advanced
        results["amazon_advanced_scraper"] = {
            "status": "ok",
            "functions": ["scrape_amazon_reviews_advanced"]
        }
    except Exception as e:
        results["amazon_advanced_scraper"] = {"status": "error", "error": str(e)}

    # Test Flipkart Scraper
    try:
        from scrapers.flipkart_product_reviews import clean_product_url, build_page_uri, extract_reviews_from_response, API_URL
        results["flipkart_product_reviews"] = {
            "status": "ok",
            "functions": ["clean_product_url", "build_page_uri", "extract_reviews_from_response"],
            "api_url": API_URL
        }
    except Exception as e:
        results["flipkart_product_reviews"] = {"status": "error", "error": str(e)}

    all_ok = all(r["status"] == "ok" for r in results.values())

    return {
        "overall_status": "all scrapers loaded" if all_ok else "some scrapers failed",
        "scrapers": results
    }


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"

    print(f"\nStarting server at http://{host}:{port}")
    print(f"API Docs: http://localhost:{port}/docs")
    print(f"ReDoc: http://localhost:{port}/redoc\n")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload
    )
