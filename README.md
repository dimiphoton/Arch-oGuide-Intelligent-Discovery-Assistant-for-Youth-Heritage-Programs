# ArchéoGuide — Intelligent Discovery Assistant for Youth Heritage Programs

Application RAG (Retrieval-Augmented Generation) développée dans le cadre du **LLM Zoomcamp**.  
Elle aide les **jeunes**, **familles** et **enseignants** à trouver des chantiers archéologiques accessibles en France, à partir du document officiel du Ministère de la Culture.

---

## Problem Description

### Contexte

Chaque année, le [Ministère de la Culture](https://www.culture.gouv.fr/thematiques/archeologie/ressources-documentaires/introduction-a-l-archeologie/la-liste-fouiller-en-benevole-ou-visiter-un-chantier-archeologique) publie un **PDF de ~13 Mo** recensant les chantiers archéologiques où l'on peut **fouiller en bénévole** ou **visiter un site** — y compris des programmes adaptés aux **enfants et aux scolaires**.

### Problème

| Difficulté | Impact |
|---|---|
| Document long et dense (~centaines de pages) | Difficile à parcourir pour un parent ou un enseignant pressé |
| Informations éparpillées par région, période, type de public | Une simple recherche Ctrl+F ne suffit pas pour des questions en langage naturel |
| Mise à jour régulière du PDF | Risque d'informations obsolètes si on garde une copie locale |
| Public cible (jeunes, familles) | Besoin de réponses claires, adaptées et fiables — pas de jargon administratif |

**Exemples de questions auxquelles le PDF doit répondre, mais difficilement sans outil :**
- *« Quels chantiers acceptent des volontaires de moins de 16 ans en Bretagne cet été ? »*
- *« Où peut-on visiter un chantier en famille près de Lyon en juillet ? »*
- *« Quels chantiers proposent une initiation à la préhistoire pour des collégiens ? »*

### Solution : ArchéoGuide

ArchéoGuide transforme ce PDF officiel en **assistant conversationnel** :

1. **Scraping automatisé** — téléchargement et détection de nouvelles versions du PDF
2. **Ingestion** — découpage, indexation dans une base vectorielle (Qdrant)
3. **Retrieval hybride** — recherche sémantique + mots-clés, avec re-ranking
4. **Génération LLM** — réponses en langage naturel, adaptées au public jeune, avec citations des sources

### Pourquoi un RAG (et pas un LLM seul) ?

- Le LLM **seul** inventerait des chantiers inexistants (hallucinations).
- Le RAG **ancre** chaque réponse dans le PDF officiel : les informations restent **vérifiables** et **à jour**.
- La recherche vectorielle permet de comprendre l'**intention** derrière une question floue, ce qu'une recherche textuelle classique ne fait pas bien.

---

## Architecture & Roadmap (branches)

| Branche | Contenu | Statut |
|---|---|---|
| `scrapping` | Téléchargement automatique du PDF (GitHub Actions quotidien) | ✅ |
| `docs/foundation` | Structure projet, config, README, deps pinées | ✅ |
| `ingest` | Pipeline Prefect : PDF → chunks → Qdrant | ✅ |
| `rag-core` | Retrieval vectoriel + LLM, CLI | ✅ |
| `eval-retrieval` | Comparaison BM25 / vector / hybrid | ✅ |
| `rag-advanced` | Query rewriting + re-ranking | ✅ |
| `eval-llm` | Comparaison de prompts | ✅ |
| `ui-streamlit` | Interface chat Streamlit | ✅ |
| `monitoring` | Feedback + dashboard | 🚧 |
| `monitoring` | Feedback utilisateur + dashboard | ⬜ |
| `docker` | docker-compose complet | ⬜ |

---

## Structure du projet

```
Arch-oGuide/
├── app/              # Interface Streamlit (à venir)
├── rag/              # Config, retrieval, génération
├── ingest/           # Pipeline d'ingestion PDF
├── eval/             # Évaluations retrieval & LLM
├── scrapping/        # Scraper PDF culture.gouv.fr
├── scripts/          # CLI (scraper, check_setup, ask…)
├── tests/            # Tests unitaires
├── data/
│   ├── pdfs/         # PDF téléchargé (gitignored)
│   └── metadata.json # État du dernier scrape
├── docker/           # docker-compose (Qdrant)
├── requirements.txt          # Dépendances principales (pinées)
├── requirements-scraping.txt # Scraping PDF
├── requirements-ingest.txt   # Ingestion PDF → Qdrant (branche ingest)
├── requirements-ui.txt       # Streamlit (branche ui-streamlit)
└── requirements-dev.txt      # Tests & lint
```

---

## Quick Start

### 1. Cloner et installer

```bash
git clone https://github.com/dimiphoton/Arch-oGuide-Intelligent-Discovery-Assistant-for-Youth-Heritage-Programs.git
cd Arch-oGuide-Intelligent-Discovery-Assistant-for-Youth-Heritage-Programs
python -m venv .venv
# Windows : .venv\Scripts\activate
# Linux/Mac : source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
# Éditer .env et renseigner OPENAI_API_KEY
```

### 3. Télécharger le PDF source

```bash
pip install -r requirements-scraping.txt
python scripts/run_scraper.py
```

Le PDF est enregistré dans `data/pdfs/liste_chantiers_latest.pdf`.

### 4. Vérifier l'installation

```bash
python scripts/check_setup.py
```

---

## Ingestion (PDF → Qdrant)

Le module `ingest/` transforme le PDF en chunks indexés dans **Qdrant**, orchestré par un **flow Prefect**.

### 1. Démarrer Qdrant

```bash
cd docker
docker compose up -d
```

Qdrant est accessible sur `http://localhost:6333`.

### 2. Installer les dépendances d'ingestion

```bash
pip install -r requirements-ingest.txt
```

### 3. Lancer l'ingestion

```bash
python scripts/run_ingest.py --dry-run    # test extraction + chunking (sans API)
python scripts/run_ingest.py              # ingestion complète (OpenAI + Qdrant)
python scripts/run_ingest.py --recreate   # recrée la collection Qdrant
```

### Flow Prefect (automatisation)

```bash
# Via Prefect CLI
prefect flow run ingest/flow.py:ingest_flow

# Ou depuis Python
python -c "from ingest.flow import ingest_flow; ingest_flow()"
```

Pipeline : **extraction PyMuPDF** → **chunking** → **embeddings OpenAI** → **index Qdrant**.

---

## RAG (question / réponse)

Le module `rag/` implémente le flux retrieval + génération LLM.

### Prérequis

- PDF ingéré dans Qdrant (`python scripts/run_ingest.py`)
- `OPENAI_API_KEY` configurée dans `.env`

### Poser une question

```bash
python scripts/ask.py "Quels chantiers acceptent des volontaires en Bretagne ?"
python scripts/ask.py -k 8 "Visites de chantiers pour des collégiens"
```

La CLI affiche la réponse et les sources (page + score).

Mode de retrieval configurable via `.env` ou `rag/config.py` :
- `vector` — recherche sémantique pure
- `bm25` — mots-clés (rank-bm25)
- `hybrid` — fusion RRF vector + BM25 **(défaut, meilleur mode selon l'éval)**
- **Query rewriting** — reformulation LLM avant recherche (activé par défaut)
- **Re-ranking** — re-classement LLM des chunks candidats (activé par défaut)

```bash
python scripts/ask.py --no-rewrite --no-rerank "..."  # désactiver les optimisations
```

---

## Évaluation retrieval

Compare **vector**, **BM25** et **hybrid** sur 20 questions de référence (`eval/ground_truth.json`).

```bash
python scripts/run_eval_retrieval.py           # nécessite Qdrant + OPENAI_API_KEY
python scripts/run_eval_retrieval.py -k 5 -v
```

Résultats exportés dans `eval/results/retrieval_eval_latest.json` (hit rate, MRR, meilleur mode).

---

## Évaluation LLM

Compare **3 prompts** (`youth_friendly`, `factual_strict`, `structured_citations`) sur 8 questions de référence.

Métriques : couverture mots-clés, citations, refus honnête (contexte vide).

```bash
python scripts/run_eval_llm.py -v
python scripts/run_eval_llm.py --no-rag   # test refus uniquement
```

Résultats → `eval/results/llm_eval_latest.json`. Prompt par défaut : `structured_citations`.

---

## Interface Streamlit

```bash
pip install -r requirements-ui.txt
python scripts/run_app.py
# ou : streamlit run app/Home.py
```

- **Chat** : conversation avec sources citées
- **Monitoring** : dashboard (volume, latence, feedback, top questions)
- **👍 / 👎** : feedback enregistré dans `data/logs/queries.jsonl`

---

## Monitoring

Le dashboard Streamlit (**page Monitoring**) affiche 6 graphiques :
1. Volume de requêtes / jour
2. Latence dans le temps
3. Taux de feedback 👍/👎
4. Distribution de latence
5. Requêtes par heure
6. Top questions

Les requêtes CLI (`ask.py`) et Streamlit sont loggées automatiquement.

---

## Scraping

Le module `scrapping/` télécharge automatiquement le PDF officiel depuis culture.gouv.fr, avec détection de changements (date de parution, URL, ETag, hash SHA-256) pour éviter les retéléchargements inutiles.

```bash
python scripts/run_scraper.py              # scrape normal
python scripts/run_scraper.py --dry-run    # simulation sans téléchargement
python scripts/run_scraper.py --force      # force le téléchargement
```

### Automatisation (GitHub Actions)

Le workflow [Scrape chantiers PDF](.github/workflows/scrape-chantiers.yml) s'exécute **tous les jours** à 06:00 UTC et peut aussi être lancé manuellement (`workflow_dispatch`). En cas de nouvelle version, il met à jour `metadata.json` et publie le PDF en artifact GitHub (rétention 90 jours).

---

## Data Source

Document officiel : [La liste — fouiller en bénévole ou visiter un chantier archéologique](https://www.culture.gouv.fr/thematiques/archeologie/ressources-documentaires/introduction-a-l-archeologie/la-liste-fouiller-en-benevole-ou-visiter-un-chantier-archeologique) — Ministère de la Culture, Direction de l'archéologie.

---

## Tests

```bash
pytest tests/
```

---

## Project Scoring (Self-Assessment)

| Category | Status |
| :--- | :--- |
| Problem Description | 2/2 |
| Retrieval Flow | 2/2 |
| Retrieval Evaluation | 2/2 |
| LLM Evaluation | 2/2 |
| Interface | 2/2 |
| Ingestion Pipeline | 2/2 (scrape auto + pipeline Prefect/Qdrant) |
| Monitoring | 2/2 |
| Containerization | 1/2 (docker-compose Qdrant ; stack complète à venir) |
| Reproducibility | 2/2 |
| Best Practices | 3/3 (hybrid + rewrite + rerank) |
| Bonus | 0/2 (Cloud Deployment) |

---

*Developed for LLM Zoomcamp.*
