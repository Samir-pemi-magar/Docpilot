from __future__ import annotations

import re
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


def _safe_paragraph_text(value: str) -> str:
    """Escape untrusted text and preserve simple Markdown formatting."""
    value = xml_escape(value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", value)
    value = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', value)
    return value


def _add_markdown_text(story: list, text: str, styles) -> None:
    """Render common Markdown constructs as readable PDF paragraphs."""
    lines = text.splitlines()
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            content = "<br/>".join(
                _safe_paragraph_text(line) for line in paragraph_lines
            )
            story.append(Paragraph(content, styles["BodyTextCustom"]))
            story.append(Spacer(1, 3 * mm))
            paragraph_lines.clear()

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            flush_paragraph()
            continue

        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            style = styles[f"Heading{level}"]
            story.append(
                Paragraph(_safe_paragraph_text(heading.group(2)), style)
            )
            story.append(Spacer(1, 2 * mm))
            continue

        bullet = re.match(r"^[-*+]\s+(.+)$", line)
        numbered = re.match(r"^\d+[.)]\s+(.+)$", line)

        if bullet or numbered:
            flush_paragraph()
            item_text = (bullet or numbered).group(1)
            marker = "•" if bullet else "–"
            story.append(
                Paragraph(
                    f"{marker}  {_safe_paragraph_text(item_text)}",
                    styles["BodyTextCustom"],
                )
            )
            story.append(Spacer(1, 1.5 * mm))
            continue

        if line.startswith(">"):
            flush_paragraph()
            story.append(
                Paragraph(
                    _safe_paragraph_text(line.lstrip("> ").strip()),
                    styles["QuoteCustom"],
                )
            )
            story.append(Spacer(1, 2 * mm))
            continue

        paragraph_lines.append(line)

    flush_paragraph()


def generate_chat_answer_pdf(
    *,
    question: str,
    answer: str,
    sources: list[dict] | None,
    conversation_id: str,
    message_id: str,
) -> bytes:
    """Generate a downloadable PDF from a persisted answer and source snapshot."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title="DocPilot Chat Answer",
        author="DocPilot",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="BodyTextCustom",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            spaceAfter=2,
            splitLongWords=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="QuoteCustom",
            parent=styles["BodyTextCustom"],
            leftIndent=10,
            borderColor=colors.HexColor("#9CA3AF"),
            borderWidth=0,
            textColor=colors.HexColor("#4B5563"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Metadata",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#6B7280"),
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SourceTitle",
            parent=styles["Heading3"],
            fontSize=10,
            leading=13,
            spaceBefore=5,
            spaceAfter=3,
        )
    )

    story = [
        Paragraph("DocPilot", styles["DocTitle"]),
        Paragraph("Chat answer export", styles["Metadata"]),
        Paragraph(
            "Generated "
            + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            styles["Metadata"],
        ),
        Spacer(1, 8 * mm),
        HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#D1D5DB")),
        Spacer(1, 5 * mm),
        Paragraph("Question", styles["Heading2"]),
    ]

    _add_markdown_text(story, question, styles)

    story.extend(
        [
            Paragraph("Answer", styles["Heading2"]),
            Spacer(1, 1 * mm),
        ]
    )
    _add_markdown_text(story, answer, styles)

    if sources:
        story.extend(
            [
                Spacer(1, 3 * mm),
                HRFlowable(
                    width="100%",
                    thickness=0.7,
                    color=colors.HexColor("#D1D5DB"),
                ),
                Spacer(1, 4 * mm),
                Paragraph("Supporting source excerpts", styles["Heading2"]),
            ]
        )

        for index, source in enumerate(sources, start=1):
            if not isinstance(source, dict):
                continue

            document_name = str(source.get("document_name") or "Document")
            chunk_index = source.get("chunk_index")
            heading = f"{index}. {document_name}"
            if chunk_index is not None:
                heading += f" — chunk {chunk_index}"

            story.append(
                Paragraph(_safe_paragraph_text(heading), styles["SourceTitle"])
            )
            source_text = str(source.get("text") or "").strip()
            if source_text:
                _add_markdown_text(story, source_text, styles)

    def add_page_number(canvas, document) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(20 * mm, 10 * mm, "DocPilot — chat answer")
        canvas.drawRightString(
            A4[0] - 20 * mm,
            10 * mm,
            f"Page {document.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return buffer.getvalue()
