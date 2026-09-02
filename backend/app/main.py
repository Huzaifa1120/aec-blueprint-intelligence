from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.session import db_ping
from app.jobs.queue import get_job_queue
from app.e2e.router import run_e2e_job

from app.catalog.router import router as catalog_router
from app.drawings.router import router as drawings_router
from app.e2e.router import router as e2e_router
from app.estimates.router import router as estimates_router
from app.exports.router import router as exports_router
from app.jobs.router import jobs_router
from app.narration.router import router as narration_router
from app.review.router import metrics_router as review_metrics_router
from app.review.router import router as review_router


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: wire the job queue runner and include jobs router
    get_job_queue().set_runner(run_e2e_job)
    yield
    # Shutdown: nothing to clean up for in-memory queue


app = FastAPI(
    title="AEC Blueprint Intelligence System",
    version="0.1.0",
    lifespan=lifespan,
)

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

# Include job status polling router (Task 2: async E2E)
app.include_router(jobs_router)

# Include review-time instrumentation routers (Phase 2.5, spec v3 §7.13/§15)
app.include_router(review_router)
app.include_router(review_metrics_router)

# Include estimates read API + replay gate (v3 conformance G1)
app.include_router(estimates_router)

# Include BOQ exports (JSON/XLSX/PDF) and narrated scope of work (G7/G8)
app.include_router(exports_router)
app.include_router(narration_router)


@app.get("/")
def root() -> dict:
    return {"service": "aec-backend", "status": "ok"}


@app.get("/health")
def health() -> dict:
    return {"status": "healthy", "db": "ok" if db_ping() else "unavailable"}