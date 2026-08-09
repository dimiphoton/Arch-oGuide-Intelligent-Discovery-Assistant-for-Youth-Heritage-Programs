"""Tests du module monitoring."""

import json
from pathlib import Path

import pytest

from monitoring import store


@pytest.fixture
def log_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "queries.jsonl"
    monkeypatch.setattr(store, "LOG_PATH", path)
    monkeypatch.setattr(store, "LOG_DIR", tmp_path)
    return path


def test_log_query_creates_event(log_file: Path) -> None:
    event_id = store.log_query("Question test ?", "Réponse.", 120.5, 3)
    assert event_id
    events = store.load_events()
    assert len(events) == 1
    assert events[0]["question"] == "Question test ?"
    assert events[0]["latency_ms"] == 120.5


def test_update_feedback(log_file: Path) -> None:
    event_id = store.log_query("Q?", "A.", 100.0, 2)
    assert store.update_feedback(event_id, "up") is True
    events = store.load_events()
    assert events[0]["feedback"] == "up"
