"""Phase 3: schedule-table detection from text spans."""

from app.parsing.sizes import detect_schedule_rows


def _span(text, x0, y0):
    return {"text": text, "x0": x0, "y0": y0, "x1": x0 + len(text) * 5, "y1": y0 + 10}


class TestDetectScheduleRows:
    def test_header_then_rows(self):
        spans = [
            _span("AIR LEGEND", 100, 100),
            _span("DUCT SIZE", 100, 700),
            _span("600x400", 100, 720),
            _span("500x300", 100, 740),
        ]
        rows = detect_schedule_rows(spans)
        assert len(rows) == 2
        assert rows[0]["width_mm"] == 600 and rows[0]["height_mm"] == 400
        assert rows[0]["ref"].startswith("schedule:DUCT SIZE")

    def test_pipe_schedule_header(self):
        spans = [
            _span("PIPE SCHEDULE", 50, 500),
            _span("DN150", 50, 520),
            _span("DN100", 50, 540),
        ]
        rows = detect_schedule_rows(spans)
        assert len(rows) == 2
        assert rows[0]["diameter_mm"] == 150

    def test_no_header_no_rows(self):
        assert detect_schedule_rows([_span("600x400", 0, 0)]) == []

    def test_non_size_rows_skipped(self):
        spans = [
            _span("DUCT SIZE", 0, 0),
            _span("NOTE: ALL DUCTS SEALED", 0, 20),
            _span("400x250", 0, 40),
        ]
        rows = detect_schedule_rows(spans)
        assert len(rows) == 1
        assert rows[0]["width_mm"] == 400
