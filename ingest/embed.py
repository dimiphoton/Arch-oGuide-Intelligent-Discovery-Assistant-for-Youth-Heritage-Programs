"""Génération d'embeddings via OpenAI."""

from __future__ import annotations

import logging

from openai import OpenAI

from ingest.chunk import TextChunk
from rag.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Taille des lots pour limiter les appels API
EMBED_BATCH_SIZE = 100


def get_openai_client(settings: Settings | None = None) -> OpenAI:
    """Client OpenAI configuré depuis les settings."""
    cfg = settings or get_settings()
    if not cfg.openai_api_key.strip():
        msg = "OPENAI_API_KEY manquante — renseigner dans .env"
        raise ValueError(msg)
    return OpenAI(api_key=cfg.openai_api_key)


def embed_texts(
    texts: list[str],
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> list[list[float]]:
    """Embed une liste de textes par lots."""
    if not texts:
        return []

    cfg = settings or get_settings()
    openai_client = client or get_openai_client(cfg)
    vectors: list[list[float]] = []

    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        logger.info("Embeddings %s/%s…", start + len(batch), len(texts))
        response = openai_client.embeddings.create(
            model=cfg.embedding_model,
            input=batch,
        )
        # L'API renvoie les vecteurs dans le même ordre que l'input
        vectors.extend(item.embedding for item in response.data)

    return vectors


def embed_chunks(
    chunks: list[TextChunk],
    settings: Settings | None = None,
    client: OpenAI | None = None,
) -> list[list[float]]:
    """Embed une liste de chunks."""
    texts = [chunk.text for chunk in chunks]
    return embed_texts(texts, settings=settings, client=client)
