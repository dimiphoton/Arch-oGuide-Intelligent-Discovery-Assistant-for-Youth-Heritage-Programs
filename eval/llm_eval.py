"""Évaluation comparative des prompts LLM."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from eval.llm_metrics import LlmEvalCase, aggregate_llm_scores, refusal_score, score_answer
from rag.config import Settings, get_settings
from rag.generate import generate_answer
from rag.prompts import list_prompts
from rag.retrieval import search

logger = logging.getLogger(__name__)

LLM_GROUND_TRUTH_PATH = Path(__file__).parent / "llm_ground_truth.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_llm_ground_truth(path: Path = LLM_GROUND_TRUTH_PATH) -> list[LlmEvalCase]:
    """Charge les cas d'évaluation LLM."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        LlmEvalCase(
            id=item["id"],
            question=item["question"],
            expected_answer_keywords=item["expected_answer_keywords"],
            require_citation=item.get("require_citation", False),
        )
        for item in raw
    ]


def evaluate_prompt(
    prompt_name: str,
    cases: list[LlmEvalCase],
    settings: Settings | None = None,
    use_rag: bool = True,
) -> dict:
    """Évalue un prompt sur tous les cas (avec ou sans pipeline RAG complet)."""
    cfg = settings or get_settings()
    totals: list[float] = []
    details: list[dict] = []

    for case in cases:
        chunks = search(case.question, settings=cfg) if use_rag else []
        answer = generate_answer(
            case.question,
            chunks,
            settings=cfg,
            prompt_name=prompt_name,
        )

        scores = score_answer(answer, case)
        totals.append(scores["total"])
        details.append(
            {
                "case_id": case.id,
                "question": case.question,
                "answer_preview": answer[:200],
                "scores": scores,
            }
        )

    metrics = aggregate_llm_scores(totals)
    return {
        "prompt_name": prompt_name,
        "metrics": metrics,
        "details": details,
    }


def evaluate_refusal(prompt_name: str, settings: Settings | None = None) -> float:
    """Teste le refus honnête quand le contexte est vide."""
    cfg = settings or get_settings()
    answer = generate_answer(
        "Quels chantiers en Antarctique ?",
        [],
        settings=cfg,
        prompt_name=prompt_name,
    )
    return refusal_score(answer)


def run_llm_evaluation(
    settings: Settings | None = None,
    use_rag: bool = True,
    output_path: Path | None = None,
) -> dict:
    """Compare tous les prompts et retourne le meilleur."""
    cfg = settings or get_settings()
    cases = load_llm_ground_truth()
    prompt_names = list_prompts()

    logger.info("Évaluation LLM sur %s cas, %s prompts", len(cases), len(prompt_names))

    results_by_prompt: list[dict] = []
    for name in prompt_names:
        logger.info("Prompt %s…", name)
        result = evaluate_prompt(name, cases, settings=cfg, use_rag=use_rag)
        result["refusal_score"] = evaluate_refusal(name, settings=cfg)
        # Score final : moyenne cas RAG (70%) + refus (30%)
        combined = 0.7 * result["metrics"]["avg_total"] + 0.3 * result["refusal_score"]
        result["combined_score"] = combined
        results_by_prompt.append(result)

    best = max(results_by_prompt, key=lambda r: r["combined_score"])

    report = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "num_cases": len(cases),
        "prompts_evaluated": prompt_names,
        "results": results_by_prompt,
        "best_prompt": best["prompt_name"],
        "best_combined_score": best["combined_score"],
    }

    if output_path is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / "llm_eval_latest.json"

    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Meilleur prompt : %s (score=%.2f)", best["prompt_name"], best["combined_score"])

    return report
