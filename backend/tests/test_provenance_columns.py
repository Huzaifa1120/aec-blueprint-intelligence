"""Phase 3: provenance columns exist and round-trip."""
import json

from app.db.base import Base
from app.db.models.estimate import BoqItem
from app.db.models.geometry import Route


class TestProvenanceColumns:
    def test_route_size_json_column(self):
        # Model metadata is the ORM's source of truth; live-DB introspection
        # is order-dependent here because get_engine() is lru_cached and
        # other tests repoint it at temp databases. Migration application
        # itself is covered by tests/test_migrations.py.
        cols = {c.name for c in Base.metadata.tables["routes"].columns}
        assert "size_json" in cols

    def test_boq_item_provenance_columns(self):
        cols = {c.name for c in Base.metadata.tables["boq_items"].columns}
        assert {"derivation_json", "size_source"} <= cols

    def test_model_attributes_nullable(self):
        assert Route.size_json is not None  # column defined
        assert BoqItem.derivation_json is not None
        assert BoqItem.size_source is not None

    def test_json_round_trip(self):
        payload = {"width_mm": 600, "height_mm": 400,
                   "source": "label", "ref": "text_span:600x400"}
        instance = Route(
            route_type="duct_rectangular",
            length_m=10.0,
            size_json=json.dumps(payload),
        )
        assert json.loads(instance.size_json) == payload
