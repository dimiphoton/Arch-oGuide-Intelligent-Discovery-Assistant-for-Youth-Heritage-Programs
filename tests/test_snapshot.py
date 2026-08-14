"""Tests export/import snapshot Qdrant."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from ingest.snapshot import import_snapshot, snapshot_exists


def test_snapshot_exists_false_when_missing(tmp_path: Path, monkeypatch) -> None:
    import ingest.snapshot as snapshot_module

    monkeypatch.setattr(snapshot_module, "SNAPSHOT_FILE", tmp_path / "missing.json.gz")
    assert snapshot_exists() is False


def test_import_snapshot_returns_zero_when_missing(tmp_path: Path, monkeypatch) -> None:
    import ingest.snapshot as snapshot_module

    monkeypatch.setattr(snapshot_module, "SNAPSHOT_FILE", tmp_path / "missing.json.gz")
    assert import_snapshot() == 0


def test_import_snapshot_with_minimal_file(tmp_path: Path, monkeypatch) -> None:
    """Vérifie qu'un snapshot vide ne plante pas."""
    import ingest.snapshot as snapshot_module

    snapshot_file = tmp_path / "index_snapshot.json.gz"
    with gzip.open(snapshot_file, "wt", encoding="utf-8") as handle:
        json.dump([], handle)

    monkeypatch.setattr(snapshot_module, "SNAPSHOT_FILE", snapshot_file)
    assert snapshot_exists() is True
    assert import_snapshot() == 0
