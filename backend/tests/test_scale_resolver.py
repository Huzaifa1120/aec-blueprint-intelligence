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


def test_missing_scale_is_assumed_1_100():
    res = resolve_scale([_span("no scale here"), _span("")])
    assert res.status == "assumed"
    assert res.scale_str == "1:100"
    assert res.denominator == 100.0


def test_parse_denominator_ok_and_not():
    assert parse_scale_denominator("1:100") == (100.0, True)
    assert parse_scale_denominator("garbage")[1] is False
