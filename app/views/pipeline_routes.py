from fastapi import APIRouter

from app.controllers.etl_controller import EtlController
from app.controllers.pipeline_controller import PipelineController
from app.models.pipeline import PipelineResponse, PipelineStatusResponse

router = APIRouter(prefix="/datasets", tags=["pipeline"])
controller = PipelineController()
status_controller = EtlController()


@router.get("/status", response_model=PipelineStatusResponse)
def get_pipeline_status() -> PipelineStatusResponse:
    """Indica se o pipeline já foi executado e os dados estão disponíveis."""
    return status_controller.get_status()


@router.post("/pipeline", response_model=PipelineResponse)
async def run_pipeline() -> PipelineResponse:
    """Executa o fluxo completo: download dos datasets seguido do ETL.

    Primeiro baixa (ou reutiliza) os CSVs em raw_data; em seguida processa
    os dados e grava no DuckDB. Retorna o resumo das duas etapas.
    """
    return await controller.run_pipeline()
