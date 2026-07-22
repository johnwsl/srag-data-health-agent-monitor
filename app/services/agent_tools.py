from typing import Any

from app.services.chart_spec_service import ChartSpecService
from app.services.srag_metrics_api_service import SragMetricsApiLangChainService
from app.services.tavily_news_service import TavilyNewsLangChainService


def build_srag_agent_tools(
    metrics_service: SragMetricsApiLangChainService,
    news_service: TavilyNewsLangChainService,
    chart_spec_service: ChartSpecService,
) -> list[Any]:
    """Tools compartilhadas pelo agente de relatório e pelo chatbot LangGraph."""
    return [
        metrics_service.as_tool(),
        metrics_service.as_series_tool(),
        chart_spec_service.as_tool(metrics_service),
        news_service.as_tool(),
    ]
