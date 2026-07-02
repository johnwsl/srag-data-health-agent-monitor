from pydantic import BaseModel, Field


class ExecutiveSummaryRequest(BaseModel):
    estado: str = Field(description="Sigla da UF (ex.: SP, RJ) ou BRASIL.")


class ExecutiveSummaryResponse(BaseModel):
    estado: str = Field(description="Sigla da UF ou BRASIL consultado.")
    resumo_executivo: str = Field(description="Resumo executivo gerado pelo agente.")
