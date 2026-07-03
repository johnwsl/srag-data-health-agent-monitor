import pytest

from app.services.tavily_news_service import TAVILY_SEARCH_QUERY, TavilyNewsLangChainService


class FakeTavilySearch:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        return self.response


def test_busca_noticias_uses_default_query():
    fake_tool = FakeTavilySearch(
        {
            "results": [
                {
                    "title": "Brasil monitora aumento de casos de SRAG",
                    "url": "https://g1.globo.com/saude/noticia-srag-brasil",
                    "content": "Autoridades de saude acompanham novos casos de sindrome respiratoria aguda grave no Brasil.",
                }
            ]
        }
    )

    service = TavilyNewsLangChainService(tavily_search_tool=fake_tool)
    response = service.buscar_noticias()

    assert fake_tool.calls == [{"query": TAVILY_SEARCH_QUERY}]
    assert "Noticias recentes sobre SRAG no Brasil:" in response
    assert "Brasil monitora aumento de casos de SRAG" in response
    assert "https://g1.globo.com/saude/noticia-srag-brasil" in response


def test_busca_noticias_filters_blocked_content():
    fake_tool = FakeTavilySearch(
        {
            "results": [
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
            ]
        }
    )

    service = TavilyNewsLangChainService(tavily_search_tool=fake_tool)
    response = service.buscar_noticias()

    assert "Brasil monitora aumento de casos de SRAG" in response
    assert "Politica e celebridade comentam surto" not in response


def test_busca_noticias_returns_fallback_when_nothing_relevant():
    fake_tool = FakeTavilySearch(
        {
            "results": [
                {
                    "title": "Noticia internacional sem contexto",
                    "url": "https://example.com/news",
                    "content": "Tema geral sem relacao com sindromes respiratorias.",
                }
            ]
        }
    )

    service = TavilyNewsLangChainService(tavily_search_tool=fake_tool)

    assert service.buscar_noticias() == "Nenhuma noticia relevante sobre SRAG no Brasil foi encontrada."


def test_service_requires_api_key_when_tool_not_injected(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        TavilyNewsLangChainService()


def test_as_tool_invokes_news_search():
    fake_tool = FakeTavilySearch(
        {
            "results": [
                {
                    "title": "Brasil monitora aumento de casos de SRAG",
                    "url": "https://gov.br/saude/noticia-srag",
                    "content": "Boletim sobre sindrome respiratoria aguda grave no Brasil.",
                }
            ]
        }
    )

    service = TavilyNewsLangChainService(tavily_search_tool=fake_tool)
    tool = service.as_tool()
    response = tool.invoke({})

    assert tool.name == "buscar_noticias_srag"
    assert "Brasil monitora aumento de casos de SRAG" in response
