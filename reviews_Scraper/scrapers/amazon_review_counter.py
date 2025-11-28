import requests
import csv
import re
from typing import Tuple
import time
from bs4 import BeautifulSoup

import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path to import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Manual cookies - update these when they expire
COOKIES = {
    'session-id': '525-9439529-3198566',
    'i18n-prefs': 'INR',
    'lc-acbin': 'en_IN',
    'ubid-acbin': '521-1884369-2376769',
    'session-token': 'ySZfNtn1rbwgFtJBCKVGaBWaVhP65RPQAspk33eM3Zh/1lHbSMuo06k8QYkn1sOFNdozR8XXdwas42LTPTWOOXlLotOA+rwQdEZ2/n92cPGqQGVNCLE/xV8MFB30NsDazNPjn2kiOorl+DiwtxMo0VzMcq+c3E3YYPqVdxCuem4rxgGEHZNmePZV0TYzUd8XNrn1ca6rN/izrr3VZD1XwVCQZMPS4ALI4iKlnmDqpebxqZRhi6tgvC8+yn+NLLxAR9t26rykIFWvPc59JrcKxjWFuDEE+iZGrhdU9/AMm0oL7SbchCMUgdNOBDQEDdWvY0k2wxDb0PwdL4QEp2ryqOl1/o7uenrtVIg4pIZSEIh7lKCihq+jvlkynE0TzZ8n',
    'x-acbin': '9?ox0ZWvqsurZjdYyy6Z8JLj58EdEHapeDL34zdCESD6gnPR4?8IG2xcfL4FHsXq',
    'at-acbin': 'Atza|gQBROPWIAwEBAuQaOeQ89VsKckFx1CFbGMzMfMa3d0h5ia6BPExkl2eAePLsIyPuFpaNKnVISb2BDR-9SSht_lOOHbY3PSe9hUhVl6x2T-flldS2JrymDI5asQYnzUgjwQmY2Y0AHJYNi02zAM41Mpx2XdgMw1N0wya9hL5RMBgd_0WAWqGBkG7z-tsd1QUL3QRDj8whTD8W0Dci3XK_bu1BWql1SVKKYWWnsSvfOFyx5EsmVSLEicrME9unXToIdlilgWeHskDV4d-NWFFbl7aw6AhQcXCxIWt_f_o6KMF5ZL4NVKd8GJWW21-MFYoRO247WCGG4k2X_P0R4Omdy2FIyakSjyAE',
    'csm-hit': 'tb:s-H78S65S2G25KFCPXQNX4|1762459586681&t:1762459586882&adb:adblk_no',
    'session-id-time': '2082787201l',
}



def extract_asin_from_url(url: str) -> str:
    """Extract ASIN from Amazon product URL."""
    try:
        match = re.search(r'/dp/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        match = re.search(r'/gp/product/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        match = re.search(r'/product-reviews/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        return None

    except Exception as e:
        return None


def extract_review_count_from_html(html: str) -> int:
    """
    Extract the total review count from product reviews page HTML.

    Looks for: <div data-hook="cr-filter-info-review-rating-count">11,936 customer reviews</div>
    """
    print(f"[AMAZON_COUNTER] extract_review_count_from_html: Parsing HTML...")
    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Look for the specific element with review count
        review_count_elem = soup.find('div', {'data-hook': 'cr-filter-info-review-rating-count'})
        print(f"[AMAZON_COUNTER] Found review count element: {review_count_elem is not None}")

        if review_count_elem:
            text = review_count_elem.get_text(strip=True)
            print(f"[AMAZON_COUNTER] Review count text: '{text}'")
            # Extract number from text like "11,936 customer reviews"
            match = re.search(r'([\d,]+)\s+customer review', text)
            if match:
                count_str = match.group(1).replace(',', '')
                print(f"[AMAZON_COUNTER] Extracted count from element: {count_str}")
                return int(count_str)

        # Fallback: Search entire HTML for review count patterns
        print(f"[AMAZON_COUNTER] Using fallback patterns...")
        patterns = [
            r'([\d,]+)\s+global ratings',
            r'([\d,]+)\s+total ratings',
            r'([\d,]+)\s+customer reviews',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                count_str = match.group(1).replace(',', '')
                print(f"[AMAZON_COUNTER] Found via pattern '{pattern}': {count_str}")
                return int(count_str)

        print(f"[AMAZON_COUNTER] No review count found in HTML")
        return 0
    except Exception as e:
        print(f"[AMAZON_COUNTER] Error in extract_review_count_from_html: {e}")
        import traceback
        traceback.print_exc()
        return 0


def get_total_review_count(asin: str) -> Tuple[int, str]:
    """
    Get the total number of reviews for a product.

    Fetches the product reviews page HTML and extracts the count.

    Args:
        asin: Product ASIN

    Returns:
        Tuple of (total_count, status_message)
    """
    print(f"\n[AMAZON_COUNTER] ========== get_total_review_count START ==========")
    print(f"[AMAZON_COUNTER] ASIN: {asin}")

    try:
        # Fetch the product reviews page
        url = f'https://www.amazon.in/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews'
        print(f"[AMAZON_COUNTER] Review URL: {url}")

        # Simple GET request with cookies
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'accept-language': 'en-GB,en;q=0.9',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-ch-ua': '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-gpc': '1',
            'upgrade-insecure-requests': '1',
        }

        # Use manual cookies
        cookies = COOKIES

        print(f"[AMAZON_COUNTER] Sending GET request...")
        response = requests.get(
            url,
            cookies=cookies,
            headers=headers,
            timeout=30,
        )
        print(f"[AMAZON_COUNTER] Response status: {response.status_code}")

        # Check if cookies need refresh based on response
        
        # Extract review count from HTML
        print(f"[AMAZON_COUNTER] Extracting review count from HTML (response length: {len(response.text)} chars)...")

        # Debug: Save HTML to file for inspection
        debug_file = f"debug_review_page_{asin}.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"[AMAZON_COUNTER] DEBUG: Saved response to {debug_file}")

        # Check for common Amazon error pages
        if "Robot Check" in response.text or "Enter the characters" in response.text:
            print(f"[AMAZON_COUNTER] WARNING: CAPTCHA/Robot check detected!")
        if "Sorry! We couldn't find that page" in response.text:
            print(f"[AMAZON_COUNTER] WARNING: 404 page detected!")

        review_count = extract_review_count_from_html(response.text)
        print(f"[AMAZON_COUNTER] Extracted review count: {review_count}")

        if review_count > 0:
            print(f"[AMAZON_COUNTER] ✅ SUCCESS - Found {review_count} reviews")
            return (review_count, "Success")
        else:
            print(f"[AMAZON_COUNTER] ⚠️  No reviews found in HTML")
            return (0, "No reviews found")

    except requests.exceptions.HTTPError as e:
        print(f"[AMAZON_COUNTER] ❌ HTTP Error: {e.response.status_code}")
        print(f"[AMAZON_COUNTER] Response text preview: {e.response.text[:500]}")

        # Try refreshing cookies and retry once more
        print(f"[AMAZON_COUNTER] [REFRESH] Attempting cookie refresh due to HTTP error...")
        return (0, f"HTTP Error: {e.response.status_code}")
    except requests.exceptions.Timeout:
        print(f"[AMAZON_COUNTER] ❌ Request timeout")
        return (0, "Request timeout")
    except requests.exceptions.RequestException as e:
        print(f"[AMAZON_COUNTER] ❌ Request error: {str(e)}")
        return (0, f"Request error: {str(e)}")
    except Exception as e:
        print(f"[AMAZON_COUNTER] ❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return (0, f"Error: {str(e)}")


def process_csv(input_file: str, output_file: str):
    """
    Process CSV file and get review counts for all products.

    Args:
        input_file: Path to input CSV file
        output_file: Path to output CSV file
    """
    print("="*80)
    print("Amazon Review Counter")
    print("="*80)
    print(f"Input file: {input_file}")
    print(f"Output file: {output_file}")
    print("="*80)

    # Read input CSV
    try:
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            products = list(reader)

        print(f"\n✓ Found {len(products)} products")
    except FileNotFoundError:
        print(f"\n✗ Error: {input_file} not found!")
        return
    except Exception as e:
        print(f"\n✗ Error reading input file: {e}")
        return

    # Process each product
    results = []
    successful = 0
    failed = 0

    print("\nProcessing products...\n")

    for index, product in enumerate(products, 1):
        amazon_url = product.get('amazon_url', '').strip()
        name = product.get('Name', '').strip()
        product_id = product.get('id', '').strip()

        if not amazon_url:
            print(f"[{index}/{len(products)}] Skipping: No Amazon URL")
            results.append({
                'amazon_url': '',
                'Name': name,
                'id': product_id,
                'asin': '',
                'total_reviews': 0,
                'status': 'No URL'
            })
            failed += 1
            continue

        # Extract ASIN
        asin = extract_asin_from_url(amazon_url)

        if not asin:
            print(f"[{index}/{len(products)}] ✗ Failed to extract ASIN from URL")
            results.append({
                'amazon_url': amazon_url,
                'Name': name,
                'id': product_id,
                'asin': '',
                'total_reviews': 0,
                'status': 'Invalid URL'
            })
            failed += 1
            continue

        # Get review count
        print(f"[{index}/{len(products)}] Processing ASIN: {asin}...", end=" ")
        review_count, status = get_total_review_count(asin)

        if review_count > 0:
            print(f"✓ {review_count} reviews")
            successful += 1
        else:
            print(f"✗ {status}")
            failed += 1

        results.append({
            'amazon_url': amazon_url,
            'Name': name,
            'id': product_id,
            'asin': asin,
            'total_reviews': review_count,
            'status': status
        })

        # Add delay to avoid rate limiting
        if index < len(products):
            time.sleep(1)

    # Write output CSV
    print(f"\nWriting results to {output_file}...")

    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['amazon_url', 'Name', 'id', 'asin', 'total_reviews', 'status']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"✓ Results saved to {output_file}")
    except Exception as e:
        print(f"✗ Error writing output file: {e}")
        return

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"  Total products: {len(products)}")
    print(f"  Successful: {successful}")
    print(f"  Failed/No reviews: {failed}")
    print(f"  Total reviews counted: {sum(r['total_reviews'] for r in results)}")
    print("="*80)


def main():
    """Main function."""
    input_file = 'unprocessed_urls.csv'
    output_file = 'amazon_review_counts.csv'

    process_csv(input_file, output_file)


if __name__ == '__main__':
    main()
