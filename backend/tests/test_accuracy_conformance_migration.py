"""Accuracy-conformance migration: bbox/corrections/dq/pdf-path columns exist at head."""

from sqlalchemy import inspect

from app.db.session import get_engine


def test_accuracy_conformance_columns_exist_on_supabase() -> None:
    """Verify accuracy-conformance columns exist in current Supabase schema."""
    engine = get_engine()
    insp = inspect(engine)
    
    boq_cols = {c["name"] for c in insp.get_columns("boq_items")}
    assert {"source_bbox_json"} <= boq_cols
    
    est_cols = {c["name"] for c in insp.get_columns("estimates")}
    assert {
        "data_quality_json",
        "scale_status",
        "source_pdf_path",
        "source_quality",
    } <= est_cols
    
    act_cols = {c["name"] for c in insp.get_columns("review_actions")}
    assert {"boq_item_id", "reason", "corrected_value"} <= act_cols


def test_review_actions_fk_has_ondelete_set_null() -> None:
    """Verify review_actions.boq_item_id FK has ON DELETE SET NULL."""
    from sqlalchemy import text
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT confdeltype
            FROM pg_constraint
            WHERE conrelid = 'review_actions'::regclass
            AND conname = 'fk_review_actions_boq_item_id_boq_items'
        """))
        row = result.fetchone()
        assert row is not None, "FK not found"
        # 'n' = SET NULL in PostgreSQL
        assert row.confdeltype == 'n', f"Expected ON DELETE SET NULL (n), got {row.confdeltype}"