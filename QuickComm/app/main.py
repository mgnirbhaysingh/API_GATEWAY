from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
import uuid

from .api import (
    search_blinkit,
    search_blinkitOxy,
    search_instamart,
    search_zepto,
    search_amazon,
    search_flipkart,
    search_jiomart,
    search_all,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(docs_url="/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_blinkit.router)
app.include_router(search_blinkitOxy.router)
app.include_router(search_instamart.router)
app.include_router(search_zepto.router)
app.include_router(search_amazon.router)
app.include_router(search_flipkart.router)
app.include_router(search_jiomart.router)
app.include_router(search_all.router)


@app.get("/health")
async def health():
    """Health check endpoint for the gateway."""
    return {"status": "ok", "service": "quickcomm"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
