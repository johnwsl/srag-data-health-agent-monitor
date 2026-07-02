from fastapi import APIRouter

from app.controllers.metrics_controller import MetricsController
from app.models.metrics import SRAGMetricsResponse

router = APIRouter(prefix="/metrics", tags=["metrics"])
controller = MetricsController()


@router.get("/{estado}", response_model=SRAGMetricsResponse)
def get_metrics(estado: str) -> SRAGMetricsResponse:
    """Retorna as quatro métricas SRAG para uma UF ou para todo o Brasil.

    Informe a sigla de um estado (ex.: SP, RJ) ou BRASIL para o escopo nacional.
    """
    return controller.get_metrics(estado)
