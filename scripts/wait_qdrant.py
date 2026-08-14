#!/usr/bin/env python3
"""Attend que Qdrant soit prêt (utilisé par les scripts shell de déploiement)."""

from __future__ import annotations

import sys
import time

from qdrant_client import QdrantClient

DEFAULT_URL = "http://127.0.0.1:6333"
DEFAULT_TIMEOUT_SEC = 60


def wait_for_qdrant(url: str = DEFAULT_URL, timeout_sec: int = DEFAULT_TIMEOUT_SEC) -> None:
    """Lève SystemExit(1) si Qdrant ne répond pas à temps."""
    for attempt in range(timeout_sec):
        try:
            QdrantClient(url=url).get_collections()
            print(f"Qdrant prêt ({url})")
            return
        except Exception:
            time.sleep(1)
    print(f"Qdrant n'a pas démarré à temps ({url})", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    wait_for_qdrant()
