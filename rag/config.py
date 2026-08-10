"""Configuration centralisée du projet (variables d'environnement + chemins)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PDF_PATH = PROJECT_ROOT / "data" / "pdfs" / "liste_chantiers_latest.pdf"
METADATA_PATH = PROJECT_ROOT / "data" / "metadata.json"


class Settings(BaseSettings):
    """Paramètres chargés depuis `.env` et l'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Chemins locaux
    project_root: Path = Field(default=PROJECT_ROOT)
    pdf_path: Path = Field(default=DEFAULT_PDF_PATH)

    # OpenAI
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    embedding_model: str = Field(default="text-embedding-3-small")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_prompt_name: str = Field(default="structured_citations")

    # Qdrant
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_collection: str = Field(default="chantiers_archeo")

    # Retrieval — top_k élevé pour lister plusieurs chantiers
    chunk_size: int = Field(default=2000)
    chunk_overlap: int = Field(default=100)
    top_k: int = Field(default=20)
    retrieval_mode: str = Field(default="hybrid")  # vector | bm25 | hybrid

    # RAG avancé (branche rag-advanced)
    enable_query_rewrite: bool = Field(default=True)
    enable_rerank: bool = Field(default=True)


def get_settings() -> Settings:
    """Retourne une instance de configuration (utile pour les tests)."""
    return Settings()
