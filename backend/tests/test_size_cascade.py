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

    def test_diameter_word_false_positives(self):
        # words ending in "D" followed by a number are not diameters
        assert parse_size_label("GRID 500") is None
        assert parse_size_label("AND 400") is None

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


class TestShapeAwareness:
    def test_round_layer_gets_no_geometry_result(self):
        # Double-line bbox present, but a round route never takes rect
        # geometry: label-less M-DUCT-RND falls to the assumed default (or
        # None when no default is configured).
        route = _route([(0, 0), (17.008, 0), (17.008, 8.504), (0, 8.504), (0, 0)])
        route["layer"] = "M-DUCT-RND"
        assert resolve_route_size(route, [], "1:100") is None
        result = resolve_route_size(
            route, [], "1:100", default_size={"diameter_mm": 250}
        )
        assert result["source"] == "assumed"
        assert result["diameter_mm"] == 250

    def test_rect_schedule_row_skipped_for_round_layer(self):
        route = _route([(0, 0), (50, 0)])
        route["layer"] = "M-DUCT-RND"
        schedule = [{"width_mm": 600, "height_mm": 400}]
        assert resolve_route_size(route, [], "1:100", schedule_rows=schedule) is None

    def test_round_schedule_row_accepted_for_round_layer(self):
        route = _route([(0, 0), (50, 0)])
        route["layer"] = "M-DUCT-RND"
        schedule = [{"diameter_mm": 250}]
        result = resolve_route_size(route, [], "1:100", schedule_rows=schedule)
        assert result["source"] == "schedule"
        assert result["diameter_mm"] == 250

    def test_rect_geometry_still_works_for_rect_layers(self):
        route = _route([(0, 0), (17.008, 0), (17.008, 8.504), (0, 8.504), (0, 0)])
        result = resolve_route_size(route, [], "1:100")
        assert result["source"] == "geometry"


def test_fixture_units_tier_beats_label_and_geometry_but_not_schedule():
    from app.parsing.sizes import resolve_route_size

    route = {"polyline": [(0.0, 0.0), (300.0, 0.0)], "layer": "P-DOM-CW"}
    fu = {"diameter_mm": 32.0, "fu_total": 70.0, "ref": ["c1", "c2"]}
    spans = [{"text": "DN50", "x0": 10.0, "y0": 10.0, "x1": 30.0, "y1": 14.0}]

    out = resolve_route_size(route, spans, "1:100", fixture_unit_size=dict(fu))
    assert out["source"] == "fixture_units"
    assert out["diameter_mm"] == 32.0
    assert out["fu_total"] == 70.0

    # Schedule still outranks FU
    sched = [{
        "diameter_mm": 40.0, "ref": "sched:r1",
        "x0": 10.0, "y0": 10.0, "x1": 30.0, "y1": 14.0,
    }]
    out2 = resolve_route_size(
        route, spans, "1:100", schedule_rows=sched, fixture_unit_size=dict(fu)
    )
    assert out2["source"] == "schedule"

    # No FU supplied -> label still works as before
    out3 = resolve_route_size(route, spans, "1:100")
    assert out3["source"] == "label"


def test_size_source_order_constant_updated():
    from app.parsing.sizes import SIZE_SOURCE_ORDER

    assert SIZE_SOURCE_ORDER == ("schedule", "fixture_units", "label", "geometry", "assumed")


def test_mpipe_dn_label_resolves_at_label_tier():
    # Regression pin: on the HVAC fixture's M-PIPE route with repeated DN150
    # labels, this tier was corrected from ASSUMED ("configured_default") to
    # LABEL by the Phase 4 shape-gate extension (2026-08-24) that treats
    # pipe-family layers as round-capable. The label was always physically
    # right; ASSUMED was a false flag. Any future change here is deliberate.
    from app.parsing.sizes import resolve_route_size

    route = {"polyline": [(0.0, 0.0), (300.0, 0.0)], "layer": "M-PIPE"}
    spans = [{"text": "DN150", "x0": 10.0, "y0": 10.0, "x1": 30.0, "y1": 14.0}]

    out = resolve_route_size(
        route,
        spans,
        "1:100",
        default_size={"diameter_mm": 150.0},
    )
    assert out["source"] == "label"
    assert out["diameter_mm"] == 150.0
