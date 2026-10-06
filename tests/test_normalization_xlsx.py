from pathlib import Path

from app.normalization.models import NormalizedElementType
from app.normalization.xlsx import XLSXNormalizer
from app.parsers.xlsx import XLSXParser


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_xlsx_normalizer_creates_tables():
    with (FIXTURES_DIR / "sample.xlsx").open("rb") as file:
        extracted = XLSXParser().parse(file)

    normalized = XLSXNormalizer().normalize(extracted)

    tables = [
        element
        for element in normalized.elements
        if element.element_type == "table"
    ]

    key_value_blocks = [
        element
        for element in normalized.elements
        if element.element_type == "key_value"
    ]

    assert len(tables) == 3
    assert len(key_value_blocks) == 2

    admissions_table = tables[0]

    assert admissions_table.metadata["sheet"] == "Admissions"

    assert admissions_table.content["headers"] == [
        "Program",
        "Deadline",
        "Fee",
        "Seats",
    ]

    assert admissions_table.content["rows"] == [
        ["BBA", "January 15", 500, 40],
        ["BCA", "February 1", 600, 35],
        ["MBA", "March 15", 800, 25],
    ]

    contacts = key_value_blocks[0]

    assert contacts.content["pairs"] == [
        {
            "key": "Email",
            "value": "admissions@example.com",
        },
        {
            "key": "Phone",
            "value": "+977-123456789",
        },
    ]

    international_contact = key_value_blocks[1]

    assert international_contact.content["pairs"] == [
        {
            "key": "Email",
            "value": "international@example.com",
        },
    ]

    assert international_contact.metadata["sheet"] == "Contacts"
    assert international_contact.metadata["start_row"] == 12
    assert international_contact.metadata["start_column"] == 5


def test_xlsx_normalizer_preserves_document_order():
    with (FIXTURES_DIR / "sample.xlsx").open("rb") as file:
        extracted = XLSXParser().parse(file)

    normalized = XLSXNormalizer().normalize(extracted)

    structure = [
        (
            element.metadata["sheet"],
            element.metadata.get(
                "start_row",
                element.metadata.get("row"),
            ),
            element.metadata.get(
                "start_column",
                element.metadata.get("column"),
            ),
            element.element_type,
            element.text,
        )
        for element in normalized.elements
    ]

    assert structure == [
        (
            "Admissions",
            1,
            1,
            "heading",
            "University Admissions 2027",
        ),
        (
            "Admissions",
            4,
            1,
            "table",
            "Program | Deadline | Fee | Seats\n"
            "BBA | January 15 | 500 | 40\n"
            "BCA | February 1 | 600 | 35\n"
            "MBA | March 15 | 800 | 25",
        ),
        (
            "Admissions",
            4,
            6,
            "heading",
            "International Programs",
        ),
        (
            "Admissions",
            6,
            6,
            "table",
            "Program | Country | Deadline | Fee\n"
            "BBA | Nepal | January 20 | 700\n"
            "BCA | India | February 10 | 900",
        ),
        (
            "Admissions",
            12,
            2,
            "paragraph",
            "Applications must be submitted before the deadline.",
        ),
        (
            "Contacts",
            2,
            2,
            "heading",
            "Admissions Office",
        ),
        (
            "Contacts",
            5,
            2,
            "key_value",
            "Email: admissions@example.com\n"
            "Phone: +977-123456789",
        ),
        (
            "Contacts",
            10,
            2,
            "heading",
            "International Office",
        ),
        (
            "Contacts",
            12,
            5,
            "key_value",
            "Email: international@example.com",
        ),
        (
            "Fees",
            1,
            1,
            "heading",
            "Program Fees",
        ),
        (
            "Fees",
            4,
            1,
            "table",
            "Program | Tuition | Registration\n"
            "BBA | 500 | 50\n"
            "BCA | 600 | 50\n"
            "MBA | 800 | 75",
        ),
    ]


def test_xlsx_normalizer_distinguishes_key_value_from_two_column_table():
    parser = XLSXParser()
    normalizer = XLSXNormalizer()

    with (FIXTURES_DIR / "sample.xlsx").open("rb") as file:
        extracted = parser.parse(file)

    normalized = normalizer.normalize(extracted)

    admissions = [
        element
        for element in normalized.elements
        if element.metadata.get("sheet") == "Admissions"
    ]

    contacts = [
        element
        for element in normalized.elements
        if element.metadata.get("sheet") == "Contacts"
    ]

    admissions_tables = [
        element
        for element in admissions
        if element.element_type == NormalizedElementType.TABLE
    ]

    contact_key_values = [
        element
        for element in contacts
        if element.element_type == NormalizedElementType.KEY_VALUE
    ]

    assert len(admissions_tables) == 2
    assert len(contact_key_values) == 2
