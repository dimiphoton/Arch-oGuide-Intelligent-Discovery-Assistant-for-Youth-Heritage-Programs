"""Tests des métriques d'évaluation retrieval."""

from eval.metrics import EvalQuery, hit_rate_at_k, is_relevant, reciprocal_rank
from rag.types import RetrievedChunk


def test_is_relevant_by_keyword() -> None:
    query = EvalQuery(id="q1", question="test", expected_keywords=["Bretagne"])
    chunk = RetrievedChunk(text="Chantier en Bretagne", page_number=1, score=0.9, source="x.pdf")
    assert is_relevant(chunk, query) is True


def test_is_relevant_miss() -> None:
    query = EvalQuery(id="q1", question="test", expected_keywords=["Corse"])
    chunk = RetrievedChunk(text="Chantier en Bretagne", page_number=1, score=0.9, source="x.pdf")
    assert is_relevant(chunk, query) is False


def test_hit_rate_at_k() -> None:
    query = EvalQuery(id="q1", question="test", expected_keywords=["Bretagne"])
    results = [
        RetrievedChunk(text="Paris", page_number=1, score=0.5, source="x.pdf"),
        RetrievedChunk(text="Bretagne fouilles", page_number=2, score=0.4, source="x.pdf"),
    ]
    assert hit_rate_at_k(results, query, k=2) == 1.0
    assert hit_rate_at_k(results, query, k=1) == 0.0


def test_reciprocal_rank() -> None:
    query = EvalQuery(id="q1", question="test", expected_keywords=["Bretagne"])
    results = [
        RetrievedChunk(text="Paris", page_number=1, score=0.5, source="x.pdf"),
        RetrievedChunk(text="Bretagne", page_number=2, score=0.4, source="x.pdf"),
    ]
    assert reciprocal_rank(results, query) == 0.5
