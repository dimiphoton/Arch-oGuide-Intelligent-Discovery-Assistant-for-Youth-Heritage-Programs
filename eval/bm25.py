"""Recherche BM25 sur le corpus local."""

from __future__ import annotations

import re
from typing import Callable

from rank_bm25 import BM25Okapi

from eval.corpus import CorpusChunk
from rag.types import RetrievedChunk


def _tokenize(text: str) -> list[str]:
    """Tokenisation simple : mots en minuscules."""
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


class BM25Index:
    """Index BM25 en mémoire, construit depuis le corpus Qdrant."""

    def __init__(self, chunks: list[CorpusChunk]) -> None:
        self.chunks = chunks
        tokenized = [_tokenize(chunk.text) for chunk in chunks]
        self._bm25 = BM25Okapi(tokenized)

    def search(
        self,
        query: str,
        top_k: int = 5,
        predicate: Callable[[dict], bool] | None = None,
    ) -> list[RetrievedChunk]:
        """
        Retourne les top-k chunks par score BM25.

        predicate : filtre métadonnées appliqué sur le payload des chunks
        (mêmes contraintes que le filtre Qdrant côté vectoriel).
        """
        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        # argsort décroissant, en écartant les chunks refusés par le filtre
        ranked_indices = sorted(
            (
                i
                for i in range(len(scores))
                if predicate is None or predicate(self.chunks[i].payload)
            ),
            key=lambda i: scores[i],
            reverse=True,
        )[:top_k]

        results: list[RetrievedChunk] = []
        for index in ranked_indices:
            chunk = self.chunks[index]
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    page_number=chunk.page_number,
                    score=float(scores[index]),
                    source=chunk.source,
                )
            )
        return results
