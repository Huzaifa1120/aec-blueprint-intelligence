"""JSON BOQ export — verbatim structured round-trip (spec v3 §7.14).

The writer serializes the payload unchanged: every number is copied
verbatim from the deterministic BOQ calculation, never recomputed.
"""

from __future__ import annotations

import json


def render(rows: dict) -> bytes:
    """Serialize the BOQ payload to UTF-8 JSON bytes, structure untouched."""
    return json.dumps(rows, indent=2, ensure_ascii=False).encode("utf-8")
