"""Recherche vectorielle, BM25 et hybride dans Qdrant."""

from __future__ import annotations

import logging
from typing import Literal

from openai import OpenAI
from qdrant_client import QdrantClient

from eval.bm25 import BM25Index
from eval.corpus import load_corpus
from eval.hybrid import reciprocal_rank_fusion
from ingest.embed import embed_texts, get_openai_client
from ingest.index import get_qdrant_client
from rag.config import Settings, get_settings
from rag.filters import MetadataFilter
from rag.types import RetrievedChunk

logger = logging.getLogger(__name__)

RetrievalMode = Literal["vector", "bm25", "hybrid"]

# Cache BM25 en mémoire (reconstruit si la collection change)
_bm25_cache: BM25Index | None = None
_bm25_cache_size: int = 0


def _get_bm25_index(settings: Settings, qdrant: QdrantClient) -> BM25Index:
    """Construit ou réutilise l'index BM25 depuis Qdrant."""
    global _bm25_cache, _bm25_cache_size

    chunks = load_corpus(settings=settings, client=qdrant)
    if _bm25_cache is not None and _bm25_cache_size == len(chunks):
        return _bm25_cache

    logger.info("Construction index BM25 (%s chunks)…", len(chunks))
    _bm25_cache = BM25Index(chunks)
    _bm25_cache_size = len(chunks)
    return _bm25_cache


def search_vector(
    query: str,
    top_k: int,
    settings: Settings,
    qdrant: QdrantClient,
    openai_client: OpenAI,
    metadata_filter: MetadataFilter | None = None,
) -> list[RetrievedChunk]:
    """Recherche vectorielle pure (cosine similarity Qdrant, filtre en amont)."""
    query_vector = embed_texts([query], settings=settings, client=openai_client)[0]

    hits = qdrant.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        limit=top_k,
        query_filter=metadata_filter.to_qdrant() if metadata_filter else None,
    )

    results: list[RetrievedChunk] = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            RetrievedChunk(
                chunk_id=str(hit.id),
                text=str(payload.get("text", "")),
                page_number=int(payload.get("page_number", 0)),
                score=float(hit.score or 0.0),
                source=str(payload.get("source", "")),
            )
        )
    return results


def search_bm25(
    query: str,
    top_k: int,
    settings: Settings,
    qdrant: QdrantClient,
    metadata_filter: MetadataFilter | None = None,
) -> list[RetrievedChunk]:
    """Recherche BM25 pure sur le corpus indexé (filtre métadonnées en amont)."""
    index = _get_bm25_index(settings, qdrant)
    predicate = None
    if metadata_filter is not None and not metadata_filter.is_empty():
        predicate = metadata_filter.accepts
    return index.search(query, top_k=top_k, predicate=predicate)


def search_hybrid(
    query: str,
    top_k: int,
    settings: Settings,
    qdrant: QdrantClient,
    openai_client: OpenAI,
    metadata_filter: MetadataFilter | None = None,
) -> list[RetrievedChunk]:
    """Fusion RRF entre vectoriel et BM25, avec le même filtre sur les deux jambes."""
    candidate_k = top_k * 3
    vector_results = search_vector(
        query, candidate_k, settings, qdrant, openai_client, metadata_filter=metadata_filter
    )
    bm25_results = search_bm25(query, candidate_k, settings, qdrant, metadata_filter=metadata_filter)
    return reciprocal_rank_fusion([vector_results, bm25_results], top_k=top_k)


def search(
    query: str,
    top_k: int | None = None,
    mode: RetrievalMode | None = None,
    settings: Settings | None = None,
    qdrant: QdrantClient | None = None,
    openai_client: OpenAI | None = None,
    metadata_filter: MetadataFilter | None = None,
) -> list[RetrievedChunk]:
    """Recherche les chunks les plus pertinents (mode configurable)."""
    cfg = settings or get_settings()
    k = top_k or cfg.top_k
    retrieval_mode: RetrievalMode = mode or cfg.retrieval_mode  # type: ignore[assignment]
    client = qdrant or get_qdrant_client(cfg)

    if not client.collection_exists(cfg.qdrant_collection):
        msg = (
            f"Collection Qdrant '{cfg.qdrant_collection}' absente. "
            "Lancer d'abord : python scripts/run_ingest.py"
        )
        raise ValueError(msg)

    # Rayon géographique actif mais aucun chantier dans la zone
    if (
        metadata_filter is not None
        and metadata_filter.geo_center_lat is not None
        and not metadata_filter.allowed_chunk_ids
    ):
        logger.info("0 chunks (aucun chantier dans le rayon géographique)")
        return []

    if retrieval_mode == "bm25":
        results = search_bm25(query, k, cfg, client, metadata_filter=metadata_filter)
    elif retrieval_mode == "hybrid":
        oai = openai_client or get_openai_client(cfg)
        results = search_hybrid(query, k, cfg, client, oai, metadata_filter=metadata_filter)
    else:
        oai = openai_client or get_openai_client(cfg)
        results = search_vector(query, k, cfg, client, oai, metadata_filter=metadata_filter)

    logger.info("%s chunks récupérés (mode=%s)", len(results), retrieval_mode)
    return results
