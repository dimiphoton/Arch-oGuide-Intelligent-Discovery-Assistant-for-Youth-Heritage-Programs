"""Indexation des chunks dans Qdrant."""

from __future__ import annotations

import logging

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from ingest.chunk import TextChunk
from rag.config import Settings, get_settings

logger = logging.getLogger(__name__)

# text-embedding-3-small produit des vecteurs de dimension 1536
EMBEDDING_DIM = 1536


def get_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    """Client Qdrant configuré depuis les settings."""
    cfg = settings or get_settings()
    return QdrantClient(url=cfg.qdrant_url)


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    recreate: bool = False,
) -> None:
    """Crée la collection si elle n'existe pas (ou la recrée)."""
    exists = client.collection_exists(collection_name)

    if recreate and exists:
        logger.info("Suppression de la collection %s…", collection_name)
        client.delete_collection(collection_name)
        exists = False

    if not exists:
        logger.info("Création de la collection %s…", collection_name)
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )


def index_chunks(
    chunks: list[TextChunk],
    vectors: list[list[float]],
    settings: Settings | None = None,
    client: QdrantClient | None = None,
    recreate: bool = False,
) -> int:
    """Upsert les chunks et leurs vecteurs dans Qdrant."""
    if len(chunks) != len(vectors):
        msg = f"Nombre de chunks ({len(chunks)}) != nombre de vecteurs ({len(vectors)})"
        raise ValueError(msg)

    cfg = settings or get_settings()
    qdrant = client or get_qdrant_client(cfg)
    ensure_collection(qdrant, cfg.qdrant_collection, recreate=recreate)

    points = [
        PointStruct(
            id=chunk.chunk_id,
            vector=vector,
            payload={
                "text": chunk.text,
                "page_number": chunk.page_number,
                "chunk_index": chunk.chunk_index,
                "source": chunk.source,
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    # Upsert par lots pour les gros PDF
    batch_size = 100
    for start in range(0, len(points), batch_size):
        batch = points[start : start + batch_size]
        qdrant.upsert(collection_name=cfg.qdrant_collection, points=batch)
        logger.info("Indexés %s/%s points", min(start + batch_size, len(points)), len(points))

    return len(points)
