"""Enrichissement des chunks avec coordonnées GPS (API BAN + cache)."""

from __future__ import annotations

import logging

from ingest.chunk import TextChunk
from rag.geo import geocode_commune, geocache_key, get_coords_from_cache, load_geocache, save_geocache

logger = logging.getLogger(__name__)


def enrich_chunks_with_coords(
    chunks: list[TextChunk],
    *,
    retry_failed: bool = False,
) -> int:
    """
    Ajoute lat/lon à chaque chunk chantier via géocodage BAN.

    Retourne le nombre de communes géolocalisées avec succès.
    """
    cache = load_geocache()
    if retry_failed:
        from rag.geo import clear_failed_geocache_entries

        removed = clear_failed_geocache_entries(cache)
        if removed:
            logger.info("%s entrées en échec retirées du cache", removed)

    geocoded = 0
    seen: set[str] = set()

    for chunk in chunks:
        if not chunk.commune or not chunk.site_name:
            continue

        key = geocache_key(chunk.commune, chunk.departement)
        if key not in seen:
            seen.add(key)
            if geocode_commune(chunk.commune, chunk.departement, cache=cache, retry_failed=retry_failed):
                geocoded += 1

        entry = cache.get(key, {})
        lat, lon = entry.get("lat"), entry.get("lon")
        coords = get_coords_from_cache(chunk.commune, chunk.departement, cache)
        if coords:
            chunk.lat, chunk.lon = coords
        elif lat is not None and lon is not None:
            chunk.lat = float(lat)
            chunk.lon = float(lon)

    save_geocache(cache)
    logger.info("%s communes géolocalisées (%s communes uniques)", geocoded, len(seen))
    return geocoded
