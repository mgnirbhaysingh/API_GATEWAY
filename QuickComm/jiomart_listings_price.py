import requests
import json
import csv
import os
import time
from datetime import datetime
# Base cookies - will be updated with pincode dynamically
cookies = {
    'AKA_A2': 'A',
    '_ALGOLIA': 'anonymous-cb48a90a-c067-4278-b530-b2dac7ced5f8',
}

headers = {
    'accept': '*/*',
    'accept-language': 'en-GB,en;q=0.8',
    'content-type': 'application/json',
    'origin': 'https://www.jiomart.com',
    'priority': 'u=1, i',
    'referer': 'https://www.jiomart.com/search?q=Detergent',
    'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-gpc': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    # 'cookie': 'AKA_A2=A; _ALGOLIA=anonymous-cb48a90a-c067-4278-b530-b2dac7ced5f8; nms_mgo_pincode=122001; nms_mgo_city=Gurgaon; nms_mgo_state_code=HR',
}

json_data = {
    'query': 'Detergent',
    'pageSize': 50,
    'facetSpecs': [
        {
            'facetKey': {
                'key': 'brands',
            },
            'limit': 500,
            'excludedFilterKeys': [
                'brands',
            ],
        },
        {
            'facetKey': {
                'key': 'categories',
            },
            'limit': 500,
            'excludedFilterKeys': [
                'categories',
            ],
        },
        {
            'facetKey': {
                'key': 'attributes.category_level_4',
            },
            'limit': 500,
            'excludedFilterKeys': [
                'attributes.category_level_4',
            ],
        },
        {
            'facetKey': {
                'key': 'attributes.category_level_1',
            },
            'excludedFilterKeys': [
                'attributes.category_level_4',
            ],
        },
        {
            'facetKey': {
                'key': 'attributes.avg_selling_price',
                'return_min_max': True,
                'intervals': [
                    {
                        'minimum': 0.1,
                        'maximum': 100000000,
                    },
                ],
            },
        },
        {
            'facetKey': {
                'key': 'attributes.avg_discount_pct',
                'return_min_max': True,
                'intervals': [
                    {
                        'minimum': 0,
                        'maximum': 99,
                    },
                ],
            },
        },
    ],
    'variantRollupKeys': [
        'variantId',
    ],
    'branch': 'projects/sr-project-jiomart-jfront-prod/locations/global/catalogs/default_catalog/branches/0',
    'queryExpansionSpec': {
        'condition': 'AUTO',
        'pinUnexpandedResults': True,
    },
    'userInfo': {
        'userId': None,
    },
    'spellCorrectionSpec': {
        'mode': 'AUTO',
    },
    # Filter for pincode 560037 (Bangalore) - Update this if using different pincodes
    'filter': 'attributes.status:ANY("active") AND (attributes.mart_availability:ANY("JIO", "JIO_WA")) AND (attributes.available_regions:ANY("PANINDIABOOKS", "PANINDIACRAFT", "PANINDIADIGITAL", "PANINDIAFASHION", "PANINDIAFURNITURE", "2852", "PANINDIAGROCERIES", "PANINDIAHOMEANDKITCHEN", "PANINDIAHOMEIMPROVEMENT", "PANINDIAJEWEL", "PANINDIALOCALSHOPS", "SK36", "PANINDIASTL", "PANINDIAWELLNESS")) AND (attributes.inv_stores_1p:ANY("ALL", "3078", "S535", "SURR", "R300", "SLI1", "TG1K", "SLE4", "T4QF", "S0XN", "SZBL", "Y524", "S4LI", "SJ14", "V012", "R975", "T5CG", "S402", "V017", "SB41", "SLTP", "SANR", "SANS", "SL7Q", "SANQ", "SH09", "V027", "VLOR", "SK36", "254", "420", "60", "270", "SF11", "HX0E", "SX9A", "S0IC", "Y331", "SK1M", "S236", "SD78", "R696", "SJ93", "R396", "SE40", "SLKO", "R804", "Y350") OR attributes.inv_stores_3p:ANY("ALL", "3P8JXZXRFC13", "3PDOLSLBFC03", "3POBGHMEFC02", "3P13PK7AFC14", "3PPKDT3ONFC12", "3P86YSFPFC02", "3PTPX4UZFC01", "3PAB3LTOFC02", "groceries_zone_non-essential_services", "general_zone", "groceries_zone_essential_services", "fashion_zone", "electronics_zone")) AND ( NOT attributes.vertical_code:ANY("ALCOHOL"))',
    'canonicalFilter': 'attributes.status:ANY("active") AND (attributes.mart_availability:ANY("JIO", "JIO_WA")) AND (attributes.available_regions:ANY("PANINDIABOOKS", "PANINDIACRAFT", "PANINDIADIGITAL", "PANINDIAFASHION", "PANINDIAFURNITURE", "2852", "PANINDIAGROCERIES", "PANINDIAHOMEANDKITCHEN", "PANINDIAHOMEIMPROVEMENT", "PANINDIAJEWEL", "PANINDIALOCALSHOPS", "SK36", "PANINDIASTL", "PANINDIAWELLNESS")) AND (attributes.inv_stores_1p:ANY("ALL", "3078", "S535", "SURR", "R300", "SLI1", "TG1K", "SLE4", "T4QF", "S0XN", "SZBL", "Y524", "S4LI", "SJ14", "V012", "R975", "T5CG", "S402", "V017", "SB41", "SLTP", "SANR", "SANS", "SL7Q", "SANQ", "SH09", "V027", "VLOR", "SK36", "254", "420", "60", "270", "SF11", "HX0E", "SX9A", "S0IC", "Y331", "SK1M", "S236", "SD78", "R696", "SJ93", "R396", "SE40", "SLKO", "R804", "Y350") OR attributes.inv_stores_3p:ANY("ALL", "3P8JXZXRFC13", "3PDOLSLBFC03", "3POBGHMEFC02", "3P13PK7AFC14", "3PPKDT3ONFC12", "3P86YSFPFC02", "3PTPX4UZFC01", "3PAB3LTOFC02", "groceries_zone_non-essential_services", "general_zone", "groceries_zone_essential_services", "fashion_zone", "electronics_zone")) AND ( NOT attributes.vertical_code:ANY("ALCOHOL"))',
    'visitorId': 'anonymous-6cde6237-dc70-4c89-92b1-35890a28dd17',
}

def get_location_info_for_pincode(pincode):
    """Get store code and location details for given pincode from JioMart API"""
    try:
        url = f'https://www.jiomart.com/mst/rest/v1/5/pin/{pincode}'
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        result = data.get('result', {})

        # Get store code
        store_code = result.get('master_codes', {}).get('GROCERIES', '')

        # Get city and state
        city = result.get('city', '')
        state_code = result.get('state', '')

        if store_code:
            print(f"Found location info for pincode {pincode}:")
            print(f"  Store code: {store_code}")
            print(f"  City: {city}")
            print(f"  State: {state_code}")

            return {
                'store_code': store_code,
                'city': city,
                'state_code': state_code
            }
        else:
            print(f"No store code found for pincode {pincode}")
            return None
    except Exception as e:
        print(f"Error fetching location info for pincode {pincode}: {e}")
        return None

def get_store_code_for_pincode(pincode):
    """Get store code for given pincode from JioMart API (backward compatibility)"""
    location_info = get_location_info_for_pincode(pincode)
    return location_info['store_code'] if location_info else None

def update_cookies_for_pincode(pincode, city='', state_code=''):
    """Update cookies with pincode, city, and state code"""
    cookies['nms_mgo_pincode'] = str(pincode)
    cookies['nms_mgo_city'] = city
    cookies['nms_mgo_state_code'] = state_code
    print(f"Updated cookies for pincode {pincode}, city {city}, state {state_code}")

def parse_buybox_mrp(buybox_mrp_text):
    """Parse buybox_mrp pipe-delimited string"""
    # Format: "STORE|SELLER_ID|SELLER_NAME||MRP|SELLING_PRICE||DISCOUNT_AMOUNT|DISCOUNT_PCT||..."
    # Example: "6704|1|Reliance Retail||225.0|185.0||40.0|17.0||6|"
    try:
        parts = buybox_mrp_text.split('|')
        if len(parts) >= 9:
            return {
                'store': parts[0],
                'seller_id': parts[1],
                'seller_name': parts[2],
                'mrp': float(parts[4]) if parts[4] else 0,
                'selling_price': float(parts[5]) if parts[5] else 0,
                'discount_amount': float(parts[7]) if parts[7] else 0,
                'discount_percent': float(parts[8]) if parts[8] else 0
            }
    except (IndexError, ValueError) as e:
        print(f"Error parsing buybox_mrp: {e}")
    return None

def find_pricing_for_store(buybox_mrp_list, store_code):
    """Find pricing information for specific store code from buybox_mrp list"""
    if not buybox_mrp_list:
        return None

    # If no store code provided, return first entry
    if not store_code:
        return parse_buybox_mrp(buybox_mrp_list[0])

    # Convert store_code to string for comparison (API might return int or string)
    store_code_str = str(store_code)

    # Try to find matching store code
    for buybox_mrp_text in buybox_mrp_list:
        pricing_info = parse_buybox_mrp(buybox_mrp_text)
        if pricing_info and str(pricing_info['store']) == store_code_str:
            return pricing_info

    # Product not available at the specified store - return None to skip it
    return None

def extract_products(response_data, store_code=None):
    """Extract product information from JioMart API response"""
    products = []

    try:
        results = response_data.get('results', [])

        for result in results:
            product_data = result.get('product', {})

            # Get the first variant (main product variant)
            variants = product_data.get('variants', [])
            if not variants:
                continue

            variant = variants[0]

            # Extract basic info
            product_id = variant.get('id', '')
            title = variant.get('title', '')
            brands = variant.get('brands', [])
            brand = brands[0] if brands else ''

            # Extract attributes
            attributes = variant.get('attributes', {})

            # Get brand ID
            brand_id = attributes.get('brand_id', {}).get('numbers', [0])[0]

            # Get popularity
            popularity = attributes.get('popularity', {}).get('numbers', [0])[0]

            # Parse buybox_mrp for pricing info
            buybox_mrp_list = attributes.get('buybox_mrp', {}).get('text', [])
            pricing_info = None
            seller_name = ''
            product_store_code = ''

            if buybox_mrp_list:
                # Find pricing for the specific store code
                pricing_info = find_pricing_for_store(buybox_mrp_list, store_code)

                # If store code was specified and product not available at that store, skip this product
                if store_code and pricing_info is None:
                    continue

                if pricing_info:
                    product_store_code = pricing_info['store']

            if pricing_info:
                mrp = pricing_info['mrp']
                selling_price = pricing_info['selling_price']
                discount_amount = pricing_info['discount_amount']
                discount_percent = pricing_info['discount_percent']
                seller_name = pricing_info['seller_name']
            else:
                # Fallback to avg prices if buybox_mrp parsing fails (only when no store code specified)
                mrp = 0
                selling_price = attributes.get('avg_selling_price', {}).get('numbers', [0])[0]
                discount_percent = attributes.get('avg_discount_pct', {}).get('numbers', [0])[0]
                discount_amount = 0
                seller_names = attributes.get('seller_names', {}).get('text', [])
                seller_name = seller_names[0] if seller_names else ''

            # Get product URL
            product_uri = variant.get('uri', '')

            # Get image URL
            images = variant.get('images', [])
            image_url = images[0].get('uri', '') if images else ''

            # Get category
            categories = product_data.get('categories', [])
            category = categories[0] if categories else ''

            # Get alternate product code
            alternate_code = attributes.get('alternate_product_code', {}).get('text', [])
            alternate_product_code = alternate_code[0] if alternate_code else ''

            # Get vertical code
            vertical_code = attributes.get('vertical_code', {}).get('text', [])
            vertical = vertical_code[0] if vertical_code else ''

            # Get seller IDs
            seller_ids = attributes.get('seller_ids', {}).get('text', [])
            seller_id = ', '.join(seller_ids) if seller_ids else ''

            products.append({
                'search_query': '',  # Will be filled in later
                'product_id': product_id,
                'title': title,
                'brand': brand,
                'brand_id': brand_id,
                'category': category,
                'vertical': vertical,
                'mrp': mrp,
                'selling_price': selling_price,
                'discount_percent': discount_percent,
                'discount_amount': discount_amount,
                'seller_name': seller_name,
                'seller_id': seller_id,
                'store_code': product_store_code,
                'product_url': product_uri,
                'image_url': image_url,
                'popularity': popularity,
                'alternate_product_code': alternate_product_code
            })

    except Exception as e:
        print(f"Error extracting products: {e}")
        import traceback
        traceback.print_exc()

    return products

def save_to_csv(products, filename, mode='w', write_header=True):
    """Save products to CSV file"""
    if not products:
        print("No products to save!")
        return

    # Create output directory if it doesn't exist
    os.makedirs('output', exist_ok=True)

    # Write to CSV with search_query as first column
    fieldnames = [
        'search_query', 'product_id', 'title', 'brand', 'brand_id', 'category', 'vertical',
        'mrp', 'selling_price', 'discount_percent', 'discount_amount',
        'seller_name', 'seller_id', 'store_code', 'product_url', 'image_url',
        'popularity', 'alternate_product_code'
    ]

    with open(filename, mode, newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(products)

    print(f"\nSuccessfully saved {len(products)} products to {filename}")
    return filename

def scrape_jiomart_products(search_query, pincode, max_pages=10):
    """Scrape JioMart products with pagination support"""
    print(f"Starting JioMart scraper for: {search_query}")
    print(f"Pincode: {pincode}")
    print(f"Maximum pages to scrape: {max_pages}")
    print()

    # Get location info and update cookies
    location_info = get_location_info_for_pincode(pincode)
    if not location_info:
        print(f"Warning: Could not get location info for pincode {pincode}, scraping may fail")
        store_code = None
    else:
        store_code = location_info['store_code']
        # Update cookies with pincode, city, and state code
        update_cookies_for_pincode(
            pincode,
            location_info.get('city', ''),
            location_info.get('state_code', '')
        )

    # Update headers with dynamic referer based on search query
    request_headers = headers.copy()
    request_headers['referer'] = f'https://www.jiomart.com/search?q={search_query}'

    all_products = []
    page_number = 1
    page_token = None

    while page_number <= max_pages:
        print(f"Scraping page {page_number}...")

        # Build request payload
        request_data = {
            'query': search_query,
            'pageSize': 50,
            'facetSpecs': json_data['facetSpecs'],
            'variantRollupKeys': json_data['variantRollupKeys'],
            'branch': json_data['branch'],
            'queryExpansionSpec': json_data['queryExpansionSpec'],
            'userInfo': json_data['userInfo'],
            'spellCorrectionSpec': json_data['spellCorrectionSpec'],
            'filter': json_data['filter'],
            'canonicalFilter': json_data['canonicalFilter'],
            'visitorId': json_data['visitorId']
        }

        # Add page token for subsequent pages
        if page_token:
            request_data['pageToken'] = page_token

        try:
            response = requests.post(
                'https://www.jiomart.com/trex/search',
                cookies=cookies,
                headers=request_headers,
                json=request_data,
                timeout=30
            )
            response.raise_for_status()

            if response.status_code == 200:
                data = response.json()

                # Extract products with store code
                products = extract_products(data, store_code)

                if not products:
                    print(f"No products found on page {page_number}. Stopping.")
                    break

                all_products.extend(products)
                print(f"Found {len(products)} products on page {page_number}")
                print(f"Total products so far: {len(all_products)}")

                # Get next page token
                page_token = data.get('nextPageToken')
                if not page_token:
                    print("No more pages available. Stopping.")
                    break

                page_number += 1
                time.sleep(2)  # Be polite, wait 2 seconds between requests
            else:
                print(f"Error: Received status code {response.status_code}")
                break

        except Exception as e:
            print(f"Error making request: {e}")
            break

    return all_products


if __name__ == "__main__":
    # Configuration
    SEARCH_QUERIES = ['Biscuit', 'chocolates', 'Milk']  # Array of search queries
    PINCODE = "560037"  # Set your delivery pincode
    MAX_PAGES = 10 # Maximum number of pages to scrape

    print("=" * 60)
    print("JioMart Multi-Query Scraper")
    print("=" * 60)
    print(f"Pincode: {PINCODE}")
    print(f"Search Queries: {', '.join(SEARCH_QUERIES)}")
    print(f"Max Pages per Query: {MAX_PAGES}")
    print("=" * 60)

    # Generate single CSV filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_filename = f"output/jiomart_products_pin{PINCODE}_{timestamp}.csv"

    total_products = 0
    write_header = True

    # Iterate through each search query
    for query_index, search_query in enumerate(SEARCH_QUERIES, 1):
        print("\n" + "=" * 60)
        print(f"[Query {query_index}/{len(SEARCH_QUERIES)}] Processing: {search_query}")
        print("=" * 60)

        # Scrape products
        products = scrape_jiomart_products(search_query, PINCODE, MAX_PAGES)

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
            print(f"\nNo products were scraped for '{search_query}'.")

        # Add delay between queries (except for the last one)
        if query_index < len(SEARCH_QUERIES):
            print(f"\nWaiting 3 seconds before next query...")
            time.sleep(3)

    print("\n" + "=" * 60)
    print("All scraping completed! Check the output/ folder for CSV files.")
    print(f"Final CSV: {csv_filename}")
    print(f"Total products across all queries: {total_products}")
    print("=" * 60)

# Note: json_data will not be serialized by requests
# exactly as it was in the original request.
#data = '{"query":"Detergent","pageSize":50,"facetSpecs":[{"facetKey":{"key":"brands"},"limit":500,"excludedFilterKeys":["brands"]},{"facetKey":{"key":"categories"},"limit":500,"excludedFilterKeys":["categories"]},{"facetKey":{"key":"attributes.category_level_4"},"limit":500,"excludedFilterKeys":["attributes.category_level_4"]},{"facetKey":{"key":"attributes.category_level_1"},"excludedFilterKeys":["attributes.category_level_4"]},{"facetKey":{"key":"attributes.avg_selling_price","return_min_max":true,"intervals":[{"minimum":0.1,"maximum":100000000}]}},{"facetKey":{"key":"attributes.avg_discount_pct","return_min_max":true,"intervals":[{"minimum":0,"maximum":99}]}}],"variantRollupKeys":["variantId"],"branch":"projects/sr-project-jiomart-jfront-prod/locations/global/catalogs/default_catalog/branches/0","queryExpansionSpec":{"condition":"AUTO","pinUnexpandedResults":true},"userInfo":{"userId":null},"spellCorrectionSpec":{"mode":"AUTO"},"filter":"attributes.status:ANY(\\"active\\") AND (attributes.mart_availability:ANY(\\"JIO\\", \\"JIO_WA\\")) AND (attributes.available_regions:ANY(\\"PANINDIABOOKS\\", \\"PANINDIACRAFT\\", \\"PANINDIADIGITAL\\", \\"PANINDIAFASHION\\", \\"PANINDIAFURNITURE\\", \\"6701\\", \\"PANINDIAGROCERIES\\", \\"PANINDIAHOMEANDKITCHEN\\", \\"PANINDIAHOMEIMPROVEMENT\\", \\"PANINDIAJEWEL\\", \\"PANINDIALOCALSHOPS\\", \\"PANINDIASTL\\")) AND (attributes.inv_stores_1p:ANY(\\"ALL\\", \\"2364\\", \\"SANR\\", \\"SANS\\", \\"SURR\\", \\"SANQ\\", \\"S4LI\\", \\"S535\\", \\"R975\\", \\"S402\\", \\"R300\\", \\"SLI1\\", \\"V017\\", \\"SB41\\", \\"TG1K\\", \\"SLE4\\", \\"SLTP\\", \\"T4QF\\", \\"S0XN\\", \\"SL7Q\\", \\"SZBL\\", \\"Y524\\", \\"SH09\\", \\"V027\\", \\"SJ14\\", \\"V012\\", \\"VLOR\\", \\"254\\", \\"79\\", \\"60\\", \\"270\\", \\"490\\", \\"R810\\", \\"T7XY\\", \\"SZ9U\\", \\"T7HH\\", \\"R696\\", \\"SE40\\", \\"TB3R\\", \\"TSF4\\", \\"R406\\", \\"SC28\\", \\"SK1M\\", \\"T4IY\\", \\"SJ93\\", \\"R396\\", \\"S3TP\\", \\"SLKO\\") OR attributes.inv_stores_3p:ANY(\\"ALL\\", \\"3P38SR7XFC118\\", \\"3P38SR7XFC117\\", \\"3P8JXZXRFC23\\", \\"3PKKFP6CFC02\\", \\"3P38SR7XFC10\\", \\"3PPKDT3ONFC20\\", \\"3P38SR7XFC116\\", \\"groceries_zone_non-essential_services\\", \\"general_zone\\", \\"groceries_zone_essential_services\\", \\"fashion_zone\\", \\"electronics_zone\\")) AND ( NOT attributes.vertical_code:ANY(\\"ALCOHOL\\"))","canonicalFilter":"attributes.status:ANY(\\"active\\") AND (attributes.mart_availability:ANY(\\"JIO\\", \\"JIO_WA\\")) AND (attributes.available_regions:ANY(\\"PANINDIABOOKS\\", \\"PANINDIACRAFT\\", \\"PANINDIADIGITAL\\", \\"PANINDIAFASHION\\", \\"PANINDIAFURNITURE\\", \\"6701\\", \\"PANINDIAGROCERIES\\", \\"PANINDIAHOMEANDKITCHEN\\", \\"PANINDIAHOMEIMPROVEMENT\\", \\"PANINDIAJEWEL\\", \\"PANINDIALOCALSHOPS\\", \\"PANINDIASTL\\")) AND (attributes.inv_stores_1p:ANY(\\"ALL\\", \\"2364\\", \\"SANR\\", \\"SANS\\", \\"SURR\\", \\"SANQ\\", \\"S4LI\\", \\"S535\\", \\"R975\\", \\"S402\\", \\"R300\\", \\"SLI1\\", \\"V017\\", \\"SB41\\", \\"TG1K\\", \\"SLE4\\", \\"SLTP\\", \\"T4QF\\", \\"S0XN\\", \\"SL7Q\\", \\"SZBL\\", \\"Y524\\", \\"SH09\\", \\"V027\\", \\"SJ14\\", \\"V012\\", \\"VLOR\\", \\"254\\", \\"79\\", \\"60\\", \\"270\\", \\"490\\", \\"R810\\", \\"T7XY\\", \\"SZ9U\\", \\"T7HH\\", \\"R696\\", \\"SE40\\", \\"TB3R\\", \\"TSF4\\", \\"R406\\", \\"SC28\\", \\"SK1M\\", \\"T4IY\\", \\"SJ93\\", \\"R396\\", \\"S3TP\\", \\"SLKO\\") OR attributes.inv_stores_3p:ANY(\\"ALL\\", \\"3P38SR7XFC118\\", \\"3P38SR7XFC117\\", \\"3P8JXZXRFC23\\", \\"3PKKFP6CFC02\\", \\"3P38SR7XFC10\\", \\"3PPKDT3ONFC20\\", \\"3P38SR7XFC116\\", \\"groceries_zone_non-essential_services\\", \\"general_zone\\", \\"groceries_zone_essential_services\\", \\"fashion_zone\\", \\"electronics_zone\\")) AND ( NOT attributes.vertical_code:ANY(\\"ALCOHOL\\"))","visitorId":"anonymous-6cde6237-dc70-4c89-92b1-35890a28dd17"}'
#response = requests.post('https://www.jiomart.com/trex/search', cookies=cookies, headers=headers, data=data)