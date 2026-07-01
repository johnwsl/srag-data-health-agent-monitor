from fastapi import FastAPI

from app.views.dataset_routes import router as dataset_router
from app.views.etl_routes import router as etl_router
from app.views.pipeline_routes import router as pipeline_router

app = FastAPI(
    title="SRAG Data Health Agent Monitor",
    description="API para monitoramento de dados de SRAG com agentes de IA.",
    version="0.1.0",
)

app.include_router(dataset_router)
app.include_router(etl_router)
app.include_router(pipeline_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Verifica se a API está em execução. Usado por health checks e Docker."""
    return {"status": "ok"}
