"""Testes unitarios de funcoes puras do orquestrador (formatacao / humanizacao)."""

from unittest.mock import MagicMock

from app.services.agent_audit_service import AgentAuditService
from app.services.chart_spec_service import ChartSpecService
from app.services.langgraph_orchestrator_agent import LangGraphOrchestratorAgent


def _orchestrator() -> LangGraphOrchestratorAgent:
    return LangGraphOrchestratorAgent(
        llm_service=MagicMock(),
        metrics_service=MagicMock(),
        news_service=MagicMock(),
        chart_spec_service=ChartSpecService(),
        graph=MagicMock(),
        audit_service=AgentAuditService(enabled=False),
    )


def test_humanize_report_text_converts_bullets_to_prose():
    raw = (
        "Taxa de Aumento de Casos:\n"
        "- Casos em Junho de 2026: 51.892\n"
        "- Casos em Maio de 2026: 63.305\n"
        "- Taxa de Aumento Percentual: -18,03%\n"
    )
    prose = _orchestrator()._humanize_report_text(raw)
    assert "•" not in prose
    assert "- Casos" not in prose
    assert "51.892" in prose
    assert "Taxa de Aumento de Casos" in prose


def test_format_percent_and_int():
    orch = _orchestrator()
    assert orch._format_percent(25.0) == "25,00%"
    assert orch._format_percent(None) == "N/D"
    assert orch._format_int(51892) == "51.892"
    assert orch._format_int(None) == "N/D"
    assert orch._format_month_year(2026, 6) == "06/2026"


def test_format_metrics_table_markdown():
    payload = {
        "metricas": {
            "taxa_aumento_casos": {
                "mes_atual_ano": 2026,
                "mes_atual_mes": 6,
                "mes_anterior_ano": 2026,
                "mes_anterior_mes": 5,
                "casos_mes_atual": 100,
                "casos_mes_anterior": 80,
                "taxa_aumento_percentual": 25.0,
            },
            "taxa_mortalidade": {
                "mes_atual_ano": 2026,
                "mes_atual_mes": 6,
                "mes_anterior_ano": 2026,
                "mes_anterior_mes": 5,
                "total_casos_2_meses": 180,
                "total_obitos_2_meses": 9,
                "taxa_mortalidade_percentual": 5.0,
            },
            "taxa_ocupacao_uti": {
                "total_casos_2_meses": 180,
                "casos_com_uti_2_meses": 36,
                "taxa_ocupacao_uti_percentual": 20.0,
            },
            "taxa_vacinacao_populacao": {
                "total_casos_2_meses": 180,
                "casos_vacinados_2_meses": 90,
                "taxa_vacinacao_percentual": 50.0,
            },
        }
    }
    table = _orchestrator()._format_metrics_table_markdown(payload)
    assert "## Quatro métricas principais" in table
    assert "| Taxa de aumento de casos |" in table
    assert "25,00%" in table


def test_format_news_section_markdown_with_links():
    text = LangGraphOrchestratorAgent._format_news_section_markdown(
        [
            {
                "title": "SRAG em queda no Brasil",
                "url": "https://www.gov.br/saude/srag",
                "snippet": "Boletim aponta redução.",
            }
        ]
    )
    assert "## Notícias encontradas" in text
    assert "[SRAG em queda no Brasil](https://www.gov.br/saude/srag)" in text
    assert "https://www.gov.br/saude/srag" in text


def test_format_news_section_markdown_empty():
    text = LangGraphOrchestratorAgent._format_news_section_markdown([])
    assert "Nenhuma notícia relevante" in text


def test_parse_news_text_fallback():
    raw = (
        "1. Boletim SRAG no Brasil\n"
        "   Resumo: Queda de casos.\n"
        "   URL: https://www.gov.br/saude/boletim\n"
    )
    items = LangGraphOrchestratorAgent._parse_news_text_fallback(raw)
    assert len(items) == 1
    assert items[0]["title"] == "Boletim SRAG no Brasil"
    assert items[0]["url"] == "https://www.gov.br/saude/boletim"
    assert items[0]["snippet"] == "Queda de casos."
