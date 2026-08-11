#!/usr/bin/env python3
"""Enrichit le corpus indexé avec des coordonnées GPS (sans ré-ingérer les embeddings)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ingest.geocode import enrich_chunks_with_coords
from ingest.chunk import TextChunk
from ingest.index import get_qdrant_client
from rag.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Géocode les fiches chantier déjà indexées dans Qdrant.")
    parser.add_argument("--dry-run", action="store_true", help="Géocode sans mettre à jour Qdrant")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Ignore le cache des échecs précédents (lat=null) et retente l'API",
    )
    args = parser.parse_args()

    cfg = get_settings()
    client = get_qdrant_client(cfg)

    if not client.collection_exists(cfg.qdrant_collection):
        logger.error("Collection absente — lancer run_ingest.py d'abord.")
        sys.exit(1)

    chunks: list[TextChunk] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=cfg.qdrant_collection,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            if not payload.get("site_name"):
                continue
            chunks.append(
                TextChunk(
                    chunk_id=str(point.id),
                    text=str(payload.get("text", "")),
                    page_number=int(payload.get("page_number", 0)),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    source=str(payload.get("source", "")),
                    region=str(payload.get("region", "")),
                    site_name=str(payload.get("site_name", "")),
                    commune=str(payload.get("commune", "")),
                    departement=str(payload.get("departement", "")),
                    periode=str(payload.get("periode", "")),
                    statut=str(payload.get("statut", "")),
                    dates=str(payload.get("dates", "")),
                    places=str(payload.get("places", "")),
                    vss=str(payload.get("vss", "")),
                    lat=payload.get("lat"),
                    lon=payload.get("lon"),
                )
            )
        if offset is None:
            break

    logger.info("%s fiches chargées", len(chunks))
    geocoded = enrich_chunks_with_coords(chunks, retry_failed=args.retry_failed)
    logger.info("%s communes géolocalisées", geocoded)

    if args.dry_run:
        logger.info("[dry-run] Qdrant non mis à jour")
        return

    updated = 0
    for chunk in chunks:
        if chunk.lat is None or chunk.lon is None:
            continue
        client.set_payload(
            collection_name=cfg.qdrant_collection,
            payload={"lat": chunk.lat, "lon": chunk.lon},
            points=[chunk.chunk_id],
        )
        updated += 1

    logger.info("%s fiches mises à jour dans Qdrant", updated)


if __name__ == "__main__":
    main()
