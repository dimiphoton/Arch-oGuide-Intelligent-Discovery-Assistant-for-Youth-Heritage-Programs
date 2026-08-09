"""Page chat Streamlit."""

from __future__ import annotations

import time

import streamlit as st

from rag.config import get_settings
from rag.pipeline import ask

st.set_page_config(page_title="Chat — ArchéoGuide", page_icon="💬", layout="wide")
st.title("💬 Chat ArchéoGuide")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Affiche l'historique
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for index, source in enumerate(message["sources"], start=1):
                    preview = source["text"][:200].replace("\n", " ")
                    st.caption(f"[{index}] p.{source['page']} — {preview}…")

# Saisie utilisateur
question = st.chat_input("Posez votre question sur les chantiers archéologiques…")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Recherche en cours…"):
            start = time.perf_counter()
            try:
                response = ask(question, settings=get_settings())
                latency_ms = (time.perf_counter() - start) * 1000
            except Exception as exc:
                st.error(f"Erreur : {exc}")
                st.stop()

        st.markdown(response.answer)

        if response.rewritten_query and response.rewritten_query != question:
            st.caption(f"Requête reformulée : _{response.rewritten_query}_")

        sources_data = [
            {
                "text": s.text,
                "page": s.page_number,
                "score": s.score,
            }
            for s in response.sources
        ]

        if sources_data:
            with st.expander("Sources"):
                for index, source in enumerate(sources_data, start=1):
                    preview = source["text"][:200].replace("\n", " ")
                    st.caption(f"[{index}] p.{source['page']} (score={source['score']:.3f}) — {preview}…")

        # Feedback utilisateur (stocké en session ; branch monitoring pour persistance)
        col1, col2 = st.columns(2)
        feedback_key = f"fb_{len(st.session_state.messages)}"
        if col1.button("👍 Utile", key=f"{feedback_key}_up"):
            st.session_state.setdefault("pending_feedback", []).append(
                {"question": question, "feedback": "up", "latency_ms": latency_ms}
            )
            st.toast("Merci pour votre retour !")
        if col2.button("👎 Pas utile", key=f"{feedback_key}_down"):
            st.session_state.setdefault("pending_feedback", []).append(
                {"question": question, "feedback": "down", "latency_ms": latency_ms}
            )
            st.toast("Merci, nous améliorerons les réponses.")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response.answer,
            "sources": sources_data,
        }
    )
