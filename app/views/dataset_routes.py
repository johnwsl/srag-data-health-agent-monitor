from fastapi import APIRouter

from app.controllers.dataset_controller import DatasetController
from app.models.dataset import DatasetsDownloadResponse

router = APIRouter(prefix="/datasets", tags=["datasets"])
controller = DatasetController()


@router.post("/download", response_model=DatasetsDownloadResponse)
async def download_datasets() -> DatasetsDownloadResponse:
    return await controller.download_datasets()
