from pydantic import BaseModel

from app.models.dataset import DatasetsDownloadResponse
from app.models.etl import EtlResponse


class PipelineResponse(BaseModel):
    message: str
    download: DatasetsDownloadResponse
    etl: EtlResponse
