from typing import Any, Literal

from pydantic import BaseModel, Field

REPORT_NOTIFICATION_DELAY_CAVEAT = (
    "Períodos recentes podem estar incompletos por atraso de digitação/notificação; "
    "queda abrupta no fim da série não implica necessariamente redução real de casos."
)


class ChartAxisSpec(BaseModel):
    field: str = Field(description="Nome do campo nos pontos de data.")
    label: str = Field(description="Rótulo do eixo para exibição.")


class ChartSpec(BaseModel):
    id: str = Field(description="Identificador estável do gráfico (ex.: casos_diarios).")
    type: Literal["line", "bar"] = Field(description="Tipo de gráfico.")
    title: str = Field(description="Título do gráfico.")
    x: ChartAxisSpec = Field(description="Eixo X.")
    y: ChartAxisSpec = Field(description="Eixo Y.")
    data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Pontos plotáveis; chaves alinhadas a x.field e y.field.",
    )
    source: str = Field(description="Origem oficial dos dados (endpoint ou descrição).")
    caveat: str | None = Field(
        default=None,
        description="Aviso de interpretação (ex.: atraso de notificação).",
    )
