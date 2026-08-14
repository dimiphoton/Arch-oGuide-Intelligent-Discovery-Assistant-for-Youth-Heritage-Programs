"""Export / import d'un snapshot Qdrant (évite les embeddings OpenAI au démarrage)."""

from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from ingest.index import EMBEDDING_DIM, ensure_collection, get_qdrant_client
from rag.config import PROJECT_ROOT, Settings, get_settings

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = PROJECT_ROOT / "data"
SNAPSHOT_FILE = SNAPSHOT_DIR / "index_snapshot.json.gz"
META_FILE = SNAPSHOT_DIR / "index_snapshot_meta.json"

UPSERT_BATCH_SIZE = 100


def snapshot_exists() -> bool:
    """True si le fichier snapshot est présent."""
    return SNAPSHOT_FILE.is_file()


def export_snapshot(settings: Settings | None = None, client: QdrantClient | None = None) -> int:
    """
    Exporte la collection Qdrant vers data/index_snapshot.json.gz.

    Retourne le nombre de points exportés.
    """
    cfg = settings or get_settings()
    qdrant = client or get_qdrant_client(cfg)

    if not qdrant.collection_exists(cfg.qdrant_collection):
        msg = f"Collection absente : {cfg.qdrant_collection}"
        raise ValueError(msg)

    points_data: list[dict[str, Any]] = []
    offset = None

    while True:
        points, offset = qdrant.scroll(
            collection_name=cfg.qdrant_collection,
            limit=100,
            offset=offset,
            with_vectors=True,
            with_payload=True,
        )
        if not points:
            break
        for point in points:
            points_data.append(
                {
                    "id": str(point.id),
                    "vector": list(point.vector),  # type: ignore[arg-type]
                    "payload": dict(point.payload or {}),
                }
            )
        if offset is None:
            break

    if not points_data:
        return 0

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(points_data, ensure_ascii=False).encode("utf-8")
    with gzip.open(SNAPSHOT_FILE, "wb") as handle:
        handle.write(payload)

    META_FILE.write_text(
        json.dumps(
            {
                "collection": cfg.qdrant_collection,
                "points": len(points_data),
                "embedding_dim": EMBEDDING_DIM,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Snapshot exporté — %s points → %s", len(points_data), SNAPSHOT_FILE.name)
    return len(points_data)


def import_snapshot(settings: Settings | None = None, client: QdrantClient | None = None) -> int:
    """
    Restaure le snapshot dans Qdrant (sans appel OpenAI).

    Retourne le nombre de points importés.
    """
    if not snapshot_exists():
        return 0

    cfg = settings or get_settings()
    qdrant = client or get_qdrant_client(cfg)

    with gzip.open(SNAPSHOT_FILE, "rt", encoding="utf-8") as handle:
        points_data: list[dict[str, Any]] = json.load(handle)

    if not points_data:
        return 0

    ensure_collection(qdrant, cfg.qdrant_collection, recreate=True)

    points = [
        PointStruct(
            id=item["id"],
            vector=item["vector"],
            payload=item.get("payload", {}),
        )
        for item in points_data
    ]

    for start in range(0, len(points), UPSERT_BATCH_SIZE):
        batch = points[start : start + UPSERT_BATCH_SIZE]
        qdrant.upsert(collection_name=cfg.qdrant_collection, points=batch)

    logger.info("Snapshot importé — %s points", len(points))
    return len(points)
