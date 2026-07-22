import os
from collections.abc import Sequence

from pydantic import BaseModel

TAVILY_SEARCH_QUERY = "SRAG sindrome respiratoria aguda grave Brasil noticias"

SRAG_NEWS_GUARDRAILS = """Restricoes (guardrails):
- Apenas pesquisas relacionadas a SRAG ou sindromes respiratorias.
- Ignora conteudos fora do Brasil.
- Evita termos explicitos, preconceituosos ou politicos.
- Noticias com algum desses termos devem ser evitados: "porn", "sexo", "violencia", "racismo", "politica", "celebridade",
  "guerra", "crime", "assassinato", "terrorismo"
"""

BLOCKED_TERMS = (
    "porn",
    "sexo",
    "violencia",
    "racismo",
    "politica",
    "celebridade",
    "guerra",
    "crime",
    "assassinato",
    "terrorismo",
)


class TavilyNewsToolInput(BaseModel):
    """Entrada vazia; a consulta enviada a Tavily e fixa e otimizada para busca de noticias."""


class TavilyNewsLangChainService:
    """Tool LangChain para buscar noticias de SRAG usando Tavily Search."""

    def __init__(
        self,
        api_key: str | None = None,
        max_results: int = 5,
        tavily_search_tool=None,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.max_results = max_results

        if not self.api_key and tavily_search_tool is None:
            raise ValueError("TAVILY_API_KEY nao configurada.")

        self._tool = tavily_search_tool or self._build_tool()

    def _build_tool(self):
        try:
            from langchain_tavily import TavilySearch
        except ImportError as exc:
            raise ImportError(
                "Dependencia ausente. Instale 'langchain-tavily' para usar TavilyNewsLangChainService."
            ) from exc

        return TavilySearch(
            api_key=self.api_key,
            max_results=self.max_results,
            topic="news",
            include_answer=False,
            include_raw_content=False,
            search_depth="advanced",
            time_range="year",
            include_domains=["gov.br", "saude.gov.br", "g1.globo.com", "uol.com.br", "cnnbrasil.com.br"],
        )

    def buscar_noticias(self) -> str:
        response = self._tool.invoke({"query": TAVILY_SEARCH_QUERY})
        results = self._extract_results(response)
        filtered_results = self._filter_results(results)

        if not filtered_results:
            return "Nenhuma noticia relevante sobre SRAG no Brasil foi encontrada."

        lines = ["Noticias recentes sobre SRAG no Brasil:"]
        for index, item in enumerate(filtered_results[: self.max_results], start=1):
            title = item.get("title", "Sem titulo").strip()
            url = item.get("url", "").strip()
            content = item.get("content", "").strip()
            snippet = self._summarize_content(content)
            lines.append(f"{index}. {title}")
            if snippet:
                lines.append(f"   Resumo: {snippet}")
            if url:
                lines.append(f"   URL: {url}")

        return "\n".join(lines)

    def _extract_results(self, response) -> list[dict]:
        if isinstance(response, dict) and "results" in response:
            results = response["results"]
            return results if isinstance(results, list) else []
        return []

    def _filter_results(self, results: Sequence[dict]) -> list[dict]:
        filtered: list[dict] = []

        for item in results:
            text = " ".join(
                str(item.get(field, "")) for field in ("title", "content", "url") if item.get(field) is not None
            ).lower()

            if "brasil" not in text and ".br" not in text and "srag" not in text:
                continue
            if "srag" not in text and "respirat" not in text:
                continue
            if any(term in text for term in BLOCKED_TERMS):
                continue

            filtered.append(item)

        return filtered

    @staticmethod
    def _summarize_content(content: str, max_length: int = 220) -> str:
        compact = " ".join(content.split())
        if len(compact) <= max_length:
            return compact
        return f"{compact[: max_length - 3].rstrip()}..."

    def as_tool(self):
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise ImportError(
                "Dependencia ausente. Instale 'langchain-core' para usar TavilyNewsLangChainService.as_tool()."
            ) from exc

        return StructuredTool.from_function(
            func=self.buscar_noticias,
            name="buscar_noticias_srag",
            description=(
                "Busca noticias recentes sobre SRAG no Brasil usando Tavily Search e retorna "
                "um resumo textual com manchetes e URLs relevantes, respeitando guardrails de conteudo.\n\n"
                f"{SRAG_NEWS_GUARDRAILS}"
            ),
            args_schema=TavilyNewsToolInput,
        )
