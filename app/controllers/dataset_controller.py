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

        skipped = sum(1 for result in results if result.skipped)

        if failed == 0:
            if skipped == len(results):
                message = "Todos os datasets já estavam presentes; nenhum download foi necessário."
            elif skipped > 0:
                message = "Download concluído; alguns datasets já estavam presentes."
            else:
                message = "Todos os datasets foram baixados com sucesso."
        else:
            message = "Download concluído com falhas parciais."

        return DatasetsDownloadResponse(
            message=message,
            total=len(results),
            successful=successful,
            failed=failed,
            datasets=results,
        )
