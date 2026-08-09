"""Point d'entrée Streamlit (streamlit run app/Home.py)."""

from __future__ import annotations

import streamlit as st

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

st.info("Utilisez la barre latérale pour naviguer : **Chat** ou **Monitoring**.")

st.markdown("""
### Démarrage rapide
1. Vérifier que Qdrant tourne et que le PDF est ingéré
2. Configurer `OPENAI_API_KEY` dans `.env`
3. Ouvrir **Chat** dans le menu latéral
""")
