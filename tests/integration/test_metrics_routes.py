from fastapi.testclient import TestClient

from app.controllers.metrics_controller import MetricsController
from app.main import app
from app.services.srag_metrics import SRAGMetrics
from app.views import metrics_routes


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
