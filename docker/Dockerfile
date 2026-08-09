# Dockerfile ArchéoGuide — app Streamlit + dépendances Python
FROM python:3.11-slim

WORKDIR /app

# Dépendances système minimales pour PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ingest.txt requirements-ui.txt ./
RUN pip install --no-cache-dir -r requirements-ui.txt -r requirements-ingest.txt

COPY . .

EXPOSE 8501

ENV PYTHONUNBUFFERED=1
ENV QDRANT_URL=http://qdrant:6333

CMD ["python", "-m", "streamlit", "run", "app/Home.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
