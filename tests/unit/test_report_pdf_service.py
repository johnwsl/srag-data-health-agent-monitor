"""Testes unitarios de funcoes puras do PDF (markdown -> ReportLab flowables)."""

from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Table

from app.services.report_pdf_service import (
    _inline_markdown_to_reportlab,
    _resumo_to_flowables,
)

COMPOSED_RESUMO = (
    "**Resumo Executivo - Estado de São Paulo (SP)**\n\n"
    "**Período Analisado:** Maio de 2026 a Junho de 2026\n\n"
    "Dados oficiais apontam redução moderada de casos no período.\n\n"
    "## Quatro métricas principais\n\n"
    "| Métrica | Valor | Detalhe |\n"
    "| --- | --- | --- |\n"
    "| Taxa de aumento de casos | -8,10% | 70 atuais / 95 anteriores |\n"
    "| Taxa de mortalidade | 5,00% | 9 óbitos / 180 casos |\n"
    "| Taxa de ocupação de UTI | 20,00% | 36 internados em UTI / 180 casos |\n"
    "| Taxa de vacinação COVID | 50,00% | 90 vacinados / 180 casos |\n\n"
    "## Notícias encontradas\n\n"
    "1. [SRAG em queda no Brasil](https://www.gov.br/saude/srag)\n"
    "   Boletim aponta redução de casos.\n"
    "   Link: https://www.gov.br/saude/srag\n"
)


def _flowable_styles():
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["Normal"])
    section = ParagraphStyle("section", parent=styles["Heading2"])
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=10)
    return body, section, bullet


def test_inline_markdown_converts_bold_and_links():
    assert _inline_markdown_to_reportlab("Taxa **-8,1%**") == "Taxa <b>-8,1%</b>"
    html_link = _inline_markdown_to_reportlab("[SRAG](https://www.gov.br/saude)")
    assert '<link href="https://www.gov.br/saude"' in html_link
    assert "<u>SRAG</u>" in html_link


def test_resumo_to_flowables_renders_narrative_table_and_news_links():
    body, section, bullet = _flowable_styles()

    flowables = _resumo_to_flowables(
        COMPOSED_RESUMO,
        body_style=body,
        section_style=section,
        bullet_style=bullet,
    )

    assert len(flowables) >= 4
    tables = [item for item in flowables if isinstance(item, Table)]
    assert len(tables) == 1
    table_text = " ".join(
        cell.getPlainText() if hasattr(cell, "getPlainText") else str(cell)
        for row in tables[0]._cellvalues
        for cell in row
    )
    assert "Taxa de aumento de casos" in table_text
    assert "-8,10%" in table_text

    rendered = " ".join(
        item.getPlainText() for item in flowables if hasattr(item, "getPlainText")
    )
    assert "**" not in rendered
    assert "Resumo Executivo - Estado de São Paulo (SP)" in rendered
    assert "Quatro métricas principais" in rendered
    assert "Notícias encontradas" in rendered
    assert "SRAG em queda no Brasil" in rendered
