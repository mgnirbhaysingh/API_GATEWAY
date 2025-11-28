"""
Image Color Matcher Module
Matches product images to color variants using Vertex AI Vision LLM.
Processes Excel files with unassigned images and assigns them to correct color variants.
"""

import pandas as pd
import requests
import base64
import json
import time
import os
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def _log(msg: str) -> None:
    """Lightweight debug logger for terminal visibility"""
    try:
        print(f"[image_matcher] {time.strftime('%H:%M:%S')} {msg}", flush=True)
    except Exception:
        pass


# Vertex AI API configuration (same as shopify_llm_processor.py)
GEMINI_API_KEY = "AQ.Ab8RN6Lqym30al4Wzr3nt74kMS_0jULMaTKv6PcR75U6WQcnyQ"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_API_URL = (
    f"https://aiplatform.googleapis.com/v1/publishers/google/models/"
    f"{GEMINI_MODEL}:streamGenerateContent?key={GEMINI_API_KEY}"
)

# Standard sizes for all variants
STANDARD_SIZES = ['S', 'M', 'L', 'XL']


def fetch_image_as_base64(image_url: str) -> Optional[str]:
    """
    Fetch an image from URL and convert to base64.

    Args:
        image_url: URL of the image to fetch

    Returns:
        Base64 encoded string of the image, or None if failed
    """
    try:
        _log(f"Fetching image: {image_url[:60]}...")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        # Encode to base64
        image_base64 = base64.b64encode(response.content).decode('utf-8')
        _log(f"Image fetched and encoded: {len(image_base64)} chars")
        return image_base64

    except Exception as e:
        _log(f"ERROR fetching image: {str(e)[:100]}")
        return None


def detect_color_from_image(image_url: str, available_colors: List[str]) -> Optional[str]:
    """
    Use Vertex AI Vision to detect the dominant clothing color in an image.

    Args:
        image_url: URL of the product image
        available_colors: List of valid color options to choose from

    Returns:
        The detected color matching one of available_colors, or None if failed
    """
    # Fetch image as base64
    image_base64 = fetch_image_as_base64(image_url)
    if not image_base64:
        return None

    # Build the prompt
    colors_str = ", ".join(available_colors)
    prompt = f"""Analyze this product/clothing image and identify the dominant color of the clothing item.

IMPORTANT: You MUST respond with EXACTLY one of these colors: {colors_str}

Look at the main clothing item in the image and determine which of the available colors best matches it.
Consider the primary/dominant color, not background or accessories.

Rules for color matching:
- BLACK: Dark black or very dark grey clothing
- WHITE: White or off-white/cream clothing
- YELLOW: Yellow, mustard, or golden clothing
- PINK: Pink, rose, coral, or salmon clothing
- BROWN: Brown, tan, beige, khaki, or camel clothing

Respond with ONLY the color name from the list above, nothing else."""

    # Build request payload with image (must include role)
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64
                    }
                },
                {
                    "text": prompt
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 50
        }
    }

    try:
        _log(f"Sending image to Vertex AI for color detection...")

        response = requests.post(
            GEMINI_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        if response.status_code != 200:
            _log(f"ERROR: API returned status {response.status_code}: {response.text[:200]}")
            return None

        # Parse streaming JSON response
        response_text = response.text
        full_text = []

        chunks = json.loads(response_text)
        if isinstance(chunks, list):
            for chunk in chunks:
                if isinstance(chunk, dict) and 'candidates' in chunk:
                    candidates = chunk.get('candidates', [])
                    if len(candidates) > 0:
                        content = candidates[0].get('content', {})
                        if 'parts' in content and len(content['parts']) > 0:
                            text_part = content['parts'][0].get('text', '')
                            if text_part:
                                full_text.append(text_part)

        detected_text = ''.join(full_text).strip().upper()
        _log(f"LLM response: '{detected_text}'")

        # Match to available colors
        for color in available_colors:
            if color.upper() == detected_text:
                _log(f"Exact match: {color}")
                return color
            if color.upper() in detected_text:
                _log(f"Partial match: {color}")
                return color

        _log(f"WARNING: Could not match '{detected_text}' to available colors: {available_colors}")
        return None

    except Exception as e:
        _log(f"ERROR in LLM color detection: {str(e)[:200]}")
        return None


def extract_base_handle(product_handle: str) -> Tuple[str, str]:
    """
    Extract base product handle and color from full handle.

    Args:
        product_handle: Full handle like 'crepe-shirt-crinkle-pants-set BLACK'

    Returns:
        Tuple of (base_handle, color)
    """
    if pd.isna(product_handle):
        return None, None

    parts = str(product_handle).rsplit(' ', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return product_handle, None


def process_excel_with_color_matching(
    input_file: str,
    output_file: str = None
) -> pd.DataFrame:
    """
    Process Excel file to match images to correct color variants using LLM vision.
    Creates exactly 4 rows (S, M, L, XL) per color variant with images.
    Additional images beyond 4 get extra rows with no size.

    Args:
        input_file: Path to input Excel file
        output_file: Path to output Excel file (optional)

    Returns:
        Processed DataFrame
    """
    _log(f"Reading input file: {input_file}")
    df = pd.read_excel(input_file)
    _log(f"Loaded {len(df)} rows")

    # Get all unique colors from existing data
    existing_colors = df['Option1 Value'].dropna().unique().tolist()
    _log(f"Available colors: {existing_colors}")

    # Get base handle from first valid row
    base_handle = None
    for handle in df['Product Handle'].dropna().unique():
        bh, _ = extract_base_handle(handle)
        if bh:
            base_handle = bh
            break
    _log(f"Base product handle: {base_handle}")

    # Collect ALL unique images from the dataset
    all_images = df['Image Src'].dropna().unique().tolist()
    _log(f"Total unique images: {len(all_images)}")

    # Detect color for EVERY image
    _log("\n=== DETECTING COLORS FOR ALL IMAGES ===")
    image_color_map: Dict[str, str] = {}

    for idx, image_url in enumerate(all_images, 1):
        _log(f"\n[{idx}/{len(all_images)}] Analyzing image...")

        detected_color = detect_color_from_image(image_url, existing_colors)

        if detected_color:
            image_color_map[image_url] = detected_color
            _log(f"Image {idx}: Detected color = {detected_color}")
        else:
            _log(f"Image {idx}: Could not detect color")

        # Small delay between API calls
        if idx < len(all_images):
            time.sleep(0.5)

    _log(f"\nColor detection complete. Matched {len(image_color_map)}/{len(all_images)} images")

    # Group images by detected color
    images_by_color: Dict[str, List[str]] = defaultdict(list)
    for image_url, color in image_color_map.items():
        images_by_color[color].append(image_url)

    _log(f"\nImages grouped by color:")
    for color, images in images_by_color.items():
        _log(f"  {color}: {len(images)} images")

    # Get template row for product data (use first non-null row)
    template_row = df.dropna(subset=['Title']).iloc[0].to_dict()

    # Build new dataset with proper structure
    new_rows = []

    for color in existing_colors:
        color_images = images_by_color.get(color, [])
        _log(f"\nProcessing {color}: {len(color_images)} images")

        if len(color_images) == 0:
            _log(f"WARNING: No images detected for {color}")
            continue

        # Create 4 rows for standard sizes (S, M, L, XL)
        for size_idx, size in enumerate(STANDARD_SIZES):
            row = template_row.copy()

            # Set product handle with color
            row['Product Handle'] = f"{base_handle} {color}"

            # Set color option
            row['Option1 Name'] = 'Color'
            row['Option1 Value'] = color

            # Set size option
            row['Option2 Name'] = 'Size'
            row['Option2 Value1'] = size
            row['Option2 Value2'] = None

            # Set image (use corresponding image if available, else use first)
            if size_idx < len(color_images):
                row['Image Src'] = color_images[size_idx]
            else:
                row['Image Src'] = color_images[0]  # Repeat first image

            # Set image position (1-based, per color variant)
            row['Image Position'] = size_idx + 1

            # Generate SKU
            row['Variant SKU'] = f"{base_handle}_{color.lower()}_{size.lower()}"

            # Set inventory
            row['Variant Inventory Qty'] = 50

            new_rows.append(row)
            _log(f"  Created row: {color} / {size} / Position {size_idx + 1}")

        # If more than 4 images, add extra image-only rows
        if len(color_images) > len(STANDARD_SIZES):
            for img_idx in range(len(STANDARD_SIZES), len(color_images)):
                row = template_row.copy()

                # Set product handle with color
                row['Product Handle'] = f"{base_handle} {color}"

                # Set color option
                row['Option1 Name'] = 'Color'
                row['Option1 Value'] = color

                # No size for extra image rows
                row['Option2 Name'] = 'Size'
                row['Option2 Value1'] = None
                row['Option2 Value2'] = None

                # Set image
                row['Image Src'] = color_images[img_idx]

                # Set image position (continues from where sizes ended)
                row['Image Position'] = img_idx + 1

                # No SKU/inventory for image-only rows
                row['Variant SKU'] = None
                row['Variant Inventory Qty'] = None
                row['Variant ID'] = None
                row['Variant URL'] = None

                new_rows.append(row)
                _log(f"  Created extra image row: {color} / Position {img_idx + 1}")

    # Create final DataFrame
    df_final = pd.DataFrame(new_rows)

    # Sort by Product Handle and Image Position
    df_final = df_final.sort_values(
        by=['Product Handle', 'Image Position'],
        na_position='last'
    ).reset_index(drop=True)

    _log(f"\nFinal dataset: {len(df_final)} rows")

    # Save output
    if output_file is None:
        output_file = input_file.replace('.xlsx', '_color_matched.xlsx')

    df_final.to_excel(output_file, index=False)
    _log(f"Saved output to: {output_file}")

    # Print summary
    _log("\n=== SUMMARY ===")
    for color in existing_colors:
        color_count = len(df_final[df_final['Option1 Value'] == color])
        _log(f"  {color}: {color_count} rows")

    return df_final


def main():
    """Main entry point"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python image_color_matcher.py <input_file.xlsx> [output_file.xlsx]")
        print("\nExample:")
        print("  python image_color_matcher.py Image_position_fix.xlsx")
        print("  python image_color_matcher.py Image_position_fix.xlsx output.xlsx")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    process_excel_with_color_matching(input_file, output_file)


if __name__ == "__main__":
    main()
