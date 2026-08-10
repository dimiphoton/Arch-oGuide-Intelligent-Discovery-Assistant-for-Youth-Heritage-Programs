"""Étude de performance du RAG : qualité retrieval, ablations, latence."""

from __future__ import annotations

import json
import logging
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval.metrics import (
    EvalQuery,
    aggregate_metrics,
    hit_rate_at_k,
    reciprocal_rank,
)
from eval.retrieval_eval import load_ground_truth
from rag.config import Settings, get_settings
from rag.query_rewrite import rewrite_query
from rag.rerank import rerank_chunks
from rag.retrieval import RetrievalMode, search

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results"
REPORT_PATH = Path(__file__).parent / "ETUDE_PERFORMANCE.md"


def _percentile(values: list[float], p: float) -> float:
    """Percentile simple (p entre 0 et 100)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (p / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _latency_stats(latencies_ms: list[float]) -> dict[str, float]:
    """Résume une série de latences en ms."""
    if not latencies_ms:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    return {
        "mean_ms": round(statistics.mean(latencies_ms), 1),
        "p50_ms": round(_percentile(latencies_ms, 50), 1),
        "p95_ms": round(_percentile(latencies_ms, 95), 1),
    }


def evaluate_retrieval_with_latency(
    queries: list[EvalQuery],
    mode: RetrievalMode,
    top_k: int,
    settings: Settings,
) -> dict[str, Any]:
    """Évalue un mode de retrieval (hit rate, MRR, latence)."""
    hits: list[float] = []
    rrs: list[float] = []
    latencies: list[float] = []

    for query in queries:
        start = time.perf_counter()
        results = search(query.question, top_k=top_k, mode=mode, settings=settings)
        latencies.append((time.perf_counter() - start) * 1000)
        hits.append(hit_rate_at_k(results, query, top_k))
        rrs.append(reciprocal_rank(results, query))

    metrics = aggregate_metrics(hits, rrs)
    return {
        "mode": mode,
        "metrics": metrics,
        "latency": _latency_stats(latencies),
    }


def evaluate_advanced_config(
    queries: list[EvalQuery],
    top_k: int,
    settings: Settings,
    use_rewrite: bool = False,
    use_rerank: bool = False,
    mode: RetrievalMode = "hybrid",
) -> dict[str, Any]:
    """
    Ablation rewrite / rerank sur le retrieval (sans génération LLM finale).

    Mesure la qualité des sources renvoyées au générateur.
    """
    hits: list[float] = []
    rrs: list[float] = []
    latencies: list[float] = []

    for query in queries:
        start = time.perf_counter()
        search_query = (
            rewrite_query(query.question, settings=settings)
            if use_rewrite
            else query.question
        )
        candidate_k = top_k * 3 if use_rerank else top_k
        chunks = search(search_query, top_k=candidate_k, mode=mode, settings=settings)

        if use_rerank and chunks:
            chunks = rerank_chunks(query.question, chunks, top_k=top_k, settings=settings)
        else:
            chunks = chunks[:top_k]

        latencies.append((time.perf_counter() - start) * 1000)
        hits.append(hit_rate_at_k(chunks, query, top_k))
        rrs.append(reciprocal_rank(chunks, query))

    label = f"hybrid{('+rewrite' if use_rewrite else '')}{('+rerank' if use_rerank else '')}"
    if not use_rewrite and not use_rerank:
        label = "hybrid (baseline)"

    metrics = aggregate_metrics(hits, rrs)
    return {
        "config": label,
        "rewrite": use_rewrite,
        "rerank": use_rerank,
        "metrics": metrics,
        "latency": _latency_stats(latencies),
    }


def evaluate_e2e_latency(
    questions: list[str],
    settings: Settings,
    rewrite: bool = False,
    rerank: bool = False,
    top_k: int = 5,
) -> dict[str, Any]:
    """Latence end-to-end du pipeline ask() (retrieval + génération)."""
    from rag.pipeline import ask

    latencies: list[float] = []
    for question in questions:
        response = ask(
            question,
            top_k=top_k,
            settings=settings,
            rewrite=rewrite,
            rerank=rerank,
            log=False,
        )
        latencies.append(response.latency_ms)

    label = f"e2e{('+rewrite' if rewrite else '')}{('+rerank' if rerank else '')}"
    return {
        "config": label,
        "num_questions": len(questions),
        "latency": _latency_stats(latencies),
    }


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_ms(value: float) -> str:
    return f"{value:.0f} ms"


def render_markdown_report(report: dict[str, Any]) -> str:
    """Transforme le JSON d'étude en rapport Markdown lisible."""
    lines: list[str] = [
        "# Étude de performance — ArchéoGuide",
        "",
        f"*Généré le {report['timestamp']} (UTC).*",
        "",
        "## Objectif",
        "",
        "Comparer les stratégies de retrieval et les optimisations avancées "
        "(query rewriting, re-ranking) sur un jeu de questions de référence, "
        "en mesurant **qualité** (Hit Rate@k, MRR) et **latence**.",
        "",
        "## Protocole",
        "",
        f"- Jeu de référence : `{report['ground_truth']}` ({report['num_queries']} questions)",
        f"- `top_k` = {report['top_k']}",
        f"- Collection Qdrant : `{report['collection']}`",
        f"- Embedding : `{report['embedding_model']}`",
        f"- LLM : `{report['llm_model']}`",
        "- Pertinence : un chunk est pertinent s'il contient au moins un "
        "`expected_keywords` de la question",
        "",
    ]

    lines.extend(
        [
            "## 1. Comparaison des modes de retrieval",
            "",
            "| Mode | Hit Rate@k | MRR | Latence moyenne | P95 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in report["retrieval_modes"]:
        m = row["metrics"]
        lat = row["latency"]
        lines.append(
            f"| `{row['mode']}` | {_fmt_pct(m['hit_rate'])} | {m['mrr']:.3f} | "
            f"{_fmt_ms(lat['mean_ms'])} | {_fmt_ms(lat['p95_ms'])} |"
        )
    lines.extend(
        [
            "",
            f"**Meilleur mode (qualité)** : `{report['best_retrieval_mode']}`",
            "",
        ]
    )

    if report.get("ablations"):
        lines.extend(
            [
                "## 2. Ablations (rewrite / rerank) sur hybrid",
                "",
                "Mesure la qualité des chunks transmis au LLM, sans noter la génération.",
                "",
                "| Configuration | Hit Rate@k | MRR | Latence moyenne | P95 |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in report["ablations"]:
            m = row["metrics"]
            lat = row["latency"]
            lines.append(
                f"| `{row['config']}` | {_fmt_pct(m['hit_rate'])} | {m['mrr']:.3f} | "
                f"{_fmt_ms(lat['mean_ms'])} | {_fmt_ms(lat['p95_ms'])} |"
            )
        lines.extend(
            [
                "",
                f"**Meilleure config avancée** : `{report['best_advanced_config']}`",
                "",
            ]
        )

    if report.get("e2e_latency"):
        lines.extend(
            [
                "## 3. Latence end-to-end (pipeline `ask`)",
                "",
                "Inclut retrieval + génération de réponse (échantillon de questions).",
                "",
                "| Configuration | Questions | Moyenne | P50 | P95 |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in report["e2e_latency"]:
            lat = row["latency"]
            lines.append(
                f"| `{row['config']}` | {row['num_questions']} | "
                f"{_fmt_ms(lat['mean_ms'])} | {_fmt_ms(lat['p50_ms'])} | "
                f"{_fmt_ms(lat['p95_ms'])} |"
            )
        lines.append("")

    lines.extend(["## Conclusions", ""])
    conclusions = report.get("conclusions") or ["- Voir les tableaux ci-dessus."]
    for note in conclusions:
        lines.append(f"- {note}")

    lines.extend(
        [
            "",
            "---",
            "",
            "*Reproduire : `python scripts/run_performance_study.py`*",
            "",
        ]
    )
    return "\n".join(lines)


def _build_conclusions(report: dict[str, Any]) -> list[str]:
    """Déduit des conclusions courtes à partir des métriques."""
    notes: list[str] = []
    modes = {r["mode"]: r for r in report["retrieval_modes"]}
    best_mode = report["best_retrieval_mode"]
    best = modes[best_mode]
    notes.append(
        f"Le mode `{best_mode}` offre le meilleur couple Hit Rate / MRR "
        f"({_fmt_pct(best['metrics']['hit_rate'])} / {best['metrics']['mrr']:.3f})."
    )

    if "hybrid" in modes and "vector" in modes:
        delta = modes["hybrid"]["metrics"]["hit_rate"] - modes["vector"]["metrics"]["hit_rate"]
        if delta > 0:
            notes.append(
                f"L'hybride gagne {_fmt_pct(delta)} de Hit Rate par rapport au vectoriel pur."
            )

    ablations = report.get("ablations") or []
    if ablations:
        by_name = {r["config"]: r for r in ablations}
        baseline = by_name.get("hybrid (baseline)")
        full = by_name.get("hybrid+rewrite+rerank")
        if baseline and full:
            d_hit = full["metrics"]["hit_rate"] - baseline["metrics"]["hit_rate"]
            d_lat = full["latency"]["mean_ms"] - baseline["latency"]["mean_ms"]
            if d_hit >= 0:
                notes.append(
                    f"Rewrite + rerank améliorent le Hit Rate de {_fmt_pct(d_hit)} "
                    f"au prix d'environ {_fmt_ms(d_lat)} de latence supplémentaire."
                )
            else:
                notes.append(
                    f"Rewrite + rerank n'améliorent pas le Hit Rate ici ({_fmt_pct(d_hit)}) ; "
                    "utile surtout pour le ranking (MRR) ou la qualité perçue des réponses."
                )
            d_mrr = full["metrics"]["mrr"] - baseline["metrics"]["mrr"]
            if d_mrr > 0.01:
                notes.append(f"Le MRR progresse de {d_mrr:.3f} avec rewrite + rerank.")

    notes.append(
        "La config recommandée en production reste celle du meilleur score "
        "qualité/latence observé (voir tableaux)."
    )
    return notes


def run_performance_study(
    top_k: int = 5,
    settings: Settings | None = None,
    *,
    skip_ablations: bool = False,
    skip_e2e: bool = False,
    e2e_limit: int = 5,
    output_json: Path | None = None,
    output_md: Path | None = None,
) -> dict[str, Any]:
    """
    Lance l'étude complète et écrit JSON + Markdown.

    - Modes retrieval : toujours exécutés
    - Ablations rewrite/rerank : optionnelles (coût LLM)
    - Latence e2e : optionnelle (échantillon)
    """
    cfg = settings or get_settings()
    queries = load_ground_truth()

    logger.info("Étude de performance : %s questions, top_k=%s", len(queries), top_k)

    modes: list[RetrievalMode] = ["vector", "bm25", "hybrid"]
    retrieval_rows: list[dict[str, Any]] = []
    for mode in modes:
        logger.info("Mode retrieval : %s", mode)
        retrieval_rows.append(
            evaluate_retrieval_with_latency(queries, mode, top_k, cfg)
        )

    best_retrieval = max(
        retrieval_rows,
        key=lambda r: (r["metrics"]["hit_rate"], r["metrics"]["mrr"]),
    )

    ablation_rows: list[dict[str, Any]] = []
    if not skip_ablations:
        configs = [(False, False), (True, False), (False, True), (True, True)]
        for use_rewrite, use_rerank in configs:
            logger.info("Ablation rewrite=%s rerank=%s", use_rewrite, use_rerank)
            ablation_rows.append(
                evaluate_advanced_config(
                    queries,
                    top_k,
                    cfg,
                    use_rewrite=use_rewrite,
                    use_rerank=use_rerank,
                )
            )

    e2e_rows: list[dict[str, Any]] = []
    if not skip_e2e:
        sample = [q.question for q in queries[: max(1, e2e_limit)]]
        for rewrite, rerank in ((False, False), (True, True)):
            logger.info("Latence e2e rewrite=%s rerank=%s", rewrite, rerank)
            e2e_rows.append(
                evaluate_e2e_latency(
                    sample,
                    cfg,
                    rewrite=rewrite,
                    rerank=rerank,
                    top_k=top_k,
                )
            )

    best_advanced = None
    if ablation_rows:
        best_advanced = max(
            ablation_rows,
            key=lambda r: (r["metrics"]["hit_rate"], r["metrics"]["mrr"]),
        )["config"]

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ground_truth": "eval/ground_truth.json",
        "num_queries": len(queries),
        "top_k": top_k,
        "collection": cfg.qdrant_collection,
        "embedding_model": cfg.embedding_model,
        "llm_model": cfg.llm_model,
        "retrieval_modes": retrieval_rows,
        "best_retrieval_mode": best_retrieval["mode"],
        "ablations": ablation_rows,
        "best_advanced_config": best_advanced,
        "e2e_latency": e2e_rows,
    }
    report["conclusions"] = _build_conclusions(report)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = output_json or (RESULTS_DIR / "performance_study_latest.json")
    md_path = output_md or REPORT_PATH

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Rapport JSON : %s", json_path)

    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    logger.info("Rapport Markdown : %s", md_path)

    return report
