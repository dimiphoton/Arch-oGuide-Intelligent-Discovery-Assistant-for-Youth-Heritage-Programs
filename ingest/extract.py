"""Extraction de texte depuis le PDF source."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class PageText:
    """Texte extrait d'une page du PDF."""

    page_number: int  # 1-indexed
    text: str


def extract_pdf(pdf_path: Path) -> list[PageText]:
    """Extrait le texte page par page depuis un PDF."""
    if not pdf_path.exists():
        msg = f"PDF introuvable : {pdf_path}"
        raise FileNotFoundError(msg)

    pages: list[PageText] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append(PageText(page_number=index, text=text))

    if not pages:
        msg = f"Aucun texte extrait du PDF : {pdf_path}"
        raise ValueError(msg)

    return pages
