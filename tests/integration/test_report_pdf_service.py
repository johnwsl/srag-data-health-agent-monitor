"""Testes de integracao do ReportPdfService (montagem de PDF com fontes/graficos)."""

from app.models.chart import ChartAxisSpec, ChartSpec
from app.models.chat import ChatReportPayload
from app.services.report_pdf_service import ReportPdfService

COMPOSED_RESUMO = (
    "**Resumo Executivo - Estado de São Paulo (SP)**\n\n"
    "Dados oficiais apontam redução moderada de casos.\n\n"
    "## Quatro métricas principais\n\n"
    "| Métrica | Valor | Detalhe |\n"
    "| --- | --- | --- |\n"
    "| Taxa de aumento de casos | -8,10% | 70 / 95 |\n\n"
    "## Notícias encontradas\n\n"
    "1. [SRAG](https://www.gov.br/saude/srag)\n"
)


def _sample_payload() -> ChatReportPayload:
    return ChatReportPayload(
        estado="SP",
        resumo_executivo=COMPOSED_RESUMO,
        charts=[
            ChartSpec(
                id="casos_diarios",
                type="line",
                title="Casos diários — SP",
                x=ChartAxisSpec(field="data", label="Data"),
                y=ChartAxisSpec(field="casos", label="Notificações"),
                data=[
                    {"data": "2026-06-01", "casos": 2},
                    {"data": "2026-06-02", "casos": 5},
                ],
                source="GET /metrics/SP/casos-diarios",
                caveat="Períodos recentes podem estar incompletos.",
            ),
            ChartSpec(
                id="casos_mensais",
                type="bar",
                title="Casos mensais — SP",
                x=ChartAxisSpec(field="label", label="Mês"),
                y=ChartAxisSpec(field="casos", label="Notificações"),
                data=[
                    {"label": "05/2026", "casos": 95},
                    {"label": "06/2026", "casos": 70},
                ],
                source="GET /metrics/SP/casos-mensais",
            ),
        ],
    )


def test_report_pdf_service_builds_valid_pdf():
    pdf_bytes = ReportPdfService().build(_sample_payload())

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 800


def test_report_pdf_monthly_bars_preserve_all_points():
    payload = _sample_payload()
    payload.charts[1].data = [
        {"label": f"{month:02d}/2025", "casos": month * 3}
        for month in range(1, 13)
    ]
    pdf_bytes = ReportPdfService().build(payload)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 800
