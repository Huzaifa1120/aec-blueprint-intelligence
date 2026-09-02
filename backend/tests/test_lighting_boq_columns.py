from sqlalchemy import inspect
from app.db.models.estimate import BoqItem


def test_spec_code_column_present_on_boq_items():
    """SQLAlchemy model has spec_code column"""
    mapper = inspect(BoqItem)
    assert "spec_code" in mapper.columns
    col = mapper.columns["spec_code"]
    assert col.type.length == 32


def test_loop_id_column_present_on_boq_items():
    """SQLAlchemy model has loop_id column"""
    mapper = inspect(BoqItem)
    assert "loop_id" in mapper.columns
    col = mapper.columns["loop_id"]
    assert col.type.length == 64


def test_both_columns_are_nullable():
    """Both spec_code and loop_id columns are nullable"""
    mapper = inspect(BoqItem)
    assert mapper.columns["spec_code"].nullable is True
    assert mapper.columns["loop_id"].nullable is True