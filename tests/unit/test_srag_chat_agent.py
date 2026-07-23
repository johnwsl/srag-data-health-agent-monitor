from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.chart import ChartAxisSpec, ChartSpec
from app.services.chart_spec_service import ChartSpecService
from app.services.srag_chat_agent import SragChatAgent
from app.services.langgraph_orchestrator_agent import LangGraphOrchestratorAgent


class FakeMetricsService:
    def __init__(self) -> None:
        self.ensure_calls = 0
        self.pipeline_status = {"ready": True, "message": "ok", "row_count": 1}

    def ensure_pipeline_ready(self):
        self.ensure_calls += 1
        return self.pipeline_status

    def get_full_metrics_data(self, estado: str) -> dict:
        return {
            "sg_uf_not": estado,
            "casos_diarios": {"pontos": []},
            "casos_mensais": {"pontos": []},
        }


def test_chat_agent_invokes_langgraph_and_returns_charts():
    chart_service = ChartSpecService()
    fake_graph = MagicMock()

    def _invoke(payload, config=None):
        chart_service.generated_charts = [
            ChartSpec(
                id="casos_diarios",
                type="line",
                title="Casos diários — SP",
                x=ChartAxisSpec(field="data", label="Data"),
                y=ChartAxisSpec(field="casos", label="Notificações"),
                data=[{"data": "2026-06-01", "casos": 2}],
                source="GET /metrics/SP/casos-diarios",
            )
        ]
        return {
            "messages": [
                SimpleNamespace(
                    type="ai",
                    content="",
                    tool_calls=[
                        {"name": "consultar_metricas_srag", "args": {"estado": "SP"}, "id": "1"}
                    ],
                ),
                SimpleNamespace(type="tool", content="{}", tool_calls=[]),
                SimpleNamespace(
                    type="ai",
                    content="Em SP a tendencia recente precisa considerar atraso de notificacao.",
                    tool_calls=[],
                ),
            ]
        }

    fake_graph.invoke.side_effect = _invoke
    metrics_service = FakeMetricsService()
    orchestrator = LangGraphOrchestratorAgent(
        llm_service=MagicMock(),
        metrics_service=metrics_service,
        news_service=MagicMock(),
        chart_spec_service=chart_service,
        graph=fake_graph,
    )
    agent = SragChatAgent(orchestrator=orchestrator)

    result = agent.chat("Como esta a SRAG em SP?", session_id="sess-1", estado_contexto="sp")

    assert result["session_id"] == "sess-1"
    assert result["estado_contexto"] == "SP"
    assert result["report"] is None
    assert "atraso" in result["reply"].lower()
    assert result["tools_used"] == ["consultar_metricas_srag"]
    assert len(result["charts"]) == 1
    assert result["charts"][0].id == "casos_diarios"
    assert metrics_service.ensure_calls == 1

    invoke_args = fake_graph.invoke.call_args
    assert invoke_args.kwargs["config"]["configurable"]["thread_id"] == "sess-1"
    content = invoke_args.args[0]["messages"][0]["content"]
    assert "[Contexto geografico inicial: SP]" in content
    assert "Como esta a SRAG em SP?" in content


def test_tools_used_only_counts_current_turn():
    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {
        "messages": [
            SimpleNamespace(type="human", content="Gere o relatorio", tool_calls=[]),
            SimpleNamespace(
                type="ai",
                content="",
                tool_calls=[{"name": "gerar_relatorio_executivo", "args": {"estado": "BRASIL"}, "id": "1"}],
            ),
            SimpleNamespace(type="tool", content="ok", tool_calls=[]),
            SimpleNamespace(type="ai", content="Relatorio pronto.", tool_calls=[]),
            SimpleNamespace(type="human", content="Qual a mortalidade?", tool_calls=[]),
            SimpleNamespace(
                type="ai",
                content="",
                tool_calls=[{"name": "consultar_metricas_srag", "args": {"estado": "BRASIL"}, "id": "2"}],
            ),
            SimpleNamespace(type="tool", content="{}", tool_calls=[]),
            SimpleNamespace(
                type="ai",
                content="A taxa de mortalidade e X.",
                tool_calls=[],
            ),
        ]
    }
    orchestrator = LangGraphOrchestratorAgent(
        llm_service=MagicMock(),
        metrics_service=FakeMetricsService(),
        news_service=MagicMock(),
        chart_spec_service=ChartSpecService(),
        graph=fake_graph,
    )

    result = orchestrator.chat("Qual a mortalidade?", session_id="sess-turn")

    assert result["tools_used"] == ["consultar_metricas_srag"]
    assert result["report"] is None
    assert "mortalidade" in result["reply"].lower()


def test_chat_agent_rejects_empty_message():
    agent = SragChatAgent(
        orchestrator=LangGraphOrchestratorAgent(
            llm_service=MagicMock(),
            metrics_service=FakeMetricsService(),
            news_service=MagicMock(),
            chart_spec_service=ChartSpecService(),
            graph=MagicMock(),
        )
    )

    try:
        agent.chat("   ")
        assert False, "deveria ter levantado ValueError"
    except ValueError as error:
        assert "vazia" in str(error).lower()


def test_chat_agent_creates_session_id_when_missing():
    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {
        "messages": [SimpleNamespace(type="ai", content="Resposta", tool_calls=[])]
    }
    agent = SragChatAgent(
        orchestrator=LangGraphOrchestratorAgent(
            llm_service=MagicMock(),
            metrics_service=FakeMetricsService(),
            news_service=MagicMock(),
            chart_spec_service=ChartSpecService(),
            graph=fake_graph,
        )
    )

    result = agent.chat("Olá", estado_contexto="BRASIL")

    assert result["session_id"]
    assert len(result["session_id"]) >= 8
    assert result["report"] is None


def test_chat_with_report_tool_exposes_report_not_in_chat_charts():
    chart_service = ChartSpecService()
    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {
        "messages": [
            SimpleNamespace(
                type="ai",
                content="",
                tool_calls=[{"name": "gerar_relatorio_executivo", "args": {"estado": "SP"}, "id": "1"}],
            ),
            SimpleNamespace(
                type="ai",
                content="Relatorio gerado. Veja a secao Relatorio gerado por IA.",
                tool_calls=[],
            ),
        ]
    }

    llm = MagicMock()
    llm.ask.return_value = "Resumo executivo SP.\nDados oficiais: ok.\nNoticias: ok."
    news = MagicMock()
    news.buscar_noticias.return_value = "Sem noticias criticas."
    metrics = FakeMetricsService()
    metrics.get_full_metrics_data = MagicMock(
        return_value={
            "sg_uf_not": "SP",
            "casos_diarios": {
                "sg_uf_not": "SP",
                "pontos": [{"data": "2026-06-01", "total_casos": 2}],
            },
            "casos_mensais": {
                "sg_uf_not": "SP",
                "pontos": [{"ano": 2026, "mes": 6, "total_casos": 20}],
            },
        }
    )

    orchestrator = LangGraphOrchestratorAgent(
        llm_service=llm,
        metrics_service=metrics,
        news_service=news,
        chart_spec_service=chart_service,
        graph=fake_graph,
    )
    # Simula o efeito da tool no grafo: o checkpointer real chamaria a tool;
    # aqui definimos last_report como a tool faria.
    sample_report = {
        "estado": "SP",
        "resumo_executivo": "Resumo executivo SP.",
        "charts": chart_service.from_metrics_payload(metrics.get_full_metrics_data("SP")),
    }

    def _invoke(payload, config=None):
        orchestrator.last_report = sample_report
        return fake_graph.invoke.return_value

    fake_graph.invoke.side_effect = _invoke

    result = orchestrator.chat("Gere o relatorio de SP", session_id="sess-r1")

    assert result["report"] is not None
    assert result["report"]["estado"] == "SP"
    assert "Resumo" in result["report"]["resumo_executivo"]
    assert result["charts"] == []
    assert result["estado_contexto"] == "SP"
    assert "Relatorio gerado" in result["reply"]


def test_same_orchestrator_serves_report_and_chat():
    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {
        "messages": [SimpleNamespace(type="ai", content="ok", tool_calls=[])]
    }
    llm = MagicMock()
    llm.ask.return_value = "Resumo curto."
    news = MagicMock()
    news.buscar_noticias.return_value = "Noticias."
    metrics = FakeMetricsService()
    metrics.get_full_metrics_data = MagicMock(
        return_value={
            "sg_uf_not": "SP",
            "casos_diarios": {"pontos": []},
            "casos_mensais": {"pontos": []},
        }
    )
    orchestrator = LangGraphOrchestratorAgent(
        llm_service=llm,
        metrics_service=metrics,
        news_service=news,
        chart_spec_service=ChartSpecService(),
        graph=fake_graph,
    )

    report = orchestrator.generate_executive_summary("SP")
    chat = orchestrator.chat("Oi", session_id="s1", estado_contexto="SP")

    assert "resumo_executivo" in report
    assert chat["reply"] == "ok"
    assert chat["report"] is None
    assert fake_graph.invoke.call_count == 1
    llm.ask.assert_called_once()
