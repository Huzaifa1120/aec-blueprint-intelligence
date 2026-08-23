"""v3 conformance schema — tables + FKs exist per spec §8."""

from sqlalchemy import Text

from app.db.base import Base
from app.db.models.extraction import Layer, ScheduleBlock, TextAnnotation


def test_new_tables_in_metadata():
    names = {t for t in Base.metadata.tables}
    assert {"layers", "schedule_blocks", "text_annotations"} <= names


def test_layer_fk_on_geometry_models():
    from app.db.models.geometry import Component, Route, Space

    for model in (Component, Route, Space):
        assert hasattr(model, "layer_id")


def test_layer_unique_per_sheet():
    unique_column_sets = [
        tuple(col.name for col in getattr(uq, "columns", []))
        for uq in Layer.__table__.constraints
        if uq.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("sheet_id", "ocg_name") in unique_column_sets


def test_text_annotation_nullable_links():
    ta = TextAnnotation.__table__
    assert ta.c.ocg_layer.nullable
    assert ta.c.component_id.nullable
    assert ta.c.route_id.nullable
    assert ta.c.space_id.nullable


def test_schedule_block_columns():
    sb = ScheduleBlock.__table__
    assert sb.c.block_type.type.length == 30
    assert isinstance(sb.c.entries_json.type, Text)


def test_sheet_source_quality_column():
    from app.db.models.project import Sheet

    sheet_col = Sheet.__table__.c.source_quality
    assert not sheet_col.nullable
    assert sheet_col.default.arg == "layered_vector"
