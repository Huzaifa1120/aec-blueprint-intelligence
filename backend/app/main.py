from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import db_ping

from app.catalog.router import router as catalog_router

settings = get_settings()

app = FastAPI(title="AEC Blueprint Intelligence System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include catalog API router (Phase 2: spreadsheet import + material listing)
app.include_router(catalog_router, prefix="/api/catalog", tags=["catalog"])


@app.get("/")
def root() -> dict:
    return {"service": "aec-backend", "status": "ok"}


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "db": "ok" if db_ping() else "unavailable"}