from fastapi import HTTPException, Query, status

from app.models.agent import ExecutiveSummaryRequest, ExecutiveSummaryResponse
from app.models.audit import (
    AgentAuditListResponse,
    AgentAuditRecord,
    AgentAuditSessionResponse,
)
from app.models.chat import ChatReportPayload, ChatRequest, ChatResponse
from app.services.agent_audit_service import AgentAuditService
from app.services.langgraph_orchestrator_agent import LangGraphOrchestratorAgent
from app.services.report_pdf_service import ReportPdfService


class AgentController:
    def __init__(
        self,
        orchestrator: LangGraphOrchestratorAgent | None = None,
        audit_service: AgentAuditService | None = None,
        pdf_service: ReportPdfService | None = None,
    ):
        self.orchestrator = orchestrator
        self.audit_service = audit_service
        self.pdf_service = pdf_service or ReportPdfService()

    def _get_orchestrator(self) -> LangGraphOrchestratorAgent:
        if self.orchestrator is None:
            self.orchestrator = LangGraphOrchestratorAgent(
                audit_service=self._get_audit_service(),
            )
        return self.orchestrator

    def _get_audit_service(self) -> AgentAuditService:
        if self.audit_service is None:
            self.audit_service = AgentAuditService()
        return self.audit_service

    def generate_report(self, payload: ExecutiveSummaryRequest) -> ExecutiveSummaryResponse:
        estado = payload.estado.strip().upper()

        try:
            result = self._get_orchestrator().generate_executive_summary(estado)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha ao gerar resumo executivo: {error}",
            ) from error

        return ExecutiveSummaryResponse(
            estado=estado,
            resumo_executivo=result["resumo_executivo"],
            charts=result.get("charts") or [],
            audit_id=result.get("audit_id"),
        )

    def export_report_pdf(self, payload: ChatReportPayload) -> bytes:
        resumo = (payload.resumo_executivo or "").strip()
        if not resumo:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="resumo_executivo e obrigatorio para exportar o PDF.",
            )
        try:
            return self.pdf_service.build(payload)
        except Exception as error:  # noqa: BLE001
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Falha ao gerar PDF do relatorio: {error}",
            ) from error

    def chat(self, payload: ChatRequest) -> ChatResponse:
        try:
            result = self._get_orchestrator().chat(
                payload.message,
                session_id=payload.session_id,
                estado_contexto=payload.estado_contexto,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Falha no chatbot SRAG: {error}",
            ) from error

        report_payload = None
        if result.get("report"):
            report_payload = ChatReportPayload(
                estado=result["report"]["estado"],
                resumo_executivo=result["report"]["resumo_executivo"],
                charts=result["report"].get("charts") or [],
            )

        return ChatResponse(
            session_id=result["session_id"],
            estado_contexto=result["estado_contexto"],
            reply=result["reply"],
            charts=result.get("charts") or [],
            tools_used=result.get("tools_used") or [],
            report=report_payload,
            audit_id=result.get("audit_id"),
        )

    def list_audit(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        kind: str | None = None,
        session_id: str | None = None,
    ) -> AgentAuditListResponse:
        items = self._get_audit_service().list_events(
            limit=limit,
            offset=offset,
            kind=kind,
            session_id=session_id,
        )
        return AgentAuditListResponse(
            total=len(items),
            items=[AgentAuditRecord(**item) for item in items],
        )

    def get_audit_session(self, session_id: str) -> AgentAuditSessionResponse:
        session = (session_id or "").strip()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="session_id e obrigatorio.",
            )
        items = self._get_audit_service().get_by_session(session)
        return AgentAuditSessionResponse(
            session_id=session,
            total=len(items),
            items=[AgentAuditRecord(**item) for item in items],
        )

    def get_audit_event(self, audit_id: str) -> AgentAuditRecord:
        event_id = (audit_id or "").strip()
        if not event_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="audit_id e obrigatorio.",
            )
        item = self._get_audit_service().get_by_id(event_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evento de auditoria nao encontrado: {event_id}",
            )
        return AgentAuditRecord(**item)
