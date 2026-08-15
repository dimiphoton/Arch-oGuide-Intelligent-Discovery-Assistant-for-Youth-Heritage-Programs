#!/usr/bin/env python3
"""Télécharge le PDF et ingère dans Qdrant si la collection est absente ou vide."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.index import get_qdrant_client
from ingest.pipeline import run_ingest_pipeline
from ingest.snapshot import import_snapshot, snapshot_exists
from rag.config import get_settings
from scrapping.scraper import run_scrape

logger = logging.getLogger(__name__)


def collection_point_count() -> int:
    """Retourne le nombre de points indexés (0 si collection absente)."""
    settings = get_settings()
    client = get_qdrant_client(settings)
    if not client.collection_exists(settings.qdrant_collection):
        return 0
    info = client.get_collection(settings.qdrant_collection)
    return int(info.points_count or 0)


def ensure_pdf_present() -> None:
    """Télécharge le PDF officiel s'il n'est pas déjà en local."""
    settings = get_settings()
    if settings.pdf_path.exists():
        logger.info("PDF déjà présent : %s", settings.pdf_path)
        return
    logger.info("PDF absent — lancement du scraper…")
    settings.pdf_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_scrape(force=True)
    if settings.pdf_path.exists():
        return
    if result.get("local_path") and Path(result["local_path"]).is_file():
        return
    msg = "Impossible de récupérer le PDF officiel (scraper sans fichier local)."
    raise FileNotFoundError(msg)


def ensure_indexed() -> int:
    """Ingère le PDF si nécessaire. Retourne le nombre de points indexés."""
    count = collection_point_count()
    if count > 0:
        logger.info("Collection déjà indexée (%s points)", count)
        return count

    if snapshot_exists():
        logger.info("Restauration du snapshot pré-calculé (sans OpenAI)…")
        try:
            imported = import_snapshot(settings=get_settings())
            if imported > 0:
                return imported
        except Exception as exc:
            logger.warning("Snapshot illisible, indexation complète : %s", exc)

    ensure_pdf_present()
    logger.info("Indexation complète en cours (OpenAI + Qdrant)…")
    result = run_ingest_pipeline(settings=get_settings())
    return int(result.get("indexed", 0))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        indexed = ensure_indexed()
    except Exception as exc:
        logger.error("Échec indexation : %s", exc)
        return 1
    logger.info("Index prêt — %s points", indexed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
