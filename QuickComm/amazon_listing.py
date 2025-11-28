import requests
import time
import logging
import csv
import os
import json
import re
from typing import Dict, List, Optional, Any
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AmazonCredentialFetcher:
    """
    Fetches fresh CSRF token and cookies from Amazon.in using Playwright.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.base_url = 'https://www.amazon.in'

    def fetch_credentials(self, zip_code: str = '110001') -> Optional[Dict[str, Any]]:
        """
        Launch browser, go to Amazon.in, trigger location change to capture CSRF token.

        Args:
            zip_code: PIN code to set (used to trigger the address-change API)

        Returns:
            Dictionary with 'csrf_token', 'cookies', and 'headers' or None if failed
        """
        logger.info("Launching Playwright to fetch fresh credentials...")

        captured_csrf = None
        captured_cookies = {}

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()

                # Intercept requests to capture CSRF token
                def handle_request(request):
                    nonlocal captured_csrf
                    if 'address-change' in request.url:
                        headers = request.headers
                        csrf = headers.get('anti-csrftoken-a2z')
                        if csrf:
                            captured_csrf = csrf
                            logger.info(f"Captured CSRF token: {csrf[:20]}...")

                page.on('request', handle_request)

                # Go to Amazon.in
                logger.info("Navigating to Amazon.in...")
                page.goto(self.base_url, wait_until='domcontentloaded')
                time.sleep(2)

                # Click on location/delivery selector
                logger.info("Clicking on location selector...")
                try:
                    # Try clicking the delivery location element
                    location_selector = page.locator('#nav-global-location-popover-link, #glow-ingress-block, [data-nav-role="glow"]')
                    location_selector.click(timeout=5000)
                    time.sleep(1)
                except PlaywrightTimeout:
                    logger.warning("Could not find location selector, trying alternative...")
                    # Try alternative selector
                    page.click('#nav-packard-glow-loc-icon', timeout=5000)
                    time.sleep(1)

                # Wait for modal and enter pincode
                logger.info(f"Entering PIN code: {zip_code}")
                try:
                    # Find and fill the pincode input
                    pincode_input = page.locator('input[data-action="GLUXPostalInputAction"], #GLUXZipUpdateInput, input[name="glowZipcode"]')
                    pincode_input.fill(zip_code, timeout=5000)
                    time.sleep(0.5)

                    # Click apply button
                    apply_btn = page.locator('[data-action="GLUXPostalUpdateAction"] input, #GLUXZipUpdate, .a-button-primary input[type="submit"]')
                    apply_btn.click(timeout=5000)
                    time.sleep(2)

                except PlaywrightTimeout as e:
                    logger.error(f"Could not interact with location modal: {e}")

                # Get cookies
                cookies_list = context.cookies()
                for cookie in cookies_list:
                    if cookie['domain'].endswith('amazon.in'):
                        captured_cookies[cookie['name']] = cookie['value']

                logger.info(f"Captured {len(captured_cookies)} cookies")

                browser.close()

                if captured_csrf and captured_cookies:
                    logger.info("Successfully fetched fresh credentials!")
                    return {
                        'csrf_token': captured_csrf,
                        'cookies': captured_cookies
                    }
                elif captured_cookies:
                    logger.warning("Got cookies but no CSRF token captured")
                    return {
                        'csrf_token': None,
                        'cookies': captured_cookies
                    }
                else:
                    logger.error("Failed to capture credentials")
                    return None

            except Exception as e:
                logger.error(f"Playwright error: {e}")
                return None


class AmazonLocationScraper:
    """
    Amazon scraper with location-based functionality.
    Allows scraping product listings for different delivery locations (pin codes).
    """

    def __init__(self, cookies: Dict[str, str], headers: Dict[str, str], csrf_token: Optional[str] = None, auto_refresh: bool = True):
        self.session = requests.Session()
        self.session.cookies.update(cookies)
        self.session.headers.update(headers)
        self.current_location = None
        self.base_url = 'https://www.amazon.in'
        self.csrf_token = csrf_token
        self.auto_refresh = auto_refresh
        self._credential_fetcher = AmazonCredentialFetcher(headless=True)

    def refresh_credentials(self, zip_code: str = '110001') -> bool:
        """
        Refresh CSRF token and cookies using Playwright.

        Returns:
            True if credentials were refreshed successfully
        """
        logger.info("Attempting to refresh credentials via Playwright...")
        credentials = self._credential_fetcher.fetch_credentials(zip_code)

        if credentials:
            # Update cookies
            if credentials.get('cookies'):
                self.session.cookies.clear()
                self.session.cookies.update(credentials['cookies'])
                logger.info("Cookies updated")

            # Update CSRF token
            if credentials.get('csrf_token'):
                self.csrf_token = credentials['csrf_token']
                logger.info("CSRF token updated")
                return True
            else:
                logger.warning("No CSRF token in refreshed credentials")
                return False
        else:
            logger.error("Failed to refresh credentials")
            return False

    def set_location(self, zip_code: str, store_context: str = 'generic', _retry: bool = True) -> bool:
        """
        Set the delivery location for the session.

        Args:
            zip_code: Indian PIN code (e.g., '110001' for Delhi)
            store_context: Store context ('generic' or 'nowstore')

        Returns:
            True if location was set successfully, False otherwise
        """
        logger.info(f"Setting location to PIN code: {zip_code}")

        try:
            # Step 1: Change address
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

            # Prepare headers with CSRF token if available
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
                logger.error(f"Response text: {response1.text[:500]}")
                return False

            # Try to parse JSON response
            try:
                address_data = response1.json()
            except Exception as json_error:
                logger.error(f"Failed to parse JSON response: {json_error}")
                logger.error(f"Response status: {response1.status_code}")
                logger.error(f"Response text: {response1.text[:1000] if response1.text else '(empty)'}")

                # Auto-refresh credentials and retry if enabled
                if _retry and self.auto_refresh:
                    logger.info("Empty/invalid response - attempting to refresh credentials...")
                    if self.refresh_credentials(zip_code):
                        logger.info("Retrying set_location with fresh credentials...")
                        return self.set_location(zip_code, store_context, _retry=False)
                    else:
                        logger.error("Credential refresh failed")
                return False

            if not address_data.get('isAddressUpdated') or not address_data.get('successful'):
                logger.error(f"Address update unsuccessful: {address_data}")
                return False

            logger.info(f"Address changed to: {address_data.get('address', {})}")

            # Small delay to mimic human behavior
            time.sleep(1)

            # Step 2: Refresh UI (optional but helps with session state)
            condo_refresh_url = f'{self.base_url}/portal-migration/hz/glow/condo-refresh-html'
            condo_params = {
                'triggerFeature': 'AddressList',
                'deviceType': 'desktop',
                'pageType': 'Search',
                'storeContext': store_context,
                'locker': '{}'
            }

            response2 = self.session.get(condo_refresh_url, params=condo_params)
            logger.info(f"UI refresh status: {response2.status_code}")

            time.sleep(0.5)

            # Step 3: Get location label for verification
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
                    'city': location_info.get('customerIntent', {}).get('city', ''),
                    'state': location_info.get('customerIntent', {}).get('state', '')
                }
                logger.info(f"Location set successfully: {self.current_location['label']}")
                return True
            else:
                logger.warning(f"Could not verify location label: {response3.status_code}")
                # Still consider it successful if address was updated
                self.current_location = {'zip_code': zip_code}
                return True

        except Exception as e:
            logger.error(f"Error setting location: {str(e)}")
            return False

    def search_products(
        self,
        search_query: str,
        category_id: Optional[str] = None,
        store: str = 'nowstore',
        page: int = 1,
        additional_params: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for products with the current location setting.

        Args:
            search_query: Search term (e.g., 'refined oil 1 ltr')
            category_id: Optional category/department ID (bbn parameter)
            store: Store context ('nowstore' for Amazon Fresh, or other stores)
            page: Page number for pagination
            additional_params: Additional URL parameters

        Returns:
            JSON response from Amazon API, or None if request failed
        """
        if not self.current_location:
            logger.warning("No location set. Results may be inaccurate.")

        logger.info(f"Searching for '{search_query}' (page {page})")

        try:
            search_url = f'{self.base_url}/s/query'

            # Build query parameters
            params = {
                'k': search_query,
                'i': store,
                'page': str(page),
                'qid': str(int(time.time())),
                'ref': 'glow_cls',
            }

            if category_id:
                params['bbn'] = category_id

            if additional_params:
                params.update(additional_params)

            # JSON payload
            json_data = {
                'customer-action': 'query'
            }

            response = self.session.post(search_url, params=params, json=json_data)

            if response.status_code == 200:
                logger.info(f"Search successful (page {page})")

                # Amazon returns data in a special format: &&&[...json...]&&&[...json...]
                # We need to parse this properly
                response_text = response.text

                # Split by &&& and parse each JSON chunk
                parsed_data = []
                chunks = response_text.split('&&&')

                for chunk in chunks:
                    chunk = chunk.strip()
                    if chunk:
                        try:
                            # Parse the JSON chunk
                            data = self._parse_json_chunk(chunk)
                            if data:
                                parsed_data.append(data)
                        except Exception as parse_error:
                            logger.debug(f"Could not parse chunk: {parse_error}")
                            continue

                if parsed_data:
                    logger.info(f"Successfully parsed {len(parsed_data)} data chunks")
                    return {
                        'chunks': parsed_data,
                        'raw_text': response_text
                    }
                else:
                    logger.error("No valid JSON chunks found in response")
                    return None
            else:
                logger.error(f"Search failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return None

    def _parse_json_chunk(self, chunk: str) -> Optional[Any]:
        """
        Parse a single JSON chunk from Amazon's response format.

        Args:
            chunk: A string that may contain JSON data

        Returns:
            Parsed JSON data or None if parsing fails
        """
        chunk = chunk.strip()
        if not chunk:
            return None

        try:
            # Try to parse as JSON array (most common format)
            if chunk.startswith('['):
                return json.loads(chunk)
            # Try to parse as JSON object
            elif chunk.startswith('{'):
                return json.loads(chunk)
            else:
                return None
        except json.JSONDecodeError:
            return None

    def extract_products(self, search_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract product information from search results.

        Args:
            search_results: The parsed search results from search_products()

        Returns:
            List of product dictionaries with extracted information
        """
        if not search_results or 'chunks' not in search_results:
            logger.warning("No search results to extract products from")
            return []

        products = []

        for chunk in search_results['chunks']:
            # Check if this is a dispatch chunk with product data
            if isinstance(chunk, list) and len(chunk) >= 3:
                action_type = chunk[0] if len(chunk) > 0 else None
                data_type = chunk[1] if len(chunk) > 1 else None
                data = chunk[2] if len(chunk) > 2 else None

                # Look for main-slot chunks (includes data-main-slot, data-main-slot:search-result-X)
                if action_type == 'dispatch' and isinstance(data_type, str) and data_type.startswith('data-main-slot') and isinstance(data, dict):
                    html_content = data.get('html', '')

                    if html_content:
                        # Parse products from HTML
                        extracted = self._extract_products_from_html(html_content)
                        products.extend(extracted)

        logger.info(f"Extracted {len(products)} products from search results")
        return products

    def _extract_products_from_html(self, html: str) -> List[Dict[str, Any]]:
        """
        Extract product data from HTML content using regex and string parsing.

        Args:
            html: HTML string containing product listings

        Returns:
            List of product dictionaries
        """
        products = []

        # Each chunk may contain a single product
        # Extract ASIN
        asin_match = re.search(r'data-asin="([^"]+)"', html)
        if not asin_match:
            return products

        asin = asin_match.group(1)
        if not asin:  # Skip empty ASINs (usually ads)
            return products

        product_data = {'asin': asin}

        try:
            # Extract product title from h2 tag aria-label
            title_match = re.search(r'<h2[^>]*aria-label="([^"]+)"', html)
            if title_match:
                product_data['title'] = title_match.group(1).strip()
            else:
                # Fallback: extract from span inside h2
                title_match2 = re.search(r'<h2[^>]*>.*?<span[^>]*>([^<]+)</span>.*?</h2>', html, re.DOTALL)
                if title_match2:
                    product_data['title'] = title_match2.group(1).strip()

            # Extract price (whole and fractional parts)
            price_whole_pattern = r'<span class="a-price-whole">([^<]+)</span>'
            price_fraction_pattern = r'<span class="a-price-fraction">([^<]+)</span>'

            price_whole_match = re.search(price_whole_pattern, html)
            price_fraction_match = re.search(price_fraction_pattern, html)

            if price_whole_match:
                price_whole = price_whole_match.group(1).strip()
                # Remove any trailing dots or commas from whole price
                price_whole = price_whole.rstrip('.,')

                price_fraction = price_fraction_match.group(1).strip() if price_fraction_match else '00'

                # Combine as numeric value
                product_data['price'] = f"{price_whole}.{price_fraction}"
                product_data['price_display'] = f"{price_whole}.{price_fraction}"

            # Extract rating
            rating_pattern = r'aria-label="([0-9.]+) out of 5 stars"'
            rating_match = re.search(rating_pattern, html)
            if rating_match:
                product_data['rating'] = float(rating_match.group(1))

            # Extract number of ratings/reviews
            reviews_pattern = r'aria-label="([0-9,]+) ratings"'
            reviews_match = re.search(reviews_pattern, html)
            if reviews_match:
                product_data['num_reviews'] = reviews_match.group(1).replace(',', '')

            # Extract image URL
            image_pattern = r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*s-image[^"]*"'
            image_match = re.search(image_pattern, html)
            if image_match:
                product_data['image_url'] = image_match.group(1)

            # Extract product URL/link
            url_pattern = r'<a[^>]+href="([^"]+)"[^>]*target="_blank"'
            url_match = re.search(url_pattern, html)
            if url_match:
                product_url = url_match.group(1)
                if not product_url.startswith('http'):
                    product_url = f"{self.base_url}{product_url}"
                product_data['url'] = product_url

            # Extract availability/stock status
            if 'Currently unavailable' in html or 'Out of stock' in html:
                product_data['in_stock'] = False
            else:
                product_data['in_stock'] = True

            # Extract brand (if available)
            brand_pattern = r'<span class="[^"]*a-size-base-plus[^"]*">([^<]+)</span>'
            brand_match = re.search(brand_pattern, html)
            if brand_match:
                product_data['brand'] = brand_match.group(1).strip()

            # Only add if we have at least ASIN and title
            if 'asin' in product_data and 'title' in product_data:
                products.append(product_data)
                logger.debug(f"Extracted product: {product_data.get('title', 'Unknown')[:50]}...")

        except Exception as e:
            logger.debug(f"Error extracting product: {e}")

        return products

    def save_products_to_csv(self, products: List[Dict[str, Any]], filename: str, mode: str = 'w', write_header: bool = True) -> bool:
        """
        Save extracted products to a CSV file.

        Args:
            products: List of product dictionaries
            filename: Output CSV filename
            mode: File write mode ('w' for write, 'a' for append)
            write_header: Whether to write CSV header

        Returns:
            True if saved successfully, False otherwise
        """
        if not products:
            logger.warning("No products to save")
            return False

        try:
            # Create output directory if it doesn't exist
            output_dir = os.path.dirname(filename)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"Created output directory: {output_dir}")

            # Define CSV columns with search_query as first column
            fieldnames = [
                'search_query',
                'asin',
                'title',
                'price',
                'price_display',
                'rating',
                'num_reviews',
                'in_stock',
                'brand',
                'image_url',
                'url'
            ]

            with open(filename, mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')

                if write_header:
                    writer.writeheader()

                for product in products:
                    writer.writerow(product)

            logger.info(f"Successfully saved {len(products)} products to {filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving products to CSV: {e}")
            return False

    def scrape_with_pagination(
        self,
        search_query: str,
        category_id: Optional[str] = None,
        store: str = 'nowstore',
        max_pages: int = 10,
        delay_between_pages: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Scrape products across multiple pages for a single search query.

        Args:
            search_query: Product search query
            category_id: Optional category ID
            store: Store context
            max_pages: Maximum number of pages to scrape
            delay_between_pages: Delay in seconds between page requests

        Returns:
            List of all products extracted from all pages
        """
        all_products = []
        page = 1

        logger.info(f"Starting paginated scrape for '{search_query}' (max {max_pages} pages)")

        while page <= max_pages:
            logger.info(f"Scraping page {page}/{max_pages}...")

            # Search for products on current page
            search_results = self.search_products(
                search_query=search_query,
                category_id=category_id,
                store=store,
                page=page
            )

            if not search_results:
                logger.warning(f"No results returned for page {page}. Stopping pagination.")
                break

            # Extract products from this page
            products = self.extract_products(search_results)

            if not products:
                logger.warning(f"No products found on page {page}. Stopping pagination.")
                break

            all_products.extend(products)
            logger.info(f"Extracted {len(products)} products from page {page}")
            logger.info(f"Total products so far: {len(all_products)}")

            # Move to next page
            page += 1

            # Add delay before next page (except for last iteration)
            if page <= max_pages:
                time.sleep(delay_between_pages)

        logger.info(f"Pagination completed. Total products extracted: {len(all_products)}")
        return all_products

    def scrape_multi_location(
        self,
        search_query: str,
        zip_codes: List[str],
        category_id: Optional[str] = None,
        store: str = 'nowstore',
        delay_between_locations: float = 3.0
    ) -> Dict[str, Any]:
        """
        Scrape the same search query across multiple locations.

        Args:
            search_query: Product search query
            zip_codes: List of Indian PIN codes
            category_id: Optional category ID
            store: Store context
            delay_between_locations: Delay in seconds between location changes

        Returns:
            Dictionary mapping zip_code -> search results
        """
        results = {}

        logger.info(f"Starting multi-location scrape for '{search_query}' across {len(zip_codes)} locations")

        for i, zip_code in enumerate(zip_codes, 1):
            logger.info(f"Processing location {i}/{len(zip_codes)}: {zip_code}")

            # Set location
            if not self.set_location(zip_code, store_context=store):
                logger.error(f"Failed to set location for {zip_code}, skipping...")
                results[zip_code] = {
                    'error': 'Failed to set location',
                    'location_info': None,
                    'products': None
                }
                continue

            # Add delay to avoid rate limiting
            time.sleep(1)

            # Search for products
            search_results = self.search_products(
                search_query=search_query,
                category_id=category_id,
                store=store
            )

            # Store results
            results[zip_code] = {
                'location_info': self.current_location,
                'products': search_results,
                'error': None if search_results else 'Search failed'
            }

            # Delay before next location (except for last iteration)
            if i < len(zip_codes):
                logger.info(f"Waiting {delay_between_locations}s before next location...")
                time.sleep(delay_between_locations)

        logger.info(f"Multi-location scrape completed. Processed {len(results)} locations")
        return results


# Configuration - Update these with your session cookies
DEFAULT_COOKIES = {
    'session-id': '261-8088829-6329855',
    'session-id-time': '2082787201l',
    'i18n-prefs': 'INR',
    'lc-acbin': 'en_IN',
    'ubid-acbin': '262-2605331-3776851',
    'session-token': 'qjGA9RxfDFqnzaSr70S6njXMjoJZMWHGTz5vm08kjkFXnmNprW2TS7mWhDMukkW39bP9bNucyKDjR4K+HWZMF9eFtPmb7BNgKAMP2ZWvQj10ycmfe7/ajknuJ1KItvcXcZ0GtdJ2wL8SMqZFFegAmSHM4eOG4nVQsqdngszgmrcpptclLvD4qea9SryTbFZBGuuwOci2BON4ljnNnFnD13+un4C4sQUmvMtyqdWjRzXQnHwVhDhkAGN+SDb47O1140XEwaBgJpw2nwJev+tlCXlTiKNopzG5VAmDivaEv67A1LQHs9KTv/ktKMhdylJaIlShY/SgZiLqivLaIiV1dD8PvYfY9UAz',
    'csm-hit': 'tb:P101B4ATSCSNCTYE63H6+sa-BZTVW0J0MSZYBRBBJS4C-7M3WGQJDTJQ06DMJ21GE|1764235889598&t:1764235889598&adb:adblk_yes',
    'rxc': 'AMV7M256qa/EXuEUStI',
}

DEFAULT_HEADERS = {
    'accept': 'text/html,*/*',
    'accept-language': 'en-GB,en;q=0.6',
    'content-type': 'application/json',
    'origin': 'https://www.amazon.in',
    'priority': 'u=1, i',
    'referer': 'https://www.amazon.in/',
    'sec-ch-ua': '"Chromium";v="142", "Brave";v="142", "Not_A Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-ch-ua-platform-version': '"15.5.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-gpc': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    'x-amazon-rush-fingerprints': 'AmazonRushAssetLoader:1202F8AA9B9E3A62A246BF3FA42812770110C222|AmazonRushFramework:BD8C9BDF8F6997A02C2999B0AFC58B7C25924910|AmazonRushRouter:759C54280619C2EE883F19F8B2A1504C35E912A0',
    'x-amazon-s-fallback-url': 'https://www.amazon.in/',
    'x-amazon-s-mismatch-behavior': 'FALLBACK',
    'x-amazon-s-swrs-version': 'CA59FD487D3FF5EFD88F40AE68461CB7,D41D8CD98F00B204E9800998ECF8427E',
    'x-requested-with': 'XMLHttpRequest',
}


# CSRF Token - IMPORTANT: You need to extract this from your browser session
# Look for 'anti-csrftoken-a2z' header in your browser's network tab when changing location
# This token is required for location changes to work
DEFAULT_CSRF_TOKEN = 'hFkrL6SHsSMOkrbx7zhpY4jBSzYbJYhknqsTE0me311zAAAAAGkoGnQAAAAB'


# Example usage
if __name__ == '__main__':
    from datetime import datetime

    print("=" * 60)
    print("Amazon Location-Based Scraper")
    print("=" * 60)

    # Array of search queries
    SEARCH_QUERIES = ['Biscuit', 'chocolates', 'Milk']

    # Initialize scraper with CSRF token
    scraper = AmazonLocationScraper(DEFAULT_COOKIES, DEFAULT_HEADERS, DEFAULT_CSRF_TOKEN)

    # Set location once for all searches
    if scraper.set_location('560037'):  # Bangalore
        print(f"\nLocation set successfully: {scraper.current_location}")

        # Generate single CSV filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"output/amazon_products_{scraper.current_location['zip_code']}_{timestamp}.csv"

        total_products = 0
        write_header = True

        # Iterate through each search query
        for query_index, search_query in enumerate(SEARCH_QUERIES, 1):
            print("\n" + "=" * 60)
            print(f"[Query {query_index}/{len(SEARCH_QUERIES)}] Searching for: {search_query}")
            print("-" * 60)

            # Use pagination to scrape multiple pages
            products = scraper.scrape_with_pagination(
                search_query=search_query,
                category_id='16392737031',
                store='nowstore',
                max_pages=10,
                delay_between_pages=2.0
            )

            if products:
                print(f"\nPaginated search successful!")
                print(f"\nTotal products found: {len(products)}")

                # Add search_query to each product
                for product in products:
                    product['search_query'] = search_query

                # Save to single CSV (append after first query)
                mode = 'w' if write_header else 'a'
                scraper.save_products_to_csv(products, csv_filename, mode=mode, write_header=write_header)
                write_header = False  # Don't write header again

                total_products += len(products)
                print(f"Products appended to: {csv_filename}")
                print(f"Total products so far: {total_products}")

                # Display first 3 products
                for i, product in enumerate(products[:3], 1):
                    print(f"\n--- Product {i} ---")
                    print(f"Title: {product.get('title', 'N/A')}")
                    print(f"ASIN: {product.get('asin', 'N/A')}")
                    print(f"Price: {product.get('price_display', 'N/A')}")
                    print(f"Rating: {product.get('rating', 'N/A')}")
                    print(f"In Stock: {product.get('in_stock', 'N/A')}")
            else:
                print(f"Search failed or no products found for '{search_query}'")

            # Add delay between queries (except for the last one)
            if query_index < len(SEARCH_QUERIES):
                print(f"\nWaiting 3 seconds before next query...")
                time.sleep(3)
    else:
        print("Failed to set location. Aborting scraping.")

    print("\n" + "=" * 60)
    print("All scraping completed! Check the output/ folder for CSV files.")
    print(f"Final CSV: {csv_filename if scraper.current_location else 'N/A'}")
    print(f"Total products across all queries: {total_products if scraper.current_location else 0}")
    print("=" * 60)
