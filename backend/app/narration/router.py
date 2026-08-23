"""Narration API — narrated scope of work for a persisted estimate (G8).

Loads the persisted BOQ via the shared payload builder
(``app.estimates.payload.payload_from_estimate`` — same row shape as
``GET /api/estimates/{id}/boq``: ``routes`` / ``materials`` / ``totals``),
then hands it to a narrator provider. Template fallback fires on ANY
provider exception, logged once.

The router only formats structured numbers verbatim downstream: it copies
values from the ORM rows without arithmetic.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as OrmSession

from app.db.models.estimate import Estimate
from app.db.session import get_db
from app.estimates.payload import payload_from_estimate
from app.narration.providers import (
    NarrationResult,
    TemplateNarrator,
    get_provider,
    verify_no_invented_numbers,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/narration", tags=["narration"])

_fallback_logged = False


@router.get("/estimates/{estimate_id}", summary="Narrated scope of work for an estimate")
def narrate_estimate(estimate_id: uuid.UUID, db: OrmSession = Depends(get_db)) -> dict:
    estimate = db.get(Estimate, estimate_id)
    if estimate is None:
        raise HTTPException(status_code=404, detail="estimate not found")

    payload = payload_from_estimate(estimate)

    global _fallback_logged
    provider = get_provider()
    try:
        result: NarrationResult = provider.narrate(payload)
        # Runtime numeric enforcement — prompt compliance is never trusted.
        verify_no_invented_numbers(result["narrative"], payload)
    except Exception:
        if not _fallback_logged:
            logger.warning(
                "narration provider %s failed verbatimism gate; falling back to template",
                getattr(provider, "name", "?"),
                exc_info=True,
            )
            _fallback_logged = True
        result = TemplateNarrator().narrate(payload)

    return {
        "estimate_id": str(estimate.id),
        "provider": result["provider"],
        "narrative": result["narrative"],
    }
