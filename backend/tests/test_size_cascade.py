"""Phase 3: size-resolution cascade — priority order + provenance."""
import pytest

from app.parsing.sizes import (
    measure_rect_width_mm,
    parse_size_label,
    resolve_route_size,
)


def _span(text, x0, y0, x1=None, y1=None):
    x1 = x1 if x1 is not None else x0 + len(text) * 5
    y1 = y1 if y1 is not None else y0 + 10
    return {"text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1}


def _route(polyline):
    return {"polyline": polyline, "length_m": 5.0, "layer": "M-DUCT"}


class TestParseSizeLabel:
    def test_rect_variants(self):
        assert parse_size_label("600x400") == {"width_mm": 600, "height_mm": 400, "shape": "rect"}
        assert parse_size_label("600X400") == {"width_mm": 600, "height_mm": 400, "shape": "rect"}
        assert parse_size_label("600×400") == {"width_mm": 600, "height_mm": 400, "shape": "rect"}
        assert parse_size_label("600 x 400") == {"width_mm": 600, "height_mm": 400, "shape": "rect"}

    def test_dn(self):
        assert parse_size_label("DN150") == {"diameter_mm": 150, "shape": "round"}

    def test_diameter_symbol(self):
        assert parse_size_label("Ø250") == {"diameter_mm": 250, "shape": "round"}
        assert parse_size_label("D250") == {"diameter_mm": 250, "shape": "round"}

    def test_inches(self):
        assert parse_size_label('12"') == {"diameter_mm": 304.8, "shape": "round"}
        assert parse_size_label("12in") == {"diameter_mm": 304.8, "shape": "round"}

    def test_no_match(self):
        assert parse_size_label("AHU-01") is None
        assert parse_size_label("") is None


class TestCascadePriority:
    def test_schedule_beats_label(self):
        route = _route([(0, 0), (100, 0)])
        spans = [_span("600x400", 90, -20)]
        schedule = [{"width_mm": 500, "height_mm": 300, "ref": "sched_row_2"}]
        result = resolve_route_size(route, spans, "1:100", schedule_rows=schedule)
        assert result["source"] == "schedule"
        assert result["width_mm"] == 500

    def test_label_beats_geometry(self):
        # route drawn 17.008pt wide (= 600mm at 1:100); nearby label says 600x400
        route = _route([(0, 0), (17.008, 0), (17.008, 8.504), (0, 8.504), (0, 0)])
        spans = [_span("600x400", 10, -15)]
        result = resolve_route_size(route, spans, "1:100")
        assert result["source"] == "label"
        assert result["width_mm"] == 600

    def test_geometry_used_when_no_text(self):
        # 17.008pt x 8.504pt rectangle at 1:100 -> 600mm wide duct
        route = _route([(0, 0), (17.008, 0), (17.008, 8.504), (0, 8.504), (0, 0)])
        result = resolve_route_size(route, [], "1:100")
        assert result["source"] == "geometry"
        assert result["width_mm"] == pytest.approx(600, rel=0.05)

    def test_assumed_default_last(self):
        result = resolve_route_size(_route([(0, 0), (10, 0)]), [], "1:100",
                                    default_size={"width_mm": 400, "height_mm": 250})
        assert result["source"] == "assumed"
        assert result["width_mm"] == 400

    def test_none_without_default(self):
        assert resolve_route_size(_route([(0, 0), (10, 0)]), [], "1:100") is None

    def test_diameter_route_takes_diameter_label(self):
        route = _route([(0, 0), (50, 0)])
        route["layer"] = "M-DUCT-RND"
        spans = [_span("DN150", 40, -12)]
        result = resolve_route_size(route, spans, "1:100")
        assert result["diameter_mm"] == 150
        assert result["source"] == "label"

    def test_ref_names_the_source(self):
        spans = [_span("600x400", 90, -20)]
        result = resolve_route_size(_route([(0, 0), (100, 0)]), spans, "1:100")
        assert "600x400" in result["ref"]


class TestGeometryMeasurement:
    def test_rect_width_from_bbox(self):
        # 17.008pt x 8.504pt at 1:100 -> 600mm x 300mm (aspect 2:1)
        route = _route([(0, 0), (17.008, 0), (17.008, 8.504), (0, 8.504), (0, 0)])
        result = measure_rect_width_mm(route, "1:100")
        assert result["width_mm"] == pytest.approx(600, rel=0.05)
        assert result["height_mm"] == pytest.approx(300, rel=0.05)

    def test_degenerate_returns_none(self):
        assert measure_rect_width_mm(_route([(0, 0), (1, 0)]), "1:100") is None
