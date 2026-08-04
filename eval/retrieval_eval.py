"""Évaluation comparative des stratégies de retrieval."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from eval.metrics import (
    EvalQuery,
    aggregate_metrics,
    hit_rate_at_k,
    reciprocal_rank,
)
from rag.config import Settings, get_settings
from rag.retrieval import RetrievalMode, search

logger = logging.getLogger(__name__)

GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.json"
RESULTS_DIR = Path(__file__).parent / "results"


def load_ground_truth(path: Path = GROUND_TRUTH_PATH) -> list[EvalQuery]:
    """Charge le jeu de questions de référence."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        EvalQuery(
            id=item["id"],
            question=item["question"],
            expected_keywords=item["expected_keywords"],
            expected_pages=item.get("expected_pages"),
        )
        for item in raw
    ]


def evaluate_mode(
    queries: list[EvalQuery],
    mode: RetrievalMode,
    top_k: int,
    settings: Settings | None = None,
) -> dict:
    """Évalue une stratégie de retrieval sur toutes les questions."""
    cfg = settings or get_settings()
    hits: list[float] = []
    rrs: list[float] = []

    for query in queries:
        results = search(query.question, top_k=top_k, mode=mode, settings=cfg)
        hits.append(hit_rate_at_k(results, query, top_k))
        rrs.append(reciprocal_rank(results, query))

    metrics = aggregate_metrics(hits, rrs)
    return {"mode": mode, "metrics": metrics}


def run_evaluation(
    top_k: int = 5,
    settings: Settings | None = None,
    output_path: Path | None = None,
) -> dict:
    """
    Compare vector, bm25 et hybrid. Retourne le meilleur mode et sauvegarde les résultats.
    """
    cfg = settings or get_settings()
    queries = load_ground_truth()
    modes: list[RetrievalMode] = ["vector", "bm25", "hybrid"]

    logger.info("Évaluation sur %s questions, top_k=%s", len(queries), top_k)

    results_by_mode: list[dict] = []
    for mode in modes:
        logger.info("Mode %s…", mode)
        results_by_mode.append(evaluate_mode(queries, mode, top_k, settings=cfg))

    # Meilleur mode : priorité hit_rate puis mrr
    best = max(
        results_by_mode,
        key=lambda r: (r["metrics"]["hit_rate"], r["metrics"]["mrr"]),
    )

    report = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "top_k": top_k,
        "num_queries": len(queries),
        "results": results_by_mode,
        "best_mode": best["mode"],
        "recommended_retrieval_mode": best["mode"],
    }

    if output_path is None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / "retrieval_eval_latest.json"

    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Meilleur mode : %s (hit_rate=%.2f, mrr=%.2f)", best["mode"], best["metrics"]["hit_rate"], best["metrics"]["mrr"])

    return report
