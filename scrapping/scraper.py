"""Scraper pour le PDF officiel des chantiers archéologiques bénévoles."""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from scrapping.config import (
    BASE_URL,
    LATEST_PDF_NAME,
    METADATA_PATH,
    PAGE_URL,
    PDF_DIR,
    PROJECT_ROOT,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

# Motif pour repérer le PDF principal (liste complète, ~13 Mo), pas la liste éthique.
MAIN_PDF_KEYWORDS = ("fouiller", "bénévole", "visiter un chantier")
EXCLUDED_PDF_KEYWORDS = ("chantier-ethique", "chantier éthique")


class ScraperError(Exception):
    """Erreur métier du scraper (réseau, parsing, etc.)."""


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def fetch_page(session: requests.Session | None = None) -> str:
    """Télécharge le HTML de la page culture.gouv.fr."""
    http = session or _session()
    response = http.get(PAGE_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def _extract_pub_date(soup: BeautifulSoup) -> tuple[str, str]:
    """Extrait la date de parution (ISO + libellé affiché)."""
    for time_tag in soup.find_all("time"):
        parent_text = time_tag.find_parent().get_text(" ", strip=True) if time_tag.find_parent() else ""
        if "Parution" in parent_text:
            pub_date_iso = time_tag.get("datetime", "").strip()
            pub_date_display = time_tag.get_text(strip=True)
            if pub_date_iso and pub_date_display:
                return pub_date_iso, pub_date_display

    raise ScraperError("Date de parution introuvable sur la page.")


def _is_main_pdf_link(link_text: str, href: str) -> bool:
    """Vérifie si le lien correspond au PDF principal de la liste."""
    normalized = f"{link_text} {href}".lower()
    if any(keyword in normalized for keyword in EXCLUDED_PDF_KEYWORDS):
        return False
    return all(keyword in normalized for keyword in MAIN_PDF_KEYWORDS)


def _extract_pdf_url(soup: BeautifulSoup) -> str:
    """Extrait l'URL du PDF principal depuis la page."""
    candidates: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        link_text = anchor.get_text(" ", strip=True)
        if ".pdf" not in href.lower() and "/mc/content/download/" not in href:
            continue
        if _is_main_pdf_link(link_text, href):
            candidates.append(urljoin(BASE_URL, href))

    if not candidates:
        raise ScraperError("Lien PDF principal introuvable sur la page.")

    # En cas de doublons, on garde le premier lien identifié.
    return candidates[0]


def parse_page(html: str) -> dict[str, str]:
    """Parse le HTML et retourne date de parution + URL PDF."""
    soup = BeautifulSoup(html, "lxml")
    pub_date_iso, pub_date_display = _extract_pub_date(soup)
    pdf_url = _extract_pdf_url(soup)

    return {
        "pub_date_iso": pub_date_iso,
        "pub_date": pub_date_display,
        "pdf_url": pdf_url,
    }


def load_metadata(path: Path = METADATA_PATH) -> dict[str, Any]:
    """Charge metadata.json (dict vide si absent ou vide)."""
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return {}
    return json.loads(content)


def save_metadata(metadata: dict[str, Any], path: Path = METADATA_PATH) -> None:
    """Sauvegarde metadata.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch_pdf_headers(session: requests.Session, pdf_url: str) -> dict[str, Any]:
    """Récupère ETag, Last-Modified et Content-Length via HEAD."""
    response = session.head(pdf_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    response.raise_for_status()

    content_length = response.headers.get("Content-Length")
    return {
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
        "content_length": int(content_length) if content_length else None,
    }


def needs_download(
    page_info: dict[str, str],
    metadata: dict[str, Any],
    pdf_headers: dict[str, Any] | None,
    force: bool = False,
) -> bool:
    """Décide si un téléchargement est nécessaire (3 niveaux de contrôle)."""
    if force:
        return True

    # metadata.json peut être présent sans le PDF (ex. déploiement Docker / Render).
    latest_path = PDF_DIR / LATEST_PDF_NAME
    if not latest_path.is_file():
        return True

    if not metadata:
        return True

    # Niveau 1 : métadonnées HTML (sans télécharger le PDF).
    if page_info.get("pub_date_iso") != metadata.get("pub_date_iso"):
        return True
    if page_info.get("pdf_url") != metadata.get("pdf_url"):
        return True

    if pdf_headers is None:
        return True

    # Niveau 2 : en-têtes HTTP du PDF.
    if pdf_headers.get("etag") and pdf_headers.get("etag") != metadata.get("etag"):
        return True
    if pdf_headers.get("last_modified") and pdf_headers.get("last_modified") != metadata.get("last_modified"):
        return True
    if pdf_headers.get("content_length") and pdf_headers.get("content_length") != metadata.get("content_length"):
        return True

    return False


def download_pdf(session: requests.Session, pdf_url: str, dest: Path) -> None:
    """Télécharge le PDF en streaming."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    response = session.get(pdf_url, timeout=REQUEST_TIMEOUT, stream=True)
    response.raise_for_status()

    with dest.open("wb") as file_obj:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file_obj.write(chunk)


def compute_sha256(path: Path) -> str:
    """Calcule le hash SHA-256 d'un fichier."""
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_path(pub_date_iso: str) -> Path:
    return PDF_DIR / f"liste_chantiers_{pub_date_iso}.pdf"


def run_scrape(force: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """
    Orchestration complète du scrape.

    Retourne un dict résumant l'action effectuée (downloaded, skipped, etc.).
    """
    session = _session()
    metadata = load_metadata()

    logger.info("Récupération de la page source…")
    html = fetch_page(session)
    page_info = parse_page(html)
    logger.info(
        "Page parsée : parution=%s, pdf_url=%s",
        page_info["pub_date"],
        page_info["pdf_url"],
    )

    pdf_headers: dict[str, Any] | None = None
    try:
        pdf_headers = fetch_pdf_headers(session, page_info["pdf_url"])
    except requests.RequestException as exc:
        logger.warning("HEAD sur le PDF impossible (%s), fallback sur métadonnées HTML.", exc)

    if not needs_download(page_info, metadata, pdf_headers, force=force):
        logger.info("Aucun changement détecté — téléchargement ignoré.")
        return {"status": "skipped", "reason": "no_change", "page_info": page_info}

    if dry_run:
        logger.info("[dry-run] Téléchargement qui serait effectué.")
        return {"status": "dry_run", "page_info": page_info, "pdf_headers": pdf_headers}

    archive_path = _archive_path(page_info["pub_date_iso"])
    latest_path = PDF_DIR / LATEST_PDF_NAME

    logger.info("Téléchargement du PDF vers %s…", archive_path)
    download_pdf(session, page_info["pdf_url"], archive_path)

    file_hash = compute_sha256(archive_path)

    # Niveau 3 : déduplication par hash.
    if file_hash == metadata.get("sha256"):
        logger.info("Hash identique au fichier précédent — doublon supprimé.")
        archive_path.unlink(missing_ok=True)
        return {"status": "skipped", "reason": "same_hash", "page_info": page_info}

    shutil.copy2(archive_path, latest_path)

    new_metadata = {
        "last_check": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pub_date_iso": page_info["pub_date_iso"],
        "pub_date": page_info["pub_date"],
        "pdf_url": page_info["pdf_url"],
        "etag": pdf_headers.get("etag") if pdf_headers else metadata.get("etag"),
        "last_modified": pdf_headers.get("last_modified") if pdf_headers else metadata.get("last_modified"),
        "content_length": pdf_headers.get("content_length") if pdf_headers else metadata.get("content_length"),
        "sha256": file_hash,
        "local_path": str(archive_path.relative_to(PROJECT_ROOT)),
    }
    save_metadata(new_metadata)

    logger.info("PDF sauvegardé : %s (sha256=%s…)", latest_path, file_hash[:12])
    return {
        "status": "downloaded",
        "page_info": page_info,
        "local_path": str(latest_path),
        "sha256": file_hash,
    }
