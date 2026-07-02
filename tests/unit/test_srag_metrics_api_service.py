import json

import httpx
import pytest

from app.services.srag_metrics_api_service import SragMetricsApiLangChainService


def _metrics_payload(estado: str = "SP") -> dict:
    return {
        "sg_uf_not": estado,
        "taxa_aumento_casos": {
            "sg_uf_not": estado,
            "mes_atual_ano": 2026,
            "mes_atual_mes": 6,
            "mes_anterior_ano": 2026,
            "mes_anterior_mes": 5,
            "casos_mes_atual": 4,
            "casos_mes_anterior": 2,
            "taxa_aumento_percentual": 100.0,
        },
        "taxa_mortalidade": {
            "sg_uf_not": estado,
            "mes_atual_ano": 2026,
            "mes_atual_mes": 6,
            "mes_anterior_ano": 2026,
            "mes_anterior_mes": 5,
            "total_casos_2_meses": 7,
            "total_obitos_2_meses": 1,
            "taxa_mortalidade_percentual": 14.29,
        },
        "taxa_ocupacao_uti": {
            "sg_uf_not": estado,
            "mes_atual_ano": 2026,
            "mes_atual_mes": 6,
            "mes_anterior_ano": 2026,
            "mes_anterior_mes": 5,
            "total_casos_2_meses": 7,
            "casos_com_uti_2_meses": 2,
            "taxa_ocupacao_uti_percentual": 28.57,
        },
        "taxa_vacinacao_populacao": {
            "sg_uf_not": estado,
            "mes_atual_ano": 2026,
            "mes_atual_mes": 6,
            "mes_anterior_ano": 2026,
            "mes_anterior_mes": 5,
            "total_casos_2_meses": 7,
            "casos_vacinados_2_meses": 3,
            "taxa_vacinacao_percentual": 42.86,
        },
    }


def _daily_payload(estado: str = "SP") -> dict:
    return {
        "sg_uf_not": estado,
        "data_inicio": "2026-06-01",
        "data_fim": "2026-06-30",
        "pontos": [{"data": "2026-06-01", "total_casos": 1}],
    }


def _monthly_payload(estado: str = "SP") -> dict:
    return {
        "sg_uf_not": estado,
        "pontos": [{"ano": 2026, "mes": 6, "total_casos": 10}],
    }


def _build_mock_transport(estado: str = "SP"):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == f"/metrics/{estado}":
            return httpx.Response(200, json=_metrics_payload(estado))
        if path == f"/metrics/{estado}/casos-diarios":
            return httpx.Response(200, json=_daily_payload(estado))
        if path == f"/metrics/{estado}/casos-mensais":
            return httpx.Response(200, json=_monthly_payload(estado))

        raise AssertionError(f"Unexpected request: {request.url}")

    return httpx.MockTransport(handler)


def _build_invalid_state_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/metrics/XX":
            return httpx.Response(422, json={"detail": "UF invalida: XX. Use uma sigla valida ou BRASIL."})
        raise AssertionError(f"Unexpected request: {request.url}")

    return httpx.MockTransport(handler)


@pytest.fixture
def metrics_api_service() -> SragMetricsApiLangChainService:
    transport = _build_mock_transport("SP")
    client = httpx.Client(transport=transport, base_url="http://testserver")
    service = SragMetricsApiLangChainService(api_base_url="http://testserver", client=client)
    yield service
    service.close()


def test_get_full_metrics_data_aggregates_all_endpoints(metrics_api_service):
    payload = metrics_api_service.get_full_metrics_data("sp")

    assert payload["sg_uf_not"] == "SP"
    assert payload["metricas"]["taxa_aumento_casos"]["taxa_aumento_percentual"] == 100.0
    assert payload["metricas"]["taxa_mortalidade"]["total_obitos_2_meses"] == 1
    assert payload["metricas"]["taxa_ocupacao_uti"]["casos_com_uti_2_meses"] == 2
    assert payload["metricas"]["taxa_vacinacao_populacao"]["casos_vacinados_2_meses"] == 3
    assert payload["casos_diarios"]["pontos"][0]["total_casos"] == 1
    assert payload["casos_mensais"]["pontos"][0]["total_casos"] == 10


def test_consultar_metricas_returns_json_string(metrics_api_service):
    response = metrics_api_service.consultar_metricas("SP")
    payload = json.loads(response)

    assert payload["sg_uf_not"] == "SP"
    assert "metricas" in payload
    assert "casos_diarios" in payload
    assert "casos_mensais" in payload


def test_consultar_metricas_handles_invalid_state():
    client = httpx.Client(transport=_build_invalid_state_transport(), base_url="http://testserver")
    service = SragMetricsApiLangChainService(api_base_url="http://testserver", client=client)

    response = service.consultar_metricas("XX")

    service.close()
    assert "Erro ao consultar metricas SRAG" in response
    assert "UF invalida" in response


def test_as_tool_invokes_service(metrics_api_service):
    tool = metrics_api_service.as_tool()

    assert tool.name == "consultar_metricas_srag"
    response = tool.invoke({"estado": "SP"})
    payload = json.loads(response)

    assert payload["sg_uf_not"] == "SP"
    assert len(payload["metricas"]) == 4
