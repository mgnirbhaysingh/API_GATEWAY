"""
Shopify Data Fetcher Module
Handles fetching and extracting product data from Shopify JSON API.
"""

from pydantic import BaseModel, HttpUrl
from typing import Any, Dict, List, Tuple
from app.configs.config import HEADERS, COOKIES, extract_brand_name_from_url
from html import unescape
import re
import requests
from collections import OrderedDict
import time


def _log(msg: str) -> None:
    """Lightweight debug logger for terminal visibility"""
    try:
        print(f"[shopify_fetcher] {time.strftime('%H:%M:%S')} {msg}", flush=True)
    except Exception:
        pass


class URLRequest(BaseModel):
    url: HttpUrl


def convert_to_json_url(product_url: str) -> str:
    """Convert product URL to JSON API URL"""
    return product_url.rstrip('/') + '.json'


def _clean_html_content(html_content: str) -> str:
    """
    Clean HTML content from body_html.
    Returns clean text for Product Detail column.
    """
    if not html_content:
        return ""
    text = unescape(html_content)
    clean_text = re.sub(r"<[^>]+>", "", text)
    clean_text = " ".join(clean_text.split())
    return clean_text.strip()


def _is_gender_value(value: str) -> bool:
    """
    Determine if a value is a gender attribute.
    Returns True if it's Male/Female/Unisex.
    """
    if not value:
        return False

    value_str = str(value).strip().lower()
    gender_values = ["male", "female", "unisex", "men", "women", "boys", "girls", "kids", "unisex adult"]

    return value_str in gender_values


def _is_fit_value(value: str) -> bool:
    """
    Determine if a value is a fit type attribute.
    Returns True if it looks like a fit type (e.g., Oversized-Fit, Regular-Fit).
    """
    if not value:
        return False

    value_str = str(value).strip().lower()

    # Common fit patterns
    fit_patterns = ["oversized-fit", "regular-fit", "slim-fit", "loose-fit", "relaxed-fit",
                    "tight-fit", "fitted", "oversized", "regular", "slim", "loose", "relaxed"]

    # Check exact match
    if value_str in fit_patterns:
        return True

    # Check if it contains "fit" keyword
    if "fit" in value_str:
        return True

    return False


def _is_size_value(value: str) -> bool:
    """
    Determine if a value looks like a size rather than a color.
    Returns True if it's a size, False if it's likely a color.
    """
    if not value:
        return False

    value_str = str(value).strip().lower()

    # Common size patterns (expanded to include XXS and hyphenated sizes)
    valid_sizes = ["xxs", "xs", "s", "m", "l", "xl", "2xl", "3xl", "4xl", "xxl", "xxxl", "plus",
                   "xl/s", "s/m", "m/l", "l/xl", "s-m", "m-l", "l-xl", "xs-s", "xl-2xl",
                   "one size", "onesize", "free size", "freesize"]

    # Check exact match with common sizes
    if value_str in valid_sizes:
        return True

    # Check if it's purely numeric (waist sizes like 28, 30, 32)
    if re.match(r"^\d+$", value_str):
        return True

    # Check if it's a size with number (like "2XL", "3XL", "SIZE 28", "S/38", "M/40", "26/S", "28/M")
    if re.search(r"\d+\s*xl|xl\s*\d+|size\s*\d+|^[a-z]{1,3}/\d+|^\d+/[a-z]{1,3}", value_str):
        return True

    # If it's very short (1-2 chars) and alphabetic, likely a size (S, M, L, XL)
    if len(value_str) <= 2 and value_str.isalpha():
        return True

    # Otherwise, it's probably a color or other attribute
    return False


def _categorize_size_option(size_value: Any) -> Tuple[str, str]:
    """
    Categorize size into Option2 Value1 (standard sizes) or Option2 Value2 (numeric/other sizes).
    Extracts size letter from patterns like "S/38" -> "S" (Option2 Value1)
    Extracts number from patterns like "26/S" -> "26" (Option2 Value2)
    Returns (option2_value1, option2_value2)
    """
    if not size_value:
        return "", ""
    size_str = str(size_value).strip()

    # Valid sizes for Option2 Value1 (including xl variations and combined sizes)
    valid_sizes = ["xxs", "xs", "s", "m", "l", "xl", "2xl", "3xl", "4xl", "xxl", "xxxl", "plus",
                   "xl/s", "s/m", "m/l", "l/xl", "s-m", "m-l", "l-xl", "xs-s", "xl-2xl",
                   "one size", "onesize", "free size", "freesize"]

    # Check if it's a valid size (including those with numbers like 2xl, 3xl)
    if size_str.lower() in valid_sizes:
        return size_str, ""

    # Check for pattern like "S/38", "M/40", "L/42" - extract the size letter for Option2 Value1
    size_letter_first_match = re.match(r"^([a-zA-Z]{1,3})/(\d+)$", size_str)
    if size_letter_first_match:
        size_letter = size_letter_first_match.group(1)
        # Return the size letter (like "S", "M", "L") in Option2 Value1
        return size_letter, ""

    # Check for pattern like "26/S", "28/M", "30/L" - extract the number for Option2 Value2
    number_first_match = re.match(r"^(\d+)/([a-zA-Z]{1,3})$", size_str)
    if number_first_match:
        number = number_first_match.group(1)
        # Return the number (like "26", "28", "30") in Option2 Value2
        return "", number

    # If it contains only digits (like 28, 30, 32 for waist sizes), put in Option2 Value2
    if re.search(r"^\d+$", size_str):
        return "", size_str

    # Default to Option2 Value2 for other cases
    return "", size_str


def _create_product_row(
    product_handle: str,
    title: str,
    brand_name: str,
    product_detail: str,
    product_category: str,
    tags: str,
    published: str,
    variant: Dict | None,
    image: Dict | None,
    raw_content: str,
    product_url: str
) -> Dict[str, Any]:
    """
    Create a product row with all the required columns.
    Handles smart detection of color, size, gender, and fit type from option1/option2/option3.
    Intelligently categorizes variant options into appropriate columns:
    - Gender values (Male/Female/Unisex) -> Target gender column
    - Fit values (Oversized-Fit, Regular-Fit, etc.) -> Fit Type column
    - Size values (XXS, XS, S, M, L, XL, etc.) -> Option2 Value1/Value2
    - Color values -> Option1 Value
    """

    # Define column order to match expected format
    column_order = [
        'Product Handle', 'Title', 'Brand Name', 'Product Detail', 'Product Category',
        'Tags', 'Published', 'Option1 Name', 'Option1 Value', 'Option2 Name',
        'Option2 Value1', 'Option2 Value2', 'Variant SKU', 'Variant Grams', 'Variant Inventory Qty',
        'Variant Price', 'Variant Compare At Price', 'Variant Barcode', 'Image Src',
        'Image Position', 'Video  Src', 'Image Model Size-Fit Details', 'Fit Type',
        'Clothing features', 'Base Color', 'Fabric', 'Neckline', 'Sleeve Length',
        'Target gender', 'Top Length', 'Care and Wash Instructions', 'Size Chart',
        'Production Type', 'SEO Title', 'SEO Description', 'Collection Type',
        'Shipping policy code', 'Shipping Policy', 'Return Policy', 'Variant ID',
        'Variant URL', 'raw_content'
    ]

    # Create ordered row with proper column order
    row = OrderedDict()
    for col in column_order:
        row[col] = ''

    # Fill basic product info (only if we have variant data)
    if variant:
        row['Product Handle'] = product_handle
        row['Title'] = title
        row['Brand Name'] = brand_name
        row['Product Detail'] = product_detail
        row['Product Category'] = product_category
        row['Tags'] = tags
        row['Published'] = published
        row['Option1 Name'] = 'Color'
        row['Option2 Name'] = 'Size'
        row['Variant Inventory Qty'] = '50'  # Set to 50 for all variants
        row['raw_content'] = raw_content

    # Update if variant exists
    if variant:
        variant_id = str(variant.get('id', ''))
        variant_price = variant.get('price', '')
        variant_grams = variant.get('grams', '')

        # Get compare_at_price from JSON, use variant_price as fallback if empty or 0
        variant_compare_at_price = variant.get('compare_at_price', '')
        # Convert to string for comparison
        compare_price_str = str(variant_compare_at_price).strip()
        # Check if empty, null, or zero (0, 0.0, 0.00, "0", "0.0", "0.00")
        if (not variant_compare_at_price or
            variant_compare_at_price in [None, 'null', ''] or
            compare_price_str in ['0', '0.0', '0.00'] or
            (isinstance(variant_compare_at_price, (int, float)) and variant_compare_at_price == 0)):
            variant_compare_at_price = variant_price

        # Get option1, option2, and option3 from Shopify variant data
        option1_from_shopify = variant.get('option1', '')
        option2_from_shopify = variant.get('option2', '')
        option3_from_shopify = variant.get('option3', '')

        # Smart detection: Determine which option is color, size, gender, or fit type
        # Different stores have different configurations:
        # - Standard: option1=color, option2=size
        # - Reversed: option1=size, option2=color
        # - Gender-based: option1=gender, option2=fit, option3=size
        # - And various other combinations

        color_value = ''
        size_raw = ''
        gender_value = ''
        fit_type_value = ''

        # Collect all options in a list for processing
        options = [
            ('option1', option1_from_shopify),
            ('option2', option2_from_shopify),
            ('option3', option3_from_shopify)
        ]

        # Categorize each option
        for option_name, option_value in options:
            if not option_value:
                continue

            # Check what type of value this is
            if _is_gender_value(option_value):
                gender_value = option_value
                _log(f"Detected GENDER in {option_name}: '{option_value}'")
            elif _is_fit_value(option_value):
                fit_type_value = option_value
                _log(f"Detected FIT TYPE in {option_name}: '{option_value}'")
            elif _is_size_value(option_value):
                size_raw = option_value
                _log(f"Detected SIZE in {option_name}: '{option_value}'")
            else:
                # If it's not gender, fit, or size, assume it's color
                # Only use it if we haven't found a color yet
                if not color_value:
                    color_value = option_value
                    _log(f"Detected COLOR in {option_name}: '{option_value}'")

        # Use detected color (or leave empty if not found)
        option1_value = color_value

        # Categorize the size
        if size_raw:
            option2_value1, option2_value2 = _categorize_size_option(size_raw)
        else:
            option2_value1, option2_value2 = '', ''

        size_value = option2_value1 or option2_value2

        # SKU format: <product_handle>_<lowercase_color>_<lowercase_size>
        # Example: red-cotton-dress_red_m
        sku_parts = [product_handle]
        if option1_value:
            sku_parts.append(option1_value.lower().replace(' ', '_'))
        if size_value:
            sku_parts.append(size_value.lower().replace(' ', '_'))
        custom_sku = '_'.join(sku_parts)

        row['Option1 Value'] = option1_value
        row['Option2 Value1'] = option2_value1
        row['Option2 Value2'] = option2_value2
        row['Variant Grams'] = variant_grams
        row['Variant Price'] = variant_price
        row['Variant Compare At Price'] = variant_compare_at_price  # From JSON, fallback to price if empty
        row['Variant ID'] = variant_id
        row['Variant URL'] = f"{product_url}?variant={variant_id}" if variant_id else ''
        row['Variant SKU'] = custom_sku

        # Set gender and fit type if detected
        if gender_value:
            row['Target gender'] = gender_value
        if fit_type_value:
            row['Fit Type'] = fit_type_value

    # Update if image exists
    if image:
        row['Image Src'] = image.get('src', '')
        row['Image Position'] = image.get('position', '')

    return row


def extract_product_data_from_json(response_data: Dict[str, Any], url: HttpUrl) -> List[OrderedDict]:
    """
    Extract product data from Shopify JSON response.
    Returns list of product rows (one per variant/image combination).
    """
    if not response_data or 'product' not in response_data:
        return []

    product = response_data['product']

    product_handle = product.get('handle', '')
    title = product.get('title', '')
    brand_name = extract_brand_name_from_url(str(url))
    tags = product.get('tags', '')
    published = "True"
    product_category = product.get('product_type', '')

    body_html = product.get('body_html', '')
    product_detail = _clean_html_content(body_html)
    raw_content = ""  # Will be filled by HTML fetcher later

    variants = product.get('variants', []) or []
    images = product.get('images', []) or []

    rows: List[OrderedDict] = []
    max_rows = max(len(variants), len(images)) if (variants or images) else 1

    for i in range(max_rows):
        variant = variants[i] if i < len(variants) else None
        image = images[i] if i < len(images) else None
        row = _create_product_row(
            product_handle, title, brand_name, product_detail, product_category,
            tags, published, variant, image, raw_content, str(url)
        )
        rows.append(row)

    return rows


def update_raw_content_in_rows(product_rows: List[OrderedDict], html_content_map: Dict[str, str]) -> List[OrderedDict]:
    """
    Update raw_content field in product rows with HTML content.

    Args:
        product_rows: List of product rows from fetch_shopify_data_from_urls
        html_content_map: Dictionary mapping product_handle to HTML text content

    Returns:
        Updated product rows with raw_content filled
    """
    _log(f"Updating raw_content for {len(product_rows)} rows using {len(html_content_map)} HTML content entries")

    # Debug: show sizes of HTML content
    for handle, content in list(html_content_map.items())[:3]:
        _log(f"  HTML content for '{handle}': {len(content)} chars (preview: {content[:100]}...)")

    updated_count = 0
    for row in product_rows:
        product_handle = row.get('Product Handle', '')
        if product_handle and product_handle in html_content_map:
            html_text = html_content_map[product_handle]
            row['raw_content'] = html_text
            _log(f"Set raw_content for '{product_handle}': {len(html_text)} chars")
            updated_count += 1

    _log(f"Updated raw_content for {updated_count}/{len(product_rows)} rows")
    return product_rows


def update_variant_inventory_from_stock(product_rows: List[OrderedDict], stock_info_map: Dict[str, Dict[str, int]]) -> List[OrderedDict]:
    """
    Update Variant Inventory Qty based on stock information from HTML.

    Args:
        product_rows: List of product rows from fetch_shopify_data_from_urls
        stock_info_map: Dictionary mapping product_handle to stock info
                       (stock info maps size -> quantity)

    Returns:
        Updated product rows with accurate inventory quantities
    """
    _log(f"Updating variant inventory for {len(product_rows)} rows using {len(stock_info_map)} stock info entries")

    updated_count = 0
    for row in product_rows:
        product_handle = row.get('Product Handle', '')
        if not product_handle or product_handle not in stock_info_map:
            continue

        stock_info = stock_info_map[product_handle]

        # Get the size from this variant
        # Check both Option2 Value1 and Option2 Value2
        size_from_option1 = row.get('Option2 Value1', '').strip()
        size_from_option2 = row.get('Option2 Value2', '').strip()
        variant_size = size_from_option1 or size_from_option2

        if not variant_size:
            continue

        # Check if we have stock info for this size
        if variant_size in stock_info:
            new_qty = stock_info[variant_size]
            old_qty = row.get('Variant Inventory Qty', '50')
            row['Variant Inventory Qty'] = str(new_qty)
            updated_count += 1
            _log(f"Product '{product_handle}' size '{variant_size}': {old_qty} → {new_qty}")

    _log(f"Updated inventory for {updated_count}/{len(product_rows)} rows")
    return product_rows


def fetch_shopify_data_from_urls(urls: List[str]) -> List[OrderedDict]:
    """
    Fetch product data from multiple Shopify URLs.
    Returns combined list of all product rows.
    """
    all_product_rows = []

    for idx, url in enumerate(urls, start=1):
        try:
            _log(f"[{idx}/{len(urls)}] processing url={url}")
            request_url = convert_to_json_url(url)
            _log(f"GET {request_url}")

            response = requests.get(request_url, headers=HEADERS, cookies=COOKIES, timeout=30)
            response.raise_for_status()
            _log(f"status={response.status_code} content_length={len(response.text or '')}")

            content = response.text.strip()
            if not content:
                _log("empty response body, skipping")
                continue

            if content.startswith('<!DOCTYPE') or content.startswith('<html'):
                _log("received HTML instead of JSON, skipping")
                continue

            if not content.startswith('{'):
                _log("response does not appear to be JSON, skipping")
                continue

            try:
                json_data = response.json()
            except ValueError:
                # Best-effort extraction
                import json as _json
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_data = _json.loads(content[json_start:json_end])
                    _log("parsed JSON via substring extraction")
                else:
                    _log("failed to parse JSON, skipping")
                    continue

            product_rows = extract_product_data_from_json(json_data, url)
            _log(f"extracted rows={len(product_rows)} from url={url}")
            all_product_rows.extend(product_rows)

        except Exception as e:
            _log(f"ERROR processing url={url} err={str(e)[:200]}")
            continue

    return all_product_rows
