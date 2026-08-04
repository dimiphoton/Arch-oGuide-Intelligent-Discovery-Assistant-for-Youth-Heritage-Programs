#!/usr/bin/env python3
"""CLI pour interroger ArchéoGuide (RAG)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.pipeline import ask


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pose une question à ArchéoGuide sur les chantiers archéologiques."
    )
    parser.add_argument("question", nargs="?", help="Question en langage naturel")
    parser.add_argument(
        "-k",
        "--top-k",
        type=int,
        default=None,
        help="Nombre de chunks à récupérer (défaut : config)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Logs détaillés")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    question = args.question
    if not question:
        question = input("Question : ").strip()
    if not question:
        logging.error("Question vide.")
        return 1

    try:
        response = ask(question, top_k=args.top_k)
    except Exception as exc:
        logging.error("Erreur RAG : %s", exc)
        return 1

    print("\n" + response.answer + "\n")

    if response.sources:
        print("--- Sources ---")
        for index, source in enumerate(response.sources, start=1):
            preview = source.text[:120].replace("\n", " ")
            print(f"  [{index}] p.{source.page_number} (score={source.score:.3f}) — {preview}…")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
