"""Génération de réponses LLM à partir du contexte RAG."""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from ingest.embed import get_openai_client
from rag.config import METADATA_PATH, Settings, get_settings
from rag.prompts import get_prompt
from rag.types import RetrievedChunk

logger = logging.getLogger(__name__)


def get_reference_date() -> str:
    """Date de publication du document officiel (depuis data/metadata.json)."""
    try:
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
        return str(metadata.get("pub_date", ""))
    except (OSError, json.JSONDecodeError):
        return ""


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
    prompt_name: str | None = None,
) -> str:
    """Génère une réponse à partir de la question et du contexte retrieval."""
    cfg = settings or get_settings()
    oai = client or get_openai_client(cfg)
    context = format_context(chunks)
    system_prompt = get_prompt(
        prompt_name or cfg.llm_prompt_name,
        reference_date=get_reference_date(),
    )

    response = oai.chat.completions.create(
        model=cfg.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Contexte :\n{context}\n\nQuestion : {question}",
            },
        ],
        temperature=0.2,
    )

    answer = response.choices[0].message.content or ""
    logger.info("Réponse générée (%s caractères, prompt=%s)", len(answer), prompt_name or cfg.llm_prompt_name)
    return answer.strip()
