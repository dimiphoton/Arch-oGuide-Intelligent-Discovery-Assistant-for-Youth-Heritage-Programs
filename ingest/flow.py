"""Flow Prefect — wrapper autour du pipeline d'ingestion."""

from __future__ import annotations

from pathlib import Path

from prefect import flow

from ingest.pipeline import run_ingest_pipeline
from rag.config import Settings


@flow(name="ingest-chantiers-pdf", log_prints=True)
def ingest_flow(
    pdf_path: Path | None = None,
    recreate_collection: bool = False,
    dry_run: bool = False,
    settings: Settings | None = None,
) -> dict:
    """
    Flow Prefect pour l'ingestion automatisée.

    Lancer via :
        prefect flow run ingest/flow.py:ingest_flow
    ou depuis Python :
        from ingest.flow import ingest_flow; ingest_flow()
    """
    return run_ingest_pipeline(
        pdf_path=pdf_path,
        recreate_collection=recreate_collection,
        dry_run=dry_run,
        settings=settings,
    )
