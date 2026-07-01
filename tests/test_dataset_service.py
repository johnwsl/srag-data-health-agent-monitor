from unittest.mock import patch

import httpx
import pytest

from app.models.dataset import DatasetInfo
from app.services.dataset_service import DatasetService


@pytest.fixture
def dataset_service(tmp_path, dataset_urls) -> DatasetService:
    return DatasetService(raw_data_dir=tmp_path, dataset_urls=dataset_urls)


@pytest.mark.asyncio
async def test_download_dataset_saves_file(dataset_service, tmp_path):
    dataset = DatasetInfo(name="dataset_a.csv", url="http://testserver/dataset_a.csv")
    content = b"NU_NOTIFIC;DT_NOTIFIC\n1;2019-01-01"

    def handler(request):
        return httpx.Response(200, content=content)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await dataset_service.download_dataset(client, dataset)

    assert result.success is True
    assert result.skipped is False
    assert result.size_bytes == len(content)
    assert (tmp_path / "dataset_a.csv").read_bytes() == content


@pytest.mark.asyncio
async def test_download_dataset_skips_existing_file(dataset_service, tmp_path):
    destination = tmp_path / "dataset_a.csv"
    destination.write_bytes(b"already-downloaded")
    dataset = DatasetInfo(name="dataset_a.csv", url="http://testserver/dataset_a.csv")

    def handler(_request):
        raise AssertionError("Download should not be called when file already exists")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await dataset_service.download_dataset(client, dataset)

    assert result.success is True
    assert result.skipped is True
    assert result.size_bytes == len(b"already-downloaded")


@pytest.mark.asyncio
async def test_download_dataset_redownloads_empty_file(dataset_service, tmp_path):
    destination = tmp_path / "dataset_a.csv"
    destination.write_bytes(b"")
    dataset = DatasetInfo(name="dataset_a.csv", url="http://testserver/dataset_a.csv")
    content = b"fresh-content"

    transport = httpx.MockTransport(lambda _request: httpx.Response(200, content=content))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await dataset_service.download_dataset(client, dataset)

    assert result.success is True
    assert result.skipped is False
    assert (tmp_path / "dataset_a.csv").read_bytes() == content


@pytest.mark.asyncio
async def test_download_dataset_handles_http_error(dataset_service):
    dataset = DatasetInfo(name="dataset_a.csv", url="http://testserver/dataset_a.csv")

    transport = httpx.MockTransport(lambda _request: httpx.Response(503))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await dataset_service.download_dataset(client, dataset)

    assert result.success is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_download_all_datasets_downloads_only_missing_files(dataset_service, tmp_path, dataset_urls):
    (tmp_path / "dataset_b.csv").write_bytes(b"existing-b")

    def handler(request):
        if request.url.path.endswith("dataset_a.csv"):
            return httpx.Response(200, content=b"downloaded-a")
        raise AssertionError(f"Unexpected request: {request.url}")

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "__init__", patched_init):
        results = await dataset_service.download_all_datasets()

    assert len(results) == 2
    assert results[0].success is True
    assert results[0].skipped is False
    assert results[1].success is True
    assert results[1].skipped is True
    assert (tmp_path / "dataset_a.csv").read_bytes() == b"downloaded-a"


@pytest.mark.asyncio
async def test_download_all_datasets_skips_http_client_when_all_files_exist(dataset_service, tmp_path, dataset_urls):
    (tmp_path / "dataset_a.csv").write_bytes(b"a")
    (tmp_path / "dataset_b.csv").write_bytes(b"b")

    with patch("app.services.dataset_service.httpx.AsyncClient") as mock_client:
        results = await dataset_service.download_all_datasets()

    mock_client.assert_not_called()
    assert len(results) == 2
    assert all(result.skipped for result in results)
