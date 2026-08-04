"""Pipeline RAG complet : retrieval + génération."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rag.config import Settings, get_settings
from rag.generate import generate_answer
from rag.retrieval import RetrievedChunk, search

logger = logging.getLogger(__name__)


@dataclass
class RagResponse:
    """Réponse complète du pipeline RAG."""

    question: str
    answer: str
    sources: list[RetrievedChunk]


def ask(
    question: str,
    top_k: int | None = None,
    settings: Settings | None = None,
) -> RagResponse:
    """Pose une question au RAG et retourne la réponse + sources."""
    cfg = settings or get_settings()
    chunks = search(question, top_k=top_k, settings=cfg)
    answer = generate_answer(question, chunks, settings=cfg)

    return RagResponse(
        question=question,
        answer=answer,
        sources=chunks,
    )
