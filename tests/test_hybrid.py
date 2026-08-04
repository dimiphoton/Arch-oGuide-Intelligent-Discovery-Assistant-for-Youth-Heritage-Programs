"""Tests de la fusion hybride RRF."""

from eval.hybrid import reciprocal_rank_fusion
from rag.types import RetrievedChunk


def test_rrf_prefers_docs_in_both_rankings() -> None:
    chunk_a = RetrievedChunk(chunk_id="a", text="A", page_number=1, score=0.9, source="x")
    chunk_b = RetrievedChunk(chunk_id="b", text="B", page_number=2, score=0.8, source="x")
    chunk_c = RetrievedChunk(chunk_id="c", text="C", page_number=3, score=0.7, source="x")

    ranking1 = [chunk_a, chunk_b, chunk_c]
    ranking2 = [chunk_b, chunk_a, chunk_c]

    fused = reciprocal_rank_fusion([ranking1, ranking2], top_k=2)

    assert len(fused) == 2
    # b et a apparaissent en tête dans les deux listes
    top_ids = {c.chunk_id for c in fused}
    assert top_ids == {"a", "b"}
