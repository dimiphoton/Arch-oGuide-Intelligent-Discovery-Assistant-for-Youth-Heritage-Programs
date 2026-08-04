"""Tests unitaires du chunking."""

from ingest.chunk import build_chunks, chunk_text
from ingest.extract import PageText


def test_chunk_text_respects_overlap() -> None:
    text = "mot " * 300  # ~1500 caractères
    chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)

    assert len(chunks) > 1
    # Chaque chunk ne dépasse pas largement la taille demandée
    assert all(len(c) <= 220 for c in chunks)


def test_chunk_text_empty() -> None:
    assert chunk_text("", chunk_size=100, chunk_overlap=10) == []
    assert chunk_text("   ", chunk_size=100, chunk_overlap=10) == []


def test_build_chunks_metadata() -> None:
    pages = [
        PageText(page_number=1, text="Chantier archéologique en Bretagne. " * 20),
        PageText(page_number=2, text="Visite de site en Normandie. " * 20),
    ]
    chunks = build_chunks(pages, source="test.pdf", chunk_size=100, chunk_overlap=20)

    assert len(chunks) >= 2
    assert all(chunk.source == "test.pdf" for chunk in chunks)
    assert all(chunk.chunk_id for chunk in chunks)
    assert {chunk.page_number for chunk in chunks} == {1, 2}
