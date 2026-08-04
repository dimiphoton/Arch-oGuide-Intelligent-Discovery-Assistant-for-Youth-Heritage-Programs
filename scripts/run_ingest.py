#!/usr/bin/env python3
"""Point d'entrée CLI pour l'ingestion PDF → Qdrant."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.pipeline import run_ingest_pipeline
from rag.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingère le PDF des chantiers archéologiques dans Qdrant."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Chemin PDF (défaut : data/pdfs/liste_chantiers_latest.pdf)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recrée la collection Qdrant avant indexation.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extraction + chunking uniquement, sans embeddings ni Qdrant.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Logs détaillés.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    settings = get_settings()
    pdf_path = args.pdf or settings.pdf_path

    try:
        result = run_ingest_pipeline(
            pdf_path=pdf_path,
            recreate_collection=args.recreate,
            dry_run=args.dry_run,
            settings=settings,
        )
    except Exception as exc:
        logging.error("Erreur ingestion : %s", exc)
        return 1

    status = result.get("status")
    logging.info(
        "Terminé — %s pages, %s chunks, statut=%s",
        result.get("pages"),
        result.get("chunks"),
        status,
    )
    if status == "indexed":
        logging.info(
            "Collection %s : %s points indexés",
            result.get("collection"),
            result.get("indexed"),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
