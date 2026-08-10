"""Catalogue des chantiers indexés (comptage / listes complètes)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from qdrant_client import QdrantClient

from ingest.chunk import REGION_HEADERS
from ingest.index import get_qdrant_client
from rag.config import Settings, get_settings
from rag.types import RetrievedChunk

# Alias pour détecter une région dans la question utilisateur
REGION_ALIASES: dict[str, str] = {
    "auvergne": "AUVERGNE-RHÔNE-ALPES",
    "rhone-alpes": "AUVERGNE-RHÔNE-ALPES",
    "rhône-alpes": "AUVERGNE-RHÔNE-ALPES",
    "bourgogne": "BOURGOGNE-FRANCHE-COMTÉ",
    "franche-comte": "BOURGOGNE-FRANCHE-COMTÉ",
    "franche-comté": "BOURGOGNE-FRANCHE-COMTÉ",
    "bretagne": "BRETAGNE",
    "breton": "BRETAGNE",
    "centre-val-de-loire": "CENTRE-VAL-DE-LOIRE",
    "centre": "CENTRE-VAL-DE-LOIRE",
    "corse": "CORSE",
    "grand est": "GRAND EST",
    "alsace": "GRAND EST",
    "lorraine": "GRAND EST",
    "champagne": "GRAND EST",
    "hauts-de-france": "HAUTS-DE-FRANCE",
    "nord": "HAUTS-DE-FRANCE",
    "ile-de-france": "ÎLE-DE-FRANCE",
    "île-de-france": "ÎLE-DE-FRANCE",
    "paris": "ÎLE-DE-FRANCE",
    "normandie": "NORMANDIE",
    "nouvelle-aquitaine": "NOUVELLE-AQUITAINE",
    "aquitaine": "NOUVELLE-AQUITAINE",
    "occitanie": "OCCITANIE",
    "pays de la loire": "PAYS DE LA LOIRE",
    "provence": "PROVENCE-ALPES-CÔTE D'AZUR",
    "paca": "PROVENCE-ALPES-CÔTE D'AZUR",
    "cote d'azur": "PROVENCE-ALPES-CÔTE D'AZUR",
    "côte d'azur": "PROVENCE-ALPES-CÔTE D'AZUR",
}


@dataclass
class ChantierRecord:
    """Fiche chantier issue de Qdrant."""

    site_name: str
    region: str
    page_number: int
    text: str
    source: str
    chunk_id: str


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def detect_region(question: str) -> str | None:
    """Détecte une région mentionnée dans la question."""
    lowered = question.lower()
    # Priorité aux alias les plus longs
    for alias in sorted(REGION_ALIASES.keys(), key=len, reverse=True):
        if alias in lowered:
            return REGION_ALIASES[alias]
    # Match direct sur les en-têtes
    lowered_plain = _strip_accents(lowered)
    for region in REGION_HEADERS:
        if _strip_accents(region.lower()) in lowered_plain:
            return region
    return None


def is_catalog_query(question: str) -> bool:
    """
    True si la question demande un décompte / une liste exhaustive.

    Ex. « Combien de chantiers ? », « Liste tous les chantiers en Bretagne »
    Les questions filtrées (âge, période, type) restent en retrieval sémantique.
    """
    lowered = question.lower()

    if re.search(r"\bcombien\b|\bnombre (de|total)\b", lowered):
        return True

    if re.search(r"\bliste\b|\blister\b|\btous les chantiers\b|\binventaire\b|\brecens\w*\b", lowered):
        return True

    # « Quels chantiers en Bretagne ? » → catalogue filtré par région
    # mais pas « Quels chantiers pour scolaires / mineurs / préhistoire ? »
    if re.search(r"\bquels? chantiers?\b|\bquelles? fouilles?\b", lowered):
        detail_filters = (
            "mineur",
            "moins de",
            "scolaire",
            "collégien",
            "enfant",
            "famille",
            "bénévole",
            "volontaire",
            "préhistoire",
            "romain",
            "médiéval",
            "antiquité",
            "visite",
            "juillet",
            "août",
            "été",
            "contact",
            "responsable",
            "places",
        )
        if any(word in lowered for word in detail_filters):
            return False
        return detect_region(question) is not None or "france" in lowered

    return False


def load_chantier_catalog(
    settings: Settings | None = None,
    client: QdrantClient | None = None,
) -> list[ChantierRecord]:
    """Charge toutes les fiches chantier (site_name non vide) depuis Qdrant."""
    cfg = settings or get_settings()
    qdrant = client or get_qdrant_client(cfg)

    if not qdrant.collection_exists(cfg.qdrant_collection):
        msg = f"Collection '{cfg.qdrant_collection}' absente — lancer run_ingest.py"
        raise ValueError(msg)

    records: list[ChantierRecord] = []
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=cfg.qdrant_collection,
            limit=100,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            site_name = str(payload.get("site_name", "")).strip()
            if not site_name:
                continue
            records.append(
                ChantierRecord(
                    site_name=site_name,
                    region=str(payload.get("region", "")),
                    page_number=int(payload.get("page_number", 0)),
                    text=str(payload.get("text", "")),
                    source=str(payload.get("source", "")),
                    chunk_id=str(point.id),
                )
            )
        if offset is None:
            break

    records.sort(key=lambda item: (item.region, item.site_name.lower()))
    return records


def filter_catalog(
    records: list[ChantierRecord],
    region: str | None = None,
) -> list[ChantierRecord]:
    """Filtre le catalogue par région si demandé."""
    if not region:
        return records
    return [item for item in records if item.region == region]


def catalog_to_chunks(records: list[ChantierRecord]) -> list[RetrievedChunk]:
    """Convertit les fiches catalogue en chunks pour le LLM."""
    return [
        RetrievedChunk(
            chunk_id=item.chunk_id,
            text=item.text,
            page_number=item.page_number,
            score=1.0,
            source=item.source,
        )
        for item in records
    ]


def format_catalog_summary(records: list[ChantierRecord], region: str | None = None) -> str:
    """Résumé textuel du catalogue (utile pour le prompt)."""
    scope = f"en {region}" if region else "dans le document officiel"
    lines = [
        f"Catalogue officiel : {len(records)} chantier(s) {scope}.",
        "Liste :",
    ]
    for index, item in enumerate(records, start=1):
        lines.append(
            f"{index}. {item.site_name} — {item.region or 'région non précisée'} (p. {item.page_number})"
        )
    return "\n".join(lines)
