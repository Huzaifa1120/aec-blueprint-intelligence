"""Exports API — download a persisted estimate's BOQ as JSON/XLSX/PDF (G7).

Loads the persisted estimate via the shared payload builder
(``app.estimates.payload.payload_from_estimate`` — the documented
``GET /api/estimates/{id}/boq`` payload shape) and hands that dict to the
selected writer (``render(rows) -> bytes``). Values are copied verbatim from
persisted rows — no arithmetic happens here.
"""

from __future__ import annotations

import io
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as OrmSession

from app.db.models.estimate import Estimate
from app.db.session import get_db
from app.estimates.payload import payload_from_estimate
from app.exports import json_export, pdf_export, xlsx_export

router = APIRouter(prefix="/api/exports", tags=["exports"])

_WRITERS = {
    "json": (json_export.render, "application/json", "boq.json"),
    "xlsx": (
        xlsx_export.render,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "boq.xlsx",
    ),
    "pdf": (pdf_export.render, "application/pdf", "boq.pdf"),
}

Format = Literal["json", "xlsx", "pdf"]


@router.get(
    "/estimates/{estimate_id}/export",
    summary="Download a persisted estimate's BOQ as JSON, XLSX or PDF",
)
def export_estimate(
    estimate_id: uuid.UUID,
    format: Format = "json",
    db: OrmSession = Depends(get_db),
) -> StreamingResponse:
    estimate = db.get(Estimate, estimate_id)
    if estimate is None:
        raise HTTPException(status_code=404, detail="estimate not found")

    payload = payload_from_estimate(estimate)
    render_fn, media_type, suffix = _WRITERS[format]
    data = render_fn(payload)
    filename = f"estimate-{estimate_id}-{suffix}"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
