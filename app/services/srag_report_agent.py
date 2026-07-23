"""Facade de compatibilidade: o orquestrador real e LangGraphOrchestratorAgent."""

from typing import Any

from app.services.chart_spec_service import ChartSpecService
from app.services.openai_langchain_service import OpenAILangChainService
from app.services.langgraph_orchestrator_agent import LangGraphOrchestratorAgent
from app.services.srag_metrics_api_service import SragMetricsApiLangChainService
from app.services.tavily_news_service import TavilyNewsLangChainService


class SragReportAgent:
    """Gera resumo executivo via orquestrador unico LangGraph."""

    def __init__(
        self,
        llm_service: OpenAILangChainService | None = None,
        metrics_service: SragMetricsApiLangChainService | None = None,
        news_service: TavilyNewsLangChainService | None = None,
        chart_spec_service: ChartSpecService | None = None,
        orchestrator: LangGraphOrchestratorAgent | None = None,
        max_chars: int = 5000,
        max_tool_iterations: int = 8,
        **kwargs: Any,
    ) -> None:
        del max_tool_iterations  # legado do loop bind_tools; ignorado no LangGraph
        self.orchestrator = orchestrator or LangGraphOrchestratorAgent(
            llm_service=llm_service,
            metrics_service=metrics_service,
            news_service=news_service,
            chart_spec_service=chart_spec_service,
            max_chars=max_chars,
            **{k: v for k, v in kwargs.items() if k in {"checkpointer", "graph"}},
        )

    def generate_executive_summary(self, estado: str) -> dict[str, Any]:
        return self.orchestrator.generate_executive_summary(estado)
