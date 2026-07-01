from fastapi import APIRouter

from app.controllers.etl_controller import EtlController
from app.models.etl import EtlResponse

router = APIRouter(prefix="/datasets", tags=["etl"])
controller = EtlController()


@router.post("/etl", response_model=EtlResponse)
def run_etl() -> EtlResponse:
    """Executa o ETL sobre os CSVs em raw_data e salva o resultado no DuckDB.

    Faz merge dos arquivos, seleciona e trata as colunas definidas, filtra
    registros inválidos, deriva ANO_NOTIFIC/MES_NOTIFIC e persiste na tabela
    configurada em ETL_TABLE_NAME.
    """
    return controller.run_etl()
