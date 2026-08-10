#!/usr/bin/env python3
"""CLI pour l'étude de performance RAG (retrieval + ablations + latence e2e)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.performance_study import run_performance_study


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Étude complète de performance : modes retrieval, ablations, latence e2e."
    )
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Top-k pour les métriques")
    parser.add_argument(
        "--skip-ablations",
        action="store_true",
        help="Ignore rewrite/rerank (plus rapide, sans coût LLM rewrite/rerank).",
    )
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Ignore la latence end-to-end (génération LLM).",
    )
    parser.add_argument(
        "--e2e-limit",
        type=int,
        default=5,
        help="Nombre de questions pour le test e2e (défaut : 5).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Fichier JSON de sortie (défaut : eval/results/performance_study_latest.json)",
    )
    parser.add_argument(
        "--md",
        type=Path,
        default=None,
        help="Rapport Markdown (défaut : eval/ETUDE_PERFORMANCE.md)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        report = run_performance_study(
            top_k=args.top_k,
            skip_ablations=args.skip_ablations,
            skip_e2e=args.skip_e2e,
            e2e_limit=args.e2e_limit,
            output_json=args.output,
            output_md=args.md,
        )
    except Exception as exc:
        logging.error("Erreur étude de performance : %s", exc)
        return 1

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nMeilleur mode retrieval : {report['best_retrieval_mode']}")
    if report.get("best_advanced_config"):
        print(f"Meilleure config avancée : {report['best_advanced_config']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
