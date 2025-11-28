#!/usr/bin/env python3
"""
flipkart_reviews_final.py

Single-threaded Flipkart reviews scraper — uses fetchSeoData payload for all pages
Reads product URLs from an input CSV, converts to review URL, scrapes reviews until last page,
and saves results to an output CSV. Deduplicates by review_id.

Usage:
  1) Create .env with FK_COOKIE, FK_USER_AGENT, FK_X_USER_AGENT, INPUT_CSV, OUTPUT_CSV
  2) Ensure input.csv has product URLs (either header 'url' or first column URLs)
  3) python flipkart_reviews_final.py
"""

import os
import re
import csv
import json
import time
import math
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote_plus, unquote_plus
import requests
from dotenv import load_dotenv

load_dotenv()

# --- Configuration from .env ---
FK_COOKIE = os.getenv("FK_COOKIE", "").strip()
FK_USER_AGENT = os.getenv("FK_USER_AGENT",
                          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")
FK_X_USER_AGENT = os.getenv("FK_X_USER_AGENT", FK_USER_AGENT + " FKUA/website/42/website/Desktop")
INPUT_CSV = os.getenv("INPUT_CSV", "input.csv")
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "flipkart_reviews_output.csv")

# Endpoint
API_URL = "https://2.rome.api.flipkart.com/api/4/page/fetch"

# Headers
HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "User-Agent": FK_USER_AGENT,
    "X-User-Agent": FK_X_USER_AGENT,
    "Referer": "https://www.flipkart.com/",
    "Origin": "https://www.flipkart.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Sec-GPC": "1",
}

if FK_COOKIE:
    HEADERS["Cookie"] = FK_COOKIE
else:
    print("[WARN] FK_COOKIE not found in .env — proceeding without cookies (may fail if Flipkart requires them).")

# Output headers requested by user:
OUTPUT_HEADERS = [
    "Company", "Product", "author", "city", "created_date", "downvotes",
    "flipkart_url", "helpful_count", "image_count", "rating", "review_id",
    "review_text", "title", "upvotes", "review_url", "review_image_url"
]


# ----------------- Utility functions -----------------
def clean_product_url(url: str) -> str:
    """
    Convert product URL to canonical review page base (without tracking params),
    then later we'll add ?page=N
    """
    url = url.strip()
    if not url:
        return ""
    try:
        p = urlparse(url)
        path = p.path
        # We expect something like /<slug>/p/<itemid> or /<slug>/p/itm...
        # Convert to product-reviews path based on observed pattern:
        # If URL already contains '/product-reviews/' keep slug and item id
        if "/product-reviews/" in path:
            base = f"{p.scheme}://{p.netloc}{path}"
            # remove any query but we'll preserve pid and lid if required — safer to keep pid
            qs = parse_qs(p.query)
            pid = qs.get("pid", [None])[0]
            if pid:
                return f"{base.split('?')[0].split('#')[0].split('&')[0]}"
            return base.split('?')[0]
        # If product page, replace '/p/' with '/product-reviews/' and drop unnecessary queries
        new_path = path
        # If path contains '/p/' -> construct review path with item token (itme... or itm...)
        if "/p/" in path:
            # replace '/p/' with '/product-reviews/'
            new_path = path.replace("/p/", "/product-reviews/")
            # create base
            base = f"{p.scheme}://{p.netloc}{new_path}"
            # preserve pid if present
            qs = parse_qs(p.query)
            pid = qs.get("pid", [None])[0]
            if pid:
                return base.split('?')[0] + f"?pid={pid}"
            return base.split('?')[0]
        # fallback — just append '/product-reviews/'
        base = f"{p.scheme}://{p.netloc}{path}"
        return base.split('?')[0]
    except Exception:
        return url


def build_page_uri(review_base: str, page_num: int) -> str:
    """
    Build the pageUri used in the payload — keep it same shape Flipkart uses:
    e.g. "/<slug>/product-reviews/itm...?...&page=2"
    review_base may already contain ?pid=...
    """
    if "?" in review_base:
        return f"{review_base}&page={page_num}"
    else:
        return f"{review_base}?page={page_num}"


def replace_image_placeholders(url: str, w=800, h=800, q=80) -> str:
    if not url:
        return ""
    return url.replace("{@width}", str(w)).replace("{@height}", str(h)).replace("{@quality}", str(q))


def recursive_find_widgets(obj):
    """
    Recursively find all dicts where key 'widget' exists and yields (parent_dict, widget_dict)
    """
    found = []
    if isinstance(obj, dict):
        if "widget" in obj and isinstance(obj["widget"], dict):
            found.append(obj)
        for v in obj.values():
            found.extend(recursive_find_widgets(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(recursive_find_widgets(item))
    return found


def safe_get(d, *keys):
    """safe nested get"""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
        if cur is None:
            return None
    return cur


# ----------------- Review extraction -----------------
def extract_reviews_from_response(resp_json, review_page_url):
    """
    Given the JSON returned by the /api/4/page/fetch endpoint,
    find all REVIEWS widgets and extract reviews list (as dicts).
    Returns (reviews_list, pagination_total_pages or None).
    """
    widgets = recursive_find_widgets(resp_json)
    reviews = []
    total_pages = None

    for widget_parent in widgets:
        widget = widget_parent.get("widget", {})
        wtype = widget.get("type")
        data = widget.get("data", {})
        # Pagination widget (if present) -> get total pages
        if wtype == "PAGINATION_BAR":
            total_pages = safe_get(data, "totalPages") or safe_get(data, "data", "totalPages") or safe_get(data, "data", "totalPages")
            # sometimes totalPages nested in data.currentPage etc.
            if total_pages is None:
                # If structure: widget.data.currentPage & widget.data.navigationPages etc
                tp = safe_get(widget, "data", "totalPages")
                if tp is not None:
                    total_pages = tp
        # Reviews widget
        if wtype == "REVIEWS" or wtype == "REVIEW_LIST" or wtype == "REVIEW":
            # expected shape: widget.data.renderableComponents -> list of review wrappers
            comps = safe_get(widget, "data", "renderableComponents") or safe_get(widget, "data", "renderableComponents") or []
            if not isinstance(comps, list):
                comps = []
            for c in comps:
                try:
                    val = c.get("value") or c.get("value", {})
                    # some structures nest value under 'value'
                    if not val:
                        val = safe_get(c, "value") or {}
                    # If the component itself contains 'value'->'value' weird doubling
                    if isinstance(val, dict) and "value" in val and isinstance(val["value"], dict):
                        val = val["value"]
                    # Pull fields safely:
                    author = val.get("author")
                    created = val.get("created")
                    helpful_count = val.get("helpfulCount") or val.get("totalCount") or 0
                    review_id = val.get("id")
                    text = val.get("text") or ""
                    title = val.get("title") or ""
                    rating = val.get("rating") or None
                    upvote = safe_get(val, "upvote", "value", "count") or safe_get(val, "upvote", "value", "count") or 0
                    downvote = safe_get(val, "downvote", "value", "count") or 0
                    loc_city = safe_get(val, "location", "city") or ""
                    images = val.get("images") or []
                    image_count = len(images)
                    # review url and image url
                    review_url = val.get("url")
                    # sometimes url doesn't include domain -> prefix domain
                    if review_url and review_url.startswith("/"):
                        review_url = "https://www.flipkart.com" + review_url
                    # first image if present:
                    review_image_url = ""
                    if images and isinstance(images, list) and len(images) > 0:
                        # images elements might contain value.imageURL with placeholders
                        img0 = images[0]
                        img_val = safe_get(img0, "value", "imageURL") or safe_get(img0, "value") or safe_get(img0, "imageURL") or None
                        if isinstance(img_val, str):
                            review_image_url = replace_image_placeholders(img_val)
                        else:
                            # sometimes nested: img0.value.imageURL
                            review_image_url = ""
                    # Compose review dict
                    review = {
                        "author": author,
                        "created_date": created,
                        "helpful_count": helpful_count,
                        "review_id": review_id,
                        "review_text": text,
                        "title": title,
                        "rating": rating,
                        "upvotes": upvote,
                        "downvotes": downvote,
                        "city": loc_city,
                        "image_count": image_count,
                        "review_url": review_url,
                        "review_image_url": review_image_url,
                        "raw_value": val
                    }
                    reviews.append(review)
                except Exception as e:
                    # skip malformed component but continue
                    print("[WARN] failed to parse review component:", e)
                    continue

    # Extra attempt: if no pagination widget found, look in RESPONSE.pageData.paginationContextMap or pageData->pageMeta or widgetFetch
    try:
        page_data = safe_get(resp_json, "RESPONSE", "pageData") or safe_get(resp_json, "RESPONSE", "pageMeta")
        if page_data and total_pages is None:
            total_pages = safe_get(page_data, "paginationContextMap", "totalPages") or safe_get(page_data, "page", "totalPages")
    except Exception:
        pass

    return reviews, (int(total_pages) if total_pages else None)


# ----------------- Main scraping loop -----------------
def scrape_reviews_for_product(product_url, writer, seen_ids):
    """
    Scrape all reviews for a single product and write to CSV via writer (csv.DictWriter).
    seen_ids is a set used to dedup across pages/products.
    """
    review_base = clean_product_url(product_url)
    if not review_base:
        print("[WARN] could not parse product url:", product_url)
        return 0

    print(f"Starting: {product_url}")
    print(f"Using review URL base: {review_base}")

    # We'll attempt to get product-level Company and Product name from page 1 response.
    company_name = ""
    product_name = ""
    total_written = 0

    # We'll track last_page if we get pagination info
    last_page_from_widget = None

    # Keep a small safety maximum absolute pages if nothing reported (avoid infinite loop). But will try to be generous (e.g. 300).
    ABS_MAX_PAGES = 500

    page = 1
    consecutive_empty_pages = 0
    MAX_CONSECUTIVE_EMPTY = 40  # user said there are sporadic empty pages; be tolerant
    while page <= ABS_MAX_PAGES:
        page_uri = build_page_uri(review_base, page)
        # build payload using fetchSeoData as you requested
        payload = {
            "pageUri": urlparse(page_uri).path + ("?" + urlparse(page_uri).query if urlparse(page_uri).query else ""),
            "pageContext": {"fetchSeoData": True}
        }
        # NOTE: Pay attention — you might need to throttle to avoid being blocked
        try:
            resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
        except Exception as e:
            print(f"[ERROR] request failed for page {page}: {e}. Retrying after 2s...")
            time.sleep(2)
            try:
                resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
            except Exception as e2:
                print(f"[ERROR] retry failed for page {page}: {e2}. Aborting this product.")
                break

        if resp.status_code != 200:
            print(f"[WARN] non-200 response for page {page}: {resp.status_code}")
            # attempt a short retry once
            time.sleep(1)
            if resp.status_code >= 500:
                # server error — retry
                continue
            else:
                # other client errors — break
                break

        try:
            j = resp.json()
        except Exception as e:
            print(f"[WARN] invalid json on page {page}: {e}")
            # save raw for debugging?
            # with open(f"debug_page_{page}.json", "w", encoding="utf-8") as fh:
            #     fh.write(resp.text)
            break

        # Extract reviews and pagination
        reviews, total_pages = extract_reviews_from_response(j, page_uri)
        if total_pages:
            last_page_from_widget = total_pages

        # If we haven't captured company/product name yet, try to extract from pageData
        if not company_name or not product_name:
            # try multiple places
            product_brand = safe_get(j, "RESPONSE", "pageData", "widget", "data", "value", "productBrand")
            titles = safe_get(j, "RESPONSE", "pageData", "widget", "data", "value", "titles")
            if not product_brand:
                product_brand = safe_get(j, "RESPONSE", "pageData", "pageContext", "tracking", "superTitle") \
                                or safe_get(j, "RESPONSE", "pageData", "pageContext", "tracking", "superTitle")
            if product_brand:
                company_name = product_brand
            if titles and isinstance(titles, dict):
                product_name = titles.get("title") or titles.get("newTitle") or product_name

        # If reviews found, reset consecutive_empty_pages, else increment
        if reviews:
            consecutive_empty_pages = 0
        else:
            # No reviews found on this page response
            consecutive_empty_pages += 1

        new_written_this_page = 0
        for r in reviews:
            rid = r.get("review_id")
            # skip if no id
            if not rid:
                # try deriving id from review_url
                rid = r.get("review_url") or None
            if not rid:
                # skip these - unreliable
                continue
            if rid in seen_ids:
                # duplicate => skip
                continue
            seen_ids.add(rid)
            # fill record
            rec = {
                "Company": company_name or "",
                "Product": product_name or "",
                "author": r.get("author") or "",
                "city": r.get("city") or "",
                "created_date": r.get("created_date") or "",
                "downvotes": r.get("downvotes") or 0,
                "flipkart_url": review_base,
                "helpful_count": r.get("helpful_count") or 0,
                "image_count": r.get("image_count") or 0,
                "rating": r.get("rating") or "",
                "review_id": rid,
                "review_text": (r.get("review_text") or "").replace("\n", " ").strip(),
                "title": r.get("title") or "",
                "upvotes": r.get("upvotes") or 0,
                "review_url": r.get("review_url") or "",
                "review_image_url": r.get("review_image_url") or ""
            }
            writer.writerow(rec)
            total_written += 1
            new_written_this_page += 1

        if new_written_this_page:
            print(f"[page {page}] Found {len(reviews)} reviews, wrote {new_written_this_page} new unique reviews.")
        else:
            print(f"[page {page}] Found {len(reviews)} reviews, no new unique reviews.")

        # If we have pagination total pages info, and we've reached last, break
        if last_page_from_widget:
            if page >= last_page_from_widget:
                print(f"[INFO] reached last page according to pagination widget: {last_page_from_widget}")
                break
        else:
            # No pagination info: use consecutive empty heuristic
            if consecutive_empty_pages >= MAX_CONSECUTIVE_EMPTY:
                print(f"[INFO] stopped after {consecutive_empty_pages} consecutive empty pages (no reviews).")
                break

        page += 1
        # be polite
        time.sleep(0.6)

    print(f"Finished scraping product. Unique reviews collected (so far): {total_written}")
    return total_written


# ----------------- Main entry -----------------
def main():
    # Read input CSV
    if not os.path.exists(INPUT_CSV):
        print(f"[ERROR] Input CSV '{INPUT_CSV}' not found. Put product URLs in this file (header 'url' or first column).")
        return

    urls = []
    with open(INPUT_CSV, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        # If header contains 'url', treat file as headered
        has_header_url = False
        if header:
            lc = [h.strip().lower() for h in header]
            if "url" in lc:
                has_header_url = True
                url_index = lc.index("url")
                # rewind isn't necessary — we will iterate remaining rows
            else:
                # treat header as first URL if it looks like URL
                if header and (header[0].startswith("http") or "flipkart" in header[0]):
                    urls.append(header[0])
        # read remaining
        for row in reader:
            if not row:
                continue
            if has_header_url:
                u = row[url_index].strip()
            else:
                u = row[0].strip()
            if u:
                urls.append(u)

    if not urls:
        print("[ERROR] No product URLs found in input CSV.")
        return

    print(f"Found {len(urls)} product URLs in input CSV.")

    # Prepare output CSV writer (append mode to be safe)
    write_header = not os.path.exists(OUTPUT_CSV)
    out_fh = open(OUTPUT_CSV, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_fh, fieldnames=OUTPUT_HEADERS)
    if write_header:
        writer.writeheader()

    seen_ids = set()
    total_all = 0
    for i, u in enumerate(urls, start=1):
        print(f"\n[{i}] Starting scraping for: {u}\n")
        try:
            written = scrape_reviews_for_product(u, writer, seen_ids)
            total_all += written
        except Exception as e:
            print(f"[ERROR] scraping product {u} failed: {e}")
        # flush to disk after each product
        out_fh.flush()
        # small delay between products
        time.sleep(1.0)

    out_fh.close()
    print(f"\nCompleted all products. Total unique reviews written: {total_all}")
    print(f"Output saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
