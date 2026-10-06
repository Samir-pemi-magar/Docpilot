from typing import BinaryIO

from openpyxl import load_workbook

from app.parsers.base import DocumentParser
from app.parsers.models import ExtractedDocument, ExtractedElement


class XLSXParser(DocumentParser):
    """Parser for Microsoft Excel workbooks."""

    def parse(self, file: BinaryIO) -> ExtractedDocument:
        workbook = load_workbook(
            file,
            read_only=False,
            data_only=False,
        )

        elements = []

        for worksheet in workbook.worksheets:
            cells = []

            for row in worksheet.iter_rows():
                for cell in row:
                    if cell.value is None:
                        continue

                    cells.append(
                        {
                            "coordinate": cell.coordinate,
                            "row": cell.row,
                            "column": cell.column,
                            "value": cell.value,
                            "data_type": cell.data_type,
                        }
                    )

            merged_ranges = [
                str(cell_range)
                for cell_range in worksheet.merged_cells.ranges
            ]

            elements.append(
                ExtractedElement(
                    element_type="worksheet",
                    text=worksheet.title,
                    metadata={
                        "sheet": worksheet.title,
                        "max_row": worksheet.max_row,
                        "max_column": worksheet.max_column,
                        "merged_ranges": merged_ranges,
                    },
                    content={
                        "cells": cells,
                    },
                )
            )

        metadata = {
            "sheet_count": len(workbook.worksheets),
            "sheet_names": workbook.sheetnames,
        }

        workbook.close()

        return ExtractedDocument(
            source_type="xlsx",
            elements=elements,
            metadata=metadata,
        )
