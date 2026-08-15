#!/usr/bin/env python3
"""
Batterie de questions pour évaluer la qualité des réponses RAG en local.

Prérequis :
  1. Qdrant : docker compose -f docker/docker-compose.yml up -d qdrant
  2. Index   : python scripts/ensure_indexed.py
  3. .env    : OPENAI_API_KEY renseignée

Usage :
  python scripts/run_quality_check.py
  python scripts/run_quality_check.py --cases open_now,trap_corse
  python scripts/run_quality_check.py -o eval/results/ma_session.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from rag.catalog import is_availability_question, is_catalog_query
from rag.pipeline import ask

DEFAULT_OUTPUT = ROOT / "eval" / "results" / "quality_check_latest.json"

# Jeux de questions : adaptées au contexte « presque tout est fermé ».
QUALITY_CASES: list[dict] = [
    {
        "id": "open_now",
        "question": "Quels chantiers sont encore ouverts aux inscriptions en ce moment ?",
        "expect_route": "rag",
        "checks": ["no_full_catalog_dump"],
    },
    {
        "id": "open_bretagne",
        "question": "Y a-t-il au moins un chantier ouvert en Bretagne ? Si non, dis-le clairement.",
        "expect_route": "rag",
        "checks": ["honest_no_open"],
    },
    {
        "id": "count_total",
        "question": "Combien de chantiers sont recensés au total dans le document ?",
        "expect_route": "catalog",
        "checks": ["mentions_total_count"],
    },
    {
        "id": "count_open_bretagne",
        "question": "Combien de chantiers ouverts en Bretagne ?",
        "expect_route": "catalog",
        "checks": ["small_or_zero_count"],
    },
    {
        "id": "list_bretagne",
        "question": "Liste tous les chantiers en Bretagne.",
        "expect_route": "catalog",
    },
    {
        "id": "trap_corse",
        "question": "Donne-moi 3 chantiers ouverts en Corse auxquels je peux m'inscrire maintenant.",
        "expect_route": "rag",
        "checks": ["no_full_catalog_dump", "honest_no_open"],
    },
    {
        "id": "family_lyon",
        "question": "Où peut-on visiter un chantier en famille près de Lyon ?",
        "expect_route": "rag",
    },
    {
        "id": "prehistory_status",
        "question": "Cite deux chantiers sur la Préhistoire et indique leur statut.",
        "expect_route": "rag",
        "checks": ["mentions_status"],
    },
    {
        "id": "difference_statut",
        "question": "Quelle est la différence entre COMPLET et CAMPAGNE ACHEVÉE ?",
        "expect_route": "rag",
    },
]


@dataclass
class CaseResult:
    """Résultat d'une question de la batterie."""

    case_id: str
    question: str
    expect_route: str
    inferred_route: str
    latency_ms: float
    answer: str
    rewritten_query: str | None
    source_count: int
    checks: dict[str, bool] = field(default_factory=dict)
    check_notes: dict[str, str] = field(default_factory=dict)
    passed: bool = True
    error: str | None = None


def infer_route(question: str, latency_ms: float, rewritten_query: str | None) -> str:
    """Devine le chemin emprunté (catalogue vs RAG)."""
    if rewritten_query:
        return "rag"
    if is_catalog_query(question) and latency_ms < 400:
        return "catalog"
    return "rag"


def _check_no_full_catalog_dump(question: str, answer: str) -> tuple[bool, str]:
    lowered = answer.lower()
    if is_availability_question(question) or "ouvert" in question.lower():
        if "81 chantier" in lowered or "recense **81" in lowered:
            return False, "Dump des 81 fiches au lieu d'une réponse ciblée"
    return True, "OK"


def _check_honest_no_open(answer: str) -> tuple[bool, str]:
    lowered = answer.lower()
    honest_markers = (
        "aucun",
        "pas de chantier",
        "n'y a pas",
        "n'existe pas",
        "malheureusement",
        "complet",
        "achevée",
        "achevee",
        "annulée",
        "annulee",
    )
    if any(marker in lowered for marker in honest_markers):
        return True, "OK"
    return False, "Ne nuance pas l'absence de places ouvertes"


def _check_mentions_total_count(answer: str) -> tuple[bool, str]:
    if any(token in answer for token in ("81", "82")):
        return True, "OK"
    return False, "Comptage total non visible dans la réponse"


def _check_small_or_zero_count(answer: str) -> tuple[bool, str]:
    lowered = answer.lower()
    if "81 chantier" in lowered or "82 chantier" in lowered:
        return False, "Semble lister tout le catalogue au lieu de filtrer « ouvert »"
    if "aucun" in lowered or "**0 chantier" in lowered or "0 chantier" in lowered:
        return True, "OK (0 ouvert)"
    if any(f"{n} chantier" in lowered for n in range(1, 10)):
        return True, "OK (peu de résultats)"
    return True, "OK (à relire manuellement)"


def _check_mentions_status(answer: str) -> tuple[bool, str]:
    lowered = answer.lower()
    if any(word in lowered for word in ("complet", "achevée", "achevee", "ouvert", "annulée", "annulee")):
        return True, "OK"
    return False, "Statut de campagne absent de la réponse"


CHECKERS = {
    "no_full_catalog_dump": lambda question, answer: _check_no_full_catalog_dump(question, answer),
    "honest_no_open": lambda _question, answer: _check_honest_no_open(answer),
    "mentions_total_count": lambda _question, answer: _check_mentions_total_count(answer),
    "small_or_zero_count": lambda _question, answer: _check_small_or_zero_count(answer),
    "mentions_status": lambda _question, answer: _check_mentions_status(answer),
}


def run_case(case: dict) -> CaseResult:
    """Exécute une question et applique les vérifications heuristiques."""
    question = case["question"]
    case_id = case["id"]
    expect_route = case.get("expect_route", "rag")
    check_ids: list[str] = case.get("checks", [])

    try:
        response = ask(question, log=False)
    except Exception as exc:
        return CaseResult(
            case_id=case_id,
            question=question,
            expect_route=expect_route,
            inferred_route="error",
            latency_ms=0.0,
            answer="",
            rewritten_query=None,
            source_count=0,
            passed=False,
            error=str(exc),
        )

    inferred = infer_route(question, response.latency_ms, response.rewritten_query)
    result = CaseResult(
        case_id=case_id,
        question=question,
        expect_route=expect_route,
        inferred_route=inferred,
        latency_ms=round(response.latency_ms, 1),
        answer=response.answer,
        rewritten_query=response.rewritten_query,
        source_count=len(response.sources),
    )

    if inferred != expect_route:
        result.passed = False
        result.check_notes["route"] = f"Attendu {expect_route}, obtenu {inferred}"

    for check_id in check_ids:
        checker = CHECKERS[check_id]
        ok, note = checker(question, response.answer)
        result.checks[check_id] = ok
        result.check_notes[check_id] = note
        if not ok:
            result.passed = False

    return result


def print_summary(results: list[CaseResult]) -> None:
    """Affiche un résumé lisible dans le terminal."""
    passed = sum(1 for item in results if item.passed)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"Qualité RAG : {passed}/{total} cas OK")
    print(f"{'=' * 60}\n")

    for item in results:
        status = "OK" if item.passed else "KO"
        print(f"[{status}] {item.case_id} ({item.inferred_route}, {item.latency_ms:.0f} ms)")
        if item.error:
            print(f"     Erreur : {item.error}")
            continue
        preview = item.answer.replace("\n", " ")[:160]
        print(f"     Q : {item.question}")
        print(f"     R : {preview}…")
        if not item.passed:
            for key, note in item.check_notes.items():
                if key == "route" or note != "OK":
                    print(f"     ! {key} : {note}")
        print()


def ensure_ready(skip_index: bool) -> None:
    """Vérifie Qdrant + index avant la batterie."""
    import importlib.util

    from rag.config import get_settings

    settings = get_settings()
    print(f"Connexion Qdrant ({settings.qdrant_url})…")

    wait_path = ROOT / "scripts" / "wait_qdrant.py"
    spec = importlib.util.spec_from_file_location("wait_qdrant", wait_path)
    if spec is None or spec.loader is None:
        msg = f"Module introuvable : {wait_path}"
        raise ImportError(msg)
    wait_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wait_module)
    wait_module.wait_for_qdrant(url=settings.qdrant_url)

    if skip_index:
        return

    index_path = ROOT / "scripts" / "ensure_indexed.py"
    spec = importlib.util.spec_from_file_location("ensure_indexed", index_path)
    if spec is None or spec.loader is None:
        msg = f"Module introuvable : {index_path}"
        raise ImportError(msg)
    index_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(index_module)

    print("Vérification de l'index…")
    count = index_module.ensure_indexed()
    if count <= 0:
        msg = "Index vide — lancer : python scripts/ensure_indexed.py"
        raise RuntimeError(msg)
    print(f"Index prêt ({count} points)\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batterie qualité RAG (local).")
    parser.add_argument(
        "--cases",
        type=str,
        default="",
        help="IDs séparés par des virgules (ex. open_now,trap_corse). Défaut : tous.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Fichier JSON de sortie.",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Ne pas tenter ensure_indexed (index déjà chargé).",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    try:
        ensure_ready(skip_index=args.skip_index)
    except SystemExit:
        return 1
    except Exception as exc:
        logging.error("%s", exc)
        logging.error(
            "Démarrer Qdrant : docker compose -f docker/docker-compose.yml up -d qdrant"
        )
        return 1

    if args.cases.strip():
        wanted = {part.strip() for part in args.cases.split(",") if part.strip()}
        cases = [case for case in QUALITY_CASES if case["id"] in wanted]
        missing = wanted - {case["id"] for case in cases}
        if missing:
            logging.error("IDs inconnus : %s", ", ".join(sorted(missing)))
            return 1
    else:
        cases = QUALITY_CASES

    results: list[CaseResult] = []
    for index, case in enumerate(cases, start=1):
        print(f"({index}/{len(cases)}) {case['id']}…")
        results.append(run_case(case))
        time.sleep(0.5)  # évite de saturer l'API OpenAI

    print_summary(results)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "passed": sum(1 for item in results if item.passed),
        "total": len(results),
        "results": [asdict(item) for item in results],
    }
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rapport JSON : {args.output}")

    return 0 if all(item.passed for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
