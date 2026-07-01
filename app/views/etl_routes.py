from fastapi import APIRouter

from app.controllers.etl_controller import EtlController
from app.models.etl import EtlResponse

router = APIRouter(prefix="/datasets", tags=["etl"])
controller = EtlController()


@router.post("/etl", response_model=EtlResponse)
def run_etl() -> EtlResponse:
    """Executa o ETL sobre os CSVs em raw_data e salva o resultado no DuckDB.

    Faz merge dos arquivos, seleciona as colunas NU_NOTIFIC, DT_NOTIFIC,
    SG_UF_NOT, CLASSI_FIN, EVOLUCAO, UTI, VACINA_COV e VACINA, filtra
    registros inválidos, preenche ausentes com 9, deriva ANO_NOTIFIC/MES_NOTIFIC
    a partir de DT_NOTIFIC e persiste na tabela configurada em ETL_TABLE_NAME.
    """
    return controller.run_etl()
