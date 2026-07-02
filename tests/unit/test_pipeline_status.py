from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest
from fastapi.testclient import TestClient

from app.controllers.etl_controller import EtlController
from app.main import app
from app.services.etl_service import EtlService
from app.views import pipeline_routes


@pytest.fixture
def empty_raw_data(tmp_path: Path) -> Path:
    raw_data = tmp_path / "raw_data"
    raw_data.mkdir()
    return raw_data


def test_get_status_when_database_is_missing(empty_raw_data: Path, tmp_path: Path):
    service = EtlService(
        raw_data_dir=empty_raw_data,
        duckdb_path=tmp_path / "missing.duckdb",
    )

    status = service.get_status()

    assert status["ready"] is False
    assert status["row_count"] == 0
    assert "não encontrado" in status["message"].lower()


def test_get_status_when_table_has_rows(empty_raw_data: Path, tmp_path: Path):
    duckdb_path = tmp_path / "srag.duckdb"
    connection = duckdb.connect(str(duckdb_path))
    try:
        connection.execute('CREATE TABLE srag_notificacoes (id INTEGER)')
        connection.execute("INSERT INTO srag_notificacoes VALUES (1), (2), (3)")
    finally:
        connection.close()

    service = EtlService(
        raw_data_dir=empty_raw_data,
        duckdb_path=duckdb_path,
        table_name="srag_notificacoes",
    )

    status = service.get_status()

    assert status["ready"] is True
    assert status["row_count"] == 3


def test_get_pipeline_status_route(mock_etl_service: MagicMock):
    mock_etl_service.get_status.return_value = {
        "ready": True,
        "message": "Dados SRAG disponíveis para consulta.",
        "row_count": 10,
    }
    pipeline_routes.status_controller = EtlController(etl_service=mock_etl_service)

    with TestClient(app) as client:
        response = client.get("/datasets/status")

    pipeline_routes.status_controller = EtlController()

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["row_count"] == 10


@pytest.fixture
def mock_etl_service() -> MagicMock:
    return MagicMock(spec=EtlService)
