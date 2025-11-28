from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
import httpx
import os
import pandas as pd
from datetime import datetime
from typing import List, Any, Dict
import os
from dotenv import load_dotenv
load_dotenv()
# === Configuration ===
APIFY_TOKEN = os.getenv("APIFY_TOKEN")
ACTOR_SYNC_URL = (
    "https://api.apify.com/v2/acts/"
    "compass~google-maps-extractor/"
    f"run-sync-get-dataset-items?token={APIFY_TOKEN}"
)
CSV_DIR = "gmaps_results"
os.makedirs(CSV_DIR, exist_ok=True)


def to_table_format(items: List[Dict[str, Any]], metadata: Dict = None) -> Dict:
    """
    Convert list of dicts to standardized table format.

    Returns:
        {
            "headers": ["col1", "col2", ...],
            "rows": [["val1", "val2", ...], ...],
            "metadata": {}
        }
    """
    if not items:
        return {"headers": [], "rows": [], "metadata": metadata or {}}

    # Get all unique keys as headers
    headers = []
    for item in items:
        for key in item.keys():
            if key not in headers:
                headers.append(key)

    # Convert items to rows
    rows = []
    for item in items:
        row = []
        for header in headers:
            value = item.get(header, "")
            # Convert complex types to string
            if isinstance(value, (dict, list)):
                value = str(value)
            elif value is None:
                value = ""
            else:
                value = str(value)
            row.append(value)
        rows.append(row)

    return {
        "headers": headers,
        "rows": rows,
        "metadata": metadata or {}
    }


# === FastAPI app ===
app = FastAPI(
    title="Google Maps Extractor API",
    description="Extract Google Maps listings via Apify. Returns standardized table format.",
    version="1.0.0"
)

# === Single shared HTTP client ===
client = httpx.AsyncClient(timeout=300.0)


@app.get("/run-google-maps", summary="Run Google Maps extractor and return results")
async def run_google_maps(
    search: str = Query(..., description="Search term (e.g., 'polycab wires', 'restaurants')"),
    location: str = Query(..., description="Location to search in (e.g., 'Kozhikode', 'Mumbai')"),
    max_results: int = Query(100, description="Maximum number of places to crawl", ge=1, le=10000),
    language: str = Query("en", description="Language code (e.g., 'en', 'hi')"),
    skip_closed: bool = Query(False, description="Skip permanently closed places"),
    save_to_server: bool = Query(False, description="Also save CSV to server disk")
):
    """
    Search Google Maps for businesses/places.

    **Example:** `/run-google-maps?search=polycab wires&location=Kozhikode`

    **Returns standardized format:**
    ```json
    {
        "headers": ["title", "address", "phone", ...],
        "rows": [["Business 1", "123 Street", "+91...", ...], ...],
        "metadata": {"search": "...", "location": "...", "total_results": 100}
    }
    ```
    """
    # Build Apify payload
    apify_payload = {
        "language": language,
        "locationQuery": location,
        "maxCrawledPlacesPerSearch": max_results,
        "searchStringsArray": [search],
        "skipClosedPlaces": skip_closed
    }

    try:
        resp = await client.post(ACTOR_SYNC_URL, json=apify_payload)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Request to Apify failed: {str(e)}")

    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=f"Apify error: {resp.text}")

    try:
        items = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Invalid JSON from Apify: {e}")

    # Validate items is list
    if not isinstance(items, list):
        raise HTTPException(status_code=502, detail="Unexpected response format from Apify")

    # Build metadata
    metadata = {
        "search": search,
        "location": location,
        "total_results": len(items),
        "language": language,
        "timestamp": datetime.utcnow().isoformat()
    }

    # Save to server if requested
    if save_to_server and items:
        try:
            df = pd.DataFrame(items)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"gmaps_{location.replace(' ', '_')}_{ts}.csv"
            filepath = os.path.join(CSV_DIR, filename)
            df.to_csv(filepath, index=False, encoding="utf-8")
            metadata["saved_file"] = filename
        except Exception as e:
            metadata["save_error"] = str(e)

    # Return standardized format
    return to_table_format(items, metadata)


@app.get(
    "/download-csv/{filename}",
    summary="Download a previously saved CSV file",
    response_class=FileResponse
)
async def download_csv(filename: str):
    """
    Download a CSV file that was previously saved to the server.
    """
    filepath = os.path.join(CSV_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    return FileResponse(
        path=filepath,
        media_type="text/csv",
        filename=filename
    )


@app.get("/list-saved-files", summary="List all saved CSV files")
async def list_saved_files():
    """
    List all CSV files saved on the server.
    """
    files = []
    for f in os.listdir(CSV_DIR):
        if f.endswith('.csv'):
            filepath = os.path.join(CSV_DIR, f)
            files.append({
                "filename": f,
                "size_bytes": os.path.getsize(filepath),
                "created": datetime.fromtimestamp(os.path.getctime(filepath)).isoformat(),
                "download_url": f"/download-csv/{f}"
            })
    return {
        "headers": ["filename", "size_bytes", "created", "download_url"],
        "rows": [[f["filename"], str(f["size_bytes"]), f["created"], f["download_url"]] for f in files],
        "metadata": {"total_files": len(files)}
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
