"""Métriques d'évaluation du retrieval."""

from __future__ import annotations

from dataclasses import dataclass

from rag.types import RetrievedChunk


@dataclass
class EvalQuery:
    """Question de référence pour l'évaluation."""

    id: str
    question: str
    expected_keywords: list[str]
    expected_pages: list[int] | None = None


def is_relevant(chunk: RetrievedChunk, query: EvalQuery) -> bool:
    """Un chunk est pertinent s'il contient un mot-clé attendu (ou page cible)."""
    text_lower = chunk.text.lower()

    for keyword in query.expected_keywords:
        if keyword.lower() in text_lower:
            return True

    if query.expected_pages and chunk.page_number in query.expected_pages:
        return True

    return False


def hit_rate_at_k(results: list[RetrievedChunk], query: EvalQuery, k: int) -> float:
    """1.0 si au moins un chunk pertinent dans le top-k, sinon 0.0."""
    top = results[:k]
    return 1.0 if any(is_relevant(chunk, query) for chunk in top) else 0.0


def reciprocal_rank(results: list[RetrievedChunk], query: EvalQuery) -> float:
    """RR du premier chunk pertinent (0 si aucun)."""
    for rank, chunk in enumerate(results, start=1):
        if is_relevant(chunk, query):
            return 1.0 / rank
    return 0.0


def aggregate_metrics(
    per_query_hits: list[float],
    per_query_rr: list[float],
) -> dict[str, float]:
    """Calcule les moyennes sur toutes les questions."""
    n = len(per_query_hits) or 1
    return {
        "hit_rate": sum(per_query_hits) / n,
        "mrr": sum(per_query_rr) / n,
        "num_queries": float(len(per_query_hits)),
    }
