"""Tests métriques et prompts LLM (sans appels API)."""

from eval.llm_metrics import (
    LlmEvalCase,
    citation_score,
    keyword_score,
    refusal_score,
    score_answer,
)
from rag.prompts import get_prompt, list_prompts


def test_keyword_score_partial() -> None:
    assert keyword_score("Chantiers en Bretagne pour bénévoles", ["Bretagne", "Corse"]) == 0.5


def test_citation_score_required() -> None:
    assert citation_score("Voir p. 12 pour details", require_citation=True) == 1.0
    assert citation_score("Pas de source", require_citation=True) == 0.0


def test_refusal_score() -> None:
    assert refusal_score("Je ne trouve pas cette information dans le document.") == 1.0
    assert refusal_score("Voici un chantier en Paris.") == 0.0


def test_score_answer_composite() -> None:
    case = LlmEvalCase(
        id="t1",
        question="test",
        expected_answer_keywords=["Bretagne"],
        require_citation=True,
    )
    scores = score_answer("Chantiers en Bretagne (p. 5)", case)
    assert scores["keyword_score"] == 1.0
    assert scores["citation_score"] == 1.0
    assert scores["total"] == 1.0


def test_prompts_registry() -> None:
    names = list_prompts()
    assert "youth_friendly" in names
    assert "factual_strict" in names
    assert "structured_citations" in names
    assert len(get_prompt("youth_friendly")) > 50
