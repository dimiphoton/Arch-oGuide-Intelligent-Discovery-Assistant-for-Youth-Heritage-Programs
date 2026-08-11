"""Point d'entrée Streamlit (streamlit run app/Home.py)."""

from __future__ import annotations

import os

import streamlit as st

from rag.index_status import indexed_point_count, is_index_ready

st.set_page_config(
    page_title="ArchéoGuide",
    page_icon="🏛️",
    layout="wide",
)

st.title("ArchéoGuide")
st.markdown(
    "Assistant pour découvrir des **chantiers archéologiques** en France "
    "(bénévoles, visites, programmes scolaires)."
)

# Lien direct vers le chat (page Streamlit multipage)
st.page_link(
    "pages/1_Chat.py",
    label="Cliquez pour tester le chat",
    icon="💬",
    use_container_width=True,
)

points = indexed_point_count()
if is_index_ready():
    st.success(f"Base prête — {points} fiches indexées.")
else:
    st.warning(
        "Indexation en cours (première visite ou réveil du serveur). "
        "Le chat sera disponible dans quelques minutes."
    )

st.markdown(
    """
### Comment ça marche
1. Ouvrez le **Chat** via le bouton ci-dessus ou le menu latéral.
2. Posez une question en langage naturel, par exemple :
   - *Quels chantiers acceptent des volontaires en Bretagne ?*
   - *Où visiter un chantier en famille près de Lyon ?*
3. Consultez les **sources** (pages du PDF officiel) sous chaque réponse.

Explorez aussi la **Carte** pour filtrer les chantiers par région.
"""
)

demo_url = os.getenv("ARCHOGUIDE_PUBLIC_URL", "").strip()
if demo_url:
    st.caption(f"Démo en ligne : {demo_url}")
