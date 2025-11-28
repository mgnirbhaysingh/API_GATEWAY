from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.shopify import router as shopify_router
import uvicorn


app = FastAPI(title="Shopify API", version="1.0.0", docs_url="/", redoc_url=None)

# Optional: Allow local dev CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(shopify_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


