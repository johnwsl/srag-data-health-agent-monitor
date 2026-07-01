from fastapi import FastAPI

from app.views.dataset_routes import router as dataset_router

app = FastAPI(
    title="SRAG Data Health Agent Monitor",
    description="API para monitoramento de dados de SRAG com agentes de IA.",
    version="0.1.0",
)

app.include_router(dataset_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
