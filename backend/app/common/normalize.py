"""Shared payload normalizers for e2e, exports, and narration.

One canonical definition each for the BOQ click-through region shape
(spec v3 §7.12) and the nonzero data-quality counter filter (spec v3
§7.14), so the live response, persistence spine, exports, and narration
render identically from the same inputs.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def source_region(page: Any, bbox: Any) -> Optional[Dict[str, Any]]:
    """Normalized click-through region for one BOQ row (spec v3 §7.12).

    ``{"page": int, "bbox": [x0, y0, x1, y1]}`` in PDF points, or None when
    no usable region exists — persistence stores exactly this shape, the
    same one the live response carries in each row's ``source`` block, so
    payload round-trips are value-identical.
    """
    if not bbox:
        return None
    try:
        corners = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return None
    if len(corners) < 4:
        return None
    return {"page": int(page or 0), "bbox": corners}


def nonzero_counters(data_quality: object) -> list[tuple[str, int]]:
    """Only counters that actually fired are disclosed; scale_str is a string
    and zero counters stay out."""
    if not isinstance(data_quality, dict):
        return []
    return [
        (name, value)
        for name, value in data_quality.items()
        if isinstance(value, int) and not isinstance(value, bool) and value != 0
    ]
