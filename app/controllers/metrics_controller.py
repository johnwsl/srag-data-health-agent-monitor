from fastapi import HTTPException, status

from app.models.metrics import (
    DailyCasesSeriesResponse,
    MonthlyCasesSeriesResponse,
    SRAGMetricsResponse,
)
from app.services.srag_metrics import SRAGMetrics


class MetricsController:
    def __init__(self, srag_metrics: SRAGMetrics | None = None):
        self.srag_metrics = srag_metrics or SRAGMetrics()

    def get_metrics(self, estado: str) -> SRAGMetricsResponse:
        estado = estado.upper()
        try:
            taxa_aumento_casos = self.srag_metrics.taxa_aumento_casos(estado=estado)
            taxa_mortalidade = self.srag_metrics.taxa_mortalidade(estado=estado)
            taxa_ocupacao_uti = self.srag_metrics.taxa_ocupacao_uti(estado=estado)
            taxa_vacinacao_populacao = self.srag_metrics.taxa_vacinacao_populacao(estado=estado)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error

        return SRAGMetricsResponse(
            sg_uf_not=taxa_aumento_casos.sg_uf_not,
            taxa_aumento_casos=taxa_aumento_casos,
            taxa_mortalidade=taxa_mortalidade,
            taxa_ocupacao_uti=taxa_ocupacao_uti,
            taxa_vacinacao_populacao=taxa_vacinacao_populacao,
        )

    def get_daily_cases(self, estado: str) -> DailyCasesSeriesResponse:
        estado = estado.upper()
        try:
            return self.srag_metrics.casos_ultimos_30_dias(estado=estado)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error

    def get_monthly_cases(self, estado: str) -> MonthlyCasesSeriesResponse:
        estado = estado.upper()
        try:
            return self.srag_metrics.casos_ultimos_12_meses(estado=estado)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
