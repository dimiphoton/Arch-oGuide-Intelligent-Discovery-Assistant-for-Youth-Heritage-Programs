"""État de l'index Qdrant (utilisé par l'interface Streamlit)."""

from __future__ import annotations

from rag.config import Settings, get_settings
from ingest.index import get_qdrant_client


def indexed_point_count(settings: Settings | None = None) -> int:
    """Nombre de chunks indexés (0 si Qdrant indisponible ou collection absente)."""
    cfg = settings or get_settings()
    try:
        client = get_qdrant_client(cfg)
        if not client.collection_exists(cfg.qdrant_collection):
            return 0
        info = client.get_collection(cfg.qdrant_collection)
        return int(info.points_count or 0)
    except Exception:
        return 0


def is_index_ready(settings: Settings | None = None) -> bool:
    """True si au moins un chunk est disponible pour le RAG."""
    return indexed_point_count(settings) > 0
