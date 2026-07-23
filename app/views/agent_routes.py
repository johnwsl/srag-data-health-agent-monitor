from fastapi import APIRouter, Query

from app.controllers.agent_controller import AgentController
from app.models.agent import ExecutiveSummaryRequest, ExecutiveSummaryResponse
from app.models.audit import AgentAuditListResponse, AgentAuditRecord, AgentAuditSessionResponse
from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/agents", tags=["agents"])
controller = AgentController()


@router.post("/report", response_model=ExecutiveSummaryResponse)
def generate_report(payload: ExecutiveSummaryRequest) -> ExecutiveSummaryResponse:
    """Gera um resumo executivo com dados oficiais SRAG e noticias recentes."""
    return controller.generate_report(payload)


@router.post("/chat", response_model=ChatResponse)
def chat_with_agent(payload: ChatRequest) -> ChatResponse:
    """Conversa com o chatbot SRAG (LangGraph), com memoria por session_id e ChartSpecs."""
    return controller.chat(payload)


@router.get("/audit", response_model=AgentAuditListResponse)
def list_agent_audit(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    kind: str | None = Query(default=None, description="Filtrar por 'chat' ou 'report'."),
    session_id: str | None = Query(default=None, description="Filtrar por session_id."),
) -> AgentAuditListResponse:
    """Lista eventos recentes de auditoria/governanca do orquestrador."""
    return controller.list_audit(
        limit=limit,
        offset=offset,
        kind=kind,
        session_id=session_id,
    )


@router.get("/audit/session/{session_id}", response_model=AgentAuditSessionResponse)
def get_agent_audit_session(session_id: str) -> AgentAuditSessionResponse:
    """Lista a trilha de auditoria de uma sessao de chat/relatorio."""
    return controller.get_audit_session(session_id)


@router.get("/audit/{audit_id}", response_model=AgentAuditRecord)
def get_agent_audit_event(audit_id: str) -> AgentAuditRecord:
    """Retorna um evento de auditoria pelo audit_id."""
    return controller.get_audit_event(audit_id)
