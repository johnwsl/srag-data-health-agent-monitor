"""Testes de integracao da tool LangChain de ChartSpec (muta estado do servico)."""

from app.services.chart_spec_service import ChartSpecService


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
