from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import hashlib
import json
import uuid
import time
from curl_cffi import requests

from ..db.models import Product
from ..db.utils import save_products_to_db
from ..utils.format_utils import model_to_dict

router = APIRouter()


def generate_signature(method, url, request_id, device_id, secret, body=None):
    """
    Generate request signature based on Zepto's JavaScript implementation.
    """
    sig_obj = {
        "method": method.lower(),
        "url": url,
        "requestId": request_id,
        "deviceId": device_id,
        "secret": secret,
    }

    if body and method.lower() != "get":
        if isinstance(body, dict):
            sig_obj["body"] = json.dumps(body, separators=(',', ':'))
        else:
            sig_obj["body"] = body

    sorted_keys = sorted(sig_obj.keys())
    signature_string = "|".join(str(sig_obj[key]) for key in sorted_keys)
    signature_hash = hashlib.sha256(signature_string.encode()).hexdigest()

    return signature_hash


def generate_timezone_hash(signature):
    """Generate x-timezone header by hashing the signature."""
    return hashlib.sha256(signature.encode()).hexdigest()


def zepto_search(query: str, page_number: int, mode: str, store_id: str, store_eta: int) -> Dict:
    """
    Search Zepto products with dynamic signature generation.
    """
    request_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    intent_id = str(uuid.uuid4())

    xsrf_token = 'oP3uwJjRw9VSIjT67Zoy7:iuS8QzNseZdvyeSZOPMOpVseoBI.U20MDun9LneIiqw4252G9ST/WGLkcVsd31SJpRH9TTs'
    csrf_secret = 'aSF-wnTr9qs'

    url_path = '/api/v3/search'
    method = 'post'

    json_data = {
        'query': query,
        'pageNumber': page_number,
        'intentId': intent_id,
        'mode': mode,
        'userSessionId': session_id,
    }

    signature = generate_signature(
        method=method,
        url=url_path,
        request_id=request_id,
        device_id=device_id,
        secret=xsrf_token,
        body=json_data
    )

    timezone_hash = generate_timezone_hash(signature)

    headers = {
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'en-GB,en;q=0.8',
        'app_sub_platform': 'WEB',
        'app_version': '13.33.2',
        'appversion': '13.33.2',
        'auth_revamp_flow': 'v2',
        'compatible_components': 'CONVENIENCE_FEE,RAIN_FEE,EXTERNAL_COUPONS,STANDSTILL,BUNDLE,MULTI_SELLER_ENABLED,PIP_V1,ROLLUPS,SCHEDULED_DELIVERY,SAMPLING_ENABLED,ETA_NORMAL_WITH_149_DELIVERY,ETA_NORMAL_WITH_199_DELIVERY,HOMEPAGE_V2,NEW_ETA_BANNER,VERTICAL_FEED_PRODUCT_GRID,AUTOSUGGESTION_PAGE_ENABLED,AUTOSUGGESTION_PIP,AUTOSUGGESTION_AD_PIP,BOTTOM_NAV_FULL_ICON,COUPON_WIDGET_CART_REVAMP,DELIVERY_UPSELLING_WIDGET,MARKETPLACE_CATEGORY_GRID,NO_PLATFORM_CHECK_ENABLED_V2,SUPER_SAVER:1,SUPERSTORE_V1,PROMO_CASH:0,24X7_ENABLED_V1,TABBED_CAROUSEL_V2,HP_V4_FEED,WIDGET_BASED_ETA,PC_REVAMP_1,NO_COST_EMI_V1,PRE_SEARCH,ITEMISATION_ENABLED,ZEPTO_PASS,ZEPTO_PASS:5,BACHAT_FOR_ALL,SAMPLING_UPSELL_CAMPAIGN,DISCOUNTED_ADDONS_ENABLED,UPSELL_COUPON_SS:0,ENABLE_FLOATING_CART_BUTTON,NEW_ROLLUPS_ENABLED,RERANKING_QCL_RELATED_PRODUCTS,PLP_ON_SEARCH,PAAN_BANNER_WIDGETIZED,ROLLUPS_UOM,DYNAMIC_FILTERS,PHARMA_ENABLED,AUTOSUGGESTION_RECIPE_PIP,SEARCH_FILTERS_V1,QUERY_DESCRIPTION_WIDGET,MEDS_WITH_SIMILAR_SALT_WIDGET,NEW_FEE_STRUCTURE,NEW_BILL_INFO,RE_PROMISE_ETA_ORDER_SCREEN_ENABLED,SUPERSTORE_V1,MANUALLY_APPLIED_DELIVERY_FEE_RECEIVABLE,MARKETPLACE_REPLACEMENT,ZEPTO_PASS,ZEPTO_PASS:5,ZEPTO_PASS_RENEWAL,CART_REDESIGN_ENABLED,SHIPMENT_WIDGETIZATION_ENABLED,TABBED_CAROUSEL_V2,24X7_ENABLED_V1,PROMO_CASH:0,HOMEPAGE_V2,SUPER_SAVER:1,NO_PLATFORM_CHECK_ENABLED_V2,HP_V4_FEED,GIFT_CARD,SCLP_ADD_MONEY,GIFTING_ENABLED,OFSE,WIDGET_BASED_ETA,PC_REVAMP_1,NEW_ETA_BANNER,NO_COST_EMI_V1,ITEMISATION_ENABLED,SWAP_AND_SAVE_ON_CART,WIDGET_RESTRUCTURE,PRICING_CAMPAIGN_ID,BACHAT_FOR_ALL,TABBED_CAROUSEL_V3,CART_LMS:2,SAMPLING_UPSELL_CAMPAIGN,DISCOUNTED_ADDONS_ENABLED,UPSELL_COUPON_SS:0,SIZE_EXCHANGE_ENABLED,ENABLE_FLOATING_CART_BUTTON,',
        'device_id': device_id,
        'deviceid': device_id,
        'marketplace_type': 'SUPER_SAVER',
        'origin': 'https://www.zepto.com',
        'platform': 'WEB',
        'priority': 'u=1, i',
        'referer': 'https://www.zepto.com/',
        'request-signature': signature,
        'request_id': request_id,
        'requestid': request_id,
        'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
        'sec-gpc': '1',
        'session_id': session_id,
        'sessionid': session_id,
        'store_etas': f'{{"{store_id}":{store_eta}}}',
        'store_id': store_id,
        'store_ids': store_id,
        'storeid': store_id,
        'tenant': 'ZEPTO',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
        'x-csrf-secret': csrf_secret,
        'x-timezone': timezone_hash,
        'x-without-bearer': 'true',
        'x-xsrf-token': xsrf_token,
    }

    cookies = {
        '_fbp': 'fb.1.1762682659821.637133562767012334',
    }

    response = requests.post(
        'https://api.zepto.com/api/v3/search',
        cookies=cookies,
        headers=headers,
        json=json_data,
        impersonate='chrome110'
    )

    return response.json()


def extract_zepto_products(results: Dict, search_query: str, store_id: str) -> List[Product]:
    """Extract Zepto products and convert to Product model."""
    products = []

    if not results:
        return products

    if isinstance(results, dict):
        results = [results]

    for response in results or []:
        if not response or not isinstance(response, dict):
            continue
        layouts = response.get("layout")
        if not layouts or not isinstance(layouts, list):
            continue
        for layout in layouts:
            if not layout or not isinstance(layout, dict):
                continue
            if layout.get("widgetId") == "PRODUCT_GRID":
                data = layout.get("data")
                if not data or not isinstance(data, dict):
                    continue
                resolver = data.get("resolver")
                if not resolver or not isinstance(resolver, dict):
                    continue
                resolver_data = resolver.get("data")
                if not resolver_data or not isinstance(resolver_data, dict):
                    continue
                items = resolver_data.get("items", [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    try:
                        if not item or not isinstance(item, dict):
                            continue
                        product_resp = item.get("productResponse", {}) or {}
                        product = product_resp.get("product", {}) or {}
                        variant = product_resp.get("productVariant", {}) or {}

                        images = variant.get("images", []) or product.get("images", []) or []
                        image_urls = [img.get("path") for img in images if img.get("path")]

                        mrp_raw = product_resp.get("mrp")
                        price_raw = product_resp.get("sellingPrice")

                        products.append(Product(
                            platform='zepto',
                            search_query=search_query,
                            store_id=product_resp.get("storeId") or store_id,
                            product_id=str(product.get("id", '')),
                            variant_id=str(variant.get("id", '')),
                            name=product.get("name", ''),
                            brand=product.get("brand", ''),
                            mrp=mrp_raw / 100 if mrp_raw is not None else None,
                            price=price_raw / 100 if price_raw is not None else 0,
                            quantity=variant.get("formattedPacksize") or "",
                            in_stock=not product_resp.get("outOfStock", False),
                            inventory=product_resp.get("availableQuantity"),
                            max_allowed_quantity=variant.get("maxAllowedQuantity"),
                            category=product_resp.get("primaryCategoryName"),
                            sub_category=product_resp.get("primarySubcategoryName"),
                            images=image_urls,
                            organic_rank=item.get("position"),
                        ))

                    except Exception as e:
                        print(f"[ERROR] Skipped product due to exception: {e}")
                        continue

    return products


@router.get("/zepto/search")
def search_zepto(
    query: str = "chocolate",
    store_id: str = "4bbfd2a7-633f-40bf-91e3-3cfdd08fd6cc",
    store_eta: int = 14,
    max_pages: int = 10,
    save_to_db: bool = False
) -> List[Dict[str, Any]]:
    """
    Search for products on Zepto.

    Args:
        query: Search query string
        store_id: Zepto store ID for your location
        store_eta: Store ETA in minutes
        max_pages: Maximum pages to fetch (default: 10)
        save_to_db: Whether to save results to database

    Returns:
        List of product dictionaries
    """
    all_products = []
    page_number = 0

    try:
        while page_number < max_pages:
            print(f"[PAGE {page_number}] Fetching...")

            result = zepto_search(
                query=query,
                page_number=page_number,
                mode='SHOW_ALL_RESULTS',
                store_id=store_id,
                store_eta=store_eta
            )

            products = extract_zepto_products(result, query, store_id)

            if not products or len(products) == 0:
                print(f"[PAGE {page_number}] No more products found. Stopping pagination.")
                break

            print(f"[PAGE {page_number}] Found {len(products)} products")
            all_products.extend(products)
            page_number += 1
            time.sleep(1)

        if save_to_db and all_products:
            save_products_to_db(all_products, "products")

        exclude_fields = ["id", "created_at", "updated_at"]
        return [model_to_dict(product, exclude_fields=exclude_fields) for product in all_products]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing Zepto search: {str(e)}"
        )
