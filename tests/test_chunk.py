"""Tests unitaires du chunking (dont découpage par chantier)."""

from ingest.chunk import build_chunks, chunk_text, split_into_chantiers
from ingest.extract import PageText


def test_chunk_text_respects_overlap() -> None:
    text = "mot " * 300
    chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)

    assert len(chunks) > 1
    assert all(len(c) <= 220 for c in chunks)


def test_chunk_text_empty() -> None:
    assert chunk_text("", chunk_size=100, chunk_overlap=10) == []
    assert chunk_text("   ", chunk_size=100, chunk_overlap=10) == []


def test_build_chunks_metadata() -> None:
    pages = [
        PageText(page_number=1, text="Chantier archéologique en Bretagne. " * 20),
        PageText(page_number=2, text="Visite de site en Normandie. " * 20),
    ]
    chunks = build_chunks(pages, source="test.pdf", chunk_size=100, chunk_overlap=20)

    assert len(chunks) >= 1
    assert all(chunk.source == "test.pdf" for chunk in chunks)
    assert all(chunk.chunk_id for chunk in chunks)


def test_split_into_chantiers_detects_sites() -> None:
    page = PageText(
        page_number=2,
        text=(
            "AUVERGNE-RHÔNE-ALPES\n"
            "Château de Saint-Germain\n"
            "Ambérieu-en-Bugey (Ain)\n"
            "Visiter le chantier de fouilles\n"
            "Visite libre.\n"
            "Fouiller\n"
            "Nombre de places : 8.\n"
            "Quand ? du 13 au 24 juillet.\n"
            "Les Bravets\n"
            "Creuzier-le-Vieux (Allier)\n"
            "Visiter le chantier de fouilles\n"
            "Visites guidées.\n"
            "Fouiller\n"
            "Nombre de places : 4.\n"
        ),
    )
    chantiers = split_into_chantiers([page])

    assert len(chantiers) == 2
    assert chantiers[0]["site_name"] == "Château de Saint-Germain"
    assert chantiers[0]["region"] == "AUVERGNE-RHÔNE-ALPES"
    assert chantiers[1]["site_name"] == "Les Bravets"


def test_split_handles_title_with_parentheses() -> None:
    page = PageText(
        page_number=5,
        text=(
            "(la liste des chantiers continue en page suivante)\n"
            "Les Renoncées (Confluence)\n"
            "Livron-sur-Drôme (Drôme)\n"
            "Visiter le chantier de fouilles\n"
            "Pas de visite.\n"
            "Fouiller\n"
            "Nombre de places : 5.\n"
        ),
    )
    chantiers = split_into_chantiers([page])
    assert len(chantiers) == 1
    assert chantiers[0]["site_name"] == "Les Renoncées (Confluence)"
