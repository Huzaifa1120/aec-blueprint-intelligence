"""Text–layer association walker tests (spec v3 §7.x, Task A5c / G5 part 1)."""

from app.e2e.extraction import TextAnnotationRow
from app.parsing.text_walker import associate_text, probe_span_ocgs


def _span(text: str, cx: float, cy: float, w: float = 20.0, h: float = 10.0) -> dict:
    return {
        "text": text,
        "x0": cx - w / 2,
        "y0": cy - h / 2,
        "x1": cx + w / 2,
        "y1": cy + h / 2,
    }


def test_span_near_centroid_attaches_with_component_index():
    spans = [_span("DB-1", 102.0, 101.0)]
    rows = associate_text(spans, [(100.0, 100.0)], [])
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, TextAnnotationRow)
    assert row.text == "DB-1"
    assert row.component_index == 0
    assert row.route_index is None
    assert row.ocg_layer is None
    x0, y0, x1, y1 = row.bbox
    assert (x0, y0) == (92.0, 96.0)
    assert (x1, y1) == (112.0, 106.0)


def test_nearer_route_wins_over_component():
    components = [(210.0, 205.0)]
    routes = [[(200.0, 200.0), (260.0, 260.0)]]
    spans = [_span("600x400", 230.0, 230.0)]  # on route; ~35pt from centroid
    rows = associate_text(spans, components, routes)
    assert len(rows) == 1
    assert rows[0].route_index == 0
    assert rows[0].component_index is None


def test_nearer_route_wins_between_routes():
    routes = [
        [(500.0, 500.0), (560.0, 500.0)],
        [(90.0, 100.0), (150.0, 100.0)],
    ]
    spans = [_span("duct tag", 120.0, 103.0)]  # ~3pt above route 1
    rows = associate_text(spans, [], routes)
    assert len(rows) == 1
    assert rows[0].route_index == 1


def test_beyond_threshold_dropped():
    spans = [_span("far away label", 400.0, 400.0)]
    rows = associate_text(spans, [(100.0, 100.0)], [])
    assert rows == []


def test_boundary_exactly_at_threshold_attaches():
    spans = [_span("edge", 100.0, 118.0)]
    rows = associate_text(spans, [(100.0, 100.0)], [], threshold_pt=18.0)
    assert len(rows) == 1
    assert rows[0].component_index == 0


def test_ocg_passthrough_by_span_index():
    spans = [_span("FCU-01", 100.0, 100.0), _span("orphan", 900.0, 900.0)]
    rows = associate_text(
        spans,
        [(100.0, 100.0)],
        [],
        ocg_by_span={0: "M-EQPT-NEW"},
        threshold_pt=18.0,
    )
    assert len(rows) == 1
    assert rows[0].ocg_layer == "M-EQPT-NEW"


def test_no_targets_yields_no_rows():
    assert associate_text([_span("x", 0.0, 0.0)], [], []) == []
    assert associate_text([], [(0.0, 0.0)], []) == []


def test_component_and_route_index_alignment():
    components = [(0.0, 0.0), (300.0, 300.0)]
    routes = [[(0.0, 50.0), (50.0, 50.0)]]
    spans = [_span("a", 301.0, 299.0), _span("b", 25.0, 52.0)]
    rows = associate_text(spans, components, routes)
    by_text = {r.text: r for r in rows}
    assert by_text["a"].component_index == 1
    assert by_text["b"].route_index == 0


class _FakePage:
    def __init__(self, info, ocgs):
        self._info = info
        self.parent = _FakeDoc(ocgs)

    def get_text(self, _kind):
        return self._info


class _FakeDoc:
    def __init__(self, ocgs):
        self._ocgs = ocgs

    def get_ocgs(self):
        return self._ocgs


def test_probe_span_ocgs_maps_xref_to_name():
    info = {
        "blocks": [
            {
                "type": 0,
                "lines": [
                    {"spans": [{"text": "one", "ocg": 7}]},
                    {"spans": [{"text": "two"}, {"text": "three", "ocg": 9}]},
                ],
            },
            {"type": 1, "width": 10, "height": 10},
        ]
    }
    page = _FakePage(info, {7: {"name": "M-DUCT-NEW", "on": True}, 9: {"name": "E-POWER"}})
    assert probe_span_ocgs(page) == {0: "M-DUCT-NEW", 2: "E-POWER"}


def test_probe_span_ocgs_graceful_when_unavailable():
    class _Broken:
        parent = None

        def get_text(self, _kind):
            raise RuntimeError("no dict extraction")

    assert probe_span_ocgs(_Broken()) == {}
    assert probe_span_ocgs(object()) == {}


def test_probe_span_ocgs_on_real_pymupdf_page():
    pymupdf = __import__("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "plain text")
    result = probe_span_ocgs(page)
    assert isinstance(result, dict)
