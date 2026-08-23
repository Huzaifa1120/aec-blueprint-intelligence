"""Legend & schedule-block detector tests (spec v3 §7.5, Task A5b)."""

from app.e2e.extraction import ScheduleBlockRow
from app.parsing.schedules import detect_blocks


def _span(text: str, x0: float, y0: float, height: float = 10.0) -> dict:
    return {
        "text": text,
        "x0": x0,
        "y0": y0,
        "x1": x0 + len(text) * 5.0,
        "y1": y0 + height,
    }


def _row(texts: list[str], xs: list[float], y0: float) -> list[dict]:
    return [_span(t, x, y0) for t, x in zip(texts, xs)]


COLS = [50.0, 110.0, 200.0]


def test_duct_size_table_is_attribute_schedule():
    spans = (
        _row(["DUCT SIZE", "THICKNESS", "GAUGE"], COLS, 100.0)
        + _row(["600x400", "0.8", "25"], COLS, 120.0)
        + _row(["500x350", "0.8", "22"], COLS, 140.0)
        + _row(["400x300", "0.6", "20"], COLS, 160.0)
    )
    (block,) = detect_blocks(spans)
    assert block.block_type == "attribute_schedule"
    assert block.entries == [
        {"cells": ["600x400", "0.8", "25"]},
        {"cells": ["500x350", "0.8", "22"]},
        {"cells": ["400x300", "0.6", "20"]},
    ]
    assert block.page_region == {"x0": 50.0, "y0": 100.0, "x1": 225.0, "y1": 170.0}
    assert isinstance(block, ScheduleBlockRow)


def test_symbol_description_legend():
    spans = (
        _row(["SYMBOL", "DESCRIPTION"], [50.0, 200.0], 100.0)
        + _row(["E1", "Emergency light"], [50.0, 200.0], 120.0)
        + _row(["E2", "Smoke detector"], [50.0, 199.0], 141.0)
    )
    (block,) = detect_blocks(spans)
    assert block.block_type == "legend"
    assert block.entries == [
        {"cells": ["E1", "Emergency light"]},
        {"cells": ["E2", "Smoke detector"]},
    ]


def test_skewed_cells_still_group_into_one_row():
    spans = (
        _row(["SYMBOL", "DESCRIPTION"], [50.0, 200.0], 100.0)
        + [
            _span("F1", 50.0, 119.0),
            _span("Fire damper", 200.0, 122.0),  # centers differ by 3 <= tol
            _span("Notes elsewhere", 700.0, 300.0),
        ]
    )
    (block,) = detect_blocks(spans)
    assert block.block_type == "legend"
    assert block.entries == [{"cells": ["F1", "Fire damper"]}]


def test_scattered_text_yields_no_blocks():
    spans = (
        _row("SCALE 1:100 AT A1".split(), [40.0 * i for i in range(5)], 30.0)
        + _row("GENERAL NOTES APPLY TO WORK".split(), [60.0 * i for i in range(5)], 90.0)
    )
    assert detect_blocks(spans) == []


def test_header_without_data_rows_returns_empty():
    spans = _row(["DUCT SIZE", "GAUGE"], COLS[:2], 100.0)
    assert detect_blocks(spans) == []


def test_two_separate_tables_yield_two_blocks():
    legend = (
        _row(["SYMBOL", "DESCRIPTION"], [50.0, 200.0], 100.0)
        + _row(["M1", "VAV box"], [50.0, 200.0], 120.0)
    )
    duct = (
        _row(["DUCT SIZE", "THICKNESS", "GAUGE"], [400.0, 460.0, 550.0], 400.0)
        + _row(["800x500", "1.0", "26"], [400.0, 460.0, 550.0], 420.0)
        + _row(["600x400", "0.8", "25"], [400.0, 460.0, 550.0], 440.0)
    )
    blocks = detect_blocks(legend + duct)
    assert [(b.block_type, len(b.entries)) for b in blocks] == [
        ("legend", 1),
        ("attribute_schedule", 2),
    ]
    assert blocks[0].page_region["y1"] < blocks[1].page_region["y0"]
    assert blocks[1].entries[0] == {"cells": ["800x500", "1.0", "26"]}


def test_empty_and_degenerate_inputs():
    assert detect_blocks([]) == []
    assert detect_blocks([_span("random label", 10.0, 10.0)]) == []
