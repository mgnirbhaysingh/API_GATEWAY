import requests
import csv
import os
from datetime import datetime
import time
import json

cookies = {
    'T': 'TI176250251006400090422924463936480118078483415426979424293560624030',
    'at': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImQ2Yjk5NDViLWZmYTEtNGQ5ZC1iZDQyLTFkN2RmZTU4ZGNmYSJ9.eyJleHAiOjE3NjQyMzA1MTAsImlhdCI6MTc2MjUwMjUxMCwiaXNzIjoia2V2bGFyIiwianRpIjoiMzg4ODAwNjUtMDY3ZS00YTJiLThlYjctZGU1ODYyZDJjMWE5IiwidHlwZSI6IkFUIiwiZElkIjoiVEkxNzYyNTAyNTEwMDY0MDAwOTA0MjI5MjQ0NjM5MzY0ODAxMTgwNzg0ODM0MTU0MjY5Nzk0MjQyOTM1NjA2MjQwMzAiLCJrZXZJZCI6IlZJNDQ3NzE4NDIxOTc1NDBBRDhCMkMyNUVEQzgyMzNDNDciLCJ0SWQiOiJtYXBpIiwidnMiOiJMTyIsInoiOiJDSCIsIm0iOnRydWUsImdlbiI6NH0.t-YaBQNf1aii_Yt7geuS6K01YdCoWFxrZOlZVYZ-Pso',
    'K-ACTION': 'null',
    'vh': '724',
    'vw': '1440',
    'dpr': '2',
    'rt': 'null',
    'AMCVS_17EB401053DAF4840A490D4C%40AdobeOrg': '1',
    'AMCV_17EB401053DAF4840A490D4C%40AdobeOrg': '-227196251%7CMCIDTS%7C20400%7CMCMID%7C30659903332841607936380996756615438569%7CMCAID%7CNONE%7CMCOPTOUT-1762509738s%7CNONE',
    'vd': 'VI44771842197540AD8B2C25EDC8233C47-1762502511297-1.1762503522.1762502511.149776040',
    's_sq': 'flipkart-prd%3D%2526pid%253Dwww.flipkart.com%25253Agrocery%25253Apr%2526pidt%253D1%2526oid%253DfunctionJr%252528%252529%25257B%25257D%2526oidt%253D2%2526ot%253DDIV',
    'ud': '6.vlZgohnaUd0_DVPJq-kjat9Tae0RmvWAv4OpTmbeV5lgOh5Me6046fUHF3opPXdbmVEaOJ5ZDTtR2X_hC7iIAedZ78ETK3srzKS6Gzaicc3gqc4JGE0OF42advKm7XELrNT5qfsWZ07TmCUteoe7RU23MIF2IyemxHGo6_gkF_HZoz2og-xpSra3PNIXksxMFi2hKZFE5cBWVeNEKpHIFw',
    'S': 'd1t12Tj8/P0wRP2sdP2tjPz8/P1QnIxlI6V6ryk6E7WHP+e+bjOK2NhYh8V95euqScw3hVhfrhejsZfpg94lqyk4/LA==',
    'SN': 'VI44771842197540AD8B2C25EDC8233C47.TOKEF6362062B214FBB82DC8657A11FE208.1762503540441.LO',
}

headers = {
    'Accept': '*/*',
    'Accept-Language': 'en-GB,en;q=0.6',
    'Connection': 'keep-alive',
    'Content-Type': 'application/json',
    'Origin': 'https://www.flipkart.com',
    'Referer': 'https://www.flipkart.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'Sec-GPC': '1',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    'X-User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 FKUA/website/42/website/Desktop',
    'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
}

def set_location(pincode):
    """Set delivery location using pincode"""
    print(f"Setting delivery location to pincode: {pincode}")

    location_data = {
        'locationContext': {
            'pincode': pincode
        },
        'marketplaceContext': {
            'marketplace': 'GROCERY'
        }
    }

    try:
        response = requests.post(
            'https://1.rome.api.flipkart.com/api/3/marketplace/serviceability',
            cookies=cookies,
            headers=headers,
            json=location_data,
            timeout=30
        )
        response.raise_for_status()

        if response.status_code == 200:
            response_data = response.json()
            serviceability = response_data.get('RESPONSE', {}).get('serviceability', False)
            pincode_response = response_data.get('RESPONSE', {}).get('pincode', '')

            if serviceability:
                print(f"Location set successfully to pincode: {pincode_response}")

                # Update cookies with new session data
                session_data = response_data.get('SESSION', {})
                if session_data.get('sn'):
                    cookies['SN'] = session_data['sn']

                # Update cookies from response
                for cookie in response.cookies:
                    cookies[cookie.name] = cookie.value

                return True
            else:
                message = response_data.get('RESPONSE', {}).get('message', 'Grocery delivery not available')
                print(f"Error: {message} for pincode {pincode}")
                return False
        else:
            print(f"Error: Failed to set location. Status code: {response.status_code}")
            return False

    except Exception as e:
        print(f"Error setting location: {e}")
        return False

def extract_page_uri_from_url(url):
    """Extract pageUri from Flipkart product URL"""
    # URL format: https://www.flipkart.com/product-name/p/itm-id?pid=PID&...
    # We need: /product-name/p/itm-id?pid=PID&lid=LID&marketplace=GROCERY

    if 'flipkart.com' in url:
        # Extract path and query params
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        path = parsed.path
        query_params = parse_qs(parsed.query)

        # Get required params
        pid = query_params.get('pid', [''])[0]
        lid = query_params.get('lid', [''])[0]

        # Build pageUri
        page_uri = f"{path}?pid={pid}"
        if lid:
            page_uri += f"&lid={lid}"
        page_uri += "&marketplace=GROCERY"

        return page_uri

    return None

def fetch_product_details(page_uri, pincode, debug=False):
    """Fetch detailed product information from PDP API"""
    print(f"Fetching product details for: {page_uri}")

    json_data = {
        'pageUri': page_uri,
        'locationContext': {
            'pincode': pincode
        },
        'isReloadRequest': True
    }

    try:
        response = requests.post(
            'https://1.rome.api.flipkart.com/api/4/page/fetch',
            cookies=cookies,
            headers=headers,
            json=json_data,
            timeout=30
        )
        response.raise_for_status()

        if response.status_code == 200:
            response_data = response.json()

            # Debug: Save raw response if requested
            if debug:
                debug_file = f"output/debug_pdp_{page_uri.split('/')[-1].split('?')[0]}.json"
                os.makedirs('output', exist_ok=True)
                with open(debug_file, 'w', encoding='utf-8') as f:
                    json.dump(response_data, f, indent=2)
                print(f"Debug: Saved raw response to {debug_file}")

            return response_data
        else:
            print(f"Error: Received status code {response.status_code}")
            return None

    except Exception as e:
        print(f"Error fetching product details: {e}")
        return None

def extract_product_info(response_data):
    """Extract detailed product information from PDP response"""
    try:
        page_context = response_data.get('RESPONSE', {}).get('pageData', {}).get('pageContext', {})

        if not page_context:
            print("Error: No pageContext found in response")
            return None

        # Extract basic information
        product_id = page_context.get('productId', '')
        item_id = page_context.get('itemId', '')
        listing_id = page_context.get('listingId', '')

        # Extract titles
        titles = page_context.get('titles', {})
        title = titles.get('title', '')
        subtitle = titles.get('subtitle', '')

        # Extract brand
        brand = page_context.get('brand', '')

        # Extract pricing
        pricing = page_context.get('pricing', {})
        mrp = pricing.get('mrp', 0)
        fsp = pricing.get('fsp', 0)
        total_discount = pricing.get('totalDiscount', 0)

        final_price_obj = pricing.get('finalPrice', {})
        final_price = final_price_obj.get('value', 0)

        # Extract rating
        rating_obj = page_context.get('rating', {})
        rating_average = rating_obj.get('average', 0)
        rating_count = rating_obj.get('count', 0)
        review_count = rating_obj.get('reviewCount', 0)

        # Extract tracking/delivery info
        tracking_data = page_context.get('trackingDataV2', {})
        serviceable = tracking_data.get('serviceable', False)
        sla_text = tracking_data.get('slaText', '')
        sla_min_days = tracking_data.get('slaMinDays', 0)
        sla_max_days = tracking_data.get('slaMaxDays', 0)
        seller_name = tracking_data.get('sellerName', '')
        seller_rating = tracking_data.get('sellerRating', 0)
        cod_available = tracking_data.get('codAvailable', False)
        return_policy = tracking_data.get('returnPolicy', '')

        # Extract image URL
        image_url = page_context.get('imageUrl', '')
        image_url = image_url.replace('{@width}', '500').replace('{@height}', '500').replace('{@quality}', '80')

        # Extract category info
        analytics_data = page_context.get('analyticsData', {})
        category = analytics_data.get('category', '')
        sub_category = analytics_data.get('subCategory', '')
        vertical = analytics_data.get('vertical', '')

        # Extract smart URL
        smart_url = page_context.get('smartUrl', '')

        # Max order quantity
        max_order_qty = page_context.get('maxOrderQuantityAllowed', 0)

        product_info = {
            'product_id': product_id,
            'item_id': item_id,
            'listing_id': listing_id,
            'title': title,
            'subtitle': subtitle,
            'brand': brand,
            'mrp': mrp,
            'selling_price': fsp,
            'final_price': final_price,
            'discount_percent': total_discount,
            'discount_amount': mrp - fsp if mrp and fsp else 0,
            'rating_average': rating_average,
            'rating_count': rating_count,
            'review_count': review_count,
            'serviceable': serviceable,
            'delivery_text': sla_text,
            'delivery_min_days': sla_min_days,
            'delivery_max_days': sla_max_days,
            'seller_name': seller_name,
            'seller_rating': seller_rating,
            'cod_available': cod_available,
            'return_policy': return_policy,
            'image_url': image_url,
            'category': category,
            'sub_category': sub_category,
            'vertical': vertical,
            'smart_url': smart_url,
            'max_order_quantity': max_order_qty
        }

        return product_info

    except Exception as e:
        print(f"Error extracting product info: {e}")
        return None

def fetch_products_from_csv(csv_file, pincode, debug=False):
    """Fetch detailed information for products listed in CSV"""
    print(f"\nReading products from CSV: {csv_file}")

    products_details = []

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            product_urls = []

            for row in reader:
                product_url = row.get('product_url', '')
                if product_url:
                    product_urls.append(product_url)

        print(f"Found {len(product_urls)} products to fetch")

        for idx, url in enumerate(product_urls, 1):
            print(f"\n[{idx}/{len(product_urls)}] Processing: {url}")

            # Extract pageUri from URL
            page_uri = extract_page_uri_from_url(url)
            if not page_uri:
                print(f"Error: Could not extract pageUri from URL")
                continue

            # Fetch product details
            response_data = fetch_product_details(page_uri, pincode, debug)
            if not response_data:
                print(f"Error: Failed to fetch product details")
                continue

            # Extract product information
            product_info = extract_product_info(response_data)
            if product_info:
                products_details.append(product_info)
                print(f"Successfully extracted details for: {product_info['title']}")
            else:
                print(f"Error: Failed to extract product information")

            # Be polite, wait between requests
            time.sleep(2)

        return products_details

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return []

def save_to_csv(products, pincode, output_filename=None):
    """Save product details to CSV file"""
    if not products:
        print("No products to save!")
        return

    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)

    # Generate filename with timestamp
    if not output_filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"output/flipkart_pdp_pin{pincode}_{timestamp}.csv"

    # Write to CSV
    fieldnames = [
        'product_id', 'item_id', 'listing_id', 'title', 'subtitle', 'brand',
        'mrp', 'selling_price', 'final_price', 'discount_percent', 'discount_amount',
        'rating_average', 'rating_count', 'review_count',
        'serviceable', 'delivery_text', 'delivery_min_days', 'delivery_max_days',
        'seller_name', 'seller_rating', 'cod_available', 'return_policy',
        'image_url', 'category', 'sub_category', 'vertical', 'smart_url', 'max_order_quantity'
    ]

    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)

    print(f"\nSuccessfully saved {len(products)} product details to {output_filename}")
    return output_filename

if __name__ == "__main__":
    # Configuration
    PINCODE = "122001"  # Set your delivery pincode
    DEBUG = False  # Set to True to save raw API responses for debugging

    # Option 1: Fetch from CSV file (from flipkart_groceries.py output)
    INPUT_CSV = "output/flipkart_detergent_pin226002_20251107_143358.csv"  # CSV with product_url column

    # Option 2: Or provide a list of product URLs directly
    PRODUCT_URLS = [
        # "https://www.flipkart.com/ariel-complete-detergent-powder/p/itm46950275b7a83?pid=LDTFG5JFMPRZJFXQ&lid=LSTLDTFG5JFMPRZJFXQT5D7ZG&marketplace=GROCERY"
    ]

    print(f"Starting Flipkart PDP scraper")
    print(f"Delivery location pincode: {PINCODE}")
    if DEBUG:
        print("Debug mode enabled - raw responses will be saved to output folder")
    print()

    # Set location
    if not set_location(PINCODE):
        print("Failed to set location. Exiting.")
        exit(1)

    time.sleep(1)

    # Fetch product details
    products_details = []

    if INPUT_CSV and os.path.exists(INPUT_CSV):
        # Fetch from CSV file
        products_details = fetch_products_from_csv(INPUT_CSV, PINCODE, DEBUG)
    elif PRODUCT_URLS:
        # Fetch from provided URLs
        for url in PRODUCT_URLS:
            page_uri = extract_page_uri_from_url(url)
            if page_uri:
                response_data = fetch_product_details(page_uri, PINCODE, DEBUG)
                if response_data:
                    product_info = extract_product_info(response_data)
                    if product_info:
                        products_details.append(product_info)
                time.sleep(2)

    # Save to CSV
    if products_details:
        save_to_csv(products_details, PINCODE)
    else:
        print("\nNo product details were scraped.")
