"""Filtres de métadonnées déduits de la question, appliqués AVANT la recherche."""

from __future__ import annotations

import re
from dataclasses import dataclass

from qdrant_client.models import FieldCondition, Filter, MatchValue

from rag.catalog import detect_region

# L'utilisateur cherche à participer / trouver des places disponibles
# → on exclut les chantiers complets, achevés ou annulés dès la recherche.
AVAILABILITY_PATTERN = re.compile(
    r"places? (?:encore )?disponibles?|encore des places?|reste(?:-t-il|nt)? des places?"
    r"|[sm][’']inscrire|inscrire|inscription|participer|rejoindre|postuler|candidat"
    r"|peut-on (?:encore )?fouiller|devenir bénévole|être bénévole"
)


@dataclass
class MetadataFilter:
    """Contraintes structurées (région, disponibilité) déduites de la question."""

    region: str | None = None
    only_open: bool = False

    def is_empty(self) -> bool:
        return self.region is None and not self.only_open

    def to_qdrant(self) -> Filter | None:
        """Filtre Qdrant appliqué en amont de la recherche vectorielle."""
        conditions = []
        if self.region:
            conditions.append(FieldCondition(key="region", match=MatchValue(value=self.region)))
        if self.only_open:
            conditions.append(FieldCondition(key="statut", match=MatchValue(value="ouvert")))
        return Filter(must=conditions) if conditions else None

    def accepts(self, payload: dict) -> bool:
        """Même filtre, appliqué aux chunks côté BM25."""
        if self.region and payload.get("region") != self.region:
            return False
        if self.only_open and payload.get("statut") != "ouvert":
            return False
        return True


def build_metadata_filter(question: str) -> MetadataFilter:
    """Déduit les filtres métadonnées de la question utilisateur."""
    return MetadataFilter(
        region=detect_region(question),
        only_open=bool(AVAILABILITY_PATTERN.search(question.lower())),
    )
