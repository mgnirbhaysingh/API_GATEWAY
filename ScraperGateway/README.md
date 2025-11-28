# Universal Scraper API

A unified API that provides a single entry point for all scraping services.

## Standardized Response Format

All endpoints return data in a consistent table format (like CSV in JSON):

```json
{
  "headers": ["column1", "column2", "column3"],
  "rows": [
    ["value1", "value2", "value3"],
    ["value4", "value5", "value6"]
  ],
  "metadata": {
    "service": "quickcomm",
    "total_rows": 2
  }
}
```

This format makes it easy to:
- Display data in tables/grids
- Convert to CSV/Excel
- Process with pandas: `pd.DataFrame(response["rows"], columns=response["headers"])`

## Architecture

```
Client Request
      │
      ▼
┌─────────────────────────────────────┐
│     Universal Scraper API           │
│         (Port 8080)                 │
│                                     │
│  /api/search/*     ──────────────►  │ ──► QuickComm (8001)
│  /api/shopify/*    ──────────────►  │ ──► ShopifyCode (8002)
│  /api/reviews/*    ──────────────►  │ ──► reviews_Scraper (8003)
│  /api/jobs/*       ──────────────►  │ ──► reviews_Scraper (8003)
│  /api/maps/*       ──────────────►  │ ──► GoogleMaps (8004)
│                                     │
└─────────────────────────────────────┘

Clients only see: /api/*
They don't know about the underlying services.
```

## Quick Start

```bash
cd ScraperGateway
pip install -r requirements.txt
python run.py
```

Access the API at: **http://localhost:8080**

API Documentation: **http://localhost:8080/docs**

## API Endpoints

### Search
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search/amazon` | GET | Search Amazon products |
| `/api/search/flipkart` | GET | Search Flipkart products |
| `/api/search/blinkit` | GET | Search Blinkit products |
| `/api/search/zepto` | GET | Search Zepto products |
| `/api/search/instamart` | GET | Search Instamart products |
| `/api/search/jiomart` | GET | Search JioMart products |
| `/api/search/all` | POST | Search all platforms |

### Shopify
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/shopify/process` | POST | Process store, get LLM-enriched CSV |

### Reviews
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reviews/amazon` | POST | Scrape Amazon reviews |
| `/api/reviews/amazon/count` | POST | Get Amazon review count |
| `/api/reviews/flipkart` | POST | Scrape Flipkart reviews |

### Google Maps
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/maps/search` | GET | Search businesses/places |
| `/api/maps/files` | GET | List saved CSV files |
| `/api/maps/files/{filename}` | GET | Download saved CSV |

### Jobs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/jobs` | GET | List all jobs |
| `/api/jobs/{job_id}` | GET | Get job status |
| `/api/jobs/{job_id}/results` | GET | Get job results |
| `/api/jobs/{job_id}` | DELETE | Cancel a job |

### Health
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | API health check |
| `/health/services` | GET | Backend services health |

## Examples

### Search Products

```bash
# Amazon
curl "http://localhost:8080/api/search/amazon?query=chocolate&pincode=560037"

# Flipkart
curl "http://localhost:8080/api/search/flipkart?query=laptop&pincode=110001"

# Blinkit
curl "http://localhost:8080/api/search/blinkit?query=milk&coordinates=28.451,77.096"

# Zepto
curl "http://localhost:8080/api/search/zepto?query=bread"

# Instamart
curl "http://localhost:8080/api/search/instamart?query=eggs&lat=12.9716&lng=77.5946"

# JioMart
curl "http://localhost:8080/api/search/jiomart?query=rice&pincode=400001"
```

### Shopify

```bash
curl -X POST "http://localhost:8080/api/shopify/process" \
  -H "Content-Type: application/json" \
  -d '{"store_url": "https://example-store.com"}' \
  --output products.csv
```

### Reviews

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

### Flipkart Reviews

```bash
curl -X POST "http://localhost:8080/api/reviews/flipkart" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.flipkart.com/product-name/p/item123"}'
```

### Google Maps

```bash
# Search for restaurants in Mumbai
curl "http://localhost:8080/api/maps/search?search=restaurants&location=Mumbai&max_results=50"

# Get CSV output
curl "http://localhost:8080/api/maps/search?search=hotels&location=Delhi&output_format=csv" --output hotels.csv

# List saved files
curl "http://localhost:8080/api/maps/files"
```

## Management

```bash
# Start all services
python run.py

# Stop all services
python run.py --stop

# Check status
python run.py --status
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_PORT` | 8080 | API port |
| `QUICKCOMM_PORT` | 8001 | QuickComm service port |
| `SHOPIFY_PORT` | 8002 | Shopify service port |
| `REVIEWS_PORT` | 8003 | Reviews service port |
| `GOOGLEMAPS_PORT` | 8004 | Google Maps service port |
