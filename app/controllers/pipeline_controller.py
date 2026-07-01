from app.controllers.dataset_controller import DatasetController
from app.controllers.etl_controller import EtlController
from app.models.pipeline import PipelineResponse


class PipelineController:
    def __init__(
        self,
        dataset_controller: DatasetController | None = None,
        etl_controller: EtlController | None = None,
    ):
        self.dataset_controller = dataset_controller or DatasetController()
        self.etl_controller = etl_controller or EtlController()

    async def run_pipeline(self) -> PipelineResponse:
        download = await self.dataset_controller.download_datasets()
        etl = self.etl_controller.run_etl()

        if download.failed > 0:
            message = "Pipeline concluído com falhas parciais no download; ETL executado com os arquivos disponíveis."
        elif all(result.skipped for result in download.datasets):
            message = "Pipeline concluído: datasets já presentes e ETL executado com sucesso."
        else:
            message = "Pipeline concluído: download e ETL executados com sucesso."

        return PipelineResponse(
            message=message,
            download=download,
            etl=etl,
        )
