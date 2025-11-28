# instamart_search_request.py
import re
import requests
from playwright.sync_api import sync_playwright
import pandas as pd
import os

INSTAMART_IMAGE_PREFIX = "https://instamart-media-assets.swiggy.com/swiggy/image/upload/fl_lossy,f_auto,q_auto,h_600/"


def get_instamart_store_info(csv_path: str = "combined_store_with_locality.csv"):
    """
    Load the CSV and return store_id, latitude, longitude, pincode, area_name for rows where platform == 'instamart'.
    Returns a list of dicts (one per matching row).
    """
    df = pd.read_csv(csv_path)

    # Filter rows where platform == 'instamart'
    instamart_rows = df[df["platform"].str.lower() == "instamart"]

    # Select only the required columns (including pincode and area_name)
    columns_to_select = ["store_id", "latitude", "longitude"]

    # Add optional columns if they exist
    if "pincode" in df.columns:
        columns_to_select.append("pincode")
    if "area_name" in df.columns:
        columns_to_select.append("area_name")

    result = instamart_rows[columns_to_select].to_dict(orient="records")

    return result

queries = ["Coffee", "Chips", "Chocolates", "Oil", "Chicken", "Handwash", "Petfood", "Charger", "Protein", "Stationery", "Sunscreen"]
# Get all instamart stores from the CSV
stores = get_instamart_store_info()
search_result_offset = 0
max_page = 10

# CSV file name
output_csv = "Sunday_Instamart_run.csv"

# Check if file exists to determine if we need to write headers
write_header = not os.path.exists(output_csv)
def extract_instamart_variations_rows(data_response, current_query=None, current_store_id=None, current_page_num=None, current_pincode=None, current_area_name=None):
    """
    Flattens Instamart search JSON into rows (one per variation).
    Returns: List[dict]
    """
    rows = []

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
                # IDs
                sku_id = var.get("skuId")
                variant_display = var.get("displayName") or item_display
                variant_brand = var.get("brandName") or item_brand

                # Pricing
                price = var.get("price", {}) or {}
                mrp_units = price.get("mrp", {}).get("units")
                offer_units = price.get("offerPrice", {}).get("units")

                

                # Inventory & other attrs
                inventory_allowed = (var.get("cartAllowedQuantity", {}) or {}).get("allowedQuantity")
                in_stock = (var.get("inventory", {}) or {}).get("inStock")
                weight = var.get("weightInGrams")
                quantity = var.get("quantityDescription")
                short_desc = var.get("shortDescription")
                category = var.get("category") or item.get("category")
                sub_category = var.get("subCategoryType") or item.get("subCategoryType")
                rank = item.get("analytics", {}).get("position")

                # Images: medias[].id + imageIds[]
                media_ids = [m.get("id") for m in (var.get("medias") or []) if isinstance(m, dict) and m.get("id")]
                image_ids = list(var.get("imageIds") or [])
                # dedupe while preserving order
                seen = set()
                images_list = []
                for _id in image_ids + media_ids:
                    if _id and _id not in seen:
                        seen.add(_id)
                        # Add the INSTAMART_IMAGE_PREFIX to each image ID
                        images_list.append(INSTAMART_IMAGE_PREFIX + _id)
                images = ", ".join(images_list)

                rows.append({
                    "platform" : "Instamart",
                    "productId": product_id,
                    "variant_id": sku_id,
                    "name": variant_display,
                    "brand": variant_brand,
                    "mrp": mrp_units,                    # strings in payload; convert later if needed
                    "price": offer_units,     # strings in payload; convert later if needed
                    "quantity" : quantity,
                    "in_stock": in_stock,
                    "inventory": inventory_allowed,
                    "max_allowed": inventory_allowed,
                    "category": category,
                    "sub_category": sub_category,
                    "images": images,
                    "organic_rank" : rank,
                    "weightInGrams": weight,
                    "shortDescription": short_desc,
                    "store_id" : current_store_id,
                    "search_query" : current_query,
                    "page" : current_page_num,
                    "pincode": current_pincode,
                    "area_name": current_area_name
                })

    return rows

# ---------- Helpers ----------
def extract_aws_waf_token(curl_text: str) -> str:
    """Extract the aws-waf-token value from a curl command string."""
    match = re.search(r"aws-waf-token=([^;'\s]+)", curl_text)
    return match.group(1) if match else ""

set_location_url = "https://www.swiggy.com/"
playwright_url = "https://www.swiggy.com/instamart"

def get_token_playwright():
    with sync_playwright() as p:
        # Set up request interceptor before creating browser
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

        # Launch browser minimized initially to reduce flash
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--window-position=0,0',
                '--window-size=1280,720'
            ]
        )

        # Create context with cookies already loaded
        context = browser.new_context(
            storage_state="instamart_cookies.json",
            viewport={'width': 1280, 'height': 720}
        )

        # Attach listener before creating page
        context.on("request", on_request)

        # Create page and navigate in one go
        page = context.new_page()
        page.goto("https://www.swiggy.com/instamart", wait_until="domcontentloaded")

        # 3) Nudge the page (some lazy calls fire on interaction)
        page.mouse.wheel(0, 300)

        # 4) Actively wait for the Instamart bootstrap call (best-effort)
        try:
            page.wait_for_request(lambda r: "instamart/home" in (r.url or ""), timeout=10000)
            page.wait_for_response(lambda r: "instamart/home" in (r.url or ""), timeout=10000)
        except Exception:
            pass  # keep going; we'll use the cookie jar fallback below

        # 5) Fallback: read from cookie jar
        if not token_holder["value"]:
            for _ in range(10):  # retry briefly; SPA may set it a bit later
                for c in context.cookies():
                    if c.get("name") == "aws-waf-token" and c.get("value"):
                        token_holder["value"] = c["value"]
                        break
                if token_holder["value"]:
                    break
                page.wait_for_timeout(300)

        # Small grace period before closing
        page.wait_for_timeout(300)
        browser.close()

        return token_holder["value"]
# ---------- Main Request ---------- 
# Global token that will be updated as needed
global_aws_waf_token = get_token_playwright()
print("✅ Extracted aws-waf-token:", global_aws_waf_token)

for query in queries:
    for store in stores:
        store_id = store["store_id"]
        latitude = store["latitude"]
        longitude = store["longitude"]
        pincode = store.get("pincode", "")
        area_name = store.get("area_name", "")
        print(f"\n🔍 Query='{query}' | Store={store_id} | Lat={latitude} | Lng={longitude} | Area={area_name} | Pincode={pincode}")
        search_result_offset = 0  # Reset offset for each query/store combination
        store_rows = []  # Collect rows for this store
        for page_num in range(max_page):
            # Use search_result_offset in URL instead of page_num
            url = f"https://www.swiggy.com/api/instamart/search/v2?offset={search_result_offset}&ageConsent=false&voiceSearchTrackingId=&storeId={store_id}&primaryStoreId={store_id}&secondaryStoreId="

            headers = {
                "accept": "*/*",
                "accept-language": "en-GB,en;q=0.5",
                "content-type": "application/json",
                "matcher": "addce8ecfeeacfb987ad7e7",
                "origin": "https://www.swiggy.com",
                "priority": "u=1, i",
                "referer": "https://www.swiggy.com/instamart/search?custom_back=true&query=Soaps",
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
                "lat": f"{latitude}",
                "lng": f"{longitude}",
                "address": "",
                "userLocation": '',
                "sid": "",
                "imOrderAttribution": '{"entryId":"Soaps","entryName":"instamartOpenSearch"}',
                "aws-waf-token": global_aws_waf_token,  
            }

            payload = {
                "facets": [],
                "sortAttribute": "",
                "query": query,
                "search_results_offset": search_result_offset,
                "page_type": "INSTAMART_SEARCH_PAGE",
                "is_pre_search_tag": False,
            }

            response = requests.post(url, headers=headers, cookies=cookies, json=payload)

            print("Status:", response.status_code)
            if response.status_code != 200:
                print("⚠️ Token expired or invalid. Getting fresh token...")
                global_aws_waf_token = get_token_playwright()  # Update the global token
                print("✅ New aws-waf-token:", global_aws_waf_token)
                cookies["aws-waf-token"] = global_aws_waf_token
                # Retry the request with new token
                response = requests.post(url, headers=headers, cookies=cookies, json=payload)
                print("Retry Status:", response.status_code)

            try:
                data_response = response.json()

                # Check if response contains error status code
                if isinstance(data_response, dict) and data_response.get('statusCode') == 'ERR_NON_2XX_3XX_RESPONSE':
                    print("⚠️ API returned error response. Getting fresh token...")
                    global_aws_waf_token = get_token_playwright()  # Update the global token
                    print("✅ New aws-waf-token:", global_aws_waf_token)
                    cookies["aws-waf-token"] = global_aws_waf_token
                    # Retry the request with new token
                    response = requests.post(url, headers=headers, cookies=cookies, json=payload)
                    data_response = response.json()
                    print("Retry response:", str(data_response)[:200] if isinstance(data_response, dict) else data_response)

                # Only process if we have valid data (not an error response)
                if data_response and not (isinstance(data_response, dict) and data_response.get('statusCode') == 'ERR_NON_2XX_3XX_RESPONSE'):
                    rows = extract_instamart_variations_rows(data_response, current_query=query, current_store_id=store_id, current_page_num=page_num, current_pincode=pincode, current_area_name=area_name)
                    # Update search_result_offset for next iteration
                    new_offset = data_response.get("data", {}).get("searchResultsOffset")
                    if new_offset is not None:
                        search_result_offset = new_offset
                    store_rows.extend(rows)

                    print(f"Current offset: {search_result_offset}")
                    print("-----------------------Mil gya next offset------------------------------------")
                    print(str(data_response)[:100])  # Convert dict to string before slicing
                    print("✅ JSON keys:", list(data_response.keys()))

                    # Break if no more results
                    if not rows or search_result_offset == 0:
                        print("No more results, moving to next query/store")
                        break
            except Exception as e:
                print(f"⚠️ Error processing response: {e}")
                print(response.text[:500])
                break

        # After processing all pages for this store, append to CSV
        if store_rows:
            df = pd.DataFrame(store_rows)

            # Write header only if it's the first store being written
            if write_header:
                df.to_csv(output_csv, mode='w', index=False, encoding="utf-8", header=True)
                write_header = False  # Don't write header again
                print(f"✅ Created {output_csv} and saved {len(store_rows)} rows for Store {store_id}")
            else:
                df.to_csv(output_csv, mode='a', index=False, encoding="utf-8", header=False)
                print(f"✅ Appended {len(store_rows)} rows for Store {store_id} to {output_csv}")
        else:
            print(f"⚠️ No products found for Store {store_id}")

print(f"\n{'='*50}")
print(f"✅ SCRAPING COMPLETED - Check {output_csv}")
print(f"{'='*50}")

