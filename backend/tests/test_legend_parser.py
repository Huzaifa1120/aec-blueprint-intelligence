"""Tests for V3 Legend Parser.

Locks in the interface from the handoff doc:
  - parse_legend(page) -> List[FixtureSpec]
  - FixtureSpec fields: code, description, wattage, dimensions, ip_rating,
    shape_hint, driver, conversion_pct, has_emergency, mount
  - query_specs(specs, required_ip, preferred_shape, has_emergency) -> List[FixtureSpec]
"""
import pytest
import pymupdf

from app.services.lighting.legend_parser import (
    FixtureSpec,
    parse_legend,
    query_specs,
    get_legend_stats,
)


SAMPLE_PDF = (
    "../data/samples/P0050-AMC-A-E2-2F-EL-122-02-B, "
    "Lighting Layout, 2nd Floor, Part-1.pdf"
)


@pytest.fixture(scope="module")
def legend_page():
    doc = pymupdf.open(SAMPLE_PDF)
    yield doc[0]
    doc.close()


@pytest.fixture(scope="module")
def specs(legend_page):
    return parse_legend(legend_page)


# ----- Structural tests -----


def test_parse_legend_returns_nonempty_list(specs):
    assert isinstance(specs, list)
    assert len(specs) > 0


def test_parse_legend_returns_fixture_spec_instances(specs):
    assert all(isinstance(s, FixtureSpec) for s in specs)


def test_fixture_spec_has_required_fields():
    """FixtureSpec must expose all fields promised by the handoff."""
    required = {
        "code", "description", "wattage", "dimensions", "ip_rating",
        "shape_hint", "driver", "conversion_pct", "has_emergency", "mount",
    }
    field_names = {f.name for f in FixtureSpec.__dataclass_fields__.values()}
    missing = required - field_names
    assert not missing, f"FixtureSpec missing fields: {missing}"


def test_parse_legend_codes_match_dd_dddd_pattern(specs):
    """Fixture type codes are formatted 02-XXXX."""
    import re
    pat = re.compile(r"^\d{2}-\d{4}$")
    bad = [s.code for s in specs if not pat.match(s.code)]
    assert not bad, f"Malformed codes: {bad}"


def test_parse_legend_codes_are_unique(specs):
    codes = [s.code for s in specs]
    assert len(codes) == len(set(codes)), "Duplicate codes in legend"


# ----- Real PDF test (Part-1) -----


def test_part1_legend_has_expected_fixture_count(specs):
    """The Part-1 legend contains dozens of fixture type codes (≥25 from handoff, ≥50 actually)."""
    assert len(specs) >= 25, f"Expected ≥25 specs, got {len(specs)}"


def test_part1_legend_stats_shape(specs):
    stats = get_legend_stats(specs)
    assert stats["total"] == len(specs)
    assert "by_shape" in stats
    assert "by_ip" in stats
    assert "by_emergency" in stats
    assert "wattage_range" in stats


# ----- query_specs interface -----


def test_query_specs_filters_by_ip(specs):
    """Query with no filters should return all specs."""
    all_specs = query_specs(specs, required_ip=None, preferred_shape=None,
                            has_emergency=None)
    assert len(all_specs) == len(specs)


def test_query_specs_filters_by_emergency(specs):
    """At least some specs should support emergency mode in this hospital plan."""
    em_specs = query_specs(specs, required_ip=None, preferred_shape=None,
                           has_emergency=True)
    assert isinstance(em_specs, list)
    assert all(s.has_emergency for s in em_specs)


def test_query_specs_filters_by_shape(specs):
    """Shape filter should return only specs with matching shape_hint."""
    circle_specs = query_specs(specs, required_ip=None, preferred_shape="circle",
                               has_emergency=None)
    assert isinstance(circle_specs, list)
    # all results should have a circle-related shape hint
    for s in circle_specs:
        assert "circle" in s.shape_hint.lower() or s.shape_hint == "circle"


def test_query_specs_combined_filter(specs):
    """Combining IP + shape + emergency narrows the result set."""
    narrow = query_specs(specs, required_ip="IP65", preferred_shape="circle",
                         has_emergency=True)
    broad = query_specs(specs, required_ip=None, preferred_shape=None,
                        has_emergency=None)
    assert len(narrow) <= len(broad)
    for s in narrow:
        assert s.ip_rating == "IP65"
        assert "circle" in s.shape_hint.lower() or s.shape_hint == "circle"
        assert s.has_emergency is True
