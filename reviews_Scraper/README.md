# Review Scraper API

A FastAPI-based REST API for scraping product reviews from Amazon and Flipkart. Features asynchronous job processing, SQLite database storage, and real-time progress tracking.

## Features

- **Amazon Reviews Scraper** - Scrape reviews with star filter pagination
- **Amazon Review Counter** - Quick total review count lookup
- **Flipkart Reviews Scraper** - Scrape reviews via Flipkart's internal API
- **Async Job Processing** - Background tasks with real-time status tracking
- **SQLite Database** - Persistent storage for jobs and scraped reviews

## Project Structure

```
scraper-db/
├── main.py                  # FastAPI application entry point
├── requirements.txt         # Python dependencies
├── scraper_jobs.db          # SQLite database (auto-created)
├── api/
│   ├── __init__.py
│   ├── database.py          # Database configuration & session management
│   ├── models.py            # SQLAlchemy ORM models
│   ├── routes.py            # API endpoint definitions
│   ├── schemas.py           # Pydantic request/response schemas
│   └── services.py          # Scraper service layer & background tasks
└── scrapers/
    ├── __init__.py
    ├── amazon_reviews.py           # Basic Amazon review scraper
    ├── amazon_review_counter.py    # Amazon review count fetcher
    └── flipkart_product_reviews.py # Flipkart review scraper
```

## Installation

### Prerequisites

- Python 3.9+
- pip

### Setup

1. **Clone or navigate to the project directory**
   ```bash
   cd scraper-db
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv .venv

   # Windows
   .venv\Scripts\activate

   # Linux/Mac
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the API server**
   ```bash
   python main.py
   ```

   Or with uvicorn directly:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Access the API**
   - API Root: http://localhost:8000
   - Swagger Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./scraper_jobs.db` | Database connection string |
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8000` | API server port |
| `API_RELOAD` | `true` | Enable hot reload |

## API Endpoints

### Amazon Endpoints

#### POST `/api/v1/amazon/reviews`
Start Amazon reviews scraping job.

**Request Body:**
```json
{
  "url": "https://www.amazon.in/dp/B08N5WRWNW",
  "max_reviews": 500,
  "use_keyword_strategy": false
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Amazon reviews scraping job created successfully",
  "url": "https://www.amazon.in/dp/B08N5WRWNW",
  "scraper_type": "amazon_reviews"
}
```

#### POST `/api/v1/amazon/count`
Get total review count for an Amazon product.

**Request Body:**
```json
{
  "url": "https://www.amazon.in/dp/B08N5WRWNW"
}
```

### Flipkart Endpoints

#### POST `/api/v1/flipkart/reviews`
Start Flipkart reviews scraping job.

**Request Body:**
```json
{
  "url": "https://www.flipkart.com/samsung-galaxy-m34-5g/p/itm123456"
}
```

### Job Management Endpoints

#### GET `/api/v1/jobs/{job_id}`
Get status of a scraping job.

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "in_progress",
  "scraper_type": "amazon_reviews",
  "url": "https://www.amazon.in/dp/B08N5WRWNW",
  "asin": "B08N5WRWNW",
  "progress_message": "Scraping four_star reviews...",
  "progress_percentage": 40.0,
  "total_reviews_found": 1500,
  "reviews_scraped": 250,
  "error_message": null,
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:01Z",
  "completed_at": null
}
```

#### GET `/api/v1/jobs/{job_id}/results`
Get scraped reviews for a completed job.

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "scraper_type": "amazon_reviews",
  "url": "https://www.amazon.in/dp/B08N5WRWNW",
  "total_reviews": 500,
  "reviews": [
    {
      "review_id": "R123ABC",
      "author": "John Doe",
      "rating": 5.0,
      "title": "Great product!",
      "review_text": "This is an amazing product...",
      "review_date": "January 10, 2024",
      "verified_purchase": "true",
      "helpful_votes": 15,
      "star_filter": "five_star",
      "keyword": null,
      "image_count": 2,
      "city": null,
      "upvotes": 0,
      "downvotes": 0
    }
  ]
}
```

#### GET `/api/v1/jobs`
List all jobs with optional filtering.

**Query Parameters:**
- `status` - Filter by status (pending, in_progress, completed, failed, cancelled)
- `scraper_type` - Filter by scraper type
- `limit` - Max results (default: 100)
- `offset` - Skip results (default: 0)

#### DELETE `/api/v1/jobs/{job_id}`
Cancel a pending or in-progress job.

### Utility Endpoints

#### GET `/health`
Health check endpoint. Returns database connection status.

#### GET `/debug/scrapers`
Test if all scraper modules can be imported correctly.

## Job Status Flow

```
PENDING → IN_PROGRESS → COMPLETED
                     ↘ FAILED

PENDING → CANCELLED (via DELETE)
IN_PROGRESS → CANCELLED (via DELETE)
```

## Database Schema

### scraping_jobs
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| job_id | VARCHAR(36) | UUID for job identification |
| scraper_type | VARCHAR(50) | Type of scraper used |
| url | TEXT | Product URL being scraped |
| asin | VARCHAR(20) | Amazon ASIN (if applicable) |
| status | VARCHAR(20) | Current job status |
| progress_message | TEXT | Human-readable progress |
| progress_percentage | FLOAT | Completion percentage |
| total_reviews_found | INTEGER | Total reviews available |
| reviews_scraped | INTEGER | Reviews successfully scraped |
| result_data | JSON | Raw result data |
| error_message | TEXT | Error details if failed |
| created_at | DATETIME | Job creation time |
| started_at | DATETIME | Job start time |
| completed_at | DATETIME | Job completion time |

### scraped_reviews
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| job_id | VARCHAR(36) | Reference to scraping job |
| source | VARCHAR(20) | 'amazon' or 'flipkart' |
| product_url | TEXT | Product URL |
| asin | VARCHAR(20) | Amazon ASIN |
| review_id | VARCHAR(100) | Unique review identifier |
| author | VARCHAR(255) | Reviewer name |
| rating | FLOAT | Star rating |
| title | TEXT | Review title |
| review_text | TEXT | Review content |
| review_date | VARCHAR(100) | Date of review |
| verified_purchase | VARCHAR(10) | Verification status |
| helpful_votes | INTEGER | Helpful vote count |
| star_filter | VARCHAR(20) | Star filter used |
| keyword | VARCHAR(100) | Keyword used (advanced) |
| image_count | INTEGER | Number of images |
| image_urls | TEXT | Image URLs |
| city | VARCHAR(100) | Reviewer city (Flipkart) |
| upvotes | INTEGER | Upvotes (Flipkart) |
| downvotes | INTEGER | Downvotes (Flipkart) |
| created_at | DATETIME | Record creation time |

## Scraper Details

### Amazon Reviews Scraper
- Uses Amazon's AJAX API for fetching reviews
- Extracts CSRF token from product page
- Iterates through star filters (5★ to 1★)
- Handles pagination within each star filter
- Deduplicates reviews by review_id

### Amazon Review Counter
- Quick lookup of total review count
- Extracts count from product page HTML
- Useful for estimating scrape time

### Flipkart Reviews Scraper
- Uses Flipkart's internal GraphQL-like API
- Paginates through all available reviews
- Extracts rich metadata including city, upvotes/downvotes
- Handles images and helpful counts

## Usage Examples

### Python
```python
import requests
import time

BASE_URL = "http://localhost:8000/api/v1"

# Start a scraping job
response = requests.post(f"{BASE_URL}/amazon/reviews", json={
    "url": "https://www.amazon.in/dp/B08N5WRWNW",
    "max_reviews": 100
})
job_id = response.json()["job_id"]

# Poll for completion
while True:
    status = requests.get(f"{BASE_URL}/jobs/{job_id}").json()
    print(f"Status: {status['status']} - {status['progress_message']}")

    if status["status"] in ["completed", "failed"]:
        break
    time.sleep(5)

# Get results
if status["status"] == "completed":
    results = requests.get(f"{BASE_URL}/jobs/{job_id}/results").json()
    print(f"Scraped {results['total_reviews']} reviews")
```

### cURL
```bash
# Start scraping job
curl -X POST "http://localhost:8000/api/v1/amazon/reviews" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.amazon.in/dp/B08N5WRWNW", "max_reviews": 100}'

# Check job status
curl "http://localhost:8000/api/v1/jobs/{job_id}"

# Get results
curl "http://localhost:8000/api/v1/jobs/{job_id}/results"

# List all jobs
curl "http://localhost:8000/api/v1/jobs?status=completed&limit=10"
```

## Troubleshooting

### Check Scraper Imports
```bash
curl http://localhost:8000/debug/scrapers
```

### Check Database Connection
```bash
curl http://localhost:8000/health
```

### View Logs
The API outputs detailed logs to stdout. Look for lines prefixed with:
- `[AMAZON_REVIEWS]` - Amazon reviews scraper
- `[AMAZON_COUNTER]` - Amazon counter
- `[FLIPKART]` - Flipkart scraper

### Common Issues

1. **Import errors** - Ensure all dependencies are installed: `pip install -r requirements.txt`
2. **Database errors** - Delete `scraper_jobs.db` and restart to recreate tables
3. **CSRF token errors** - Amazon may be rate-limiting; add delays between requests
4. **Empty results** - Check if the product URL is valid and has reviews

## License

This project is for educational purposes only. Ensure compliance with Amazon and Flipkart's terms of service when using these scrapers.
