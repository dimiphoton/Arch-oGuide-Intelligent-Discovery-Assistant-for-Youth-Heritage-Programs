"""Génération de réponses LLM à partir du contexte RAG."""

from __future__ import annotations

import logging

from openai import OpenAI

from ingest.embed import get_openai_client
from rag.config import Settings, get_settings
from rag.types import RetrievedChunk

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es ArchéoGuide, un assistant pour aider les jeunes, les familles \
et les enseignants à découvrir des chantiers archéologiques en France.

Règles :
- Réponds en français, de façon claire et accessible.
- Base-toi UNIQUEMENT sur le contexte fourni ci-dessous.
- Si le contexte ne contient pas l'information, dis-le honnêtement.
- Cite la page source quand c'est pertinent (ex. « p. 12 »).
- Ne invente jamais de chantier, de date ou de contact."""


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Formate les chunks récupérés pour le prompt LLM."""
    if not chunks:
        return "Aucun contexte disponible."

    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[Source {index} — p. {chunk.page_number}, score={chunk.score:.3f}]\n{chunk.text}"
        )
    return "\n\n".join(parts)


def generate_answer(
    question: str,
    chunks: list[RetrievedChunk],
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> str:
    """Génère une réponse à partir de la question et du contexte retrieval."""
    cfg = settings or get_settings()
    oai = client or get_openai_client(cfg)
    context = format_context(chunks)

    response = oai.chat.completions.create(
        model=cfg.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Contexte :\n{context}\n\nQuestion : {question}",
            },
        ],
        temperature=0.2,
    )

    answer = response.choices[0].message.content or ""
    logger.info("Réponse générée (%s caractères)", len(answer))
    return answer.strip()
