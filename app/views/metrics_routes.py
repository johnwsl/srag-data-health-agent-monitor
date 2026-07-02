from fastapi import APIRouter

from app.controllers.metrics_controller import MetricsController
from app.models.metrics import (
    DailyCasesSeriesResponse,
    MonthlyCasesSeriesResponse,
    SRAGMetricsResponse,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])
controller = MetricsController()


@router.get("/{estado}/casos-diarios", response_model=DailyCasesSeriesResponse)
def get_daily_cases(estado: str) -> DailyCasesSeriesResponse:
    """Retorna a contagem diária de casos SRAG dos últimos 30 dias."""
    return controller.get_daily_cases(estado)


@router.get("/{estado}/casos-mensais", response_model=MonthlyCasesSeriesResponse)
def get_monthly_cases(estado: str) -> MonthlyCasesSeriesResponse:
    """Retorna a contagem mensal de casos SRAG dos últimos 12 meses."""
    return controller.get_monthly_cases(estado)


@router.get("/{estado}", response_model=SRAGMetricsResponse)
def get_metrics(estado: str) -> SRAGMetricsResponse:
    """Retorna as quatro métricas SRAG para uma UF ou para todo o Brasil.

    Informe a sigla de um estado (ex.: SP, RJ) ou BRASIL para o escopo nacional.
    """
    return controller.get_metrics(estado)
