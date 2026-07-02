from fastapi import APIRouter

from app.controllers.agent_controller import AgentController
from app.models.agent import ExecutiveSummaryRequest, ExecutiveSummaryResponse

router = APIRouter(prefix="/agents", tags=["agents"])
controller = AgentController()


@router.post("/report", response_model=ExecutiveSummaryResponse)
def generate_report(payload: ExecutiveSummaryRequest) -> ExecutiveSummaryResponse:
    """Gera um resumo executivo com dados oficiais SRAG e noticias recentes."""
    return controller.generate_report(payload)
