"""Chargement du corpus depuis Qdrant."""

from __future__ import annotations

from dataclasses import dataclass, field

from qdrant_client import QdrantClient

from rag.config import Settings, get_settings
from ingest.index import get_qdrant_client


@dataclass
class CorpusChunk:
    """Chunk indexé avec identifiant stable."""

    chunk_id: str
    text: str
    page_number: int
    source: str
    # Payload Qdrant complet (region, statut…) pour le filtrage métadonnées
    payload: dict = field(default_factory=dict)


def load_corpus(
    settings: Settings | None = None,
    client: QdrantClient | None = None,
) -> list[CorpusChunk]:
    """Récupère tous les chunks de la collection Qdrant."""
    cfg = settings or get_settings()
    qdrant = client or get_qdrant_client(cfg)

    if not qdrant.collection_exists(cfg.qdrant_collection):
        msg = f"Collection '{cfg.qdrant_collection}' absente — lancer run_ingest.py"
        raise ValueError(msg)

    chunks: list[CorpusChunk] = []
    offset = None

    while True:
        points, offset = qdrant.scroll(
            collection_name=cfg.qdrant_collection,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            chunks.append(
                CorpusChunk(
                    chunk_id=str(point.id),
                    text=text,
                    page_number=int(payload.get("page_number", 0)),
                    source=str(payload.get("source", "")),
                    payload={**dict(payload), "chunk_id": str(point.id)},
                )
            )
        if offset is None:
            break

    return chunks
