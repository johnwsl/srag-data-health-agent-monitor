from pydantic import BaseModel, Field

from app.models.chart import ChartSpec


class ExecutiveSummaryRequest(BaseModel):
    estado: str = Field(description="Sigla da UF (ex.: SP, RJ) ou BRASIL.")


class ExecutiveSummaryResponse(BaseModel):
    estado: str = Field(description="Sigla da UF ou BRASIL consultado.")
    resumo_executivo: str = Field(description="Resumo executivo gerado pelo agente.")
    charts: list[ChartSpec] = Field(
        default_factory=list,
        description="Especificações de gráficos oficiais associados ao relatório.",
    )
