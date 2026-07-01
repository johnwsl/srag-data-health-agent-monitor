from fastapi import APIRouter

from app.controllers.pipeline_controller import PipelineController
from app.models.pipeline import PipelineResponse

router = APIRouter(prefix="/datasets", tags=["pipeline"])
controller = PipelineController()


@router.post("/pipeline", response_model=PipelineResponse)
async def run_pipeline() -> PipelineResponse:
    """Executa o fluxo completo: download dos datasets seguido do ETL.

    Primeiro baixa (ou reutiliza) os CSVs em raw_data; em seguida processa
    os dados e grava no DuckDB. Retorna o resumo das duas etapas.
    """
    return await controller.run_pipeline()
