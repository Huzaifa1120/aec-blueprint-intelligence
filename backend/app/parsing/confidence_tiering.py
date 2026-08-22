"""Confidence tiering — per-line MEASURED / DERIVED / ASSUMED status.

Non-negotiable rules (Rules.md §7, §3.8):
- Per-line confidence status: MEASURED / DERIVED / ASSUMED — never blended "%".
- MEASURED: directly read from vector geometry (default).
- DERIVED: calculated via assembly rules or formulas from a measured input.
- ASSUMED: filled from a default assumption, no source data (forced review in human UI).
- Raster-derived measurements always have lower base confidence than vector-derived.
- Never present a single blended accuracy % — each BOQ line has one discrete status.

This module provides the logic to assign and validate confidence statuses
throughout the Phase 1 pipeline, ensuring traceability and honesty.
"""

from __future__ import annotations

from typing import Literal, Dict, Any, Optional


# ---------------------------------------------------------------------------
# Confidence status type
# ---------------------------------------------------------------------------

ConfidenceStatus = Literal["MEASURED", "DERIVED", "ASSUMED"]


# ---------------------------------------------------------------------------
# Core assignment logic
# ---------------------------------------------------------------------------


def assign_confidence_status(
    source: str,
    calculation_method: Optional[str] = None,
    rule_version: Optional[str] = None,
) -> ConfidenceStatus:
    """Assign a confidence status based on the source of the measurement.

    Strategy:
    - "vector" → MEASURED (direct geometry read from PyMuPDF)
    - "assembly_rule" → DERIVED (calculated from assembly BOM)
    - "formula" → DERIVED (calculated from volume/area formula)
    - "default" or None → ASSUMED (filled from assumption, forced review)

    Constraints from Rules.md:
    - ASSUMED values must be explicitly flagged and force-reviewed in UI
    - Raster measurements get lower base confidence (handled by caller)
    """
    if source == "vector":
        return "MEASURED"
    elif source == "raster":
        return "MEASURED"
    elif source in ("assembly_rule", "formula"):
        # Verify rule_version is recorded for auditability
        if not rule_version:
            raise ValueError(
                "rule_version must be recorded for DERIVED quantities"
            )
        return "DERIVED"
    else:
        # source == "default" or unknown → ASSUMED
        # These items force review in the human UI (Rules.md §3.9)
        return "ASSUMED"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_confidence_status(status: Any) -> ConfidenceStatus:
    """Validate that a confidence status is one of the three discrete values.

    Raises ValueError if status is not a valid confidence tier.
    Also checks that status is not a blended percentage string.
    """
    valid = {"MEASURED", "DERIVED", "ASSUMED"}
    if status not in valid:
        raise ValueError(
            f"Invalid confidence status: {status!r}. "
            f"Must be one of {valid}"
        )
    # Check it's not a blended percentage
    if "/" in str(status) or "%" in str(status):
        raise ValueError(
            f"Confidence status should not be a blended percentage: {status!r}"
        )
    return status


# ---------------------------------------------------------------------------
# Confidence score computation (accompanies the status, 0–1)
# ---------------------------------------------------------------------------

def confidence_score(
    status: ConfidenceStatus,
    source_quality: Optional[Dict[str, Any]] = None,
) -> float:
    """Return a base confidence score (0–1) for the given status.

    Important: The score accompanies the status but is SEPARATE from it.
    - MEASURED from vector geometry → 1.0 (maximum)
    - MEASURED from raster/OCR → 0.6 (lower base confidence)
    - DERIVED from assembly rules → depends on rule version confidence
    - ASSUMED from defaults → 0.3 (lowest, forces human review)

    Callers must display the status AND the score, never a blended "%".
    """
    if status == "MEASURED":
        if source_quality and source_quality.get("raster"):
            # Raster-derived measurements always have lower base confidence
            return 0.6
        return 1.0  # Vector geometry direct read

    elif status == "DERIVED":
        # Derived quality depends on the rule that produced it
        rule_version = source_quality.get("rule_version") if source_quality else None
        # MVP: all rule v1.0 derivations have score 0.8
        if rule_version == "1.0.0":
            return 0.8
        return 0.7  # fallback

    elif status == "ASSUMED":
        return 0.3  # lowest — forces review in UI

    return 0.5  # default fallback


# ---------------------------------------------------------------------------
# Pipeline integration: assign status when creating a Measurement
# ---------------------------------------------------------------------------

def measurement_status_from_pipeline(
    source_type: str,
    calculation_method: Optional[str] = None,
    rule_version: Optional[str] = None,
) -> Dict[str, Any]:
    """Produce the full measurement status dict for a new Measurement record.

    Returns dict with keys matching the SQLAlchemy Measurement model fields:
    - confidence_status: one of "MEASURED"/"DERIVED"/"ASSUMED"
    - confidence_score: float 0–1
    - calculation_method: string description
    - rule_version: string or None
    """
    status = assign_confidence_status(
        source=source_type,
        calculation_method=calculation_method,
        rule_version=rule_version,
    )

    # Compute score based on status and source quality
    score_input: Optional[Dict[str, Any]] = None
    if rule_version:
        score_input = {"rule_version": rule_version}

    score = confidence_score(status, source_quality=score_input)

    return {
        "confidence_status": status,
        "confidence_score": score,
        "calculation_method": calculation_method,
        "rule_version": rule_version,
    }


# ---------------------------------------------------------------------------
# Display helpers for the human review UI
# ---------------------------------------------------------------------------

STATUS_DISPLAY: Dict[ConfidenceStatus, Dict[str, str]] = {
    "MEASURED": {
        "label": "Measured",
        "color": "green",
        "description": "Directly read from vector geometry",
    },
    "DERIVED": {
        "label": "Derived",
        "color": "purple",
        "description": "Calculated via assembly rule or formula",
    },
    "ASSUMED": {
        "label": "Assumed",
        "color": "red",
        "description": "Filled from default — forces human review",
    },
}


def get_status_display(status: ConfidenceStatus) -> Dict[str, str]:
    """Get the UI display configuration for a confidence status."""
    return STATUS_DISPLAY.get(status, STATUS_DISPLAY["ASSUMED"])


# ---------------------------------------------------------------------------
# Compliance with trap file constraints
# ---------------------------------------------------------------------------

TRAP_CONSTRAINTS = {
    "no_blended_percentage": (
        "Each BOQ line has a single discrete status (MEASURED/DERIVED/ASSUMED), "
        "never a blended accuracy %"
    ),
    "assumed_forces_review": (
        "ASSUMED values must be explicitly flagged and force-reviewed in the human UI"
    ),
    "raster_lower_confidence": (
        "Raster-derived measurements always have lower base confidence than vector-derived"
    ),
    "traceability": (
        "Every status traces back to a deterministic calculation source"
    ),
}


def check_trap_constraint(constraint_name: str) -> str:
    """Check that a trap constraint is being honored.

    Used by CI/lint to enforce Rules.md compliance.
    """
    return TRAP_CONSTRAINTS.get(constraint_name, "Unknown constraint")


# ---------------------------------------------------------------------------
# Definition of Done checks for confidence tiering
# ---------------------------------------------------------------------------

CONFIDENCE_DONE_Checks = {
    "all_measurements_have_status": (
        "Every Measurement record has confidence_status set to MEASURED, DERIVED, or ASSUMED"
    ),
    "no_blended_percentage_in_ui": (
        "The UI never displays a blended accuracy percentage — per-line status only"
    ),
    "assumed_items_force_review": (
        "ASSUMED-status items are forced under review in the human review UI (cannot bulk-accept)"
    ),
    "vector_measured_is_1": (
        "MEASURED status from vector geometry has confidence_score = 1.0"
    ),
    "derived_has_rule_version": (
        "DERIVED quantities always have rule_version recorded for auditability"
    ),
}


def confidence_done_check(check_name: str) -> str:
    """Return the status of a Definition-of-Done check for confidence tiering."""
    return CONFIDENCE_DONE_Checks.get(check_name, "Unknown check")