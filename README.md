# AllScrapers - Universal E-commerce & Data Scraping Platform

A comprehensive, modular scraping platform that provides unified access to multiple e-commerce platforms, review aggregation, Shopify store processing, and Google Maps data extraction.

## Architecture Overview

```
                                    ┌─────────────────────────────────────┐
                                    │        ScraperGateway               │
                                    │         (Port 8080)                 │
                                    │                                     │
          Client Request ──────────►│  Unified API Entry Point            │
                                    │                                     │
                                    │  /api/search/*   ───────────────────┼──► QuickComm (8001)
                                    │  /api/shopify/*  ───────────────────┼──► ShopifyCode (8002)
                                    │  /api/reviews/*  ───────────────────┼──► reviews_Scraper (8003)
                                    │  /api/jobs/*     ───────────────────┼──► reviews_Scraper (8003)
                                    │  /api/maps/*     ───────────────────┼──► GoogleMaps (8004)
                                    │                                     │
                                    └─────────────────────────────────────┘
```

## Project Structure

```
allScrapers/
├── README.md                    # This file
├── get_cords.py                 # Utility: Get GPS coordinates from address
│
├── ScraperGateway/              # API Gateway - Single entry point
│   ├── main.py                  # FastAPI gateway with routing
│   ├── config.py                # Service configurations
│   ├── run.py                   # Start all services
│   └── README.md                # Gateway documentation
│
├── QuickComm/                   # E-commerce product search
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── api/                 # Platform-specific scrapers
│   │   │   ├── search_amazon.py
│   │   │   ├── search_flipkart.py
│   │   │   ├── search_blinkit.py
│   │   │   ├── search_zepto.py
│   │   │   ├── search_instamart.py
│   │   │   ├── search_jiomart.py
│   │   │   └── search_all.py
│   │   ├── db/                  # Database models & utilities
│   │   └── utils/               # Helper functions
│   └── *.py                     # Standalone scraper scripts
│
├── ShopifyCode/                 # Shopify store processor
│   ├── main.py                  # FastAPI application
│   └── app/
│       ├── api/
│       │   ├── shopify.py       # Main router
│       │   ├── shopify_fetcher.py
│       │   ├── shopify_llm_processor.py
│       │   └── shopify_html_fetcher.py
│       └── configs/
│
├── reviews_Scraper/             # Product review scraper
│   ├── main.py                  # FastAPI application
│   ├── api/                     # Routes & services
│   ├── scrapers/                # Amazon & Flipkart scrapers
│   └── README.md                # Detailed documentation
│
└── googlemaps/                  # Google Maps data extractor
    └── maps_scraper.py          # FastAPI with Apify integration
```

## Quick Start

### Prerequisites

- Python 3.9+
- pip
- Virtual environment (recommended)

### Installation

```bash
# Clone the repository
cd allScrapers

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies for each service
pip install fastapi uvicorn httpx requests pandas pydantic sqlalchemy

# Or install from each service's requirements.txt
pip install -r ScraperGateway/requirements.txt
pip install -r reviews_Scraper/requirements.txt
```

### Running the Platform

**Option 1: Start All Services (Recommended)**

```bash
cd ScraperGateway
python run.py
```

This starts:
- QuickComm on port 8001
- ShopifyCode on port 8002
- reviews_Scraper on port 8003
- GoogleMaps on port 8004
- Gateway on port 8080

**Option 2: Start Individual Services**

```bash
# Terminal 1 - QuickComm
cd QuickComm && uvicorn app.main:app --port 8001

# Terminal 2 - ShopifyCode
cd ShopifyCode && uvicorn main:app --port 8002

# Terminal 3 - reviews_Scraper
cd reviews_Scraper && uvicorn main:app --port 8003

# Terminal 4 - GoogleMaps
cd googlemaps && uvicorn maps_scraper:app --port 8004

# Terminal 5 - Gateway
cd ScraperGateway && uvicorn main:app --port 8080
```

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| **Gateway** | http://localhost:8080 | Main API entry point |
| **API Docs** | http://localhost:8080/docs | Swagger documentation |
| QuickComm | http://localhost:8001 | Direct e-commerce access |
| ShopifyCode | http://localhost:8002 | Direct Shopify access |
| Reviews | http://localhost:8003 | Direct reviews access |
| GoogleMaps | http://localhost:8004 | Direct maps access |

## API Reference

### Standardized Response Format

All endpoints return data in a consistent table format:

```json
{
  "headers": ["name", "price", "brand", "in_stock"],
  "rows": [
    ["Product 1", "299.00", "Brand A", "true"],
    ["Product 2", "499.00", "Brand B", "true"]
  ],
  "metadata": {
    "service": "quickcomm",
    "total_rows": 2
  }
}
```

### Quickcomm Listings (E-commerce Search)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search/amazon_fresh` | GET | Search Amazon Fresh/Now products |
| `/api/search/flipkart` | GET | Search Flipkart products |
| `/api/search/blinkit` | GET | Search Blinkit products |
| `/api/search/zepto` | GET | Search Zepto products |
| `/api/search/instamart` | GET | Search Swiggy Instamart products |
| `/api/search/jiomart` | GET | Search JioMart products |
| `/api/search/all` | POST | Search all platforms simultaneously |

**Example:**
```bash
# Search Amazon Fresh
curl "http://localhost:8080/api/search/amazon_fresh?query=chocolate&pincode=560037"

# Search Blinkit
curl "http://localhost:8080/api/search/blinkit?query=milk&coordinates=28.451,77.096"

# Search Zepto
curl "http://localhost:8080/api/search/zepto?query=bread&store_id=YOUR_STORE_ID"
```

### Shopify

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/shopify/process` | POST | Process Shopify store, get LLM-enriched CSV |

**Example:**
```bash
curl -X POST "http://localhost:8080/api/shopify/process" \
  -H "Content-Type: application/json" \
  -d '{"store_url": "https://example-store.com"}' \
  --output products.csv
```

### Reviews

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reviews/amazon` | POST | Start Amazon review scraping job |
| `/api/reviews/amazon/count` | POST | Get Amazon review count |
| `/api/reviews/flipkart` | POST | Start Flipkart review scraping job |

**Example:**
```bash
# Start Amazon review scrape
curl -X POST "http://localhost:8080/api/reviews/amazon" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.amazon.in/dp/B08N5WRWNW", "max_reviews": 100}'

# Response: {"job_id": "abc-123", "status": "pending"}

# Check job status
curl "http://localhost:8080/api/jobs/abc-123"

# Get results when complete
curl "http://localhost:8080/api/jobs/abc-123/results"
```

### Google Maps

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/maps/search` | GET | Search businesses/places |
| `/api/maps/files` | GET | List saved CSV files |
| `/api/maps/files/{filename}` | GET | Download saved CSV |

**Example:**
```bash
# Search for restaurants in Mumbai
curl "http://localhost:8080/api/maps/search?search=restaurants&location=Mumbai&max_results=50"
```

### Jobs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List all jobs |
| `/api/jobs/{job_id}` | GET | Get job status |
| `/api/jobs/{job_id}/results` | GET | Get job results |
| `/api/jobs/{job_id}` | DELETE | Cancel a job |

### Health Checks

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Gateway health |
| `/health/services` | GET | All backend services health |

## Service Management

```bash
# Start all services
cd ScraperGateway && python run.py

# Stop all services
python run.py --stop

# Check status
python run.py --status
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_PORT` | 8080 | Gateway API port |
| `QUICKCOMM_PORT` | 8001 | QuickComm service port |
| `SHOPIFY_PORT` | 8002 | Shopify service port |
| `REVIEWS_PORT` | 8003 | Reviews service port |
| `GOOGLEMAPS_PORT` | 8004 | Google Maps service port |
| `REQUEST_TIMEOUT` | 120.0 | Request timeout (seconds) |

---

## Known Limitations & TODO

### Amazon Scraper - Cookie Refresh Logic (TODO)

The Amazon scraper in `QuickComm/app/api/search_amazon.py` currently uses **hardcoded session cookies** that will expire over time. This is a known limitation that requires manual intervention.

**Current Implementation:**
```python
# QuickComm/app/api/search_amazon.py (lines 17-22)
DEFAULT_COOKIES = {
    'session-id': '525-9439529-3198566',
    'i18n-prefs': 'INR',
    'lc-acbin': 'en_IN',
    'ubid-acbin': '259-7891041-6972353',
}
```

**Issue:**
- Amazon session cookies expire after a certain period
- When expired, the scraper will fail to set delivery location or return empty results
- Currently requires manual cookie refresh from browser DevTools

**Planned Solution (To Be Implemented):**

1. **Automatic Cookie Refresh via Headless Browser**
   ```python
   # Future implementation using Playwright/Selenium
   async def refresh_amazon_cookies():
       """
       Automatically refresh Amazon session cookies using headless browser.

       Steps:
       1. Launch headless browser
       2. Navigate to amazon.in
       3. Extract fresh cookies from browser session
       4. Update DEFAULT_COOKIES or store in Redis/DB
       5. Set cookie expiry tracking
       """
       pass
   ```

2. **Cookie Health Check Endpoint**
   ```python
   @router.get("/amazon/cookie-status")
   def check_cookie_status():
       """
       Check if current cookies are valid.
       Returns: {"valid": bool, "expires_in": seconds, "last_refresh": timestamp}
       """
       pass
   ```

3. **Cookie Refresh Trigger**
   ```python
   @router.post("/amazon/refresh-cookies")
   async def trigger_cookie_refresh():
       """
       Manually trigger cookie refresh.
       Useful when automated refresh fails.
       """
       pass
   ```

4. **Scheduled Background Refresh**
   - Use APScheduler or Celery Beat for periodic cookie refresh
   - Refresh every 6-12 hours before expiry
   - Store cookies in Redis with TTL

**Workaround (Current):**

To manually refresh cookies:

1. Open Amazon.in in browser (Chrome/Firefox)
2. Open DevTools (F12) > Network tab
3. Refresh the page
4. Click on any request to amazon.in
5. Find "Cookie" in Request Headers
6. Copy the cookie values for:
   - `session-id`
   - `ubid-acbin`
   - `i18n-prefs`
   - `lc-acbin`
7. Update `DEFAULT_COOKIES` in `search_amazon.py`

**CSRF Token Note:**

The `csrf_token` parameter in the API is optional but recommended for reliable location setting:
- Extract from Amazon page: search for `csrfToken` in page source
- Pass via API: `?csrf_token=YOUR_TOKEN`
- Without it, location changes may fail silently

---

### Other Known Limitations

1. **Blinkit** - Requires valid coordinates; no automatic geocoding
2. **Zepto** - Store ID must be provided; varies by delivery location
3. **Instamart** - Rate limited; add delays between requests
4. **Google Maps** - Uses Apify (external service); requires API token

---

## Development

### Adding a New Scraper

1. Create scraper in `QuickComm/app/api/search_newplatform.py`
2. Register router in `QuickComm/app/main.py`
3. Add gateway endpoint in `ScraperGateway/main.py`
4. Update this README

### Testing

```bash
# Test health endpoints
curl http://localhost:8080/health
curl http://localhost:8080/health/services

# Test individual scrapers
curl "http://localhost:8080/api/search/amazon_fresh?query=test"
```

## License

This project is for educational and authorized testing purposes only. Ensure compliance with each platform's terms of service.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

**Note:** For detailed documentation on individual services, see their respective README files:
- [ScraperGateway/README.md](ScraperGateway/README.md)
- [reviews_Scraper/README.md](reviews_Scraper/README.md)
