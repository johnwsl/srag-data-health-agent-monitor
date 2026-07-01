from fastapi import HTTPException, status

from app.models.dataset import DatasetsDownloadResponse
from app.services.dataset_service import DatasetService


class DatasetController:
    def __init__(self, dataset_service: DatasetService | None = None):
        self.dataset_service = dataset_service or DatasetService()

    async def download_datasets(self) -> DatasetsDownloadResponse:
        results = await self.dataset_service.download_all_datasets()
        successful = sum(1 for result in results if result.success)
        failed = len(results) - successful

        if failed == len(results):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "message": "Falha ao baixar todos os datasets.",
                    "datasets": [result.model_dump() for result in results],
                },
            )

        message = (
            "Todos os datasets foram baixados com sucesso."
            if failed == 0
            else "Download concluído com falhas parciais."
        )

        return DatasetsDownloadResponse(
            message=message,
            total=len(results),
            successful=successful,
            failed=failed,
            datasets=results,
        )
