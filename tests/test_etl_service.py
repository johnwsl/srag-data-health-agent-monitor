import duckdb
import pytest

from app.config import ETL_COLUMNS, ETL_MISSING_VALUE
from app.services.etl_service import EtlService


@pytest.fixture
def etl_service(raw_data_dir, tmp_path) -> EtlService:
    return EtlService(
        raw_data_dir=raw_data_dir,
        duckdb_path=tmp_path / "test.duckdb",
        table_name="srag_notificacoes_test",
    )


def test_etl_run_merges_filters_fills_and_saves(etl_service):
    result = etl_service.run()

    assert result["files_merged"] == ["dataset_a.csv", "dataset_b.csv"]
    assert result["rows_before_filter"] == 5
    assert result["rows_after_filter"] == 3
    assert result["rows_saved"] == 3

    connection = duckdb.connect(str(etl_service.duckdb_path))
    try:
        saved = connection.execute(
            f'SELECT * FROM "{etl_service.table_name}" ORDER BY NU_NOTIFIC'
        ).fetchdf()
    finally:
        connection.close()

    assert list(saved.columns) == ETL_COLUMNS + ["ANO_NOTIFIC", "MES_NOTIFIC"]
    assert len(saved) == 3
    assert saved["NU_NOTIFIC"].tolist() == ["111", "444", "555"]

    row_111 = saved.loc[saved["NU_NOTIFIC"] == "111"].iloc[0]
    assert row_111["SG_UF_NOT"] == "SP"
    assert row_111["CLASSI_FIN"] == "1"
    assert row_111["EVOLUCAO"] == ETL_MISSING_VALUE
    assert row_111["UTI"] == "2"
    assert row_111["VACINA_COV"] == ETL_MISSING_VALUE
    assert row_111["VACINA"] == "2"
    assert row_111["ANO_NOTIFIC"] == 2019
    assert row_111["MES_NOTIFIC"] == 7

    row_444 = saved.loc[saved["NU_NOTIFIC"] == "444"].iloc[0]
    assert row_444["CLASSI_FIN"] == ETL_MISSING_VALUE
    assert row_444["UTI"] == ETL_MISSING_VALUE
    assert row_444["VACINA_COV"] == ETL_MISSING_VALUE
    assert row_444["ANO_NOTIFIC"] == 2021
    assert row_444["MES_NOTIFIC"] == 5


def test_etl_run_raises_when_no_csv_files(tmp_path):
    service = EtlService(raw_data_dir=tmp_path / "empty", duckdb_path=tmp_path / "test.duckdb")

    with pytest.raises(FileNotFoundError, match="Nenhum arquivo CSV encontrado"):
        service.run()


def test_etl_run_raises_when_required_columns_are_missing(tmp_path):
    dataset_dir = tmp_path / "raw_data"
    dataset_dir.mkdir()
    (dataset_dir / "invalid.csv").write_text(
        '"NU_NOTIFIC";"SG_UF_NOT"\n"1";"SP"\n',
        encoding="utf-8",
    )
    service = EtlService(raw_data_dir=dataset_dir, duckdb_path=tmp_path / "test.duckdb")

    with pytest.raises(ValueError, match="Colunas obrigatórias ausentes"):
        service.run()


def test_etl_filter_required_fields(etl_service, raw_data_dir):
    merged = etl_service._merge_datasets(sorted(raw_data_dir.glob("*.csv")))
    filtered = etl_service._filter_required_fields(merged)

    assert len(filtered) == 3
    assert filtered["NU_NOTIFIC"].tolist() == ["111", "444", "555"]


def test_etl_fill_missing_values(etl_service, raw_data_dir):
    merged = etl_service._merge_datasets(sorted(raw_data_dir.glob("*.csv")))
    filtered = etl_service._filter_required_fields(merged)
    selected = etl_service._select_columns(filtered)
    filled = etl_service._fill_missing_values(selected)

    row_111 = filled.loc[filled["NU_NOTIFIC"] == "111"].iloc[0]
    assert row_111["EVOLUCAO"] == ETL_MISSING_VALUE
    assert row_111["VACINA_COV"] == ETL_MISSING_VALUE
    assert row_111["CLASSI_FIN"] == "1"
