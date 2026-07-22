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
        description="Sigla da UF ou BRASIL usada como contexto geografico padrao das tools.",
    )


class ChatResponse(BaseModel):
    session_id: str = Field(description="Identificador da sessao de conversa.")
    estado_contexto: str = Field(description="Contexto geografico usado nesta resposta.")
    reply: str = Field(description="Resposta textual do agente.")
    charts: list[ChartSpec] = Field(
        default_factory=list,
        description="Graficos oficiais gerados nesta rodada (ChartSpec).",
    )
    tools_used: list[str] = Field(
        default_factory=list,
        description="Nomes das tools invocadas nesta rodada.",
    )
