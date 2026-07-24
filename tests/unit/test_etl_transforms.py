"""Testes unitarios de funcoes puras do ETL (transformacoes em DataFrame)."""

from pathlib import Path

import pandas as pd

from app.config import ETL_COLUMNS, ETL_MISSING_VALUE
from app.services.etl_service import EtlService


def _service() -> EtlService:
    # Paths nao sao usados pelas transformacoes puras abaixo.
    return EtlService(
        raw_data_dir=Path("."),
        duckdb_path=Path("unused.duckdb"),
        table_name="srag_test",
    )


def test_filter_required_fields_drops_rows_without_key_columns():
    frame = pd.DataFrame(
        [
            {"NU_NOTIFIC": "1", "DT_NOTIFIC": "2019-01-01", "SG_UF_NOT": "SP"},
            {"NU_NOTIFIC": "", "DT_NOTIFIC": "2019-01-01", "SG_UF_NOT": "RJ"},
            {"NU_NOTIFIC": "3", "DT_NOTIFIC": "2019-01-01", "SG_UF_NOT": ""},
            {"NU_NOTIFIC": "4", "DT_NOTIFIC": "2019-01-01", "SG_UF_NOT": "MG"},
        ]
    )

    filtered = _service()._filter_required_fields(frame)

    assert filtered["NU_NOTIFIC"].tolist() == ["1", "4"]


def test_fill_missing_values_uses_placeholder():
    frame = pd.DataFrame(
        [
            {
                "NU_NOTIFIC": "111",
                "DT_NOTIFIC": "2019-07-22",
                "SG_UF_NOT": "SP",
                "CLASSI_FIN": "1",
                "EVOLUCAO": "",
                "UTI": "2",
                "VACINA_COV": None,
                "VACINA": "2",
            }
        ]
    )
    # Garante colunas esperadas na ordem do ETL.
    frame = frame.reindex(columns=ETL_COLUMNS)

    filled = _service()._fill_missing_values(frame)
    row = filled.iloc[0]

    assert row["CLASSI_FIN"] == "1"
    assert row["EVOLUCAO"] == ETL_MISSING_VALUE
    assert row["VACINA_COV"] == ETL_MISSING_VALUE
    assert row["UTI"] == "2"
