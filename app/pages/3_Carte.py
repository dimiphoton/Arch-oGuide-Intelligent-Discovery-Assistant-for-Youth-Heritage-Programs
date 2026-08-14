"""Page carte des chantiers archéologiques."""

from __future__ import annotations

import streamlit as st
from streamlit_folium import st_folium

from rag.catalog import detect_region, filter_catalog, load_chantier_catalog
from rag.config import get_settings
from rag.filters import build_metadata_filter
from rag.geo import records_to_map_sites
from rag.index_status import is_index_ready
from rag.map_utils import STATUT_LABELS, build_folium_map

st.set_page_config(page_title="Carte — ArchéoGuide", page_icon="🗺️", layout="wide")
st.title("🗺️ Carte des chantiers archéologiques")

st.markdown(
    "Visualisez les chantiers géolocalisés à partir du document officiel. "
    "Les coordonnées proviennent de la [Base Adresse Nationale](https://adresse.data.gouv.fr/)."
)

if not is_index_ready():
    st.warning(
        "La base de connaissances est en cours de préparation. "
        "Patientez quelques minutes puis rechargez la page."
    )
    st.stop()

try:
    catalog = load_chantier_catalog(settings=get_settings())
except ValueError as exc:
    st.error(f"Impossible de charger la carte : {exc}")
    st.stop()

# Filtres latéraux
with st.sidebar:
    st.subheader("Filtres")
    regions = sorted({r.region for r in catalog if r.region})
    region_filter = st.selectbox("Région", ["Toutes"] + regions)
    statut_filter = st.selectbox(
        "Statut",
        ["Tous", "ouvert", "complet", "achevee", "annulee"],
        format_func=lambda value: STATUT_LABELS.get(value, value),
    )
    search_place = st.text_input(
        "Proximité d'une ville",
        placeholder="Ex. Lyon, Rennes…",
        help="Filtre les chantiers dans un rayon de 50 km (géocodage BAN).",
    )

filtered = catalog
if region_filter != "Toutes":
    filtered = filter_catalog(filtered, region=region_filter)
if statut_filter != "Tous":
    filtered = [item for item in filtered if item.statut == statut_filter]
if search_place.strip():
    metadata_filter = build_metadata_filter(f"près de {search_place.strip()}", load_vocab=False)
    filtered = filter_catalog(filtered, metadata_filter=metadata_filter)

sites = records_to_map_sites(filtered)
geolocated = len(sites)
total = len(filtered)

col1, col2, col3 = st.columns(3)
col1.metric("Chantiers affichés", total)
col2.metric("Géolocalisés", geolocated)
col3.metric("Sans coordonnées", total - geolocated)

if total - geolocated > 0:
    st.caption(
        f"{total - geolocated} chantier(s) sans coordonnées GPS "
        "(géocodage BAN indisponible ou commune non reconnue)."
    )

fmap = build_folium_map(sites)
st_folium(fmap, width=None, height=600, returned_objects=[])

if sites:
    st.subheader("Liste des chantiers sur la carte")
    for site in sites:
        statut = STATUT_LABELS.get(site.statut, site.statut or "—")
        st.markdown(
            f"- **{site.site_name}** — {site.commune} ({site.departement}), "
            f"{site.region} — _{statut}_ — p. {site.page_number}"
        )
