import requests
import csv
import os
from datetime import datetime
import time

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

                # Update cookies with new session data from the response
                session_data = response_data.get('SESSION', {})
                if session_data.get('sn'):
                    cookies['SN'] = session_data['sn']

                # Update cookies from the response's Set-Cookie headers
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

def extract_products(response_data):
    """Extract product information from API response"""
    products = []

    try:
        slots = response_data.get('RESPONSE', {}).get('slots', [])

        for slot in slots:
            widget = slot.get('widget', {})
            widget_type = widget.get('type', '')

            # Check for different product widget types
            if slot.get('slotType') == 'WIDGET' and widget_type in ['PRODUCT_SUMMARY_EXTENDED', 'PRODUCT_SUMMARY']:
                widget_products = widget.get('data', {}).get('products', [])

                for product in widget_products:
                    try:
                        product_value = product.get('productInfo', {}).get('value', {})

                        # Extract basic info
                        product_id = product_value.get('id', '')
                        item_id = product_value.get('itemId', '')
                        listing_id = product_value.get('listingId', '')

                        # Extract titles
                        titles = product_value.get('titles', {})
                        title = titles.get('title', '')
                        new_title = titles.get('newTitle', '')
                        brand = titles.get('superTitle', product_value.get('productBrand', ''))
                        quantity = titles.get('subtitle', '')

                        # Extract pricing
                        pricing = product_value.get('pricing', {})
                        final_price = pricing.get('finalPrice', {}).get('value', 0)

                        prices = pricing.get('prices', [])
                        mrp = 0
                        selling_price = 0
                        discount_percent = 0

                        for price in prices:
                            if price.get('priceType') == 'MRP':
                                mrp = price.get('value', 0)
                                discount_percent = price.get('discount', 0)
                            elif price.get('priceType') == 'FSP':
                                selling_price = price.get('value', 0)

                        discount_amount = pricing.get('discountAmount', 0)

                        # Extract availability
                        availability = product_value.get('availability', {})
                        stock_status = availability.get('displayState', '')

                        # Extract image
                        images = product_value.get('media', {}).get('images', [])
                        image_url = images[0].get('url', '') if images else ''
                        image_url = image_url.replace('{@width}', '312').replace('{@height}', '312').replace('{@quality}', '70')

                        # Extract URL
                        base_url = product_value.get('baseUrl', '')
                        product_url = f"https://www.flipkart.com{base_url}" if base_url else ''

                        # Extract key specs
                        key_specs = product_value.get('keySpecs', [])
                        specs = ' | '.join(key_specs) if key_specs else ''

                        products.append({
                            'search_query': '',  # Will be filled in later
                            'product_id': product_id,
                            'item_id': item_id,
                            'listing_id': listing_id,
                            'title': title,
                            'product_name': new_title,
                            'brand': brand,
                            'quantity': quantity,
                            'mrp': mrp,
                            'selling_price': selling_price,
                            'final_price': final_price,
                            'discount_percent': discount_percent,
                            'discount_amount': discount_amount,
                            'stock_status': stock_status,
                            'image_url': image_url,
                            'product_url': product_url,
                            'specifications': specs
                        })
                    except Exception as e:
                        print(f"Error extracting product: {e}")
                        continue
    except Exception as e:
        print(f"Error parsing response: {e}")

    return products

def scrape_flipkart_groceries(search_query, max_pages=5, pincode=None, debug=False):
    """Scrape Flipkart grocery products for a given search query"""
    # Set location if pincode is provided
    if pincode:
        if not set_location(pincode):
            print("Failed to set location. Aborting scraping.")
            return []
        time.sleep(1)  # Wait a bit after setting location

    all_products = []
    page_number = 1

    while page_number <= max_pages:
        print(f"Scraping page {page_number}...")

        # Build the pageUri with page parameter
        if page_number == 1:
            page_uri = f'/search?q={search_query}&as=on&as-show=on&marketplace=GROCERY'
        else:
            page_uri = f'/search?q={search_query}&as=on&as-show=on&marketplace=GROCERY&page={page_number}'

        json_data = {
            'pageUri': page_uri,
            'pageContext': {
                'fetchSeoData': page_number == 1,  # Only fetch SEO data on first page
                'paginatedFetch': True,
                'pageNumber': page_number,
            },
            'requestContext': {
                'type': 'BROWSE_PAGE',
            },
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
                    import json
                    debug_file = f"output/debug_{search_query}_page{page_number}.json"
                    os.makedirs('output', exist_ok=True)
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        json.dump(response_data, f, indent=2)
                    print(f"Debug: Saved raw response to {debug_file}")

                # Debug: Check if response has slots
                slots = response_data.get('RESPONSE', {}).get('slots', [])
                print(f"Response has {len(slots)} slots")

                products = extract_products(response_data)

                if not products:
                    print(f"No products found on page {page_number}.")

                    # Debug: Check what slot types we have
                    slot_types = [slot.get('widget', {}).get('type') for slot in slots if slot.get('widget')]
                    print(f"Available slot types: {set(slot_types)}")

                    # Still check if there are more pages
                    page_data = response_data.get('RESPONSE', {}).get('pageData', {})
                    pagination_context = page_data.get('paginationContextMap', {}).get('federator', {})
                    has_more_pages = pagination_context.get('hasMorePages', False)

                    if not has_more_pages or page_number >= max_pages:
                        print("No more pages available or max pages reached. Stopping.")
                        break

                    # Try next page anyway
                    page_number += 1
                    time.sleep(2)
                    continue

                all_products.extend(products)
                print(f"Found {len(products)} products on page {page_number}")
                print(f"Total products so far: {len(all_products)}")

                # Move to next page
                page_number += 1

                # Check if we've reached max pages
                if page_number > max_pages:
                    print(f"Reached maximum page limit ({max_pages}). Stopping.")
                    break

                time.sleep(2)  # Be polite, wait 2 seconds between requests
            else:
                print(f"Error: Received status code {response.status_code}")
                break

        except Exception as e:
            print(f"Error making request: {e}")
            break

    return all_products

def save_to_csv(products, filename, mode='w', write_header=True):
    """Save products to CSV file"""
    if not products:
        print("No products to save!")
        return

    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)

    # Write to CSV with search_query as first column
    fieldnames = [
        'search_query', 'product_id', 'item_id', 'listing_id', 'title', 'product_name',
        'brand', 'quantity', 'mrp', 'selling_price', 'final_price',
        'discount_percent', 'discount_amount', 'stock_status',
        'image_url', 'product_url', 'specifications'
    ]

    with open(filename, mode, newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(products)

    print(f"\nSuccessfully saved {len(products)} products to {filename}")
    return filename

if __name__ == "__main__":
    # Configuration
    SEARCH_QUERIES = ['Biscuit', 'chocolates', 'Milk']  # Array of search queries
    MAX_PAGES = 10  # Maximum number of pages to scrape
    PINCODE = "560037"  # Set your delivery pincode (None to use default location)
    DEBUG = False  # Set to True to save raw API responses for debugging

    print("=" * 60)
    print("Flipkart Grocery Multi-Query Scraper")
    print("=" * 60)
    print(f"Search Queries: {', '.join(SEARCH_QUERIES)}")
    print(f"Maximum pages to scrape per query: {MAX_PAGES}")
    if PINCODE:
        print(f"Delivery location pincode: {PINCODE}")
    if DEBUG:
        print("Debug mode enabled - raw responses will be saved to output folder")
    print("=" * 60)

    # Set location once if pincode is provided
    location_set = False
    if PINCODE:
        if set_location(PINCODE):
            location_set = True
            print(f"\nLocation set successfully to pincode: {PINCODE}")
            time.sleep(1)
        else:
            print("\nFailed to set location. Aborting scraping.")
            exit(1)

    # Generate single CSV filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    pincode_suffix = f"_pin{PINCODE}" if PINCODE else ""
    csv_filename = f"output/flipkart_products{pincode_suffix}_{timestamp}.csv"

    total_products = 0
    write_header = True

    # Iterate through each search query
    for query_index, search_query in enumerate(SEARCH_QUERIES, 1):
        print("\n" + "=" * 60)
        print(f"[Query {query_index}/{len(SEARCH_QUERIES)}] Processing: {search_query}")
        print("=" * 60)

        # Scrape products (don't set location again if already set)
        products = scrape_flipkart_groceries(search_query, MAX_PAGES, None if location_set else PINCODE, DEBUG)

        # Add search_query to each product
        if products:
            for product in products:
                product['search_query'] = search_query

            # Save to single CSV (append after first query)
            mode = 'w' if write_header else 'a'
            save_to_csv(products, csv_filename, mode=mode, write_header=write_header)
            write_header = False  # Don't write header again

            total_products += len(products)
            print(f"Total products so far: {total_products}")
        else:
            print(f"\nNo products were scraped for '{search_query}'. Check debug output if enabled.")

        # Add delay between queries (except for the last one)
        if query_index < len(SEARCH_QUERIES):
            print(f"\nWaiting 3 seconds before next query...")
            time.sleep(3)

    print("\n" + "=" * 60)
    print("All scraping completed! Check the output/ folder for CSV files.")
    print(f"Final CSV: {csv_filename}")
    print(f"Total products across all queries: {total_products}")
    print("=" * 60)
