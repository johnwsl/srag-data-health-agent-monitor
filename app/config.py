import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

API_HOST = os.environ["API_HOST"]
API_PORT = int(os.environ["API_PORT"])
HTTP_TIMEOUT_SECONDS = float(os.environ["HTTP_TIMEOUT_SECONDS"])

_raw_data_dir = Path(os.environ["RAW_DATA_DIR"])
RAW_DATA_DIR = _raw_data_dir if _raw_data_dir.is_absolute() else BASE_DIR / _raw_data_dir

_duckdb_path = Path(os.environ["DUCKDB_PATH"])
DUCKDB_PATH = _duckdb_path if _duckdb_path.is_absolute() else BASE_DIR / _duckdb_path
ETL_TABLE_NAME = os.environ["ETL_TABLE_NAME"]

ETL_COLUMNS = [
    "NU_NOTIFIC",
    "DT_NOTIFIC",
    "SG_UF_NOT",
    "CLASSI_FIN",
    "EVOLUCAO",
    "UTI",
    "VACINA_COV",
    "VACINA",
]
ETL_FILL_MISSING_COLUMNS = ["CLASSI_FIN", "EVOLUCAO", "UTI", "VACINA_COV", "VACINA"]
ETL_DATE_SOURCE_COLUMN = "DT_NOTIFIC"
ETL_MISSING_VALUE = "9"

DATASET_NAME_2019 = os.environ["DATASET_NAME_2019"]
DATASET_URL_2019 = os.environ["DATASET_URL_2019"]
DATASET_NAME_2025 = os.environ["DATASET_NAME_2025"]
DATASET_URL_2025 = os.environ["DATASET_URL_2025"]

DATASET_URLS: list[dict[str, str]] = [
    {"name": DATASET_NAME_2019, "url": DATASET_URL_2019},
    {"name": DATASET_NAME_2025, "url": DATASET_URL_2025},
]
