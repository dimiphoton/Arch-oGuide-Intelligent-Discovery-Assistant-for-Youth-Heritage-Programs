"""Réécriture de la question utilisateur pour améliorer le retrieval."""

from __future__ import annotations

import logging

from openai import OpenAI

from ingest.embed import get_openai_client
from rag.config import Settings, get_settings

logger = logging.getLogger(__name__)

REWRITE_PROMPT = """Tu reformules une question sur les chantiers archéologiques en France \
pour optimiser une recherche documentaire.

Règles :
- Garde l'intention originale (région, public, type de chantier, période…).
- Ajoute des mots-clés utiles (bénévole, visite, fouille, scolaire…).
- Réponds UNIQUEMENT avec la question reformulée, sans explication.
- Une seule phrase, en français."""


def rewrite_query(
    question: str,
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> str:
    """Réécrit la question pour améliorer la recherche vectorielle / BM25."""
    cfg = settings or get_settings()
    oai = client or get_openai_client(cfg)

    response = oai.chat.completions.create(
        model=cfg.llm_model,
        messages=[
            {"role": "system", "content": REWRITE_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.0,
    )

    rewritten = (response.choices[0].message.content or question).strip()
    logger.info("Query rewrite : '%s' -> '%s'", question[:60], rewritten[:60])
    return rewritten or question
