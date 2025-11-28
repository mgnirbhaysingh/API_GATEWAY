"""
Universal Scraper API
A unified API gateway that presents all scraper services as a single cohesive API.

Clients see only:
    /api/search/amazon
    /api/search/flipkart
    /api/shopify/process
    /api/reviews/amazon
    /api/jobs/{job_id}

They don't know about the underlying services.
"""

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from contextlib import asynccontextmanager
import httpx
import asyncio
import time
import json
from typing import Optional, List, Dict, Any
import logging

from config import SERVICES, GATEWAY_HOST, GATEWAY_PORT, REQUEST_TIMEOUT, CONNECT_TIMEOUT


def to_table_format(data: Any, metadata: Dict = None) -> Dict:
    """
    Convert API response to standardized table format.

    Input can be:
    - List of dicts: [{"name": "A", "price": 10}, ...]
    - Dict with "items" key: {"items": [...], "count": 5}
    - Already in table format: {"headers": [...], "rows": [...]}

    Output:
    {
        "headers": ["name", "price", ...],
        "rows": [["A", "10", ...], ...],
        "metadata": {}
    }
    """
    if metadata is None:
        metadata = {}

    # Already in table format
    if isinstance(data, dict) and "headers" in data and "rows" in data:
        if "metadata" not in data:
            data["metadata"] = metadata
        return data

    # Extract items from common wrapper formats
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # Try common keys that contain the actual data
        for key in ["items", "data", "results", "products", "reviews"]:
            if key in data and isinstance(data[key], list):
                items = data[key]
                # Add other dict keys to metadata
                for k, v in data.items():
                    if k != key and not isinstance(v, (list, dict)):
                        metadata[k] = v
                break

        # If no list found, treat the dict itself as a single row
        if not items and data:
            items = [data]

    if not items:
        return {"headers": [], "rows": [], "metadata": metadata}

    # Get all unique keys as headers (preserve order)
    headers = []
    for item in items:
        if isinstance(item, dict):
            for key in item.keys():
                if key not in headers:
                    headers.append(key)

    # Convert items to rows
    rows = []
    for item in items:
        if isinstance(item, dict):
            row = []
            for header in headers:
                value = item.get(header, "")
                # Convert to string
                if isinstance(value, (dict, list)):
                    value = json.dumps(value) if value else ""
                elif value is None:
                    value = ""
                else:
                    value = str(value)
                row.append(value)
            rows.append(row)

    metadata["total_rows"] = len(rows)

    return {
        "headers": headers,
        "rows": rows,
        "metadata": metadata
    }

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api")

# Global HTTP client
http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - manage HTTP client."""
    global http_client

    logger.info("=" * 60)
    logger.info("Universal Scraper API Starting...")
    logger.info("=" * 60)

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        follow_redirects=True
    )

    logger.info(f"API ready at http://{GATEWAY_HOST}:{GATEWAY_PORT}")
    logger.info("=" * 60)

    yield

    logger.info("Shutting down...")
    await http_client.aclose()


app = FastAPI(
    title="Universal Scraper API",
    description="""
## Unified Scraper API

A single API for all your scraping needs.

### Product Search
Search products across multiple e-commerce platforms:
- `GET /api/search/amazon` - Amazon products
- `GET /api/search/flipkart` - Flipkart products
- `GET /api/search/blinkit` - Blinkit quick commerce
- `GET /api/search/zepto` - Zepto quick commerce
- `GET /api/search/instamart` - Swiggy Instamart
- `GET /api/search/jiomart` - JioMart products
- `POST /api/search/all` - Search all platforms at once

### Shopify
- `POST /api/shopify/process` - Process Shopify store, get LLM-enriched CSV

### Reviews
- `POST /api/reviews/amazon` - Scrape Amazon reviews (async job)
- `POST /api/reviews/amazon/count` - Get Amazon review count
- `POST /api/reviews/flipkart` - Scrape Flipkart reviews (async job)

### Google Maps
- `GET /api/maps/search` - Search Google Maps for businesses/places
- `GET /api/maps/files` - List saved CSV files
- `GET /api/maps/files/{filename}` - Download a saved CSV

### Jobs
- `GET /api/jobs` - List all scraping jobs
- `GET /api/jobs/{job_id}` - Get job status
- `GET /api/jobs/{job_id}/results` - Get job results
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


@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


# ============== Helper Functions ==============

async def forward_request(
    service_name: str,
    backend_path: str,
    request: Request,
    method: str = None,
    transform: bool = True
) -> Response:
    """
    Forward request to a backend service.

    Args:
        service_name: Name of the backend service
        backend_path: Path on the backend
        request: FastAPI request object
        method: Override HTTP method
        transform: Whether to transform JSON response to table format
    """
    config = SERVICES[service_name]
    url = f"{config.base_url}{backend_path}"

    # Add query params
    if request.query_params:
        url = f"{url}?{request.query_params}"

    logger.info(f"-> {method or request.method} {url}")

    try:
        body = None
        if (method or request.method) in ["POST", "PUT", "PATCH"]:
            body = await request.body()

        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length", "transfer-encoding", "connection")
        }

        response = await http_client.request(
            method=method or request.method,
            url=url,
            content=body,
            headers=headers
        )

        content_type = response.headers.get("content-type", "")

        # Pass through non-JSON responses (CSV, files, etc.)
        if "text/csv" in content_type or "application/octet-stream" in content_type:
            return StreamingResponse(
                iter([response.content]),
                status_code=response.status_code,
                media_type=content_type,
                headers={
                    k: v for k, v in response.headers.items()
                    if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
                }
            )

        # Transform JSON responses to table format
        if transform and "application/json" in content_type:
            try:
                data = response.json()
                table_data = to_table_format(data, {"service": service_name})
                return JSONResponse(content=table_data, status_code=response.status_code)
            except Exception as e:
                logger.warning(f"Failed to transform response: {e}")
                # Fall through to return raw response

        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=content_type or "application/json"
        )

    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        logger.exception(f"Error: {e}")
        raise HTTPException(status_code=502, detail=str(e))


# ============== Root & Health ==============

@app.get("/", tags=["Info"])
async def root():
    """API information and available endpoints."""
    return {
        "name": "Universal Scraper API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "search": {
                "amazon": "GET /api/search/amazon?query=...",
                "flipkart": "GET /api/search/flipkart?query=...",
                "blinkit": "GET /api/search/blinkit?query=...",
                "zepto": "GET /api/search/zepto?query=...",
                "instamart": "GET /api/search/instamart?query=...",
                "jiomart": "GET /api/search/jiomart?query=...",
                "all": "POST /api/search/all"
            },
            "shopify": {
                "process": "POST /api/shopify/process"
            },
            "reviews": {
                "amazon": "POST /api/reviews/amazon",
                "amazon_count": "POST /api/reviews/amazon/count",
                "flipkart": "POST /api/reviews/flipkart"
            },
            "maps": {
                "search": "GET /api/maps/search?search=...&location=...",
                "files": "GET /api/maps/files",
                "download": "GET /api/maps/files/{filename}"
            },
            "jobs": {
                "list": "GET /api/jobs",
                "status": "GET /api/jobs/{job_id}",
                "results": "GET /api/jobs/{job_id}/results"
            }
        }
    }


@app.get("/health", tags=["Health"])
async def health():
    """Health check."""
    return {"status": "healthy"}


@app.get("/health/services", tags=["Health"])
async def services_health():
    """Check health of all backend services."""
    results = {}

    for name, config in SERVICES.items():
        url = f"{config.base_url}{config.health_endpoint}"
        try:
            resp = await http_client.get(url, timeout=5.0)
            results[name] = {"status": "healthy" if resp.status_code == 200 else "unhealthy"}
        except Exception as e:
            results[name] = {"status": "unreachable", "error": str(e)}

    all_healthy = all(r["status"] == "healthy" for r in results.values())
    return {"status": "healthy" if all_healthy else "degraded", "services": results}


# ============== SEARCH ENDPOINTS ==============

@app.get("/api/search/amazon_fresh", tags=["Quickcomm Listings"])
async def search_amazon(
    request: Request,
    query: str = Query(..., description="Search query (required)"),
    pincode: str = Query("560037", description="Delivery pincode"),
    store: str = Query("nowstore", description="Store context ('nowstore' for Amazon Fresh)"),
    max_pages: int = Query(5, description="Maximum pages to scrape")
):
    """Search products on Amazon India."""
    return await forward_request("quickcomm", "/amazon/search", request)


@app.get("/api/search/flipkart", tags=["Quickcomm Listings"])
async def search_flipkart(
    request: Request,
    query: str = Query(..., description="Search query"),
    pincode: str = Query("560037", description="Delivery pincode"),
    max_pages: int = Query(5, description="Maximum pages to scrape")
):
    """Search products on Flipkart."""
    return await forward_request("quickcomm", "/flipkart/search", request)


@app.get("/api/search/blinkit", tags=["Quickcomm Listings"])
async def search_blinkit(
    request: Request,
    query: str = Query(..., description="Search query"),
    coordinates: str = Query("28.451,77.096", description="Lat,Long coordinates")
):
    """Search products on Blinkit."""
    return await forward_request("quickcomm", "/blinkit/search", request)


@app.get("/api/search/zepto", tags=["Quickcomm Listings"])
async def search_zepto(
    request: Request,
    query: str = Query(..., description="Search query"),
    store_id: str = Query("4bbfd2a7-633f-40bf-91e3-3cfdd08fd6cc", description="Store ID"),
    max_pages: int = Query(10, description="Maximum pages to scrape")
):
    """Search products on Zepto."""
    return await forward_request("quickcomm", "/zepto/search", request)


@app.get("/api/search/instamart", tags=["Quickcomm Listings"])
async def search_instamart(
    request: Request,
    query: str = Query(..., description="Search query"),
    lat: str = Query("12.9716", description="Latitude"),
    lng: str = Query("77.5946", description="Longitude"),
    max_pages: int = Query(10, description="Maximum pages to scrape")
):
    """Search products on Swiggy Instamart."""
    return await forward_request("quickcomm", "/instamart/search", request)


@app.get("/api/search/jiomart", tags=["Quickcomm Listings"])
async def search_jiomart(
    request: Request,
    query: str = Query(..., description="Search query"),
    pincode: str = Query("560037", description="Delivery pincode"),
    max_pages: int = Query(5, description="Maximum pages to scrape")
):
    """Search products on JioMart."""
    return await forward_request("quickcomm", "/jiomart/search", request)


@app.post("/api/search/all", tags=["Quickcomm Listings"])
async def search_all(request: Request):
    """
    Search across all platforms simultaneously.

    Request body should contain search parameters for each platform.
    """
    return await forward_request("quickcomm", "/search/all", request)


# ============== SHOPIFY ENDPOINTS ==============

@app.post("/api/shopify/process", tags=["Shopify"])
async def shopify_process(request: Request):
    """
    Process a Shopify store and get LLM-enriched product data as CSV.

    **Request Body:**
    ```json
    {
        "store_url": "https://example-store.com"
    }
    ```

    **Returns:** CSV file with product data including LLM-enriched attributes.
    """
    return await forward_request("shopify", "/shopify/process_store", request)


# ============== REVIEWS ENDPOINTS ==============

@app.post("/api/reviews/amazon", tags=["Reviews"])
async def reviews_amazon(request: Request):
    """
    Start an Amazon review scraping job.

    **Request Body:**
    ```json
    {
        "url": "https://www.amazon.in/dp/PRODUCT_ID",
        "max_reviews": 500
    }
    ```

    **Returns:** Job ID to track progress.
    """
    return await forward_request("reviews", "/api/v1/amazon/reviews", request)


@app.post("/api/reviews/amazon/count", tags=["Reviews"])
async def reviews_amazon_count(request: Request):
    """
    Get total review count for an Amazon product.

    **Request Body:**
    ```json
    {
        "url": "https://www.amazon.in/dp/PRODUCT_ID"
    }
    ```
    """
    return await forward_request("reviews", "/api/v1/amazon/count", request)


@app.post("/api/reviews/flipkart", tags=["Reviews"])
async def reviews_flipkart(request: Request):
    """
    Start a Flipkart review scraping job.

    **Request Body:**
    ```json
    {
        "url": "https://www.flipkart.com/product-url"
    }
    ```

    **Returns:** Job ID to track progress.
    """
    return await forward_request("reviews", "/api/v1/flipkart/reviews", request)


# ============== GOOGLE MAPS ENDPOINTS ==============

@app.get("/api/maps/search", tags=["Google Maps"])
async def maps_search(
    request: Request,
    search: str = Query(..., description="Search term (e.g., 'restaurants', 'hotels')"),
    location: str = Query(..., description="Location (e.g., 'Mumbai', 'Delhi')"),
    max_results: int = Query(100, description="Maximum results (1-10000)"),
    language: str = Query("en", description="Language code"),
    skip_closed: bool = Query(False, description="Skip permanently closed places"),
    output_format: str = Query("json", description="Output: 'json' or 'csv'"),
    save_to_server: bool = Query(False, description="Save CSV to server")
):
    """
    Search Google Maps for businesses and places.

    **Example:** `/api/maps/search?search=restaurants&location=Mumbai&max_results=50`

    Returns business listings with name, address, phone, ratings, reviews, etc.
    """
    return await forward_request("googlemaps", "/run-google-maps", request)


@app.get("/api/maps/files", tags=["Google Maps"])
async def maps_list_files(request: Request):
    """List all saved CSV files from previous searches."""
    return await forward_request("googlemaps", "/list-saved-files", request)


@app.get("/api/maps/files/{filename}", tags=["Google Maps"])
async def maps_download_file(filename: str, request: Request):
    """Download a previously saved CSV file."""
    return await forward_request("googlemaps", f"/download-csv/{filename}", request)


# ============== JOBS ENDPOINTS ==============

@app.get("/api/jobs", tags=["Jobs"])
async def list_jobs(request: Request):
    """List all scraping jobs."""
    return await forward_request("reviews", "/api/v1/jobs", request)


@app.get("/api/jobs/{job_id}", tags=["Jobs"])
async def get_job(job_id: str, request: Request):
    """Get status of a specific job."""
    return await forward_request("reviews", f"/api/v1/jobs/{job_id}", request, transform=False)


@app.get("/api/jobs/{job_id}/results", tags=["Jobs"])
async def get_job_results(job_id: str, request: Request):
    """Get results of a completed job."""
    return await forward_request("reviews", f"/api/v1/jobs/{job_id}/results", request)


@app.delete("/api/jobs/{job_id}", tags=["Jobs"])
async def cancel_job(job_id: str, request: Request):
    """Cancel a running job."""
    return await forward_request("reviews", f"/api/v1/jobs/{job_id}", request, method="DELETE", transform=False)


# ============== Main ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=GATEWAY_HOST, port=GATEWAY_PORT, reload=True)
