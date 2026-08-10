"""Tests de la configuration RAG."""

from rag.config import DEFAULT_PDF_PATH, PROJECT_ROOT, get_settings


def test_project_root_exists() -> None:
    assert PROJECT_ROOT.is_dir()
    assert (PROJECT_ROOT / "rag" / "config.py").exists()


def test_default_pdf_path() -> None:
    assert DEFAULT_PDF_PATH.name == "liste_chantiers_latest.pdf"
    assert "pdfs" in DEFAULT_PDF_PATH.parts


def test_settings_defaults() -> None:
    settings = get_settings()
    assert settings.qdrant_collection == "chantiers_archeo"
    assert settings.chunk_size == 2000
    assert settings.top_k == 20
    assert settings.llm_model == "gpt-4o-mini"
