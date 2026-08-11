"""Filtres de métadonnées déduits de la question, appliqués AVANT la recherche."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from qdrant_client.models import FieldCondition, Filter, HasIdCondition, MatchValue

from rag.catalog import detect_region
from rag.geo import (
    detect_commune,
    detect_departement,
    detect_nearby_query,
    geocode_place,
    get_geo_vocabulary,
    haversine_km,
    normalize_geo_label,
)

# L'utilisateur cherche à participer / trouver des places disponibles
# → on exclut les chantiers complets, achevés ou annulés dès la recherche.
AVAILABILITY_PATTERN = re.compile(
    r"places? (?:encore )?disponibles?|encore des places?|reste(?:-t-il|nt)? des places?"
    r"|[sm][’']inscrire|inscrire|inscription|participer|rejoindre|postuler|candidat"
    r"|peut-on (?:encore )?fouiller|devenir bénévole|être bénévole"
)


@dataclass
class MetadataFilter:
    """Contraintes structurées (région, commune, proximité…) déduites de la question."""

    region: str | None = None
    commune: str | None = None
    departement: str | None = None
    only_open: bool = False
    geo_center_lat: float | None = None
    geo_center_lon: float | None = None
    geo_radius_km: float | None = None
    allowed_chunk_ids: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            self.region is None
            and self.commune is None
            and self.departement is None
            and not self.only_open
            and self.geo_center_lat is None
            and not self.allowed_chunk_ids
        )

    def to_qdrant(self) -> Filter | None:
        """Filtre Qdrant appliqué en amont de la recherche vectorielle."""
        conditions = []
        if self.allowed_chunk_ids:
            conditions.append(HasIdCondition(has_id=self.allowed_chunk_ids))
        if self.region:
            conditions.append(FieldCondition(key="region", match=MatchValue(value=self.region)))
        if self.commune:
            conditions.append(FieldCondition(key="commune", match=MatchValue(value=self.commune)))
        if self.departement:
            conditions.append(FieldCondition(key="departement", match=MatchValue(value=self.departement)))
        if self.only_open:
            conditions.append(FieldCondition(key="statut", match=MatchValue(value="ouvert")))
        return Filter(must=conditions) if conditions else None

    def accepts(self, payload: dict) -> bool:
        """Même filtre, appliqué aux chunks côté BM25."""
        if self.allowed_chunk_ids:
            chunk_id = str(payload.get("chunk_id", ""))
            if chunk_id and chunk_id not in self.allowed_chunk_ids:
                return False
        if self.region and payload.get("region") != self.region:
            return False
        if self.commune and normalize_geo_label(str(payload.get("commune", ""))) != normalize_geo_label(
            self.commune
        ):
            return False
        if self.departement and normalize_geo_label(str(payload.get("departement", ""))) != normalize_geo_label(
            self.departement
        ):
            return False
        if self.only_open and payload.get("statut") != "ouvert":
            return False
        if self.geo_center_lat is not None and self.geo_center_lon is not None and self.geo_radius_km:
            lat = payload.get("lat")
            lon = payload.get("lon")
            if lat is None or lon is None:
                return False
            distance = haversine_km(
                self.geo_center_lat,
                self.geo_center_lon,
                float(lat),
                float(lon),
            )
            if distance > self.geo_radius_km:
                return False
        return True


def _build_radius_chunk_ids(
    center_lat: float,
    center_lon: float,
    radius_km: float,
) -> list[str]:
    """Liste les chunk_id dans le rayon (scroll Qdrant)."""
    from eval.corpus import load_corpus

    chunks = load_corpus()
    ids: list[str] = []
    for chunk in chunks:
        lat = chunk.payload.get("lat")
        lon = chunk.payload.get("lon")
        if lat is None or lon is None:
            continue
        if haversine_km(center_lat, center_lon, float(lat), float(lon)) <= radius_km:
            ids.append(chunk.chunk_id)
    return ids


def build_metadata_filter(question: str, *, load_vocab: bool = True) -> MetadataFilter:
    """Déduit les filtres métadonnées de la question utilisateur."""
    communes: list[str] = []
    departements: list[str] = []
    if load_vocab:
        communes, departements = get_geo_vocabulary()

    nearby = detect_nearby_query(question)
    geo_center_lat: float | None = None
    geo_center_lon: float | None = None
    geo_radius_km: float | None = None
    allowed_chunk_ids: list[str] = []

    if nearby:
        place, radius_km = nearby
        point = geocode_place(place)
        if point:
            geo_center_lat = point.lat
            geo_center_lon = point.lon
            geo_radius_km = radius_km
            allowed_chunk_ids = _build_radius_chunk_ids(point.lat, point.lon, radius_km)

    region = detect_region(question)
    commune = None if nearby else detect_commune(question, communes)
    departement = None if nearby else detect_departement(question, departements)

    return MetadataFilter(
        region=region,
        commune=commune,
        departement=departement,
        only_open=bool(AVAILABILITY_PATTERN.search(question.lower())),
        geo_center_lat=geo_center_lat,
        geo_center_lon=geo_center_lon,
        geo_radius_km=geo_radius_km,
        allowed_chunk_ids=allowed_chunk_ids,
    )
