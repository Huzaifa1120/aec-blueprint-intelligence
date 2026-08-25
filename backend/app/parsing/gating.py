"""Legend / title-block gating guardrails (spec v3 §7.6/§7.9 philosophy).

Classification via ``data/layer_mapping.yaml`` is sheet-global: any cluster on
a mapped OCG layer becomes a priced assembly instance. That is wrong for
annotation geometry — a drawing's legend table draws its own symbol cells,
often on a legitimately-mapped layer, and title blocks hatch/label inside
their own band. This module adds two deterministic, text-driven gates that
keep annotation glyphs out of the priced BOQ WITHOUT ever silently dropping
them:

1. Title-block region exclusion — sheet text carrying multiple title-block
   keywords (DRAWER, SHEET NO, REVISION, …) anchors an annotation band; any
   mapped component cluster whose centroid falls inside it is flagged
   ``title_block_region`` for human review instead of being priced.
2. Legend whitelist — when a readable legend block exists (``detect_blocks``
   found SYMBOL+DESCRIPTION rows), each assembly may declare the legend
   keywords that describe it (optional ``legend_keywords`` in its YAML rule);
   component types absent from that whitelist are flagged
   ``not_in_legend``. No readable legend ⇒ gate is inert (fail-open) so
   sheets with outlined-curve legends keep working through gate 1 alone.

Trap compliance: regions come from deterministic span geometry; the allowed
set comes from YAML-declared keywords; nothing here outputs a quantity —
it only decides priceability and always leaves a reviewable trace.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

# Exact-match vocabulary (after strip + colon removal + upper()). Deliberately
# conservative: words this specific do not appear as plan annotations.
TITLE_BLOCK_KEYWORDS = frozenset(
    {
        "DRAWER",
        "SHEET NO",
        "SHEET NAME",
        "APPROVE",
        "CONTROL",
        "REVISION",
        "DISCIPLINE",
        "SCALE",
        "DATE",
        "OWNER",
        "CONSULTANT",
        "PROJECT",
        "KEY PLAN",
    }
)

_MIN_KEYWORD_ANCHORS = 3
_DEFAULT_MARGIN_PT = 32.0

Region = Dict[str, float]
FlagReason = str


def _norm_label(text: str) -> str:
    return (text or "").strip().rstrip(":").strip().upper()


def _center(span: dict) -> Tuple[float, float]:
    return (
        (float(span["x0"]) + float(span["x1"])) / 2.0,
        (float(span["y0"]) + float(span["y1"])) / 2.0,
    )


def detect_title_block_regions(
    spans: List[dict],
    *,
    min_keywords: int = _MIN_KEYWORD_ANCHORS,
    margin_pt: float = _DEFAULT_MARGIN_PT,
) -> List[Region]:
    """Detect annotation/title-block bands from title-block keyword spans.

    A region is the bounding envelope of ALL matched keyword spans expanded
    by ``margin_pt`` on every side. Fewer than ``min_keywords`` distinct
    keyword hits ⇒ no region (a lone 'SCALE' or 'DATE' must never swallow
    plan geometry).
    """
    matched = [s for s in spans if _norm_label(s.get("text", "")) in TITLE_BLOCK_KEYWORDS]
    if len({_norm_label(s.get("text", "")) for s in matched}) < min_keywords:
        return []
    envelope: Region = {
        "x0": min(float(s["x0"]) for s in matched) - margin_pt,
        "y0": min(float(s["y0"]) for s in matched) - margin_pt,
        "x1": max(float(s["x1"]) for s in matched) + margin_pt,
        "y1": max(float(s["y1"]) for s in matched) + margin_pt,
    }
    return [envelope]


def _point_in_region(x: float, y: float, region: Region) -> bool:
    return region["x0"] <= x <= region["x1"] and region["y0"] <= y <= region["y1"]


def legend_allowed_assemblies(blocks: Sequence) -> Optional[set]:
    """Assembly types declared by the sheet's own readable legend(s).

    Builds the keyword→assembly index from the YAML rules' optional
    ``legend_keywords`` and matches them against every legend-type block's
    entry cell text (case-insensitive substring). Returns None when no
    legend block was detected — callers must fail open to region-only
    gating.
    """
    from app.assembly.rules import all_legend_keywords

    legend_blocks = [b for b in blocks or [] if getattr(b, "block_type", "") == "legend"]
    if not legend_blocks:
        return None
    index = all_legend_keywords()
    corpus = " ".join(
        cell
        for block in legend_blocks
        for entry in (block.entries or [])
        for cell in (entry.get("cells") or [])
        if isinstance(cell, str)
    ).upper()
    if not corpus.strip():
        return set()
    return {
        assembly
        for assembly, keywords in index.items()
        if any(keyword.upper() in corpus for keyword in keywords)
    }


def gate_components(
    components: List[Dict],
    regions: Sequence[Region],
    allowed_assemblies: Optional[set],
) -> Tuple[List[Dict], List[Dict]]:
    """Split counted components into priceable vs flagged-for-review.

    Gate order (a symbol can only be flagged once):
    1. centroid inside any title-block region ⇒ ``title_block_region``
    2. legend whitelist active and type undeclared ⇒ ``not_in_legend``

    Flagged dicts are shallow copies carrying ``gate_reason``; priced dicts
    are returned untouched.
    """
    priced: List[Dict] = []
    flagged: List[Dict] = []
    for comp in components:
        reason: Optional[FlagReason] = None
        if any(
            _point_in_region(float(comp.get("x", 0.0)), float(comp.get("y", 0.0)), r)
            for r in regions
        ):
            reason = "title_block_region"
        elif allowed_assemblies is not None and comp.get("assembly_type") not in allowed_assemblies:
            reason = "not_in_legend"
        if reason is None:
            priced.append(comp)
        else:
            flagged.append({**comp, "gate_reason": reason})
    return priced, flagged


def aggregate_flagged(flagged: List[Dict]) -> List[Dict]:
    """Aggregate flagged component dicts by (assembly_type, layer, reason)."""
    aggregated: Dict[Tuple[str, str, FlagReason], Dict] = {}
    order: List[Tuple[str, str, FlagReason]] = []
    for comp in flagged:
        key = (
            str(comp.get("assembly_type") or ""),
            str(comp.get("layer") or ""),
            comp.get("gate_reason", ""),
        )
        if key not in aggregated:
            aggregated[key] = {
                "assembly_type": key[0],
                "layer": key[1],
                "reason": key[2],
                "count": 0,
                "source_path_ids": list(comp.get("source_path_ids", [])[:3]),
            }
            order.append(key)
        aggregated[key]["count"] += 1
    return [aggregated[key] for key in order]
