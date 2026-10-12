import re
from typing import BinaryIO

import pymupdf

from app.parsers.base import DocumentParser
from app.parsers.models import ExtractedDocument, ExtractedElement


class PDFParser(DocumentParser):
    """Extract PDF prose and detected tables while preserving page context."""

    def parse(self, file: BinaryIO) -> ExtractedDocument:
        document = pymupdf.open(stream=file.read(), filetype="pdf")

        try:
            elements: list[ExtractedElement] = []

            for page_number, page in enumerate(document, start=1):
                tables = page.find_tables().tables

                if not tables:
                    text = page.get_text()
                    if text.strip():
                        elements.append(
                            ExtractedElement(
                                element_type="paragraph",
                                text=text,
                                metadata={"page_number": page_number},
                            )
                        )
                    continue

                blocks = page.get_text("blocks")
                table_records = []

                for table_index, table in enumerate(tables, start=1):
                    rows = table.extract()
                    if not rows:
                        continue

                    header = getattr(table, "header", None)
                    header_names = (
                        getattr(header, "names", None) if header else None
                    )
                    if (
                        header
                        and getattr(header, "external", False)
                        and header_names
                        and rows
                        and list(rows[0]) != list(header_names)
                    ):
                        rows = [list(header_names), *rows]

                    rendered_rows = []
                    for row in rows:
                        values = [
                            re.sub(r"\s+", " ", str(value)).strip()
                            if value is not None
                            else ""
                            for value in row
                        ]
                        if any(values):
                            rendered_rows.append(" | ".join(values))

                    if not rendered_rows:
                        continue

                    x0, y0, x1, y1 = table.bbox

                    # Prefer the table's own first header cell, e.g.
                    # "Table 1. Plan", over nearby explanatory prose.
                    first_header = re.sub(
                        r"\s+", " ", str(rows[0][0] or "")
                    ).strip() if rows and rows[0] else ""

                    table_title = None
                    if re.match(r"^Table\s+\d+\b", first_header, re.I):
                        table_title = first_header

                    if not table_title:
                        title_candidates = [
                            (
                                float(block[3]),
                                re.sub(r"\s+", " ", str(block[4])).strip(),
                            )
                            for block in blocks
                            if len(block) >= 5
                            and str(block[4]).strip()
                            and float(block[3]) <= float(y0)
                            and float(y0) - float(block[3]) <= 90
                        ]

                        # Only use nearby text when it resembles a short
                        # heading, not a complete explanatory paragraph.
                        short_headings = [
                            (y, text)
                            for y, text in title_candidates
                            if len(text) <= 80 and len(text.split()) <= 12
                        ]
                        if short_headings:
                            table_title = max(
                                short_headings, key=lambda item: item[0]
                            )[1]

                    elements.append(
                        ExtractedElement(
                            element_type="table",
                            text="\n".join(rendered_rows),
                            metadata={
                                "page_number": page_number,
                                "table_index": table_index,
                                "table_title": table_title,
                                "table_bbox": [x0, y0, x1, y1],
                            },
                            content={"rows": rows},
                        )
                    )
                    table_records.append((x0, y0, x1, y1))

                # Avoid indexing the same text both as prose and table cells.
                prose_blocks = []
                for block in blocks:
                    if len(block) < 5:
                        continue

                    x0, y0, x1, y1 = map(float, block[:4])
                    text = str(block[4]).strip()
                    if not text:
                        continue

                    overlaps_table = any(
                        x0 < tx1 and x1 > tx0 and y0 < ty1 and y1 > ty0
                        for tx0, ty0, tx1, ty1 in table_records
                    )
                    if not overlaps_table:
                        prose_blocks.append((y0, x0, text))

                for _, _, text in sorted(prose_blocks):
                    elements.append(
                        ExtractedElement(
                            element_type="paragraph",
                            text=text,
                            metadata={"page_number": page_number},
                        )
                    )

            return ExtractedDocument(
                source_type="pdf",
                elements=elements,
                metadata={"page_count": len(document)},
            )
        finally:
            document.close()
