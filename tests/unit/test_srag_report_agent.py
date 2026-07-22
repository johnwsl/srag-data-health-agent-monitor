import json

from app.services.srag_report_agent import SragReportAgent


class FakeTool:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        return self.response


class FakeMetricsService:
    def __init__(self, payload: dict | str) -> None:
        if isinstance(payload, str):
            self.payload = json.loads(payload)
            self.tool = FakeTool(payload)
        else:
            self.payload = payload
            self.tool = FakeTool(json.dumps(payload, ensure_ascii=False))
        self.ensure_calls = 0
        self.metrics_calls: list[str] = []
        self.pipeline_status = {
            "ready": True,
            "message": "Dados SRAG disponíveis para consulta.",
            "row_count": 10,
        }

    def as_tool(self):
        return self.tool

    def get_full_metrics_data(self, estado: str) -> dict:
        self.metrics_calls.append(estado)
        return self.payload

    def ensure_pipeline_ready(self):
        self.ensure_calls += 1
        return self.pipeline_status


class FakeNewsService:
    def __init__(self, response: str) -> None:
        self.tool = FakeTool(response)

    def as_tool(self):
        return self.tool


class FakeLLMService:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = []

    def ask(self, query: str, system_prompt: str | None = None) -> str:
        self.calls.append({"query": query, "system_prompt": system_prompt})
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


def test_generate_executive_summary_orchestrates_tools_and_llm():
    metrics_service = FakeMetricsService(SAMPLE_METRICS_PAYLOAD)
    news_service = FakeNewsService("Noticias recentes sobre SRAG no Brasil:\n1. Titulo\n   URL: https://gov.br")
    llm_service = FakeLLMService("Resumo executivo.\nDados oficiais: ...\nNoticias: ...")

    agent = SragReportAgent(
        llm_service=llm_service,
        metrics_service=metrics_service,
        news_service=news_service,
    )

    response = agent.generate_executive_summary("sp")

    assert response["resumo_executivo"] == "Resumo executivo.\nDados oficiais: ...\nNoticias: ..."
    assert len(response["charts"]) == 2
    assert response["charts"][0].id == "casos_diarios"
    assert response["charts"][1].id == "casos_mensais"
    assert metrics_service.ensure_calls == 1
    assert metrics_service.metrics_calls == ["sp"]
    assert news_service.tool.calls == [{}]
    assert "Estado consultado: SP" in llm_service.calls[0]["query"]
    assert "Status da pipeline SRAG:" in llm_service.calls[0]["query"]
    assert "Dados oficiais da API SRAG:" in llm_service.calls[0]["query"]
    assert "Noticias recentes coletadas:" in llm_service.calls[0]["query"]
    assert "Dados oficiais" in llm_service.calls[0]["system_prompt"]
    assert "Noticias" in llm_service.calls[0]["system_prompt"]
    assert "atraso" in llm_service.calls[0]["system_prompt"].lower()


def test_generate_executive_summary_limits_output_to_4000_chars():
    long_text = "A" * 4500
    agent = SragReportAgent(
        llm_service=FakeLLMService(long_text),
        metrics_service=FakeMetricsService(SAMPLE_METRICS_PAYLOAD),
        news_service=FakeNewsService("Nenhuma noticia relevante sobre SRAG no Brasil foi encontrada."),
    )

    response = agent.generate_executive_summary("BRASIL")

    assert len(response["resumo_executivo"]) <= 4000
    assert response["resumo_executivo"].endswith("...")
    assert len(response["charts"]) == 2
