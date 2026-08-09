"""Page chat Streamlit."""

from __future__ import annotations

import streamlit as st

from monitoring.store import update_feedback
from rag.config import get_settings
from rag.pipeline import ask

st.set_page_config(page_title="Chat — ArchéoGuide", page_icon="💬", layout="wide")
st.title("💬 Chat ArchéoGuide")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for index, source in enumerate(message["sources"], start=1):
                    preview = source["text"][:200].replace("\n", " ")
                    st.caption(f"[{index}] p.{source['page']} — {preview}…")

question = st.chat_input("Posez votre question sur les chantiers archéologiques…")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Recherche en cours…"):
            try:
                response = ask(question, settings=get_settings())
            except Exception as exc:
                st.error(f"Erreur : {exc}")
                st.stop()

        st.markdown(response.answer)

        if response.rewritten_query and response.rewritten_query != question:
            st.caption(f"Requête reformulée : _{response.rewritten_query}_")

        sources_data = [
            {"text": s.text, "page": s.page_number, "score": s.score}
            for s in response.sources
        ]

        if sources_data:
            with st.expander("Sources"):
                for index, source in enumerate(sources_data, start=1):
                    preview = source["text"][:200].replace("\n", " ")
                    st.caption(
                        f"[{index}] p.{source['page']} (score={source['score']:.3f}) — {preview}…"
                    )

        if response.event_id:
            col1, col2 = st.columns(2)
            if col1.button("👍 Utile", key=f"up_{response.event_id}"):
                update_feedback(response.event_id, "up")
                st.toast("Merci pour votre retour !")
            if col2.button("👎 Pas utile", key=f"down_{response.event_id}"):
                update_feedback(response.event_id, "down")
                st.toast("Merci, nous améliorerons les réponses.")

        st.caption(f"Latence : {response.latency_ms:.0f} ms")

    st.session_state.messages.append(
        {"role": "assistant", "content": response.answer, "sources": sources_data}
    )
