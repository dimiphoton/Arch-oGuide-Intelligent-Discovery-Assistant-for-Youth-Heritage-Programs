"""Tests unitaires du scraper."""

from pathlib import Path

import pytest

from scrapping.config import LATEST_PDF_NAME
from scrapping.scraper import needs_download, parse_page

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "culture_page.html"


@pytest.fixture
def page_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parse_page_extracts_pub_date_and_pdf_url(page_html: str) -> None:
    result = parse_page(page_html)

    assert result["pub_date_iso"] == "2026-07-08"
    assert result["pub_date"] == "8 juillet 2026"
    assert "Fouiller" in result["pdf_url"]
    assert result["pdf_url"].endswith("version=314") or ".pdf" in result["pdf_url"]


def test_needs_download_when_pub_date_changes(page_html: str) -> None:
    page_info = parse_page(page_html)
    metadata = {"pub_date_iso": "2026-01-01", "pdf_url": page_info["pdf_url"]}

    assert needs_download(page_info, metadata, pdf_headers=None) is True


def test_needs_download_when_local_pdf_missing(page_html: str) -> None:
    page_info = parse_page(page_html)
    metadata = {
        "pub_date_iso": page_info["pub_date_iso"],
        "pdf_url": page_info["pdf_url"],
    }

    assert needs_download(page_info, metadata, pdf_headers=None) is True


def test_needs_download_skips_when_unchanged(page_html: str, tmp_path: Path, monkeypatch) -> None:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / LATEST_PDF_NAME).write_bytes(b"fake-pdf")

    import scrapping.scraper as scraper_module

    monkeypatch.setattr(scraper_module, "PDF_DIR", pdf_dir)

    page_info = parse_page(page_html)
    metadata = {
        "pub_date_iso": page_info["pub_date_iso"],
        "pdf_url": page_info["pdf_url"],
        "etag": '"abc123"',
        "last_modified": "Wed, 08 Jul 2026 00:00:00 GMT",
        "content_length": 13631488,
    }
    pdf_headers = {
        "etag": '"abc123"',
        "last_modified": "Wed, 08 Jul 2026 00:00:00 GMT",
        "content_length": 13631488,
    }

    assert needs_download(page_info, metadata, pdf_headers) is False


def test_needs_download_force_bypasses_checks(page_html: str) -> None:
    page_info = parse_page(page_html)
    metadata = {
        "pub_date_iso": page_info["pub_date_iso"],
        "pdf_url": page_info["pdf_url"],
    }

    assert needs_download(page_info, metadata, pdf_headers=None, force=True) is True
