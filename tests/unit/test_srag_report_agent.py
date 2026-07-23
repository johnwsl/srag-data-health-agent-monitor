from unittest.mock import MagicMock

from app.services.agent_audit_service import AgentAuditService
from app.services.chart_spec_service import ChartSpecService
from app.services.langgraph_orchestrator_agent import LangGraphOrchestratorAgent
from app.services.srag_report_agent import SragReportAgent


class FakeMetricsService:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.ensure_calls = 0
        self.metrics_calls: list[str] = []
        self.pipeline_status = {
            "ready": True,
            "message": "Dados SRAG disponíveis para consulta.",
            "row_count": 10,
        }

    def ensure_pipeline_ready(self):
        self.ensure_calls += 1
        return self.pipeline_status

    def get_full_metrics_data(self, estado: str) -> dict:
        self.metrics_calls.append(estado)
        return self.payload


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


def test_generate_executive_summary_composes_report_with_llm():
    metrics_service = FakeMetricsService(SAMPLE_METRICS_PAYLOAD)
    llm = MagicMock()
    llm.ask.return_value = "Resumo executivo.\nDados oficiais: ...\nNoticias: ..."
    news = MagicMock()
    news.buscar_noticias.return_value = "Sem eventos criticos."
    orchestrator = LangGraphOrchestratorAgent(
        llm_service=llm,
        metrics_service=metrics_service,
        news_service=news,
        chart_spec_service=ChartSpecService(),
        graph=MagicMock(),
        audit_service=AgentAuditService(enabled=False),
    )
    agent = SragReportAgent(orchestrator=orchestrator)

    response = agent.generate_executive_summary("sp")

    assert response["resumo_executivo"] == "Resumo executivo.\nDados oficiais: ...\nNoticias: ..."
    assert [chart.id for chart in response["charts"]] == ["casos_diarios", "casos_mensais"]
    assert metrics_service.ensure_calls == 1
    assert metrics_service.metrics_calls == ["SP"]
    llm.ask.assert_called_once()
    news.buscar_noticias.assert_called_once()


def test_generate_executive_summary_limits_output_to_4000_chars():
    llm = MagicMock()
    llm.ask.return_value = "A" * 4500
    news = MagicMock()
    news.buscar_noticias.return_value = "Noticias."
    metrics_service = FakeMetricsService(SAMPLE_METRICS_PAYLOAD)
    orchestrator = LangGraphOrchestratorAgent(
        llm_service=llm,
        metrics_service=metrics_service,
        news_service=news,
        chart_spec_service=ChartSpecService(),
        graph=MagicMock(),
        audit_service=AgentAuditService(enabled=False),
    )

    response = SragReportAgent(orchestrator=orchestrator).generate_executive_summary("BRASIL")

    assert len(response["resumo_executivo"]) <= 4000
    assert response["resumo_executivo"].endswith("...")
    assert len(response["charts"]) == 2


def test_generate_executive_summary_includes_charts_from_metrics():
    llm = MagicMock()
    llm.ask.return_value = "Resumo sem chamada explicita de grafico."
    news = MagicMock()
    news.buscar_noticias.return_value = "Noticias."
    metrics_service = FakeMetricsService(SAMPLE_METRICS_PAYLOAD)
    orchestrator = LangGraphOrchestratorAgent(
        llm_service=llm,
        metrics_service=metrics_service,
        news_service=news,
        chart_spec_service=ChartSpecService(),
        graph=MagicMock(),
        audit_service=AgentAuditService(enabled=False),
    )

    response = SragReportAgent(orchestrator=orchestrator).generate_executive_summary("SP")

    assert len(response["charts"]) == 2
    assert response["charts"][0].id == "casos_diarios"
    assert metrics_service.metrics_calls == ["SP"]


def test_generate_executive_summary_rejects_invalid_uf():
    orchestrator = LangGraphOrchestratorAgent(
        llm_service=MagicMock(),
        metrics_service=FakeMetricsService(SAMPLE_METRICS_PAYLOAD),
        news_service=MagicMock(),
        chart_spec_service=ChartSpecService(),
        graph=MagicMock(),
        audit_service=AgentAuditService(enabled=False),
    )

    try:
        SragReportAgent(orchestrator=orchestrator).generate_executive_summary("XX")
        assert False, "deveria ter levantado ValueError"
    except ValueError as error:
        assert "UF invalida" in str(error)
