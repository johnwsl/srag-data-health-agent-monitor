from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.controllers.agent_controller import AgentController
from app.main import app
from app.models.chart import ChartAxisSpec, ChartSpec
from app.services.srag_report_agent import SragReportAgent
from app.views import agent_routes


@pytest.fixture
def mock_report_agent() -> MagicMock:
    agent = MagicMock(spec=SragReportAgent)
    agent.generate_executive_summary.return_value = {
        "resumo_executivo": (
            "Panorama geral.\nDados oficiais: taxa de aumento, mortalidade, UTI e vacinacao.\n"
            "Noticias: sem eventos criticos recentes."
        ),
        "charts": [
            ChartSpec(
                id="casos_diarios",
                type="line",
                title="Casos diários de SRAG — SP",
                x=ChartAxisSpec(field="data", label="Data"),
                y=ChartAxisSpec(field="casos", label="Notificações"),
                data=[{"data": "2026-06-01", "casos": 2}],
                source="GET /metrics/SP/casos-diarios",
                caveat="Períodos recentes podem estar incompletos.",
            )
        ],
    }
    return agent


@pytest.fixture
def client(mock_report_agent):
    agent_routes.controller = AgentController(report_agent=mock_report_agent)
    with TestClient(app) as test_client:
        yield test_client
    agent_routes.controller = AgentController(report_agent=mock_report_agent)


def test_generate_report_returns_summary(client, mock_report_agent):
    response = client.post("/agents/report", json={"estado": "sp"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["estado"] == "SP"
    assert "Dados oficiais" in payload["resumo_executivo"]
    assert len(payload["charts"]) == 1
    assert payload["charts"][0]["id"] == "casos_diarios"
    mock_report_agent.generate_executive_summary.assert_called_once_with("SP")


def test_generate_report_returns_422_for_invalid_state(client, mock_report_agent):
    mock_report_agent.generate_executive_summary.side_effect = ValueError("UF inválida: XX.")

    response = client.post("/agents/report", json={"estado": "XX"})

    assert response.status_code == 422
    assert "UF inválida" in response.json()["detail"]


def test_generate_report_returns_502_for_agent_failure(client, mock_report_agent):
    mock_report_agent.generate_executive_summary.side_effect = RuntimeError("OpenAI indisponivel")

    response = client.post("/agents/report", json={"estado": "SP"})

    assert response.status_code == 502
    assert "Falha ao gerar resumo executivo" in response.json()["detail"]
