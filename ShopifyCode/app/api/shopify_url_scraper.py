"""
Shopify URL Scraper Module
Scrapes product URLs from Shopify collection pages using Playwright.
Based on Shopify_listings_universal.py logic.
"""

import asyncio
from typing import List, Set
from playwright.async_api import async_playwright
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
import time


def _log(msg: str) -> None:
    """Lightweight debug logger for terminal visibility"""
    try:
        print(f"[url_scraper] {time.strftime('%H:%M:%S')} {msg}", flush=True)
    except Exception:
        pass


# Configuration
SCROLL_PAUSE = 1500
MAX_SCROLLS = 25
MAX_PAGES = 50
HEADLESS = True

# Universal selector pool (order matters - more specific first)
SELECTOR_POOL = [
    "a[href*='/products/']",  # Most common Shopify pattern
    "a[href*='/product/']",   # Alternative product URL pattern
    "a.product-link",
    "div.product a",
    ".product-card a",
    ".grid-product__link",
    ".product-tile a",
    "a[href*='product']",     # Generic fallback
    "a[href*='/item']",
    "a[href*='/shop']",
    "a[href*='prd']",
    "a[href*='p/']",
    "a[href*='/collections/']"  # Last resort (catches collection links too)
]

# Pagination detection selectors
PAGINATION_SELECTORS = [
    "a[href*='page=']",
    ".pagination a",
    ".paginate a",
    "nav[role='navigation'] a",
    ".next-page",
    "a.next",
    "a[rel='next']"
]


# Common collection URL patterns to try
COLLECTION_URL_PATTERNS = [
    "/collections/all",
    "/collections/all-products",
    "/collections/all-2",
    "/collections/products",
    "/collections/shop-all",
    "/collections/shop",
    "/collections/catalog",
    "/products",
]


def build_collections_url(base_url: str) -> str:
    """
    Build the collections/all URL from a base domain.
    Examples:
        https://example.com → https://example.com/collections/all
        https://example.com/ → https://example.com/collections/all
    """
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return f"{base}/collections/all"


def get_all_collection_urls(base_url: str) -> list:
    """
    Get all possible collection URLs to try.
    Returns list of URLs to try in order.
    """
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return [f"{base}{pattern}" for pattern in COLLECTION_URL_PATTERNS]


def build_page_url_query(base_url: str, page_num: int) -> str:
    """Build URL with query parameter pagination: ?page=N"""
    parsed = urlparse(base_url)
    query_params = parse_qs(parsed.query)
    query_params['page'] = [str(page_num)]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def build_page_url_path(base_url: str, page_num: int) -> str:
    """Build URL with path-based pagination: /collections/all-2"""
    base = base_url.rstrip('/')
    if page_num == 1:
        return base
    return f"{base}-{page_num}"


async def detect_pagination(page) -> bool:
    """Detect if the page uses pagination."""
    for selector in PAGINATION_SELECTORS:
        try:
            elements = await page.query_selector_all(selector)
            if len(elements) > 0:
                _log(f"Detected pagination using selector: {selector}")
                return True
        except:
            continue
    return False


async def auto_detect_product_selector(page) -> tuple:
    """Try selectors in priority order and pick first one with valid product URLs."""
    for selector in SELECTOR_POOL:
        try:
            elements = await page.query_selector_all(selector)
            count = len(elements)

            # Check if this selector actually finds product URLs
            if count > 0:
                # Test a few links to see if they contain /products/ or /product/
                valid_product_links = 0
                test_limit = min(5, count)  # Test first 5 links

                for i in range(test_limit):
                    try:
                        href = await elements[i].get_attribute("href")
                        if href and ('/products/' in href or '/product/' in href):
                            valid_product_links += 1
                    except:
                        continue

                # If at least some links are product URLs, use this selector
                if valid_product_links > 0:
                    return selector, count
        except:
            continue

    # Fallback: return None if no valid selector found
    return None, 0


async def scroll_page(page, scroll_pause: int = SCROLL_PAUSE, max_scrolls: int = MAX_SCROLLS):
    """Scroll to bottom repeatedly for infinite-scroll pages."""
    _log("Scrolling for infinite scroll...")
    prev_height = await page.evaluate("document.body.scrollHeight")
    scrolls_without_change = 0

    for i in range(max_scrolls):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(scroll_pause)
        new_height = await page.evaluate("document.body.scrollHeight")

        if new_height == prev_height:
            scrolls_without_change += 1
            if scrolls_without_change >= 3:
                _log(f"No more new content after {i+1} scrolls")
                break
        else:
            scrolls_without_change = 0

        prev_height = new_height
        _log(f"Scrolled {i+1} times (height: {new_height})")
    _log("Scrolling complete")


async def extract_product_urls(page, base_url: str) -> List[str]:
    """Detect product blocks and extract product URLs."""
    selector, count = await auto_detect_product_selector(page)

    if not selector or count == 0:
        _log("No suitable product selectors found")
        return []

    _log(f"Using selector '{selector}' — found {count} candidates")

    elements = await page.query_selector_all(selector)
    urls = []

    for el in elements:
        try:
            href = await el.get_attribute("href")
            if href:
                full = urljoin(base_url, href.strip())
                # Filter out non-product URLs - accept both '/product' and '/products/'
                if full not in urls and ('/product' in full or '/products/' in full):
                    urls.append(full)
        except:
            pass

    _log(f"Extracted {len(urls)} product URLs")
    return urls


async def scrape_page(page, url: str, base_url: str, all_urls: Set[str]) -> int:
    """Scrape a single page and add URLs to the set."""
    _log(f"Scraping {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        # Wait for product grid
        try:
            await page.wait_for_selector("a[href*='product'], .product, .grid", timeout=10000)
        except:
            pass

        # Extract product URLs from this page
        page_urls = await extract_product_urls(page, base_url)

        before_count = len(all_urls)
        all_urls.update(page_urls)
        after_count = len(all_urls)
        new_count = after_count - before_count

        _log(f"Added {new_count} new URLs (total: {after_count})")
        return new_count

    except Exception as e:
        _log(f"Error scraping page: {str(e)[:100]}")
        return 0


async def scrape_shopify_product_urls(store_url: str) -> List[str]:
    """
    Main function to scrape all product URLs from a Shopify store.

    Args:
        store_url: Base URL of the Shopify store (e.g., "https://example.com")

    Returns:
        List of product URLs
    """
    _log(f"Starting scrape for store: {store_url}")

    # Build collections URL
    start_url = build_collections_url(store_url)
    _log(f"Collections URL: {start_url}")

    base_url = f"{urlparse(store_url).scheme}://{urlparse(store_url).netloc}"
    all_urls: Set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Load first page
        _log(f"Opening {start_url}")
        await page.goto(start_url, wait_until="domcontentloaded", timeout=30000)

        # Try to wait for product grid hints
        try:
            await page.wait_for_selector("a[href*='product'], .product, .grid", timeout=10000)
            _log("Product grid likely loaded")
        except:
            _log("No obvious grid found. Continuing anyway...")

        # Check if pagination exists
        has_pagination = await detect_pagination(page)

        # Scrape page 1 first
        _log("Scraping page 1...")
        page1_urls = await extract_product_urls(page, base_url)
        all_urls.update(page1_urls)
        _log(f"Page 1: Found {len(page1_urls)} product URLs")

        if has_pagination:
            _log("Pagination detected - will try multiple pages")

            # Try query-based pagination first (?page=2), then path-based (-2)
            pagination_type = None  # Will be determined by testing page 2

            # Test which pagination type works by trying page 2
            query_url = build_page_url_query(start_url, 2)
            path_url = build_page_url_path(start_url, 2)

            _log(f"Testing pagination type with page 2...")
            _log(f"  Query URL: {query_url}")
            _log(f"  Path URL: {path_url}")

            # Try query pagination first
            test_urls_before = len(all_urls)
            await scrape_page(page, query_url, base_url, all_urls)
            if len(all_urls) > test_urls_before:
                pagination_type = "query"
                _log("Using query-based pagination (?page=N)")
            else:
                # Try path-based pagination
                await scrape_page(page, path_url, base_url, all_urls)
                if len(all_urls) > test_urls_before:
                    pagination_type = "path"
                    _log("Using path-based pagination (-N)")
                else:
                    _log("Neither pagination type found products on page 2")

            # Continue with detected pagination type starting from page 3
            if pagination_type:
                pages_without_new_urls = 0

                for page_num in range(3, MAX_PAGES + 1):
                    if pagination_type == "query":
                        page_url = build_page_url_query(start_url, page_num)
                    else:
                        page_url = build_page_url_path(start_url, page_num)

                    new_count = await scrape_page(page, page_url, base_url, all_urls)

                    if new_count == 0:
                        pages_without_new_urls += 1
                        if pages_without_new_urls >= 3:
                            _log("Stopping pagination - no new URLs found in last 3 pages")
                            break
                    else:
                        pages_without_new_urls = 0

                    # Small delay between pages
                    await asyncio.sleep(1)

        else:
            _log("No pagination detected - using infinite scroll approach")

            # Try infinite scroll approach
            await scroll_page(page)

            # Extract URLs after scrolling
            urls = await extract_product_urls(page, base_url)
            all_urls.update(urls)

        await browser.close()

    product_urls = sorted(list(all_urls))
    _log(f"Scraping complete. Found {len(product_urls)} unique product URLs")

    return product_urls


async def scrape_shopify_product_urls_batch(store_urls: List[str]) -> dict:
    """
    Scrape product URLs from multiple Shopify stores concurrently.

    Args:
        store_urls: List of Shopify store base URLs

    Returns:
        Dictionary mapping store URL to list of product URLs
    """
    _log(f"Starting batch scrape for {len(store_urls)} stores")

    results = {}

    # Process stores concurrently with a limit
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent browser instances

    async def scrape_with_semaphore(url: str):
        async with semaphore:
            try:
                product_urls = await scrape_shopify_product_urls(url)
                return url, product_urls
            except Exception as e:
                _log(f"Error scraping {url}: {str(e)[:200]}")
                return url, []

    tasks = [scrape_with_semaphore(url) for url in store_urls]
    scrape_results = await asyncio.gather(*tasks)

    for store_url, product_urls in scrape_results:
        results[store_url] = product_urls

    total_urls = sum(len(urls) for urls in results.values())
    _log(f"Batch scraping complete. Total URLs found: {total_urls}")

    return results
