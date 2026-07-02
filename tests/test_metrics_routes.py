from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.controllers.metrics_controller import MetricsController
from app.main import app
from app.models.metrics import (
    CaseIncreaseRateMetric,
    CovidVaccinationRateMetric,
    MortalityRateMetric,
    UtiOccupancyRateMetric,
)
from app.services.srag_metrics import SRAGMetrics
from app.views import metrics_routes

pytest_plugins = ("tests.test_srag_metrics",)


@pytest.fixture
def sample_metrics() -> dict:
    return {
        "taxa_aumento_casos": CaseIncreaseRateMetric(
            sg_uf_not="SP",
            mes_atual_ano=2026,
            mes_atual_mes=6,
            mes_anterior_ano=2026,
            mes_anterior_mes=5,
            casos_mes_atual=4,
            casos_mes_anterior=2,
            taxa_aumento_percentual=100.0,
        ),
        "taxa_mortalidade": MortalityRateMetric(
            sg_uf_not="SP",
            mes_atual_ano=2026,
            mes_atual_mes=6,
            mes_anterior_ano=2026,
            mes_anterior_mes=5,
            total_casos_2_meses=7,
            total_obitos_2_meses=1,
            taxa_mortalidade_percentual=14.285714285714286,
        ),
        "taxa_ocupacao_uti": UtiOccupancyRateMetric(
            sg_uf_not="SP",
            mes_atual_ano=2026,
            mes_atual_mes=6,
            mes_anterior_ano=2026,
            mes_anterior_mes=5,
            total_casos_2_meses=7,
            casos_com_uti_2_meses=2,
            taxa_ocupacao_uti_percentual=28.571428571428573,
        ),
        "taxa_vacinacao_populacao": CovidVaccinationRateMetric(
            sg_uf_not="SP",
            mes_atual_ano=2026,
            mes_atual_mes=6,
            mes_anterior_ano=2026,
            mes_anterior_mes=5,
            total_casos_2_meses=7,
            casos_vacinados_2_meses=3,
            taxa_vacinacao_percentual=42.857142857142854,
        ),
    }


@pytest.fixture
def mock_srag_metrics(sample_metrics) -> MagicMock:
    metrics = MagicMock(spec=SRAGMetrics)
    metrics.taxa_aumento_casos.return_value = sample_metrics["taxa_aumento_casos"]
    metrics.taxa_mortalidade.return_value = sample_metrics["taxa_mortalidade"]
    metrics.taxa_ocupacao_uti.return_value = sample_metrics["taxa_ocupacao_uti"]
    metrics.taxa_vacinacao_populacao.return_value = sample_metrics["taxa_vacinacao_populacao"]
    return metrics


@pytest.fixture
def client(mock_srag_metrics):
    metrics_routes.controller = MetricsController(srag_metrics=mock_srag_metrics)
    with TestClient(app) as test_client:
        yield test_client
    metrics_routes.controller = MetricsController()


def test_get_metrics_for_state(client, mock_srag_metrics):
    response = client.get("/metrics/SP")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sg_uf_not"] == "SP"
    assert payload["taxa_aumento_casos"]["taxa_aumento_percentual"] == 100.0
    assert payload["taxa_mortalidade"]["total_obitos_2_meses"] == 1
    assert payload["taxa_ocupacao_uti"]["casos_com_uti_2_meses"] == 2
    assert payload["taxa_vacinacao_populacao"]["casos_vacinados_2_meses"] == 3
    mock_srag_metrics.taxa_aumento_casos.assert_called_once_with(estado="SP")
    mock_srag_metrics.taxa_mortalidade.assert_called_once_with(estado="SP")
    mock_srag_metrics.taxa_ocupacao_uti.assert_called_once_with(estado="SP")
    mock_srag_metrics.taxa_vacinacao_populacao.assert_called_once_with(estado="SP")


def test_get_metrics_for_brasil(client, mock_srag_metrics, sample_metrics):
    sample_metrics["taxa_aumento_casos"] = sample_metrics["taxa_aumento_casos"].model_copy(
        update={"sg_uf_not": "BRASIL"}
    )
    sample_metrics["taxa_mortalidade"] = sample_metrics["taxa_mortalidade"].model_copy(
        update={"sg_uf_not": "BRASIL"}
    )
    sample_metrics["taxa_ocupacao_uti"] = sample_metrics["taxa_ocupacao_uti"].model_copy(
        update={"sg_uf_not": "BRASIL"}
    )
    sample_metrics["taxa_vacinacao_populacao"] = sample_metrics["taxa_vacinacao_populacao"].model_copy(
        update={"sg_uf_not": "BRASIL"}
    )
    mock_srag_metrics.taxa_aumento_casos.return_value = sample_metrics["taxa_aumento_casos"]
    mock_srag_metrics.taxa_mortalidade.return_value = sample_metrics["taxa_mortalidade"]
    mock_srag_metrics.taxa_ocupacao_uti.return_value = sample_metrics["taxa_ocupacao_uti"]
    mock_srag_metrics.taxa_vacinacao_populacao.return_value = sample_metrics["taxa_vacinacao_populacao"]

    response = client.get("/metrics/BRASIL")

    assert response.status_code == 200
    assert response.json()["sg_uf_not"] == "BRASIL"
    mock_srag_metrics.taxa_aumento_casos.assert_called_once_with(estado="BRASIL")


def test_get_metrics_normalizes_state_to_uppercase(client, mock_srag_metrics):
    response = client.get("/metrics/sp")

    assert response.status_code == 200
    mock_srag_metrics.taxa_aumento_casos.assert_called_once_with(estado="SP")


def test_get_metrics_returns_422_for_invalid_state(client, mock_srag_metrics):
    mock_srag_metrics.taxa_aumento_casos.side_effect = ValueError("UF inválida: XX. Use uma sigla válida ou BRASIL.")

    response = client.get("/metrics/XX")

    assert response.status_code == 422
    assert "UF inválida" in response.json()["detail"]


def test_get_metrics_integration(metrics_db):
    metrics_routes.controller = MetricsController(
        srag_metrics=SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    )
    with TestClient(app) as test_client:
        response = test_client.get("/metrics/SP")

    metrics_routes.controller = MetricsController()

    assert response.status_code == 200
    payload = response.json()
    assert payload["sg_uf_not"] == "SP"
    assert payload["taxa_aumento_casos"]["casos_mes_atual"] == 4
    assert payload["taxa_mortalidade"]["total_casos_2_meses"] == 7
    assert payload["taxa_ocupacao_uti"]["total_casos_2_meses"] == 7
    assert payload["taxa_vacinacao_populacao"]["total_casos_2_meses"] == 7


def test_get_daily_cases_integration(metrics_db):
    metrics_routes.controller = MetricsController(
        srag_metrics=SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    )
    with TestClient(app) as test_client:
        response = test_client.get("/metrics/SP/casos-diarios")

    metrics_routes.controller = MetricsController()

    assert response.status_code == 200
    payload = response.json()
    assert payload["sg_uf_not"] == "SP"
    assert len(payload["pontos"]) == 30


def test_get_monthly_cases_integration(metrics_db):
    metrics_routes.controller = MetricsController(
        srag_metrics=SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
    )
    with TestClient(app) as test_client:
        response = test_client.get("/metrics/SP/casos-mensais")

    metrics_routes.controller = MetricsController()

    assert response.status_code == 200
    payload = response.json()
    assert payload["sg_uf_not"] == "SP"
    assert len(payload["pontos"]) == 12
