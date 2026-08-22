from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import db_ping

from app.catalog.router import router as catalog_router
from app.drawings.router import router as drawings_router
from app.e2e.router import router as e2e_router
from app.review.router import metrics_router as review_metrics_router
from app.review.router import router as review_router

settings = get_settings()

app = FastAPI(title="AEC Blueprint Intelligence System", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include catalog API router (Phase 2: spreadsheet import + material listing)
app.include_router(catalog_router)

# Include E2E pipeline router (Phase 2)
app.include_router(e2e_router)

# Include drawing quality gate router (Phase 2.5, spec v3 §7.2)
app.include_router(drawings_router)

# Include review-time instrumentation routers (Phase 2.5, spec v3 §7.13/§15)
app.include_router(review_router)
app.include_router(review_metrics_router)


@app.get("/")
def root() -> dict:
    return {"service": "aec-backend", "status": "ok"}


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "db": "ok" if db_ping() else "unavailable"}