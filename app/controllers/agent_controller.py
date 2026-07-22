from fastapi import HTTPException, status

from app.models.agent import ExecutiveSummaryRequest, ExecutiveSummaryResponse
from app.services.srag_report_agent import SragReportAgent


class AgentController:
    def __init__(self, report_agent: SragReportAgent | None = None):
        self.report_agent = report_agent

    def _get_report_agent(self) -> SragReportAgent:
        if self.report_agent is None:
            self.report_agent = SragReportAgent()
        return self.report_agent

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
