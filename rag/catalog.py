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
    commune: str = ""
    departement: str = ""
    statut: str = ""
    lat: float | None = None
    lon: float | None = None


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


# Mots qui indiquent une question filtrée (âge, période, statut…) → retrieval sémantique,
# car le catalogue global ne sait pas répondre seul à ces critères.
DETAIL_FILTERS = (
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
    "encore",
    "actuellement",
    "maintenant",
)

# Indices de disponibilité actuelle → synthèse LLM plutôt que dump catalogue.
AVAILABILITY_HINTS = (
    "encore",
    "actuellement",
    "maintenant",
    "en ce moment",
    "à ce jour",
    "y a-t-il",
    "existe-t-il",
    "peut-on encore",
    "inscription",
    "inscrire",
)

# Motifs de statut de campagne détectables dans la question.
STATUT_PATTERNS: dict[str, tuple[str, ...]] = {
    "ouvert": ("ouvert", "ouverte", "ouverts", "ouvertes", "disponible", "disponibles"),
    "complet": ("complet", "complète", "complets", "complètes"),
    "achevee": ("achevee", "achevée", "achevees", "achevées", "terminee", "terminée"),
    "annulee": ("annulee", "annulée", "annulees", "annulées", "annule", "annulé"),
}

# Détection d'un décompte : « combien », « nombre de/total », « nb de », « au total »
COUNT_PATTERN = re.compile(r"\bcombien\b|\bnombre (de|total)\b|\bnb\b|\bau total\b")

# Détection d'une liste exhaustive
LIST_PATTERN = re.compile(
    r"\bliste\b|\blister\b|\bénumèr\w*|\benumer\w*|\binventaire\b|\brecens\w*"
    r"|\btou(?:s|tes) les (?:chantiers|sites|fouilles)\b"
    r"|\bl[’']ensemble des (?:chantiers|sites|fouilles)\b"
)

# Tableau récapitulatif (souvent formulé sans « liste » ni « tous les »)
TABLE_PATTERN = re.compile(
    r"\btableau\b|\btable\b|\btabulaire\b|\bsous forme de tableau\b|\bformat tableau\b"
)

# « Quels (sont les) chantiers… » — tolère jusqu'à 3 mots entre « quels » et le nom
QUELS_PATTERN = re.compile(r"\bquel(?:le)?s?\b(?:\s+\w+){0,3}\s+(chantiers?|fouilles?|sites?)\b")

STATUT_LABELS = {
    "ouvert": "Ouvert",
    "complet": "Complet",
    "achevee": "Campagne achevée",
    "annulee": "Campagne annulée",
}


def detect_statut_filter(question: str) -> str | None:
    """Détecte un filtre de statut de campagne (ouvert, complet, etc.)."""
    lowered = _strip_accents(question.lower())
    for statut, keywords in STATUT_PATTERNS.items():
        if any(keyword in lowered for keyword in keywords):
            return statut
    return None


def is_availability_question(question: str) -> bool:
    """
    True si la question porte sur la disponibilité actuelle.

    Ex. « Quels chantiers sont encore ouverts ? » → RAG (synthèse), pas dump des 81 fiches.
    Les comptages (« Combien de chantiers ouverts ? ») restent gérés par le catalogue filtré.
    """
    if detect_statut_filter(question) != "ouvert":
        return False
    if is_count_query(question):
        return False
    lowered = question.lower()
    if any(hint in lowered for hint in AVAILABILITY_HINTS):
        return True
    # « Quels chantiers ouverts en Bretagne ? » nécessite une réponse ciblée, pas la liste totale.
    return bool(QUELS_PATTERN.search(lowered))


def is_table_query(question: str) -> bool:
    """True si la question demande un tableau (markdown) plutôt qu'une liste libre."""
    return bool(TABLE_PATTERN.search(question.lower()))


def is_count_query(question: str) -> bool:
    """True si la question demande un décompte (« Combien de chantiers ? »)."""
    return bool(COUNT_PATTERN.search(question.lower()))


def is_catalog_query(question: str) -> bool:
    """
    True si la question demande un décompte / une liste exhaustive.

    Ex. « Combien de chantiers ? », « Liste tous les chantiers en Bretagne »
    Les questions filtrées (âge, période, type) restent en retrieval sémantique.
    """
    lowered = question.lower()

    # Disponibilité actuelle → LLM (réponse nuancée, refus honnête si tout est fermé).
    if is_availability_question(question):
        return False

    # Un critère de détail rend le catalogue global inutilisable
    # (ex. « Combien de chantiers acceptent des mineurs ? » ≠ total du document).
    if any(word in lowered for word in DETAIL_FILTERS):
        return False

    if COUNT_PATTERN.search(lowered):
        return True

    if LIST_PATTERN.search(lowered):
        return True

    if TABLE_PATTERN.search(lowered):
        return True

    # « Quels sont les chantiers (en Bretagne) ? » → catalogue.
    # Au singulier (« quel chantier me conseilles-tu ? »), on exige une région.
    match = QUELS_PATTERN.search(lowered)
    if match:
        noun = match.group(1)
        if noun.endswith("s"):
            return True
        return detect_region(question) is not None

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
                    commune=str(payload.get("commune", "")),
                    departement=str(payload.get("departement", "")),
                    statut=str(payload.get("statut", "")),
                    lat=float(payload["lat"]) if payload.get("lat") is not None else None,
                    lon=float(payload["lon"]) if payload.get("lon") is not None else None,
                )
            )
        if offset is None:
            break

    records = dedup_catalog(records)
    records.sort(key=lambda item: (item.region, item.site_name.lower()))
    return records


def dedup_catalog(records: list[ChantierRecord]) -> list[ChantierRecord]:
    """
    Supprime les doublons d'une même fiche (page + nom de site).

    Cas couverts : fiche découpée en plusieurs chunks, ou ré-ingestion
    sans --recreate qui laisse d'anciens points dans la collection.
    """
    seen: set[tuple[int, str]] = set()
    unique: list[ChantierRecord] = []
    for record in records:
        key = (record.page_number, record.site_name.lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def filter_catalog(
    records: list[ChantierRecord],
    region: str | None = None,
    commune: str | None = None,
    departement: str | None = None,
    statut: str | None = None,
    metadata_filter=None,
) -> list[ChantierRecord]:
    """Filtre le catalogue par région, commune, département, statut ou contrainte géographique."""
    filtered = records
    if region:
        filtered = [item for item in filtered if item.region == region]
    if statut:
        filtered = [item for item in filtered if item.statut == statut]
    if commune:
        from rag.geo import normalize_geo_label

        commune_norm = normalize_geo_label(commune)
        filtered = [item for item in filtered if normalize_geo_label(item.commune) == commune_norm]
    if departement:
        from rag.geo import normalize_geo_label

        dept_norm = normalize_geo_label(departement)
        filtered = [
            item for item in filtered if normalize_geo_label(item.departement) == dept_norm
        ]
    if metadata_filter is not None and metadata_filter.geo_center_lat is not None:
        filtered = [
            item
            for item in filtered
            if metadata_filter.accepts(
                {
                    "lat": item.lat,
                    "lon": item.lon,
                    "region": item.region,
                    "commune": item.commune,
                    "departement": item.departement,
                    "statut": item.statut,
                    "chunk_id": item.chunk_id,
                }
            )
        ]
    return filtered


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


def format_catalog_answer(
    records: list[ChantierRecord],
    region: str | None = None,
    statut: str | None = None,
) -> str:
    """
    Réponse complète et déterministe (sans LLM), groupée par région.

    Garantit que TOUS les chantiers filtrés sont listés, sans troncature possible.
    """
    scope_parts: list[str] = []
    if statut:
        scope_parts.append(STATUT_LABELS.get(statut, statut).lower())
    if region:
        scope_parts.append(f"en {region}")
    scope = f" {' '.join(scope_parts)}" if scope_parts else ""

    if not records:
        return (
            f"Aucun chantier{scope} recensé dans le document officiel à la date de publication du PDF."
        )

    lines = [f"Le document officiel recense **{len(records)} chantier(s)**{scope}.", ""]

    statut_labels = {
        "complet": " — COMPLET",
        "achevee": " — CAMPAGNE ACHEVÉE",
        "annulee": " — CAMPAGNE ANNULÉE",
    }
    current_region = None
    numero = 0
    for item in records:
        if item.region != current_region:
            if current_region is not None:
                lines.append("")
            current_region = item.region
            lines.append(f"**{current_region or 'Région non précisée'}**")
        numero += 1
        commune = f", {item.commune}" if item.commune else ""
        statut = statut_labels.get(item.statut, "")
        lines.append(f"{numero}. {item.site_name}{commune} (p. {item.page_number}){statut}")
    return "\n".join(lines)


def _escape_table_cell(value: str) -> str:
    """Échappe les caractères spéciaux markdown dans une cellule de tableau."""
    return value.replace("|", "\\|").replace("\n", " ")


def format_catalog_table(
    records: list[ChantierRecord],
    region: str | None = None,
    statut: str | None = None,
) -> str:
    """
    Tableau markdown complet, construit sans LLM.

    Garantit toutes les fiches filtrées — pas de troncature.
    """
    scope_parts: list[str] = []
    if statut:
        scope_parts.append(STATUT_LABELS.get(statut, statut).lower())
    if region:
        scope_parts.append(f"en {region}")
    scope = f" {' '.join(scope_parts)}" if scope_parts else ""

    if not records:
        return (
            f"Aucun chantier{scope} recensé dans le document officiel à la date de publication du PDF."
        )

    lines = [
        f"Le document officiel recense **{len(records)} chantier(s)**{scope}.",
        "",
        "| # | Site | Région | Commune | Département | Statut | Page |",
        "|---:|---|---|---|---|---|---:|",
    ]
    for index, item in enumerate(records, start=1):
        statut = STATUT_LABELS.get(item.statut, item.statut or "—")
        lines.append(
            "| "
            f"{index} | "
            f"{_escape_table_cell(item.site_name)} | "
            f"{_escape_table_cell(item.region or '—')} | "
            f"{_escape_table_cell(item.commune or '—')} | "
            f"{_escape_table_cell(item.departement or '—')} | "
            f"{statut} | "
            f"{item.page_number} |"
        )
    return "\n".join(lines)
