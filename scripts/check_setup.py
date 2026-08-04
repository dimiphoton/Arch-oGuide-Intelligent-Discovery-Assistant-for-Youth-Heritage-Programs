#!/usr/bin/env python3
"""Vérifie que l'environnement local est prêt pour ArchéoGuide."""

from __future__ import annotations

import sys
from pathlib import Path

# Permet l'import depuis la racine du projet.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check_python_version() -> tuple[bool, str]:
    version = sys.version_info
    if version >= (3, 11):
        return True, f"Python {version.major}.{version.minor}.{version.micro}"
    return False, f"Python {version.major}.{version.minor} — Python 3.11+ requis"


def check_env_file() -> tuple[bool, str]:
    env_path = ROOT / ".env"
    if env_path.exists():
        return True, ".env présent"
    return False, ".env absent — copier .env.example vers .env"


def check_openai_key() -> tuple[bool, str]:
    from rag.config import get_settings

    settings = get_settings()
    if settings.openai_api_key.strip():
        return True, "OPENAI_API_KEY configurée"
    return False, "OPENAI_API_KEY manquante (requise pour le RAG)"


def check_pdf() -> tuple[bool, str]:
    from rag.config import get_settings

    settings = get_settings()
    if settings.pdf_path.exists():
        size_mb = settings.pdf_path.stat().st_size / (1024 * 1024)
        return True, f"PDF trouvé ({size_mb:.1f} Mo) : {settings.pdf_path.name}"
    return False, (
        f"PDF absent : {settings.pdf_path}\n"
        "  -> lancer : pip install -r requirements-scraping.txt && python scripts/run_scraper.py"
    )


def check_imports() -> tuple[bool, str]:
    try:
        import openai  # noqa: F401
        import qdrant_client  # noqa: F401
        from rag.config import get_settings  # noqa: F401

        return True, "Imports principaux OK"
    except ImportError as exc:
        return False, f"Import manquant : {exc}\n  -> lancer : pip install -r requirements.txt"


def main() -> int:
    checks = [
        ("Version Python", check_python_version),
        ("Fichier .env", check_env_file),
        ("Clé OpenAI", check_openai_key),
        ("PDF source", check_pdf),
        ("Dépendances", check_imports),
    ]

    print("ArchéoGuide — vérification de l'environnement\n")
    all_ok = True
    warnings = 0

    for label, fn in checks:
        ok, message = fn()
        icon = "OK" if ok else "!!"
        print(f"  [{icon}] {label} : {message}")
        if not ok:
            # .env et OpenAI sont des avertissements en phase foundation
            if label in ("Fichier .env", "Clé OpenAI"):
                warnings += 1
            else:
                all_ok = False

    print()
    if all_ok and warnings == 0:
        print("Tout est prêt.")
        return 0
    if all_ok:
        print(f"Prêt pour le développement ({warnings} avertissement(s) — normal avant configuration).")
        return 0
    print("Certaines vérifications ont échoué. Corriger avant de continuer.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
