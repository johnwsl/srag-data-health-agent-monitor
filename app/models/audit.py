from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentAuditRecord(BaseModel):
    audit_id: str = Field(description="Identificador unico do evento de auditoria.")
    created_at: str = Field(description="Timestamp UTC ISO-8601 do evento.")
    kind: Literal["chat", "report"] = Field(description="Tipo de operacao auditada.")
    session_id: str = Field(description="Sessao/thread associada a execucao.")
    estado_contexto: str = Field(description="Escopo geografico associado.")
    user_message: str = Field(description="Mensagem do usuario (ou pedido de relatorio).")
    reply: str = Field(description="Resposta textual do agente nesta rodada.")
    tools_used: list[str] = Field(
        default_factory=list,
        description="Nomes das tools invocadas neste turno.",
    )
    tool_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Detalhes das tools: nome, args e preview do resultado.",
    )
    report_generated: bool = Field(
        default=False,
        description="True se um relatorio executivo foi gerado nesta rodada.",
    )
    charts_count: int = Field(default=0, description="Quantidade de charts produzidos.")
    duration_ms: float = Field(description="Duracao da execucao em milissegundos.")
    status: Literal["ok", "error"] = Field(description="Status da execucao.")
    error_message: str | None = Field(
        default=None,
        description="Mensagem de erro, quando status=error.",
    )


class AgentAuditListResponse(BaseModel):
    total: int = Field(description="Total de registros retornados (apos filtros).")
    items: list[AgentAuditRecord] = Field(default_factory=list)


class AgentAuditSessionResponse(BaseModel):
    session_id: str
    total: int
    items: list[AgentAuditRecord] = Field(default_factory=list)
