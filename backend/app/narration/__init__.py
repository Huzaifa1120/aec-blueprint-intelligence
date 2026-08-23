"""Scope-of-work narration (spec v3 §7.14 / G8).

Providers turn a persisted BOQ payload into a human-readable narrative.
The narrator formats structured numbers VERBATIM only — it never computes,
rounds, or invents a quantity, length, area, or price (AGENTS.md §1).
"""

from app.narration.providers import (
    AnthropicNarrator,
    NarrationResult,
    NarratorProvider,
    TemplateNarrator,
    get_provider,
)

__all__ = [
    "AnthropicNarrator",
    "NarrationResult",
    "NarratorProvider",
    "TemplateNarrator",
    "get_provider",
]
