from fastapi import HTTPException, status

from app.models.agent import ExecutiveSummaryRequest, ExecutiveSummaryResponse
from app.models.chat import ChatReportPayload, ChatRequest, ChatResponse
from app.services.srag_langgraph_agent import SragLangGraphAgent


class AgentController:
    def __init__(self, orchestrator: SragLangGraphAgent | None = None):
        self.orchestrator = orchestrator

    def _get_orchestrator(self) -> SragLangGraphAgent:
        if self.orchestrator is None:
            self.orchestrator = SragLangGraphAgent()
        return self.orchestrator

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
        )

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
        )
