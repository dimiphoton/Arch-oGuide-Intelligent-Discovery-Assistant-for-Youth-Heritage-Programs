# Dockerfile ArchéoGuide — app Streamlit + Qdrant embarqué (déploiement cloud)
FROM python:3.11-slim

WORKDIR /app

ARG QDRANT_VERSION=1.12.5

# Dépendances système : PyMuPDF + binaire Qdrant
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libmupdf-dev \
    && curl -fsSL "https://github.com/qdrant/qdrant/releases/download/v${QDRANT_VERSION}/qdrant-x86_64-unknown-linux-gnu.tar.gz" \
    | tar -xz -C /usr/local/bin qdrant \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ingest.txt requirements-ui.txt requirements-scraping.txt ./
RUN pip install --no-cache-dir \
    -r requirements-ui.txt \
    -r requirements-ingest.txt \
    -r requirements-scraping.txt

COPY . .

# PDF absent du dépôt (.gitignore) : on le récupère au build pour éviter un échec au runtime.
RUN mkdir -p data/pdfs && python scripts/run_scraper.py -v

RUN chmod +x scripts/start_production.sh

EXPOSE 8501

ENV PYTHONUNBUFFERED=1
ENV QDRANT_URL=http://127.0.0.1:6333

CMD ["bash", "scripts/start_production.sh"]
