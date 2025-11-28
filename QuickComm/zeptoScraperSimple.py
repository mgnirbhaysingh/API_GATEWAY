import asyncio
import time
import pandas as pd
import os
from playwright.async_api import async_playwright
from asyncio import Semaphore
from typing import List, Dict, Any


async def auto_scroll(page, max_scrolls=20):
    """Scroll down incrementally to trigger more results/pages."""
    await page.evaluate(f"""
        async () => {{
            let count = 0;
            while (count < {max_scrolls}) {{
                window.scrollBy(0, 500);
                await new Promise(r => setTimeout(r, 400));
                count++;
            }}
        }}
    """)


async def set_zepto_location(page, locality: str):
    """Open the location selector, enter locality, select first suggestion, and confirm location."""
    try:
        # Wait for page to load
        print("🔍 Looking for location button...")
        await page.wait_for_timeout(2000)

        # Try multiple selector strategies to find and click the location button
        clicked = False

        # Strategy 1: Click button by aria-label
        try:
            await page.wait_for_selector('button[aria-label="Select Location"]', timeout=5000)
            await page.click('button[aria-label="Select Location"]')
            print("✅ Clicked location button (aria-label)")
            clicked = True
        except Exception as e:
            print(f"⚠️ Strategy 1 failed: {e}")

        # Strategy 2: Click button containing the h3
        if not clicked:
            try:
                await page.wait_for_selector('h3[data-testid="user-address"]', timeout=5000)
                # Use JavaScript to click the parent button
                await page.evaluate('''() => {
                    const h3 = document.querySelector('h3[data-testid="user-address"]');
                    const button = h3.closest('button');
                    if (button) button.click();
                }''')
                print("✅ Clicked location button (parent button via JS)")
                clicked = True
            except Exception as e:
                print(f"⚠️ Strategy 2 failed: {e}")

        # Strategy 3: Direct force click on h3
        if not clicked:
            try:
                await page.click('h3[data-testid="user-address"]', force=True)
                print("✅ Clicked location h3 (force click)")
                clicked = True
            except Exception as e:
                print(f"⚠️ Strategy 3 failed: {e}")
                raise Exception("All click strategies failed")

        await page.wait_for_timeout(2000)

        await page.fill('input[placeholder="Search a new address"]', locality)
        print(f"✍️ Filled locality: {locality}")

        # Click the first suggestion
        await page.wait_for_selector('div[data-testid="address-search-item"]')
        await page.click('div[data-testid="address-search-item"]')
        print("📍 Selected first address suggestion")

        await page.wait_for_timeout(2000)

        await page.wait_for_selector('button[data-testid="location-confirm-btn"]')
        print("✅ Found confirm button")

        await page.click('button[data-testid="location-confirm-btn"]')
        print("👍 Location confirmed")

        await page.wait_for_timeout(3000)

    except Exception as e:
        print(f"[ERROR] Failed to set location: {e}")


async def fetch_zepto_search_for_queries(queries: list, locality: str, max_scrolls: int = 20):
    """Capture Zepto search API responses for multiple queries using the same browser context."""
    all_results = {}

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(
            headless=False,  # Set to True for production
            # proxy = {
            #     "server": "http://pr.oxylabs.io:7777",
            #     "username": "customer-MINDCASE_STm58-cc-IN",
            #     "password": "Mindcase+2024"
            # }
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        # Step 1: Open homepage
        print(f"\n🌍 Opening Zepto homepage for location: {locality}...")
        await page.goto("https://www.zeptonow.com", wait_until="domcontentloaded")

        # Step 2: Set location once
        await set_zepto_location(page, locality)

        # Process each query
        for query in queries:
            print(f"\n{'='*60}")
            print(f"Processing query: '{query}' at {locality}")
            print(f"{'='*60}")

            # Store results for current query
            captured_responses = []

            # Create handler that captures to the current query's list
            def create_handler(response_list):
                async def handle_response(resp):
                    # Updated URL pattern to match current Zepto API endpoint
                    if resp.request.method == "POST" and "api.zepto.com/api/v3/search" in resp.url:
                        try:
                            print(f"[DEBUG] Captured API response for {query}")
                            data = await resp.json()
                            response_list.append(data)
                        except Exception as e:
                            print(f"[DEBUG] Error parsing response: {e}")
                return handle_response

            # Set up the handler for this query
            handler = create_handler(captured_responses)
            page.on("response", handler)

            # Step 3: Search for current query
            search_url = f"https://www.zeptonow.com/search?query={query.replace(' ', '+')}"
            print(f"🔎 Navigating to: {search_url}")

            # Navigate and wait for initial load
            await page.goto(search_url, wait_until="domcontentloaded")

            # Wait for search results to appear
            try:
                await page.wait_for_selector('[data-testid="product-card"]', timeout=10000)
                print(f"✅ Search results loaded for '{query}'")
            except:
                print(f"⚠️ No search results found for '{query}', continuing...")

            # Step 4: Trigger pagination to load more results
            print(f"📜 Scrolling to load more results...")
            await auto_scroll(page, max_scrolls=max_scrolls)

            # Wait for any pending API calls to complete
            await page.wait_for_timeout(3000)

            # Remove the handler after capturing
            page.remove_listener("response", handler)

            all_results[query] = captured_responses
            print(f"✅ Captured {len(captured_responses)} API responses for '{query}'")

            # Small delay between queries
            await asyncio.sleep(1)

        await browser.close()

    return all_results


def extract_zepto_data(results, current_query, locality):
    """
    Flatten Zepto search JSON responses into structured rows.
    """
    rows = []

    # Handle None or empty results
    if not results:
        return rows

    for response in results or []:
        if not response or not isinstance(response, dict):
            continue
        layouts = response.get("layout")
        if not layouts or not isinstance(layouts, list):
            continue
        for layout in layouts:
            if not layout or not isinstance(layout, dict):
                continue
            if layout.get("widgetId") == "PRODUCT_GRID":
                data = layout.get("data")
                if not data or not isinstance(data, dict):
                    continue
                resolver = data.get("resolver")
                if not resolver or not isinstance(resolver, dict):
                    continue
                resolver_data = resolver.get("data")
                if not resolver_data or not isinstance(resolver_data, dict):
                    continue
                items = resolver_data.get("items", [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    try:
                        if not item or not isinstance(item, dict):
                            continue
                        product_resp = item.get("productResponse", {}) or {}
                        product = product_resp.get("product", {}) or {}
                        variant = product_resp.get("productVariant", {}) or {}

                        images = variant.get("images", []) or product.get("images", []) or []
                        image_urls = [img.get("path") for img in images if img.get("path")]

                        row = {
                            "platform" : "Zepto",
                            "product_id": product.get("id"),
                            "variant_id": variant.get("id"),
                            "name": product.get("name"),
                            "brand": product.get("brand"),
                            "mrp": product_resp.get("mrp"),
                            "price": product_resp.get("sellingPrice"),
                            "quantity": variant.get("formattedPacksize") or "",
                            "in_stock": not product_resp.get("outOfStock", False),
                            "inventory": product_resp.get("availableQuantity"),
                            "max_allowed_quantity": variant.get("maxAllowedQuantity"),
                            "category": product_resp.get("primaryCategoryName"),
                            "sub_category": product_resp.get("primarySubcategoryName"),
                            "images": ", ".join(image_urls),
                            "organic_rank": item.get("position"),
                            "weightInGrams" : product_resp.get("packskze"),
                            "shortDescription" : product.get("description"),
                            "store_id": product_resp.get("storeId"), 
                            "search_query": current_query,   
                            "locality": locality,
                        }

                        rows.append(row)

                    except Exception as e:
                        print(f"[ERROR] Skipped product due to exception: {e}")
                        continue

    return rows


async def fetch_zepto_parallel_worker(semaphore: Semaphore, queries: list, locality: str, max_scrolls: int = 15):
    """Worker function for parallel processing with semaphore control"""
    async with semaphore:  # Limit concurrent browsers
        try:
            print(f"[PARALLEL] Starting worker for {locality}")
            results = await fetch_zepto_search_for_queries(queries, locality, max_scrolls)
            print(f"[PARALLEL] Completed worker for {locality}")
            return locality, results
        except Exception as e:
            print(f"[PARALLEL ERROR] Failed to process {locality}: {e}")
            return locality, {}


async def process_locations_parallel(zepto_df: pd.DataFrame, queries: list, output_csv: str,
                                    max_concurrent: int = 5, start_row: int = 1):
    """Process multiple locations in parallel with controlled concurrency"""

    semaphore = Semaphore(max_concurrent)
    write_header = not os.path.exists(output_csv)

    if start_row > 1 and not os.path.exists(output_csv):
        print(f"WARNING: Starting from row {start_row} but output CSV doesn't exist yet.")
        print(f"Creating new file with headers.")
    elif start_row > 1 and os.path.exists(output_csv):
        print(f"Appending to existing CSV: {output_csv}")

    total_products = 0
    batch_size = max_concurrent * 2  # Process 2x semaphore size at a time

    # Create batches of locations to process
    locations = []
    for idx, row in zepto_df.iterrows():
        locality = row['locality']
        if pd.isna(locality) or locality == '':
            continue
        locations.append(locality)

    print(f"\n[PARALLEL MODE] Processing {len(locations)} locations with {max_concurrent} concurrent browsers")

    # Process in batches
    for batch_start in range(0, len(locations), batch_size):
        batch_end = min(batch_start + batch_size, len(locations))
        batch = locations[batch_start:batch_end]

        current_start = start_row + batch_start
        current_end = start_row + batch_end - 1

        print(f"\n{'='*80}")
        print(f"[BATCH] Processing locations {current_start} to {current_end}")
        print(f"{'='*80}")

        # Create tasks for this batch
        tasks = []
        for locality in batch:
            task = fetch_zepto_parallel_worker(semaphore, queries, locality, max_scrolls=15)
            tasks.append(task)

        # Execute all tasks in parallel (with exception handling)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and save to CSV
        batch_rows = []
        for result in results:
            # Handle exceptions from gather
            if isinstance(result, Exception):
                print(f"[ERROR] Task failed with exception: {result}")
                continue

            locality, results_dict = result
            if not results_dict:
                print(f"[{locality}] No results returned (might have failed)")
                continue
            for query, query_results in results_dict.items():
                rows = extract_zepto_data(query_results, query, locality)
                batch_rows.extend(rows)
                print(f"[{locality}] Extracted {len(rows)} products for '{query}'")

        # Write batch results to CSV
        if batch_rows:
            df = pd.DataFrame(batch_rows)

            if write_header:
                df.to_csv(output_csv, mode='w', index=False, encoding="utf-8", header=True)
                write_header = False
                print(f"✅ Created {output_csv} and saved {len(batch_rows)} products")
            else:
                df.to_csv(output_csv, mode='a', index=False, encoding="utf-8", header=False)
                print(f"✅ Appended {len(batch_rows)} products to {output_csv}")

            total_products += len(batch_rows)
            print(f"Total products so far: {total_products}")

        # Small delay between batches to avoid overwhelming the system
        if batch_end < len(locations):
            print("Waiting 2 seconds before next batch...")
            await asyncio.sleep(2)

    print(f"\n{'='*80}")
    print(f"[PARALLEL] COMPLETED! Total products extracted: {total_products}")
    print(f"Results saved to: {output_csv}")
    print(f"{'='*80}")


# ---------------- MAIN ----------------
if __name__ == "__main__":
    # ===== CONFIGURATION =====
    START_ROW = 1  # Start from this row number (1-indexed) of Zepto-filtered rows. Set to 1 to start from beginning
    DELAY_BETWEEN_LOCATIONS = 0.5  # Delay in seconds between processing locations (sequential mode only)
    PARALLEL = True  # Set to True for parallel processing, False for sequential
    MAX_CONCURRENT = 5  # Maximum concurrent browser contexts when PARALLEL=True (keep low for browser stability)
    # =========================

    # Define queries to search - matching other scrapers
    queries = ["Coffee", "Chips", "Chocolates", "Oil", "Chicken", "Handwash", "Petfood", "Charger", "Protein", "Stationery", "Sunscreen"]

    # Load the stores data - assuming your CSV has a 'locality' column
    stores_df = pd.read_csv("combined_store_with_locality.csv")

    # Filter for Zepto stores only
    zepto_df = stores_df[stores_df['platform'] == 'Zepto'].copy()

    # Remove duplicates based on locality to avoid processing same location multiple times
    zepto_df = zepto_df.drop_duplicates(subset=['locality'])

    print(f"Found {len(zepto_df)} unique Zepto locations to process")

    # Apply START_ROW logic
    if START_ROW > 1:
        if START_ROW > len(zepto_df):
            print(f"ERROR: START_ROW ({START_ROW}) is greater than total Zepto locations ({len(zepto_df)})")
            exit(1)
        zepto_df = zepto_df.iloc[START_ROW - 1:]  # Use iloc for proper indexing
        print(f"Starting from row {START_ROW} of Zepto locations")
        print(f"Will process {len(zepto_df)} locations (rows {START_ROW} to {START_ROW + len(zepto_df) - 1})")

    print(f"Will search for queries: {queries}")
    print(f"Mode: {'PARALLEL' if PARALLEL else 'SEQUENTIAL'}")
    if PARALLEL:
        print(f"Max Concurrent Browsers: {MAX_CONCURRENT}")
    else:
        print(f"Delay between locations: {DELAY_BETWEEN_LOCATIONS}s")

    # Output CSV file
    output_csv = "30_September_zepto_products_all_locations_evening.csv"

    # Run in parallel or sequential mode
    if PARALLEL:
        print("\n🚀 Starting PARALLEL with multiple browsers...")
        asyncio.run(process_locations_parallel(
            zepto_df=zepto_df,
            queries=queries,
            output_csv=output_csv,
            max_concurrent=MAX_CONCURRENT,
            start_row=START_ROW
        ))
    else:
        print("\n📝 Starting SEQUENTIAL processing...")

        # Check if file exists to determine if we need to write headers
        # When START_ROW > 1, we should always append (never overwrite)
        write_header = not os.path.exists(output_csv)

        if START_ROW > 1 and not os.path.exists(output_csv):
            print(f"WARNING: Starting from row {START_ROW} but output CSV doesn't exist yet.")
            print(f"Creating new file with headers.")
        elif START_ROW > 1 and os.path.exists(output_csv):
            print(f"Appending to existing CSV: {output_csv}")

        # Track total products for reporting
        total_products = 0

        # Process each Zepto location
        for counter, (idx, row) in enumerate(zepto_df.iterrows(), START_ROW):
            locality = row['locality']

            if pd.isna(locality) or locality == '':
                print(f"Skipping location {counter}/{START_ROW + len(zepto_df) - 1} with no locality")
                continue

            print(f"\n{'='*80}")
            print(f"Processing location {counter}/{START_ROW + len(zepto_df) - 1}: {locality}")
            print(f"{'='*80}")

            try:
                # Fetch results for all queries at this location
                results_dict = asyncio.run(fetch_zepto_search_for_queries(queries, locality, max_scrolls=15))

                # Store rows for this location
                location_rows = []

                # Extract data for each query
                for query, results in results_dict.items():
                    rows = extract_zepto_data(results, query, locality)
                    location_rows.extend(rows)
                    print(f"Extracted {len(rows)} products for '{query}'")

                # Append to CSV after processing all queries for this location
                if location_rows:
                    df = pd.DataFrame(location_rows)

                    # Write header only if file doesn't exist
                    if write_header:
                        df.to_csv(output_csv, mode='w', index=False, encoding="utf-8", header=True)
                        write_header = False  # Don't write header again
                        print(f"✅ Created {output_csv} and saved {len(location_rows)} products for {locality}")
                    else:
                        df.to_csv(output_csv, mode='a', index=False, encoding="utf-8", header=False)
                        print(f"✅ Appended {len(location_rows)} products for {locality} to {output_csv}")

                    total_products += len(location_rows)
                    print(f"Total products so far: {total_products}")
                else:
                    print(f"⚠️ No products found for {locality}")

                # Add delay between locations to avoid rate limiting
                if counter < len(zepto_df):
                    print(f"Waiting {DELAY_BETWEEN_LOCATIONS} seconds before next location...")
                    time.sleep(DELAY_BETWEEN_LOCATIONS)

            except Exception as e:
                print(f"[ERROR] Failed to process location {locality}: {e}")
                continue

        print(f"\n{'='*80}")
        print(f"COMPLETED! Total products extracted: {total_products}")
        print(f"Locations processed: {len(zepto_df)}")
        print(f"Results saved to: {output_csv}")
        print(f"{'='*80}")