from pathlib import Path

import duckdb
import pandas as pd

from app.config import (
    DUCKDB_PATH,
    ETL_COLUMNS,
    ETL_DATE_SOURCE_COLUMN,
    ETL_FILL_MISSING_COLUMNS,
    ETL_MISSING_VALUE,
    ETL_TABLE_NAME,
    RAW_DATA_DIR,
)


class EtlService:
    def __init__(
        self,
        raw_data_dir: Path = RAW_DATA_DIR,
        duckdb_path: Path = DUCKDB_PATH,
        table_name: str = ETL_TABLE_NAME,
    ):
        self.raw_data_dir = raw_data_dir
        self.duckdb_path = duckdb_path
        self.table_name = table_name

    def _list_csv_files(self) -> list[Path]:
        return sorted(self.raw_data_dir.glob("*.csv"))

    def _read_columns_for_file(self, csv_file: Path) -> list[str]:
        header = pd.read_csv(csv_file, sep=";", nrows=0, encoding="utf-8").columns.tolist()
        needed = set(ETL_COLUMNS) | {ETL_DATE_SOURCE_COLUMN}
        return [column for column in header if column in needed]

    def _merge_datasets(self, csv_files: list[Path]) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []

        for csv_file in csv_files:
            columns = self._read_columns_for_file(csv_file)
            frame = pd.read_csv(
                csv_file,
                sep=";",
                usecols=columns,
                dtype=str,
                encoding="utf-8",
                low_memory=False,
            )
            frames.append(frame)

        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _has_information(series: pd.Series) -> pd.Series:
        return series.notna() & series.astype(str).str.strip().ne("")

    def _filter_required_fields(self, frame: pd.DataFrame) -> pd.DataFrame:
        filtered = frame[self._has_information(frame["NU_NOTIFIC"])].copy()
        return filtered[self._has_information(filtered["SG_UF_NOT"])]

    def _select_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        return frame[ETL_COLUMNS].copy()

    def _fill_missing_values(self, frame: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()
        for column in ETL_FILL_MISSING_COLUMNS:
            missing_mask = ~self._has_information(result[column])
            result.loc[missing_mask, column] = ETL_MISSING_VALUE
        return result

    def _add_notification_period(self, frame: pd.DataFrame, source: pd.DataFrame) -> pd.DataFrame:
        result = frame.copy()
        notification_dates = pd.to_datetime(source[ETL_DATE_SOURCE_COLUMN], errors="coerce", utc=True)
        result["ANO_NOTIFIC"] = notification_dates.dt.year
        result["MES_NOTIFIC"] = notification_dates.dt.month
        return result

    def _save_to_duckdb(self, frame: pd.DataFrame) -> None:
        self.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(self.duckdb_path))
        try:
            connection.register("etl_frame", frame)
            connection.execute(f'CREATE OR REPLACE TABLE "{self.table_name}" AS SELECT * FROM etl_frame')
        finally:
            connection.close()

    def run(self) -> dict:
        csv_files = self._list_csv_files()
        if not csv_files:
            raise FileNotFoundError(f"Nenhum arquivo CSV encontrado em {self.raw_data_dir}.")

        merged = self._merge_datasets(csv_files)
        rows_before_filter = len(merged)

        missing_columns = [column for column in ETL_COLUMNS if column not in merged.columns]
        if missing_columns:
            raise ValueError(f"Colunas obrigatórias ausentes nos datasets: {', '.join(missing_columns)}.")

        if ETL_DATE_SOURCE_COLUMN not in merged.columns:
            raise ValueError(
                f"Coluna {ETL_DATE_SOURCE_COLUMN} ausente nos datasets; "
                "necessária para derivar ANO_NOTIFIC e MES_NOTIFIC."
            )

        filtered = self._filter_required_fields(merged)
        selected = self._select_columns(filtered)
        filled = self._fill_missing_values(selected)
        transformed = self._add_notification_period(filled, filtered)
        self._save_to_duckdb(transformed)

        return {
            "files_merged": [file.name for file in csv_files],
            "rows_before_filter": rows_before_filter,
            "rows_after_filter": len(filtered),
            "rows_saved": len(transformed),
            "table_name": self.table_name,
            "database_path": str(self.duckdb_path),
        }
