"""Types partagés du module RAG."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    """Chunk récupéré par une stratégie de retrieval."""

    text: str
    page_number: int
    score: float
    source: str
    chunk_id: str = field(default="")
