"""Tests des filtres métadonnées appliqués en amont de la recherche."""

from rag.filters import build_metadata_filter


def test_filtre_disponibilite() -> None:
    f = build_metadata_filter("Où puis-je m'inscrire pour fouiller cet été ?")
    assert f.only_open is True

    f = build_metadata_filter("Y a-t-il encore des places disponibles ?")
    assert f.only_open is True

    f = build_metadata_filter("Quelle est la période du chantier des Malnaux ?")
    assert f.only_open is False


def test_filtre_region() -> None:
    f = build_metadata_filter("Je veux participer à une fouille en Bretagne")
    assert f.region == "BRETAGNE"
    assert f.only_open is True

    f = build_metadata_filter("Parle-moi du chantier Grotte Mandrin")
    assert f.region is None
    assert f.is_empty() is True


def test_accepts_applique_les_deux_criteres() -> None:
    f = build_metadata_filter("Comment participer à un chantier en Bretagne ?")
    assert f.accepts({"region": "BRETAGNE", "statut": "ouvert"}) is True
    assert f.accepts({"region": "BRETAGNE", "statut": "complet"}) is False
    assert f.accepts({"region": "OCCITANIE", "statut": "ouvert"}) is False


def test_to_qdrant_vide_si_aucune_contrainte() -> None:
    f = build_metadata_filter("Bonjour !")
    assert f.to_qdrant() is None
