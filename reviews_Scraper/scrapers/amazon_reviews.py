import requests
import json
import csv
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Add parent directory to path to import utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

MAX_RETRIES = 5
MAX_REVIEWS = 500  # Maximum number of reviews to scrape per product (set to None for unlimited)
USE_KEYWORD = False  # Set to True to use keyword strategy for >100 reviews, False for straightforward pagination

# =========================
# 🔧 Oxylabs Configuration
# =========================
PROXY_CONFIG = {
    'http': os.getenv("PROXY_HTTP_URL") or os.getenv("PROXY_HTTP"),
    'https': os.getenv("PROXY_HTTPS_URL") or os.getenv("PROXY_HTTPS"),
}

# Manual cookies - update these when they expire
COOKIES = {
    'session-id': '520-2663281-5809705',
    'ubid-acbin': '523-5911053-3929744',
    'rx': 'AQDWESCaNcSs3IVL77aPaA6vxqg=@Ab+AJGk=',
    'x-amz-captcha-1': '1764009673377678',
    'x-amz-captcha-2': 'm3l35dnJ18cDzBaVFwECRg==',
    'i18n-prefs': 'INR',
    'lc-acbin': 'en_IN',
    'id_pkel': 'n0',
    'id_pk': 'eyJuIjoiMCIsImFmIjoiMSIsImNjIjoiMSJ9',
    'sso-state-acbin': 'Xdsso|ZQHeKH3v9wmW8MYhiN2XpjHRQNBoDK6FWBr4CASShuNIX_Yy9DJygEydpj9lyDGrjgX07t0_KtV785y-7g7Z_-cDLHfRon0WTKsOGykRuKwUDFwJ',
    'x-acbin': '"JPJS@Za3aTdx2sjDUhnJ8OqY4VW5PU0QsL1WgQO2sRbBpY2TKUD6NGEo3YD7RhAU"',
    'at-acbin': 'Atza|gQAP9i9XAwEBAieTI6CjbQc0zsnL5yCOEA82MJ4B5jSW9O8ML-wuB8M2zd5thcpaeGo3o-AT1oEJ3gilUms0xLUga230j-uaXtbAj9WBDuGDXnVlXrXmIi7SMs7UOYfLJ1c_6XGJS5eTRxdhP476uDErueXyrqleK7JVjnrLZmF9pVa15JY3GsZcqXst4pTblGo0_HCr6Z7wpua4cZlK9lHCL10uQ6aTDXpxS40zar-IAY-zG6F9mNqeeGxBEv7OtytAznWHM1F85zYLHiUd4dYg_2-7Fe9Yo6WBKVL-EvJJsvslstZHbNIwUOAlFRp2c-lVwMxuvIUmsyjrlNT9U1deVw',
    'sess-at-acbin': '"/a2mXUhPquaEZHYfFpoNM2aeW9Uih7ppkM9Tv380ujo="',
    'sst-acbin': 'Sst1|PQE1HZVej7vzcvFeL3wZzM0zCf4pBaBkIOuWe_pHl7PEEbdqiXz-2rX0v11vrgi0ypBRrIFpFuKGzVC87t0uc8hIHCIjRpX250adxsi1qLmnzEDkOVdeSNqQnrYrt0zbq22ywTYZdOmUtlVe7PDgGadrAkp8f-3D61PX4sCX47ZltS7Lcdr-0sfqNKttqKnVXSPGrnaFrGzUk54DmljoHum2GbMk2EYIIgjhXYk-kJ6Q0wdoYJc6vYJTLOB9TAPa1j3SwYYSPWqqcQJ1p3QV5Uf5nyj0Lws-a08EA70QdRDnSQs',
    'session-id-time': '2082787201l',
    'csm-hit': 'tb:s-2DW42WBW0KP576N1Y0Z4|1764002798273&t:1764002800008&adb:adblk_yes',
    'session-token': 'gXQ4AG6ndyE3hn3HYhB1o8Q/cqcOgcnFUjgTDdQLi4R8zUrJRIryXPSwoey9xo0wRgRY4TRrVhdUaiK86kSQE0gKq/wi/7n8N8x4Lf0IvY+x2w8JfwRB+aDnTWMmR1EHdNJJcDr0peYrT/5zRmVqz97bfNO5Vb8JJLs9AaewtWJNmNPQrCkVfQVLpwOkTMfIT0UmAhE3rR9UN9K7Q63XHSJHwZEWeB2Es9lIFHemvGbgCquy/UiL2kyXFp0iumZ3RXGgBdV4CVK6+ms/WG/fA41d3tSzzW5HNBD97tTBnua+ifA2/xmXX6Y+YaIsSO0sn0gUzcjEDsIZJgEfFdj2eFi6m7MK9Lf0eXRVUaYxbxM9Yj4rN9v9Dg==',
    'rxc': 'ABkCgVswaDALgkipqnY',
}


HEADERS = {
    'accept': 'text/html,*/*',
    'accept-language': 'en-GB,en;q=0.9',
    'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
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

# Thread-safe print lock
print_lock = threading.Lock()


def thread_safe_print(*args, **kwargs):
    """Thread-safe print function."""
    with print_lock:
        print(*args, **kwargs)


def get_csrf_token_from_page(asin: str) -> str:
    """
    Fetch CSRF token from product page.

    Args:
        asin: Product ASIN

    Returns:
        CSRF token string
    """
    print(f"\n[AMAZON_REVIEWS] ========== get_csrf_token_from_page START ==========")
    print(f"[AMAZON_REVIEWS] ASIN: {asin}")

    # Try multiple URLs to get CSRF token
    urls_to_try = [
        f'https://www.amazon.in/dp/{asin}',  # Product page (try first)
        f'https://www.amazon.in/product-reviews/{asin}',  # Reviews page
        f'https://www.amazon.in/gp/product/{asin}'  # Alternative product page
    ]

    for url_index, url in enumerate(urls_to_try, 1):
        print(f"[AMAZON_REVIEWS] Trying URL {url_index}/{len(urls_to_try)}: {url}")
        try:
            print(f"[AMAZON_REVIEWS] Sending GET request...")
            cookies = COOKIES
            response = requests.get(url, cookies=cookies, headers={
                'User-Agent': HEADERS['user-agent']
            }, proxies=PROXY_CONFIG if PROXY_CONFIG.get('http') or PROXY_CONFIG.get('https') else None, timeout=30)

            print(f"[AMAZON_REVIEWS] Response status: {response.status_code}")

            # Skip 404 errors, try next URL
            if response.status_code == 404:
                print(f"[AMAZON_REVIEWS] 404 error, trying next URL...")
                continue

            response.raise_for_status()

            print(f"[AMAZON_REVIEWS] Parsing HTML (length: {len(response.text)} chars)...")
            soup = BeautifulSoup(response.text, 'html.parser')

            # Method 1: Check meta tags
            csrf_meta = soup.find('meta', {'name': 'anti-csrftoken-a2z'})
            print(f"[AMAZON_REVIEWS] Method 1 (meta tag): {csrf_meta is not None}")
            if csrf_meta and csrf_meta.get('content'):
                token = csrf_meta['content']
                print(f"[AMAZON_REVIEWS] ✅ CSRF token found via meta tag: {token[:20]}...")
                thread_safe_print(f"✓ CSRF token found from {url}")
                return token

            # Method 2: Check input fields
            csrf_input = soup.find('input', {'name': 'anti-csrftoken-a2z'})
            print(f"[AMAZON_REVIEWS] Method 2 (input field): {csrf_input is not None}")
            if csrf_input and csrf_input.get('value'):
                token = csrf_input['value']
                print(f"[AMAZON_REVIEWS] ✅ CSRF token found via input field: {token[:20]}...")
                thread_safe_print(f"✓ CSRF token found from {url}")
                return token

            # Method 3: Extract from any data attribute
            elements = soup.find_all(attrs={'data-csrf': True})
            print(f"[AMAZON_REVIEWS] Method 3 (data-csrf): Found {len(elements)} elements")
            if elements:
                token = elements[0]['data-csrf']
                print(f"[AMAZON_REVIEWS] ✅ CSRF token found via data-csrf: {token[:20]}...")
                thread_safe_print(f"✓ CSRF token found from {url}")
                return token

            print(f"[AMAZON_REVIEWS] No CSRF token found in this page, trying next URL...")
            # If page loaded but no CSRF found, continue to next URL
            # (Don't break - try all URLs)

        except requests.exceptions.HTTPError as e:
            print(f"[AMAZON_REVIEWS] HTTP error: {e}")
            # Skip HTTP errors and try next URL
            continue
        except Exception as e:
            print(f"[AMAZON_REVIEWS] Exception: {e}")
            import traceback
            traceback.print_exc()
            # Skip other errors and try next URL
            continue

    # If all URLs failed, return default fallback
    fallback_token = "hBNGvfRGziIX9Ow%2BcuVpuX2FMciVgYUvUbK8YfUB6i3NAAAAAGkMzQsAAAAB"
    print(f"[AMAZON_REVIEWS] ⚠️  No CSRF token found for {asin}, using fallback: {fallback_token[:20]}...")
    thread_safe_print(f"⚠ No CSRF token found for {asin}, using fallback")
    return fallback_token


def extract_review_count_from_response(response_text: str) -> int:
    """Extract total review count from Amazon's AJAX response."""
    try:
        if '#filter-info-section' in response_text:
            parts = response_text.split('&&&')
            for part in parts:
                if '#filter-info-section' in part:
                    try:
                        data = json.loads(part.strip())
                        if isinstance(data, list) and len(data) >= 3:
                            html_content = data[2]
                            match = re.search(r'(\d+)\s+matching customer review', html_content)
                            if match:
                                return int(match.group(1))
                    except (json.JSONDecodeError, ValueError):
                        continue
        return 0
    except Exception as e:
        return 0


def parse_ajax_response(response_text: str) -> List[str]:
    """Parse Amazon's special AJAX response format."""
    html_snippets = []

    try:
        parts = response_text.split('&&&')

        for part in parts:
            part = part.strip()
            if not part:
                continue

            try:
                data = json.loads(part)

                if isinstance(data, list) and len(data) >= 3:
                    command = data[0]
                    selector = data[1]
                    html_content = data[2]

                    if command in ['append', 'html', 'replaceWith'] and html_content:
                        html_snippets.append(html_content)

            except json.JSONDecodeError:
                continue

    except Exception as e:
        thread_safe_print(f"Error parsing AJAX response: {e}")

    return html_snippets


def extract_reviews_from_html(html_snippets: List[str]) -> List[Dict[str, Any]]:
    """Extract reviews from HTML snippets."""
    reviews = []

    for html in html_snippets:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # Amazon uses both <li> and <div> tags for reviews
            review_divs = soup.find_all(['li', 'div'], {'data-hook': 'review'})

            for review_div in review_divs:
                try:
                    review_id = review_div.get('id', '')

                    author_elem = review_div.find('span', {'class': 'a-profile-name'})
                    author = author_elem.get_text(strip=True) if author_elem else ''

                    rating_elem = review_div.find('i', {'data-hook': 'review-star-rating'})
                    if not rating_elem:
                        rating_elem = review_div.find('i', {'data-hook': 'cmps-review-star-rating'})

                    rating = 0
                    if rating_elem:
                        rating_text = rating_elem.get_text(strip=True)
                        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                        if rating_match:
                            rating = float(rating_match.group(1))

                    title_elem = review_div.find('a', {'data-hook': 'review-title'})
                    if not title_elem:
                        title_elem = review_div.find('span', {'data-hook': 'review-title'})
                    title = title_elem.get_text(strip=True) if title_elem else ''

                    text_elem = review_div.find('span', {'data-hook': 'review-body'})
                    review_text = text_elem.get_text(strip=True) if text_elem else ''

                    date_elem = review_div.find('span', {'data-hook': 'review-date'})
                    review_date = date_elem.get_text(strip=True) if date_elem else ''

                    verified_elem = review_div.find('span', {'data-hook': 'avp-badge'})
                    verified_purchase = verified_elem is not None

                    helpful_elem = review_div.find('span', {'data-hook': 'helpful-vote-statement'})
                    helpful_votes = 0
                    if helpful_elem:
                        helpful_text = helpful_elem.get_text(strip=True)
                        helpful_match = re.search(r'(\d+)', helpful_text.replace(',', ''))
                        if helpful_match:
                            helpful_votes = int(helpful_match.group(1))

                    format_elem = review_div.find('a', {'data-hook': 'format-strip'})
                    product_format = format_elem.get_text(strip=True) if format_elem else ''

                    image_elems = review_div.find_all('img', {'data-hook': 'review-image-tile'})
                    image_urls = [img.get('src', '') for img in image_elems if img.get('src')]

                    review = {
                        'review_id': review_id,
                        'author': author,
                        'rating': rating,
                        'title': title,
                        'review_text': review_text,
                        'review_date': review_date,
                        'verified_purchase': verified_purchase,
                        'helpful_votes': helpful_votes,
                        'product_format': product_format,
                        'image_count': len(image_urls),
                        'image_urls': '|'.join(image_urls) if image_urls else '',
                    }

                    reviews.append(review)

                except Exception as e:
                    continue

        except Exception as e:
            continue

    return reviews


def fetch_reviews_ajax(asin: str, page_number: int, csrf_token: str, filter_by_star: str = '', keyword: str = '') -> tuple:
    """Fetch reviews using Amazon's AJAX API with optional keyword filtering."""
    print(f"\n[AMAZON_REVIEWS] ========== fetch_reviews_ajax START ==========")
    print(f"[AMAZON_REVIEWS] ASIN: {asin}, Page: {page_number}, Star: {filter_by_star}, Keyword: '{keyword}'")

    max_retries = 5
    retry_delay = 3

    for attempt in range(1, max_retries + 1):
        try:
            if attempt > 1:
                print(f"[AMAZON_REVIEWS] Retry attempt {attempt}/{max_retries}...")
                thread_safe_print(f"  Retry attempt {attempt}/{max_retries}...")

            # Determine URL ref and scope based on filter and keyword
            if keyword:
                ref_tag = 'cm_cr_arp_d_viewopt_kywd'
                scope_num = 1
            elif filter_by_star:
                ref_tag = 'cm_cr_arp_d_viewopt_sr'
                scope_num = 2
            else:
                ref_tag = f'cm_cr_arp_d_paging_btm_next_{page_number}'
                scope_num = 1

            url = f'https://www.amazon.in/portal/customer-reviews/ajax/reviews/get/ref={ref_tag}'
            print(f"[AMAZON_REVIEWS] AJAX URL: {url}")

            data = {
                'sortBy': '',
                'reviewerType': 'all_reviews',
                'formatType': 'all_formats' if keyword else '',
                'mediaType': 'all_contents' if keyword else '',
                'filterByStar': filter_by_star,
                'filterByAge': '',
                'pageNumber': str(page_number),
                'filterByLanguage': '',
                'filterByKeyword': keyword,
                'shouldAppend': 'undefined',
                'deviceType': 'desktop',
                'canShowIntHeader': 'undefined',
                'reftag': ref_tag,
                'pageSize': '10',
                'asin': asin,
                'scope': f'reviewsAjax{scope_num}',
            }

            headers = HEADERS.copy()
            headers['anti-csrftoken-a2z'] = csrf_token

            if keyword:
                headers['referer'] = f'https://www.amazon.in/product-reviews/{asin}/ref=cm_cr_arp_d_viewopt_kywd?ie=UTF8&pageNumber={page_number}&reviewerType=all_reviews&filterByStar={filter_by_star}&formatType=all_formats&mediaType=all_contents'
            elif filter_by_star:
                headers['referer'] = f'https://www.amazon.in/product-reviews/{asin}/ref=cm_cr_arp_d_viewopt_sr?ie=UTF8&reviewerType=all_reviews&pageNumber={page_number}&filterByStar={filter_by_star}'
            else:
                headers['referer'] = f'https://www.amazon.in/product-reviews/{asin}/ref=cm_cr_arp_d_paging_btm_next_{page_number}?ie=UTF8&reviewerType=all_reviews&pageNumber={page_number}'

            print(f"[AMAZON_REVIEWS] Sending POST request to AJAX API...")
            cookies = COOKIES
            response = requests.post(
                url,
                data=data,
                cookies=cookies,
                headers=headers,
                proxies=PROXY_CONFIG if PROXY_CONFIG.get('http') or PROXY_CONFIG.get('https') else None,
                timeout=30,
            )
            print(f"[AMAZON_REVIEWS] Response status: {response.status_code}")
            print(f"[AMAZON_REVIEWS] Response length: {len(response.text)} chars")
            
            review_count = 0
            if page_number == 1:
                print(f"[AMAZON_REVIEWS] Extracting review count from AJAX response (page 1)...")
                review_count = extract_review_count_from_response(response.text)
                print(f"[AMAZON_REVIEWS] Review count from AJAX: {review_count}")

            print(f"[AMAZON_REVIEWS] Parsing AJAX response...")
            html_snippets = parse_ajax_response(response.text)
            print(f"[AMAZON_REVIEWS] Found {len(html_snippets)} HTML snippets")

            if not html_snippets:
                print(f"[AMAZON_REVIEWS] ⚠️  No HTML snippets found, returning empty")
                return ([], review_count)

            print(f"[AMAZON_REVIEWS] Extracting reviews from HTML snippets...")
            reviews = extract_reviews_from_html(html_snippets)
            print(f"[AMAZON_REVIEWS] Extracted {len(reviews)} reviews")

            for review in reviews:
                if filter_by_star:
                    review['star_filter'] = filter_by_star
                if keyword:
                    review['keyword'] = keyword
                else:
                    review['keyword'] = ''

            print(f"[AMAZON_REVIEWS] ✅ SUCCESS - Returning {len(reviews)} reviews, count={review_count}")
            return (reviews, review_count)

        except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            print(f"[AMAZON_REVIEWS] ❌ Network error (attempt {attempt}/{max_retries}): {type(e).__name__} - {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                print(f"[AMAZON_REVIEWS] Max retries reached, returning empty")
                return ([], 0)
        except Exception as e:
            print(f"[AMAZON_REVIEWS] ❌ Unexpected error: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()
            return ([], 0)

    print(f"[AMAZON_REVIEWS] Exiting after all retries, returning empty")
    return ([], 0)


def extract_asin_from_url(url: str) -> str:
    """Extract ASIN from Amazon product URL."""
    try:
        match = re.search(r'/dp/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        match = re.search(r'/gp/product/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)

        return None

    except Exception as e:
        return None


def get_processed_asins(output_file: str) -> set:
    """
    Read the output CSV and return a set of already processed ASINs.
    Used for resume functionality.
    """
    processed_asins = set()

    if not os.path.exists(output_file):
        return processed_asins

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                asin = row.get('asin', '').strip()
                if asin:
                    processed_asins.add(asin)

        if processed_asins:
            print(f"✓ Resume mode: Found {len(processed_asins)} already processed products")
    except Exception as e:
        print(f"⚠ Warning: Could not read output file for resume: {e}")

    return processed_asins


def scrape_product_reviews_worker(args):
    """
    Worker function for parallel scraping.
    Uses intelligent strategy: keyword filtering for >100 reviews, normal pagination for ≤100.

    Args:
        args: Tuple of (index, amazon_url, company, product_type, total_products)

    Returns:
        Tuple of (index, reviews_list, review_count, success, summary_data)
    """
    index, amazon_url, Name, id, total_products = args

    thread_safe_print(f"\n{'#'*80}")
    thread_safe_print(f"PRODUCT {index}/{total_products}")
    thread_safe_print(f"{'#'*80}")

    try:
        asin = extract_asin_from_url(amazon_url)

        if not asin:
            thread_safe_print(f"✗ Failed to extract ASIN from URL")
            return (index, [], 0, False, None)

        thread_safe_print(f"\n{'='*80}")
        thread_safe_print(f"Processing: {Name} - {id}")
        thread_safe_print(f"Amazon URL: {amazon_url}")
        thread_safe_print(f"ASIN: {asin}")
        thread_safe_print(f"Max Reviews: {MAX_REVIEWS if MAX_REVIEWS is not None else 'Unlimited'}")
        thread_safe_print(f"{'='*80}")

        thread_safe_print(f"\nFetching CSRF token for {asin}...")
        csrf_token = get_csrf_token_from_page(asin)
        thread_safe_print(f"CSRF Token: {csrf_token[:20]}...")

        star_filters = ['five_star', 'four_star', 'three_star', 'two_star', 'one_star']
        star_names = {'five_star': '5 Star', 'four_star': '4 Star', 'three_star': '3 Star',
                      'two_star': '2 Star', 'one_star': '1 Star'}

        five_star_keywords = [
            'good', 'great', 'excellent', 'amazing', 'fantastic', 'wonderful', 'awesome',
            'perfect', 'nice', 'best', 'love', 'loved', 'happy', 'satisfied', 'worth', 'value',
            'recommend', 'impressive', 'superb', 'pleasant', 'gentle', 'effective', 'comfortable',
            'works', 'working', 'useful', 'reliable', 'trustworthy', 'soothing', 'smooth', 'soft',
            
            # Product experience
            'smell', 'fragrance', 'texture', 'feel', 'non sticky', 'absorbs', 'moisturizing',
            'hydrating', 'creamy', 'light', 'refreshing', 'cooling', 'clean', 'mild', 'safe',
            'natural', 'organic', 'fresh', 'pure', 'softness', 'nourishing',
            
            # Usability & suitability
            'easy', 'convenient', 'handy', 'travel', 'daily', 'routine', 'quick', 'simple',
            'lasting', 'long', 'durable', 'gentle', 'safe', 'for baby', 'for skin', 'for hair',
            
            # Purchase & service experience
            'delivery', 'fast', 'quick', 'service', 'packaging', 'sealed', 'intact', 'on time',
            'original', 'authentic', 'brand', 'quality', 'premium', 'genuine', 'affordable',
            'price', 'deal', 'offer', 'saver', 'value for money',
            
            # Function & performance
            'protects', 'prevents', 'helps', 'improves', 'reduces', 'softens', 'cleanses',
            'moisturizes', 'hydrates', 'heals', 'soothes', 'absorbs well', 'non greasy',
            'gentle on skin', 'no irritation', 'baby safe', 'rash free', 'effective results',
            
            # Common neutral/filler words
            'the', 'is', 'and', 'it', 'this', 'very', 'so', 'well', 'much', 'really',
            'has', 'have', 'was', 'are', 'been', 'for', 'with', 'all', 'my', 'me',
            'product', 'buy', 'purchase', 'bought', 'got', 'received'
        ]

        low_star_keywords = [
            'not', 'no', 'never', 'bad', 'worst', 'poor', 'terrible', 'horrible', 'pathetic',
            'fridge', 'refrigerator', 'cooling', 'freezer', 'compressor', 'temperature', 'ice',
            'leak', 'leaking',
            'problem', 'issue', 'defect', 'fault', 'broken', 'damage', 'damaged',
            'service', 'delayed', 'delay', 'late', 'slow', 'call center', 'customer care',
            'return', 'returned', 'refund', 'refunded', 'replace', 'replacement', 'exchange',
            'waste', 'disappointed', 'disappointment', 'regret', 'useless', 'cheap', 'fail', 'failed',
            'amazon', 'seller', 'delivery',
            'but', 'ok', 'okay', 'okayish', 'average', 'overall', 'however', 'though',
            'good', 'great', 'nice', 'best', 'happy', 'better', 'fine', 'satisfied',
            'the', 'is', 'and', 'it', 'this', 'very', 'so', 'was', 'has', 'have',
            'are', 'been', 'for', 'with', 'all', 'my', 'me', 'after', 'within',
            'product', 'buy', 'purchase', 'bought', 'got', 'received', 'ordered'
        ]

        product_reviews = []
        star_counts = {}
        star_available_counts = {}
        seen_review_ids = set()

        for star_filter in star_filters:
            # Stop if we've reached MAX_REVIEWS
            if MAX_REVIEWS is not None and len(product_reviews) >= MAX_REVIEWS:
                thread_safe_print(f"\n  ✓ MAX_REVIEWS limit reached ({len(product_reviews)}/{MAX_REVIEWS}). Stopping scraping.")
                break
            thread_safe_print(f"\n  [{star_names[star_filter]}] Processing...")

            reviews_batch, total_count = fetch_reviews_ajax(asin, 1, csrf_token, filter_by_star=star_filter)

            thread_safe_print(f"    [{star_names[star_filter]}] Available: {total_count} reviews (Page 1: {len(reviews_batch)} reviews)")
            star_available_counts[star_filter] = total_count

            # Don't skip if we got reviews in first batch, even if total_count is 0
            if total_count == 0 and not reviews_batch:
                star_counts[star_filter] = 0
                thread_safe_print(f"    [{star_names[star_filter]}] No reviews found")
                continue

            # If total_count is 0 but we have reviews, use batch count as estimate
            if total_count == 0 and reviews_batch:
                thread_safe_print(f"    [{star_names[star_filter]}] API returned 0 but got {len(reviews_batch)} reviews - continuing...")
                total_count = len(reviews_batch) * 10  # Estimate more pages exist

            use_keywords = USE_KEYWORD and total_count > 100
            keywords = five_star_keywords if star_filter == 'five_star' else low_star_keywords if use_keywords else []

            star_unique_reviews = {}

            if use_keywords:
                thread_safe_print(f"    [{star_names[star_filter]}] Using hybrid strategy: pages 1-10, then keywords")

                # PHASE 1: First scrape pages 1-10 to get ~100 reviews
                thread_safe_print(f"    [{star_names[star_filter]}] Phase 1: Scraping pages 1-10...")

                # Add first batch (page 1 already fetched)
                for review in reviews_batch:
                    review_id = review.get('review_id', '')
                    if review_id and review_id not in star_unique_reviews:
                        star_unique_reviews[review_id] = review

                # Scrape pages 2-10
                for page in range(2, 11):
                    # Check if we've reached MAX_REVIEWS
                    if MAX_REVIEWS is not None and len(star_unique_reviews) >= (MAX_REVIEWS - len(product_reviews)):
                        thread_safe_print(f"\n      [Page {page}] Stopping: Approaching MAX_REVIEWS limit")
                        break

                    reviews_batch, _ = fetch_reviews_ajax(asin, page, csrf_token, filter_by_star=star_filter)

                    if reviews_batch:
                        new_reviews = 0
                        for review in reviews_batch:
                            review_id = review.get('review_id', '')
                            if review_id and review_id not in star_unique_reviews:
                                star_unique_reviews[review_id] = review
                                new_reviews += 1

                        # Show detailed page info
                        thread_safe_print(f"\n      [Page {page}] ✓ Status: Success | Extracted: {len(reviews_batch)} reviews | New: {new_reviews}")
                        # Show preview of first review
                        if reviews_batch and len(reviews_batch) > 0:
                            first_review = reviews_batch[0]
                            title_preview = first_review.get('title', 'No title')[:60]
                            author_preview = first_review.get('author', 'Unknown')[:30]
                            thread_safe_print(f"      Preview: \"{title_preview}...\" by {author_preview}")
                        time.sleep(1.5)
                    else:
                        thread_safe_print(f"\n      [Page {page}] ✗ Status: Empty response | Extracted: 0 reviews")

                thread_safe_print(f"\n    [{star_names[star_filter]}] Phase 1 complete: {len(star_unique_reviews)} reviews collected")

                # PHASE 2: Use keyword strategy for remaining reviews
                if len(star_unique_reviews) < total_count:
                    remaining = total_count - len(star_unique_reviews)
                    thread_safe_print(f"    [{star_names[star_filter]}] Phase 2: Using keywords for remaining {remaining} reviews")

                    for keyword_index, keyword in enumerate(keywords, 1):
                        # Check if we've reached MAX_REVIEWS
                        if MAX_REVIEWS is not None and len(star_unique_reviews) >= (MAX_REVIEWS - len(product_reviews)):
                            thread_safe_print(f"    [{star_names[star_filter]}] Stopping: Approaching MAX_REVIEWS limit")
                            break

                        if len(star_unique_reviews) >= total_count:
                            thread_safe_print(f"    [{star_names[star_filter]}] Target reached ({len(star_unique_reviews)}/{total_count})")
                            break

                        thread_safe_print(f"\n      [Keyword {keyword_index}/{len(keywords)}: '{keyword}']")

                        page = 1
                        consecutive_empty_pages = 0
                        max_consecutive_empty = 3
                        max_pages = 10

                        while page <= max_pages:
                            # Check if we've reached MAX_REVIEWS
                            if MAX_REVIEWS is not None and len(star_unique_reviews) >= (MAX_REVIEWS - len(product_reviews)):
                                thread_safe_print(f"        Stopping: Approaching MAX_REVIEWS limit")
                                break

                            reviews_batch, _ = fetch_reviews_ajax(asin, page, csrf_token, filter_by_star=star_filter, keyword=keyword)

                            if reviews_batch:
                                new_reviews = 0
                                for review in reviews_batch:
                                    review_id = review.get('review_id', '')
                                    if review_id and review_id not in star_unique_reviews:
                                        star_unique_reviews[review_id] = review
                                        new_reviews += 1

                                consecutive_empty_pages = 0

                                # Show detailed info
                                thread_safe_print(f"        Page {page}: ✓ Status: Success | Extracted: {len(reviews_batch)} reviews | New: {new_reviews}")
                                if reviews_batch and len(reviews_batch) > 0 and new_reviews > 0:
                                    first_new = reviews_batch[0]
                                    title_preview = first_new.get('title', 'No title')[:50]
                                    thread_safe_print(f"        Preview: \"{title_preview}...\"")

                                if len(star_unique_reviews) >= total_count:
                                    thread_safe_print(f"        Target reached ({len(star_unique_reviews)}/{total_count})!")
                                    break
                            else:
                                consecutive_empty_pages += 1
                                thread_safe_print(f"        Page {page}: ✗ Status: Empty response")
                                if consecutive_empty_pages >= max_consecutive_empty:
                                    break

                            page += 1
                            if reviews_batch:
                                time.sleep(1.5)

                        if len(star_unique_reviews) >= total_count:
                            break

            else:
                thread_safe_print(f"    [{star_names[star_filter]}] Using normal pagination (≤100 reviews)")

                page = 1
                consecutive_empty_pages = 0
                max_consecutive_empty = 3
                max_pages = 15

                for review in reviews_batch:
                    review_id = review.get('review_id', '')
                    if review_id and review_id not in star_unique_reviews:
                        star_unique_reviews[review_id] = review

                page = 2

                while page <= max_pages:
                    # Check if we've reached MAX_REVIEWS
                    if MAX_REVIEWS is not None and len(star_unique_reviews) >= (MAX_REVIEWS - len(product_reviews)):
                        thread_safe_print(f"\n      [Page {page}] Stopping: Approaching MAX_REVIEWS limit")
                        break

                    reviews_batch, _ = fetch_reviews_ajax(asin, page, csrf_token, filter_by_star=star_filter)

                    if reviews_batch:
                        new_reviews = 0
                        for review in reviews_batch:
                            review_id = review.get('review_id', '')
                            if review_id and review_id not in star_unique_reviews:
                                star_unique_reviews[review_id] = review
                                new_reviews += 1

                        consecutive_empty_pages = 0

                        # Show detailed page info
                        thread_safe_print(f"\n      [Page {page}] ✓ Status: Success | Extracted: {len(reviews_batch)} reviews | New: {new_reviews}")
                        # Show preview of first review
                        if reviews_batch and len(reviews_batch) > 0:
                            first_review = reviews_batch[0]
                            title_preview = first_review.get('title', 'No title')[:60]
                            author_preview = first_review.get('author', 'Unknown')[:30]
                            thread_safe_print(f"      Preview: \"{title_preview}...\" by {author_preview}")
                    else:
                        consecutive_empty_pages += 1
                        thread_safe_print(f"\n      [Page {page}] ✗ Status: Empty response | Extracted: 0 reviews")
                        if consecutive_empty_pages >= max_consecutive_empty:
                            break

                    page += 1
                    if reviews_batch:
                        time.sleep(2.0)

            for review_id, review in star_unique_reviews.items():
                if review_id not in seen_review_ids:
                    # Check if adding this review would exceed MAX_REVIEWS
                    if MAX_REVIEWS is not None and len(product_reviews) >= MAX_REVIEWS:
                        thread_safe_print(f"\n    [{star_names[star_filter]}] MAX_REVIEWS limit reached, stopping")
                        break

                    review['amazon_url'] = amazon_url
                    review['Name'] = Name
                    review['Id'] = id
                    review['asin'] = asin
                    product_reviews.append(review)
                    seen_review_ids.add(review_id)

            star_counts[star_filter] = len(star_unique_reviews)
            thread_safe_print(f"\n    [{star_names[star_filter]}] Collected: {len(star_unique_reviews)} unique reviews")
            thread_safe_print(f"    Total reviews so far: {len(product_reviews)}" + (f"/{MAX_REVIEWS}" if MAX_REVIEWS is not None else ""))

            if star_filter != star_filters[-1]:
                time.sleep(2)

        summary_data = {
            'amazon_url': amazon_url,
            'Name': Name,
            'id': id,
            'asin': asin,
            'five_star_available': star_available_counts.get('five_star', 0),
            'five_star_scraped': star_counts.get('five_star', 0),
            'four_star_available': star_available_counts.get('four_star', 0),
            'four_star_scraped': star_counts.get('four_star', 0),
            'three_star_available': star_available_counts.get('three_star', 0),
            'three_star_scraped': star_counts.get('three_star', 0),
            'two_star_available': star_available_counts.get('two_star', 0),
            'two_star_scraped': star_counts.get('two_star', 0),
            'one_star_available': star_available_counts.get('one_star', 0),
            'one_star_scraped': star_counts.get('one_star', 0),
            'total_reviews': len(product_reviews)
        }

        thread_safe_print(f"\n  Product Summary: {len(product_reviews)} unique reviews extracted")
        return (index, product_reviews, len(product_reviews), True, summary_data)

    except Exception as e:
        thread_safe_print(f"\n✗ Error scraping product {index}: {e}")
        import traceback
        traceback.print_exc()
        return (index, [], 0, False, None)


def save_reviews_to_csv_ordered(all_reviews: List[Dict[str, Any]], output_file: str):
    """
    Save reviews to CSV file in order.

    Args:
        all_reviews: List of review dictionaries (already ordered)
        output_file: Path to output CSV file
    """
    if not all_reviews:
        print("No reviews to save.")
        return

    fieldnames = [
        'amazon_url', 'Name', 'id', 'asin',
        'review_id', 'author', 'rating', 'title', 'review_text',
        'review_date', 'verified_purchase', 'helpful_votes',
        'product_format', 'image_count', 'image_urls', 'star_filter', 'keyword'
    ]

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_reviews)

    print(f"\n✓ Saved {len(all_reviews)} reviews to {output_file}")


def main():
    """Main function - Parallel scraping with ordered output."""

    input_csv = 'unprocessed_urls.csv'
    output_file = 'allLinksAmazon_reviews_Unprocessed.csv'
    summary_file = 'allLinksAmazon_reviews_unprocessed_summary.csv'
    max_workers = 1 # Number of parallel threads (adjust based on your needs)

    print("="*80)
    print("Starting Amazon Multi-Product Review Scraper (PARALLEL Mode)")
    print("="*80)
    print(f"Input CSV: {input_csv}")
    print(f"Output CSV: {output_file}")
    print(f"Summary CSV: {summary_file}")
    print(f"Max Workers: {max_workers}")
    print(f"Max Reviews per Product: {MAX_REVIEWS if MAX_REVIEWS is not None else 'Unlimited'}")
    print(f"Keyword Strategy: {'Enabled' if USE_KEYWORD else 'Disabled (straightforward pagination)'}")

    # Read input CSV
    try:
        with open(input_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            products = list(reader)

        print(f"\nFound {len(products)} products to scrape")
    except Exception as e:
        print(f"\n✗ Error reading input CSV: {e}")
        return

    # Get already processed ASINs for resume functionality
    processed_asins = get_processed_asins(output_file)

    # Prepare tasks
    tasks = []
    skipped_count = 0
    task_index = 1  # Sequential task numbering for ordered CSV writing
    for index, product in enumerate(products, 1):
        amazon_url = product.get('amazon_url', '').strip()
        Name = product.get('Name', '').strip()
        id = product.get('id', '').strip()

        if not amazon_url:
            print(f"[{index}/{len(products)}] Skipping row - no Amazon URL")
            continue

        # Check if already processed (resume functionality)
        asin = extract_asin_from_url(amazon_url)
        if asin and asin in processed_asins:
            skipped_count += 1
            if skipped_count <= 5:  # Only show first 5 to avoid spam
                print(f"[{index}/{len(products)}] Skipping {asin} - already processed")
            continue

        # Use sequential task_index for ordered writing, not original index
        tasks.append((task_index, amazon_url, Name, id, len(products)))
        task_index += 1

    if skipped_count > 0:
        print(f"\n✓ Skipped {skipped_count} already processed products")

    print(f"\n{'='*80}")
    print(f"Processing {len(tasks)} products in parallel (max {max_workers} at a time)...")
    print(f"{'='*80}")

    # Execute tasks in parallel
    results = {}
    csv_lock = threading.Lock()  # Lock for CSV writing
    next_product_to_write = 1  # Track which product should be written next
    pending_results = {}  # Buffer for out-of-order results
    summary_data_list = []
    total_reviews = 0
    successful_products = 0
    # If resuming (processed_asins exist), append mode; otherwise write fresh
    first_write = len(processed_asins) == 0

    def write_product_to_csv(prod_index, reviews, review_count, success, summary_data):
        """Write a single product's reviews to CSV in order."""
        nonlocal first_write, total_reviews, successful_products

        if reviews:
            thread_safe_print(f"  → Writing Product {prod_index}: {review_count} reviews...")
            total_reviews += review_count

            # Determine write mode
            mode = 'w' if first_write else 'a'

            # Write to CSV
            fieldnames = [
                'amazon_url', 'Name', 'id', 'asin',
                'review_id', 'author', 'rating', 'title', 'review_text',
                'review_date', 'verified_purchase', 'helpful_votes',
                'product_format', 'image_count', 'image_urls', 'star_filter', 'keyword'
            ]

            with open(output_file, mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')

                if first_write:
                    writer.writeheader()
                    first_write = False

                writer.writerows(reviews)

        if success and review_count > 0:
            successful_products += 1

        if summary_data:
            summary_data_list.append(summary_data)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {executor.submit(scrape_product_reviews_worker, task): task for task in tasks}

        # Collect results as they complete
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                result = future.result()
                index, reviews, review_count, success, summary_data = result
                results[index] = (reviews, review_count, success, summary_data)

                if success:
                    thread_safe_print(f"\n✓ Product {index}: Completed with {review_count} reviews")
                else:
                    thread_safe_print(f"\n✗ Product {index}: Failed")

                # Write to CSV in order
                with csv_lock:
                    # Store this result
                    pending_results[index] = (reviews, review_count, success, summary_data)

                    # Write all consecutive products that are ready
                    while next_product_to_write in pending_results:
                        prod_index = next_product_to_write
                        prod_reviews, prod_count, prod_success, prod_summary = pending_results[prod_index]

                        write_product_to_csv(prod_index, prod_reviews, prod_count, prod_success, prod_summary)

                        del pending_results[prod_index]
                        next_product_to_write += 1

            except Exception as e:
                thread_safe_print(f"\n✗ Error processing task: {e}")

    thread_safe_print(f"\n{'='*80}")
    thread_safe_print(f"All products written to CSV in order")
    thread_safe_print(f"{'='*80}")

    # Write summary CSV
    print(f"\n{'='*80}")
    print("Writing summary CSV...")
    print(f"{'='*80}")

    with open(summary_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['amazon_url', 'Name', 'id', 'asin',
                      'five_star_available', 'five_star_scraped',
                      'four_star_available', 'four_star_scraped',
                      'three_star_available', 'three_star_scraped',
                      'two_star_available', 'two_star_scraped',
                      'one_star_available', 'one_star_scraped',
                      'total_reviews']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for summary_data in summary_data_list:
            writer.writerow(summary_data)

    print(f"\n✓ Summary written to {summary_file}")

    # Print final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY - ALL PRODUCTS (PARALLEL)")
    print("="*80)
    print(f"  Total products processed: {len(tasks)}")
    print(f"  Successful products: {successful_products}")
    print(f"  Failed products: {len(tasks) - successful_products}")
    print(f"  Total reviews extracted: {total_reviews}")
    print(f"\n  Reviews CSV: {output_file}")
    print(f"  Summary CSV: {summary_file}")
    print("="*80)


if __name__ == '__main__':
    main()
