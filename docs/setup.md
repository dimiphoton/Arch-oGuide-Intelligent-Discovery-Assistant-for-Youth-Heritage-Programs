# Setup

How to run ArchéoGuide locally, with Docker, or via the hosted demo.

**Prerequisites**

- Python 3.11+
- Docker (for Qdrant, or for the full stack)
- An [OpenAI API key](https://platform.openai.com/api-keys) (`OPENAI_API_KEY`)

The fastest way to try the app is the [live demo](https://archoguide.onrender.com/Chat). The steps below are for reviewers who want to reproduce the pipeline.

---

## 1. Clone and install

```bash
git clone https://github.com/dimiphoton/Arch-oGuide-Intelligent-Discovery-Assistant-for-Youth-Heritage-Programs.git
cd Arch-oGuide-Intelligent-Discovery-Assistant-for-Youth-Heritage-Programs
python -m venv archoguide-env
```

Windows:

```bash
archoguide-env\Scripts\activate
```

Linux / macOS:

```bash
source archoguide-env/bin/activate
```

```bash
pip install -r requirements-dev.txt
```

`requirements-dev.txt` pulls in the core stack plus tests. Extra files:

| File | When you need it |
|---|---|
| `requirements.txt` | Core RAG + Qdrant client |
| `requirements-scraping.txt` | Download the official PDF |
| `requirements-ingest.txt` | PDF → chunks → Qdrant (Prefect, PyMuPDF, embeddings) |
| `requirements-ui.txt` | Streamlit UI + monitoring charts |
| `requirements-dev.txt` | Tests, lint, and the above |

---

## 2. Environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at least `OPENAI_API_KEY`.

| Variable | Required | Default | Role |
|---|---|---|---|
| `OPENAI_API_KEY` | yes (RAG) | empty | Embeddings + LLM |
| `QDRANT_URL` | no | `http://localhost:6333` | Vector database |
| `QDRANT_COLLECTION` | no | `chantiers_archeo` | Collection name |
| `EMBEDDING_MODEL` | no | `text-embedding-3-small` | OpenAI embeddings |
| `LLM_MODEL` | no | `gpt-4o-mini` | Answer generation |
| `LLM_PROMPT_NAME` | no | `structured_citations` | Prompt variant |
| `ENABLE_QUERY_REWRITE` | no | `true` | LLM query rewriting |
| `ENABLE_RERANK` | no | `true` | LLM re-ranking |
| `PDF_PATH` | no | `data/pdfs/liste_chantiers_latest.pdf` | Source PDF |

---

## 3. Download the source PDF

```bash
pip install -r requirements-scraping.txt
python scripts/run_scraper.py
```

The file is stored at `data/pdfs/liste_chantiers_latest.pdf` (gitignored). Useful flags:

```bash
python scripts/run_scraper.py --dry-run   # no download
python scripts/run_scraper.py --force     # ignore cache
```

A GitHub Action ([Scrape chantiers PDF](../.github/workflows/scrape-chantiers.yml)) runs daily at 06:00 UTC and stores the PDF as an artifact when the official file changes.

---

## 4. Start Qdrant and ingest

```bash
cd docker
docker compose up -d
cd ..
pip install -r requirements-ingest.txt
python scripts/run_ingest.py --dry-run    # extract + chunk, no API calls
python scripts/run_ingest.py              # embeddings + Qdrant upsert
python scripts/run_ingest.py --recreate   # drop and rebuild the collection
```

Qdrant UI: <http://localhost:6333>.

Prefect wrapper (same pipeline):

```bash
prefect flow run ingest/flow.py:ingest_flow
```

---

## 5. Check the install

```bash
python scripts/check_setup.py
```

This checks Python version, `.env`, the API key, the PDF, and imports.

---

## 6. Run the app

```bash
pip install -r requirements-ui.txt
python scripts/run_app.py
# equivalent: streamlit run app/Home.py
```

Open <http://localhost:8501>.

CLI (no UI):

```bash
python scripts/ask.py "Quels chantiers acceptent des volontaires en Bretagne ?"
```

---

## Docker (full stack)

From the repository root:

```bash
cp .env.example .env   # set OPENAI_API_KEY
cd docker
docker compose up -d --build
docker compose --profile ingest run --rm ingest
```

App: <http://localhost:8501>.

---

## Cloud (Render)

The live instance is a single service (Streamlit + embedded Qdrant) defined in `render.yaml`.

1. Connect the GitHub repo on [Render](https://render.com) → **New Blueprint**.
2. Set `OPENAI_API_KEY` in the Render dashboard.
3. First boot downloads the official PDF and indexes it in the background.

A pre-built snapshot (`data/index_snapshot.json.gz`) is restored at startup so Render does not call OpenAI for every cold start (~10 s instead of several minutes). The snapshot is rebuilt by [Prebuild index snapshot](../.github/workflows/prebuild-index.yml).

---

## Tests

```bash
pytest tests/
```
