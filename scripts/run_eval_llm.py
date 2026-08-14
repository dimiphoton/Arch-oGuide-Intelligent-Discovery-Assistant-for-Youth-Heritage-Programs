#!/usr/bin/env python3
"""CLI pour l'évaluation comparative des prompts LLM."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.llm_eval import run_llm_evaluation


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare les prompts LLM (factual / jeunes / structuré)."
    )
    parser.add_argument(
        "--no-rag",
        action="store_true",
        help="Évalue sans retrieval (contexte vide, test refus uniquement).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Fichier JSON de sortie.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        report = run_llm_evaluation(use_rag=not args.no_rag, output_path=args.output)
    except Exception as exc:
        logging.error("Erreur évaluation LLM : %s", exc)
        return 1

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nMeilleur prompt : {report['best_prompt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
