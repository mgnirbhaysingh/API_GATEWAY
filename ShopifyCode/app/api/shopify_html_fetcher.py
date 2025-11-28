"""
Shopify HTML Fetcher Module
Fetches HTML pages from Shopify product URLs and extracts textual content.
Makes one request per product (not per variant) to get comprehensive product descriptions.
"""

import requests
import time
from typing import Dict, Optional, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from html import unescape


def _log(msg: str) -> None:
    """Lightweight debug logger for terminal visibility"""
    try:
        print(f"[shopify_html_fetcher] {time.strftime('%H:%M:%S')} {msg}", flush=True)
    except Exception:
        pass


# HTTP headers for the request (based on the curl example)
HEADERS = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-GB,en;q=0.7',
    'cache-control': 'max-age=0',
    'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'sec-gpc': '1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
}

# Cookies (basic localization)
COOKIES = {
    'localization': 'IN'
}


def _extract_text_from_html(html_content: str) -> str:
    """
    Extract all textual content from HTML by removing tags.
    Returns clean text suitable for LLM processing.
    """
    if not html_content:
        _log("WARNING: Empty HTML content provided")
        return ""

    try:
        _log(f"Starting HTML text extraction from {len(html_content)} chars of HTML")

        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements (but keep most content)
        for script in soup(["script", "style", "noscript"]):
            script.decompose()

        # Get text with newline separators to preserve structure
        text = soup.get_text(separator='\n', strip=False)
        _log(f"After BeautifulSoup extraction: {len(text)} chars")

        # More gentle whitespace cleanup - preserve line structure
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if line:  # Only keep non-empty lines
                lines.append(line)

        # Join with spaces to create readable text
        text = ' '.join(lines)
        _log(f"After whitespace cleanup: {len(text)} chars")

        # Decode HTML entities
        text = unescape(text)

        final_length = len(text.strip())
        _log(f"Final extracted text length: {final_length} chars")

        if final_length < 500:
            _log(f"WARNING: Very short extracted text ({final_length} chars): '{text[:200]}'")

        return text.strip()

    except Exception as e:
        _log(f"ERROR extracting text from HTML: {str(e)[:200]}")
        return ""


def extract_variant_stock_info(html_content: str) -> Dict[str, int]:
    """
    Extract variant stock information from HTML.
    Returns a dictionary mapping size values to inventory quantity (0 or 50).

    Detects out-of-stock variants by looking for:
    - class="product-variant__item--disabled"
    - class="disabled" on input elements
    - soldout/sold-out/unavailable classes
    - disabled attribute on inputs

    Args:
        html_content: Raw HTML content from product page

    Returns:
        Dictionary with size as key and quantity as value (0 for out of stock, 50 for in stock)
    """
    stock_info = {}

    if not html_content:
        return stock_info

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Pattern 1: Look for product-variant__item containers with disabled class
        variant_items = soup.find_all('div', class_=lambda x: x and 'product-variant__item' in str(x))

        for item in variant_items:
            # Check if this item is disabled
            is_disabled = False

            # Check if the container has disabled class
            item_classes = item.get('class', [])
            # Convert all classes to lowercase strings for comparison
            item_classes_lower = [str(c).lower() for c in item_classes]

            # Check for disabled in any class name (e.g., 'product-variant__item--disabled')
            if any('disabled' in c for c in item_classes_lower):
                is_disabled = True
                _log(f"Found disabled class in item: {item_classes}")

            # Find the input element to get the size value
            input_elem = item.find('input')
            if input_elem:
                size_value = input_elem.get('value', '').strip()

                # Check if input itself is disabled (attribute or class)
                input_classes = input_elem.get('class', [])
                input_classes_lower = [str(c).lower().strip() for c in input_classes]

                # Check for 'disabled' as exact match in classes list or as attribute
                if input_elem.has_attr('disabled'):
                    is_disabled = True
                    _log(f"Found 'disabled' attribute for size '{size_value}'")
                elif 'disabled' in input_classes_lower:
                    is_disabled = True
                    _log(f"Found 'disabled' class for size '{size_value}': classes={input_classes}")

                if size_value:
                    stock_info[size_value] = 0 if is_disabled else 50
                    _log(f"FINAL: Size '{size_value}': {'OUT OF STOCK (qty=0)' if is_disabled else 'IN STOCK (qty=50)'}")

        # Pattern 2: Look for select option elements (dropdown)
        select_options = soup.find_all('option')
        for option in select_options:
            if option.has_attr('disabled') or 'sold' in option.get_text().lower():
                size_value = option.get('value', '').strip()
                if size_value and size_value not in stock_info:
                    stock_info[size_value] = 0
                    _log(f"Size '{size_value}': OUT OF STOCK (from select option)")

        # Pattern 3: Look for button elements with size variants
        variant_buttons = soup.find_all(['button', 'a'], class_=lambda x: x and any(
            keyword in str(x).lower() for keyword in ['variant', 'swatch', 'size']
        ))

        for button in variant_buttons:
            is_disabled = button.has_attr('disabled')
            button_classes = button.get('class', [])

            # Check for soldout/unavailable classes
            if any(keyword in str(c).lower() for c in button_classes for keyword in ['disabled', 'soldout', 'sold-out', 'unavailable']):
                is_disabled = True

            # Try to extract size from value, data attributes, or text
            size_value = (
                button.get('value') or
                button.get('data-value') or
                button.get('data-variant-value') or
                button.get_text().strip()
            )

            if size_value and len(size_value) <= 10:  # Reasonable size value length
                if size_value not in stock_info:
                    stock_info[size_value] = 0 if is_disabled else 50
                    _log(f"Size '{size_value}': {'OUT OF STOCK' if is_disabled else 'IN STOCK'} (from button)")

        _log(f"Extracted stock info for {len(stock_info)} size variants")

    except Exception as e:
        _log(f"ERROR extracting variant stock info: {str(e)[:200]}")

    return stock_info


def fetch_html_content(product_url: str) -> Optional[str]:
    """
    Fetch HTML content from a Shopify product URL and extract textual content.
    Makes one request per product (not per variant).

    Args:
        product_url: The full product URL (e.g., https://store.com/products/item-name)

    Returns:
        Extracted textual content as a string, or None if failed
    """
    try:
        # Clean URL - remove any query parameters or variant IDs
        base_url = product_url.split('?')[0]

        _log(f"Fetching HTML from {base_url}")

        # Set referer to collections/all for better compatibility
        parsed = urlparse(base_url)
        referer = f"{parsed.scheme}://{parsed.netloc}/collections/all"

        headers = HEADERS.copy()
        headers['referer'] = referer

        # Make request
        response = requests.get(
            base_url,
            headers=headers,
            cookies=COOKIES,
            timeout=30,
            allow_redirects=True
        )

        response.raise_for_status()
        _log(f"Received HTML response: status={response.status_code}, size={len(response.text)} chars")

        # Extract text content
        text_content = _extract_text_from_html(response.text)

        if text_content:
            _log(f"Extracted {len(text_content)} characters of text content")
            return text_content
        else:
            _log("No text content extracted from HTML")
            return None

    except requests.exceptions.RequestException as e:
        _log(f"ERROR fetching HTML from {product_url}: {str(e)[:200]}")
        return None
    except Exception as e:
        _log(f"ERROR processing HTML from {product_url}: {str(e)[:200]}")
        return None


def fetch_html_content_for_products(product_urls: list[str]) -> tuple[Dict[str, str], Dict[str, Dict[str, int]]]:
    """
    Fetch HTML content for multiple product URLs.
    Returns both text content and stock information.

    Args:
        product_urls: List of product URLs

    Returns:
        Tuple of:
        - Dictionary with product_handle as key and extracted text as value
        - Dictionary with product_handle as key and stock info dict as value
          (stock info dict maps size -> quantity)
    """
    html_content_map = {}
    stock_info_map = {}

    # Deduplicate URLs by extracting product handles
    # This ensures one request per product, not per variant
    unique_products = {}

    for url in product_urls:
        # Extract product handle from URL
        # Example: https://store.com/products/item-name -> item-name
        base_url = url.split('?')[0]
        parts = base_url.rstrip('/').split('/')

        if 'products' in parts:
            product_idx = parts.index('products')
            if product_idx + 1 < len(parts):
                product_handle = parts[product_idx + 1]
                if product_handle not in unique_products:
                    unique_products[product_handle] = base_url

    _log(f"Found {len(unique_products)} unique products from {len(product_urls)} URLs")

    # Fetch HTML for each unique product
    for idx, (product_handle, url) in enumerate(unique_products.items(), start=1):
        _log(f"[{idx}/{len(unique_products)}] Processing product: {product_handle}")

        # Fetch HTML and extract both text and stock info
        try:
            # Clean URL - remove any query parameters or variant IDs
            base_url = url.split('?')[0]

            # Set referer to collections/all for better compatibility
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            referer = f"{parsed.scheme}://{parsed.netloc}/collections/all"

            headers = HEADERS.copy()
            headers['referer'] = referer

            # Make request
            response = requests.get(
                base_url,
                headers=headers,
                cookies=COOKIES,
                timeout=30,
                allow_redirects=True
            )

            response.raise_for_status()

            # Extract text content
            html_text = _extract_text_from_html(response.text)
            if html_text:
                html_content_map[product_handle] = html_text

            # Extract stock information
            stock_info = extract_variant_stock_info(response.text)
            if stock_info:
                stock_info_map[product_handle] = stock_info

        except Exception as e:
            _log(f"ERROR processing {product_handle}: {str(e)[:200]}")

        # Be polite - add small delay between requests
        if idx < len(unique_products):
            time.sleep(0.5)

    _log(f"Successfully fetched HTML content for {len(html_content_map)}/{len(unique_products)} products")
    _log(f"Successfully fetched stock info for {len(stock_info_map)}/{len(unique_products)} products")

    return html_content_map, stock_info_map
