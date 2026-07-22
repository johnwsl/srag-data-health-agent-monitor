from fastapi import HTTPException, status

from app.models.agent import ExecutiveSummaryRequest, ExecutiveSummaryResponse
from app.models.chat import ChatRequest, ChatResponse
from app.services.srag_chat_agent import SragChatAgent
from app.services.srag_report_agent import SragReportAgent


class AgentController:
    def __init__(
        self,
        report_agent: SragReportAgent | None = None,
        chat_agent: SragChatAgent | None = None,
    ):
        self.report_agent = report_agent
        self.chat_agent = chat_agent

    def _get_report_agent(self) -> SragReportAgent:
        if self.report_agent is None:
            self.report_agent = SragReportAgent()
        return self.report_agent

    def _get_chat_agent(self) -> SragChatAgent:
        if self.chat_agent is None:
            self.chat_agent = SragChatAgent()
        return self.chat_agent

    def generate_report(self, payload: ExecutiveSummaryRequest) -> ExecutiveSummaryResponse:
        estado = payload.estado.strip().upper()

        try:
            result = self._get_report_agent().generate_executive_summary(estado)
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
            result = self._get_chat_agent().chat(
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

        return ChatResponse(
            session_id=result["session_id"],
            estado_contexto=result["estado_contexto"],
            reply=result["reply"],
            charts=result.get("charts") or [],
            tools_used=result.get("tools_used") or [],
        )
