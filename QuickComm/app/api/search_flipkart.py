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
    'T': 'TI176250251006400090422924463936480118078483415426979424293560624030',
    'K-ACTION': 'null',
    'vh': '724',
    'vw': '1440',
    'dpr': '2',
    'rt': 'null',
}

DEFAULT_HEADERS = {
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


def set_flipkart_location(pincode: str, cookies: Dict) -> bool:
    """Set delivery location using pincode."""
    logger.info(f"Setting delivery location to pincode: {pincode}")

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
            headers=DEFAULT_HEADERS,
            json=location_data,
            timeout=30
        )
        response.raise_for_status()

        if response.status_code == 200:
            response_data = response.json()
            serviceability = response_data.get('RESPONSE', {}).get('serviceability', False)

            if serviceability:
                logger.info(f"Location set successfully to pincode: {pincode}")

                session_data = response_data.get('SESSION', {})
                if session_data.get('sn'):
                    cookies['SN'] = session_data['sn']

                for cookie in response.cookies:
                    cookies[cookie.name] = cookie.value

                return True
            else:
                message = response_data.get('RESPONSE', {}).get('message', 'Grocery delivery not available')
                logger.error(f"Error: {message} for pincode {pincode}")
                return False
        return False

    except Exception as e:
        logger.error(f"Error setting location: {e}")
        return False


def extract_flipkart_products(response_data: Dict, search_query: str, pincode: str) -> List[Product]:
    """Extract product information from Flipkart API response."""
    products = []

    try:
        slots = response_data.get('RESPONSE', {}).get('slots', [])

        for slot in slots:
            widget = slot.get('widget', {})
            widget_type = widget.get('type', '')

            if slot.get('slotType') == 'WIDGET' and widget_type in ['PRODUCT_SUMMARY_EXTENDED', 'PRODUCT_SUMMARY']:
                widget_products = widget.get('data', {}).get('products', [])

                for product in widget_products:
                    try:
                        product_value = product.get('productInfo', {}).get('value', {})

                        product_id = product_value.get('id', '')
                        item_id = product_value.get('itemId', '')
                        listing_id = product_value.get('listingId', '')

                        titles = product_value.get('titles', {})
                        title = titles.get('title', '')
                        new_title = titles.get('newTitle', '')
                        brand = titles.get('superTitle', product_value.get('productBrand', ''))
                        quantity = titles.get('subtitle', '')

                        pricing = product_value.get('pricing', {})
                        final_price = pricing.get('finalPrice', {}).get('value', 0)

                        prices = pricing.get('prices', [])
                        mrp = 0
                        selling_price = 0

                        for price in prices:
                            if price.get('priceType') == 'MRP':
                                mrp = price.get('value', 0)
                            elif price.get('priceType') == 'FSP':
                                selling_price = price.get('value', 0)

                        availability = product_value.get('availability', {})
                        stock_status = availability.get('displayState', '')
                        in_stock = stock_status.lower() not in ['out_of_stock', 'unavailable']

                        images = product_value.get('media', {}).get('images', [])
                        image_url = images[0].get('url', '') if images else ''
                        image_url = image_url.replace('{@width}', '312').replace('{@height}', '312').replace('{@quality}', '70')

                        base_url = product_value.get('baseUrl', '')
                        product_url = f"https://www.flipkart.com{base_url}" if base_url else ''

                        products.append(Product(
                            platform='flipkart',
                            search_query=search_query,
                            store_id=pincode,
                            product_id=str(product_id),
                            variant_id=str(item_id) if item_id else str(listing_id),
                            name=new_title or title,
                            brand=brand,
                            mrp=float(mrp) if mrp else None,
                            price=float(selling_price) if selling_price else float(final_price),
                            quantity=quantity,
                            in_stock=in_stock,
                            inventory=None,
                            max_allowed_quantity=None,
                            category='',
                            sub_category='',
                            images=[image_url] if image_url else [],
                            organic_rank=0,
                            platform_specific_details={
                                'listing_id': listing_id,
                                'product_url': product_url,
                                'stock_status': stock_status,
                            }
                        ))
                    except Exception as e:
                        logger.error(f"Error extracting product: {e}")
                        continue
    except Exception as e:
        logger.error(f"Error parsing response: {e}")

    return products


def fetch_flipkart_data(
    search_query: str,
    page_number: int,
    cookies: Dict
) -> Optional[Dict]:
    """Fetch data from Flipkart API."""
    if page_number == 1:
        page_uri = f'/search?q={search_query}&as=on&as-show=on&marketplace=GROCERY'
    else:
        page_uri = f'/search?q={search_query}&as=on&as-show=on&marketplace=GROCERY&page={page_number}'

    json_data = {
        'pageUri': page_uri,
        'pageContext': {
            'fetchSeoData': page_number == 1,
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
            headers=DEFAULT_HEADERS,
            json=json_data,
            timeout=30
        )
        response.raise_for_status()

        if response.status_code == 200:
            return response.json()
        return None

    except Exception as e:
        logger.error(f"Error making request: {e}")
        return None


@router.get("/flipkart/search")
def search_flipkart(
    query: str = "chocolate",
    pincode: str = "560037",
    max_pages: int = 5,
    save_to_db: bool = False
) -> List[Dict[str, Any]]:
    """
    Search for grocery products on Flipkart.

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
        # Set location
        if pincode:
            if not set_flipkart_location(pincode, cookies):
                logger.warning(f"Failed to set location for {pincode}, continuing anyway")
            time.sleep(1)

        page_number = 1
        while page_number <= max_pages:
            logger.info(f"Scraping page {page_number}...")

            response_data = fetch_flipkart_data(query, page_number, cookies)

            if not response_data:
                logger.warning(f"No response for page {page_number}. Stopping.")
                break

            products = extract_flipkart_products(response_data, query, pincode)

            if not products:
                logger.info(f"No products found on page {page_number}.")

                page_data = response_data.get('RESPONSE', {}).get('pageData', {})
                pagination_context = page_data.get('paginationContextMap', {}).get('federator', {})
                has_more_pages = pagination_context.get('hasMorePages', False)

                if not has_more_pages or page_number >= max_pages:
                    logger.info("No more pages available. Stopping.")
                    break

                page_number += 1
                time.sleep(2)
                continue

            all_products.extend(products)
            logger.info(f"Found {len(products)} products on page {page_number}")

            page_number += 1
            if page_number > max_pages:
                break

            time.sleep(2)

        if save_to_db and all_products:
            save_products_to_db(all_products, "products")

        exclude_fields = ["id", "created_at", "updated_at"]
        return [model_to_dict(product, exclude_fields=exclude_fields) for product in all_products]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing Flipkart search: {str(e)}"
        )
