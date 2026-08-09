"""Métriques d'évaluation des réponses LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class LlmEvalCase:
    """Cas de test pour l'évaluation LLM."""

    id: str
    question: str
    expected_answer_keywords: list[str]
    require_citation: bool = False


REFUSAL_PATTERNS = (
    "je ne trouve pas",
    "pas d'information",
    "ne contient pas",
    "contexte ne contient",
    "je ne sais pas",
    "aucune information",
)


def keyword_score(answer: str, keywords: list[str]) -> float:
    """Part des mots-clés attendus présents dans la réponse."""
    if not keywords:
        return 1.0
    answer_lower = answer.lower()
    hits = sum(1 for kw in keywords if kw.lower() in answer_lower)
    return hits / len(keywords)


def has_citation(answer: str) -> bool:
    """Détecte une citation de page dans la réponse."""
    return bool(re.search(r"p\.\s*\d+|page\s*\d|sources\s*:", answer, flags=re.IGNORECASE))


def citation_score(answer: str, require_citation: bool) -> float:
    """1.0 si citation présente (ou non requise), sinon 0.0."""
    if not require_citation:
        return 1.0
    return 1.0 if has_citation(answer) else 0.0


def refusal_score(answer: str) -> float:
    """1.0 si la réponse refuse honnêtement (contexte vide)."""
    answer_lower = answer.lower()
    return 1.0 if any(pattern in answer_lower for pattern in REFUSAL_PATTERNS) else 0.0


def score_answer(answer: str, case: LlmEvalCase) -> dict[str, float]:
    """Score composite d'une réponse pour un cas donné."""
    kw = keyword_score(answer, case.expected_answer_keywords)
    cit = citation_score(answer, case.require_citation)
    total = 0.7 * kw + 0.3 * cit
    return {
        "keyword_score": kw,
        "citation_score": cit,
        "total": total,
    }


def aggregate_llm_scores(per_answer_totals: list[float]) -> dict[str, float]:
    """Moyenne des scores sur plusieurs questions."""
    n = len(per_answer_totals) or 1
    return {
        "avg_total": sum(per_answer_totals) / n,
        "num_cases": float(len(per_answer_totals)),
    }
