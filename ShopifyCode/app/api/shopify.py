"""
Main Shopify API Router
Combines fetching and LLM processing modules.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from enum import Enum
import csv
import io
import time

# Import our modularized components
from app.api.shopify_fetcher import (
    fetch_shopify_data_from_urls,
    update_raw_content_in_rows,
    update_variant_inventory_from_stock,
    _log as fetcher_log
)
from app.api.shopify_llm_processor import (
    enrich_product_data_with_llm,
    NEW_COLUMNS,
    _log as llm_log
)
from app.api.shopify_url_scraper import (
    scrape_shopify_product_urls,
    _log as scraper_log
)
from app.api.shopify_html_fetcher import (
    fetch_html_content_for_products,
    _log as html_fetcher_log
)

router = APIRouter(prefix="/shopify", tags=["shopify"])


def _log(msg: str) -> None:
    """Lightweight debug logger for terminal visibility"""
    try:
        print(f"[shopify] {time.strftime('%H:%M:%S')} {msg}", flush=True)
    except Exception:
        pass


class ResponseFormat(str, Enum):
    json = "json"
    csv = "csv"
    processed_csv = "processed_csv"


class StoreURLRequest(BaseModel):
    """Request model for store URL endpoint"""
    store_url: HttpUrl


@router.post("/get_shopify_data")
async def get_shopify_data(
    payload: StoreURLRequest,
    format: ResponseFormat = Query(ResponseFormat.json, description="Select output format")
):
    """
    Main endpoint to fetch and process Shopify product data from a store URL.

    This endpoint:
    1. Takes a store URL as input
    2. Scrapes all product URLs from the store's /collections/all page
    3. Fetches product data from Shopify JSON API
    4. Fetches HTML content from product pages for comprehensive descriptions
    5. Enriches with LLM (if processed_csv format)
    6. Returns the data in the requested format

    Formats:
    - json: Raw JSON data from Shopify API
    - csv: Product data in CSV format (no LLM enrichment)
    - processed_csv: Product data enriched with LLM attributes
    """
    try:
        store_url = str(payload.store_url)
        _log(f"endpoint /shopify/get_shopify_data START store_url={store_url} format={format}")

        # Scrape all product URLs from the store
        _log("Scraping product URLs from store /collections/all...")
        urls = await scrape_shopify_product_urls(store_url)

        if not urls:
            raise HTTPException(status_code=404, detail={
                "error": "No product URLs found",
                "message": f"Could not find any products at {store_url}/collections/all"
            })

        _log(f"Found {len(urls)} product URLs from store")

        # For JSON format, we need to fetch raw data differently
        if format == ResponseFormat.json:
            all_json_data = []
            import requests
            from app.configs.config import HEADERS, COOKIES
            from app.api.shopify_fetcher import convert_to_json_url

            for idx, url in enumerate(urls, start=1):
                try:
                    _log(f"[{idx}/{len(urls)}] processing url={url}")
                    request_url = convert_to_json_url(url)
                    response = requests.get(request_url, headers=HEADERS, cookies=COOKIES, timeout=30)
                    response.raise_for_status()

                    content = response.text.strip()
                    if not content or not content.startswith('{'):
                        continue

                    try:
                        json_data = response.json()
                    except ValueError:
                        import json as _json
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_data = _json.loads(content[json_start:json_end])
                        else:
                            continue

                    all_json_data.append({
                        "url": url,
                        "data": json_data
                    })

                except Exception as e:
                    _log(f"ERROR processing url={url} err={str(e)[:200]}")
                    continue

            # Return JSON response
            resp_payload = {
                "summary": {
                    "total_urls_processed": len(all_json_data),
                    "total_urls_found": len(urls)
                },
                "data": all_json_data
            }
            _log(f"returning JSON total_urls_processed={len(all_json_data)} of {len(urls)}")
            return resp_payload

        # For CSV formats, fetch and extract product data
        _log("Step 1/3: Fetching product data from Shopify JSON API...")
        all_product_rows = fetch_shopify_data_from_urls(urls)

        if not all_product_rows:
            raise HTTPException(status_code=404, detail={
                "error": "No product data found in any of the URLs"
            })

        _log(f"Fetched {len(all_product_rows)} product rows")

        # Step 2: Fetch HTML content for raw_content field and stock information
        _log("Step 2/3: Fetching HTML content and stock info for products...")
        html_content_map, stock_info_map = fetch_html_content_for_products(urls)
        all_product_rows = update_raw_content_in_rows(all_product_rows, html_content_map)
        all_product_rows = update_variant_inventory_from_stock(all_product_rows, stock_info_map)
        _log(f"Updated raw_content and variant inventory for products")

        # Get fieldnames from the first row
        fieldnames = list(all_product_rows[0].keys()) if all_product_rows else []

        # Step 3: If processed_csv requested, enrich via LLM
        if format == ResponseFormat.processed_csv:
            _log("Step 3/3: Starting LLM enrichment for processed_csv")

            # Ensure new columns exist in fieldnames
            for col in NEW_COLUMNS:
                if col not in fieldnames:
                    fieldnames.append(col)

            # Enrich data with LLM
            all_product_rows = await enrich_product_data_with_llm(
                all_product_rows,
                detect_colors_from_images=True
            )

            _log("LLM enrichment completed")

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_product_rows)

        # Prepare CSV for download
        output.seek(0)
        csv_content = output.getvalue()
        output.close()

        # Create filename based on store name
        from urllib.parse import urlparse
        store_name = urlparse(store_url).netloc.replace('.', '_')
        filename = f"{store_name}_products_data.csv" if format == ResponseFormat.csv else f"{store_name}_products_processed.csv"

        _log(f"returning CSV rows={len(all_product_rows)} filename={filename}")
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        _log(f"endpoint ERROR {str(e)[:200]}")
        import traceback
        _log(f"Traceback: {traceback.format_exc()[:500]}")
        raise HTTPException(status_code=500, detail={
            "error": "Internal server error",
            "message": str(e)
        })


@router.post("/process_store")
async def process_store(
    payload: StoreURLRequest,
    format: ResponseFormat = Query(ResponseFormat.processed_csv, description="Select output format")
):
    """
    Process an entire Shopify store by automatically discovering all products.

    This endpoint:
    1. Scrapes all product URLs from the store's /collections/all page
    2. Fetches product data from Shopify JSON API
    3. Fetches HTML content from product pages for comprehensive descriptions
    4. Enriches with LLM (if processed_csv format)
    5. Returns the data in the requested format

    Args:
        payload: Store URL (e.g., "https://example.com")
        format: Output format (json, csv, or processed_csv)

    Returns:
        Product data in the requested format
    """
    try:
        store_url = str(payload.store_url)
        _log(f"endpoint /shopify/process_store START store_url={store_url} format={format}")

        # Step 1: Scrape all product URLs from the store
        _log("Step 1/3: Scraping product URLs from store...")
        product_urls = await scrape_shopify_product_urls(store_url)

        if not product_urls:
            raise HTTPException(status_code=404, detail={
                "error": "No product URLs found",
                "message": f"Could not find any products at {store_url}/collections/all"
            })

        _log(f"Found {len(product_urls)} product URLs")

        # For JSON format, return just the URLs
        if format == ResponseFormat.json:
            _log(f"returning JSON with {len(product_urls)} URLs")
            return {
                "store_url": store_url,
                "total_products": len(product_urls),
                "product_urls": product_urls
            }

        # Step 2: Fetch product data from all URLs
        _log(f"Step 2/4: Fetching product data from {len(product_urls)} URLs...")
        all_product_rows = fetch_shopify_data_from_urls(product_urls)

        if not all_product_rows:
            raise HTTPException(status_code=404, detail={
                "error": "No product data found",
                "message": "Could not extract product data from the URLs"
            })

        _log(f"Fetched {len(all_product_rows)} product rows")

        # Step 3: Fetch HTML content for raw_content field and stock information
        _log("Step 3/4: Fetching HTML content and stock info for products...")
        html_content_map, stock_info_map = fetch_html_content_for_products(product_urls)
        all_product_rows = update_raw_content_in_rows(all_product_rows, html_content_map)
        all_product_rows = update_variant_inventory_from_stock(all_product_rows, stock_info_map)
        _log(f"Updated raw_content and variant inventory for products")

        # Get fieldnames from the first row
        fieldnames = list(all_product_rows[0].keys()) if all_product_rows else []

        # Step 4: If processed_csv requested, enrich via LLM
        if format == ResponseFormat.processed_csv:
            _log("Step 4/4: Starting LLM enrichment...")

            # Ensure new columns exist in fieldnames
            for col in NEW_COLUMNS:
                if col not in fieldnames:
                    fieldnames.append(col)

            # Enrich data with LLM
            all_product_rows = await enrich_product_data_with_llm(
                all_product_rows,
                detect_colors_from_images=True
            )

            _log("LLM enrichment completed")
        else:
            _log("Step 4/4: Skipping LLM enrichment (csv format)")

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_product_rows)

        # Prepare CSV for download
        output.seek(0)
        csv_content = output.getvalue()
        output.close()

        # Create filename based on store name
        from urllib.parse import urlparse
        store_name = urlparse(store_url).netloc.replace('.', '_')
        filename = f"{store_name}_products_data.csv" if format == ResponseFormat.csv else f"{store_name}_products_processed.csv"

        _log(f"returning CSV rows={len(all_product_rows)} filename={filename}")
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        _log(f"endpoint ERROR {str(e)[:200]}")
        import traceback
        _log(f"Traceback: {traceback.format_exc()[:500]}")
        raise HTTPException(status_code=500, detail={
            "error": "Internal server error",
            "message": str(e)
        })
