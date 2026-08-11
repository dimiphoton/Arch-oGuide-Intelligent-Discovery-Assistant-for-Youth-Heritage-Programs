"""Géocodage (BAN), cache, détection géographique et calculs de distance."""

from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import requests

from rag.config import PROJECT_ROOT, Settings, get_settings

logger = logging.getLogger(__name__)

GEOCACHE_PATH = PROJECT_ROOT / "data" / "geocache.json"
BAN_SEARCH_URL = "https://api-adresse.data.gouv.fr/search/"
GEO_API_COMMUNES_URL = "https://geo.api.gouv.fr/communes"
DEFAULT_RADIUS_KM = 50.0

# PDF : commune erronée ou lieu-dit → vraie commune à géocoder
COMMUNE_REDIRECTS: dict[str, tuple[str, str]] = {
    "regismont-le-haut|herault": ("Poilhes", "Hérault"),
    "dolus-d'oleron et le grand-village-plage|charente-maritime": ("Dolus-d'Oléron", "Charente-Maritime"),
}

# Orthographe PDF sans accent → forme officielle
COMMUNE_SPELLING_FIXES: dict[str, str] = {
    "meailles": "Méailles",
    "aleria": "Aléria",
}

# Codes département pour désambiguïser (ex. Lisle en Loir-et-Cher vs Dordogne)
DEPARTEMENT_CODES: dict[str, str] = {
    "ain": "01",
    "aisne": "02",
    "allier": "03",
    "alpes-de-haute-provence": "04",
    "hautes-alpes": "05",
    "alpes-maritimes": "06",
    "ardeche": "07",
    "ardennes": "08",
    "ariege": "09",
    "aube": "10",
    "aude": "11",
    "aveyron": "12",
    "bouches-du-rhone": "13",
    "calvados": "14",
    "cantal": "15",
    "charente": "16",
    "charente-maritime": "17",
    "cher": "18",
    "correze": "19",
    "corse-du-sud": "2A",
    "haute-corse": "2B",
    "cote-d'or": "21",
    "cotes-d'armor": "22",
    "creuse": "23",
    "dordogne": "24",
    "doubs": "25",
    "drome": "26",
    "eure": "27",
    "eure-et-loir": "28",
    "finistere": "29",
    "gard": "30",
    "haute-garonne": "31",
    "gers": "32",
    "gironde": "33",
    "herault": "34",
    "ille-et-vilaine": "35",
    "indre": "36",
    "indre-et-loire": "37",
    "isere": "38",
    "jura": "39",
    "landes": "40",
    "loir-et-cher": "41",
    "loire": "42",
    "haute-loire": "43",
    "loire-atlantique": "44",
    "loiret": "45",
    "lot": "46",
    "lot-et-garonne": "47",
    "lozere": "48",
    "maine-et-loire": "49",
    "manche": "50",
    "marne": "51",
    "haute-marne": "52",
    "mayenne": "53",
    "meurthe-et-moselle": "54",
    "meuse": "55",
    "morbihan": "56",
    "moselle": "57",
    "nievre": "58",
    "nord": "59",
    "oise": "60",
    "orne": "61",
    "pas-de-calais": "62",
    "puy-de-dome": "63",
    "pyrenees-atlantiques": "64",
    "hautes-pyrenees": "65",
    "pyrenees-orientales": "66",
    "bas-rhin": "67",
    "haut-rhin": "68",
    "rhone": "69",
    "haute-saone": "70",
    "saone-et-loire": "71",
    "sarthe": "72",
    "savoie": "73",
    "haute-savoie": "74",
    "paris": "75",
    "seine-maritime": "76",
    "seine-et-marne": "77",
    "yvelines": "78",
    "deux-sevres": "79",
    "somme": "80",
    "tarn": "81",
    "tarn-et-garonne": "82",
    "var": "83",
    "vaucluse": "84",
    "vendee": "85",
    "vienne": "86",
    "haute-vienne": "87",
    "vosges": "88",
    "yonne": "89",
    "territoire-de-belfort": "90",
    "essonne": "91",
    "hauts-de-seine": "92",
    "seine-saint-denis": "93",
    "val-de-marne": "94",
    "val-d'oise": "95",
}

# Villes fréquentes dans les questions (géocodage « près de … »)
PLACE_ALIASES: dict[str, str] = {
    "lyon": "Lyon",
    "marseille": "Marseille",
    "toulouse": "Toulouse",
    "bordeaux": "Bordeaux",
    "nantes": "Nantes",
    "lille": "Lille",
    "strasbourg": "Strasbourg",
    "rennes": "Rennes",
    "montpellier": "Montpellier",
    "nice": "Nice",
}

# Détection d'une demande de carte dans le chat
MAP_QUERY_PATTERN = re.compile(
    r"\bcarte\b|\bsur une carte\b|\bvisualis\w*\b.*\bcarte\b|\bgeolocalis\w*\b|\blocalis\w*\b.*\bcarte\b",
    re.IGNORECASE,
)

# « près de Lyon », « autour de Marseille », « à 30 km de Toulouse »
NEAR_PLACE_PATTERN = re.compile(
    r"(?:pr[eè]s d['e]?|autour d['e]?|aux? alentours d['e]?)\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-']{1,40})",
    re.IGNORECASE,
)
RADIUS_KM_PATTERN = re.compile(
    r"(?:rayon|dans un rayon|radius)\s*(?:de\s*)?(\d{1,3})\s*km|"
    r"(\d{1,3})\s*km\s*(?:de|autour|autour de|autour d['e])",
    re.IGNORECASE,
)
KM_FROM_PLACE_PATTERN = re.compile(
    r"(\d{1,3})\s*km\s*(?:de|d['e])\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-']{1,40})",
    re.IGNORECASE,
)

# « à Carcassonne », « sur Elne », « commune de X »
COMMUNE_QUESTION_PATTERN = re.compile(
    r"(?:\b(?:à|a|sur|dans la commune de|commune de)\s+)"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-']{2,40})",
    re.IGNORECASE,
)

# « dans le Morbihan », « en Dordogne »
DEPARTEMENT_QUESTION_PATTERN = re.compile(
    r"(?:dans l['e]|dans le|dans la|en)\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s\-']{2,40})",
    re.IGNORECASE,
)


@dataclass
class GeoPoint:
    """Coordonnées géographiques."""

    lat: float
    lon: float


@dataclass
class MapSite:
    """Site affichable sur une carte."""

    site_name: str
    commune: str
    departement: str
    region: str
    lat: float
    lon: float
    statut: str = ""
    page_number: int = 0
    chunk_id: str = ""


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def normalize_geo_label(value: str) -> str:
    """Normalise un libellé géographique pour comparaison."""
    cleaned = value.strip().lower()
    # Apostrophes typographiques du PDF → apostrophe simple
    cleaned = cleaned.replace("\u2019", "'").replace("\u2018", "'").replace("\u02bc", "'")
    cleaned = _strip_accents(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.rstrip("?.!,;")


def _departement_code(departement: str) -> str | None:
    if not departement:
        return None
    return DEPARTEMENT_CODES.get(normalize_geo_label(departement))


def _normalize_commune_for_search(commune: str) -> str:
    """Nettoie le nom de commune extrait du PDF."""
    cleaned = commune.strip()
    cleaned = cleaned.replace("\u2019", "'").replace("\u2018", "'").replace("\u02bc", "'")
    # « Dolus-d'Oléron et Le Grand-Village-Plage » → première commune
    if " et " in cleaned.lower():
        cleaned = re.split(r"\s+et\s+", cleaned, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    fixed = COMMUNE_SPELLING_FIXES.get(normalize_geo_label(cleaned))
    return fixed or cleaned


def _department_matches(context: str, departement: str) -> bool:
    """Vérifie que le résultat BAN est dans le bon département."""
    if not departement:
        return True
    context_norm = normalize_geo_label(context)
    dept_norm = normalize_geo_label(departement)
    code = _departement_code(departement)
    if dept_norm in context_norm:
        return True
    if code and re.search(rf"(^|[,\s]){re.escape(code.lower())}([,\s]|$)", context_norm):
        return True
    return False


def _commune_name_matches(result_name: str, searched_name: str) -> bool:
    result_norm = normalize_geo_label(result_name)
    search_norm = normalize_geo_label(searched_name)
    return result_norm == search_norm or search_norm in result_norm or result_norm in search_norm


def _store_cache(
    geo_cache: dict[str, dict[str, float | None]],
    key: str,
    lat: float | None,
    lon: float | None,
    *,
    persist: bool,
) -> None:
    geo_cache[key] = {"lat": lat, "lon": lon}
    if persist:
        save_geocache(geo_cache)


def _geocode_via_geo_api(
    commune: str,
    departement: str = "",
    *,
    timeout: float = 8.0,
) -> GeoPoint | None:
    """Géocodage via geo.api.gouv.fr (fiable pour désambiguïser par département)."""
    params: dict[str, str | int] = {
        "nom": commune,
        "fields": "nom,centre,departement",
        "limit": 15,
    }
    code = _departement_code(departement)
    if code:
        params["codeDepartement"] = code

    try:
        response = requests.get(GEO_API_COMMUNES_URL, params=params, timeout=timeout)
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.debug("geo.api.gouv.fr échoué pour %r : %s", commune, exc)
        return None

    commune_norm = normalize_geo_label(commune)
    exact = [item for item in results if normalize_geo_label(item.get("nom", "")) == commune_norm]
    candidates = exact or results

    for item in candidates:
        centre = item.get("centre") or {}
        coords = centre.get("coordinates")
        if not coords or len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        if exact:
            return GeoPoint(lat=lat, lon=lon)
        if code and str(item.get("departement", {}).get("code", "")).upper() == code.upper():
            return GeoPoint(lat=lat, lon=lon)

    if len(candidates) == 1 and candidates[0].get("centre"):
        lon, lat = candidates[0]["centre"]["coordinates"]
        return GeoPoint(lat=float(lat), lon=float(lon))
    return None


def _ban_search(
    query: str,
    *,
    municipality_only: bool = True,
    limit: int = 8,
    timeout: float = 8.0,
) -> list[dict]:
    params: dict[str, str | int] = {"q": query, "limit": limit}
    if municipality_only:
        params["type"] = "municipality"
    try:
        response = requests.get(BAN_SEARCH_URL, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json().get("features", [])
    except (requests.RequestException, ValueError):
        return []


def _pick_ban_feature(
    features: list[dict],
    commune: str,
    departement: str = "",
) -> dict | None:
    """Choisit le meilleur résultat BAN en vérifiant commune + département."""
    if not features:
        return None

    scored: list[tuple[int, dict]] = []
    for feature in features:
        props = feature.get("properties") or {}
        city = str(props.get("city") or props.get("name") or "")
        context = str(props.get("context") or "")
        rank = 0
        if _commune_name_matches(city, commune):
            rank += 2
        if _department_matches(context, departement):
            rank += 3
        if rank > 0:
            scored.append((rank, feature))

    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    # Secours : premier résultat si un seul retour municipalité
    if len(features) == 1:
        return features[0]
    return None


def _geocode_via_ban(
    commune: str,
    departement: str = "",
    *,
    timeout: float = 8.0,
) -> GeoPoint | None:
    """Géocodage BAN avec plusieurs formulations de requête."""
    queries = [commune]
    if departement:
        code = _departement_code(departement)
        if code:
            queries.append(f"{commune} {code}")

    seen: set[str] = set()
    for query in queries:
        if query in seen:
            continue
        seen.add(query)
        features = _ban_search(query, municipality_only=True, timeout=timeout)
        feature = _pick_ban_feature(features, commune, departement)
        if feature:
            coords = feature["geometry"]["coordinates"]
            return GeoPoint(lat=float(coords[1]), lon=float(coords[0]))
    return None


def _resolve_commune_redirect(commune: str, departement: str) -> tuple[str, str]:
    """Applique une redirection commune/lieu-dit si connue."""
    key = geocache_key(commune, departement)
    redirect = COMMUNE_REDIRECTS.get(key)
    if redirect:
        return redirect
    return _normalize_commune_for_search(commune), departement


def geocache_key(commune: str, departement: str = "") -> str:
    """Clé de cache pour une commune + département."""
    return f"{normalize_geo_label(commune)}|{normalize_geo_label(departement)}"


def _cache_key(commune: str, departement: str = "") -> str:
    return geocache_key(commune, departement)


def load_geocache() -> dict[str, dict[str, float | None]]:
    """Charge le cache de géocodage local."""
    if not GEOCACHE_PATH.exists():
        return {}
    try:
        return json.loads(GEOCACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Cache géocodage illisible, recréation.")
        return {}


def save_geocache(cache: dict[str, dict[str, float | None]]) -> None:
    """Persiste le cache de géocodage."""
    GEOCACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOCACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance en km entre deux points GPS (formule haversine)."""
    radius_earth_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_earth_km * math.asin(math.sqrt(a))


def get_coords_from_cache(
    commune: str,
    departement: str,
    cache: dict[str, dict[str, float | None]],
) -> tuple[float, float] | None:
    """Lit lat/lon dans le cache (gère redirections et noms composés du PDF)."""
    search_commune, search_dept = _resolve_commune_redirect(commune, departement)
    candidate_keys = [
        geocache_key(commune, departement),
        geocache_key(search_commune, search_dept),
    ]
    for key in candidate_keys:
        entry = cache.get(key, {})
        lat, lon = entry.get("lat"), entry.get("lon")
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    return None


def geocode_place(
    place: str,
    departement: str = "",
    *,
    cache: dict[str, dict[str, float | None]] | None = None,
    timeout: float = 8.0,
    retry_failed: bool = False,
) -> GeoPoint | None:
    """
    Géocode une commune ou ville (geo.api.gouv.fr puis BAN, avec cache).

    retry_failed=True ignore les entrées cacheées en échec (lat=null).
    """
    place = place.strip()
    if not place:
        return None

    alias = PLACE_ALIASES.get(normalize_geo_label(place))
    if alias:
        place = alias

    original_key = geocache_key(place, departement)
    search_commune, search_dept = _resolve_commune_redirect(place, departement)
    key = geocache_key(search_commune, search_dept)

    geo_cache = cache if cache is not None else load_geocache()

    if key in geo_cache and not (retry_failed and geo_cache[key].get("lat") is None):
        entry = geo_cache[key]
        lat, lon = entry.get("lat"), entry.get("lon")
        if lat is not None and lon is not None:
            return GeoPoint(float(lat), float(lon))
        if not retry_failed:
            return None

    persist = cache is None
    point = _geocode_via_geo_api(search_commune, search_dept, timeout=timeout)
    if point is None:
        point = _geocode_via_ban(search_commune, search_dept, timeout=timeout)

    if point is None:
        _store_cache(geo_cache, key, None, None, persist=persist)
        if key != original_key:
            _store_cache(geo_cache, original_key, None, None, persist=persist)
        return None

    _store_cache(geo_cache, key, point.lat, point.lon, persist=persist)
    if key != original_key:
        _store_cache(geo_cache, original_key, point.lat, point.lon, persist=persist)
    return point


def clear_failed_geocache_entries(cache: dict[str, dict[str, float | None]] | None = None) -> int:
    """Supprime les entrées en échec du cache pour permettre un nouveau passage."""
    geo_cache = cache if cache is not None else load_geocache()
    failed_keys = [key for key, value in geo_cache.items() if value.get("lat") is None]
    for key in failed_keys:
        del geo_cache[key]
    if cache is None and failed_keys:
        save_geocache(geo_cache)
    return len(failed_keys)


def geocode_commune(
    commune: str,
    departement: str = "",
    *,
    cache: dict[str, dict[str, float | None]] | None = None,
    retry_failed: bool = False,
) -> GeoPoint | None:
    """Géocode une commune du corpus (avec département si disponible)."""
    return geocode_place(
        commune,
        departement=departement,
        cache=cache,
        retry_failed=retry_failed,
    )


def is_map_query(question: str) -> bool:
    """True si l'utilisateur demande une visualisation cartographique."""
    return bool(MAP_QUERY_PATTERN.search(question))


def detect_nearby_query(question: str) -> tuple[str, float] | None:
    """
    Détecte une recherche par proximité (« près de Lyon », « 30 km de Nantes »).

    Retourne (nom_du_lieu, rayon_km) ou None.
    """
    lowered = question.lower()
    radius_km = DEFAULT_RADIUS_KM

    km_match = RADIUS_KM_PATTERN.search(question)
    if km_match:
        radius_km = float(km_match.group(1) or km_match.group(2))

    km_from = KM_FROM_PLACE_PATTERN.search(question)
    if km_from:
        radius_km = float(km_from.group(1))
        place = km_from.group(2).strip(" ?!.,")
        return place, radius_km

    near_match = NEAR_PLACE_PATTERN.search(question)
    if near_match:
        place = near_match.group(1).strip(" ?!.,")
        return place, radius_km

    # « chantiers Lyon » / « autour Marseille » sans préposition explicite
    if any(word in lowered for word in ("près", "pres", "autour", "alentours", "proximité", "proche")):
        for alias, canonical in PLACE_ALIASES.items():
            if alias in lowered:
                return canonical, radius_km

    return None


def _match_vocabulary(candidate: str, vocabulary: list[str]) -> str | None:
    """Retourne l'entrée du vocabulaire qui correspond au candidat extrait."""
    candidate_norm = normalize_geo_label(candidate)
    if not candidate_norm:
        return None

    for item in sorted(vocabulary, key=len, reverse=True):
        item_norm = normalize_geo_label(item)
        if candidate_norm == item_norm:
            return item
        # Le candidat peut contenir des mots en trop (« Bretagne cet été »)
        if item_norm in candidate_norm:
            return item
    return None


def detect_commune(question: str, communes: list[str]) -> str | None:
    """Détecte une commune mentionnée dans la question."""
    if not communes:
        return None

    for match in COMMUNE_QUESTION_PATTERN.finditer(question):
        found = _match_vocabulary(match.group(1), communes)
        if found:
            return found

    # Recherche directe du nom de commune dans la question
    lowered = normalize_geo_label(question)
    for commune in sorted(communes, key=len, reverse=True):
        if normalize_geo_label(commune) in lowered:
            return commune
    return None


def detect_departement(question: str, departements: list[str]) -> str | None:
    """Détecte un département mentionné dans la question."""
    if not departements:
        return None

    for match in DEPARTEMENT_QUESTION_PATTERN.finditer(question):
        found = _match_vocabulary(match.group(1), departements)
        if found:
            return found

    lowered = normalize_geo_label(question)
    for dept in sorted(departements, key=len, reverse=True):
        if normalize_geo_label(dept) in lowered:
            return dept
    return None


def load_geo_vocabulary(settings: Settings | None = None) -> tuple[list[str], list[str]]:
    """
    Charge les communes et départements connus depuis le catalogue Qdrant.

    Évite une dépendance circulaire en important catalog ici.
    """
    from rag.catalog import load_chantier_catalog

    cfg = settings or get_settings()
    try:
        records = load_chantier_catalog(settings=cfg)
    except ValueError:
        return [], []

    communes = sorted({r.commune for r in records if r.commune})
    departements = sorted({r.departement for r in records if r.departement})
    return communes, departements


_vocab_cache: tuple[list[str], list[str]] | None = None


def get_geo_vocabulary(settings: Settings | None = None) -> tuple[list[str], list[str]]:
    """Vocabulaire géographique mis en cache pour la session."""
    global _vocab_cache
    if _vocab_cache is None:
        _vocab_cache = load_geo_vocabulary(settings)
    return _vocab_cache


def reset_geo_vocabulary_cache() -> None:
    """Réinitialise le cache vocabulaire (tests)."""
    global _vocab_cache
    _vocab_cache = None


def records_to_map_sites(records: list) -> list[MapSite]:
    """Convertit des ChantierRecord en points cartographiques."""
    sites: list[MapSite] = []
    for record in records:
        if record.lat is None or record.lon is None:
            continue
        sites.append(
            MapSite(
                site_name=record.site_name,
                commune=record.commune,
                departement=record.departement,
                region=record.region,
                lat=record.lat,
                lon=record.lon,
                statut=record.statut,
                page_number=record.page_number,
                chunk_id=record.chunk_id,
            )
        )
    return sites
