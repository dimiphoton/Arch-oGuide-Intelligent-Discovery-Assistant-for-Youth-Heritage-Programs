"""Tests du module géographique."""

from unittest.mock import patch

from rag.filters import MetadataFilter, build_metadata_filter
from rag.geo import (
    MapSite,
    detect_commune,
    detect_departement,
    detect_nearby_query,
    geocache_key,
    haversine_km,
    is_map_query,
    normalize_geo_label,
    records_to_map_sites,
)


def test_haversine_paris_lyon() -> None:
    # Paris ↔ Lyon ≈ 390 km
    distance = haversine_km(48.8566, 2.3522, 45.7640, 4.8357)
    assert 380 < distance < 410


def test_detect_nearby_query() -> None:
    assert detect_nearby_query("Chantiers près de Lyon") == ("Lyon", 50.0)
    assert detect_nearby_query("30 km de Nantes") == ("Nantes", 30.0)
    assert detect_nearby_query("Liste en Bretagne") is None


def test_detect_commune_from_vocabulary() -> None:
    communes = ["Saint-Tugdual", "Elne", "Toulon-sur-Allier"]
    assert detect_commune("Chantiers à Elne", communes) == "Elne"
    assert detect_commune("Fouilles sur Toulon-sur-Allier", communes) == "Toulon-sur-Allier"


def test_detect_departement_from_vocabulary() -> None:
    departements = ["Morbihan", "Allier", "Pyrénées-Orientales"]
    assert detect_departement("Chantiers dans le Morbihan", departements) == "Morbihan"
    assert detect_departement("Sites en Dordogne", ["Dordogne"]) == "Dordogne"


def test_is_map_query() -> None:
    assert is_map_query("Montre-moi une carte des chantiers") is True
    assert is_map_query("Quels chantiers en Bretagne ?") is False


def test_metadata_filter_commune_accepts() -> None:
    filt = MetadataFilter(commune="Elne")
    assert filt.accepts({"commune": "Elne", "statut": "ouvert"}) is True
    assert filt.accepts({"commune": "Autre", "statut": "ouvert"}) is False


def test_metadata_filter_geo_radius() -> None:
    # Centre sur Paris, rayon 50 km — Lyon doit être exclu
    filt = MetadataFilter(
        geo_center_lat=48.8566,
        geo_center_lon=2.3522,
        geo_radius_km=50.0,
    )
    assert filt.accepts({"lat": 48.86, "lon": 2.35}) is True
    assert filt.accepts({"lat": 45.76, "lon": 4.83}) is False
    assert filt.accepts({"lat": None, "lon": None}) is False


def test_build_metadata_filter_sans_vocab() -> None:
    filt = build_metadata_filter("Bonjour !", load_vocab=False)
    assert filt.is_empty() is True


@patch("rag.filters.geocode_place")
@patch("rag.filters._build_radius_chunk_ids")
def test_build_metadata_filter_rayon(mock_ids, mock_geocode) -> None:
    from rag.geo import GeoPoint

    mock_geocode.return_value = GeoPoint(lat=45.76, lon=4.83)
    mock_ids.return_value = ["abc-123"]
    filt = build_metadata_filter("Chantiers près de Lyon", load_vocab=False)
    assert filt.geo_center_lat == 45.76
    assert filt.geo_radius_km == 50.0
    assert filt.allowed_chunk_ids == ["abc-123"]


def test_records_to_map_sites_ignore_sans_coords() -> None:
    from rag.catalog import ChantierRecord

    records = [
        ChantierRecord(
            site_name="A",
            region="BRETAGNE",
            page_number=1,
            text="",
            source="x.pdf",
            chunk_id="1",
            commune="Rennes",
            lat=48.11,
            lon=-1.68,
        ),
        ChantierRecord(
            site_name="B",
            region="BRETAGNE",
            page_number=2,
            text="",
            source="x.pdf",
            chunk_id="2",
            commune="Sans GPS",
        ),
    ]
    sites = records_to_map_sites(records)
    assert len(sites) == 1
    assert isinstance(sites[0], MapSite)


def test_geocache_key_normalise() -> None:
    assert geocache_key("Elne", "Pyrénées-Orientales") == geocache_key("elne", "pyrenees-orientales")
    assert normalize_geo_label("  Saint-Tugdual ") == "saint-tugdual"


def test_commune_redirect_regismont() -> None:
    from rag.geo import _resolve_commune_redirect

    commune, dept = _resolve_commune_redirect("Regismont-le-Haut", "Hérault")
    assert commune == "Poilhes"
    assert dept == "Hérault"


def test_department_matches_context() -> None:
    from rag.geo import _department_matches

    assert _department_matches("41, Loir-et-Cher, Centre-Val de Loire", "Loir-et-Cher") is True
    assert _department_matches("24, Dordogne, Nouvelle-Aquitaine", "Loir-et-Cher") is False


@patch("rag.geo.requests.get")
def test_geocode_via_geo_api(mock_get) -> None:
    from rag.geo import _geocode_via_geo_api

    mock_get.return_value.json.return_value = [
        {
            "nom": "Lisle",
            "centre": {"coordinates": [1.1078, 47.8702]},
            "departement": {"code": "41"},
        }
    ]
    mock_get.return_value.raise_for_status = lambda: None
    point = _geocode_via_geo_api("Lisle", "Loir-et-Cher")
    assert point is not None
    assert abs(point.lat - 47.8702) < 0.001
