import json
from types import SimpleNamespace

from app.models.chart import ChartSpec
from app.services.chart_spec_service import ChartSpecService
from app.services.srag_report_agent import SragReportAgent


class FakeTool:
    def __init__(self, name: str, response: str | None = None, handler=None) -> None:
        self.name = name
        self.response = response
        self.handler = handler
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        if self.handler is not None:
            return self.handler(payload)
        return self.response


class FakeMetricsService:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.ensure_calls = 0
        self.metrics_calls: list[str] = []
        self.series_calls: list[dict] = []
        self.daily_calls: list[str] = []
        self.monthly_calls: list[str] = []
        self.pipeline_status = {
            "ready": True,
            "message": "Dados SRAG disponíveis para consulta.",
            "row_count": 10,
        }
        self.metrics_tool = FakeTool(
            "consultar_metricas_srag",
            handler=lambda args: json.dumps(self.get_full_metrics_data(args["estado"]), default=str),
        )
        self.series_tool = FakeTool(
            "consultar_serie_temporal",
            handler=lambda args: self.consultar_serie(args["estado"], args["serie"]),
        )

    def as_tool(self):
        return self.metrics_tool

    def as_series_tool(self):
        return self.series_tool

    def get_full_metrics_data(self, estado: str) -> dict:
        self.metrics_calls.append(estado)
        return self.payload

    def get_daily_cases(self, estado: str) -> dict:
        self.daily_calls.append(estado)
        return self.payload["casos_diarios"]

    def get_monthly_cases(self, estado: str) -> dict:
        self.monthly_calls.append(estado)
        return self.payload["casos_mensais"]

    def consultar_serie(self, estado: str, serie: str) -> str:
        self.series_calls.append({"estado": estado, "serie": serie})
        if serie == "diaria":
            payload = self.get_daily_cases(estado)
        else:
            payload = self.get_monthly_cases(estado)
        return json.dumps({"serie": serie, **payload}, default=str)

    def ensure_pipeline_ready(self):
        self.ensure_calls += 1
        return self.pipeline_status


class FakeNewsService:
    def __init__(self, response: str) -> None:
        self.tool = FakeTool("buscar_noticias_srag", response=response)

    def as_tool(self):
        return self.tool


class FakeLLMService:
    """Simula tool calling: na 1a rodada invoca as tools; na 2a devolve o texto final."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []

    def run_with_tools(self, *, system_prompt: str, user_prompt: str, tools, max_iterations: int = 8) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "tool_names": [tool.name for tool in tools],
                "max_iterations": max_iterations,
            }
        )
        tool_map = {tool.name: tool for tool in tools}
        estado = "SP"
        if "BRASIL" in user_prompt.upper():
            estado = "BRASIL"

        if "consultar_metricas_srag" in tool_map:
            tool_map["consultar_metricas_srag"].invoke({"estado": estado})
        if "gerar_especificacao_grafico" in tool_map:
            tool_map["gerar_especificacao_grafico"].invoke({"estado": estado, "serie": "diaria"})
            tool_map["gerar_especificacao_grafico"].invoke({"estado": estado, "serie": "mensal"})
        if "buscar_noticias_srag" in tool_map:
            tool_map["buscar_noticias_srag"].invoke({})

        return self.response


SAMPLE_METRICS_PAYLOAD = {
    "sg_uf_not": "SP",
    "metricas": {"taxa_aumento_casos": {"taxa_aumento_percentual": 100.0}},
    "casos_diarios": {
        "sg_uf_not": "SP",
        "pontos": [
            {"data": "2026-06-01", "total_casos": 2},
            {"data": "2026-06-02", "total_casos": 5},
        ],
    },
    "casos_mensais": {
        "sg_uf_not": "SP",
        "pontos": [
            {"ano": 2026, "mes": 5, "total_casos": 10},
            {"ano": 2026, "mes": 6, "total_casos": 20},
        ],
    },
}


def test_generate_executive_summary_uses_dynamic_tool_calling():
    metrics_service = FakeMetricsService(SAMPLE_METRICS_PAYLOAD)
    news_service = FakeNewsService("Noticias recentes sobre SRAG no Brasil:\n1. Titulo\n   URL: https://gov.br")
    llm_service = FakeLLMService("Resumo executivo.\nDados oficiais: ...\nNoticias: ...")
    chart_service = ChartSpecService()

    agent = SragReportAgent(
        llm_service=llm_service,
        metrics_service=metrics_service,
        news_service=news_service,
        chart_spec_service=chart_service,
    )

    response = agent.generate_executive_summary("sp")

    assert response["resumo_executivo"] == "Resumo executivo.\nDados oficiais: ...\nNoticias: ..."
    assert [chart.id for chart in response["charts"]] == ["casos_diarios", "casos_mensais"]
    assert all(isinstance(chart, ChartSpec) for chart in response["charts"])
    assert metrics_service.ensure_calls == 1
    assert metrics_service.metrics_tool.calls == [{"estado": "SP"}]
    assert metrics_service.daily_calls == ["SP"]
    assert metrics_service.monthly_calls == ["SP"]
    assert news_service.tool.calls == [{}]
    assert llm_service.calls[0]["tool_names"] == [
        "consultar_metricas_srag",
        "consultar_serie_temporal",
        "gerar_especificacao_grafico",
        "buscar_noticias_srag",
    ]
    assert "SP" in llm_service.calls[0]["user_prompt"]
    assert "Status da pipeline SRAG:" in llm_service.calls[0]["user_prompt"]
    assert "atraso" in llm_service.calls[0]["system_prompt"].lower()
    assert "gerar_especificacao_grafico" in llm_service.calls[0]["system_prompt"]


def test_generate_executive_summary_limits_output_to_4000_chars():
    long_text = "A" * 4500
    agent = SragReportAgent(
        llm_service=FakeLLMService(long_text),
        metrics_service=FakeMetricsService(SAMPLE_METRICS_PAYLOAD),
        news_service=FakeNewsService("Nenhuma noticia relevante sobre SRAG no Brasil foi encontrada."),
        chart_spec_service=ChartSpecService(),
    )

    response = agent.generate_executive_summary("BRASIL")

    assert len(response["resumo_executivo"]) <= 4000
    assert response["resumo_executivo"].endswith("...")
    assert len(response["charts"]) == 2


def test_generate_executive_summary_fallback_charts_when_graph_tool_not_used():
    class MetricsOnlyLLM(FakeLLMService):
        def run_with_tools(self, *, system_prompt, user_prompt, tools, max_iterations=8):
            self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
            tool_map = {tool.name: tool for tool in tools}
            tool_map["consultar_metricas_srag"].invoke({"estado": "SP"})
            tool_map["buscar_noticias_srag"].invoke({})
            return self.response

    metrics_service = FakeMetricsService(SAMPLE_METRICS_PAYLOAD)
    agent = SragReportAgent(
        llm_service=MetricsOnlyLLM("Resumo sem chamada explicita de grafico."),
        metrics_service=metrics_service,
        news_service=FakeNewsService("sem noticias"),
        chart_spec_service=ChartSpecService(),
    )

    response = agent.generate_executive_summary("SP")

    assert len(response["charts"]) == 2
    assert response["charts"][0].id == "casos_diarios"


def test_run_with_tools_loop_executes_tool_calls(monkeypatch):
    from app.services.openai_langchain_service import OpenAILangChainService

    class FakeBoundLLM:
        def __init__(self):
            self.calls = 0

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    content="",
                    tool_calls=[
                        {
                            "name": "consultar_metricas_srag",
                            "args": {"estado": "SP"},
                            "id": "call-1",
                        }
                    ],
                )
            return SimpleNamespace(content="texto final", tool_calls=[])

    class FakeClient:
        def __init__(self):
            self.bound = FakeBoundLLM()

        def bind_tools(self, tools):
            return self.bound

        def invoke(self, messages):
            return SimpleNamespace(content="unused")

    monkeypatch.setattr(
        OpenAILangChainService,
        "_build_client",
        lambda self: FakeClient(),
    )

    service = OpenAILangChainService(api_key="test-key")
    tool = FakeTool("consultar_metricas_srag", response='{"ok": true}')

    result = service.run_with_tools(
        system_prompt="sistema",
        user_prompt="humano",
        tools=[tool],
        max_iterations=3,
    )

    assert result == "texto final"
    assert tool.calls == [{"estado": "SP"}]
