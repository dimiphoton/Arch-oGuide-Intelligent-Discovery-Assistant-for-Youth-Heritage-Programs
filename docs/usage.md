# Usage

The product UI is in **French**. Ask questions in French. Reviewers who do not speak French can still follow the screenshots and the English notes below.

**Live demo:** [https://archoguide.onrender.com/Chat](https://archoguide.onrender.com/Chat)

On the free Render plan, the first request after idle time can take a few minutes (index restore). Reload if the chat says the knowledge base is not ready.

---

## Walkthrough (Streamlit)

1. Open **Home** — you should see `Base prête` and the number of indexed site records (about 80).
2. Open **Chat** and ask a natural-language question.
3. Read the answer, then expand **Sources** (PDF page + score).
4. Use **👍 Utile** / **👎 Pas utile** — feedback is stored in `data/logs/queries.jsonl`.
5. Open **Monitoring** for volume, latency, feedback, and top questions.
6. Open **Carte** to filter sites by region, status, or city proximity.

### Example questions

| Intent | Question (French) |
|---|---|
| Volunteers by region | *Quels chantiers acceptent des volontaires en Bretagne ?* |
| Family visit | *Où visiter un chantier en famille près de Lyon ?* |
| School group | *Quels chantiers proposent une initiation pour des collégiens ?* |
| Map | *Montre-moi les chantiers en Auvergne-Rhône-Alpes* |

### Example: volunteers in Brittany

**Input**

> Quels chantiers acceptent des volontaires en Bretagne ?

**Observed output** (live demo, 16 Aug 2026)

- Short intro: no Brittany campaign currently accepts new volunteers (all `COMPLET` or `CAMPAGNE ACHEVÉE` in the official PDF).
- Structured list of the matching sites (name, region, town, dates, status, type, contact).
- `Sources :` with PDF page numbers (`p. 9` … `p. 12`).
- Query rewrite caption (the LLM restated the question before retrieval).
- Latency caption (about 8.8 s end-to-end on Render).
- 👍 / 👎 buttons.

![Chat — Brittany volunteer query](images/ui-chat.png)

This is the behaviour we want: the model **does not invent open digs**. It reports the official status and still lists the relevant sites with citations.

### Home, monitoring, map

![Home](images/ui-home.png)

![Monitoring dashboard](images/ui-monitoring.png)

![Map of sites](images/ui-carte.png)

---

## CLI

Needs a running Qdrant collection and `OPENAI_API_KEY`.

```bash
python scripts/ask.py "Quels chantiers acceptent des volontaires en Bretagne ?"
python scripts/ask.py -k 8 "Visites de chantiers pour des collégiens"
python scripts/ask.py --no-rewrite --no-rerank "..."
```

The CLI prints the answer and the source chunks (page + score). Queries are logged the same way as the UI, so they appear on the Monitoring page.

---

## Retrieval modes

Set `retrieval_mode` in `.env` or `rag/config.py`:

| Mode | What it does |
|---|---|
| `vector` | Semantic search (OpenAI embeddings + Qdrant) |
| `bm25` | Keyword search (`rank-bm25`) |
| `hybrid` | Reciprocal Rank Fusion of vector + BM25 (**default**) |
| Query rewriting | LLM rewrites the question before search (on by default) |
| Re-ranking | LLM re-orders candidate chunks (on by default) |

See [evaluation.md](evaluation.md) for measured hit rate, MRR, and latency.

---

## Feedback and logs

Each `ask()` call appends a JSON line to `data/logs/queries.jsonl`:

- timestamp, question, answer preview, latency_ms, num_sources, feedback

The Streamlit **Monitoring** page reads that file and plots:

1. Requests per day
2. Latency over time
3. 👍 / 👎 rate
4. Latency distribution
5. Requests by hour
6. Top questions
