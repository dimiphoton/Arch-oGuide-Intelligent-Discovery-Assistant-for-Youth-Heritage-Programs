"""Pipeline RAG complet : retrieval + génération."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from monitoring.store import log_query
from rag.catalog import (
    catalog_to_chunks,
    detect_region,
    filter_catalog,
    format_catalog_answer,
    format_catalog_summary,
    format_catalog_table,
    is_catalog_query,
    is_count_query,
    is_table_query,
    load_chantier_catalog,
)
from rag.config import Settings, get_settings
from rag.filters import MetadataFilter, build_metadata_filter
from rag.generate import generate_answer
from rag.geo import MapSite, is_map_query, records_to_map_sites
from rag.query_rewrite import rewrite_query
from rag.rerank import rerank_chunks
from rag.retrieval import search
from rag.types import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass
class RagResponse:
    """Réponse complète du pipeline RAG."""

    question: str
    answer: str
    sources: list[RetrievedChunk]
    rewritten_query: str | None = field(default=None)
    event_id: str | None = field(default=None)
    latency_ms: float = field(default=0.0)
    map_sites: list[MapSite] = field(default_factory=list)


# Au-delà de ce nombre de fiches, on répond sans LLM pour garantir une liste complète.
MAX_FICHES_POUR_LLM = 30


def _map_sites_from_catalog(
    question: str,
    settings: Settings,
    metadata_filter: MetadataFilter | None = None,
) -> list[MapSite]:
    """Charge les sites cartographiables selon les filtres géographiques."""
    region = detect_region(question)
    catalog = load_chantier_catalog(settings=settings)
    filtered = filter_catalog(
        catalog,
        region=region,
        commune=metadata_filter.commune if metadata_filter else None,
        departement=metadata_filter.departement if metadata_filter else None,
        metadata_filter=metadata_filter,
    )
    return records_to_map_sites(filtered)


def _answer_from_catalog(
    question: str,
    settings: Settings,
    metadata_filter: MetadataFilter | None = None,
) -> tuple[str, list[RetrievedChunk]] | None:
    """
    Répond via le catalogue complet (pas top_k) pour les questions liste/comptage.

    Retourne None si ce n'est pas une question catalogue.
    """
    if not is_catalog_query(question):
        return None

    region = detect_region(question)
    catalog = load_chantier_catalog(settings=settings)
    filtered = filter_catalog(
        catalog,
        region=region,
        commune=metadata_filter.commune if metadata_filter else None,
        departement=metadata_filter.departement if metadata_filter else None,
        metadata_filter=metadata_filter,
    )
    chunks = catalog_to_chunks(filtered)

    if is_table_query(question):
        return format_catalog_table(filtered, region=region), chunks
    if is_count_query(question) or len(filtered) > MAX_FICHES_POUR_LLM:
        return format_catalog_answer(filtered, region=region), chunks

    summary = format_catalog_summary(filtered, region=region)
    context_chunks = [
        RetrievedChunk(
            text=summary,
            page_number=0,
            score=1.0,
            source="catalog",
            chunk_id="catalog-summary",
        ),
        *chunks,
    ]
    answer = generate_answer(question, context_chunks, settings=settings)
    return answer, chunks


def ask(
    question: str,
    top_k: int | None = None,
    settings: Settings | None = None,
    rewrite: bool | None = None,
    rerank: bool | None = None,
    log: bool = True,
) -> RagResponse:
    """Pose une question au RAG et retourne la réponse + sources."""
    cfg = settings or get_settings()
    k = top_k or cfg.top_k
    do_rewrite = cfg.enable_query_rewrite if rewrite is None else rewrite
    do_rerank = cfg.enable_rerank if rerank is None else rerank

    start = time.perf_counter()
    rewritten: str | None = None
    metadata_filter = build_metadata_filter(question)
    wants_map = is_map_query(question)

    catalog_result = _answer_from_catalog(question, cfg, metadata_filter=metadata_filter)
    if catalog_result is not None:
        answer, chunks = catalog_result
        search_query = question
    else:
        search_query = rewrite_query(question, settings=cfg) if do_rewrite else question
        rewritten = search_query if do_rewrite else None
        candidate_k = k * 3 if do_rerank else k
        chunks = search(search_query, top_k=candidate_k, settings=cfg, metadata_filter=metadata_filter)

        if do_rerank and chunks:
            chunks = rerank_chunks(question, chunks, top_k=k, settings=cfg)
        else:
            chunks = chunks[:k]

        answer = generate_answer(question, chunks, settings=cfg)

    map_sites: list[MapSite] = []
    if wants_map:
        map_sites = _map_sites_from_catalog(question, cfg, metadata_filter=metadata_filter)
        if map_sites:
            answer += (
                f"\n\n🗺️ **{len(map_sites)} chantier(s)** géolocalisé(s) — "
                "consultez la carte dans l'onglet **Carte** ou ci-dessous."
            )
        else:
            answer += (
                "\n\n🗺️ Aucun chantier géolocalisé pour cette zone. "
                "Relancez l'ingestion (`python scripts/run_ingest.py`) pour enrichir les coordonnées GPS."
            )

    latency_ms = (time.perf_counter() - start) * 1000

    event_id = None
    if log:
        event_id = log_query(question, answer, latency_ms, len(chunks))

    return RagResponse(
        question=question,
        answer=answer,
        sources=chunks,
        rewritten_query=rewritten,
        event_id=event_id,
        latency_ms=latency_ms,
        map_sites=map_sites,
    )
