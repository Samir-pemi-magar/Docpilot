from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _paragraph(value: Any) -> str:
    """Escape arbitrary stored text before passing it to ReportLab."""
    return escape(str(value if value is not None else "")).replace("\n", "<br/>")


def _format_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return str(value)


def generate_evaluation_report_pdf(
    *,
    dataset_name: str,
    run: Any,
    results: list[Any],
) -> bytes:
    """Generate a PDF report from a persisted evaluation run and its results."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title=f"DocPilot Evaluation Report - {dataset_name}",
        author="DocPilot",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1F2937"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMetadata",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#6B7280"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportBody",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=12,
            splitLongWords=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSmall",
            parent=styles["BodyText"],
            fontSize=7.5,
            leading=10,
            splitLongWords=True,
        )
    )

    story = [
        Paragraph("DocPilot", styles["ReportTitle"]),
        Paragraph("Evaluation report", styles["ReportMetadata"]),
        Paragraph(
            "Generated "
            + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            styles["ReportMetadata"],
        ),
        Spacer(1, 7 * mm),
        HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#D1D5DB")),
        Spacer(1, 4 * mm),
        Paragraph("Run overview", styles["Heading2"]),
    ]

    overview = [
        ["Dataset", dataset_name],
        ["Run ID", str(run.id)],
        ["Status", str(run.status)],
        ["Total cases", str(run.total_cases)],
        ["Completed cases", str(run.completed_cases)],
        ["Failed cases", str(run.failed_cases)],
        ["Started", _format_value(run.started_at)],
        ["Completed", _format_value(run.completed_at)],
    ]
    overview_table = Table(
        [
            [
                Paragraph(f"<b>{_paragraph(label)}</b>", styles["ReportBody"]),
                Paragraph(_paragraph(value), styles["ReportBody"]),
            ]
            for label, value in overview
        ],
        colWidths=[42 * mm, 125 * mm],
        hAlign="LEFT",
    )
    overview_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([overview_table, Spacer(1, 5 * mm)])

    if run.error_message:
        story.extend(
            [
                Paragraph("Run error", styles["Heading3"]),
                Paragraph(_paragraph(run.error_message), styles["ReportBody"]),
                Spacer(1, 3 * mm),
            ]
        )

    story.append(Paragraph("Aggregate metrics", styles["Heading2"]))
    metrics = run.metrics or {}
    if metrics:
        metric_rows = [
            [
                Paragraph("<b>Metric</b>", styles["ReportSmall"]),
                Paragraph("<b>Value</b>", styles["ReportSmall"]),
            ]
        ]
        for key, value in sorted(metrics.items()):
            metric_rows.append(
                [
                    Paragraph(_paragraph(key.replace("_", " ")), styles["ReportSmall"]),
                    Paragraph(_paragraph(_format_value(value)), styles["ReportSmall"]),
                ]
            )
        metric_table = Table(metric_rows, colWidths=[85 * mm, 82 * mm], repeatRows=1)
        metric_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.extend([metric_table, Spacer(1, 5 * mm)])
    else:
        story.extend(
            [
                Paragraph("No aggregate metrics were recorded for this run.", styles["ReportBody"]),
                Spacer(1, 4 * mm),
            ]
        )

    story.append(Paragraph(f"Case results ({len(results)} records)", styles["Heading2"]))

    if not results:
        story.append(Paragraph("No case results were recorded.", styles["ReportBody"]))

    for index, result in enumerate(results, start=1):
        story.append(
            KeepTogether(
                [
                    HRFlowable(
                        width="100%",
                        thickness=0.5,
                        color=colors.HexColor("#D1D5DB"),
                    ),
                    Spacer(1, 2 * mm),
                    Paragraph(
                        f"Question {index} — {_paragraph(result.status)}"
                        + (
                            f" — {result.duration_ms} ms"
                            if result.duration_ms is not None
                            else ""
                        ),
                        styles["Heading3"],
                    ),
                    Paragraph("<b>Question</b>", styles["ReportBody"]),
                    Paragraph(_paragraph(result.question_snapshot), styles["ReportBody"]),
                    Spacer(1, 2 * mm),
                ]
            )
        )

        if result.reference_answer_snapshot:
            story.extend(
                [
                    Paragraph("<b>Reference answer</b>", styles["ReportBody"]),
                    Paragraph(
                        _paragraph(result.reference_answer_snapshot),
                        styles["ReportBody"],
                    ),
                    Spacer(1, 2 * mm),
                ]
            )

        story.extend(
            [
                Paragraph("<b>Generated answer</b>", styles["ReportBody"]),
                Paragraph(
                    _paragraph(result.actual_answer or "No answer produced."),
                    styles["ReportBody"],
                ),
                Spacer(1, 2 * mm),
            ]
        )

        if result.error_message:
            story.extend(
                [
                    Paragraph("<b>Error</b>", styles["ReportBody"]),
                    Paragraph(_paragraph(result.error_message), styles["ReportBody"]),
                    Spacer(1, 2 * mm),
                ]
            )

        if result.metrics:
            story.extend(
                [
                    Paragraph("<b>Case metrics</b>", styles["ReportBody"]),
                    Paragraph(_paragraph(_format_value(result.metrics)), styles["ReportSmall"]),
                    Spacer(1, 2 * mm),
                ]
            )

        metadata = result.case_metadata_snapshot or {}
        if metadata:
            story.extend(
                [
                    Paragraph("<b>Benchmark metadata</b>", styles["ReportBody"]),
                    Paragraph(_paragraph(_format_value(metadata)), styles["ReportSmall"]),
                    Spacer(1, 2 * mm),
                ]
            )

        sources = result.retrieved_sources or []
        story.append(
            Paragraph(f"<b>Retrieved sources ({len(sources)})</b>", styles["ReportBody"])
        )
        if not sources:
            story.append(Paragraph("No sources returned.", styles["ReportSmall"]))
        else:
            for source_index, source in enumerate(sources, start=1):
                if not isinstance(source, dict):
                    continue
                source_label = (
                    source.get("document_name")
                    or source.get("filename")
                    or source.get("document_id")
                    or f"Source {source_index}"
                )
                chunk_index = source.get("chunk_index")
                if chunk_index is not None:
                    source_label = f"{source_label} — chunk {chunk_index}"
                story.append(
                    Paragraph(
                        f"<b>{source_index}. {_paragraph(source_label)}</b>",
                        styles["ReportSmall"],
                    )
                )
                source_text = source.get("text") or source.get("content")
                if source_text:
                    story.append(
                        Paragraph(_paragraph(source_text), styles["ReportSmall"])
                    )
                story.append(Spacer(1, 1.5 * mm))

        story.append(Spacer(1, 3 * mm))

    def add_page_number(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(18 * mm, 9 * mm, "DocPilot — evaluation report")
        canvas.drawRightString(
            A4[0] - 18 * mm,
            9 * mm,
            f"Page {document.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()
