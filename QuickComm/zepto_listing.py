from curl_cffi import requests
import hashlib
import json
import uuid
import pandas as pd
from datetime import datetime
import os

# ============================================
# Dynamic Signature Generation (from Zepto's JS)
# ============================================

def generate_signature(method, url, request_id, device_id, secret, body=None):
    """
    Generate request signature based on Zepto's JavaScript implementation.

    The JS code does:
    1. Create object with: method, url, requestId, deviceId, secret, body
    2. Sort keys alphabetically
    3. Join values with "|"
    4. SHA-256 hash
    5. Return hex string
    """
    # Create the signature object
    sig_obj = {
        "method": method.lower(),
        "url": url,
        "requestId": request_id,
        "deviceId": device_id,
        "secret": secret,
    }

    # Add body only for non-GET requests
    if body and method.lower() != "get":
        if isinstance(body, dict):
            sig_obj["body"] = json.dumps(body, separators=(',', ':'))
        else:
            sig_obj["body"] = body

    # Sort keys and join values with "|"
    sorted_keys = sorted(sig_obj.keys())
    signature_string = "|".join(str(sig_obj[key]) for key in sorted_keys)

    # SHA-256 hash
    signature_hash = hashlib.sha256(signature_string.encode()).hexdigest()

    return signature_hash


def generate_timezone_hash(signature):
    """
    Generate x-timezone header by hashing the signature.
    Based on Zepto's JS: x-timezone = hash(signature)
    """
    return hashlib.sha256(signature.encode()).hexdigest()


def zepto_search(query, page_number, mode, store_id, store_eta):
    """
    Search Zepto products with dynamic signature generation.

    Args:
        query (str): Search query (e.g., 'handwash', 'oil', 'biscuit')
        page_number (int): Page number for pagination (default: 0)
        mode (str): Search mode - 'SHOW_ALL_RESULTS' or 'AUTOSUGGEST' (default: 'SHOW_ALL_RESULTS')
        store_id (str): Store ID for your location
        store_eta (int): Store ETA in minutes

    Returns:
        dict: JSON response from Zepto API
    """

    # Generate unique IDs for this request
    request_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    intent_id = str(uuid.uuid4())

    # These would typically come from cookies/authentication
    # For now, using example values
    xsrf_token = 'oP3uwJjRw9VSIjT67Zoy7:iuS8QzNseZdvyeSZOPMOpVseoBI.U20MDun9LneIiqw4252G9ST/WGLkcVsd31SJpRH9TTs'
    csrf_secret = 'aSF-wnTr9qs'

    # Prepare request data
    url_path = '/api/v3/search'
    method = 'post'

    json_data = {
        'query': query,
        'pageNumber': page_number,
        'intentId': intent_id,
        'mode': mode,
        'userSessionId': session_id,
    }

    # Generate signature
    signature = generate_signature(
        method=method,
        url=url_path,
        request_id=request_id,
        device_id=device_id,
        secret=xsrf_token,
        body=json_data
    )

    # Generate timezone hash
    timezone_hash = generate_timezone_hash(signature)

    # Build headers with dynamic values
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
        'request-signature': signature,  # Dynamic signature
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
        'x-timezone': timezone_hash,  # Dynamic timezone hash
        'x-without-bearer': 'true',
        'x-xsrf-token': xsrf_token,
    }

    cookies = {
        '_fbp': 'fb.1.1762682659821.637133562767012334',
    }

    # Make request
    response = requests.post(
        'https://api.zepto.com/api/v3/search',
        cookies=cookies,
        headers=headers,
        json=json_data,
        impersonate='chrome110'
    )

    return response.json()


# ============================================
# Data Extraction Logic
# ============================================

def extract_zepto_data(results, current_query, locality):
    """
    Flatten Zepto search JSON responses into structured rows.
    """
    rows = []

    # Handle None or empty results
    if not results:
        return rows

    # If results is a single dict response, wrap it in a list
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

                        # Prices are in paise, convert to rupees by dividing by 100
                        mrp_raw = product_resp.get("mrp")
                        price_raw = product_resp.get("sellingPrice")

                        row = {
                            "platform": "Zepto",
                            "product_id": product.get("id"),
                            "variant_id": variant.get("id"),
                            "name": product.get("name"),
                            "brand": product.get("brand"),
                            "mrp": mrp_raw / 100 if mrp_raw is not None else None,
                            "price": price_raw / 100 if price_raw is not None else None,
                            "quantity": variant.get("formattedPacksize") or "",
                            "in_stock": not product_resp.get("outOfStock", False),
                            "inventory": product_resp.get("availableQuantity"),
                            "max_allowed_quantity": variant.get("maxAllowedQuantity"),
                            "category": product_resp.get("primaryCategoryName"),
                            "sub_category": product_resp.get("primarySubcategoryName"),
                            "images": ", ".join(image_urls),
                            "organic_rank": item.get("position"),
                            "weightInGrams": product_resp.get("packskze"),
                            "shortDescription": product.get("description"),
                            "store_id": product_resp.get("storeId"),
                            "search_query": current_query,
                            "locality": locality,
                        }

                        rows.append(row)

                    except Exception as e:
                        print(f"[ERROR] Skipped product due to exception: {e}")
                        continue

    return rows


# ============================================
# Main Scraping Function
# ============================================

def scrape_zepto_queries(queries, locality="Unknown", store_id='5bbd5e39-81de-4d1a-9706-25cbe2cb58af', store_eta=14, output_dir='../output', max_pages=20):
    """
    Scrape multiple queries with pagination and save to CSV.

    Args:
        queries (list): List of search queries
        locality (str): Locality name for the store
        store_id (str): Store ID for your location
        store_eta (int): Store ETA in minutes
        output_dir (str): Directory to save output CSV
        max_pages (int): Maximum pages to fetch per query (safety limit)

    Returns:
        pd.DataFrame: DataFrame with all products
    """
    all_products = []

    for query in queries:
        print(f"\n{'='*60}")
        print(f"[SCRAPING] Query: '{query}'")
        print('='*60)

        query_products = []
        page_number = 0

        try:
            while page_number < max_pages:
                print(f"[PAGE {page_number}] Fetching...")

                # Get search results for current page
                result = zepto_search(query, page_number=page_number, mode = 'SHOW_ALL_RESULTS', store_id=store_id, store_eta=store_eta)

                # Extract data
                products = extract_zepto_data(result, query, locality)

                # If no products found, we've reached the end
                if not products or len(products) == 0:
                    print(f"[PAGE {page_number}] No more products found. Stopping pagination.")
                    break

                print(f"[PAGE {page_number}] Found {len(products)} products")
                query_products.extend(products)

                # Move to next page
                page_number += 1

            print(f"\n[QUERY COMPLETE] '{query}': {len(query_products)} total products across {page_number} pages")
            all_products.extend(query_products)

        except Exception as e:
            print(f"[ERROR] Failed to scrape '{query}' at page {page_number}: {e}")
            import traceback
            traceback.print_exc()
            # Continue with accumulated products even if error occurs
            if query_products:
                all_products.extend(query_products)

    # Convert to DataFrame
    if all_products:
        df = pd.DataFrame(all_products)

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"zepto_products_{locality.replace(' ', '_')}_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)

        # Save to CSV
        df.to_csv(filepath, index=False)
        print(f"\n[SAVED] {len(df)} products saved to: {filepath}")

        return df
    else:
        print("\n[WARNING] No products found")
        return pd.DataFrame()


# ============================================
# Example Usage
# ============================================

if __name__ == "__main__":
    # Example: Scrape multiple queries for a specific store with pagination
    queries = ['vegetable']
    locality = ''  # Change to your locality
    store_id = '4bbfd2a7-633f-40bf-91e3-3cfdd08fd6cc'  # Change to your store ID

    print("\n" + "="*60)
    print("ZEPTO SCRAPER - API-based with Dynamic Signatures")
    print("="*60)
    print(f"Queries: {queries}")
    print(f"Locality: {locality}")
    print(f"Store ID: {store_id}")
    print("="*60)

    df = scrape_zepto_queries(
        queries=queries,
        locality=locality,
        store_id=store_id,
        store_eta=14,
        output_dir='../output',
        max_pages=20  # Will automatically stop when no more products
    )

    if not df.empty:
        print(f"\n{'='*60}")
        print(f"FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"Total products scraped: {len(df)}")
        print(f"Total queries: {len(queries)}")
        print(f"Unique products: {df['product_id'].nunique()}")
        print(f"{'='*60}")

        print("\nProducts per query:")
        print(df.groupby('search_query').size())

        print("\n\nSample products:")
        print(df[['name', 'brand', 'price', 'search_query', 'in_stock']].head(15).to_string())
    else:
        print("\n[ERROR] No data was scraped")