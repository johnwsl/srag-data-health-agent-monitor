import json
from typing import Any

from app.services.chart_spec_service import ChartSpecService
from app.services.openai_langchain_service import OpenAILangChainService
from app.services.srag_metrics_api_service import SragMetricsApiLangChainService
from app.services.tavily_news_service import TavilyNewsLangChainService


class SragReportAgent:
    """Orquestra tools de metricas e noticias para gerar um resumo executivo."""

    def __init__(
        self,
        llm_service: OpenAILangChainService | None = None,
        metrics_service: SragMetricsApiLangChainService | None = None,
        news_service: TavilyNewsLangChainService | None = None,
        chart_spec_service: ChartSpecService | None = None,
        max_chars: int = 4000,
    ) -> None:
        self.llm_service = llm_service or OpenAILangChainService()
        self.metrics_service = metrics_service or SragMetricsApiLangChainService()
        self.news_service = news_service or TavilyNewsLangChainService()
        self.chart_spec_service = chart_spec_service or ChartSpecService()
        self.max_chars = max_chars

    def generate_executive_summary(self, estado: str) -> dict[str, Any]:
        pipeline_status = self.metrics_service.ensure_pipeline_ready()
        official_payload = self.metrics_service.get_full_metrics_data(estado)
        official_data = json.dumps(official_payload, ensure_ascii=False, default=str)
        news_data = self.news_service.as_tool().invoke({})
        charts = self.chart_spec_service.from_metrics_payload(official_payload)

        system_prompt = (
            "Voce e um analista de saude publica. Produza um resumo executivo em portugues, "
            "com no maximo 5000 caracteres, separando claramente 'Dados oficiais' e 'Noticias'. "
            "Mostre as 4 metricas principais, destaque tendencias recentes dos casos diarios e mensais, "
            "e use as noticias apenas como contexto complementar. Nao invente dados. "
            "Se houver ausencia de noticias relevantes, diga isso explicitamente. "
            "Importante sobre vies temporal: os dados recentes de SRAG sofrem atraso de "
            "digitacao/notificacao. Nao interprete queda abrupta nos dias ou semanas mais recentes "
            "como reducao real de casos sem mencionar a possibilidade de incompleteness dos dados. "
            "Prefira analisar tendencias em periodos mais consolidados quando houver sinais de "
            "defasagem. O relatorio e acompanhado por graficos oficiais das series diaria e mensal; "
            "voce pode referenciar esses graficos no texto."
        )

        user_prompt = (
            f"Estado consultado: {estado.upper().strip()}\n\n"
            "Status da pipeline SRAG:\n"
            f"{pipeline_status}\n\n"
            "Dados oficiais da API SRAG:\n"
            f"{official_data}\n\n"
            "Noticias recentes coletadas:\n"
            f"{news_data}\n\n"
            "Escreva um resumo executivo curto com:\n"
            "1. panorama geral;\n"
            "2. bloco 'Dados oficiais' com as 4 metricas e tendencias "
            "(incluindo referencia aos graficos diario e mensal quando fizer sentido);\n"
            "3. bloco 'Noticias' separado dos dados oficiais;\n"
            "4. linguagem objetiva;\n"
            "5. alerta breve se a serie recente parecer incompleta por atraso de notificacao."
        )

        response = self.llm_service.ask(user_prompt, system_prompt=system_prompt)
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
