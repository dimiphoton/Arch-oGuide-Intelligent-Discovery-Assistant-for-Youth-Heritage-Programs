from pathlib import Path

PAGE_URL = (
    "https://www.culture.gouv.fr/thematiques/archeologie/"
    "ressources-documentaires/introduction-a-l-archeologie/"
    "la-liste-fouiller-en-benevole-ou-visiter-un-chantier-archeologique"
)
BASE_URL = "https://www.culture.gouv.fr"
USER_AGENT = "Arch-oGuide-Scraper/1.0 (Educational RAG project)"
REQUEST_TIMEOUT = 60

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_PATH = PROJECT_ROOT / "data" / "metadata.json"
PDF_DIR = PROJECT_ROOT / "data" / "pdfs"
LATEST_PDF_NAME = "liste_chantiers_latest.pdf"
