"""PDF export — session to .pdf file via reportlab."""

from __future__ import annotations

from pathlib import Path

from voicemeet.export import _resolve_output
from voicemeet.store.models import Segment, Session
from voicemeet.summarize.ollama_summarizer import SummaryResult


def export_pdf(
    session: Session,
    summary: SummaryResult,
    segments: list[Segment],
    output_path: str | Path | None = None,
    export_dir: Path | None = None,
) -> str:
    """Export session as a PDF file. Returns the file path."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as e:
        raise ImportError(
            "reportlab is required for PDF export. Install with: pip install reportlab"
        ) from e

    path = _resolve_output(output_path, session, summary, "pdf", export_dir)

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=20,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
    )

    story: list = []

    # Title
    title = summary.title or session.title or "Untitled Meeting"
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 10))

    # Metadata table
    started = session.started_dt
    date_str = started.strftime("%d.%m.%Y")
    start_time = started.strftime("%H:%M")
    end_time = session.ended_dt.strftime("%H:%M") if session.ended_dt else "—"

    meta_data = [
        ["Date", date_str],
        ["Time", f"{start_time} – {end_time} ({session.duration_str})"],
        ["Mode", session.mode],
    ]
    participants = summary.participants or session.participants
    if participants:
        meta_data.append(["Participants", ", ".join(participants)])
    topics = summary.topics or session.topics
    if topics:
        meta_data.append(["Topics", ", ".join(topics)])

    meta_table = Table(meta_data, colWidths=[100, 350])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # Summary
    if summary.summary_markdown:
        story.append(Paragraph("Summary", heading_style))
        for line in summary.summary_markdown.split("\n"):
            line = line.strip()
            if line:
                clean = line.replace("#", "").replace("*", "").strip()
                story.append(Paragraph(clean, body_style))
        story.append(Spacer(1, 10))

    # Action Items
    if summary.action_items:
        story.append(Paragraph("Action Items", heading_style))
        for item in summary.action_items:
            story.append(Paragraph(f"☐ {item}", body_style))
        story.append(Spacer(1, 10))

    # Transcript
    if segments:
        story.append(Paragraph("Transcript", heading_style))
        transcript_data = [["Time", "Speaker", "Text"]]
        for seg in segments:
            transcript_data.append(
                [
                    Paragraph(seg.start_str, cell_style),
                    Paragraph(seg.speaker or "Speaker", cell_style),
                    Paragraph(seg.text, cell_style),
                ]
            )
        transcript_table = Table(
            transcript_data,
            colWidths=[50, 70, 330],
            repeatRows=1,
        )
        transcript_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0e0e0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 9),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(transcript_table)

    doc.build(story)
    return str(path)
