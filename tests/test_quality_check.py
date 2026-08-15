"""Tests heuristiques du script run_quality_check (sans Qdrant)."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "run_quality_check",
    ROOT / "scripts" / "run_quality_check.py",
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)

infer_route = module.infer_route
_check_honest_no_open = module._check_honest_no_open
_check_no_full_catalog_dump = module._check_no_full_catalog_dump
_check_small_or_zero_count = module._check_small_or_zero_count


def test_infer_route_catalog_fast() -> None:
    route = infer_route("Combien de chantiers ?", latency_ms=120.0, rewritten_query=None)
    assert route == "catalog"


def test_infer_route_rag_with_rewrite() -> None:
    route = infer_route("Question ?", latency_ms=50.0, rewritten_query="reformulée")
    assert route == "rag"


def test_no_full_catalog_dump_flags_81() -> None:
    question = "Quels chantiers sont encore ouverts ?"
    answer = "Le document officiel recense **81 chantier(s)**."
    ok, _ = _check_no_full_catalog_dump(question, answer)
    assert ok is False


def test_honest_no_open_accepts_aucun() -> None:
    ok, _ = _check_honest_no_open("Malheureusement, aucun chantier ouvert en Bretagne.")
    assert ok is True


def test_small_or_zero_count_rejects_81() -> None:
    ok, _ = _check_small_or_zero_count("Le document recense **81 chantier(s)** ouvert en Bretagne.")
    assert ok is False
