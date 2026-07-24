from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.controllers.agent_controller import AgentController
from app.main import app
from app.models.chart import ChartAxisSpec, ChartSpec
from app.services.langgraph_orchestrator_agent import LangGraphOrchestratorAgent
from app.views import agent_routes


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    agent = MagicMock(spec=LangGraphOrchestratorAgent)
    agent.generate_executive_summary.return_value = {
        "resumo_executivo": (
            "Panorama geral.\nDados oficiais: taxa de aumento, mortalidade, UTI e vacinacao.\n"
            "Noticias: sem eventos criticos recentes."
        ),
        "charts": [
            ChartSpec(
                id="casos_diarios",
                type="line",
                title="Casos diários de SRAG (últimos 30 dias) — SP",
                x=ChartAxisSpec(field="data", label="Data"),
                y=ChartAxisSpec(field="casos", label="Notificações"),
                data=[{"data": "2026-06-01", "casos": 2}],
                source="GET /metrics/SP/casos-diarios",
                caveat="Períodos recentes podem estar incompletos.",
            )
        ],
        "tools_used": ["consultar_metricas_srag", "buscar_noticias_srag"],
        "audit_id": "audit-report-1",
    }
    agent.chat.return_value = {
        "session_id": "sess-123",
        "estado_contexto": "SP",
        "reply": "Resposta do chatbot com dados oficiais.",
        "charts": [
            ChartSpec(
                id="casos_mensais",
                type="bar",
                title="Casos mensais de SRAG (últimos 12 meses) — SP",
                x=ChartAxisSpec(field="label", label="Mês"),
                y=ChartAxisSpec(field="casos", label="Notificações"),
                data=[{"label": "06/2026", "casos": 10}],
                source="GET /metrics/SP/casos-mensais",
            )
        ],
        "tools_used": ["consultar_metricas_srag", "gerar_especificacao_grafico"],
        "report": None,
        "audit_id": "audit-chat-1",
    }
    return agent


@pytest.fixture
def client(mock_orchestrator, tmp_path):
    from app.services.agent_audit_service import AgentAuditService

    audit = AgentAuditService(duckdb_path=tmp_path / "audit.duckdb", enabled=True)
    agent_routes.controller = AgentController(
        orchestrator=mock_orchestrator,
        audit_service=audit,
    )
    with TestClient(app) as test_client:
        yield test_client
    agent_routes.controller = AgentController()


def test_generate_report_returns_summary(client, mock_orchestrator):
    response = client.post("/agents/report", json={"estado": "sp"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["estado"] == "SP"
    assert "Dados oficiais" in payload["resumo_executivo"]
    assert len(payload["charts"]) == 1
    assert payload["charts"][0]["id"] == "casos_diarios"
    assert payload["audit_id"] == "audit-report-1"
    mock_orchestrator.generate_executive_summary.assert_called_once_with("SP")


def test_export_report_pdf_returns_pdf_bytes(client):
    response = client.post(
        "/agents/report/pdf",
        json={
            "estado": "SP",
            "resumo_executivo": (
                "Escopo SP.\n\n"
                "## Quatro métricas principais\n\n"
                "| Métrica | Valor | Detalhe |\n"
                "| --- | --- | --- |\n"
                "| Taxa de mortalidade | 5,00% | 9 óbitos / 180 casos |\n\n"
                "## Notícias encontradas\n\n"
                "1. [SRAG no Brasil](https://www.gov.br/saude/srag)\n"
                "   Link: https://www.gov.br/saude/srag\n"
            ),
            "charts": [
                {
                    "id": "casos_diarios",
                    "type": "line",
                    "title": "Casos diários — SP",
                    "x": {"field": "data", "label": "Data"},
                    "y": {"field": "casos", "label": "Casos"},
                    "data": [
                        {"data": "2026-06-01", "casos": 2},
                        {"data": "2026-06-02", "casos": 3},
                    ],
                    "source": "GET /metrics/SP/casos-diarios",
                    "caveat": "Atraso de notificação possível.",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "relatorio_srag_SP.pdf" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 500


def test_export_report_pdf_requires_resumo(client):
    response = client.post(
        "/agents/report/pdf",
        json={"estado": "SP", "resumo_executivo": "   ", "charts": []},
    )

    assert response.status_code == 422
    assert "resumo_executivo" in response.json()["detail"]


def test_generate_report_returns_422_for_invalid_state(client, mock_orchestrator):
    mock_orchestrator.generate_executive_summary.side_effect = ValueError("UF inválida: XX.")

    response = client.post("/agents/report", json={"estado": "XX"})

    assert response.status_code == 422
    assert "UF inválida" in response.json()["detail"]


def test_generate_report_returns_502_for_agent_failure(client, mock_orchestrator):
    mock_orchestrator.generate_executive_summary.side_effect = RuntimeError("OpenAI indisponivel")

    response = client.post("/agents/report", json={"estado": "SP"})

    assert response.status_code == 502
    assert "Falha ao gerar resumo executivo" in response.json()["detail"]


def test_chat_returns_reply_and_charts(client, mock_orchestrator):
    response = client.post(
        "/agents/chat",
        json={
            "message": "Mostre a tendencia mensal",
            "session_id": "sess-123",
            "estado_contexto": "sp",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "sess-123"
    assert payload["estado_contexto"] == "SP"
    assert "dados oficiais" in payload["reply"].lower()
    assert payload["tools_used"] == ["consultar_metricas_srag", "gerar_especificacao_grafico"]
    assert payload["charts"][0]["id"] == "casos_mensais"
    assert payload["report"] is None
    assert payload["audit_id"] == "audit-chat-1"
    mock_orchestrator.chat.assert_called_once_with(
        "Mostre a tendencia mensal",
        session_id="sess-123",
        estado_contexto="sp",
    )


def test_list_audit_events(client, tmp_path):
    from app.services.agent_audit_service import AgentAuditService

    audit = AgentAuditService(duckdb_path=tmp_path / "audit-routes.duckdb", enabled=True)
    audit.record(
        kind="chat",
        session_id="sess-audit",
        estado_contexto="BRASIL",
        user_message="Oi",
        reply="Ola",
        tools_used=["consultar_metricas_srag"],
        tool_events=[{"name": "consultar_metricas_srag", "args": {"estado": "BRASIL"}, "result": "{}"}],
        duration_ms=5.0,
    )
    agent_routes.controller = AgentController(
        orchestrator=MagicMock(spec=LangGraphOrchestratorAgent),
        audit_service=audit,
    )

    response = client.get("/agents/audit?limit=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["session_id"] == "sess-audit"

    by_session = client.get("/agents/audit/session/sess-audit")
    assert by_session.status_code == 200
    assert by_session.json()["total"] == 1

    audit_id = payload["items"][0]["audit_id"]
    by_id = client.get(f"/agents/audit/{audit_id}")
    assert by_id.status_code == 200
    assert by_id.json()["audit_id"] == audit_id


def test_get_audit_event_returns_404(client, tmp_path):
    from app.services.agent_audit_service import AgentAuditService

    audit = AgentAuditService(duckdb_path=tmp_path / "audit-404.duckdb", enabled=True)
    agent_routes.controller = AgentController(
        orchestrator=MagicMock(spec=LangGraphOrchestratorAgent),
        audit_service=audit,
    )
    response = client.get("/agents/audit/nao-existe")
    assert response.status_code == 404


def test_chat_returns_report_payload_for_dashboard_section(client, mock_orchestrator):
    mock_orchestrator.chat.return_value = {
        "session_id": "sess-r",
        "estado_contexto": "SP",
        "reply": "Relatorio disponivel na secao Relatorio gerado por IA.",
        "charts": [],
        "tools_used": ["gerar_relatorio_executivo"],
        "report": {
            "estado": "SP",
            "resumo_executivo": "Resumo executivo de SP.",
            "charts": [
                ChartSpec(
                    id="casos_diarios",
                    type="line",
                    title="Casos diários — SP",
                    x=ChartAxisSpec(field="data", label="Data"),
                    y=ChartAxisSpec(field="casos", label="Notificações"),
                    data=[{"data": "2026-06-01", "casos": 2}],
                    source="GET /metrics/SP/casos-diarios",
                )
            ],
        },
    }

    response = client.post(
        "/agents/chat",
        json={"message": "Gere o relatorio de SP", "session_id": "sess-r"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["estado"] == "SP"
    assert "Resumo executivo" in payload["report"]["resumo_executivo"]
    assert payload["report"]["charts"][0]["id"] == "casos_diarios"
    assert payload["charts"] == []


def test_chat_returns_422_for_empty_message(client, mock_orchestrator):
    mock_orchestrator.chat.side_effect = ValueError("A mensagem do chat nao pode ser vazia.")

    response = client.post("/agents/chat", json={"message": "   ", "estado_contexto": "SP"})

    assert response.status_code == 422
    assert "vazia" in response.json()["detail"].lower()


def test_chat_returns_502_for_agent_failure(client, mock_orchestrator):
    mock_orchestrator.chat.side_effect = RuntimeError("LangGraph indisponivel")

    response = client.post("/agents/chat", json={"message": "Oi", "estado_contexto": "BRASIL"})

    assert response.status_code == 502
    assert "Falha no chatbot SRAG" in response.json()["detail"]
