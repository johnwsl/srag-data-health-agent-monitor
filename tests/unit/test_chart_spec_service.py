"""Testes unitarios de funcoes puras do ChartSpecService."""

from app.models.chart import REPORT_NOTIFICATION_DELAY_CAVEAT
from app.services.chart_spec_service import ChartSpecService


def test_from_metrics_payload_builds_daily_and_monthly_charts():
    payload = {
        "sg_uf_not": "RJ",
        "casos_diarios": {
            "sg_uf_not": "RJ",
            "pontos": [{"data": "2026-07-01", "total_casos": 3}],
        },
        "casos_mensais": {
            "sg_uf_not": "RJ",
            "pontos": [{"ano": 2026, "mes": 6, "total_casos": 40}],
        },
    }

    charts = ChartSpecService().from_metrics_payload(payload)

    assert [chart.id for chart in charts] == ["casos_diarios", "casos_mensais"]
    assert charts[0].type == "line"
    assert charts[0].data == [{"data": "2026-07-01", "casos": 3}]
    assert charts[0].source == "GET /metrics/RJ/casos-diarios"
    assert charts[0].caveat == REPORT_NOTIFICATION_DELAY_CAVEAT
    assert charts[1].type == "bar"
    assert charts[1].data == [{"label": "06/2026", "casos": 40}]
    assert charts[1].source == "GET /metrics/RJ/casos-mensais"


def test_from_metrics_payload_returns_empty_when_series_missing():
    charts = ChartSpecService().from_metrics_payload({"sg_uf_not": "SP", "metricas": {}})
    assert charts == []
