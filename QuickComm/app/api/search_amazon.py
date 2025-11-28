from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import requests
import time
import re
import json
import logging

from ..db.models import Product
from ..db.utils import save_products_to_db
from ..utils.format_utils import model_to_dict

router = APIRouter()
logger = logging.getLogger(__name__)

# =============================================================================
# TODO: COOKIE REFRESH LOGIC - TO BE IMPLEMENTED
# =============================================================================
#
# ISSUE: Amazon session cookies expire after a certain period, causing:
#   - Location setting to fail
#   - Empty or incomplete search results
#   - 403/401 errors from Amazon
#
# PLANNED IMPLEMENTATION:
#
# 1. Automatic Cookie Refresh (using Playwright/Selenium):
#    async def refresh_amazon_cookies():
#        """Launch headless browser, visit amazon.in, extract fresh cookies"""
#        from playwright.async_api import async_playwright
#        async with async_playwright() as p:
#            browser = await p.chromium.launch(headless=True)
#            page = await browser.new_page()
#            await page.goto('https://www.amazon.in')
#            cookies = await page.context.cookies()
#            # Extract and store: session-id, ubid-acbin, i18n-prefs, lc-acbin
#            await browser.close()
#            return {c['name']: c['value'] for c in cookies if c['name'] in REQUIRED_COOKIES}
#
# 2. Cookie Health Check Endpoint:
#    @router.get("/amazon/cookie-status")
#    def check_cookie_status() -> dict:
#        """Return {"valid": bool, "expires_in": seconds, "last_refresh": timestamp}"""
#
# 3. Background Scheduler (APScheduler/Celery):
#    - Refresh cookies every 6-12 hours
#    - Store in Redis with TTL for distributed access
#    - Alert on refresh failure
#
# 4. Fallback: Accept cookies via API request headers for manual override
#
# CURRENT WORKAROUND:
#   1. Open amazon.in in browser
#   2. DevTools (F12) > Network > Any request > Headers > Cookie
#   3. Copy session-id, ubid-acbin, i18n-prefs, lc-acbin values
#   4. Update DEFAULT_COOKIES below
#
# =============================================================================

# Default cookies - these should be updated with valid session cookies
# WARNING: These cookies WILL EXPIRE. See TODO above for refresh implementation.
DEFAULT_COOKIES = {
    'session-id': '525-9439529-3198566',
    'i18n-prefs': 'INR',
    'lc-acbin': 'en_IN',
    'ubid-acbin': '259-7891041-6972353',
}

DEFAULT_HEADERS = {
    'accept': 'text/html,*/*',
    'accept-language': 'en-GB,en;q=0.9',
    'content-type': 'application/json',
    'origin': 'https://www.amazon.in',
    'priority': 'u=1, i',
    'referer': 'https://www.amazon.in/',
    'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-gpc': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
    'x-requested-with': 'XMLHttpRequest',
}


class AmazonScraper:
    def __init__(self, cookies: Dict[str, str] = None, headers: Dict[str, str] = None, csrf_token: Optional[str] = None):
        self.session = requests.Session()
        self.session.cookies.update(cookies or DEFAULT_COOKIES)
        self.session.headers.update(headers or DEFAULT_HEADERS)
        self.current_location = None
        self.base_url = 'https://www.amazon.in'
        self.csrf_token = csrf_token

    def set_location(self, zip_code: str, store_context: str = 'generic') -> bool:
        """Set the delivery location for the session."""
        logger.info(f"Setting location to PIN code: {zip_code}")

        try:
            address_change_url = f'{self.base_url}/portal-migration/hz/glow/address-change'
            address_payload = {
                'locationType': 'LOCATION_INPUT',
                'zipCode': zip_code,
                'storeContext': store_context,
                'deviceType': 'web',
                'pageType': 'Search',
                'actionSource': 'glow'
            }

            params = {'actionSource': 'glow'}
            request_headers = {}
            if self.csrf_token:
                request_headers['anti-csrftoken-a2z'] = self.csrf_token

            response1 = self.session.post(
                address_change_url,
                params=params,
                json=address_payload,
                headers=request_headers
            )

            if response1.status_code != 200:
                logger.error(f"Address change failed: {response1.status_code}")
                return False

            try:
                address_data = response1.json()
            except Exception:
                logger.error("Failed to parse JSON response")
                return False

            if not address_data.get('isAddressUpdated') or not address_data.get('successful'):
                logger.error(f"Address update unsuccessful: {address_data}")
                return False

            time.sleep(0.5)

            location_label_url = f'{self.base_url}/portal-migration/hz/glow/get-location-label'
            label_params = {
                'storeContext': store_context,
                'pageType': 'Search',
                'actionSource': 'desktop-modal'
            }

            response3 = self.session.get(location_label_url, params=label_params)

            if response3.status_code == 200:
                location_info = response3.json()
                self.current_location = {
                    'zip_code': zip_code,
                    'label': location_info.get('deliveryShortLine', ''),
                }
                return True
            else:
                self.current_location = {'zip_code': zip_code}
                return True

        except Exception as e:
            logger.error(f"Error setting location: {str(e)}")
            return False

    def search_products(self, search_query: str, store: str = 'nowstore', page: int = 1) -> Optional[Dict]:
        """Search for products."""
        logger.info(f"Searching for '{search_query}' (page {page})")

        try:
            search_url = f'{self.base_url}/s/query'
            params = {
                'k': search_query,
                'i': store,
                'page': str(page),
                'qid': str(int(time.time())),
                'ref': 'glow_cls',
            }

            json_data = {'customer-action': 'query'}
            response = self.session.post(search_url, params=params, json=json_data)

            if response.status_code == 200:
                response_text = response.text
                parsed_data = []
                chunks = response_text.split('&&&')

                for chunk in chunks:
                    chunk = chunk.strip()
                    if chunk:
                        try:
                            if chunk.startswith('['):
                                parsed_data.append(json.loads(chunk))
                            elif chunk.startswith('{'):
                                parsed_data.append(json.loads(chunk))
                        except:
                            continue

                if parsed_data:
                    return {'chunks': parsed_data, 'raw_text': response_text}
            return None

        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return None

    def extract_products(self, search_results: Dict, search_query: str) -> List[Product]:
        """Extract product information from search results."""
        if not search_results or 'chunks' not in search_results:
            return []

        products = []

        for chunk in search_results['chunks']:
            if isinstance(chunk, list) and len(chunk) >= 3:
                action_type = chunk[0] if len(chunk) > 0 else None
                data_type = chunk[1] if len(chunk) > 1 else None
                data = chunk[2] if len(chunk) > 2 else None

                if action_type == 'dispatch' and isinstance(data_type, str) and data_type.startswith('data-main-slot') and isinstance(data, dict):
                    html_content = data.get('html', '')
                    if html_content:
                        extracted = self._extract_from_html(html_content, search_query)
                        products.extend(extracted)

        return products

    def _extract_from_html(self, html: str, search_query: str) -> List[Product]:
        """Extract product data from HTML content."""
        products = []

        asin_match = re.search(r'data-asin="([^"]+)"', html)
        if not asin_match:
            return products

        asin = asin_match.group(1)
        if not asin:
            return products

        try:
            title = ''
            title_match = re.search(r'<h2[^>]*aria-label="([^"]+)"', html)
            if title_match:
                title = title_match.group(1).strip()
            else:
                title_match2 = re.search(r'<h2[^>]*>.*?<span[^>]*>([^<]+)</span>.*?</h2>', html, re.DOTALL)
                if title_match2:
                    title = title_match2.group(1).strip()

            price = 0.0
            price_whole_match = re.search(r'<span class="a-price-whole">([^<]+)</span>', html)
            price_fraction_match = re.search(r'<span class="a-price-fraction">([^<]+)</span>', html)
            if price_whole_match:
                price_whole = price_whole_match.group(1).strip().rstrip('.,').replace(',', '')
                price_fraction = price_fraction_match.group(1).strip() if price_fraction_match else '00'
                try:
                    price = float(f"{price_whole}.{price_fraction}")
                except:
                    pass

            rating = 0.0
            rating_match = re.search(r'aria-label="([0-9.]+) out of 5 stars"', html)
            if rating_match:
                try:
                    rating = float(rating_match.group(1))
                except:
                    pass

            image_url = ''
            image_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*s-image[^"]*"', html)
            if image_match:
                image_url = image_match.group(1)

            in_stock = 'Currently unavailable' not in html and 'Out of stock' not in html

            brand = ''
            brand_match = re.search(r'<span class="[^"]*a-size-base-plus[^"]*">([^<]+)</span>', html)
            if brand_match:
                brand = brand_match.group(1).strip()

            if asin and title:
                products.append(Product(
                    platform='amazon',
                    search_query=search_query,
                    store_id='',
                    product_id=asin,
                    variant_id=asin,
                    name=title,
                    brand=brand,
                    mrp=price,
                    price=price,
                    quantity='',
                    in_stock=in_stock,
                    inventory=None,
                    max_allowed_quantity=None,
                    category='',
                    sub_category='',
                    images=[image_url] if image_url else [],
                    organic_rank=0,
                    rating=rating,
                ))

        except Exception as e:
            logger.debug(f"Error extracting product: {e}")

        return products


@router.get("/amazon/search")
def search_amazon(
    query: str,
    pincode: str = "560037",
    store: str = "nowstore",
    max_pages: int = 5,
    csrf_token: Optional[str] = None,
    save_to_db: bool = False
) -> List[Dict[str, Any]]:
    """
    Search for products on Amazon India.

    Args:
        query: Search query string (required)
        pincode: Indian PIN code for delivery location
        store: Store context ('nowstore' for Amazon Fresh)
        max_pages: Maximum pages to fetch (default: 5)
        csrf_token: CSRF token for location changes (optional)
        save_to_db: Whether to save results to database

    Returns:
        List of product dictionaries
    """
    all_products = []

    try:
        scraper = AmazonScraper(csrf_token=csrf_token)

        # Set location
        if pincode:
            if not scraper.set_location(pincode, store_context=store):
                logger.warning(f"Failed to set location for {pincode}, continuing anyway")

        page = 1
        while page <= max_pages:
            logger.info(f"Scraping page {page}/{max_pages}...")

            search_results = scraper.search_products(
                search_query=query,
                store=store,
                page=page
            )

            if not search_results:
                logger.warning(f"No results returned for page {page}. Stopping.")
                break

            products = scraper.extract_products(search_results, query)

            if not products:
                logger.warning(f"No products found on page {page}. Stopping.")
                break

            all_products.extend(products)
            logger.info(f"Extracted {len(products)} products from page {page}")

            page += 1
            time.sleep(2)

        if save_to_db and all_products:
            save_products_to_db(all_products, "products")

        exclude_fields = ["id", "created_at", "updated_at"]
        return [model_to_dict(product, exclude_fields=exclude_fields) for product in all_products]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing Amazon search: {str(e)}"
        )
