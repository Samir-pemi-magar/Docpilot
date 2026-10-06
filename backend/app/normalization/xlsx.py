from app.normalization.models import (
    NormalizedDocument,
    NormalizedElement,
    NormalizedElementType,
)
from app.parsers.models import ExtractedDocument


class XLSXNormalizer:
    """Normalize extracted Excel workbook content."""

    def normalize(
        self,
        document: ExtractedDocument,
    ) -> NormalizedDocument:
        elements = []

        for sheet_index, element in enumerate(document.elements):
            if element.element_type != "worksheet":
                continue

            cells = element.content["cells"]
            regions = self._find_regions(cells)

            consumed_positions = set()

            for region in regions:
                region_type = self._classify_region(
                    cells=cells,
                    region=region,
                )

                if region_type == NormalizedElementType.KEY_VALUE:
                    content = self._region_to_key_value(
                        cells=cells,
                        region=region,
                    )
                else:
                    content = self._region_to_table(
                        cells=cells,
                        region=region,
                    )

                for row in range(
                    region["start_row"],
                    region["end_row"] + 1,
                ):
                    for column in range(
                        region["start_column"],
                        region["end_column"] + 1,
                    ):
                        consumed_positions.add((row, column))

                elements.append(
                    NormalizedElement(
                        element_type=region_type,
                        text=content["text"],
                        metadata={
                            "sheet": element.metadata["sheet"],
                            "sheet_index": sheet_index,
                            "start_row": region["start_row"],
                            "end_row": region["end_row"],
                            "start_column": region["start_column"],
                            "end_column": region["end_column"],
                        },
                        content=content,
                    )
                )

            for cell in cells:
                position = (cell["row"], cell["column"])

                if position in consumed_positions:
                    continue

                value = cell["value"]

                if not isinstance(value, str):
                    continue

                text = value.strip()

                if not text:
                    continue

                if len(text) <= 40:
                    element_type = NormalizedElementType.HEADING
                else:
                    element_type = NormalizedElementType.PARAGRAPH

                elements.append(
                    NormalizedElement(
                        element_type=element_type,
                        text=text,
                        metadata={
                            "sheet": element.metadata["sheet"],
                            "sheet_index": sheet_index,
                            "row": cell["row"],
                            "column": cell["column"],
                            "coordinate": cell["coordinate"],
                        },
                        content=None,
                    )
                )

        elements.sort(
            key=lambda element: (
                element.metadata["sheet_index"],
                element.metadata.get(
                    "start_row",
                    element.metadata.get("row", 0),
                ),
                element.metadata.get(
                    "start_column",
                    element.metadata.get("column", 0),
                ),
            )
        )

        return NormalizedDocument(
            source_type=document.source_type,
            elements=elements,
            metadata=document.metadata.copy(),
        )

    def _classify_region(
        self,
        cells: list[dict],
        region: dict,
    ) -> NormalizedElementType:
        """Classify a rectangular region."""

        column_count = (
            region["end_column"]
            - region["start_column"]
            + 1
        )

        row_count = (
            region["end_row"]
            - region["start_row"]
            + 1
        )

        if column_count == 2 and row_count <= 2:
            return NormalizedElementType.KEY_VALUE

        return NormalizedElementType.TABLE

    def _region_to_key_value(
        self,
        cells: list[dict],
        region: dict,
    ) -> dict:
        """Convert a two-column region into key-value data."""

        cells_by_position = {
            (cell["row"], cell["column"]): cell
            for cell in cells
        }

        pairs = []

        for row_number in range(
            region["start_row"],
            region["end_row"] + 1,
        ):
            key = cells_by_position[
                (
                    row_number,
                    region["start_column"],
                )
            ]["value"]

            value = cells_by_position[
                (
                    row_number,
                    region["start_column"] + 1,
                )
            ]["value"]

            pairs.append(
                {
                    "key": key,
                    "value": value,
                }
            )

        text = "\n".join(
            f"{pair['key']}: {pair['value']}"
            for pair in pairs
        )

        return {
            "pairs": pairs,
            "text": text,
        }

    def _region_to_table(
        self,
        cells: list[dict],
        region: dict,
    ) -> dict:
        """Convert a rectangular cell region into table data."""

        cells_by_position = {
            (cell["row"], cell["column"]): cell
            for cell in cells
        }

        rows = []

        for row_number in range(
            region["start_row"],
            region["end_row"] + 1,
        ):
            row = []

            for column_number in range(
                region["start_column"],
                region["end_column"] + 1,
            ):
                cell = cells_by_position[
                    (row_number, column_number)
                ]

                row.append(cell["value"])

            rows.append(row)

        headers = rows[0]
        data_rows = rows[1:]

        text_lines = [
            " | ".join(str(value) for value in headers)
        ]

        for row in data_rows:
            text_lines.append(
                " | ".join(str(value) for value in row)
            )

        return {
            "headers": headers,
            "rows": data_rows,
            "text": "\n".join(text_lines),
        }

    def _find_regions(
        self,
        cells: list[dict],
    ) -> list[dict]:
        """Find the largest dense rectangular regions of populated cells."""

        cells_by_position = {
            (cell["row"], cell["column"]): cell
            for cell in cells
        }

        regions = []

        rows = sorted({row for row, _ in cells_by_position})
        columns = sorted({column for _, column in cells_by_position})

        for start_row in rows:
            for start_column in columns:
                if (start_row, start_column) not in cells_by_position:
                    continue

                end_column = start_column

                while (
                    start_row,
                    end_column + 1,
                ) in cells_by_position:
                    end_column += 1

                end_row = start_row

                while (
                    end_row + 1,
                    start_column,
                ) in cells_by_position:
                    end_row += 1

                row_count = end_row - start_row + 1
                column_count = end_column - start_column + 1

                if row_count < 1 or column_count < 2:
                    continue

                complete = all(
                    (row, column) in cells_by_position
                    for row in range(
                        start_row,
                        end_row + 1,
                    )
                    for column in range(
                        start_column,
                        end_column + 1,
                    )
                )

                if not complete:
                    continue

                # A single-row two-column region can represent
                # a key-value pair, such as:
                # Email | international@example.com
                if row_count == 1 and column_count == 2:
                    regions.append(
                        {
                            "start_row": start_row,
                            "end_row": end_row,
                            "start_column": start_column,
                            "end_column": end_column,
                        }
                    )
                    continue

                regions.append(
                    {
                        "start_row": start_row,
                        "end_row": end_row,
                        "start_column": start_column,
                        "end_column": end_column,
                    }
                )

        filtered_regions = []

        for region in regions:
            contained = any(
                other != region
                and other["start_row"] <= region["start_row"]
                and other["end_row"] >= region["end_row"]
                and other["start_column"] <= region["start_column"]
                and other["end_column"] >= region["end_column"]
                for other in regions
            )

            if not contained:
                filtered_regions.append(region)

        return filtered_regions
