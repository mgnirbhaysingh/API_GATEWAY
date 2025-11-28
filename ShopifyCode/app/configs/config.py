from urllib.parse import urlparse

HEADERS = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en-US,en;q=0.6',
    'cache-control': 'no-cache',
    'sec-ch-ua': '"Not;A=Brand";v="99", "Brave";v="139", "Chromium";v="139"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/139.0.0.0 Mobile Safari/537.36',
    'x-requested-with': 'XMLHttpRequest'
}

COOKIES = {
    'localization': 'IN',
    '_shopify_y': '88e6b743-5714-4595-a9bf-a1fe00995fdd',
    '_shopify_s': '7ea43a4d-2d9b-4e66-b5d5-f5a25c6f08a5',
    '_tracking_consent': '3s.AMP_INUP_f_f_vjkP-rd-QV-RiLlnp9EC6w',
    '_orig_referrer': '',
    '_landing_page': '%2Fproducts%2Fhachi-patola-silk-patchwork-reversible-quilted-jacket%3Fvariant%3D44527952298028',
    'shopify_recently_viewed': 'brooke-french-riviera-hand-woven-cotton-patchwork-dress%20hadrey-patola-silk-patchwork-kantha-long-jacket%20tia-taffeta-trove-patola-silk-patchwork-top-and-trouser-set%20maple-mondrian-hand-woven-cotton-derby-dress%20hachi-patola-silk-patchwork-reversible-quilted-jacket%20beverly-french-riviera-hand-woven-cotton-patchwork-dress%20deanna-festive-flamboyance-brocade-dress%20alarina-shibori-shabang-quilted-bedcover-set',
    'keep_alive': 'eyJ2IjoyLCJ0cyI6MTc1NjM2NzIyNDc4MSwiZW52Ijp7IndkIjowLCJ1YSI6MSwiY3YiOjEsImJyIjoxfSwiYmh2Ijp7Im1hIjoxLCJjYSI6Miwia2EiOjAsInNhIjoxMSwia2JhIjowLCJ0YSI6MSwidCI6MzYwMCwibm0iOjAsIm1zIjowLCJtaiI6MCwibXNwIjowLCJ2YyI6MCwiY3AiOjAuMDksInJjIjowLCJraiI6MCwia2kiOjAsInNzIjowLjc3LCJzaiI6MC42Miwic3NtIjowLjgxLCJzcCI6MiwidHMiOjAsInRqIjowLCJ0cCI6MCwidHNtIjowfSwic2VzIjp7InAiOjUsInMiOjE3NTYzNTg3MTQwMzYsImQiOjgzODJ9fQ%3D%3D',
    '_shopify_essential': ':AZjvIxpEAAEAwiu2H_G6lkjcPgTO_5rlRordhh7xIVhDgHcvdZ8yGZo4lptxCTZv1em8_XPvxXJiZFVBwFQR8Iok_G0_MThApfdVjg:'
}

DOCHEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "en-GB,en;q=0.8",
    "cache-control": "max-age=0",
    "cookie": "localization=IN; _shopify_y=3bdc672b-5c47-47a0-87db-260289ab7096; _tracking_consent=3s.AMP_INUP_f_f_6413Xr-fQ4ivcHusv7Nokw; _orig_referrer=; _landing_page=%2Fproducts%2Fpure-shirt%3Fvariant%3D50771198771482.0; _shopify_essential=:AZkUYTNnAAEA0dWnAL_GAyKVG9AN6Bv96axwqF1qNUmRWJ9TlrHB3cQR3MZAMtRTgXou0V9GlURFU7nYUDqSKi6_Lrz-zmK5YAs1m6T0nTxDRb0mjWRo5w:; _shopify_s=23b5e1b1-3bcd-4f70-aceb-045769a30539; keep_alive=eyJ2IjoyLCJ0cyI6MTc1Njk4NDUzMzI4MCwiZW52Ijp7IndkIjowLCJ1YSI6MSwiY3YiOjEsImJyIjoxfSwiYmh2Ijp7Im1hIjo5LCJjYSI6MCwia2EiOjAsInNhIjowLCJrYmEiOjAsInRhIjowLCJ0IjoyMzAsIm5tIjoxLCJtcyI6MC4xNCwibWoiOjAuNywibXNwIjowLjQ5LCJ2YyI6MCwiY3AiOjAsInJjIjowLCJraiI6MCwia2kiOjAsInNzIjowLCJzaiI6MCwic3NtIjowLCJzcCI6MCwidHMiOjAsInRqIjowLCJ0cCI6MCwidHNtIjowfSwic2VzIjp7InAiOjMsInMiOjE3NTY5ODM1Mzk0OTAsImQiOjk1NX19",
    "if-none-match": "\"cacheable:c16663777da2b135dae59f4af703facc\"",
    "priority": "u=0, i",
    "sec-ch-ua": "\"Not;A=Brand\";v=\"99\", \"Brave\";v=\"139\", \"Chromium\";v=\"139\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"macOS\"",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "sec-gpc": "1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
}


DOCCOOKIES = {
    "localization": "IN",
    "_shopify_y": "3bdc672b-5c47-47a0-87db-260289ab7096",
    "_tracking_consent": "3s.AMP_INUP_f_f_6413Xr-fQ4ivcHusv7Nokw",
    "_orig_referrer": "",
    "_landing_page": "%2Fproducts%2Fpure-shirt%3Fvariant%3D50771198771482.0",
    "_shopify_essential": ":AZkUYTNnAAEA0dWnAL_GAyKVG9AN6Bv96axwqF1qNUmRWJ9TlrHB3cQR3MZAMtRTgXou0V9GlURFU7nYUDqSKi6_Lrz-zmK5YAs1m6T0nTxDRb0mjWRo5w:",
    "_shopify_s": "23b5e1b1-3bcd-4f70-aceb-045769a30539",
    "keep_alive": "eyJ2IjoyLCJ0cyI6MTc1Njk4NDUzMzI4MCwiZW52Ijp7IndkIjowLCJ1YSI6MSwiY3YiOjEsImJyIjoxfSwiYmh2Ijp7Im1hIjo5LCJjYSI6MCwia2EiOjAsInNhIjowLCJrYmEiOjAsInRhIjowLCJ0IjoyMzAsIm5tIjoxLCJtcyI6MC4xNCwibWoiOjAuNywibXNwIjowLjQ5LCJ2YyI6MCwiY3AiOjAsInJjIjowLCJraiI6MCwia2kiOjAsInNzIjowLCJzaiI6MCwic3NtIjowLCJzcCI6MCwidHMiOjAsInRqIjowLCJ0cCI6MCwidHNtIjowfSwic2VzIjp7InAiOjMsInMiOjE3NTY5ODM1Mzk0OTAsImQiOjk1NX19",
}



def extract_brand_name_from_url(url: str) -> str:
    """Extract brand name from product URL"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove www. if present
        if domain.startswith('www.'):
            domain = domain[4:]
            
        # Extract brand name from domain
        if 'karmadori' in domain:
            return 'Karmadori'
        elif 'wastedwrld' in domain:
            return 'Wasted Wrld'
        elif 'dioza' in domain:
            return 'Dioza'
        else:
            # Generic extraction - take first part before .com/.in etc
            brand = domain.split('.')[0]
            return brand.title()
    except:
        return 'Unknown'

def get_base_url(url):
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return base_url 





        

    