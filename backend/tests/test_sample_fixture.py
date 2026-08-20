from pathlib import Path

import pymupdf

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
)


def test_sample_fixture_vector_metadata() -> None:
    assert SAMPLE.exists()
    doc = pymupdf.open(SAMPLE)
    try:
        assert doc.page_count == 1
        page = doc[0]
        assert len(page.get_drawings()) > 10000
        assert len(page.get_images(full=True)) == 2
        ocgs = doc.get_ocgs()
        assert len(ocgs) == 46
        names = [v["name"] for v in ocgs.values()]
        assert "access control" in names
    finally:
        doc.close()