from pydantic import BaseModel

from app.models.dataset import DatasetsDownloadResponse
from app.models.etl import EtlResponse


class PipelineResponse(BaseModel):
    message: str
    download: DatasetsDownloadResponse
    etl: EtlResponse


class PipelineStatusResponse(BaseModel):
    ready: bool
    message: str
    row_count: int = 0
