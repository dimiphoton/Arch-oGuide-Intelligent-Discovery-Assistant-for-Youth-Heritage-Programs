#!/usr/bin/env bash
# Démarre Qdrant + Streamlit pour le déploiement cloud (Render, etc.).
set -euo pipefail

cd /app
QDRANT_STORAGE="${QDRANT_STORAGE:-/app/data/qdrant_storage}"
mkdir -p "$QDRANT_STORAGE" data/pdfs

export QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6333}"
# Qdrant n'accepte pas --storage-path en CLI : le chemin se règle via env.
export QDRANT__STORAGE__STORAGE_PATH="$QDRANT_STORAGE"

echo ">> Démarrage Qdrant…"
qdrant &
QDRANT_PID=$!

python - <<'PY'
import sys
import time

from qdrant_client import QdrantClient

url = "http://127.0.0.1:6333"
for attempt in range(60):
    try:
        QdrantClient(url=url).get_collections()
        print(f"Qdrant prêt ({url})")
        break
    except Exception:
        time.sleep(1)
else:
    print("Qdrant n'a pas démarré à temps", file=sys.stderr)
    sys.exit(1)
PY

echo ">> Indexation en arrière-plan (si nécessaire)…"
python scripts/ensure_indexed.py >> /tmp/ingest.log 2>&1 &

PORT="${PORT:-8501}"
echo ">> Démarrage Streamlit sur le port ${PORT}…"
exec python -m streamlit run app/Home.py \
  --server.address 0.0.0.0 \
  --server.port "${PORT}" \
  --server.headless true
