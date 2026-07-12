# Arch-oGuide-Intelligent-Discovery-Assistant-for-Youth-Heritage-Programs
ArchéoGuide is a RAG application designed to connect young students and families with accessible archaeological excavation opportunities and educational heritage programs. By synthesizing PDF-based schedules and academic curricula into an intuitive conversational interface, the platform provides precise, context-aware information.


# ArchéoGuide: Intelligent Discovery Assistant for Youth Heritage Programs

ArchéoGuide is an end-to-end RAG (Retrieval-Augmented Generation) application built for the LLM Zoomcamp. It streamlines access to archaeological excavation opportunities for young enthusiasts by transforming unstructured official government documents into an interactive conversational experience.

## Problem Description

The ministry for Culture has a useful pdf for who seeks to make children discover archeology. I thought It was a good RAG project because:
- it is lightweight and quite clean
- it is typical of my AI projects: help people not lose time 

## Architecture & Features
- **Retrieval Flow**: Implements a RAG pipeline utilizing a vector database (Elasticsearch/Qdrant) combined with semantic search.
- **Ingestion Pipeline**: Fully automated ingestion pipeline using Python scripts to parse the official Ministry of Culture source.
- **Evaluation**: 
    - **Retrieval**: Comparison between keyword search and vector search (Hybrid Search).
    - **LLM**: Evaluation of prompt engineering techniques to ensure age-appropriate and accurate responses.
- **Best Practices**:
    - Hybrid Search (combining text and vector search).
    - Document re-ranking.
    - User query rewriting for improved retrieval.
- **Monitoring**: Dashboard for tracking queries, latency, and user feedback (thumbs up/down).
- **Interface**: Streamlit-based web application.
- **Containerization**: Full stack deployment using `docker-compose`.

## Data Source
The data is sourced from the French Ministry of Culture: [La liste fouiller en bénévole ou visiter un chantier archéologique](https://www.culture.gouv.fr/thematiques/archeologie/ressources-documentaires/introduction-a-l-archeologie/la-liste-fouiller-en-benevole-ou-visiter-un-chantier-archeologique)

## Project Scoring (Self-Assessment)
| Category | Status |
| :--- | :--- |
| Problem Description | 1/2 |
| Retrieval Flow | 0/2 |
| Retrieval Evaluation | 0/2 |
| LLM Evaluation | 0/2 |
| Interface | 0/2 |
| Ingestion Pipeline | 0/2 |
| Monitoring | 0/2 |
| Containerization | 0/2 |
| Reproducibility | 0/2 |
| Best Practices | 0/3 |
| Bonus | 0/2 (Cloud Deployment) |

---
*Developed for LLM Zoomcamp.*
