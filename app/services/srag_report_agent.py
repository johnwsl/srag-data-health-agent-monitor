from typing import Any

from app.services.agent_tools import build_srag_agent_tools
from app.services.chart_spec_service import ChartSpecService
from app.services.openai_langchain_service import OpenAILangChainService
from app.services.srag_metrics_api_service import SragMetricsApiLangChainService
from app.services.tavily_news_service import TavilyNewsLangChainService


class SragReportAgent:
    """Agente com tool calling para gerar resumo executivo e ChartSpecs oficiais."""

    SYSTEM_PROMPT = (
        "Voce e um analista de saude publica. Use as ferramentas disponiveis para obter "
        "dados oficiais e noticias antes de escrever. Nao invente numeros. "
        "Produza um resumo executivo em portugues, com no maximo 4000 caracteres, "
        "separando claramente 'Dados oficiais' e 'Noticias'. "
        "Mostre as 4 metricas principais e tendencias das series quando disponiveis. "
        "Use noticias apenas como contexto complementar; se nao houver noticias relevantes, "
        "diga isso explicitamente. "
        "Importante sobre vies temporal: os dados recentes de SRAG sofrem atraso de "
        "digitacao/notificacao. Nao interprete queda abrupta nos dias ou semanas mais recentes "
        "como reducao real de casos sem mencionar a possibilidade de incompleteness dos dados. "
        "Prefira analisar tendencias em periodos mais consolidados quando houver sinais de "
        "defasagem. "
        "Para um relatorio completo, chame tipicamente: consultar_metricas_srag, "
        "gerar_especificacao_grafico (diaria e mensal) e buscar_noticias_srag. "
        "Voce pode usar consultar_serie_temporal quando precisar inspecionar uma serie isolada. "
        "Depois de usar as tools, escreva o texto final do relatorio."
    )

    def __init__(
        self,
        llm_service: OpenAILangChainService | None = None,
        metrics_service: SragMetricsApiLangChainService | None = None,
        news_service: TavilyNewsLangChainService | None = None,
        chart_spec_service: ChartSpecService | None = None,
        max_chars: int = 4000,
        max_tool_iterations: int = 8,
    ) -> None:
        self.llm_service = llm_service or OpenAILangChainService()
        self.metrics_service = metrics_service or SragMetricsApiLangChainService()
        self.news_service = news_service or TavilyNewsLangChainService()
        self.chart_spec_service = chart_spec_service or ChartSpecService()
        self.max_chars = max_chars
        self.max_tool_iterations = max_tool_iterations

    def _build_tools(self) -> list[Any]:
        return build_srag_agent_tools(
            self.metrics_service,
            self.news_service,
            self.chart_spec_service,
        )

    def generate_executive_summary(self, estado: str) -> dict[str, Any]:
        estado_normalizado = estado.strip().upper()
        pipeline_status = self.metrics_service.ensure_pipeline_ready()
        self.chart_spec_service.reset_generated_charts()
        tools = self._build_tools()

        user_prompt = (
            f"Gere o resumo executivo de SRAG para o estado/escopo: {estado_normalizado}.\n\n"
            "Status da pipeline SRAG:\n"
            f"{pipeline_status}\n\n"
            "Instrucoes:\n"
            "1. Consulte metricas oficiais com as tools.\n"
            "2. Gere especificacoes de grafico diaria e mensal.\n"
            "3. Busque noticias recentes com guardrails.\n"
            "4. Escreva o resumo com panorama geral, bloco 'Dados oficiais' "
            "(referenciando os graficos quando fizer sentido), bloco 'Noticias', "
            "linguagem objetiva e alerta breve se a serie recente parecer incompleta."
        )

        response = self.llm_service.run_with_tools(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=tools,
            max_iterations=self.max_tool_iterations,
        )

        charts = list(self.chart_spec_service.generated_charts)
        if not charts:
            try:
                official_payload = self.metrics_service.get_full_metrics_data(estado_normalizado)
                charts = self.chart_spec_service.from_metrics_payload(official_payload)
            except Exception:  # noqa: BLE001
                charts = []

        return {
            "resumo_executivo": self._limit_text(response),
            "charts": charts,
        }

    def _limit_text(self, text: str) -> str:
        compact = text.strip()
        if len(compact) <= self.max_chars:
            return compact

        truncated = compact[: self.max_chars - 3].rstrip()
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        return f"{truncated}..."
