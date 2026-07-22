from typing import Any

from pydantic import BaseModel, Field

from app.models.chart import ChartSpec


class ChatRequest(BaseModel):
    message: str = Field(description="Mensagem do analista para o chatbot.")
    session_id: str | None = Field(
        default=None,
        description="Identificador da sessao de conversa. Se omitido, a API cria um novo.",
    )
    estado_contexto: str = Field(
        default="BRASIL",
        description="Contexto geografico padrao inicial; o agente pode inferir UF/BRASIL da mensagem.",
    )


class ChatReportPayload(BaseModel):
    estado: str = Field(description="UF ou BRASIL do relatorio gerado.")
    resumo_executivo: str = Field(description="Texto completo do relatorio executivo.")
    charts: list[ChartSpec] = Field(
        default_factory=list,
        description="Graficos oficiais do relatorio.",
    )


class ChatResponse(BaseModel):
    session_id: str = Field(description="Identificador da sessao de conversa.")
    estado_contexto: str = Field(description="Contexto geografico associado a esta resposta.")
    reply: str = Field(description="Resposta textual curta do chatbot (sem colar o relatorio completo).")
    charts: list[ChartSpec] = Field(
        default_factory=list,
        description="Graficos avulsos da rodada de chat (nao substitui o relatorio).",
    )
    tools_used: list[str] = Field(
        default_factory=list,
        description="Nomes das tools invocadas nesta rodada.",
    )
    report: ChatReportPayload | None = Field(
        default=None,
        description="Relatorio executivo gerado para a secao Relatorio gerado por IA, se solicitado.",
    )
