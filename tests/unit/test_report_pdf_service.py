from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

from app.models.chart import ChartAxisSpec, ChartSpec
from app.models.chat import ChatReportPayload
from app.services.report_pdf_service import (
    ReportPdfService,
    _inline_markdown_to_reportlab,
    _resumo_to_flowables,
)


def _sample_payload() -> ChatReportPayload:
    return ChatReportPayload(
        estado="SP",
        resumo_executivo=(
            "**Resumo Executivo - Estado de São Paulo (SP)**\n\n"
            "**Período Analisado:** Maio de 2026 a Junho de 2026\n\n"
            "Principais Métricas:\n"
            "- Taxa de aumento: **-8,1%**\n"
            "- Mortalidade estável no período.\n\n"
            "Dados oficiais apontam redução moderada de casos."
        ),
        charts=[
            ChartSpec(
                id="casos_diarios",
                type="line",
                title="Casos diários de SRAG (últimos 30 dias) — SP",
                x=ChartAxisSpec(field="data", label="Data"),
                y=ChartAxisSpec(field="casos", label="Notificações"),
                data=[
                    {"data": "2026-06-01", "casos": 2},
                    {"data": "2026-06-02", "casos": 5},
                    {"data": "2026-06-03", "casos": 4},
                ],
                source="GET /metrics/SP/casos-diarios",
                caveat="Períodos recentes podem estar incompletos.",
            ),
            ChartSpec(
                id="casos_mensais",
                type="bar",
                title="Casos mensais de SRAG (últimos 12 meses) — SP",
                x=ChartAxisSpec(field="label", label="Mês"),
                y=ChartAxisSpec(field="casos", label="Notificações"),
                data=[
                    {"label": "04/2026", "casos": 80},
                    {"label": "05/2026", "casos": 95},
                    {"label": "06/2026", "casos": 70},
                ],
                source="GET /metrics/SP/casos-mensais",
            ),
        ],
    )


def test_inline_markdown_converts_bold_and_links():
    assert _inline_markdown_to_reportlab("Taxa **-8,1%**") == "Taxa <b>-8,1%</b>"
    html_link = _inline_markdown_to_reportlab("[SRAG](https://www.gov.br/saude)")
    assert '<link href="https://www.gov.br/saude"' in html_link
    assert "<u>SRAG</u>" in html_link


def test_resumo_to_flowables_converts_lists_to_prose():
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"])
    section = ParagraphStyle("section", parent=styles["Heading2"])
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=10)

    flowables = _resumo_to_flowables(
        _sample_payload().resumo_executivo,
        body_style=body,
        section_style=section,
        bullet_style=bullet,
    )

    assert len(flowables) >= 3
    rendered = " ".join(item.getPlainText() for item in flowables)
    assert "**" not in rendered
    assert "•" not in rendered
    assert "Resumo Executivo - Estado de São Paulo (SP)" in rendered
    assert "Taxa de aumento" in rendered


def test_report_pdf_service_builds_valid_pdf():
    pdf_bytes = ReportPdfService().build(_sample_payload())

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_report_pdf_monthly_bars_preserve_all_points():
    payload = _sample_payload()
    payload.charts[1].data = [
        {"label": f"{month:02d}/2025", "casos": month * 3}
        for month in range(1, 13)
    ]
    pdf_bytes = ReportPdfService().build(payload)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 800
