from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.chart import ChartAxisSpec, ChartSpec
from app.services.chart_spec_service import ChartSpecService
from app.services.srag_chat_agent import SragChatAgent


class FakeMetricsService:
    def __init__(self) -> None:
        self.ensure_calls = 0
        self.pipeline_status = {"ready": True, "message": "ok", "row_count": 1}

    def ensure_pipeline_ready(self):
        self.ensure_calls += 1
        return self.pipeline_status


class FakeNewsService:
    pass


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

    agent = SragChatAgent(
        llm_service=MagicMock(),
        metrics_service=FakeMetricsService(),
        news_service=FakeNewsService(),
        chart_spec_service=chart_service,
        graph=fake_graph,
    )

    result = agent.chat("Como esta a SRAG em SP?", session_id="sess-1", estado_contexto="sp")

    assert result["session_id"] == "sess-1"
    assert result["estado_contexto"] == "SP"
    assert "atraso" in result["reply"].lower()
    assert result["tools_used"] == ["consultar_metricas_srag"]
    assert len(result["charts"]) == 1
    assert result["charts"][0].id == "casos_diarios"
    assert agent.metrics_service.ensure_calls == 1

    invoke_args = fake_graph.invoke.call_args
    assert invoke_args.kwargs["config"]["configurable"]["thread_id"] == "sess-1"
    content = invoke_args.args[0]["messages"][0]["content"]
    assert "[Contexto geografico padrao: SP]" in content
    assert "Como esta a SRAG em SP?" in content


def test_chat_agent_rejects_empty_message():
    agent = SragChatAgent(
        llm_service=MagicMock(),
        metrics_service=FakeMetricsService(),
        news_service=FakeNewsService(),
        chart_spec_service=ChartSpecService(),
        graph=MagicMock(),
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
        llm_service=MagicMock(),
        metrics_service=FakeMetricsService(),
        news_service=FakeNewsService(),
        chart_spec_service=ChartSpecService(),
        graph=fake_graph,
    )

    result = agent.chat("Olá", estado_contexto="BRASIL")

    assert result["session_id"]
    assert len(result["session_id"]) >= 8
