"""Input Quality Gate tests (spec v3 §7.2)."""

from pathlib import Path

import pymupdf

from app.ingestion.quality_gate import (
    VERDICT_DEGRADED,
    VERDICT_LAYERED,
    assess_quality,
)
from app.ingestion.router import classify_upload

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
)


def _make_pdf(tmp_path: Path, *, layered: bool) -> Path:
    """Deterministic synthetic fixture: identical shapes, OCGs only if layered."""
    doc = pymupdf.open()
    page = doc.new_page()
    ocgs = []
    if layered:
        ocgs = [doc.add_ocg(name, on=True) for name in ("E-LIGHT", "E-POWER", "E-SWITCH")]
    for i in range(12):
        x = 50 + i * 30
        oc = ocgs[i % 3] if ocgs else None
        page.draw_circle((x, 200), radius=5, oc=oc)
        page.draw_rect(pymupdf.Rect(x - 5, 300, x + 5, 310), oc=oc)
        page.insert_text((x, 400), f"S{i}")
    out = tmp_path / ("layered.pdf" if layered else "flattened.pdf")
    doc.save(str(out))
    doc.close()
    return out


def test_layered_synthetic_passes_gate(tmp_path):
    path = _make_pdf(tmp_path, layered=True)
    result = assess_quality(str(path))
    assert result["verdict"] == VERDICT_LAYERED


def test_flattened_synthetic_flagged_degraded(tmp_path):
    path = _make_pdf(tmp_path, layered=False)
    result = assess_quality(str(path))
    assert result["verdict"] == VERDICT_DEGRADED
    assert "re-export" in result["loop_back_message"].lower()


def _make_flattened_vector_twin(tmp_path: Path) -> Path:
    """True flattened VECTOR twin of the REAL sample (Phases.md item 1):
    same shapes redrawn with no OCG definitions and no layer attributes —
    the print-to-PDF / discard-hidden-layers effect. Stays vector, loses
    layer data ⇒ the exact case degraded_vector exists for.
    """
    src = pymupdf.open(str(SAMPLE))
    out = pymupdf.open()
    for page in src:
        new_page = out.new_page(width=page.rect.width, height=page.rect.height)
        shape = new_page.new_shape()
        for d in page.get_drawings():
            for item in d.get("items", []):
                kind = item[0]
                if kind == "l":
                    shape.draw_line(item[1], item[2])
                elif kind == "re":
                    shape.draw_rect(item[1])
                elif kind == "c":
                    shape.draw_bezier(item[1], item[2], item[3], item[4])
                # 'qu' quads skipped: cosmetic, not needed to prove the gate
        shape.commit()
    path = tmp_path / "flattened_vector_twin.pdf"
    out.save(str(path))
    out.close()
    src.close()
    return path


def test_flattened_vector_twin_of_sample_flagged_degraded(tmp_path):
    """The gate must flag a flattened derivative of the REAL sheet."""
    path = _make_flattened_vector_twin(tmp_path)
    result = assess_quality(str(path))
    assert result["verdict"] == VERDICT_DEGRADED
    assert "re-export" in result["loop_back_message"].lower()


def test_real_sample_is_layered_vector():
    result = assess_quality(str(SAMPLE))
    assert result["verdict"] == VERDICT_LAYERED


def test_rasterized_twin_classified_raster(tmp_path):
    """Rasterize sample pages → binary router check must say raster."""
    doc = pymupdf.open(str(SAMPLE))
    flat = pymupdf.open()
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        new_page = flat.new_page(width=page.rect.width, height=page.rect.height)
        new_page.insert_image(new_page.rect, pixmap=pix)
    out = tmp_path / "raster_twin.pdf"
    flat.save(str(out))
    flat.close()
    doc.close()
    result = assess_quality(str(out))
    assert result["verdict"] == "raster"


def test_scoring_error_fails_closed(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 not really")
    result = assess_quality(str(bad))
    assert result["verdict"] == VERDICT_DEGRADED


def test_classify_upload_reports_source_quality():
    result = classify_upload(str(SAMPLE))
    assert result["status"] == "vector"
    assert result["source_quality"] == VERDICT_LAYERED
    assert result["degraded"] is False


def test_boq_line_applies_degraded_confidence_multiplier():
    """Spec §4a: degraded-file measurements carry lower base confidence."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as OrmSession

    from app.db.base import Base
    from app.e2e.router import _boq_line

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with OrmSession(engine) as session:
        normal = _boq_line("lighting_outlet", "Lamp", 2.0, "MEASURED", ["p1"], session)
        degraded = _boq_line("lighting_outlet", "Lamp", 2.0, "MEASURED", ["p1"], session,
                             source_quality="degraded_vector")
    assert normal["source_quality"] == "layered_vector"
    # contract change: spec conformance 2026-08-25 — BOQ lines are DERIVED (0.8), never MEASURED (1.0)
    assert normal["confidence_status"] == "DERIVED"
    assert normal["confidence_score"] == 0.8
    assert degraded["source_quality"] == "degraded_vector"
    # contract change: spec conformance 2026-08-25 — degraded multiplier composes: 0.8 * 0.8 = 0.64
    assert abs(degraded["confidence_score"] - 0.64) < 1e-9
