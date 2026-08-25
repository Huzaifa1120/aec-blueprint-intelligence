"""Narration providers — deterministic template default + gated Anthropic adapter.

Constraints (spec v3 §4.9, AGENTS.md §1):
- TemplateNarrator is the always-available default; it renders payload numbers
  verbatim via str() — no rounding, no arithmetic, no invented values.
- AnthropicNarrator is import-gated: the SDK is NOT in pyproject.toml and is
  only activated when ANTHROPIC_API_KEY is set AND the package imports. Its
  prompt carries only the serialized payload plus an instruction that the
  model may not introduce numbers.
"""

from __future__ import annotations

import json
import logging
import os
import re
import typing
from typing import Protocol

try:  # optional runtime enhancement — mirrors the heavy-deps policy
    import anthropic
except ImportError:  # pragma: no cover - exercised implicitly when absent
    anthropic = None

logger = logging.getLogger(__name__)


class NarrationResult(typing.TypedDict):
    narrative: str
    provider: str  # "template" | "anthropic"


class NarratorProvider(Protocol):
    name: str

    def narrate(self, boq_payload: dict) -> NarrationResult: ...


_ANTHROPIC_SYSTEM_PROMPT = (
    "You are writing a scope-of-work narrative for a construction quantity "
    "takeoff estimate. You will receive a JSON payload of BOQ rows. You may "
    "not introduce numbers: every number in your output must be copied "
    "verbatim from the payload. Do not compute, round, sum, or convert any "
    "value. Do not add dates, prices, or counts that are not in the payload."
)


def _fmt(value: object) -> str:
    """Format a structured number verbatim — never round or recompute."""
    return str(value)


_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


class NumberVerbatimismError(RuntimeError):
    """Raised when a narrative contains a number not traceable to the payload."""


def _allowed_number_tokens(payload: object) -> set[str]:
    """Numeric strings traceable to the payload + structural row counts.

    A narrative number is legitimate only if it (a) is a payload number,
    (b) occurs inside a payload string (e.g. a size ref "600x400"), or
    (c) counts rows in a payload list. Nothing else may appear.
    """
    allowed: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, (int, float)):
            token = str(node)
            allowed.add(token)
            allowed.update(_NUM_RE.findall(token))  # e.g. scientific notation
            return
        if isinstance(node, str):
            allowed.update(_NUM_RE.findall(node))
            return
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            allowed.add(str(len(node)))
            for value in node:
                walk(value)

    walk(payload)
    return allowed


def verify_no_invented_numbers(narrative: str, boq_payload: dict) -> None:
    """Runtime guard: raise NumberVerbatimismError on any untraceable number.

    Enforcement floor for LLM-backed providers — prompt compliance is never
    trusted; the deterministic template remains the only unconditional output.
    """
    allowed = _allowed_number_tokens(boq_payload)
    for token in _NUM_RE.findall(narrative):
        if token not in allowed:
            raise NumberVerbatimismError(f"invented number {token}")


class TemplateNarrator:
    """Deterministic narrator: renders sections directly from payload rows."""

    name = "template"

    def narrate(self, boq_payload: dict) -> NarrationResult:
        materials: list[dict] = boq_payload.get("materials") or []
        routes: list[dict] = boq_payload.get("routes") or []
        totals: dict = boq_payload.get("totals") or {}

        priced = [m for m in materials if not m.get("unpriced")]
        unpriced = [m for m in materials if m.get("unpriced")]

        lines: list[str] = ["SCOPE OF WORK", "", "Summary"]
        lines.append(f"- Material line items: {len(materials)}")
        if "grand" in totals:
            lines.append(f"- Grand total cost: {_fmt(totals['grand'])}")

        lines.extend(["", "Materials"])
        if not priced and not unpriced:
            lines.append("- No material line items recorded.")
        for item in priced:
            label = item.get("material_name") or "unnamed item"
            parts = [f"- {label}: quantity {_fmt(item['quantity'])}"]
            if item.get("total_cost") is not None:
                parts.append(f"total cost {_fmt(item['total_cost'])}")
            lines.append(", ".join(parts) + ".")

        if routes:
            lines.extend(["", "Measured Routes"])
            for route in routes:
                label = route.get("route_type") or "route"
                length = route.get("length_m")
                if length is None:
                    continue
                detail = f"- {label}: length {_fmt(length)} m"
                if not route.get("unpriced") and route.get("total_cost") is not None:
                    detail += f", total cost {_fmt(route['total_cost'])}"
                size_json = route.get("size_json")
                if isinstance(size_json, dict):
                    ref = size_json.get("ref")
                    if ref:
                        detail += f" (size ref {ref})"
                lines.append(detail + ".")

        if totals:
            lines.extend(["", "Labor"])
            if "labor" in totals:
                lines.append(f"- Total labor cost: {_fmt(totals['labor'])}")
            else:
                lines.append("- No labor costs recorded.")

        if unpriced:
            lines.extend(["", "Unpriced Items"])
            for item in unpriced:
                label = item.get("material_name") or "unnamed item"
                lines.append(f"- {label}: UNPRICED - review required.")

        scale = boq_payload.get("scale") or {}
        counters = [
            (name, value)
            for name, value in (boq_payload.get("data_quality") or {}).items()
            if isinstance(value, int) and not isinstance(value, bool) and value != 0
        ]
        if scale.get("status") == "assumed" or counters:
            lines.extend(["", "Assumptions & Data Quality"])
            if scale.get("status") == "assumed":
                scale_value = scale.get("value")
                if scale_value:
                    lines.append(
                        f"- Scale assumed ({scale_value}): verify against the source drawing."
                    )
                else:
                    lines.append("- Scale assumed: no scale parsed from the drawing.")
            for name, count in counters:
                lines.append(f"- {name}: {_fmt(count)}")

        return {"narrative": "\n".join(lines), "provider": self.name}


class AnthropicNarrator:
    """LLM-assisted narration; prompt forbids introducing any number."""

    name = "anthropic"

    def __init__(self, client: object | None = None, model: str = "claude-sonnet-4-5") -> None:
        self._client = client
        self._model = model

    def _call_client(self, system: str, prompt: str) -> str:
        if self._client is None:
            if anthropic is None:
                raise RuntimeError("anthropic SDK not installed")
            self._client = anthropic.Anthropic()
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content)

    def narrate(self, boq_payload: dict) -> NarrationResult:
        payload_json = json.dumps(boq_payload, indent=2, sort_keys=True)
        prompt = (
            "Write a concise scope-of-work narrative from the payload below. "
            "You may not introduce numbers; copy every number verbatim.\n\n"
            f"{payload_json}"
        )
        narrative = self._call_client(_ANTHROPIC_SYSTEM_PROMPT, prompt)
        return {"narrative": narrative, "provider": self.name}


_KEY_ABSENT_LOGGED = False


def get_provider() -> NarratorProvider:
    """Anthropic iff env key set AND sdk importable, else template."""
    global _KEY_ABSENT_LOGGED
    if os.environ.get("ANTHROPIC_API_KEY") and anthropic is not None:
        return AnthropicNarrator()
    if not os.environ.get("ANTHROPIC_API_KEY") and not _KEY_ABSENT_LOGGED:
        # Honesty log (fix-wave F8): state once per process WHY narration is
        # template-pinned; behavior itself stays deterministic per request.
        logger.info(
            "anthropic key absent - template narration pinned for process"
        )
        _KEY_ABSENT_LOGGED = True
    return TemplateNarrator()
