from app.services.openai_langchain_service import OpenAILangChainService
from app.services.srag_metrics_api_service import SragMetricsApiLangChainService
from app.services.tavily_news_service import SRAG_NEWS_QUERY, TavilyNewsLangChainService


class SragReportAgent:
    """Orquestra tools de metricas e noticias para gerar um resumo executivo."""

    def __init__(
        self,
        llm_service: OpenAILangChainService | None = None,
        metrics_service: SragMetricsApiLangChainService | None = None,
        news_service: TavilyNewsLangChainService | None = None,
        max_chars: int = 1500,
    ) -> None:
        self.llm_service = llm_service or OpenAILangChainService()
        self.metrics_service = metrics_service or SragMetricsApiLangChainService()
        self.news_service = news_service or TavilyNewsLangChainService()
        self.max_chars = max_chars

    def generate_executive_summary(self, estado: str) -> str:
        metrics_tool = self.metrics_service.as_tool()
        news_tool = self.news_service.as_tool()

        official_data = metrics_tool.invoke({"estado": estado})
        news_data = news_tool.invoke({"query": SRAG_NEWS_QUERY})

        system_prompt = (
            "Voce e um analista de saude publica. Produza um resumo executivo em portugues, "
            "com no maximo 1500 caracteres, separando claramente 'Dados oficiais' e 'Noticias'. "
            "Mostre as 4 metricas principais, destaque tendencias recentes dos casos diarios e mensais, "
            "e use as noticias apenas como contexto complementar. Nao invente dados. "
            "Se houver ausencia de noticias relevantes, diga isso explicitamente."
        )

        user_prompt = (
            f"Estado consultado: {estado.upper().strip()}\n\n"
            "Dados oficiais da API SRAG:\n"
            f"{official_data}\n\n"
            "Noticias recentes coletadas:\n"
            f"{news_data}\n\n"
            "Escreva um resumo executivo curto com:\n"
            "1. panorama geral;\n"
            "2. bloco 'Dados oficiais' com as 4 metricas e tendencias;\n"
            "3. bloco 'Noticias' separado dos dados oficiais;\n"
            "4. linguagem objetiva."
        )

        response = self.llm_service.ask(user_prompt, system_prompt=system_prompt)
        return self._limit_text(response)

    def _limit_text(self, text: str) -> str:
        compact = text.strip()
        if len(compact) <= self.max_chars:
            return compact

        truncated = compact[: self.max_chars - 3].rstrip()
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        return f"{truncated}..."
