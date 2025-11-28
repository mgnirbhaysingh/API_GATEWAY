from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import requests
import time
import logging

from ..db.models import Product
from ..db.utils import save_products_to_db
from ..utils.format_utils import model_to_dict

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_COOKIES = {
    'AKA_A2': 'A',
    '_ALGOLIA': 'anonymous-cb48a90a-c067-4278-b530-b2dac7ced5f8',
}

DEFAULT_HEADERS = {
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
}

# Default filter for Bangalore (560037) - will be updated based on pincode
DEFAULT_FILTER = 'attributes.status:ANY("active") AND (attributes.mart_availability:ANY("JIO", "JIO_WA")) AND (attributes.available_regions:ANY("PANINDIABOOKS", "PANINDIACRAFT", "PANINDIADIGITAL", "PANINDIAFASHION", "PANINDIAFURNITURE", "2852", "PANINDIAGROCERIES", "PANINDIAHOMEANDKITCHEN", "PANINDIAHOMEIMPROVEMENT", "PANINDIAJEWEL", "PANINDIALOCALSHOPS", "SK36", "PANINDIASTL", "PANINDIAWELLNESS")) AND ( NOT attributes.vertical_code:ANY("ALCOHOL"))'


def get_jiomart_location_info(pincode: str) -> Optional[Dict]:
    """Get store code and location details for given pincode from JioMart API."""
    try:
        url = f'https://www.jiomart.com/mst/rest/v1/5/pin/{pincode}'
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()
        result = data.get('result', {})

        store_code = result.get('master_codes', {}).get('GROCERIES', '')
        city = result.get('city', '')
        state_code = result.get('state', '')

        if store_code:
            logger.info(f"Found location info for pincode {pincode}: Store={store_code}, City={city}")
            return {
                'store_code': store_code,
                'city': city,
                'state_code': state_code
            }
        else:
            logger.warning(f"No store code found for pincode {pincode}")
            return None
    except Exception as e:
        logger.error(f"Error fetching location info for pincode {pincode}: {e}")
        return None


def parse_buybox_mrp(buybox_mrp_text: str) -> Optional[Dict]:
    """Parse buybox_mrp pipe-delimited string."""
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
        logger.debug(f"Error parsing buybox_mrp: {e}")
    return None


def find_pricing_for_store(buybox_mrp_list: List[str], store_code: str) -> Optional[Dict]:
    """Find pricing information for specific store code from buybox_mrp list."""
    if not buybox_mrp_list:
        return None

    if not store_code:
        return parse_buybox_mrp(buybox_mrp_list[0])

    store_code_str = str(store_code)

    for buybox_mrp_text in buybox_mrp_list:
        pricing_info = parse_buybox_mrp(buybox_mrp_text)
        if pricing_info and str(pricing_info['store']) == store_code_str:
            return pricing_info

    return None


def extract_jiomart_products(response_data: Dict, search_query: str, store_code: Optional[str] = None) -> List[Product]:
    """Extract product information from JioMart API response."""
    products = []

    try:
        results = response_data.get('results', [])

        for result in results:
            product_data = result.get('product', {})

            variants = product_data.get('variants', [])
            if not variants:
                continue

            variant = variants[0]

            product_id = variant.get('id', '')
            title = variant.get('title', '')
            brands = variant.get('brands', [])
            brand = brands[0] if brands else ''

            attributes = variant.get('attributes', {})

            buybox_mrp_list = attributes.get('buybox_mrp', {}).get('text', [])
            pricing_info = None
            product_store_code = ''

            if buybox_mrp_list:
                pricing_info = find_pricing_for_store(buybox_mrp_list, store_code)

                if store_code and pricing_info is None:
                    continue

                if pricing_info:
                    product_store_code = pricing_info['store']

            if pricing_info:
                mrp = pricing_info['mrp']
                selling_price = pricing_info['selling_price']
            else:
                mrp = 0
                selling_price = attributes.get('avg_selling_price', {}).get('numbers', [0])[0]

            product_uri = variant.get('uri', '')

            images = variant.get('images', [])
            image_url = images[0].get('uri', '') if images else ''

            categories = product_data.get('categories', [])
            category = categories[0] if categories else ''

            vertical_code = attributes.get('vertical_code', {}).get('text', [])
            vertical = vertical_code[0] if vertical_code else ''

            popularity = attributes.get('popularity', {}).get('numbers', [0])[0]

            products.append(Product(
                platform='jiomart',
                search_query=search_query,
                store_id=product_store_code,
                product_id=str(product_id),
                variant_id=str(product_id),
                name=title,
                brand=brand,
                mrp=float(mrp) if mrp else None,
                price=float(selling_price) if selling_price else 0,
                quantity='',
                in_stock=True,
                inventory=None,
                max_allowed_quantity=None,
                category=category,
                sub_category=vertical,
                images=[image_url] if image_url else [],
                organic_rank=0,
                platform_specific_details={
                    'product_url': product_uri,
                    'popularity': popularity,
                }
            ))

    except Exception as e:
        logger.error(f"Error extracting products: {e}")
        import traceback
        traceback.print_exc()

    return products


def fetch_jiomart_data(
    search_query: str,
    page_token: Optional[str] = None,
    cookies: Dict = None,
    filter_str: str = DEFAULT_FILTER
) -> Optional[Dict]:
    """Fetch data from JioMart search API."""
    cookies = cookies or DEFAULT_COOKIES.copy()

    request_headers = DEFAULT_HEADERS.copy()
    request_headers['referer'] = f'https://www.jiomart.com/search?q={search_query}'

    request_data = {
        'query': search_query,
        'pageSize': 50,
        'facetSpecs': [
            {'facetKey': {'key': 'brands'}, 'limit': 500, 'excludedFilterKeys': ['brands']},
            {'facetKey': {'key': 'categories'}, 'limit': 500, 'excludedFilterKeys': ['categories']},
            {'facetKey': {'key': 'attributes.category_level_4'}, 'limit': 500, 'excludedFilterKeys': ['attributes.category_level_4']},
            {'facetKey': {'key': 'attributes.category_level_1'}, 'excludedFilterKeys': ['attributes.category_level_4']},
            {'facetKey': {'key': 'attributes.avg_selling_price', 'return_min_max': True, 'intervals': [{'minimum': 0.1, 'maximum': 100000000}]}},
            {'facetKey': {'key': 'attributes.avg_discount_pct', 'return_min_max': True, 'intervals': [{'minimum': 0, 'maximum': 99}]}},
        ],
        'variantRollupKeys': ['variantId'],
        'branch': 'projects/sr-project-jiomart-jfront-prod/locations/global/catalogs/default_catalog/branches/0',
        'queryExpansionSpec': {'condition': 'AUTO', 'pinUnexpandedResults': True},
        'userInfo': {'userId': None},
        'spellCorrectionSpec': {'mode': 'AUTO'},
        'filter': filter_str,
        'canonicalFilter': filter_str,
        'visitorId': 'anonymous-6cde6237-dc70-4c89-92b1-35890a28dd17'
    }

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
            return response.json()
        return None

    except Exception as e:
        logger.error(f"Error making request: {e}")
        return None


@router.get("/jiomart/search")
def search_jiomart(
    query: str = "chocolate",
    pincode: str = "560037",
    max_pages: int = 5,
    save_to_db: bool = False
) -> List[Dict[str, Any]]:
    """
    Search for products on JioMart.

    Args:
        query: Search query string
        pincode: Indian PIN code for delivery location
        max_pages: Maximum pages to fetch (default: 5)
        save_to_db: Whether to save results to database

    Returns:
        List of product dictionaries
    """
    all_products = []
    cookies = DEFAULT_COOKIES.copy()

    try:
        # Get location info
        location_info = get_jiomart_location_info(pincode)
        store_code = None

        if location_info:
            store_code = location_info['store_code']
            cookies['nms_mgo_pincode'] = str(pincode)
            cookies['nms_mgo_city'] = location_info.get('city', '')
            cookies['nms_mgo_state_code'] = location_info.get('state_code', '')
        else:
            logger.warning(f"Could not get location info for pincode {pincode}, continuing anyway")

        page_number = 1
        page_token = None

        while page_number <= max_pages:
            logger.info(f"Scraping page {page_number}...")

            response_data = fetch_jiomart_data(
                search_query=query,
                page_token=page_token,
                cookies=cookies
            )

            if not response_data:
                logger.warning(f"No response for page {page_number}. Stopping.")
                break

            products = extract_jiomart_products(response_data, query, store_code)

            if not products:
                logger.info(f"No products found on page {page_number}. Stopping.")
                break

            all_products.extend(products)
            logger.info(f"Found {len(products)} products on page {page_number}")

            page_token = response_data.get('nextPageToken')
            if not page_token:
                logger.info("No more pages available. Stopping.")
                break

            page_number += 1
            time.sleep(2)

        if save_to_db and all_products:
            save_products_to_db(all_products, "products")

        exclude_fields = ["id", "created_at", "updated_at"]
        return [model_to_dict(product, exclude_fields=exclude_fields) for product in all_products]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing JioMart search: {str(e)}"
        )
