"""Page dashboard monitoring Streamlit."""

from __future__ import annotations

import streamlit as st

try:
    import pandas as pd
except ImportError:
    pd = None

from monitoring.store import load_events

st.set_page_config(page_title="Monitoring — ArchéoGuide", page_icon="📊", layout="wide")
st.title("📊 Monitoring ArchéoGuide")

events = load_events()

if not events:
    st.info("Aucune requête enregistrée. Utilisez le **Chat** pour générer des données.")
    st.stop()

if pd is None:
    st.error("pandas requis : pip install -r requirements-ui.txt")
    st.stop()

df = pd.DataFrame(events)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["date"] = df["timestamp"].dt.date
df["hour"] = df["timestamp"].dt.hour

# KPIs
col1, col2, col3, col4 = st.columns(4)
col1.metric("Requêtes totales", len(df))
col2.metric("Latence moyenne (ms)", f"{df['latency_ms'].mean():.0f}")
col3.metric("Latence p95 (ms)", f"{df['latency_ms'].quantile(0.95):.0f}")
feedback_counts = df["feedback"].dropna().value_counts()
up = int(feedback_counts.get("up", 0))
down = int(feedback_counts.get("down", 0))
col4.metric("Feedback 👍 / 👎", f"{up} / {down}")

st.divider()

# 5+ graphiques
left, right = st.columns(2)

with left:
    st.subheader("1. Volume de requêtes par jour")
    daily = df.groupby("date").size().reset_index(name="count")
    daily["date"] = daily["date"].astype(str)
    st.bar_chart(daily.set_index("date"))

    st.subheader("3. Taux de feedback")
    if up + down > 0:
        fb_df = pd.DataFrame({"feedback": ["👍 up", "👎 down"], "count": [up, down]})
        st.bar_chart(fb_df.set_index("feedback"))
    else:
        st.caption("Pas encore de feedback.")

with right:
    st.subheader("2. Latence dans le temps")
    latency_series = df.set_index("timestamp")["latency_ms"]
    st.line_chart(latency_series)

    st.subheader("4. Distribution de latence")
    st.bar_chart(df["latency_ms"].value_counts(bins=10).sort_index())

st.subheader("5. Requêtes par heure de la journée")
hourly = df.groupby("hour").size().reset_index(name="count")
st.bar_chart(hourly.set_index("hour"))

st.subheader("6. Top questions")
top_q = df["question"].value_counts().head(10).reset_index()
top_q.columns = ["question", "count"]
st.dataframe(top_q, use_container_width=True, hide_index=True)

st.subheader("Journal récent")
st.dataframe(
    df[["timestamp", "question", "latency_ms", "num_sources", "feedback"]].tail(20),
    use_container_width=True,
    hide_index=True,
)
