"""Tests du catalogue chantiers."""

from rag.catalog import detect_region, is_catalog_query


def test_detect_region_bretagne() -> None:
    assert detect_region("Quels chantiers en Bretagne ?") == "BRETAGNE"
    assert detect_region("fouilles en PACA") == "PROVENCE-ALPES-CÔTE D'AZUR"


def test_is_catalog_query() -> None:
    assert is_catalog_query("Combien de chantiers dans le PDF ?") is True
    assert is_catalog_query("Liste tous les chantiers") is True
    assert is_catalog_query("Quels chantiers en Bretagne ?") is True
    assert is_catalog_query("Quels chantiers pour des scolaires ?") is False
    assert is_catalog_query("Quel est le contact du chantier Mandrin ?") is False
