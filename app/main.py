import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.config import LOG_LEVEL
from app.logging_config import setup_logging
from app.views.agent_routes import router as agent_router
from app.views.dataset_routes import router as dataset_router
from app.views.etl_routes import router as etl_router
from app.views.metrics_routes import router as metrics_router
from app.views.pipeline_routes import router as pipeline_router

setup_logging(LOG_LEVEL)
logger = logging.getLogger("app.main")
request_logger = logging.getLogger("app.request")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API iniciada")
    yield
    logger.info("API encerrada")


app = FastAPI(
    title="SRAG Data Health Agent Monitor",
    description="API para monitoramento de dados de SRAG com agentes de IA.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(dataset_router)
app.include_router(etl_router)
app.include_router(pipeline_router)
app.include_router(metrics_router)
app.include_router(agent_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    request_logger.info(
        "%s %s %s %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Verifica se a API está em execução. Usado por health checks e Docker."""
    return {"status": "ok"}
