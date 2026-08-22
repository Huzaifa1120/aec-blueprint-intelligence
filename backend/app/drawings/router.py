"""Drawing quality endpoints — GET quality, POST request-reexport (spec §7.2)."""
from __future__ import annotations

import json
import os
import tempfile
import uuid as _uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlalchemy.orm import Session as OrmSession

from app.db.models.quality import DrawingQualityAssessment, ReexportRequest
from app.db.session import get_engine
from app.ingestion.quality_gate import LOOP_BACK_MESSAGE, assess_quality

router = APIRouter(prefix="/api/drawings", tags=["drawings"])


@router.post("/check")
def check_drawing_quality(file: UploadFile = File(...)) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        result = assess_quality(tmp_path)
    finally:
        os.unlink(tmp_path)
    return result


@router.get("/{drawing_id}/quality")
def get_quality(drawing_id: str) -> dict:
    try:
        did = _uuid.UUID(drawing_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid drawing id")
    with OrmSession(get_engine()) as db:
        row = (
            db.query(DrawingQualityAssessment)
            .filter(DrawingQualityAssessment.drawing_id == did)
            .order_by(DrawingQualityAssessment.created_at.desc())
            .first()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="No quality assessment recorded for drawing")
        return {"drawing_id": drawing_id, "verdict": row.verdict,
                "metrics": json.loads(row.metrics_json) if row.metrics_json else None}


@router.post("/{drawing_id}/request-reexport")
def request_reexport(drawing_id: str) -> dict:
    with OrmSession(get_engine()) as db:
        req = ReexportRequest(message=LOOP_BACK_MESSAGE)
        db.add(req)
        db.commit()
        return {"status": "recorded", "message": LOOP_BACK_MESSAGE}
