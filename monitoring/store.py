"""Persistance des logs de requêtes (JSONL)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rag.config import PROJECT_ROOT

LOG_DIR = PROJECT_ROOT / "data" / "logs"
LOG_PATH = LOG_DIR / "queries.jsonl"


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_query(
    question: str,
    answer: str,
    latency_ms: float,
    num_sources: int,
    feedback: str | None = None,
) -> str:
    """Enregistre une requête et retourne son ID."""
    _ensure_log_dir()
    event_id = str(uuid.uuid4())
    event = {
        "id": event_id,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "question": question,
        "answer_preview": answer[:300],
        "latency_ms": round(latency_ms, 1),
        "num_sources": num_sources,
        "feedback": feedback,
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event_id


def update_feedback(event_id: str, feedback: str) -> bool:
    """Met à jour le feedback d'un événement existant."""
    if not LOG_PATH.exists():
        return False

    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines: list[str] = []

    for line in lines:
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("id") == event_id:
            event["feedback"] = feedback
            updated = True
        new_lines.append(json.dumps(event, ensure_ascii=False))

    if updated:
        LOG_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


def load_events() -> list[dict[str, Any]]:
    """Charge tous les événements du fichier log."""
    if not LOG_PATH.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events
