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


def test_as_tool_generates_and_remembers_chart_specs():
    class FakeMetrics:
        def get_daily_cases(self, estado: str) -> dict:
            return {"sg_uf_not": estado, "pontos": [{"data": "2026-07-01", "total_casos": 3}]}

        def get_monthly_cases(self, estado: str) -> dict:
            return {"sg_uf_not": estado, "pontos": [{"ano": 2026, "mes": 6, "total_casos": 40}]}

    service = ChartSpecService()
    tool = service.as_tool(FakeMetrics())

    assert tool.name == "gerar_especificacao_grafico"
    daily_json = tool.invoke({"estado": "rj", "serie": "diaria"})
    monthly_json = tool.invoke({"estado": "rj", "serie": "mensal"})

    assert '"id":"casos_diarios"' in daily_json.replace(" ", "")
    assert '"id":"casos_mensais"' in monthly_json.replace(" ", "")
    assert [chart.id for chart in service.generated_charts] == ["casos_diarios", "casos_mensais"]
