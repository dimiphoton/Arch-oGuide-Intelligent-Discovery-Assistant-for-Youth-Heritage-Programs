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

SKIP_TITLES = {
    "COMPLET",
    "CAMPAGNE ACHEVÉE",
    "CAMPAGNE ANNULÉE",
    "S'Y RENDRE",
    "FOUILLER",
    "CONTACT",
    "RESPONSABLE",
}

# Ligne « Commune (Département) » — ex. Ambérieu-en-Bugey (Ain)
COMMUNE_LINE = re.compile(r"^.+\([^)]{2,60}\)$")

# Statuts courts du PDF → phrases explicites pour le LLM et les embeddings
STATUT_PHRASES = {
    "ouvert": "campagne ouverte, des places peuvent être disponibles pour les bénévoles",
    "complet": "COMPLET — toutes les places sont réservées, le chantier n'accepte plus de bénévoles",
    "achevee": "CAMPAGNE ACHEVÉE — la campagne de fouille est terminée",
    "annulee": "CAMPAGNE ANNULÉE — la campagne de fouille n'aura pas lieu",
}


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
    commune: str = ""
    departement: str = ""
    periode: str = ""
    statut: str = ""
    dates: str = ""
    places: str = ""
    vss: str = ""
    lat: float | None = None
    lon: float | None = None


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Découpe un texte en morceaux avec chevauchement."""
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
    if cleaned.lower().startswith("responsable"):
        return False
    return True


def _looks_like_commune(line: str) -> bool:
    """Vérifie si la ligne ressemble à « Commune (Département) »."""
    cleaned = line.strip()
    if not COMMUNE_LINE.match(cleaned):
        return False
    # Évite « Responsable : X (labo) » / « Contact : … »
    lower = cleaned.lower()
    if lower.startswith("responsable") or lower.startswith("contact"):
        return False
    return True


def _window_has_chantier_markers(lines: list[str], start_index: int) -> bool:
    """Un vrai chantier contient Visiter/Fouiller dans les lignes qui suivent."""
    window = "\n".join(lines[start_index : start_index + 20])
    return (
        "Visiter le chantier" in window
        or "Visiter le château" in window
        or "\nFouiller\n" in f"\n{window}\n"
        or window.lstrip().startswith("Fouiller")
    )


def _find_chantier_spans(text: str) -> list[tuple[int, int, str, str]]:
    """
    Trouve les spans (start, end, titre, commune) des fiches chantier.

    Un chantier = titre + ligne commune (Dept) + marqueurs Visiter/Fouiller bientôt après.
    """
    lines = text.splitlines(keepends=True)
    # Positions absolues de chaque ligne
    offsets: list[int] = []
    pos = 0
    stripped_lines: list[str] = []
    for line in lines:
        offsets.append(pos)
        stripped_lines.append(line.rstrip("\n"))
        pos += len(line)

    starts: list[tuple[int, str, str]] = []  # (line_index, title, commune)
    for index in range(len(stripped_lines) - 1):
        title = stripped_lines[index].strip()
        commune = stripped_lines[index + 1].strip()
        if not _is_valid_chantier_title(title):
            continue
        if _normalize_region(title):
            continue
        if not _looks_like_commune(commune):
            continue
        if not _window_has_chantier_markers(stripped_lines, index):
            continue
        starts.append((index, title, commune))

    spans: list[tuple[int, int, str, str]] = []
    for i, (line_index, title, commune) in enumerate(starts):
        start_pos = offsets[line_index]
        if i + 1 < len(starts):
            end_pos = offsets[starts[i + 1][0]]
        else:
            end_pos = len(text)
        spans.append((start_pos, end_pos, title, commune))
    return spans


def _detect_statut(block: str) -> str:
    """Statut de la campagne : ouvert / complet / achevee / annulee."""
    upper = block.upper()
    if "CAMPAGNE ANNULÉE" in upper or "CAMPAGNE ANNULEE" in upper:
        return "annulee"
    if "CAMPAGNE ACHEVÉE" in upper or "CAMPAGNE ACHEVEE" in upper:
        return "achevee"
    if re.search(r"(?m)^COMPLET\s*$", block):
        return "complet"
    return "ouvert"


def _normalize_vss(raw: str) -> str:
    """Ramène la réponse VSS à « oui » / « non » / « en attente » si possible."""
    lowered = raw.lower().strip()
    if lowered.startswith("oui"):
        return "oui"
    if lowered.startswith("non"):
        return "non"
    if lowered.startswith("en attente"):
        return "en attente"
    return raw.strip()[:80]


def extract_fiche_metadata(block: str, commune_line: str) -> dict:
    """
    Extrait les métadonnées structurées d'une fiche chantier.

    Retourne : commune, departement, periode, statut, dates, places, vss.
    """
    # Le PDF coupe les phrases en pleine ligne → on aplatit pour les regex.
    flat = re.sub(r"\s+", " ", block)

    commune = commune_line.strip()
    departement = ""
    match = re.match(r"^(.+?)\s*\(([^)]+)\)$", commune)
    if match:
        commune = match.group(1).strip()
        departement = match.group(2).strip()

    periode_match = re.search(r"Période\s*:\s*([^.]+)", flat)
    dates_match = re.search(r"Quand\s*\?\s*([^.]+)", flat)
    places_match = re.search(r"Nombre de places\s*:\s*([^.]+)", flat)
    vss_match = re.search(
        r"violences sexistes et sexuelles sur le\s*chantier\s*:\s*([^;.]+)", flat
    )

    return {
        "commune": commune,
        "departement": departement,
        "periode": periode_match.group(1).strip() if periode_match else "",
        "statut": _detect_statut(block),
        "dates": dates_match.group(1).strip() if dates_match else "",
        "places": places_match.group(1).strip() if places_match else "",
        "vss": _normalize_vss(vss_match.group(1)) if vss_match else "",
    }


def build_fiche_header(region: str, site_name: str, metadata: dict) -> str:
    """
    En-tête textuel normalisé, préfixé au texte vectorisé.

    Rend explicites la géographie et le statut pour les embeddings et le LLM.
    """
    lines = [f"Chantier archéologique : {site_name}"]
    if region:
        lines.append(f"Région : {region}")
    if metadata.get("commune"):
        lines.append(f"Commune : {metadata['commune']}")
    if metadata.get("departement"):
        lines.append(f"Département : {metadata['departement']}")
    if metadata.get("periode"):
        lines.append(f"Période archéologique : {metadata['periode']}")
    if metadata.get("dates"):
        lines.append(f"Dates de la campagne : {metadata['dates']}")
    lines.append(f"Statut de la campagne : {STATUT_PHRASES[metadata['statut']]}.")
    if metadata.get("vss"):
        lines.append(f"Dispositif de prévention des violences sexistes et sexuelles (VSS) : {metadata['vss']}.")
    return "\n".join(lines)


def split_into_chantiers(pages: list[PageText]) -> list[dict]:
    """Découpe le PDF en fiches chantier (1 chantier = 1 chunk)."""
    chantiers: list[dict] = []
    current_region = ""

    for page in pages:
        text = page.text
        region_before_page = current_region

        region_marks: list[tuple[int, str]] = [
            (m.start(), region)
            for m in re.finditer(r"(?m)^(.+)$", text)
            if (region := _normalize_region(m.group(1)))
        ]
        if region_marks:
            current_region = region_marks[-1][1]

        def region_at(pos: int) -> str:
            active = region_before_page
            for mark_pos, region in region_marks:
                if mark_pos <= pos:
                    active = region
                else:
                    break
            return active

        spans = _find_chantier_spans(text)
        if not spans:
            stripped = text.strip()
            if stripped and len(stripped) > 80 and not any(
                marker in stripped for marker in ("Visiter le chantier", "\nFouiller\n")
            ):
                # Page d'intro / hors liste
                chantiers.append(
                    {
                        "text": stripped,
                        "page_number": page.page_number,
                        "region": region_before_page,
                        "site_name": "",
                    }
                )
            continue

        for start, end, title, commune in spans:
            block = text[start:end].strip()
            if len(block) < 40:
                continue
            region = region_at(start)
            # Le PDF marque les nouveautés par un préfixe « nouveau » collé au titre
            site_name = re.sub(r"(?i)^nouveau\s+", "", title).strip()
            metadata = extract_fiche_metadata(block, commune)
            header = build_fiche_header(region, site_name, metadata)
            chantiers.append(
                {
                    "text": f"{header}\n---\n{block}",
                    "page_number": page.page_number,
                    "region": region,
                    "site_name": site_name,
                    **metadata,
                }
            )

    return chantiers


def build_chunks(
    pages: list[PageText],
    source: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    """Transforme les pages en chunks indexables (1 chantier = 1 chunk)."""
    chantiers = split_into_chantiers(pages)
    result: list[TextChunk] = []
    chunk_index = 0

    for chantier in chantiers:
        pieces = chunk_text(chantier["text"], chunk_size, chunk_overlap) or [chantier["text"]]
        for piece_index, piece in enumerate(pieces):
            site = chantier.get("site_name", "")
            region = chantier.get("region", "")
            seed = f"{source}:{chantier['page_number']}:{site}:{piece_index}:{piece[:80]}"
            result.append(
                TextChunk(
                    chunk_id=str(uuid5(NAMESPACE_URL, seed)),
                    text=piece,
                    page_number=chantier["page_number"],
                    chunk_index=chunk_index,
                    source=source,
                    region=region,
                    site_name=site,
                    commune=chantier.get("commune", ""),
                    departement=chantier.get("departement", ""),
                    periode=chantier.get("periode", ""),
                    statut=chantier.get("statut", ""),
                    dates=chantier.get("dates", ""),
                    places=chantier.get("places", ""),
                    vss=chantier.get("vss", ""),
                    lat=chantier.get("lat"),
                    lon=chantier.get("lon"),
                )
            )
            chunk_index += 1

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
