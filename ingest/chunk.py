"""Découpage du texte en chunks pour l'indexation."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid5, NAMESPACE_URL

from ingest.extract import PageText


@dataclass
class TextChunk:
    """Fragment de texte prêt à être embeddé et indexé."""

    chunk_id: str
    text: str
    page_number: int
    chunk_index: int
    source: str


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    Découpe un texte en morceaux avec chevauchement.
    Coupe de préférence sur un espace pour ne pas briser les mots.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    text_len = len(cleaned)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        piece = cleaned[start:end]

        # Recule jusqu'au dernier espace si on n'est pas en fin de texte
        if end < text_len:
            last_space = piece.rfind(" ")
            if last_space > chunk_size // 2:
                end = start + last_space
                piece = cleaned[start:end]

        piece = piece.strip()
        if piece:
            chunks.append(piece)

        if end >= text_len:
            break
        start = max(end - chunk_overlap, start + 1)

    return chunks


def build_chunks(
    pages: list[PageText],
    source: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    """Transforme les pages extraites en chunks indexables."""
    result: list[TextChunk] = []

    for page in pages:
        page_chunks = chunk_text(page.text, chunk_size, chunk_overlap)
        for index, text in enumerate(page_chunks):
            # ID stable pour éviter les doublons lors d'un re-run
            chunk_id = str(uuid5(NAMESPACE_URL, f"{source}:{page.page_number}:{index}:{text[:80]}"))
            result.append(
                TextChunk(
                    chunk_id=chunk_id,
                    text=text,
                    page_number=page.page_number,
                    chunk_index=index,
                    source=source,
                )
            )

    return result
