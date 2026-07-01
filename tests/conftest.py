import pytest

from app.config import ETL_COLUMNS

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
