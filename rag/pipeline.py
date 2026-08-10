"""Pipeline RAG complet : retrieval + génération."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from monitoring.store import log_query
from rag.catalog import (
    catalog_to_chunks,
    detect_region,
    filter_catalog,
    format_catalog_summary,
    is_catalog_query,
    load_chantier_catalog,
)
from rag.config import Settings, get_settings
from rag.generate import generate_answer
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


def _is_count_query(question: str) -> bool:
    lowered = question.lower()
    return bool(re.search(r"\bcombien\b|\bnombre\b|\bcombien y a\b", lowered))


def _answer_from_catalog(question: str, settings: Settings) -> tuple[str, list[RetrievedChunk]] | None:
    """
    Répond via le catalogue complet (pas top_k) pour les questions liste/comptage.

    Retourne None si ce n'est pas une question catalogue.
    """
    if not is_catalog_query(question):
        return None

    region = detect_region(question)
    catalog = load_chantier_catalog(settings=settings)
    filtered = filter_catalog(catalog, region=region)
    chunks = catalog_to_chunks(filtered)
    summary = format_catalog_summary(filtered, region=region)

    if _is_count_query(question):
        scope = f"en {region}" if region else "dans le document officiel"
        answer = (
            f"Le document officiel recense **{len(filtered)} chantier(s)** {scope}.\n\n"
            f"{summary}"
        )
        return answer, chunks

    # Liste : on donne le résumé + les fiches (tronquées si trop nombreuses)
    max_full = 30
    context_chunks = chunks[:max_full]
    if len(chunks) > max_full:
        # Injecte le résumé complet comme premier "chunk" synthétique
        context_chunks = [
            RetrievedChunk(
                text=summary,
                page_number=0,
                score=1.0,
                source="catalog",
                chunk_id="catalog-summary",
            ),
            *context_chunks,
        ]
    else:
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

    catalog_result = _answer_from_catalog(question, cfg)
    if catalog_result is not None:
        answer, chunks = catalog_result
        search_query = question
    else:
        search_query = rewrite_query(question, settings=cfg) if do_rewrite else question
        rewritten = search_query if do_rewrite else None
        candidate_k = k * 3 if do_rerank else k
        chunks = search(search_query, top_k=candidate_k, settings=cfg)

        if do_rerank and chunks:
            chunks = rerank_chunks(question, chunks, top_k=k, settings=cfg)
        else:
            chunks = chunks[:k]

        answer = generate_answer(question, chunks, settings=cfg)

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
    )
