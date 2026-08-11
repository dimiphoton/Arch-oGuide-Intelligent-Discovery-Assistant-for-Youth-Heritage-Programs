"""Tests du catalogue chantiers."""

from rag.catalog import (
    ChantierRecord,
    dedup_catalog,
    detect_region,
    format_catalog_answer,
    format_catalog_table,
    is_catalog_query,
    is_count_query,
    is_table_query,
)


def test_detect_region_bretagne() -> None:
    assert detect_region("Quels chantiers en Bretagne ?") == "BRETAGNE"
    assert detect_region("fouilles en PACA") == "PROVENCE-ALPES-CÔTE D'AZUR"


def test_is_catalog_query_comptage() -> None:
    assert is_catalog_query("Combien de chantiers dans le PDF ?") is True
    assert is_catalog_query("Combien y a-t-il de chantiers en France ?") is True
    assert is_catalog_query("Quel est le nombre total de chantiers ?") is True
    assert is_catalog_query("nb de chantiers ?") is True
    assert is_catalog_query("Il y a combien de chantiers au total ?") is True


def test_is_catalog_query_liste() -> None:
    assert is_catalog_query("Liste tous les chantiers") is True
    assert is_catalog_query("Donne-moi la liste des chantiers") is True
    assert is_catalog_query("Énumère tous les chantiers") is True
    assert is_catalog_query("Donne-moi l'ensemble des chantiers") is True
    assert is_catalog_query("Montre-moi tous les sites de fouilles") is True


def test_is_catalog_query_quels() -> None:
    assert is_catalog_query("Quels chantiers en Bretagne ?") is True
    assert is_catalog_query("Quels sont les chantiers en France ?") is True
    assert is_catalog_query("Quels sont les chantiers ?") is True
    assert is_catalog_query("Quelles fouilles en Occitanie ?") is True


def test_is_catalog_query_tableau() -> None:
    assert is_catalog_query("Fais un tableau de tous les chantiers") is True
    assert is_catalog_query("Peux-tu faire un tableau récapitulatif ?") is True
    assert is_catalog_query("Mettre sous forme de tableau les chantiers") is True
    assert is_catalog_query("Tableau des chantiers en Bretagne") is True
    assert is_catalog_query("Crée un table avec les sites") is True
    assert is_table_query("Peux-tu faire un tableau récapitulatif ?") is True
    assert is_table_query("Liste tous les chantiers") is False


def test_is_catalog_query_questions_filtrees() -> None:
    # Les questions avec critère (âge, période, contact…) restent en retrieval sémantique.
    assert is_catalog_query("Quels chantiers pour des scolaires ?") is False
    assert is_catalog_query("Quel est le contact du chantier Mandrin ?") is False
    assert is_catalog_query("Combien de chantiers acceptent des mineurs ?") is False
    assert is_catalog_query("Liste des chantiers pour les enfants") is False


def test_is_count_query() -> None:
    assert is_count_query("Combien de chantiers ?") is True
    assert is_count_query("Quel est le nombre de chantiers ?") is True
    assert is_count_query("Liste tous les chantiers") is False


def _record(site_name: str, page: int, region: str = "BRETAGNE") -> ChantierRecord:
    return ChantierRecord(
        site_name=site_name,
        region=region,
        page_number=page,
        text=f"fiche {site_name}",
        source="test.pdf",
        chunk_id=f"{site_name}-{page}",
    )


def test_dedup_catalog() -> None:
    records = [
        _record("Panner", 12),
        _record("Panner", 12),  # doublon (fiche multi-chunks ou ré-ingestion)
        _record("Le Château", 27),
        _record("Le Château", 35),  # même nom mais autre page → conservé
    ]
    unique = dedup_catalog(records)
    assert len(unique) == 3


def test_format_catalog_answer_liste_tout() -> None:
    records = [
        _record("Panner", 12, "BRETAGNE"),
        _record("Palol", 42, "OCCITANIE"),
    ]
    answer = format_catalog_answer(records)
    assert "2 chantier(s)" in answer
    assert "Panner" in answer
    assert "Palol" in answer
    assert "**BRETAGNE**" in answer
    assert "**OCCITANIE**" in answer


def test_format_catalog_table_complet() -> None:
    records = [
        ChantierRecord(
            site_name="Panner",
            region="BRETAGNE",
            page_number=12,
            text="",
            source="test.pdf",
            chunk_id="1",
            commune="Saint-Tugdual",
            departement="Morbihan",
            statut="ouvert",
        ),
        ChantierRecord(
            site_name="Palol",
            region="OCCITANIE",
            page_number=42,
            text="",
            source="test.pdf",
            chunk_id="2",
            commune="Elne",
            departement="Pyrénées-Orientales",
            statut="complet",
        ),
    ]
    table = format_catalog_table(records)
    assert "2 chantier(s)" in table
    assert "| # | Site | Région |" in table
    assert "| 1 | Panner | BRETAGNE |" in table
    assert "| 2 | Palol | OCCITANIE |" in table
    assert table.count("| ") >= 2 + 2  # en-tête + 2 lignes de données
