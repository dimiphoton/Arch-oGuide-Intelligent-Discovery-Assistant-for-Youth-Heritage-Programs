"""Recherche vectorielle dans Qdrant."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openai import OpenAI
from qdrant_client import QdrantClient

from ingest.embed import embed_texts, get_openai_client
from ingest.index import get_qdrant_client
from rag.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """Chunk récupéré depuis Qdrant."""

    text: str
    page_number: int
    score: float
    source: str


def search(
    query: str,
    top_k: int | None = None,
    settings: Settings | None = None,
    qdrant: QdrantClient | None = None,
    openai_client: OpenAI | None = None,
) -> list[RetrievedChunk]:
    """Recherche les chunks les plus pertinents pour une question."""
    cfg = settings or get_settings()
    k = top_k or cfg.top_k
    client = qdrant or get_qdrant_client(cfg)
    oai = openai_client or get_openai_client(cfg)

    query_vector = embed_texts([query], settings=cfg, client=oai)[0]

    if not client.collection_exists(cfg.qdrant_collection):
        msg = (
            f"Collection Qdrant '{cfg.qdrant_collection}' absente. "
            "Lancer d'abord : python scripts/run_ingest.py"
        )
        raise ValueError(msg)

    hits = client.search(
        collection_name=cfg.qdrant_collection,
        query_vector=query_vector,
        limit=k,
    )

    results: list[RetrievedChunk] = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            RetrievedChunk(
                text=str(payload.get("text", "")),
                page_number=int(payload.get("page_number", 0)),
                score=float(hit.score or 0.0),
                source=str(payload.get("source", "")),
            )
        )

    logger.info("%s chunks récupérés pour la requête", len(results))
    return results
