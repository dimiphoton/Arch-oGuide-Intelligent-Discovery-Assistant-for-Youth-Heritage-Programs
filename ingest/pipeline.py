"""Orchestration de l'ingestion PDF → Qdrant (sans dépendance Prefect)."""

from __future__ import annotations

import logging
from pathlib import Path

from ingest.chunk import build_chunks
from ingest.embed import embed_chunks
from ingest.extract import extract_pdf
from ingest.index import index_chunks
from rag.config import Settings, get_settings

logger = logging.getLogger(__name__)


def run_ingest_pipeline(
    pdf_path: Path | None = None,
    recreate_collection: bool = False,
    dry_run: bool = False,
    settings: Settings | None = None,
) -> dict:
    """
    Pipeline complet : extraction → chunking → embeddings → Qdrant.

    dry_run=True : s'arrête après le chunking (pas d'appel API).
    """
    cfg = settings or get_settings()
    path = pdf_path or cfg.pdf_path
    source = path.name

    pages = extract_pdf(path)
    logger.info("%s pages extraites", len(pages))

    chunks = build_chunks(pages, source, cfg.chunk_size, cfg.chunk_overlap)
    logger.info("%s chunks créés", len(chunks))

    result = {
        "pdf_path": str(path),
        "pages": len(pages),
        "chunks": len(chunks),
        "status": "dry_run" if dry_run else "pending",
    }

    if dry_run:
        logger.info("[dry-run] %s chunks prêts, indexation ignorée", len(chunks))
        result["status"] = "dry_run"
        return result

    vectors = embed_chunks(chunks, settings=cfg)
    indexed = index_chunks(chunks, vectors, settings=cfg, recreate=recreate_collection)
    result["indexed"] = indexed
    result["status"] = "indexed"
    result["collection"] = cfg.qdrant_collection
    return result
