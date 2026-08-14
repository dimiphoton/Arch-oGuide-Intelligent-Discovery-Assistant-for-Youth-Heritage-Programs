#!/usr/bin/env python3
"""Construit data/index_snapshot.* (embeddings OpenAI une seule fois, ex. CI ou local)."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingest.index import get_qdrant_client
from ingest.pipeline import run_ingest_pipeline
from ingest.snapshot import export_snapshot
from rag.config import get_settings
sys.path.insert(0, str(ROOT / "scripts"))
from ensure_indexed import ensure_pdf_present  # noqa: E402

logger = logging.getLogger(__name__)


def wait_for_qdrant(url: str, timeout_sec: int = 60) -> None:
    """Attend que Qdrant réponde."""
    from qdrant_client import QdrantClient

    for _ in range(timeout_sec):
        try:
            QdrantClient(url=url).get_collections()
            return
        except Exception:
            time.sleep(1)
    msg = f"Qdrant indisponible après {timeout_sec}s ({url})"
    raise TimeoutError(msg)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    settings = get_settings()

    wait_for_qdrant(settings.qdrant_url)
    ensure_pdf_present()

    logger.info("Indexation complète (OpenAI + Qdrant)…")
    run_ingest_pipeline(settings=settings, recreate_collection=True)

    client = get_qdrant_client(settings)
    count = export_snapshot(settings=settings, client=client)
    logger.info("Snapshot prêt — %s points", count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
