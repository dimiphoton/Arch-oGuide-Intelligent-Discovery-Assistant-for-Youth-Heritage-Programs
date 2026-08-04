#!/usr/bin/env python3
"""CLI pour l'évaluation comparative du retrieval."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.retrieval_eval import run_evaluation


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare vector / BM25 / hybrid sur le jeu de référence."
    )
    parser.add_argument("-k", "--top-k", type=int, default=5, help="Top-k pour les métriques")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Fichier JSON de sortie (défaut : eval/results/retrieval_eval_latest.json)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        report = run_evaluation(top_k=args.top_k, output_path=args.output)
    except Exception as exc:
        logging.error("Erreur évaluation : %s", exc)
        return 1

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nMeilleur mode : {report['best_mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
