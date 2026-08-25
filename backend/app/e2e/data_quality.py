"""Per-run data-quality counters (spec v3 conformance).

Every input that enters the pipeline but silently vanishes — a measured route
with no applicable assembly, a symbol skipped in the count path, an unmapped
cluster, a degenerate polyline, a fixture outside the FU corridor, a failed
upload classification — is tallied here and surfaced in the e2e response
under ``data_quality`` so nothing disappears without trace. Counts feed
human review; they never alter quantities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class DataQuality:
    """Tally of silently-dropped inputs for one e2e run."""

    dropped_routes: int = 0
    dropped_symbols: int = 0
    unmapped_count: int = 0
    degenerate_skipped: int = 0
    fu_corridor_excluded: int = 0
    classifier_errors: int = 0
    # Legend/title-block gating (app.parsing.gating): annotation glyphs and
    # legend-undeclared types are flagged for review instead of being priced.
    title_block_excluded: int = 0
    legend_gate_excluded: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "dropped_routes": self.dropped_routes,
            "dropped_symbols": self.dropped_symbols,
            "unmapped_count": self.unmapped_count,
            "degenerate_skipped": self.degenerate_skipped,
            "fu_corridor_excluded": self.fu_corridor_excluded,
            "classifier_errors": self.classifier_errors,
            "title_block_excluded": self.title_block_excluded,
            "legend_gate_excluded": self.legend_gate_excluded,
        }
