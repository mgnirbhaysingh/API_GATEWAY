import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from .search_instamart import search_instamart
from .search_zepto import search_zepto
from .search_blinkit import search_blinkit
from .search_amazon import search_amazon
from .search_flipkart import search_flipkart
from .search_jiomart import search_jiomart

router = APIRouter()

# Thread pool for running sync functions
executor = ThreadPoolExecutor(max_workers=10)


class SearchParams(BaseModel):
    queries: List[str] = Field(..., description="List of search queries to execute")
    instamart_store_ids: List[str] = Field(default=[], description="List of Instamart store IDs to search in")
    zepto_store_ids: List[str] = Field(default=[], description="List of Zepto store IDs to search in")
    blinkit_coordinates: List[str] = Field(default=[], description="List of Blinkit coordinates as 'lat,lon' strings")
    amazon_pincodes: List[str] = Field(default=[], description="List of Amazon PIN codes")
    flipkart_pincodes: List[str] = Field(default=[], description="List of Flipkart PIN codes")
    jiomart_pincodes: List[str] = Field(default=[], description="List of JioMart PIN codes")
    save_to_db: bool = Field(False, description="Whether to save search results to the database")


class SearchResult(BaseModel):
    platform: str
    query: str
    store: Optional[str] = None
    products: List[Dict[str, Any]]


async def run_sync_in_thread(func, *args, **kwargs):
    """Run a synchronous function in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))


async def create_platform_result(platform: str, query: str, store: str = None, save_to_db: bool = False) -> SearchResult:
    try:
        products = []

        if platform == "instamart":
            products = await run_sync_in_thread(search_instamart, query=query, store_id=store, save_to_db=save_to_db)
        elif platform == "zepto":
            products = await run_sync_in_thread(search_zepto, query=query, store_id=store, save_to_db=save_to_db)
        elif platform == "blinkit":
            products = await run_sync_in_thread(search_blinkit, query=query, coordinates=store, save_to_db=save_to_db)
        elif platform == "amazon":
            products = await run_sync_in_thread(search_amazon, query=query, pincode=store, save_to_db=save_to_db)
        elif platform == "flipkart":
            products = await run_sync_in_thread(search_flipkart, query=query, pincode=store, save_to_db=save_to_db)
        elif platform == "jiomart":
            products = await run_sync_in_thread(search_jiomart, query=query, pincode=store, save_to_db=save_to_db)
        else:
            raise ValueError(f"Unknown platform: {platform}")

        return SearchResult(
            platform=platform,
            query=query,
            store=store,
            products=products
        )

    except Exception as e:
        print(f"Error in {platform} search for query '{query}', location '{store}': {str(e)}")

        return SearchResult(
            platform=platform,
            query=query,
            store=store,
            products=[]
        )


@router.post("/search/all", response_model=List[SearchResult])
async def search_all_platforms(search_params: SearchParams) -> List[SearchResult]:
    """
    Search across all platforms concurrently.

    Supports: Instamart, Zepto, Blinkit, Amazon, Flipkart, JioMart
    """
    all_results = []
    tasks = []

    for query in search_params.queries:
        # Instamart
        for store_id in search_params.instamart_store_ids:
            tasks.append(create_platform_result("instamart", query, store=store_id, save_to_db=search_params.save_to_db))

        # Zepto
        for store_id in search_params.zepto_store_ids:
            tasks.append(create_platform_result("zepto", query, store=store_id, save_to_db=search_params.save_to_db))

        # Blinkit
        for coords in search_params.blinkit_coordinates:
            tasks.append(create_platform_result("blinkit", query, store=coords, save_to_db=search_params.save_to_db))

        # Amazon
        for pincode in search_params.amazon_pincodes:
            tasks.append(create_platform_result("amazon", query, store=pincode, save_to_db=search_params.save_to_db))

        # Flipkart
        for pincode in search_params.flipkart_pincodes:
            tasks.append(create_platform_result("flipkart", query, store=pincode, save_to_db=search_params.save_to_db))

        # JioMart
        for pincode in search_params.jiomart_pincodes:
            tasks.append(create_platform_result("jiomart", query, store=pincode, save_to_db=search_params.save_to_db))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if not isinstance(result, Exception):
            all_results.append(result)

    return all_results