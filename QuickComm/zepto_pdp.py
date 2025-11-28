#!/usr/bin/env python3
"""
Replicates the given Zepto product cURL request.
Downloads the HTML for the product:
'Tide Plus Jasmine Rose Detergent Powder'
and saves it to 'zepto_tide.html'.
"""

import requests
from pathlib import Path

# ======================================================
# 🌐 Target URL
# ======================================================
url = (
    "https://www.zeptonow.com/pn/"
    "tide-plus-jasmine-rose-detergent-powder/"
    "pvid/72320d9c-f67f-4f87-9643-1f3f147d7f7f"
)

# ======================================================
# 🧾 Headers (copied from cURL)
# ======================================================
headers = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "en-GB,en;q=0.8",
    "cache-control": "max-age=0",
    "priority": "u=0, i",
    "sec-ch-ua": '"Brave";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "sec-gpc": "1",
    "upgrade-insecure-requests": "1",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/141.0.0.0 Safari/537.36"
    ),
}

# ======================================================
# 🍪 Cookies (exact from your cURL)
# ======================================================
cookies = {
    "device_id": "",
    "marketplace": "SUPER_SAVER",
    "pwa": "false",
    "_fbp": "fb.1.1762407594653.616184555635580323",
    "unique_browser_id": "3345307054313141",
    "user_position": '',
    "latitude": "26.7836657",
    "longitude": "80.9357697",
    "session_id": "",
    "session_count": "3",
    "prev_store_id": "913cea7d-879a-46d4-a31d-375e6272a237",
    "serviceability": (
        '{"primaryStore":{"serviceable":true,"storeId":"913cea7d-879a-46d4-a31d-375e6272a237"'
    ),
    "csrfSecret": "izLvnPzrcUo",
    "XSRF-TOKEN": (
        "gB7L180Zf3ME9PliiOgAh:sRvHi-N39mHoHMUCxmJRdKW8Ygs."
        "Ry3H4DdQZ/3rJ6pQHxVu2nK233wdX569y2GgnzHUUcI"
    ),
}

# ======================================================
# 🚀 Send the GET request
# ======================================================
try:
    print(f"📡 Fetching Zepto product page:\n{url}\n")
    resp = requests.get(url, headers=headers, cookies=cookies, timeout=30)

    # Ensure response was successful
    resp.raise_for_status()

    # Save the HTML response
    output_file = Path("zepto_tide.html")
    output_file.write_text(resp.text, encoding="utf-8")

    # Print diagnostics
    print(f"✅ Saved HTML to: {output_file.resolve()}")
    print(f"🌐 HTTP Status Code: {resp.status_code}")
    print(f"📦 File Size: {output_file.stat().st_size} bytes\n")
    print("🔍 Preview (first 400 chars):\n")
    print(resp.text[:400])

except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")