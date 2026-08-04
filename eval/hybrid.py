"""Fusion hybride BM25 + recherche vectorielle (RRF)."""

from __future__ import annotations

from rag.types import RetrievedChunk


def reciprocal_rank_fusion(
    rankings: list[list[RetrievedChunk]],
    top_k: int = 5,
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    """
    Fusionne plusieurs classements via Reciprocal Rank Fusion (RRF).

    rrf_k : constante de lissage (60 est une valeur courante).
    """
    scores: dict[str, float] = {}
    chunk_map: dict[str, RetrievedChunk] = {}

    for ranking in rankings:
        for rank, chunk in enumerate(ranking):
            chunk_id = chunk.chunk_id or chunk.text[:80]
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank + 1)
            chunk_map[chunk_id] = chunk

    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    fused: list[RetrievedChunk] = []
    for chunk_id in sorted_ids[:top_k]:
        base = chunk_map[chunk_id]
        fused.append(
            RetrievedChunk(
                chunk_id=base.chunk_id,
                text=base.text,
                page_number=base.page_number,
                score=scores[chunk_id],
                source=base.source,
            )
        )
    return fused
