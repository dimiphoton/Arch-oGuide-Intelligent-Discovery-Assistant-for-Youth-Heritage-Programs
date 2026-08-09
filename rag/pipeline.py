"""Pipeline RAG complet : retrieval + génération."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from monitoring.store import log_query
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
    search_query = rewrite_query(question, settings=cfg) if do_rewrite else question
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
        rewritten_query=search_query if do_rewrite else None,
        event_id=event_id,
        latency_ms=latency_ms,
    )
