from pathlib import Path

from app.domain.chunking import ParsedDocument, ParsedPage, build_chunks


def fixture_document() -> ParsedDocument:
    content = Path("tests/fixtures/SOP_Operational.md").read_text(encoding="utf-8")
    return ParsedDocument(
        filename="SOP_Operational.md",
        content_type="text/markdown",
        pages=[ParsedPage(page_number=None, text=content)],
        detected_version="1.0.0",
    )


def test_markdown_table_is_preserved_with_sensitive_symbols() -> None:
    chunks = build_chunks(
        fixture_document(),
        document_id="document-1",
        document_checksum="a" * 64,
    )

    table = next(chunk for chunk in chunks if chunk.type == "table")
    assert "< 80%" in table.content
    assert "80% - 100%" in table.content
    assert "> 100%" in table.content
    assert "Rp 50.000" in table.content
    assert table.heading_path[-1] == "Skema Insentif Finansial Harian"
    assert "Skema Insentif Finansial Harian" in table.embedding_text


def test_chunk_ids_are_deterministic() -> None:
    first = build_chunks(fixture_document(), document_id="doc-a", document_checksum="b" * 64)
    second = build_chunks(fixture_document(), document_id="doc-b", document_checksum="b" * 64)

    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]


def test_long_table_repeats_header_without_cutting_rows() -> None:
    rows = "\n".join(f"| key-{index} | value-{index} |" for index in range(20))
    markdown = f"# Rules\n\n| Key | Value |\n|---|---|\n{rows}"
    document = ParsedDocument(
        filename="rules.md",
        content_type="text/markdown",
        pages=[ParsedPage(None, markdown)],
    )

    chunks = build_chunks(
        document,
        document_id="doc",
        document_checksum="c" * 64,
        maximum_tokens=30,
        overlap_tokens=5,
    )

    assert len(chunks) > 1
    assert all(chunk.content.startswith("| Key | Value |\n|---|---|") for chunk in chunks)
