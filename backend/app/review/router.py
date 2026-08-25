"""Review-time endpoints — sessions, actions, project metrics (spec v3 §7.13/§15)."""
from __future__ import annotations

import uuid as _uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from app.db.models.review import ReviewAction, ReviewSession, utcnow
from app.db.session import get_engine

router = APIRouter(prefix="/api/review", tags=["review"])
metrics_router = APIRouter(tags=["review"])


class CreateSessionRequest(BaseModel):
    sheet_label: str
    project_id: str | None = None


class AddActionRequest(BaseModel):
    item_id: str
    action: Literal["accept", "reject", "correct"]
    confidence_tier: Literal["MEASURED", "DERIVED", "ASSUMED", "UNMAPPED"]
    boq_item_id: _uuid.UUID | None = None
    reason: str | None = None
    corrected_value: float | None = None


def _parse_uuid(value: str) -> _uuid.UUID:
    try:
        return _uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")


def compute_metrics(engine, project_id: _uuid.UUID | None = None) -> dict:
    from sqlalchemy import orm

    from app.core.config import get_settings

    target = get_settings().review_time_target_min
    with orm.Session(engine) as s:
        query = s.query(ReviewSession)
        if project_id is not None:
            query = query.filter(ReviewSession.project_id == project_id)
        sessions = query.all()
        closed = [x for x in sessions if x.started_at and x.ended_at]
        if not closed:
            return {"avg_minutes_per_sheet": None, "per_tier": {}, "sessions": len(sessions),
                    "target_minutes": target, "breaches_target": False}
        minutes = [(x.ended_at - x.started_at).total_seconds() / 60.0 for x in closed]
        avg = sum(minutes) / len(minutes)
        tier_map: dict[str, list[float]] = {}
        for x in closed:
            tiers = {a.confidence_tier for a in x.actions}
            dur = (x.ended_at - x.started_at).total_seconds() / 60.0
            for t in tiers:
                tier_map.setdefault(t, []).append(dur)
        per_tier = {t: sum(v) / len(v) for t, v in tier_map.items()}
        return {"avg_minutes_per_sheet": avg, "per_tier": per_tier,
                "sessions": len(sessions), "target_minutes": target,
                "breaches_target": avg > target}


@router.post("/sessions")
def create_session(payload: CreateSessionRequest) -> dict:
    project_id = _parse_uuid(payload.project_id) if payload.project_id else None
    with OrmSession(get_engine()) as db:
        session = ReviewSession(sheet_label=payload.sheet_label, project_id=project_id)
        db.add(session)
        db.commit()
        return {"session_id": str(session.id)}


@router.post("/sessions/{session_id}/close")
def close_session(session_id: str) -> dict:
    sid = _parse_uuid(session_id)
    with OrmSession(get_engine()) as db:
        session = db.get(ReviewSession, sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Review session not found")
        session.ended_at = utcnow()
        db.commit()
        return {"status": "closed", "session_id": str(session.id)}


@router.post("/sessions/{session_id}/actions")
def add_action(session_id: str, payload: AddActionRequest) -> dict:
    sid = _parse_uuid(session_id)
    with OrmSession(get_engine()) as db:
        session = db.get(ReviewSession, sid)
        if session is None:
            raise HTTPException(status_code=404, detail="Review session not found")
        db.add(
            ReviewAction(
                session_id=session.id,
                item_id=payload.item_id,
                action=payload.action,
                confidence_tier=payload.confidence_tier,
                boq_item_id=payload.boq_item_id,
                reason=payload.reason,
                corrected_value=payload.corrected_value,
            )
        )
        db.commit()
        return {"status": "recorded", "session_id": str(session.id)}


@metrics_router.get("/api/projects/{project_id}/review-metrics")
def get_review_metrics(project_id: str) -> dict:
    pid = _parse_uuid(project_id)
    return compute_metrics(get_engine(), project_id=pid)
