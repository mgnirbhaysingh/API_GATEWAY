"""
Shopify LLM Processor Module
Handles LLM enrichment of product data using Gemini API.
"""

from typing import Any, Dict, List, Tuple
from collections import OrderedDict
import time
import json
import os
import httpx
import asyncio
import base64


def _log(msg: str) -> None:
    """Lightweight debug logger for terminal visibility"""
    try:
        print(f"[shopify_llm] {time.strftime('%H:%M:%S')} {msg}", flush=True)
    except Exception:
        pass


# Vertex AI API configuration
GEMINI_API_KEY = "AQ.Ab8RN6Lqym30al4Wzr3nt74kMS_0jULMaTKv6PcR75U6WQcnyQ"
# Available Vertex AI models:
# - "gemini-2.5-flash-lite" (fastest, most cost-effective)
# - "gemini-2.0-flash" (balanced)
# - "gemini-1.5-flash" (stable)
# - "gemini-1.5-pro" (most capable)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
# Vertex AI endpoint structure - using streamGenerateContent with API key
GEMINI_API_URL = (
    f"https://aiplatform.googleapis.com/v1/publishers/google/models/"
    f"{GEMINI_MODEL}:streamGenerateContent?key={GEMINI_API_KEY}"
)

# Structured columns for output
NEW_COLUMNS = [
    'Base Color', 'Fabric', 'Fit Type', 'Sleeve Length', 'Target gender',
    'Image Model Size-Fit Details', 'Care and Wash Instructions', 'Collection Type',
    'Production Type', 'Clothing features', 'Neckline', 'Top Length',
    'Return Policy', 'Tags', 'Shipping Policy', 'Product Category',
    'llm_response', 'category_llm_response', 'Option1 Value'
]


def build_attributes_prompt(product_title: str, raw_content: str) -> str:
    """Build prompt for extracting product attributes"""
    # Increase limit to 5000 chars for better context from HTML pages
    content_text = str(raw_content)[:10000]
    title_text = str(product_title).strip()

    # Debug logging
    _log(f"Building prompt for product: {title_text[:50]}...")
    _log(f"Raw content length: {len(raw_content)} chars, using first {len(content_text)} chars")
    if len(content_text) < 100:
        _log(f"WARNING: Very short content for LLM: '{content_text}'")
    elif len(content_text) < 1000:
        _log(f"WARNING: Short content ({len(content_text)} chars). Preview: {content_text[:300]}...")

    return (
        "You are analyzing product information from an e-commerce website. The content below contains product descriptions, specifications, and details.\n\n"
        "TASK: Extract ALL the specified attributes from the product information.\n\n"
        "IMPORTANT RULES:\n"
        "1. Search carefully through ALL the content - information may appear anywhere\n"
        "2. For color: Check the PRODUCT TITLE first, then look for color mentions in the content\n"
        "3. For fabric/material: Look for keywords like 'cotton', 'polyester', 'silk', 'blend', 'satin', etc.\n"
        "4. For model details: Look for 'model wearing', 'model size', 'model height', measurements\n"
        "5. For care instructions: Look for 'wash', 'care', 'dry clean', 'iron', 'machine wash'\n"
        "6. For shipping/return: Look for 'shipping', 'delivery', 'return policy', 'days'\n"
        "7. If truly not found after thorough search, respond with \"Not specified\"\n"
        "8. For multiple values, separate with commas\n\n"
        "ATTRIBUTES TO EXTRACT:\n"
        "- color: Main color(s) from title or content (e.g., \"Blue\", \"Multicolor\")\n"
        "- fabric: Material/fabric type (e.g., \"Cotton Satin\", \"Polyester blend\")\n"
        "- fit_type: Fit style (e.g., \"Oversized\", \"Regular fit\", \"Slim fit\")\n"
        "- sleeve_length: Sleeve type (e.g., \"Full sleeve\", \"Half sleeve\", \"Sleeveless\")\n"
        "- target_gender: Target gender (e.g., \"Male\", \"Female\", \"Unisex\")\n"
        "- model_size_fit: Model information (e.g., \"Model wearing size M, height 6.1 feet\")\n"
        "- wash_care_instructions: Care instructions (e.g., \"Dry clean only\", \"Machine wash cold\")\n"
        "- collection_type: Collection/season (e.g., \"Autumn/Winter'25\")\n"
        "- production_type: Where made (e.g., \"Made in India\", \"Made to order\")\n"
        "- clothing_features: Key features (e.g., \"Drop pocket, Button-Up\")\n"
        "- neckline: Neck style (e.g., \"Spread Collar\", \"Round neck\")\n"
        "- top_length: Length measurement (e.g., \"24 inches\")\n"
        "- return_policy: Return policy (e.g., \"14 days return\")\n"
        "- tags: Product tags if any\n"
        "- shipping_policy: Shipping details (e.g., \"Ships within 3-6 business days\")\n\n"
        f"=== PRODUCT TITLE ===\n{title_text}\n\n"
        f"=== PRODUCT CONTENT ===\n{content_text}\n\n"
        "Extract all attributes in JSON format with this EXACT structure:\n"
        '{\n'
        '  "EXTRACT": {\n'
        '    "color": "value",\n'
        '    "fabric": "value",\n'
        '    "fit_type": "value",\n'
        '    "sleeve_length": "value",\n'
        '    "target_gender": "value",\n'
        '    "model_size_fit": "value",\n'
        '    "wash_care_instructions": "value",\n'
        '    "collection_type": "value",\n'
        '    "production_type": "value",\n'
        '    "clothing_features": "value",\n'
        '    "neckline": "value",\n'
        '    "top_length": "value",\n'
        '    "return_policy": "value",\n'
        '    "tags": "value",\n'
        '    "shipping_policy": "value"\n'
        '  }\n'
        '}\n\n'
        "Return ONLY the JSON, no other text."
    )


def build_category_prompt(product_title: str) -> str:
    """Build prompt for determining product category"""
    title_text = str(product_title).strip()
    return (
        "Analyze the following product title and determine the EXACT product category. Be precise and use only the standard clothing categories.\n\n"
        "RULES:\n"
        "1. Respond with ONLY ONE category from the list below\n"
        "2. Choose the most specific and accurate category\n"
        "3. If unsure, choose the closest match\n"
        "4. Respond in JSON format with the key \"category\"\n\n"
        "VALID CATEGORIES:\n"
        "- Shirts\n- T-shirts\n- Polos\n- Hoodies\n- Sweatshirts\n- Jackets\n- Hoodie jackets\n- Blouses\n- Bodysuits\n- Overshirts\n- Tank tops\n- Tunics\n- Dresses\n- Vests\n- Cardigans\n- Blazers\n- Tops\n- Kurtas\n- Coats\n- Cargos\n- Chinos\n- Jeans\n- Joggers\n- Trousers\n- Shorts\n- Leggings\n- Jeggings\n- Skirts\n- Pants\n- Outfit set\n- Co-ords\n- Jumpsuits\n- Sarees\n\n"
        f"Product Title: {title_text}\n\n"
        "Extract the product category in JSON format:"
    )


def parse_json_from_text(response_text: str) -> Dict[str, Any]:
    """Robustly parse JSON from LLM text responses, handling wrappers and double-encoded JSON."""
    def _attempt_load(text: str):
        try:
            return json.loads(text)
        except Exception:
            return None

    # 1) direct load
    obj = _attempt_load(response_text)
    # 1a) if string containing JSON, try to decode again
    if isinstance(obj, str):
        inner = _attempt_load(obj)
        if isinstance(inner, dict):
            return inner
    if isinstance(obj, dict):
        # Some providers wrap under 'response' as a string JSON
        if 'response' in obj and isinstance(obj['response'], str):
            inner = _attempt_load(obj['response'])
            if isinstance(inner, dict):
                return inner
        return obj

    # 2) strip code fences and try again
    import re as _re
    cleaned = _re.sub(r"```[a-zA-Z]*", "", response_text)
    cleaned = cleaned.replace("```", "").strip()
    obj = _attempt_load(cleaned)
    if isinstance(obj, str):
        inner = _attempt_load(obj)
        if isinstance(inner, dict):
            return inner
    if isinstance(obj, dict):
        if 'response' in obj and isinstance(obj['response'], str):
            inner = _attempt_load(obj['response'])
            if isinstance(inner, dict):
                return inner
        return obj

    # 3) regex first JSON object
    m = _re.search(r"\{[\s\S]*\}", response_text)
    if m:
        obj = _attempt_load(m.group())
        if isinstance(obj, str):
            inner = _attempt_load(obj)
            if isinstance(inner, dict):
                return inner
        if isinstance(obj, dict):
            return obj
    return {}


def map_attributes_to_columns(parsed_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Map parsed LLM response to structured columns"""
    result: Dict[str, Any] = {}
    extract_obj = parsed_obj.get('EXTRACT', {}) if isinstance(parsed_obj, dict) else {}
    if not isinstance(extract_obj, dict):
        extract_obj = {}

    # normalize keys for robustness
    normalized = {str(k).strip().lower(): v for k, v in extract_obj.items()}

    def pick(*keys: str, default: str = '') -> str:
        for k in keys:
            if k in normalized and normalized[k] not in (None, ''):
                val = str(normalized[k]).strip()
                # Filter out unwanted values - leave blank if not specified/unclassified
                if val.lower() in ['not specified', 'unclassified', 'n/a', 'na', 'none']:
                    continue
                return val
        return default

    result['Base Color'] = pick('color')
    result['Fabric'] = pick('fabric')
    result['Fit Type'] = pick('fit_type', 'fit')
    result['Sleeve Length'] = pick('sleeve_length', 'sleeves')
    result['Target gender'] = pick('target_gender', 'gender')
    result['Image Model Size-Fit Details'] = pick('model_size_fit', 'model', 'model_fit')
    result['Care and Wash Instructions'] = pick('wash_care_instructions', 'wash_care', 'care_instructions')
    result['Collection Type'] = pick('collection_type', 'collection')
    result['Production Type'] = pick('production_type', 'production')
    result['Clothing features'] = pick('clothing_features', 'features')
    result['Neckline'] = pick('neckline')
    result['Top Length'] = pick('top_length', 'length')
    result['Return Policy'] = pick('return_policy')
    result['Tags'] = pick('tags')
    result['Shipping Policy'] = pick('shipping_policy', 'shipping')
    result['Option1 Value'] = result['Base Color']
    return result


async def _post_json(client: httpx.AsyncClient, prompt: str, max_tokens: int,
                     semaphore: asyncio.Semaphore, image_url: str = None) -> Tuple[int, str]:
    """Post request to Gemini API with optional image"""
    async with semaphore:
        # Gemini API payload format (text-only or with image)
        parts = []

        if image_url:
            # Add image part for vision analysis
            parts.append({"text": prompt})
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_url  # Will be base64 encoded data
                }
            })
        else:
            # Text-only
            parts.append({"text": prompt})

        payload = {
            "contents": [{
                "role": "user",
                "parts": parts
            }],
            "generationConfig": {
                "temperature": 0.1,
                "topK": 32,
                "topP": 1,
                "maxOutputTokens": max_tokens,
            }
        }

        headers = {
            "Content-Type": "application/json"
        }

        resp = await client.post(
            GEMINI_API_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        # Extract text from Vertex AI streaming response (JSON array format)
        if resp.status_code == 200:
            try:
                response_text = resp.text
                full_text = []

                # Parse as JSON array: [{...}, {...}, ...]
                try:
                    chunks = json.loads(response_text)
                    if isinstance(chunks, list):
                        # Array of streaming chunks
                        for chunk in chunks:
                            if isinstance(chunk, dict) and 'candidates' in chunk:
                                candidates = chunk.get('candidates', [])
                                if len(candidates) > 0:
                                    content = candidates[0].get('content', {})
                                    if 'parts' in content and len(content['parts']) > 0:
                                        text_part = content['parts'][0].get('text', '')
                                        if text_part:
                                            full_text.append(text_part)
                    elif isinstance(chunks, dict):
                        # Single object response
                        if 'candidates' in chunks:
                            candidates = chunks.get('candidates', [])
                            if len(candidates) > 0:
                                content = candidates[0].get('content', {})
                                if 'parts' in content and len(content['parts']) > 0:
                                    text_part = content['parts'][0].get('text', '')
                                    if text_part:
                                        full_text.append(text_part)
                except json.JSONDecodeError:
                    _log(f"Failed to parse response as JSON: {response_text[:200]}")

                if full_text:
                    return resp.status_code, ''.join(full_text)
            except Exception as e:
                _log(f"Error parsing streaming response: {str(e)[:100]}")
        return resp.status_code, resp.text


def _key_for_row(r: OrderedDict) -> str:
    """Generate unique key for row based on product handle or title/content"""
    handle = str(r.get('Product Handle', '') or '').strip()
    if handle:
        return handle
    title_value = str(r.get('Title', '') or '').strip()
    raw_value = str(r.get('raw_content', '') or '').strip()
    return f"{title_value}::{raw_value[:64]}"


async def enrich_product_data_with_llm(all_product_rows: List[OrderedDict],
                                       detect_colors_from_images: bool = True) -> List[OrderedDict]:
    """
    Enrich product data using LLM.

    Args:
        all_product_rows: List of product rows to enrich
        detect_colors_from_images: Whether to detect colors from images for variants without color

    Returns:
        Enriched product rows
    """
    _log("Starting LLM enrichment")

    # Deduplicate by product handle
    enrichment_by_handle: Dict[str, Dict[str, Any]] = {}
    unique_items: Dict[str, Tuple[str, str]] = {}

    for row in all_product_rows:
        key = _key_for_row(row)
        if key in unique_items:
            continue
        unique_items[key] = (
            str(row.get('Title', '') or '').strip(),
            str(row.get('raw_content', '') or '').strip()
        )

    semaphore = asyncio.Semaphore(50)

    async def _enrich_one(key: str, title_value: str, raw_value: str) -> Tuple[str, Dict[str, Any]]:
        """Enrich one product with attributes and category"""
        if not title_value and not raw_value:
            result = {c: '' for c in NEW_COLUMNS}
            result['llm_response'] = ''
            result['Product Category'] = ''
            result['category_llm_response'] = ''
            return key, result

        attributes_prompt = build_attributes_prompt(title_value, raw_value)
        category_prompt = build_category_prompt(title_value)

        async with httpx.AsyncClient() as client:
            # Attributes
            try:
                status_a, text_a = await _post_json(client, attributes_prompt, 300, semaphore)
                if status_a >= 400:
                    mapped_attrs = {c: '' for c in NEW_COLUMNS}
                    mapped_attrs['llm_response'] = f"ERROR {status_a}: {text_a}"[:5000]
                    _log(f"LLM attributes error status={status_a}, response: {text_a[:200]}")
                else:
                    try:
                        direct = json.loads(text_a)
                        if isinstance(direct, dict) and 'response' in direct:
                            resp_payload_a = str(direct['response'])
                        else:
                            resp_payload_a = text_a
                    except Exception:
                        resp_payload_a = text_a
                    parsed = parse_json_from_text(resp_payload_a)
                    mapped_attrs = map_attributes_to_columns(parsed)
                    mapped_attrs['llm_response'] = resp_payload_a[:5000]
                    _log("LLM attributes success")
            except Exception as e:
                mapped_attrs = {c: '' for c in NEW_COLUMNS}
                mapped_attrs['llm_response'] = f"EXCEPTION: {str(e)}"[:5000]
                _log(f"LLM attributes exception err={str(e)[:200]}")

            # Category
            product_category = ''
            category_llm_text = ''
            try:
                status_c, text_c = await _post_json(client, category_prompt, 100, semaphore)
                if status_c < 400:
                    parsed_c = parse_json_from_text(text_c)
                    if isinstance(parsed_c, dict):
                        cat_value = str(parsed_c.get('category', ''))
                        if cat_value.lower() not in ['unclassified', 'not specified', 'n/a', 'na', 'none']:
                            product_category = cat_value
                    else:
                        valid_categories = [
                            'Shirts', 'T-shirts', 'Polos', 'Hoodies', 'Sweatshirts', 'Jackets',
                            'Hoodie jackets', 'Blouses', 'Bodysuits', 'Overshirts', 'Tank tops',
                            'Tunics', 'Dresses', 'Vests', 'Cardigans', 'Blazers', 'Tops',
                            'Kurtas', 'Coats', 'Cargos', 'Chinos', 'Jeans', 'Joggers',
                            'Trousers', 'Shorts', 'Leggings', 'Jeggings', 'Skirts', 'Pants',
                            'Outfit set', 'Co-ords', 'Jumpsuits', 'Sarees'
                        ]
                        found = ''
                        for cat in valid_categories:
                            if cat.lower() in text_c.lower():
                                found = cat
                                break
                        product_category = found
                    category_llm_text = text_c[:5000]
                    _log("LLM category success")
                else:
                    category_llm_text = f"ERROR {status_c}: {text_c}"[:5000]
                    _log(f"LLM category error status={status_c}, response: {text_c[:200]}")
            except Exception:
                category_llm_text = ''
                _log("LLM category exception")

            mapped_attrs['Product Category'] = product_category
            mapped_attrs['category_llm_response'] = category_llm_text
            return key, mapped_attrs

    # Run all enrichments concurrently
    tasks = [
        _enrich_one(key, title, raw)
        for key, (title, raw) in unique_items.items()
    ]
    results = await asyncio.gather(*tasks)
    for key, mapped in results:
        enrichment_by_handle[key] = mapped

    # Extract global store policies from first successful product response
    # These fields are typically the same across all products in a store
    global_production_type = ''
    global_shipping_policy = ''
    global_return_policy = ''

    _log("Extracting global store policies (Production Type, Shipping Policy, Return Policy)...")
    for key, mapped in enrichment_by_handle.items():
        # Try to get Production Type
        if not global_production_type:
            prod_type = mapped.get('Production Type', '').strip()
            if prod_type and prod_type.lower() not in ['not specified', 'unclassified', 'n/a', 'na', 'none', '']:
                global_production_type = prod_type
                _log(f"Found global Production Type: '{global_production_type}'")

        # Try to get Shipping Policy (priority)
        if not global_shipping_policy:
            ship_policy = mapped.get('Shipping Policy', '').strip()
            if ship_policy and ship_policy.lower() not in ['not specified', 'unclassified', 'n/a', 'na', 'none', '']:
                global_shipping_policy = ship_policy
                _log(f"Found global Shipping Policy: '{global_shipping_policy}'")

        # Try to get Return Policy (priority)
        if not global_return_policy:
            ret_policy = mapped.get('Return Policy', '').strip()
            if ret_policy and ret_policy.lower() not in ['not specified', 'unclassified', 'n/a', 'na', 'none', '']:
                global_return_policy = ret_policy
                _log(f"Found global Return Policy: '{global_return_policy}'")

        # Stop searching once we have shipping and return policies (Production Type can be empty)
        if global_shipping_policy and global_return_policy:
            _log("All priority global policies found, stopping search")
            break

    # Apply global policies to all enrichment entries
    if global_production_type or global_shipping_policy or global_return_policy:
        for key in enrichment_by_handle:
            if global_production_type:
                enrichment_by_handle[key]['Production Type'] = global_production_type
            if global_shipping_policy:
                enrichment_by_handle[key]['Shipping Policy'] = global_shipping_policy
            if global_return_policy:
                enrichment_by_handle[key]['Return Policy'] = global_return_policy
        _log(f"Applied global policies to all {len(enrichment_by_handle)} products")

    # Helper function to get color from image
    async def _get_color_from_image(client: httpx.AsyncClient, image_url: str,
                                    semaphore: asyncio.Semaphore) -> str:
        """Use Gemini Vision to detect color from product image."""
        if not image_url:
            return ''

        try:
            # Download image and convert to base64
            img_resp = await client.get(image_url, timeout=30)
            if img_resp.status_code != 200:
                return ''

            image_data = base64.b64encode(img_resp.content).decode('utf-8')

            color_prompt = (
                "Analyze this product image and identify the primary color of the clothing item. "
                "Respond with ONLY the color name in JSON format: {\"color\": \"color_name\"}\n"
                "Examples: {\"color\": \"Blue\"}, {\"color\": \"Red\"}, {\"color\": \"Black\"}"
            )

            status, text = await _post_json(client, color_prompt, 50, semaphore, image_data)
            if status < 400:
                parsed = parse_json_from_text(text)
                if isinstance(parsed, dict) and 'color' in parsed:
                    color = str(parsed['color']).strip()
                    if color.lower() not in ['not specified', 'unclassified', 'n/a', 'na', 'none']:
                        return color
        except Exception as e:
            import traceback
            _log(f"Error detecting color from image {image_url}: {str(e)}")
            _log(f"Traceback: {traceback.format_exc()}")

        return ''

    # Apply enrichment to every row
    products_needing_color = {}  # Map product_handle -> first row with image
    for row in all_product_rows:
        key = _key_for_row(row)
        mapped = enrichment_by_handle.get(key, {c: '' for c in NEW_COLUMNS})

        # Preserve values that already exist from Shopify fetcher
        existing_option1_value = row.get('Option1 Value', '')
        existing_target_gender = row.get('Target gender', '')
        existing_fit_type = row.get('Fit Type', '')

        for col in NEW_COLUMNS:
            # Don't overwrite these columns if they already exist from Shopify
            if col == 'Option1 Value' and existing_option1_value:
                continue
            if col == 'Target gender' and existing_target_gender:
                continue
            if col == 'Fit Type' and existing_fit_type:
                continue
            row[col] = mapped.get(col, row.get(col, ''))

        # Track PRODUCTS (not variants) that need color detection from image
        # One color detection per product, not per variant
        if detect_colors_from_images:
            product_handle = row.get('Product Handle', '')
            has_variant_data = (
                row.get('Variant ID', '') != '' and
                row.get('Variant SKU', '') != ''
            )
            if has_variant_data and not row.get('Option1 Value', '') and product_handle:
                image_src = row.get('Image Src', '')
                if image_src and product_handle not in products_needing_color:
                    # Store first variant of each product that needs color detection
                    products_needing_color[product_handle] = image_src

    # Detect colors from images - ONCE PER PRODUCT, not per variant
    if detect_colors_from_images and products_needing_color:
        _log(f"Detecting colors from images for {len(products_needing_color)} products (not per-variant)")

        # Configure httpx with longer timeouts for image uploads
        timeout_config = httpx.Timeout(
            connect=10.0,
            read=60.0,
            write=120.0,
            pool=10.0
        )

        # Detect colors for unique products
        product_colors = {}  # Map product_handle -> detected color
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            color_tasks = [
                _get_color_from_image(client, image_src, semaphore)
                for image_src in products_needing_color.values()
            ]
            detected_colors = await asyncio.gather(*color_tasks, return_exceptions=True)

            for (product_handle, image_src), color in zip(products_needing_color.items(), detected_colors):
                if isinstance(color, Exception):
                    _log(f"Failed to detect color for product '{product_handle}': {color}")
                elif color:
                    product_colors[product_handle] = color
                    _log(f"Detected color '{color}' for product '{product_handle}'")

        # Apply detected colors to ALL variants of each product
        for row in all_product_rows:
            product_handle = row.get('Product Handle', '')
            if product_handle in product_colors and not row.get('Option1 Value', ''):
                color = product_colors[product_handle]
                row['Option1 Value'] = color
                row['Base Color'] = color
                _log(f"Applied color '{color}' to variant SKU {row.get('Variant SKU', 'unknown')}")

    # Update Variant SKUs with final color values
    # SKU format: <product_handle>_<lowercase_color>_<lowercase_size>
    for row in all_product_rows:
        product_handle = row.get('Product Handle', '')
        size_value = row.get('Option2 Value1', '') or row.get('Option2 Value2', '')
        option1_value = row.get('Option1 Value', '')

        if product_handle:
            sku_parts = [product_handle]
            if option1_value:
                sku_parts.append(option1_value.lower().replace(' ', '_'))
            if size_value:
                sku_parts.append(size_value.lower().replace(' ', '_'))
            row['Variant SKU'] = '_'.join(sku_parts)

    _log(f"LLM enrichment completed for {len(all_product_rows)} rows")
    return all_product_rows
