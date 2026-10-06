from pathlib import Path

from app.parsers.models import ExtractedDocument
from app.parsers.xlsx import XLSXParser


FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "sample.xlsx"


def test_xlsx_parser_extracts_workbook():
    with FIXTURE_PATH.open("rb") as file:
        document = XLSXParser().parse(file)

    assert isinstance(document, ExtractedDocument)
    assert document.source_type == "xlsx"

    assert document.metadata["sheet_count"] == 3
    assert document.metadata["sheet_names"] == [
        "Admissions",
        "Contacts",
        "Fees",
    ]

    assert len(document.elements) == 3


def test_xlsx_parser_preserves_worksheets():
    with FIXTURE_PATH.open("rb") as file:
        document = XLSXParser().parse(file)

    admissions = document.elements[0]
    contacts = document.elements[1]
    fees = document.elements[2]

    assert admissions.element_type == "worksheet"
    assert admissions.text == "Admissions"

    assert contacts.element_type == "worksheet"
    assert contacts.text == "Contacts"

    assert fees.element_type == "worksheet"
    assert fees.text == "Fees"


def test_xlsx_parser_preserves_cell_coordinates_and_values():
    with FIXTURE_PATH.open("rb") as file:
        document = XLSXParser().parse(file)

    admissions = document.elements[0]
    cells = admissions.content["cells"]

    cells_by_coordinate = {
        cell["coordinate"]: cell
        for cell in cells
    }

    assert cells_by_coordinate["A1"]["value"] == "University Admissions 2027"

    assert cells_by_coordinate["A5"]["value"] == "BBA"
    assert cells_by_coordinate["B5"]["value"] == "January 15"
    assert cells_by_coordinate["C5"]["value"] == 500
    assert cells_by_coordinate["D5"]["value"] == 40

    assert cells_by_coordinate["F7"]["value"] == "BBA"
    assert cells_by_coordinate["G7"]["value"] == "Nepal"

    assert cells_by_coordinate["I8"]["value"] == 900


def test_xlsx_parser_preserves_sheet_metadata():
    with FIXTURE_PATH.open("rb") as file:
        document = XLSXParser().parse(file)

    admissions = document.elements[0]

    assert admissions.metadata["sheet"] == "Admissions"
    assert "A1:D1" in admissions.metadata["merged_ranges"]
    assert admissions.metadata["max_row"] >= 12
    assert admissions.metadata["max_column"] >= 9
