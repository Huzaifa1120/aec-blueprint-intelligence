"""Narrator (G8) — scope-of-work narration tests.

Exit gate: the number-verbatimism guard. A narrator may format structured
numbers VERBATIM only; it may never compute or invent a number. Every digit
in the template narrative must trace to the BOQ payload (row values or row
counts).
"""

from __future__ import annotations

import json
import re
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.estimate import BoqItem, Estimate, Measurement
from app.db.models.geometry import Component, Route
from app.db.models.project import Drawing, Project, Sheet
import app.narration.router as narration_router_module
from app.db.session import get_db
from app.estimates.payload import payload_from_estimate
from app.narration.providers import (
    AnthropicNarrator,
    NarrationResult,
    NumberVerbatimismError,
    TemplateNarrator,
    get_provider,
    verify_no_invented_numbers,
)
from app.narration.router import router as narration_router

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


# ---------------------------------------------------------------------------
# Payload fixtures
# ---------------------------------------------------------------------------
def _small_payload() -> dict:
    """Quantities {12.5, 3.0}; totals {87.5}; one route, one material line."""
    return {
        "estimate_id": "00000000-0000-0000-0000-000000000001",
        "totals": {"materials": 87.5, "grand": 87.5},
        "routes": [
            {
                "route_type": "duct_rectangular",
                "length_m": 12.5,
                "size_json": None,
                "confidence_status": "MEASURED",
                "material_name": "Rectangular duct",
                "quantity": 12.5,
                "unit_cost": 7.0,
                "total_cost": 87.5,
                "unpriced": False,
                "size_source": "schedule",
            }
        ],
        "materials": [
            {
                "material_name": "Duct sealant",
                "quantity": 3.0,
                "unit_cost": 2.5,
                "total_cost": 7.5,
                "unpriced": False,
                "confidence_status": "MEASURED",
                "size_source": None,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Template narrator — sections
# ---------------------------------------------------------------------------
def test_template_renders_required_sections():
    res = TemplateNarrator().narrate(_small_payload())
    assert res["provider"] == "template"
    assert "Summary" in res["narrative"]
    assert "Materials" in res["narrative"]
    assert "87.5" in res["narrative"]
    assert "Duct sealant" in res["narrative"]


def test_template_renders_labor_section_from_totals_only():
    payload = _small_payload()
    payload["totals"]["labor"] = 42.0
    res = TemplateNarrator().narrate(payload)
    assert "Labor" in res["narrative"]
    assert "42.0" in res["narrative"]


def test_template_empty_payload_is_safe():
    res = TemplateNarrator().narrate(
        {"estimate_id": "e1", "totals": {}, "routes": [], "materials": []}
    )
    assert res["provider"] == "template"
    assert "Summary" in res["narrative"]


# ---------------------------------------------------------------------------
# Number-verbatimism guard (EXIT GATE)
# ---------------------------------------------------------------------------
def test_no_invented_numbers():
    payload = _small_payload()
    res = TemplateNarrator().narrate(payload)
    # Allowed: payload numbers verbatim + structural row counts only.
    allowed = (
        {"12.5", "3.0", "7.5", "87.5"}
        | {str(len(payload["materials"]))}
        | {str(len(payload["routes"]))}
    )
    for n in _NUM_RE.findall(res["narrative"]):
        assert n in allowed, f"invented number {n}"


def test_unpriced_flagged_never_zero_substituted():
    payload = _small_payload()
    payload["materials"].append(
        {
            "material_name": "Mystery bracket",
            "quantity": 3.0,
            "unit_cost": 0.0,
            "total_cost": 0.0,
            "unpriced": True,
            "confidence_status": "MEASURED",
            "size_source": None,
        }
    )
    res = TemplateNarrator().narrate(payload)
    assert "UNPRICED" in res["narrative"]
    assert "Mystery bracket" in res["narrative"]
    assert "review required" in res["narrative"].lower()


def test_verbatim_formatting_preserves_float_representation():
    payload = _small_payload()
    res = TemplateNarrator().narrate(payload)
    # str() of the payload floats — no rounding, no reformatting.
    assert "12.5" in res["narrative"]
    assert "3.0" in res["narrative"]
    assert "87.5" in res["narrative"]
    assert "12.50" not in res["narrative"]
    assert "3.00" not in res["narrative"]


# ---------------------------------------------------------------------------
# Anthropic adapter — stubbed client seam, SDK never invoked
# ---------------------------------------------------------------------------
class _FakeBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeMessages:
    def __init__(self, recorder: list[dict], text: str) -> None:
        self._recorder = recorder
        self._text = text

    def create(self, **kwargs):
        self._recorder.append(kwargs)
        return SimpleNamespace(content=[_FakeBlock(self._text)])


class _FakeClient:
    def __init__(self, text: str) -> None:
        self.calls: list[dict] = []
        self.messages = _FakeMessages(self.calls, text)


def test_anthropic_adapter_uses_injected_client_and_returns_result():
    fake = _FakeClient("Narrative without new digits.")
    narrator = AnthropicNarrator(client=fake)
    res: NarrationResult = narrator.narrate(_small_payload())
    assert res["provider"] == "anthropic"
    assert res["narrative"] == "Narrative without new digits."
    assert len(fake.calls) == 1
    sent_prompt = fake.calls[0]["messages"][0]["content"]
    # Prompt carries ONLY serialized payload + the verbatim-only instruction.
    assert '"quantity": 3.0' in sent_prompt
    assert "may not introduce numbers" in sent_prompt.lower()
    assert fake.calls[0]["system"]


def test_anthropic_adapter_raises_without_sdk_and_client(monkeypatch):
    import app.narration.providers as providers_module

    monkeypatch.setattr(providers_module, "anthropic", None)
    with pytest.raises(RuntimeError):
        AnthropicNarrator()._call_client("sys", "prompt")


def test_anthropic_model_configurable_via_constructor():
    fake = _FakeClient("ok")
    AnthropicNarrator(client=fake, model="test-model").narrate(_small_payload())
    assert fake.calls[0]["model"] == "test-model"


# ---------------------------------------------------------------------------
# Runtime numeric verification (verbatimism gate on the LLM path)
# ---------------------------------------------------------------------------
def test_verify_rejects_invented_number():
    with pytest.raises(NumberVerbatimismError, match="42.7"):
        verify_no_invented_numbers("Total run is 42.7 m long.", _small_payload())


def test_verify_accepts_payload_numbers_counts_and_string_embedded_digits():
    payload = _small_payload()
    payload["routes"][0]["size_json"] = {"width_mm": 600, "height_mm": 400, "ref": "600x400"}
    narrative = (
        "Summary: 1 material line item and 1 measured route; grand total 87.5. "
        "Duct run 12.5 m at size ref 600x400; sealant quantity 3.0."
    )
    verify_no_invented_numbers(narrative, payload)  # must not raise


def test_verify_rejects_computed_total_not_in_payload():
    payload = _small_payload()
    payload["totals"].pop("grand")
    with pytest.raises(NumberVerbatimismError):
        verify_no_invented_numbers("Grand total cost: 95.0.", payload)


def test_endpoint_anthropic_invented_number_falls_back_to_template(api, monkeypatch):
    client, session = api
    estimate_id = _seed_estimate(session)
    fake = _FakeClient("Scope narrative citing invented value 42.7 metres.")
    monkeypatch.setattr(
        narration_router_module,
        "get_provider",
        lambda: AnthropicNarrator(client=fake),
    )

    resp = client.get(f"/api/narration/estimates/{estimate_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "template"
    # Narrative is exactly the template's deterministic output for the payload.
    payload = payload_from_estimate(session.get(Estimate, estimate_id))
    assert body["narrative"] == TemplateNarrator().narrate(payload)["narrative"]
    assert "42.7" not in body["narrative"]


def test_endpoint_anthropic_compliant_narrative_passes_through(api, monkeypatch):
    client, session = api
    estimate_id = _seed_estimate(session)
    compliant = "Scope: duct run of 12.5 m and sealant quantity 3.0; grand total cost 95.0."
    fake = _FakeClient(compliant)
    monkeypatch.setattr(
        narration_router_module,
        "get_provider",
        lambda: AnthropicNarrator(client=fake),
    )

    resp = client.get(f"/api/narration/estimates/{estimate_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "anthropic"
    assert body["narrative"] == compliant


# ---------------------------------------------------------------------------
# Provider selection — anthropic iff env key set AND sdk importable
# ---------------------------------------------------------------------------
def test_get_provider_defaults_to_template(monkeypatch):
    import app.narration.providers as providers_module

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(providers_module, "anthropic", None)
    assert isinstance(get_provider(), TemplateNarrator)


def test_get_provider_template_when_key_set_but_sdk_missing(monkeypatch):
    import app.narration.providers as providers_module

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(providers_module, "anthropic", None)
    assert isinstance(get_provider(), TemplateNarrator)


def test_get_provider_anthropic_when_key_and_sdk_present(monkeypatch):
    import app.narration.providers as providers_module

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(providers_module, "anthropic", SimpleNamespace(Anthropic=object))
    provider = get_provider()
    assert isinstance(provider, AnthropicNarrator)
    assert provider.name == "anthropic"


# ---------------------------------------------------------------------------
# Narration endpoint — ORM-backed payload, 404, template fallback
# ---------------------------------------------------------------------------
@pytest.fixture()
def api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    app = FastAPI()
    app.include_router(narration_router)
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app), session
    session.close()


def _seed_estimate(session: Session) -> uuid.UUID:
    project = Project(name="P")
    drawing = Drawing(project=project)
    sheet = Sheet(drawing=drawing, name="S-1")
    route = Route(sheet=sheet, route_type="duct_rectangular", length_m=12.5)
    component = Component(sheet=sheet, component_type="lighting_outlet", x=1.0, y=2.0)

    meas_route = Measurement(
        route=route,
        source_sheet="S-1",
        source_region="full",
        measurement_type="route_length",
        raw_value=12.5,
        final_value=12.5,
    )
    meas_count = Measurement(
        component=component,
        source_sheet="S-1",
        source_region="symbol",
        measurement_type="count",
        raw_value=3.0,
        final_value=3.0,
    )
    estimate = Estimate(
        project=project,
        total_material_cost=95.0,
        total_labor_cost=0.0,
        total_cost=95.0,
    )
    session.add_all(
        [
            BoqItem(
                measurement=meas_route,
                estimate=estimate,
                quantity=12.5,
                unit_cost=7.0,
                total_cost=87.5,
                derivation_json=json.dumps({"linear_per_m": 7.0, "inputs": {"length_m": 12.5}}),
                size_source="schedule",
            ),
            BoqItem(
                measurement=meas_count,
                estimate=estimate,
                quantity=3.0,
                unit_cost=2.5,
                total_cost=7.5,
            ),
        ]
    )
    session.commit()
    return estimate.id


def test_endpoint_returns_template_narration_for_persisted_boq(api):
    client, session = api
    estimate_id = _seed_estimate(session)
    resp = client.get(f"/api/narration/estimates/{estimate_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "template"
    assert body["estimate_id"] == str(estimate_id)
    # Numbers rendered verbatim from persisted rows.
    assert "12.5" in body["narrative"]
    assert "3.0" in body["narrative"]
    assert "87.5" in body["narrative"]


def test_endpoint_payload_carries_route_metadata(api):
    """Router-side payload must match the /boq contract shape."""
    client, session = api
    estimate_id = _seed_estimate(session)
    payload = payload_from_estimate(session.get(Estimate, estimate_id))
    assert payload["routes"][0]["route_type"] == "duct_rectangular"
    assert payload["routes"][0]["length_m"] == 12.5
    assert payload["totals"]["grand"] == 95.0
    material_names = [m["material_name"] for m in payload["materials"]]
    assert any("lighting_outlet" in name for name in material_names)


def test_endpoint_404_on_unknown_estimate(api):
    client, _ = api
    unknown = uuid.uuid4()
    resp = client.get(f"/api/narration/estimates/{unknown}")
    assert resp.status_code == 404


def test_endpoint_unpriced_line_flagged_in_narration(api):
    client, session = api
    project = Project(name="P")
    drawing = Drawing(project=project)
    sheet = Sheet(drawing=drawing, name="S-1")
    component = Component(sheet=sheet, component_type="mystery_bracket", x=0.0, y=0.0)
    meas = Measurement(
        component=component,
        source_sheet="S-1",
        source_region="symbol",
        measurement_type="count",
        raw_value=3.0,
        final_value=3.0,
    )
    estimate = Estimate(project=project, total_cost=0.0)
    session.add_all(
        [
            BoqItem(
                measurement=meas,
                estimate=estimate,
                quantity=3.0,
                unit_cost=0.0,
                total_cost=0.0,
            )
        ]
    )
    session.commit()

    resp = client.get(f"/api/narration/estimates/{estimate.id}")
    assert resp.status_code == 200
    assert "UNPRICED" in resp.json()["narrative"]


def test_endpoint_falls_back_to_template_on_provider_exception(api, monkeypatch):
    client, session = api
    estimate_id = _seed_estimate(session)

    class _ExplodingProvider:
        name = "exploding"

        def narrate(self, boq_payload: dict) -> NarrationResult:
            raise RuntimeError("provider down")

    monkeypatch.setattr(narration_router_module, "get_provider", lambda: _ExplodingProvider())
    resp = client.get(f"/api/narration/estimates/{estimate_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "template"
    assert "87.5" in body["narrative"]
