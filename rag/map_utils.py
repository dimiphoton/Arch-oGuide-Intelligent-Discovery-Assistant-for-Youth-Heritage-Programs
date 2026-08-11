"""Utilitaires de carte interactive (Folium)."""

from __future__ import annotations

import folium
from folium.plugins import MarkerCluster

from rag.geo import MapSite

STATUT_COLORS = {
    "ouvert": "#22c55e",
    "complet": "#ef4444",
    "achevee": "#94a3b8",
    "annulee": "#f97316",
}

STATUT_LABELS = {
    "ouvert": "Ouvert",
    "complet": "Complet",
    "achevee": "Campagne achevée",
    "annulee": "Campagne annulée",
}


def build_folium_map(sites: list[MapSite], *, zoom: int = 6) -> folium.Map:
    """Construit une carte Folium centrée sur les chantiers."""
    if not sites:
        # Carte France par défaut
        fmap = folium.Map(location=[46.6, 2.5], zoom_start=6)
        folium.Marker(
            [46.6, 2.5],
            popup="Aucun chantier géolocalisé à afficher",
            icon=folium.Icon(color="gray"),
        ).add_to(fmap)
        return fmap

    avg_lat = sum(site.lat for site in sites) / len(sites)
    avg_lon = sum(site.lon for site in sites) / len(sites)
    fmap = folium.Map(location=[avg_lat, avg_lon], zoom_start=zoom)
    cluster = MarkerCluster(name="Chantiers").add_to(fmap)

    for site in sites:
        statut_label = STATUT_LABELS.get(site.statut, site.statut or "—")
        popup_html = (
            f"<b>{site.site_name}</b><br>"
            f"{site.commune} ({site.departement})<br>"
            f"Région : {site.region}<br>"
            f"Statut : {statut_label}<br>"
            f"Page PDF : {site.page_number}"
        )
        folium.Marker(
            location=[site.lat, site.lon],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=site.site_name,
            icon=folium.Icon(color="green" if site.statut == "ouvert" else "red"),
        ).add_to(cluster)

    folium.LayerControl().add_to(fmap)
    return fmap
