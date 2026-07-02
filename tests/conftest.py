import duckdb
import pytest

from app.config import ETL_COLUMNS
from app.services.srag_metrics import SRAGMetrics

SRAG_HEADER = ";".join(f'"{column}"' for column in ETL_COLUMNS)


@pytest.fixture
def sample_csv_rows() -> list[str]:
    return [
        f'{SRAG_HEADER}',
        '"111";"2019-07-22T00:00:00.000Z";"SP";"1";"";"2";"";"2"',
        '"";"2019-01-01T00:00:00.000Z";"RJ";"1";"1";"1";"1";"1"',
        '"333";"2020-03-15T00:00:00.000Z";"";"2";"2";"2";"2";"2"',
        '"444";"2021-05-10T00:00:00.000Z";"MG";"";"1";"";"";""',
    ]


@pytest.fixture
def raw_data_dir(tmp_path, sample_csv_rows):
    dataset_dir = tmp_path / "raw_data"
    dataset_dir.mkdir()
    (dataset_dir / "dataset_a.csv").write_text("\n".join(sample_csv_rows), encoding="utf-8")
    (dataset_dir / "dataset_b.csv").write_text(
        "\n".join(
            [
                SRAG_HEADER,
                '"555";"2022-11-30T00:00:00.000Z";"PR";"3";"2";"1";"1";"1"',
            ]
        ),
        encoding="utf-8",
    )
    return dataset_dir


@pytest.fixture
def dataset_urls() -> list[dict[str, str]]:
    return [
        {"name": "dataset_a.csv", "url": "http://testserver/dataset_a.csv"},
        {"name": "dataset_b.csv", "url": "http://testserver/dataset_b.csv"},
    ]


@pytest.fixture
def metrics_db(tmp_path):
    db_path = tmp_path / "metrics.duckdb"
    connection = duckdb.connect(str(db_path))
    connection.execute(
        """
        CREATE TABLE srag_notificacoes (
            NU_NOTIFIC VARCHAR,
            DT_NOTIFIC VARCHAR,
            SG_UF_NOT VARCHAR,
            CLASSI_FIN VARCHAR,
            EVOLUCAO VARCHAR,
            UTI VARCHAR,
            VACINA_COV VARCHAR,
            VACINA VARCHAR,
            ANO_NOTIFIC INTEGER,
            MES_NOTIFIC INTEGER
        )
        """
    )
    rows = [
        ("1", "2026-06-01", "SP", "1", "1", "2", "9", "2", 2026, 6),
        ("2", "2026-06-02", "SP", "2", "1", "2", "9", "2", 2026, 6),
        ("3", "2026-06-03", "SP", "3", "1", "2", "9", "2", 2026, 6),
        ("4", "2026-06-04", "SP", "4", "1", "2", "9", "2", 2026, 6),
        ("5", "2026-06-05", "SP", "9", "1", "2", "9", "2", 2026, 6),
        ("6", "2026-05-01", "SP", "1", "1", "2", "9", "2", 2026, 5),
        ("7", "2026-05-02", "SP", "2", "1", "2", "9", "2", 2026, 5),
        ("8", "2026-07-01", "SP", "1", "1", "2", "9", "2", 2026, 7),
        ("9", "2026-07-02", "SP", "2", "1", "2", "9", "2", 2026, 7),
    ]
    connection.executemany(
        """
        INSERT INTO srag_notificacoes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.close()
    return db_path


@pytest.fixture
def metrics_service(metrics_db) -> SRAGMetrics:
    return SRAGMetrics(duckdb_path=metrics_db, table_name="srag_notificacoes")
