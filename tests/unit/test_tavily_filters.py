"""Testes unitarios de funcoes puras do filtro Tavily."""

from app.services.tavily_news_service import TavilyNewsLangChainService


def _service() -> TavilyNewsLangChainService:
    return TavilyNewsLangChainService(tavily_search_tool=object())


def test_filter_results_keeps_relevant_brasil_srag():
    results = [
        {
            "title": "Brasil monitora aumento de casos de SRAG",
            "url": "https://gov.br/saude/noticia-srag",
            "content": "Boletim sobre sindrome respiratoria aguda grave no Brasil.",
        },
        {
            "title": "Politica e celebridade comentam surto",
            "url": "https://site.com.br/noticia",
            "content": "Materia mistura politica com celebridade e SRAG.",
        },
        {
            "title": "Noticia internacional sem contexto",
            "url": "https://example.com/news",
            "content": "Tema geral sem relacao.",
        },
    ]

    filtered = _service()._filter_results(results)

    assert len(filtered) == 1
    assert filtered[0]["title"].startswith("Brasil monitora")


def test_summarize_content_truncates_long_text():
    long_text = "palavra " * 80
    summarized = TavilyNewsLangChainService._summarize_content(long_text, max_length=40)
    assert len(summarized) <= 40
    assert summarized.endswith("...")
