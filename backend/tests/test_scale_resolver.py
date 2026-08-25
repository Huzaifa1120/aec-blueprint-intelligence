from app.parsing.scale import resolve_scale, parse_scale_denominator


def _span(text):
    return {"text": text}


def test_electrical_scale_detected():
    res = resolve_scale([_span("ELECTRICAL.SCALE 1:100"), _span("noise")])
    assert res.status == "detected"
    assert res.denominator == 100.0
    assert res.scale_str == "1:100"


def test_architectural_quarter_inch():
    res = resolve_scale([_span('SCALE 1/4"=1\'-0"')])
    assert res.status == "detected"
    assert res.denominator == 48.0


def test_architectural_eighth_inch():
    assert resolve_scale([_span('1/8"=1\'-0"')]).denominator == 96.0


def test_generic_ratio_detected():
    res = resolve_scale([_span("SCALE 1:50")])
    assert res.status == "detected"
    assert res.denominator == 50.0


def test_imperial_title_block_40ft():
    res = resolve_scale([_span("SCALE 1=40'-0\"")])
    assert res.status == "detected"
    assert res.denominator == 480.0


def test_imperial_title_block_100ft():
    res = resolve_scale([_span('SCALE 1=100\'-0"')])
    assert res.status == "detected"
    assert res.denominator == 1200.0


def test_electrical_precedence_over_architectural_in_same_span():
    res = resolve_scale([_span('ELECTRICAL.SCALE 1:50   SCALE 1/4"=1\'-0"')])
    assert res.status == "detected"
    assert res.denominator == 50.0


def test_missing_scale_is_assumed_1_100():
    res = resolve_scale([_span("no scale here"), _span("")])
    assert res.status == "assumed"
    assert res.scale_str == "1:100"
    assert res.denominator == 100.0


# ---------------------------------------------------------------------------
# Paired title-block labels: 'SCALE' anchor span + nearby ratio token span.
# Real-world case (MMC-JVC-CD-ELEC-3902_AC-WIRE): rotated title-block cells
# put the label and the slash-form value in two separate spans ~26 pt apart.
# ---------------------------------------------------------------------------

def _pt_span(text, x0, y0, x1, y1):
    return {"text": text, "bbox": (x0, y0, x1, y1)}


def test_paired_slash_ratio_detected():
    res = resolve_scale([
        _pt_span("SCALE", 50.7, 1114.7, 55.5, 1130.3),
        _pt_span("1/100", 39.8, 1132.9, 49.4, 1161.7),
    ])
    assert res.status == "detected"
    assert res.scale_str == "1:100"
    assert res.denominator == 100.0


def test_paired_colon_ratio_detected():
    res = resolve_scale([
        _pt_span("SCALE", 50.7, 1114.7, 55.5, 1130.3),
        _pt_span("1:200", 39.8, 1132.9, 49.4, 1161.7),
    ])
    assert res.status == "detected"
    assert res.denominator == 200.0


def test_paired_ratio_requires_proximity():
    res = resolve_scale([
        _pt_span("SCALE", 10.0, 10.0, 20.0, 20.0),
        _pt_span("1/100", 500.0, 500.0, 520.0, 530.0),
    ])
    assert res.status == "assumed"


def test_slash_ratio_without_scale_anchor_ignored():
    # A bare ratio token with no SCALE label must NOT be promoted to a
    # detected scale — guards against false positives from dimension text.
    res = resolve_scale([_pt_span("1/100", 39.8, 1132.9, 49.4, 1161.7)])
    assert res.status == "assumed"


def test_inline_patterns_still_win_over_pairing():
    # Existing inline behaviour is unchanged when a span carries both parts.
    res = resolve_scale([
        _pt_span("ELECTRICAL.SCALE 1:50", 0.0, 0.0, 60.0, 12.0),
        _pt_span("SCALE", 50.7, 1114.7, 55.5, 1130.3),
        _pt_span("1/100", 39.8, 1132.9, 49.4, 1161.7),
    ])
    assert res.denominator == 50.0


def test_parse_denominator_ok_and_not():
    assert parse_scale_denominator("1:100") == (100.0, True)
    assert parse_scale_denominator("garbage")[1] is False
