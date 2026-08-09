"""Tests query rewrite et rerank (sans appels API)."""

from unittest.mock import MagicMock, patch

from rag.pipeline import ask
from rag.rerank import _parse_ranking, rerank_chunks
from rag.types import RetrievedChunk


def test_parse_ranking_valid_json() -> None:
    raw = '{"ranking": [2, 1, 3]}'
    assert _parse_ranking(raw, num_chunks=3) == [2, 1, 3]


def test_parse_ranking_fallback_on_invalid() -> None:
    assert _parse_ranking("pas du json", num_chunks=3) == [1, 2, 3]


@patch("rag.rerank.get_openai_client")
def test_rerank_reorders_chunks(mock_client: MagicMock) -> None:
    mock_oai = MagicMock()
    mock_client.return_value = mock_oai
    mock_oai.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"ranking": [2, 1]}'))]
    )

    chunks = [
        RetrievedChunk(chunk_id="a", text="A", page_number=1, score=0.5, source="x"),
        RetrievedChunk(chunk_id="b", text="B", page_number=2, score=0.9, source="x"),
    ]

    result = rerank_chunks("question", chunks, top_k=2, settings=MagicMock())

    assert result[0].text == "B"
    assert result[1].text == "A"


@patch("rag.pipeline.generate_answer")
@patch("rag.pipeline.rerank_chunks")
@patch("rag.pipeline.search")
@patch("rag.pipeline.rewrite_query")
def test_ask_with_rewrite_and_rerank(
    mock_rewrite: MagicMock,
    mock_search: MagicMock,
    mock_rerank: MagicMock,
    mock_generate: MagicMock,
) -> None:
    mock_rewrite.return_value = "question reformulée Bretagne bénévole"
    mock_search.return_value = [
        RetrievedChunk(text="chunk1", page_number=1, score=0.8, source="x"),
        RetrievedChunk(text="chunk2", page_number=2, score=0.7, source="x"),
    ]
    mock_rerank.return_value = [
        RetrievedChunk(text="chunk2", page_number=2, score=2.0, source="x"),
    ]
    mock_generate.return_value = "Réponse test."

    response = ask("Bretagne ?", settings=MagicMock(enable_query_rewrite=True, enable_rerank=True, top_k=1))

    mock_rewrite.assert_called_once()
    mock_search.assert_called_once()
    mock_rerank.assert_called_once()
    assert response.rewritten_query == "question reformulée Bretagne bénévole"
    assert len(response.sources) == 1
