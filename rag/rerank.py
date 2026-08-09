"""Re-classement des chunks récupérés par pertinence."""

from __future__ import annotations

import json
import logging
import re

from openai import OpenAI

from ingest.embed import get_openai_client
from rag.config import Settings, get_settings
from rag.types import RetrievedChunk

logger = logging.getLogger(__name__)

RERANK_PROMPT = """Tu es un classificateur de pertinence documentaire.

On te donne une question et des extraits numérotés d'un PDF officiel sur les \
chantiers archéologiques en France.

Classe les extraits du PLUS pertinent au MOINS pertinent pour répondre à la question.

Réponds UNIQUEMENT en JSON valide :
{"ranking": [3, 1, 2]}

où les nombres sont les IDs des extraits (champ "id"), du meilleur au moins bon.
Inclus seulement les extraits utiles ; ignore les hors-sujet."""


def _build_rerank_payload(question: str, chunks: list[RetrievedChunk]) -> str:
    """Construit le payload compact pour le LLM reranker."""
    items = []
    for index, chunk in enumerate(chunks, start=1):
        preview = chunk.text[:250].replace("\n", " ")
        items.append({"id": index, "page": chunk.page_number, "text": preview})
    return json.dumps({"question": question, "passages": items}, ensure_ascii=False)


def _parse_ranking(raw: str, num_chunks: int) -> list[int]:
    """Extrait la liste d'IDs depuis la réponse JSON du LLM."""
    # Cherche un bloc JSON même si le LLM ajoute du texte autour
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return list(range(1, num_chunks + 1))

    try:
        data = json.loads(match.group())
        ranking = data.get("ranking", [])
        valid = [int(i) for i in ranking if isinstance(i, (int, float)) and 1 <= int(i) <= num_chunks]
        return valid or list(range(1, num_chunks + 1))
    except (json.JSONDecodeError, ValueError):
        return list(range(1, num_chunks + 1))


def rerank_chunks(
    question: str,
    chunks: list[RetrievedChunk],
    top_k: int | None = None,
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> list[RetrievedChunk]:
    """
    Re-classe les chunks via LLM et retourne le top-k.

    Si un seul chunk ou liste vide, retourne tel quel.
    """
    if len(chunks) <= 1:
        return chunks

    cfg = settings or get_settings()
    k = top_k or cfg.top_k
    oai = client or get_openai_client(cfg)

    payload = _build_rerank_payload(question, chunks)
    response = oai.chat.completions.create(
        model=cfg.llm_model,
        messages=[
            {"role": "system", "content": RERANK_PROMPT},
            {"role": "user", "content": payload},
        ],
        temperature=0.0,
    )

    raw = response.choices[0].message.content or ""
    ranking = _parse_ranking(raw, len(chunks))

    # Réordonne selon le ranking LLM ; ajoute les chunks oubliés à la fin
    seen: set[int] = set()
    reranked: list[RetrievedChunk] = []

    for rank_index, chunk_id in enumerate(ranking, start=1):
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        chunk = chunks[chunk_id - 1]
        reranked.append(
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                page_number=chunk.page_number,
                score=float(len(ranking) - rank_index + 1),  # score décroissant
                source=chunk.source,
            )
        )

    for index, chunk in enumerate(chunks, start=1):
        if index not in seen:
            reranked.append(chunk)

    logger.info("Rerank : %s chunks -> top %s", len(chunks), k)
    return reranked[:k]
