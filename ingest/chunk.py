"""Découpage du texte en chunks pour l'indexation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from ingest.extract import PageText

# En-têtes de région du PDF (majuscules).
REGION_HEADERS = {
    "AUVERGNE-RHÔNE-ALPES",
    "BOURGOGNE-FRANCHE-COMTÉ",
    "BRETAGNE",
    "CENTRE-VAL-DE-LOIRE",
    "CORSE",
    "GRAND EST",
    "HAUTS-DE-FRANCE",
    "ÎLE-DE-FRANCE",
    "NORMANDIE",
    "NOUVELLE-AQUITAINE",
    "OCCITANIE",
    "PAYS DE LA LOIRE",
    "PROVENCE-ALPES-CÔTE D'AZUR",
}

# Statuts / bruit à ignorer comme titre de chantier.
SKIP_TITLES = {
    "COMPLET",
    "CAMPAGNE ACHEVÉE",
    "CAMPAGNE ANNULÉE",
    "S'Y RENDRE",
    "FOUILLER",
}

# Titre du chantier + ligne « Commune (Département) »
CHANTIER_START = re.compile(
    r"^([^\n]{2,90})\n([^\n]{2,90}\([^)]{2,40}\))\n",
    re.MULTILINE,
)


@dataclass
class TextChunk:
    """Fragment de texte prêt à être embeddé et indexé."""

    chunk_id: str
    text: str
    page_number: int
    chunk_index: int
    source: str
    region: str = ""
    site_name: str = ""


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """
    Découpe un texte en morceaux avec chevauchement.
    Coupe de préférence sur un espace pour ne pas briser les mots.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    text_len = len(cleaned)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        piece = cleaned[start:end]

        if end < text_len:
            last_space = piece.rfind(" ")
            if last_space > chunk_size // 2:
                end = start + last_space
                piece = cleaned[start:end]

        piece = piece.strip()
        if piece:
            chunks.append(piece)

        if end >= text_len:
            break
        start = max(end - chunk_overlap, start + 1)

    return chunks


def _normalize_region(line: str) -> str | None:
    """Retourne le nom de région si la ligne est un en-tête régional."""
    # Normalise apostrophes typographiques du PDF (U+2019, U+2018, etc.)
    cleaned = (
        line.strip()
        .upper()
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u02bc", "'")
    )
    if cleaned in REGION_HEADERS:
        return cleaned
    for region in REGION_HEADERS:
        if cleaned.replace("É", "E").replace("Ô", "O") == region.replace("É", "E").replace("Ô", "O"):
            return region
    return None


def _is_valid_chantier_title(title: str) -> bool:
    """Filtre les faux positifs (notes de page, statuts, régions)."""
    cleaned = title.strip()
    if not cleaned or len(cleaned) < 3:
        return False
    upper = cleaned.upper()
    if upper in REGION_HEADERS or upper in SKIP_TITLES:
        return False
    if "page suivante" in cleaned.lower():
        return False
    if cleaned.startswith("("):
        return False
    # Évite les lignes qui sont juste un statut collé
    if upper.startswith("NOUVEAU "):
        return True
    return True


def split_into_chantiers(pages: list[PageText]) -> list[dict]:
    """
    Découpe le PDF en fiches chantier (1 chantier = 1 chunk).

    Chaque page est annotée ; on suit la région courante entre les pages.
    """
    chantiers: list[dict] = []
    current_region = ""

    for page in pages:
        text = page.text
        matches = list(CHANTIER_START.finditer(text))

        # Positions des en-têtes régionaux dans la page
        region_marks: list[tuple[int, str]] = [
            (m.start(), region)
            for m in re.finditer(r"(?m)^(.+)$", text)
            if (region := _normalize_region(m.group(1)))
        ]

        # Région en début de page = dernière région connue (pages précédentes)
        region_before_page = current_region

        def region_at(pos: int) -> str:
            """Région active à une position donnée dans la page."""
            active = region_before_page
            for mark_pos, region in region_marks:
                if mark_pos <= pos:
                    active = region
                else:
                    break
            return active

        # Met à jour la région courante pour la page suivante
        if region_marks:
            current_region = region_marks[-1][1]

        if not matches:
            stripped = text.strip()
            if stripped and len(stripped) > 80:
                chantiers.append(
                    {
                        "text": stripped,
                        "page_number": page.page_number,
                        "region": region_before_page,
                        "site_name": "",
                    }
                )
            continue

        for index, match in enumerate(matches):
            title = match.group(1).strip()
            commune = match.group(2).strip()
            if not _is_valid_chantier_title(title):
                continue

            if _normalize_region(title):
                continue

            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block = text[start:end].strip()
            if len(block) < 40:
                continue

            region = region_at(start)
            header = f"Région : {region}\n" if region else ""
            chunk_text_value = f"{header}{block}"

            chantiers.append(
                {
                    "text": chunk_text_value,
                    "page_number": page.page_number,
                    "region": region,
                    "site_name": title,
                    "commune": commune,
                }
            )

    return chantiers


def build_chunks(
    pages: list[PageText],
    source: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    """
    Transforme les pages en chunks indexables.

    Priorité : 1 chantier = 1 chunk. Si trop long, découpe avec overlap.
    """
    chantiers = split_into_chantiers(pages)
    result: list[TextChunk] = []
    chunk_index = 0

    for chantier in chantiers:
        pieces = chunk_text(chantier["text"], chunk_size, chunk_overlap)
        if not pieces:
            pieces = [chantier["text"]]

        for piece_index, piece in enumerate(pieces):
            site = chantier.get("site_name", "")
            region = chantier.get("region", "")
            seed = f"{source}:{chantier['page_number']}:{site}:{piece_index}:{piece[:80]}"
            chunk_id = str(uuid5(NAMESPACE_URL, seed))
            result.append(
                TextChunk(
                    chunk_id=chunk_id,
                    text=piece,
                    page_number=chantier["page_number"],
                    chunk_index=chunk_index,
                    source=source,
                    region=region,
                    site_name=site,
                )
            )
            chunk_index += 1

    # Sécurité : si le parsing chantier échoue totalement, fallback page/taille
    if not result:
        for page in pages:
            for index, text in enumerate(chunk_text(page.text, chunk_size, chunk_overlap)):
                chunk_id = str(uuid5(NAMESPACE_URL, f"{source}:{page.page_number}:{index}:{text[:80]}"))
                result.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        text=text,
                        page_number=page.page_number,
                        chunk_index=index,
                        source=source,
                    )
                )

    return result
