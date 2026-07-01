from pydantic import BaseModel, Field


class DatasetInfo(BaseModel):
    name: str
    url: str


class DatasetDownloadResult(BaseModel):
    name: str
    url: str
    path: str
    size_bytes: int
    success: bool
    error: str | None = None


class DatasetsDownloadResponse(BaseModel):
    message: str
    total: int
    successful: int
    failed: int
    datasets: list[DatasetDownloadResult] = Field(default_factory=list)
