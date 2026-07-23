"""Gera Resumo_Arquitetura_Solucao_srag.pdf com fluxo do chatbot, guardrails e figura."""

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Resumo_Arquitetura_Solucao_srag.pdf"
FLOW_IMG = ROOT / "docs" / "fluxo_chatbot_orquestrador.png"

font_path = Path(r"C:\Windows\Fonts\arial.ttf")
font_bold = Path(r"C:\Windows\Fonts\arialbd.ttf")
pdfmetrics.registerFont(TTFont("ArialPT", str(font_path)))
pdfmetrics.registerFont(TTFont("ArialPT-Bold", str(font_bold)))

PAGE_W, PAGE_H = A4
CONTENT_W = PAGE_W - 4 * cm

doc = SimpleDocTemplate(
    str(OUT),
    pagesize=A4,
    leftMargin=2 * cm,
    rightMargin=2 * cm,
    topMargin=1.6 * cm,
    bottomMargin=1.6 * cm,
    title="Arquitetura Conceitual da Solução SRAG — Chatbot e Orquestrador",
    author="SRAG Data Health Agent Monitor",
)

styles = getSampleStyleSheet()
title = ParagraphStyle(
    "TitlePT",
    parent=styles["Title"],
    fontName="ArialPT-Bold",
    fontSize=16,
    leading=20,
    textColor=HexColor("#0B3D60"),
    spaceAfter=8,
)
subtitle = ParagraphStyle(
    "SubPT",
    parent=styles["Normal"],
    fontName="ArialPT",
    fontSize=10,
    leading=13,
    textColor=HexColor("#495057"),
    spaceAfter=8,
)
h1 = ParagraphStyle(
    "H1PT",
    parent=styles["Heading1"],
    fontName="ArialPT-Bold",
    fontSize=12,
    leading=15,
    textColor=HexColor("#0B3D60"),
    spaceBefore=12,
    spaceAfter=5,
)
h2 = ParagraphStyle(
    "H2PT",
    parent=styles["Heading2"],
    fontName="ArialPT-Bold",
    fontSize=10.5,
    leading=13,
    textColor=HexColor("#1F4E79"),
    spaceBefore=8,
    spaceAfter=3,
)
body = ParagraphStyle(
    "BodyPT",
    parent=styles["Normal"],
    fontName="ArialPT",
    fontSize=9.5,
    leading=13,
    spaceAfter=5,
)
bullet = ParagraphStyle(
    "BulletPT",
    parent=body,
    leftIndent=10,
    spaceAfter=2.5,
)
caption = ParagraphStyle(
    "CapPT",
    parent=body,
    fontSize=8,
    textColor=HexColor("#6C757D"),
    alignment=1,
    spaceBefore=4,
    spaceAfter=8,
)
footer = ParagraphStyle(
    "FooterPT",
    parent=body,
    fontSize=8,
    textColor=HexColor("#6C757D"),
)

story: list = []


def add(text: str, style=body) -> None:
    story.append(Paragraph(text, style))


def bullets(items: list[str]) -> None:
    for item in items:
        story.append(Paragraph(f"• {item}", bullet))


add("Arquitetura Conceitual da Solução SRAG", title)
add(
    "<b>Chatbot + Orquestrador LangGraph</b> — o usuário conversa em linguagem natural; "
    "o agente toma decisões dinâmicas (ReAct), escolhe tools e responde no chat ou gera "
    "relatório executivo.",
    subtitle,
)
story.append(HRFlowable(width="100%", thickness=1, color=HexColor("#B6D4FE"), spaceAfter=8))

add("1. O que é este sistema", h1)
add(
    "Trata-se de um <b>chatbot analítico de saúde pública</b> para monitoramento de "
    "<b>SRAG</b> (Síndrome Respiratória Aguda Grave) no Brasil. A interface principal é o "
    "dashboard Shiny (<font color='#0d6efd'>http://localhost:8080</font>), onde o analista "
    "digita mensagens no chatbot."
)
add(
    "Por trás do chat está o <b>LangGraphOrchestratorAgent</b>: um agente orquestrador com "
    "<b>tool calling dinâmico</b>. Em cada turno ele <b>decide</b> se responde direto ou se "
    "chama uma ou mais ferramentas (métricas, séries, gráficos, notícias ou relatório). "
    "Não há um pipeline fixo “sempre métricas → sempre notícias”; a decisão é do agente, "
    "guiada pelo system prompt e pelos guardrails."
)

add("2. Fluxo entre chatbot e agente orquestrador", h1)
add(
    "A figura abaixo mostra o caminho completo da mensagem do usuário até a resposta no "
    "chat ou no painel de relatório."
)

if FLOW_IMG.exists():
    # Largura máxima da página; altura proporcional.
    img = Image(str(FLOW_IMG))
    max_w = CONTENT_W
    max_h = 11.5 * cm
    iw, ih = img.imageWidth, img.imageHeight
    scale = min(max_w / iw, max_h / ih)
    img.drawWidth = iw * scale
    img.drawHeight = ih * scale
    story.append(KeepTogether([img, Paragraph(
        "Figura — Fluxo do chatbot com LangGraphOrchestratorAgent (ReAct + tools + auditoria).",
        caption,
    )]))
else:
    add("<i>[Figura docs/fluxo_chatbot_orquestrador.png não encontrada]</i>")

add("2.1 Explicação detalhada do fluxo", h2)
bullets(
    [
        "<b>1. Usuário no chatbot</b> — digita uma pergunta ou um pedido "
        "(ex.: “qual a mortalidade no Brasil?” ou “gere o relatório de SP”).",
        "<b>2. POST /agents/chat</b> — o dashboard envia a mensagem (e o "
        "<font face='Courier'>session_id</font> da conversa) para a API FastAPI.",
        "<b>3. LangGraphOrchestratorAgent</b> — recebe o turno, garante que a pipeline de "
        "dados está pronta e inicia o grafo LangGraph com memória "
        "(<font face='Courier'>MemorySaver</font>).",
        "<b>4. Auditoria em paralelo</b> — ao final (e em erros), grava evento em "
        "<font face='Courier'>agent_audit_log</font> (tools, args, reply, duração, status).",
        "<b>5. Decisão ReAct: tool ou resposta?</b> — este é o núcleo da autonomia do agente. "
        "A LLM analisa a mensagem + histórico e escolhe: chamar tool(s) <b>ou</b> emitir o "
        "texto final. Se chamar tool, recebe o resultado e <b>volta</b> à decisão "
        "(loop), até concluir.",
        "<b>6. Tools de análise</b> — "
        "<font face='Courier'>consultar_metricas_srag</font>, "
        "<font face='Courier'>consultar_serie_temporal</font>, "
        "<font face='Courier'>gerar_especificacao_grafico</font>, "
        "<font face='Courier'>buscar_noticias_srag</font>. Usadas para perguntas pontuais.",
        "<b>7. Pedido explícito de relatório</b> — somente se o usuário pedir de forma "
        "direta um relatório/resumo executivo, o agente chama "
        "<font face='Courier'>gerar_relatorio_executivo</font>. O texto completo + charts "
        "vão para a seção <b>Relatório gerado por IA</b>; no chat fica só uma confirmação breve.",
        "<b>8. Texto final → bolhas do chat</b> — a resposta conversacional "
        "(<font face='Courier'>reply</font>) aparece nas bolhas do chatbot, com escopo e "
        "período quando métricas oficiais foram usadas.",
    ]
)

add(
    "Em resumo: <b>o chatbot é a porta de entrada</b>; <b>o agente toma as decisões</b> "
    "(quais tools, em qual ordem, se gera relatório ou só responde). O frontend apenas "
    "exibe <font face='Courier'>reply</font> e, quando houver, "
    "<font face='Courier'>report</font> + gráficos Plotly a partir de ChartSpec."
)

add("3. Componentes da solução", h1)
add("Frontend (Shiny)", h2)
bullets(
    [
        "Chatbot no topo da página — interface conversacional",
        "Seção Relatório gerado por IA — texto + gráficos (não no chat)",
        "Sem filtro lateral de UF e sem botão “Gerar Relatório por IA”",
        "Escopo (UF/Brasil) e período vêm nas respostas do agente",
    ]
)
add("Backend (FastAPI)", h2)
bullets(
    [
        "<font face='Courier'>POST /agents/chat</font> — fluxo principal do chatbot",
        "<font face='Courier'>POST /agents/report</font> — relatório one-shot via API",
        "<font face='Courier'>GET /agents/audit*</font> — consulta da trilha de auditoria",
        "Métricas e pipeline: <font face='Courier'>/metrics/...</font>, "
        "<font face='Courier'>/datasets/...</font>",
    ]
)
add("Dados", h2)
bullets(
    [
        "OpenDataSUS → ETL → DuckDB <font face='Courier'>srag_notificacoes</font>",
        "Auditoria do agente em <font face='Courier'>agent_audit_log</font> (mesma base, "
        "tabela separada)",
        "Tools de métricas usam a API do projeto (não DuckDB direto)",
    ]
)

add("4. Tools disponíveis (escolhidas pelo agente)", h1)
bullets(
    [
        "<b>consultar_metricas_srag</b> — 4 métricas oficiais + séries",
        "<b>consultar_serie_temporal</b> — série diária ou mensal",
        "<b>gerar_especificacao_grafico</b> — ChartSpec (o dashboard desenha com Plotly)",
        "<b>buscar_noticias_srag</b> — Tavily Search com guardrails",
        "<b>gerar_relatorio_executivo</b> — relatório completo (só pedido explícito)",
    ]
)

add("5. Guardrails", h1)
add(
    "Os guardrails limitam o que o chatbot/agente pode fazer e o que entra no contexto. "
    "Há duas camadas principais:"
)

add("5.1 Guardrails do chatbot / orquestrador (system prompt)", h2)
bullets(
    [
        "Escopo restrito a <b>SRAG / saúde respiratória no Brasil</b>; fora disso, recusa "
        "educada.",
        "<b>Não inventa números</b> — deve usar tools oficiais da API.",
        "Nas respostas com métricas, <b>informa escopo</b> (UF ou BRASIL) e "
        "<b>período analisado</b> (campos mes_anterior → mes_atual).",
        "<font face='Courier'>gerar_relatorio_executivo</font> só em pedido "
        "<b>explícito e direto</b> de relatório/resumo executivo/painel completo.",
        "Perguntas pontuais (taxa, tendência, notícia) <b>não</b> disparam relatório.",
        "<b>Nunca cola o relatório completo no chat</b> — só confirma e aponta a seção "
        "“Relatório gerado por IA”.",
        "Aviso de <b>atraso de notificação</b>: não interpretar queda recente no fim da "
        "série como redução real sem mencionar incompleteness.",
        "Temperatura da LLM padrão <b>0</b> — decisões mais estáveis e reprodutíveis.",
    ]
)

add("5.2 Guardrails de notícias (Tavily)", h2)
bullets(
    [
        "Consulta fixa otimizada para SRAG no Brasil "
        "(<font face='Courier'>topic=news</font>, "
        "<font face='Courier'>time_range=year</font>, "
        "<font face='Courier'>max_results=5</font>).",
        "Domínios prioritários: gov.br, saude.gov.br, g1.globo.com, uol.com.br, "
        "cnnbrasil.com.br.",
        "Filtro pós-busca: exige Brasil/“.br” e termos SRAG/respiratório.",
        "Bloqueio de conteúdos inadequados (ex.: porn, sexo, violencia, racismo, politica, "
        "celebridade, guerra, crime, assassinato, terrorismo).",
        "Notícias são <b>contexto complementar</b> — não substituem dados oficiais.",
    ]
)

add("5.3 Guardrails de dados e API", h2)
bullets(
    [
        "Fonte oficial = API SRAG do próprio projeto.",
        "UF inválida → HTTP 422; falha de geração → HTTP 502.",
        "Resumo executivo limitado a ~5000 caracteres.",
        "Falha ao gravar auditoria <b>não</b> interrompe a resposta ao usuário.",
    ]
)

add("6. Resultado para o analista", h1)
bullets(
    [
        "Conversar no chatbot sobre métricas, tendências e notícias de SRAG",
        "Ver o agente decidir quais tools usar (visíveis no metadado da bolha)",
        "Pedir relatório executivo citando UF ou Brasil e vê-lo na seção dedicada",
        "Consultar a trilha de decisões via <font face='Courier'>GET /agents/audit</font>",
    ]
)

story.append(Spacer(1, 10))
story.append(
    HRFlowable(width="100%", thickness=0.5, color=HexColor("#CED4DA"), spaceBefore=4, spaceAfter=6)
)
add(
    "<i>Documento alinhado ao código atual (LangGraphOrchestratorAgent, chatbot Shiny, "
    "ChartSpec, Tavily e agent_audit_log). Figura: docs/fluxo_chatbot_orquestrador.png. "
    "Fonte textual: docs/arquitetura_solucao_srag.md e docs/agente_orquestrador.md.</i>",
    footer,
)

doc.build(story)
print(f"OK {OUT} ({OUT.stat().st_size} bytes) img={FLOW_IMG.exists()}")
