#!/usr/bin/env python3
"""Point d'entrée CLI pour le scraper de la liste des chantiers."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Permet l'import du package depuis la racine du projet.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapping.scraper import ScraperError, run_scrape


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape le PDF officiel des chantiers archéologiques bénévoles."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force le téléchargement même si aucun changement n'est détecté.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche ce qui serait fait sans télécharger le PDF.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Active les logs détaillés.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        result = run_scrape(force=args.force, dry_run=args.dry_run)
    except ScraperError as exc:
        logging.error("Erreur scraper : %s", exc)
        return 1
    except Exception as exc:
        logging.error("Erreur inattendue : %s", exc)
        return 1

    status = result.get("status")
    if status == "skipped":
        logging.info("Terminé — aucun téléchargement nécessaire (%s).", result.get("reason"))
    elif status == "dry_run":
        logging.info("Terminé — dry-run, aucun fichier écrit.")
    elif status == "downloaded":
        logging.info("Terminé — PDF téléchargé : %s", result.get("local_path"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
