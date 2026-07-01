import httpx

from app.config import DATASET_URLS, HTTP_TIMEOUT_SECONDS, RAW_DATA_DIR
from app.models.dataset import DatasetDownloadResult, DatasetInfo


class DatasetService:
    def __init__(self, raw_data_dir=RAW_DATA_DIR, dataset_urls: list[dict[str, str]] | None = None):
        self.raw_data_dir = raw_data_dir
        self.dataset_urls = dataset_urls or DATASET_URLS

    def _ensure_raw_data_dir(self) -> None:
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)

    async def download_dataset(self, client: httpx.AsyncClient, dataset: DatasetInfo) -> DatasetDownloadResult:
        destination = self.raw_data_dir / dataset.name

        try:
            response = await client.get(dataset.url, follow_redirects=True)
            response.raise_for_status()

            destination.write_bytes(response.content)
            size_bytes = destination.stat().st_size

            return DatasetDownloadResult(
                name=dataset.name,
                url=dataset.url,
                path=str(destination),
                size_bytes=size_bytes,
                success=True,
            )
        except httpx.HTTPError as exc:
            return DatasetDownloadResult(
                name=dataset.name,
                url=dataset.url,
                path=str(destination),
                size_bytes=0,
                success=False,
                error=str(exc),
            )

    async def download_all_datasets(self) -> list[DatasetDownloadResult]:
        self._ensure_raw_data_dir()
        datasets = [DatasetInfo(**item) for item in self.dataset_urls]
        results: list[DatasetDownloadResult] = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(HTTP_TIMEOUT_SECONDS)) as client:
            for dataset in datasets:
                result = await self.download_dataset(client, dataset)
                results.append(result)

        return results
