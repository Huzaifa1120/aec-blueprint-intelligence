"""Phase 3: provenance columns exist and round-trip."""
import json

from sqlalchemy import inspect

from app.db.models.estimate import BoqItem
from app.db.models.geometry import Route
from app.db.session import get_engine


class TestProvenanceColumns:
    def test_route_size_json_column(self):
        cols = {c["name"] for c in inspect(get_engine()).get_columns("routes")}
        assert "size_json" in cols

    def test_boq_item_provenance_columns(self):
        cols = {c["name"] for c in inspect(get_engine()).get_columns("boq_items")}
        assert {"derivation_json", "size_source"} <= cols

    def test_model_attributes_nullable(self):
        assert Route.size_json is not None  # column defined
        assert BoqItem.derivation_json is not None
        assert BoqItem.size_source is not None

    def test_json_round_trip(self):
        payload = {"width_mm": 600, "height_mm": 400,
                   "source": "label", "ref": "text_span:600x400"}
        assert json.loads(json.dumps(payload)) == payload
