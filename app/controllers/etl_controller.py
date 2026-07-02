from fastapi import HTTPException, status

from app.models.etl import EtlResponse
from app.models.pipeline import PipelineStatusResponse
from app.services.etl_service import EtlService


class EtlController:
    def __init__(self, etl_service: EtlService | None = None):
        self.etl_service = etl_service or EtlService()

    def get_status(self) -> PipelineStatusResponse:
        status = self.etl_service.get_status()
        return PipelineStatusResponse(**status)

    def run_etl(self) -> EtlResponse:
        try:
            result = self.etl_service.run()
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Falha ao executar o ETL: {exc}",
            ) from exc

        return EtlResponse(
            message="ETL concluído com sucesso.",
            files_merged=result["files_merged"],
            rows_before_filter=result["rows_before_filter"],
            rows_after_filter=result["rows_after_filter"],
            rows_saved=result["rows_saved"],
            table_name=result["table_name"],
            database_path=result["database_path"],
        )
