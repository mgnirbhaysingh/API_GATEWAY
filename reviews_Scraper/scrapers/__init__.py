"""
Scrapers Package
Contains all scraper modules for Amazon and Flipkart

Available modules:
- amazon_reviews: Main Amazon review scraper with parallel processing
- amazon_review_counter: Get total review count for Amazon products
- amazon_advanced_scraper: Advanced scraper with keyword-based pagination bypass
- flipkart_product_reviews: Flipkart review scraper

Usage:
    from scrapers.amazon_reviews import fetch_reviews_ajax, get_csrf_token_from_page
    from scrapers.amazon_review_counter import get_total_review_count
    from scrapers.amazon_advanced_scraper import scrape_amazon_reviews_advanced
    from scrapers.flipkart_product_reviews import scrape_reviews_for_product
"""

__all__ = [
    'amazon_reviews',
    'amazon_review_counter',
    'amazon_advanced_scraper',
    'flipkart_product_reviews'
]
