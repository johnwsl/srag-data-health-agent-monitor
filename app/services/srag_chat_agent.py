"""Facade de compatibilidade: o orquestrador real e LangGraphOrchestratorAgent."""

from typing import Any

from app.services.chart_spec_service import ChartSpecService
from app.services.openai_langchain_service import OpenAILangChainService
from app.services.langgraph_orchestrator_agent import LangGraphOrchestratorAgent
from app.services.srag_metrics_api_service import SragMetricsApiLangChainService
from app.services.tavily_news_service import TavilyNewsLangChainService


class SragChatAgent:
    """Chatbot via orquestrador unico LangGraph."""

    def __init__(
        self,
        llm_service: OpenAILangChainService | None = None,
        metrics_service: SragMetricsApiLangChainService | None = None,
        news_service: TavilyNewsLangChainService | None = None,
        chart_spec_service: ChartSpecService | None = None,
        orchestrator: LangGraphOrchestratorAgent | None = None,
        checkpointer=None,
        graph=None,
    ) -> None:
        self.orchestrator = orchestrator or LangGraphOrchestratorAgent(
            llm_service=llm_service,
            metrics_service=metrics_service,
            news_service=news_service,
            chart_spec_service=chart_spec_service,
            checkpointer=checkpointer,
            graph=graph,
        )
        # Exposto para testes que inspecionam metrics_service no agente.
        self.metrics_service = self.orchestrator.metrics_service

    def chat(
        self,
        message: str,
        *,
        session_id: str | None = None,
        estado_contexto: str = "BRASIL",
    ) -> dict[str, Any]:
        return self.orchestrator.chat(
            message,
            session_id=session_id,
            estado_contexto=estado_contexto,
        )
