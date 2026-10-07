from io import BytesIO

from app.normalization.models import NormalizedElementType
from app.processing.factory import create_document_processor


def test_document_processor_processes_txt_end_to_end() -> None:
    processor = create_document_processor()

    file = BytesIO(
        b"""Introduction

DocPilot processes organizational documents.

This is another paragraph with useful information.
"""
    )

    result = processor.process(
        filename="example.txt",
        file=file,
    )

    assert result.extracted_document.source_type == "txt"

    assert result.normalized_document.source_type == "txt"

    assert len(result.normalized_document.elements) == 3

    assert all(
        element.element_type == NormalizedElementType.PARAGRAPH
        for element in result.normalized_document.elements
    )

    assert len(result.chunks) > 0

    assert all(
        chunk.element_type == NormalizedElementType.PARAGRAPH
        for chunk in result.chunks
    )

    assert result.chunks[0].text

    assert all(
        chunk.token_count > 0
        for chunk in result.chunks
    )


def test_document_processor_processes_xlsx_end_to_end() -> None:
    from io import BytesIO

    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Members"

    worksheet.append(["Name", "Role"])
    worksheet.append(["Alice", "Admin"])
    worksheet.append(["Bob", "Member"])

    file = BytesIO()
    workbook.save(file)
    file.seek(0)

    processor = create_document_processor()

    result = processor.process(
        filename="members.xlsx",
        file=file,
    )

    assert result.extracted_document.source_type == "xlsx"

    assert result.normalized_document.source_type == "xlsx"

    assert len(result.normalized_document.elements) >= 1

    assert any(
        element.element_type == NormalizedElementType.TABLE
        for element in result.normalized_document.elements
    )

    table_chunks = [
        chunk
        for chunk in result.chunks
        if chunk.element_type == NormalizedElementType.TABLE
    ]

    assert table_chunks

    assert any("Alice" in chunk.text for chunk in table_chunks)

    assert all(
        chunk.token_count > 0
        for chunk in result.chunks
    )
