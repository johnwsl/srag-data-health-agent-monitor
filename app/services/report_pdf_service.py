"""Gera PDF do relatório executivo SRAG (texto + gráficos ChartSpec)."""

from __future__ import annotations

import html
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.chart import ChartSpec
from app.models.chat import ChatReportPayload

_FONT_REGISTERED = False
_FONT_NAME = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"

# Cores alinhadas ao dashboard Shiny (Plotly).
_COLOR_LINE = "#0d6efd"
_COLOR_BAR = "#198754"
_CONTENT_WIDTH = 16.5 * cm


def _register_fonts() -> None:
    global _FONT_REGISTERED, _FONT_NAME, _FONT_BOLD
    if _FONT_REGISTERED:
        return

    candidates = [
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
        ),
        (
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ),
    ]
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont("SragSans", str(regular)))
            pdfmetrics.registerFont(TTFont("SragSans-Bold", str(bold)))
            _FONT_NAME = "SragSans"
            _FONT_BOLD = "SragSans-Bold"
            break

    _FONT_REGISTERED = True


def _inline_markdown_to_reportlab(text: str) -> str:
    """Converte links/negrito/italico markdown simples para markup do ReportLab."""
    placeholders: list[str] = []

    def _replace_link(match: re.Match[str]) -> str:
        label = html.escape(match.group(1))
        url = html.escape(match.group(2), quote=True)
        placeholders.append(
            f'<link href="{url}" color="#0d6efd"><u>{label}</u></link>'
        )
        return f"@@LINK{len(placeholders) - 1}@@"

    with_links = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _replace_link, text or "")
    escaped = html.escape(with_links, quote=False)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", escaped)
    for index, link_html in enumerate(placeholders):
        escaped = escaped.replace(html.escape(f"@@LINK{index}@@"), link_html)
    return escaped


def _strip_markdown_heading_markers(line: str) -> str:
    cleaned = re.sub(r"^#{1,6}\s*", "", line.strip())
    if cleaned.startswith("**") and cleaned.endswith("**") and cleaned.count("**") == 2:
        cleaned = cleaned[2:-2].strip()
    return cleaned


def _is_section_heading(line: str) -> bool:
    raw = line.strip()
    if not raw or len(raw) > 120:
        return False
    if re.match(r"^#{1,6}\s+\S", raw):
        return True
    if raw.startswith("**") and raw.endswith("**") and raw.count("**") == 2:
        return True
    # Titulo curto terminando em dois pontos, sem ser item de lista.
    if raw.endswith(":") and not re.match(r"^([-*•]|\d+\.)\s+", raw) and "|" not in raw:
        return True
    return False


def _is_bullet_line(line: str) -> bool:
    return bool(re.match(r"^([-*•]|\d+\.)\s+\S", line.strip()))


def _bullet_body(line: str) -> str:
    return re.sub(r"^([-*•]|\d+\.)\s+", "", line.strip())


def _is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.count("|") >= 2


def _is_markdown_table_separator(line: str) -> bool:
    stripped = line.strip().strip("|").replace(" ", "")
    return bool(stripped) and set(stripped) <= set("-:")


def _parse_markdown_table(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        if _is_markdown_table_separator(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells:
            rows.append(cells)
    return rows


def _build_markdown_table(rows: list[list[str]], font_name: str, font_bold: str) -> Table | None:
    if len(rows) < 2:
        return None
    col_count = max(len(row) for row in rows)
    normalized = [row + [""] * (col_count - len(row)) for row in rows]
    col_width = _CONTENT_WIDTH / col_count
    table = Table(normalized, colWidths=[col_width] * col_count, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0B3D60")),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTNAME", (0, 0), (-1, 0), font_bold),
                ("FONTNAME", (0, 1), (-1, -1), font_name),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#ced4da")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#f8f9fa")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _resumo_to_flowables(
    text: str,
    *,
    body_style: ParagraphStyle,
    section_style: ParagraphStyle,
    bullet_style: ParagraphStyle,
    font_name: str = "Helvetica",
    font_bold: str = "Helvetica-Bold",
) -> list[Any]:
    """Quebra o resumo em paragrafos/titulos/tabelas legiveis no PDF."""
    del bullet_style  # mantido na assinatura por compatibilidade
    compact = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not compact:
        return []

    blocks = re.split(r"\n{2,}", compact)
    flowables: list[Any] = []

    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        if len(lines) == 1 and _is_section_heading(lines[0]) and not _is_bullet_line(lines[0]):
            heading = _strip_markdown_heading_markers(lines[0]).rstrip(":")
            flowables.append(
                Paragraph(f"<b>{html.escape(heading)}</b>", section_style)
            )
            continue

        table_lines = [line for line in lines if _is_markdown_table_line(line)]
        if len(table_lines) >= 2 and len(table_lines) >= len(lines) - 1:
            heading_lines = [line for line in lines if not _is_markdown_table_line(line)]
            for heading_line in heading_lines:
                if _is_section_heading(heading_line):
                    heading = _strip_markdown_heading_markers(heading_line).rstrip(":")
                    flowables.append(
                        Paragraph(f"<b>{html.escape(heading)}</b>", section_style)
                    )
            table = _build_markdown_table(
                _parse_markdown_table(table_lines),
                font_name=font_name,
                font_bold=font_bold,
            )
            if table is not None:
                flowables.append(table)
                flowables.append(Spacer(1, 0.2 * cm))
            continue

        if all(_is_bullet_line(line) for line in lines):
            for line in lines:
                flowables.append(
                    Paragraph(
                        _inline_markdown_to_reportlab(_bullet_body(line)),
                        body_style,
                    )
                )
            continue

        # Bloco misto: titulo opcional + texto/itens.
        buffer: list[str] = []
        bullet_buffer: list[str] = []

        def _flush_buffer() -> None:
            nonlocal buffer
            if buffer:
                flowables.append(
                    Paragraph(
                        _inline_markdown_to_reportlab(" ".join(buffer)),
                        body_style,
                    )
                )
                buffer = []

        def _flush_bullets() -> None:
            nonlocal bullet_buffer
            if not bullet_buffer:
                return
            for item in bullet_buffer:
                flowables.append(
                    Paragraph(
                        _inline_markdown_to_reportlab(item),
                        body_style,
                    )
                )
            bullet_buffer = []

        for line in lines:
            if (
                _is_section_heading(line)
                and not _is_bullet_line(line)
                and not buffer
                and not bullet_buffer
            ):
                heading = _strip_markdown_heading_markers(line).rstrip(":")
                flowables.append(
                    Paragraph(f"<b>{html.escape(heading)}</b>", section_style)
                )
                continue
            if _is_bullet_line(line):
                _flush_buffer()
                bullet_buffer.append(_bullet_body(line))
            else:
                _flush_bullets()
                buffer.append(_strip_markdown_heading_markers(line))
        _flush_buffer()
        _flush_bullets()

    return flowables


def _chart_as_dict(chart: ChartSpec | dict[str, Any]) -> dict[str, Any]:
    if isinstance(chart, ChartSpec):
        return chart.model_dump()
    return dict(chart)


def _series_from_chart(chart: dict[str, Any]) -> tuple[list[str], list[float]]:
    """Extrai eixos X/Y na mesma ordem do frontend (sem descartar pontos)."""
    x_field = (chart.get("x") or {}).get("field") or "x"
    y_field = (chart.get("y") or {}).get("field") or "y"
    labels: list[str] = []
    values: list[float] = []
    for point in chart.get("data") or []:
        if not isinstance(point, dict):
            continue
        raw_y = point.get(y_field)
        try:
            value = float(raw_y if raw_y is not None else 0)
        except (TypeError, ValueError):
            value = 0.0
        labels.append(str(point.get(x_field, "")))
        values.append(value)
    return labels, values


def _build_chart_drawing(
    chart: dict[str, Any],
    width: float = _CONTENT_WIDTH,
    height: float = 7.2 * cm,
) -> Drawing | None:
    labels, values = _series_from_chart(chart)
    if len(values) < 1:
        return None

    drawing = Drawing(width, height)
    chart_type = (chart.get("type") or "line").lower()
    y_max = max(values) if values else 1.0
    if y_max <= 0:
        y_max = 1.0

    if chart_type == "bar":
        plot = VerticalBarChart()
        plot.x = 1.3 * cm
        plot.y = 1.6 * cm
        plot.height = height - 2.6 * cm
        plot.width = width - 2.4 * cm
        plot.data = [values]
        # Mesma ordem e rotulos do frontend (sem omitir categorias).
        plot.categoryAxis.categoryNames = list(labels)
        plot.categoryAxis.labels.angle = 45
        plot.categoryAxis.labels.boxAnchor = "ne"
        plot.categoryAxis.labels.dx = -1
        plot.categoryAxis.labels.dy = -2
        plot.categoryAxis.labels.fontName = _FONT_NAME
        plot.categoryAxis.labels.fontSize = 6.5 if len(labels) <= 14 else 5.5
        plot.valueAxis.valueMin = 0
        plot.valueAxis.valueMax = y_max * 1.12
        plot.valueAxis.labels.fontName = _FONT_NAME
        plot.valueAxis.labels.fontSize = 7
        plot.barWidth = 0.7
        plot.groupSpacing = 0.2
        plot.bars[0].fillColor = HexColor(_COLOR_BAR)
        drawing.add(plot)
    else:
        plot = LinePlot()
        plot.x = 1.3 * cm
        plot.y = 1.6 * cm
        plot.height = height - 2.6 * cm
        plot.width = width - 2.4 * cm
        plot.data = [[(idx, value) for idx, value in enumerate(values)]]
        plot.joinedLines = 1
        plot.lines[0].strokeColor = HexColor(_COLOR_LINE)
        plot.lines[0].strokeWidth = 1.8
        plot.lines[0].symbol = makeMarker("Circle")
        plot.lines[0].symbol.size = 3
        plot.lines[0].symbol.fillColor = HexColor(_COLOR_LINE)
        plot.xValueAxis.valueMin = 0
        plot.xValueAxis.valueMax = max(len(values) - 1, 1)
        plot.xValueAxis.labels.fontName = _FONT_NAME
        plot.xValueAxis.labels.fontSize = 6
        plot.yValueAxis.valueMin = 0
        plot.yValueAxis.valueMax = y_max * 1.12
        plot.yValueAxis.labels.fontName = _FONT_NAME
        plot.yValueAxis.labels.fontSize = 7

        # Para series diarias longas, mostra um subconjunto de rotulos.
        step = max(1, len(labels) // 8)

        def _x_label(idx: float) -> str:
            i = int(round(idx))
            if i < 0 or i >= len(labels) or i % step != 0:
                return ""
            return labels[i]

        plot.xValueAxis.labelTextFormat = _x_label
        drawing.add(plot)

    title = str(chart.get("title") or chart.get("id") or "Gráfico")
    drawing.add(
        String(
            1.3 * cm,
            height - 0.55 * cm,
            title[:90],
            fontName=_FONT_BOLD,
            fontSize=9,
            fillColor=HexColor("#0B3D60"),
        )
    )
    return drawing


class ReportPdfService:
    """Monta bytes PDF a partir do payload do relatório já gerado."""

    def build(self, payload: ChatReportPayload | dict[str, Any]) -> bytes:
        _register_fonts()
        if isinstance(payload, dict):
            data = ChatReportPayload.model_validate(payload)
        else:
            data = payload

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=1.8 * cm,
            rightMargin=1.8 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
            title=f"Relatório executivo SRAG — {data.estado}",
            author="SRAG Data Health Agent Monitor",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "SragTitle",
            parent=styles["Title"],
            fontName=_FONT_BOLD,
            fontSize=16,
            leading=20,
            textColor=HexColor("#0B3D60"),
            spaceAfter=6,
        )
        meta_style = ParagraphStyle(
            "SragMeta",
            parent=styles["Normal"],
            fontName=_FONT_NAME,
            fontSize=9,
            leading=12,
            textColor=HexColor("#495057"),
            spaceAfter=8,
        )
        heading_style = ParagraphStyle(
            "SragH1",
            parent=styles["Heading1"],
            fontName=_FONT_BOLD,
            fontSize=11,
            leading=14,
            textColor=HexColor("#1F4E79"),
            spaceBefore=10,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "SragBody",
            parent=styles["Normal"],
            fontName=_FONT_NAME,
            fontSize=10,
            leading=14,
            textColor=HexColor("#212529"),
            spaceAfter=8,
            alignment=0,
        )
        section_style = ParagraphStyle(
            "SragSection",
            parent=styles["Heading2"],
            fontName=_FONT_BOLD,
            fontSize=10.5,
            leading=13,
            textColor=HexColor("#0B3D60"),
            spaceBefore=8,
            spaceAfter=4,
        )
        bullet_style = ParagraphStyle(
            "SragBullet",
            parent=body_style,
            leftIndent=12,
            spaceAfter=3,
            leading=13,
        )
        caveat_style = ParagraphStyle(
            "SragCaveat",
            parent=styles["Normal"],
            fontName=_FONT_NAME,
            fontSize=8,
            leading=11,
            textColor=HexColor("#6c757d"),
            spaceBefore=4,
            spaceAfter=8,
        )
        source_style = ParagraphStyle(
            "SragSource",
            parent=styles["Normal"],
            fontName=_FONT_NAME,
            fontSize=7.5,
            leading=10,
            textColor=HexColor("#6c757d"),
            spaceAfter=4,
        )

        generated_at = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        story: list[Any] = [
            Paragraph("Relatório executivo SRAG", title_style),
            Paragraph(
                f"<b>Escopo:</b> {html.escape(data.estado)} &nbsp;|&nbsp; "
                f"<b>Gerado em:</b> {generated_at}",
                meta_style,
            ),
            Paragraph("Resumo executivo", heading_style),
        ]
        story.extend(
            _resumo_to_flowables(
                data.resumo_executivo,
                body_style=body_style,
                section_style=section_style,
                bullet_style=bullet_style,
                font_name=_FONT_NAME,
                font_bold=_FONT_BOLD,
            )
        )

        charts = [_chart_as_dict(chart) for chart in data.charts]
        caveat = next((c.get("caveat") for c in charts if c.get("caveat")), None)
        if caveat:
            story.append(Paragraph(f"<i>{html.escape(str(caveat))}</i>", caveat_style))

        if charts:
            story.append(Paragraph("Gráficos SRAG", heading_style))
            for chart in charts:
                drawing = _build_chart_drawing(chart)
                if drawing is not None:
                    story.append(drawing)
                    story.append(Spacer(1, 0.25 * cm))
                else:
                    labels, values = _series_from_chart(chart)
                    if labels and values:
                        rows = [["Período", "Valor"]] + [
                            [labels[i], f"{values[i]:.0f}"]
                            for i in range(min(len(labels), 12))
                        ]
                        table = Table(rows, colWidths=[8 * cm, 4 * cm])
                        table.setStyle(
                            TableStyle(
                                [
                                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#0B3D60")),
                                    ("TEXTCOLOR", (0, 0), (-1, 0), white),
                                    ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
                                    ("FONTNAME", (0, 1), (-1, -1), _FONT_NAME),
                                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                                    ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#ced4da")),
                                    (
                                        "ROWBACKGROUNDS",
                                        (0, 1),
                                        (-1, -1),
                                        [white, HexColor("#f8f9fa")],
                                    ),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                ]
                            )
                        )
                        story.append(
                            Paragraph(
                                html.escape(
                                    str(chart.get("title") or chart.get("id") or "Série")
                                ),
                                body_style,
                            )
                        )
                        story.append(table)
                        story.append(Spacer(1, 0.3 * cm))

                source = chart.get("source")
                if source:
                    story.append(
                        Paragraph(
                            f"Fonte: {html.escape(str(source))}",
                            source_style,
                        )
                    )

        story.append(Spacer(1, 0.4 * cm))
        story.append(
            Paragraph(
                "Documento gerado pelo SRAG Data Health Agent Monitor. "
                "Os números oficiais vêm da API do projeto (OpenDataSUS / DATASUS).",
                caveat_style,
            )
        )

        doc.build(story)
        return buffer.getvalue()
