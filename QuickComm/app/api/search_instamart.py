from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import requests
import logging
import re
import os

from ..db.models import Product
from ..db.utils import save_products_to_db
from ..utils.format_utils import model_to_dict

router = APIRouter()
logger = logging.getLogger(__name__)

INSTAMART_IMAGE_PREFIX = "https://instamart-media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,h_600/"

# Global token cache
_cached_waf_token = None


def get_token_playwright() -> Optional[str]:
    """
    Use Playwright to get a fresh AWS WAF token from Swiggy.
    Requires: playwright and a valid instamart_cookies.json file.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None

    token_holder = {"value": None}

    def on_request(req):
        url = req.url or ""
        if "instamart/home" in url:
            try:
                headers = getattr(req, "headers", None) or req.all_headers()
            except Exception:
                headers = {}
            cookie_header = headers.get("cookie", "") or headers.get("Cookie", "")
            m = re.search(r"aws-waf-token=([^;,\s]+)", cookie_header)
            if m:
                token_holder["value"] = m.group(1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--window-position=0,0',
                    '--window-size=1280,720'
                ]
            )

            # Check if cookies file exists
            cookies_file = "instamart_cookies.json"
            if os.path.exists(cookies_file):
                context = browser.new_context(
                    storage_state=cookies_file,
                    viewport={'width': 1280, 'height': 720}
                )
            else:
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720}
                )

            context.on("request", on_request)

            page = context.new_page()
            page.goto("https://www.swiggy.com/instamart", wait_until="domcontentloaded")
            page.mouse.wheel(0, 300)

            try:
                page.wait_for_request(lambda r: "instamart/home" in (r.url or ""), timeout=10000)
                page.wait_for_response(lambda r: "instamart/home" in (r.url or ""), timeout=10000)
            except Exception:
                pass

            if not token_holder["value"]:
                for _ in range(10):
                    for c in context.cookies():
                        if c.get("name") == "aws-waf-token" and c.get("value"):
                            token_holder["value"] = c["value"]
                            break
                    if token_holder["value"]:
                        break
                    page.wait_for_timeout(300)

            page.wait_for_timeout(300)
            browser.close()

            return token_holder["value"]

    except Exception as e:
        logger.error(f"Error getting WAF token via Playwright: {e}")
        return None


def get_waf_token(force_refresh: bool = False) -> Optional[str]:
    """Get WAF token, using cached value if available."""
    global _cached_waf_token

    if force_refresh or _cached_waf_token is None:
        logger.info("Fetching fresh AWS WAF token...")
        _cached_waf_token = get_token_playwright()
        if _cached_waf_token:
            logger.info(f"Got WAF token: {_cached_waf_token[:20]}...")

    return _cached_waf_token


def extract_instamart_products(
    data_response: Dict,
    search_query: str,
    store_id: str,
    page_num: int = 0
) -> List[Product]:
    """
    Extract products from Instamart search response and convert to Product model.
    """
    products = []

    data = (data_response or {}).get("data", {})
    cards = data.get("cards", [])

    for card_wrap in cards:
        card = (card_wrap or {}).get("card", {}).get("card", {})
        items = (
            card.get("gridElements", {})
                .get("infoWithStyle", {})
                .get("items", [])
        )
        for item in items:
            product_id = item.get("productId")
            item_display = item.get("displayName")
            item_brand = item.get("brand")
            variations = item.get("variations", []) or []

            for var in variations:
                sku_id = var.get("skuId")
                variant_display = var.get("displayName") or item_display
                variant_brand = var.get("brandName") or item_brand

                price = var.get("price", {}) or {}
                mrp_units = price.get("mrp", {}).get("units")
                offer_units = price.get("offerPrice", {}).get("units")

                inventory_allowed = (var.get("cartAllowedQuantity", {}) or {}).get("allowedQuantity")
                in_stock = (var.get("inventory", {}) or {}).get("inStock")
                quantity = var.get("quantityDescription")
                category = var.get("category") or item.get("category")
                sub_category = var.get("subCategoryType") or item.get("subCategoryType")
                rank = item.get("analytics", {}).get("position")

                media_ids = [m.get("id") for m in (var.get("medias") or []) if isinstance(m, dict) and m.get("id")]
                image_ids = list(var.get("imageIds") or [])
                seen = set()
                images_list = []
                for _id in image_ids + media_ids:
                    if _id and _id not in seen:
                        seen.add(_id)
                        images_list.append(INSTAMART_IMAGE_PREFIX + _id)

                try:
                    products.append(Product(
                        platform='instamart',
                        search_query=search_query,
                        store_id=store_id,
                        product_id=str(product_id) if product_id else '',
                        variant_id=str(sku_id) if sku_id else '',
                        name=variant_display or '',
                        brand=variant_brand or '',
                        mrp=float(mrp_units) if mrp_units is not None else None,
                        price=float(offer_units) if offer_units is not None else 0,
                        quantity=quantity or '',
                        in_stock=in_stock if in_stock is not None else False,
                        inventory=inventory_allowed,
                        max_allowed_quantity=inventory_allowed,
                        category=category,
                        sub_category=sub_category,
                        images=images_list,
                        organic_rank=rank,
                        page=page_num,
                    ))
                except Exception as e:
                    logger.error(f"Error creating product: {e}")
                    continue

    return products


def fetch_instamart_data(
    query: str,
    store_id: str,
    lat: str,
    lng: str,
    offset: int = 0,
    aws_waf_token: Optional[str] = None
) -> Dict:
    """
    Fetch data from Instamart search API.
    """
    global _cached_waf_token

    # Get token if not provided
    if not aws_waf_token:
        aws_waf_token = get_waf_token()

    url = f"https://www.swiggy.com/api/instamart/search/v2?offset={offset}&ageConsent=false&voiceSearchTrackingId=&storeId={store_id}&primaryStoreId={store_id}&secondaryStoreId="

    headers = {
        "accept": "*/*",
        "accept-language": "en-GB,en;q=0.5",
        "content-type": "application/json",
        "matcher": "addce8ecfeeacfb987ad7e7",
        "origin": "https://www.swiggy.com",
        "priority": "u=1, i",
        "referer": f"https://www.swiggy.com/instamart/search?custom_back=true&query={query}",
        "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Brave";v="140"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "sec-gpc": "1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "x-build-version": "2.297.0",
    }

    cookies = {
        "__SW": "ZG54_yum0Yur8QOrIKhpO6pezekMBgLi",
        "_device_id": "a623544e-9d5b-8e93-51c9-91b1c418c3a8",
        "deviceId": "s%3Aa623544e-9d5b-8e93-51c9-91b1c418c3a8.53UqHyVquomHYBHMOTGszfqRymDEl1qs5bFisYdf%2F2s",
        "versionCode": "1200",
        "platform": "web",
        "subplatform": "dweb",
        "statusBarHeight": "0",
        "bottomOffset": "0",
        "genieTrackOn": "false",
        "ally-on": "false",
        "isNative": "false",
        "strId": "",
        "openIMHP": "false",
        "LocSrc": "s%3AswgyUL.Dzm1rLPIhJmB3Tl2Xs6141hVZS0ofGP7LGmLXgQOA7Y",
        "webBottomBarHeight": "0",
        "_is_logged_in": "1",
        "_session_tid": "",
        "tid": "",
        "addressId": "",
        "fontsLoaded": "1",
        "dadl": "true",
        "lat": lat,
        "lng": lng,
        "address": "",
        "userLocation": '',
        "sid": "",
        "imOrderAttribution": f'{{"entryId":"{query}","entryName":"instamartOpenSearch"}}',
    }

    if aws_waf_token:
        cookies["aws-waf-token"] = aws_waf_token

    payload = {
        "facets": [],
        "sortAttribute": "",
        "query": query,
        "search_results_offset": offset,
        "page_type": "INSTAMART_SEARCH_PAGE",
        "is_pre_search_tag": False,
    }

    response = requests.post(url, headers=headers, cookies=cookies, json=payload, timeout=30)

    # If request fails, try refreshing the token
    if response.status_code != 200:
        logger.warning(f"Request failed with status {response.status_code}, refreshing token...")
        new_token = get_waf_token(force_refresh=True)
        if new_token:
            cookies["aws-waf-token"] = new_token
            response = requests.post(url, headers=headers, cookies=cookies, json=payload, timeout=30)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to fetch data from Instamart API: {response.text[:500]}"
        )

    data = response.json()

    # Check for error response and retry with fresh token
    if isinstance(data, dict) and data.get('statusCode') == 'ERR_NON_2XX_3XX_RESPONSE':
        logger.warning("API returned error response, refreshing token...")
        new_token = get_waf_token(force_refresh=True)
        if new_token:
            cookies["aws-waf-token"] = new_token
            response = requests.post(url, headers=headers, cookies=cookies, json=payload, timeout=30)
            data = response.json()

    return data


@router.get("/instamart/search")
def search_instamart(
    query: str = "chocolate",
    store_id: str = "1234567",
    lat: str = "12.9716",
    lng: str = "77.5946",
    max_pages: int = 10,
    aws_waf_token: Optional[str] = None,
    save_to_db: bool = False
) -> List[Dict[str, Any]]:
    """
    Search for products on Swiggy Instamart.

    Args:
        query: Search query string
        store_id: Instamart store ID for your location
        lat: Latitude of the location
        lng: Longitude of the location
        max_pages: Maximum pages to fetch (default: 10)
        aws_waf_token: AWS WAF token (optional - will be fetched automatically via Playwright if not provided)
        save_to_db: Whether to save results to database

    Returns:
        List of product dictionaries

    Note:
        This endpoint requires Playwright to be installed for automatic token fetching.
        Run: pip install playwright && playwright install chromium
        Optionally place 'instamart_cookies.json' in the root directory for better reliability.
    """
    all_products = []
    search_result_offset = 0

    try:
        for page_num in range(max_pages):
            logger.info(f"Fetching page {page_num}, offset {search_result_offset}")

            data_response = fetch_instamart_data(
                query=query,
                store_id=store_id,
                lat=lat,
                lng=lng,
                offset=search_result_offset,
                aws_waf_token=aws_waf_token
            )

            # Check for error response
            if isinstance(data_response, dict) and data_response.get('statusCode') == 'ERR_NON_2XX_3XX_RESPONSE':
                logger.warning("API returned error response, stopping pagination")
                break

            products = extract_instamart_products(
                data_response,
                search_query=query,
                store_id=store_id,
                page_num=page_num
            )

            if not products:
                logger.info(f"No products found on page {page_num}, stopping pagination")
                break

            all_products.extend(products)
            logger.info(f"Found {len(products)} products on page {page_num}")

            # Get next offset
            new_offset = data_response.get("data", {}).get("searchResultsOffset")
            if new_offset is not None and new_offset != 0:
                search_result_offset = new_offset
            else:
                logger.info("No more results, stopping pagination")
                break

        if save_to_db and all_products:
            save_products_to_db(all_products, "products")

        exclude_fields = ["id", "created_at", "updated_at"]
        return [model_to_dict(product, exclude_fields=exclude_fields) for product in all_products]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing Instamart search: {str(e)}"
        )
