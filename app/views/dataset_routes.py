from fastapi import APIRouter

from app.controllers.dataset_controller import DatasetController
from app.models.dataset import DatasetsDownloadResponse

router = APIRouter(prefix="/datasets", tags=["datasets"])
controller = DatasetController()


@router.post("/download/datasets", response_model=DatasetsDownloadResponse)
async def download_datasets() -> DatasetsDownloadResponse:
    """Baixa os datasets SRAG do OpenDataSUS para a pasta raw_data.

    Ignora arquivos que já existem e não estão vazios. Retorna o status
    de cada download (sucesso, falha ou ignorado).
    """
    return await controller.download_datasets()
