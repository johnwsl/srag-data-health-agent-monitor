import json
import os
from typing import Any

import httpx
from pydantic import BaseModel, Field


class SragMetricsToolInput(BaseModel):
    estado: str = Field(
        description="Sigla da UF (ex.: SP, RJ) ou BRASIL para consultar metricas nacionais."
    )


class SragMetricsApiLangChainService:
    """Cliente HTTP da API SRAG com exposicao como tool LangChain."""

    def __init__(
        self,
        api_base_url: str | None = None,
        timeout_seconds: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.api_base_url = (api_base_url or os.getenv("API_BASE_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else float(os.getenv("HTTP_TIMEOUT_SECONDS", "300"))
        )
        self._client = client
        self._owns_client = client is None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=httpx.Timeout(self.timeout_seconds))
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "SragMetricsApiLangChainService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _request_json(self, path: str) -> dict[str, Any]:
        response = self._get_client().get(f"{self.api_base_url}{path}")
        if response.status_code == 422:
            payload = response.json()
            detail = payload.get("detail", "Erro ao consultar metricas SRAG.")
            raise ValueError(detail if isinstance(detail, str) else str(detail))
        response.raise_for_status()
        return response.json()

    def _post_json(self, path: str) -> dict[str, Any]:
        response = self._get_client().post(f"{self.api_base_url}{path}")
        response.raise_for_status()
        return response.json()

    def _normalize_estado(self, estado: str) -> str:
        return estado.strip().upper()

    def get_metrics(self, estado: str) -> dict[str, Any]:
        estado = self._normalize_estado(estado)
        return self._request_json(f"/metrics/{estado}")

    def get_dataset_status(self) -> dict[str, Any]:
        return self._request_json("/datasets/status")

    def run_pipeline(self) -> dict[str, Any]:
        return self._post_json("/datasets/pipeline")

    def ensure_pipeline_ready(self) -> dict[str, Any]:
        status_payload = self.get_dataset_status()
        if status_payload.get("ready") is True:
            return status_payload

        self.run_pipeline()
        status_payload = self.get_dataset_status()
        if status_payload.get("ready") is not True:
            raise RuntimeError("Pipeline SRAG nao ficou pronta apos a execucao automatica.")
        return status_payload

    def get_daily_cases(self, estado: str) -> dict[str, Any]:
        estado = self._normalize_estado(estado)
        return self._request_json(f"/metrics/{estado}/casos-diarios")

    def get_monthly_cases(self, estado: str) -> dict[str, Any]:
        estado = self._normalize_estado(estado)
        return self._request_json(f"/metrics/{estado}/casos-mensais")

    def get_full_metrics_data(self, estado: str) -> dict[str, Any]:
        estado = self._normalize_estado(estado)
        metrics = self.get_metrics(estado)
        daily_cases = self.get_daily_cases(estado)
        monthly_cases = self.get_monthly_cases(estado)

        return {
            "sg_uf_not": metrics.get("sg_uf_not", estado),
            "metricas": {
                "taxa_aumento_casos": metrics.get("taxa_aumento_casos"),
                "taxa_mortalidade": metrics.get("taxa_mortalidade"),
                "taxa_ocupacao_uti": metrics.get("taxa_ocupacao_uti"),
                "taxa_vacinacao_populacao": metrics.get("taxa_vacinacao_populacao"),
            },
            "casos_diarios": daily_cases,
            "casos_mensais": monthly_cases,
        }

    def consultar_metricas(self, estado: str) -> str:
        try:
            payload = self.get_full_metrics_data(estado)
        except ValueError as error:
            return f"Erro ao consultar metricas SRAG: {error}"
        except httpx.HTTPError as error:
            return f"Erro de comunicacao com a API SRAG: {error}"

        return json.dumps(payload, ensure_ascii=False, default=str)

    def as_tool(self):
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise ImportError(
                "Dependencia ausente. Instale 'langchain' para usar SragMetricsApiLangChainService.as_tool()."
            ) from exc

        return StructuredTool.from_function(
            func=self.consultar_metricas,
            name="consultar_metricas_srag",
            description=(
                "Consulta a API SRAG e retorna as quatro metricas principais "
                "(aumento de casos, mortalidade, ocupacao de UTI e vacinacao), "
                "alem das series de casos diarios dos ultimos 30 dias e casos mensais "
                "dos ultimos 12 meses para uma UF (estado do brasil - sg_uf_not) ou para BRASIL."
            ),
            args_schema=SragMetricsToolInput,
        )
