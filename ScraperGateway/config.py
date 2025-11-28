"""
Configuration for the Universal Scraper Gateway.
Defines backend services and their routing rules.
"""

from dataclasses import dataclass
from typing import List
import os


@dataclass
class ServiceConfig:
    """Configuration for a backend service."""
    name: str
    display_name: str
    host: str
    port: int
    health_endpoint: str
    path_prefix: str  # Gateway prefix (e.g., /ecommerce)
    backend_prefix: str  # Backend's actual prefix (e.g., "" or "/api/v1")

    @property
    def base_url(self) -> str:
        return f"{self.host}:{self.port}"


# Backend service configurations
SERVICES = {
    "quickcomm": ServiceConfig(
        name="quickcomm",
        display_name="QuickComm E-commerce Search",
        host="http://127.0.0.1",
        port=int(os.getenv("QUICKCOMM_PORT", "8001")),
        health_endpoint="/health",
        path_prefix="/ecommerce",
        backend_prefix="",  # Routes are at root (e.g., /amazon/search)
    ),
    "shopify": ServiceConfig(
        name="shopify",
        display_name="Shopify Scraper",
        host="http://127.0.0.1",
        port=int(os.getenv("SHOPIFY_PORT", "8002")),
        health_endpoint="/health",
        path_prefix="/shopify",
        backend_prefix="/shopify",  # Routes already have /shopify prefix
    ),
    "reviews": ServiceConfig(
        name="reviews",
        display_name="Reviews Scraper",
        host="http://127.0.0.1",
        port=int(os.getenv("REVIEWS_PORT", "8003")),
        health_endpoint="/health",
        path_prefix="/reviews",
        backend_prefix="/api/v1",  # Routes are under /api/v1
    ),
    "googlemaps": ServiceConfig(
        name="googlemaps",
        display_name="Google Maps Scraper",
        host="http://127.0.0.1",
        port=int(os.getenv("GOOGLEMAPS_PORT", "8004")),
        health_endpoint="/health",
        path_prefix="/maps",
        backend_prefix="",  # Routes are at root
    ),
}

# Gateway settings
GATEWAY_HOST = os.getenv("GATEWAY_HOST", "0.0.0.0")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8080"))

# Request settings
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "120.0"))
CONNECT_TIMEOUT = float(os.getenv("CONNECT_TIMEOUT", "10.0"))
