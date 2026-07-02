from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas


OUTPUT_PATH = Path(__file__).with_name("arquitetura_solucao_agente.pdf")


def draw_box(pdf: canvas.Canvas, x: float, y: float, w: float, h: float, title: str, lines: list[str], fill_color):
    pdf.setFillColor(fill_color)
    pdf.setStrokeColor(colors.HexColor("#355070"))
    pdf.roundRect(x, y, w, h, 6 * mm, stroke=1, fill=1)

    pdf.setFillColor(colors.HexColor("#1f2937"))
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(x + 8, y + h - 18, title)

    pdf.setFont("Helvetica", 10)
    text_y = y + h - 34
    for line in lines:
        pdf.drawString(x + 10, text_y, f"- {line}")
        text_y -= 14


def draw_arrow(pdf: canvas.Canvas, x1: float, y1: float, x2: float, y2: float, label: str):
    pdf.setStrokeColor(colors.HexColor("#4b5563"))
    pdf.setFillColor(colors.HexColor("#4b5563"))
    pdf.setLineWidth(1.5)
    pdf.line(x1, y1, x2, y2)

    angle = 0
    if x2 != x1:
        angle = (y2 - y1) / (x2 - x1)

    arrow_size = 7
    if abs(x2 - x1) >= abs(y2 - y1):
        pdf.line(x2, y2, x2 - arrow_size, y2 + arrow_size / 2)
        pdf.line(x2, y2, x2 - arrow_size, y2 - arrow_size / 2)
    else:
        pdf.line(x2, y2, x2 - arrow_size / 2, y2 - arrow_size)
        pdf.line(x2, y2, x2 + arrow_size / 2, y2 - arrow_size)

    if label:
        pdf.setFont("Helvetica", 9)
        label_x = (x1 + x2) / 2
        label_y = (y1 + y2) / 2 + 8
        width = stringWidth(label, "Helvetica", 9)
        pdf.setFillColor(colors.white)
        pdf.rect(label_x - width / 2 - 3, label_y - 2, width + 6, 12, stroke=0, fill=1)
        pdf.setFillColor(colors.HexColor("#374151"))
        pdf.drawString(label_x - width / 2, label_y, label)


def draw_note(pdf: canvas.Canvas, x: float, y: float, w: float, h: float, text: str):
    pdf.setFillColor(colors.HexColor("#fff7ed"))
    pdf.setStrokeColor(colors.HexColor("#fb923c"))
    pdf.roundRect(x, y, w, h, 4 * mm, stroke=1, fill=1)

    styles = getSampleStyleSheet()
    style = ParagraphStyle(
        "note",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#7c2d12"),
    )
    paragraph = Paragraph(text, style)
    paragraph.wrapOn(pdf, w - 12, h - 12)
    paragraph.drawOn(pdf, x + 6, y + h - 40)


def build_pdf():
    width, height = landscape(A4)
    pdf = canvas.Canvas(str(OUTPUT_PATH), pagesize=(width, height))
    pdf.setTitle("Arquitetura da Solucao - Agente Orquestrador SRAG")

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(22 * mm, height - 18 * mm, "Arquitetura Conceitual da Solucao")

    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(colors.HexColor("#374151"))
    pdf.drawString(
        22 * mm,
        height - 26 * mm,
        "Agente principal, tools LangChain, LLM, fontes de noticias, API SRAG, pipeline e banco de dados.",
    )

    top_y = height - 70 * mm

    draw_box(
        pdf,
        18 * mm,
        top_y,
        58 * mm,
        46 * mm,
        "Dashboard / Usuario",
        [
            "Filtro por UF ou BRASIL",
            "Botao 'Gerar relatorio'",
            "Visualiza metricas, graficos",
            "Exibe resumo executivo",
        ],
        colors.HexColor("#e0f2fe"),
    )

    draw_box(
        pdf,
        92 * mm,
        top_y,
        68 * mm,
        52 * mm,
        "Agente Principal (Orquestrador)",
        [
            "SragReportAgent",
            "Verifica status da pipeline",
            "Aciona tools de metricas e noticias",
            "Monta prompt e limita saida",
        ],
        colors.HexColor("#dbeafe"),
    )

    draw_box(
        pdf,
        176 * mm,
        top_y + 10 * mm,
        48 * mm,
        34 * mm,
        "LLM OpenAI",
        [
            "LangChain + ChatOpenAI",
            "Gera resumo final",
        ],
        colors.HexColor("#ede9fe"),
    )

    lower_y = 44 * mm

    draw_box(
        pdf,
        18 * mm,
        lower_y,
        58 * mm,
        44 * mm,
        "Tool de Noticias",
        [
            "TavilyNewsLangChainService",
            "Usa Tavily Search",
            "Aplica guardrails",
            "Retorna manchetes e URLs",
        ],
        colors.HexColor("#dcfce7"),
    )

    draw_box(
        pdf,
        92 * mm,
        lower_y,
        68 * mm,
        56 * mm,
        "Tool de Metricas / API SRAG",
        [
            "SragMetricsApiLangChainService",
            "GET /datasets/status",
            "POST /datasets/pipeline se necessario",
            "GET /metrics e series temporais",
        ],
        colors.HexColor("#fef3c7"),
    )

    draw_box(
        pdf,
        176 * mm,
        lower_y + 14 * mm,
        48 * mm,
        28 * mm,
        "Banco de Dados",
        [
            "DuckDB",
            "Tabela srag_notificacoes",
        ],
        colors.HexColor("#fee2e2"),
    )

    draw_box(
        pdf,
        176 * mm,
        lower_y - 20 * mm,
        48 * mm,
        26 * mm,
        "Fontes Externas",
        [
            "OpenDataSUS",
            "Noticias via Tavily",
        ],
        colors.HexColor("#f3e8ff"),
    )

    draw_arrow(pdf, 76 * mm, top_y + 23 * mm, 92 * mm, top_y + 23 * mm, "requisicao")
    draw_arrow(pdf, 160 * mm, top_y + 26 * mm, 176 * mm, top_y + 26 * mm, "prompt")
    draw_arrow(pdf, 176 * mm, top_y + 18 * mm, 160 * mm, top_y + 18 * mm, "resumo")
    draw_arrow(pdf, 126 * mm, top_y, 126 * mm, lower_y + 56 * mm, "tool")
    draw_arrow(pdf, 92 * mm, top_y, 58 * mm, lower_y + 44 * mm, "tool")
    draw_arrow(pdf, 160 * mm, lower_y + 30 * mm, 176 * mm, lower_y + 30 * mm, "queries")
    draw_arrow(pdf, 160 * mm, lower_y + 10 * mm, 176 * mm, lower_y - 7 * mm, "coleta")

    draw_note(
        pdf,
        18 * mm,
        14 * mm,
        206 * mm,
        18 * mm,
        "<b>Fluxo resumido:</b> Usuario/dash aciona o agente. O orquestrador garante que a pipeline esteja pronta, "
        "consulta metricas oficiais e noticias recentes, envia o contexto consolidado ao LLM e devolve um resumo "
        "executivo com separacao entre dados oficiais e noticias.",
    )

    pdf.showPage()
    pdf.save()


if __name__ == "__main__":
    build_pdf()
    print(OUTPUT_PATH)
