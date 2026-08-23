"""Phase 3: generated HVAC fixture produces a layer-rich, parseable PDF."""

import pymupdf

from tests.fixtures.make_hvac_fixture import build_hvac_fixture


class TestHvacFixture:
    def test_builds_and_reports_expectations(self, tmp_path):
        pdf_path = str(tmp_path / "hvac_fixture.pdf")
        expected = build_hvac_fixture(pdf_path)
        assert expected["scale"] == "1:100"
        assert expected["equipment_count"] >= 2

    def test_pdf_has_ocg_layers(self, tmp_path):
        pdf_path = str(tmp_path / "hvac_fixture.pdf")
        build_hvac_fixture(pdf_path)
        doc = pymupdf.open(pdf_path)
        layer_names = {ocgs[k].get("name") for ocgs in [doc.get_ocgs()] for k in ocgs}
        assert {"M-DUCT", "M-DUCT-RND", "M-PIPE", "M-EQPT-NEW"} <= layer_names
        doc.close()

    def test_pdf_has_vector_content_and_text(self, tmp_path):
        pdf_path = str(tmp_path / "hvac_fixture.pdf")
        build_hvac_fixture(pdf_path)
        doc = pymupdf.open(pdf_path)
        page = doc[0]
        assert len(page.get_drawings()) > 20
        text = page.get_text()
        assert "600x400" in text
        assert "DUCT SIZE" in text
        doc.close()
