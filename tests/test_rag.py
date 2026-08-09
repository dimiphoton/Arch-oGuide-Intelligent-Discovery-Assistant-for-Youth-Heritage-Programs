"""Tests du pipeline RAG (sans appels API)."""

from unittest.mock import MagicMock, patch

from rag.generate import format_context
from rag.pipeline import ask
from rag.types import RetrievedChunk


def test_format_context_includes_pages() -> None:
    chunks = [
        RetrievedChunk(text="Chantier en Bretagne", page_number=5, score=0.9, source="test.pdf"),
        RetrievedChunk(text="Visite en Normandie", page_number=12, score=0.8, source="test.pdf"),
    ]
    context = format_context(chunks)

    assert "p. 5" in context
    assert "p. 12" in context
    assert "Bretagne" in context


@patch("rag.pipeline.generate_answer")
@patch("rag.pipeline.search")
def test_ask_returns_response(mock_search: MagicMock, mock_generate: MagicMock) -> None:
    mock_search.return_value = [
        RetrievedChunk(text="Info chantier", page_number=1, score=0.95, source="test.pdf"),
    ]
    mock_generate.return_value = "Voici un chantier en Bretagne."

    response = ask(
        "Chantiers en Bretagne ?",
        rewrite=False,
        rerank=False,
        log=False,
    )

    assert response.question == "Chantiers en Bretagne ?"
    assert "Bretagne" in response.answer
    assert len(response.sources) == 1
    mock_search.assert_called_once()
    mock_generate.assert_called_once()
