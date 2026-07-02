from datetime import date
from pydantic import BaseModel, Field


class CaseIncreaseRateMetric(BaseModel):
    sg_uf_not: str = Field(description="Sigla da UF ou BRASIL para todo o Brasil.")
    mes_atual_ano: int = Field(description="Ano do último mês completo considerado.")
    mes_atual_mes: int = Field(description="Número do último mês completo considerado.")
    mes_anterior_ano: int = Field(description="Ano do mês completo imediatamente anterior.")
    mes_anterior_mes: int = Field(description="Número do mês completo imediatamente anterior.")
    casos_mes_atual: int = Field(description="Total de casos no último mês completo.")
    casos_mes_anterior: int = Field(description="Total de casos no mês completo anterior.")
    taxa_aumento_percentual: float | None = Field(
        description="Variação percentual entre os dois meses. None se o mês anterior teve 0 casos."
    )


class MortalityRateMetric(BaseModel):
    sg_uf_not: str = Field(description="Sigla da UF ou BRASIL para todo o Brasil.")
    mes_atual_ano: int = Field(description="Ano do último mês completo considerado.")
    mes_atual_mes: int = Field(description="Número do último mês completo considerado.")
    mes_anterior_ano: int = Field(description="Ano do mês completo imediatamente anterior.")
    mes_anterior_mes: int = Field(description="Número do mês completo imediatamente anterior.")
    total_casos_2_meses: int = Field(description="Total de casos notificados nos dois meses completos.")
    total_obitos_2_meses: int = Field(description="Total de óbitos (EVOLUCAO = 2) nos dois meses completos.")
    taxa_mortalidade_percentual: float | None = Field(
        description="Letalidade no período. None se não houver casos nos dois meses."
    )


class UtiOccupancyRateMetric(BaseModel):
    sg_uf_not: str = Field(description="Sigla da UF ou BRASIL para todo o Brasil.")
    mes_atual_ano: int = Field(description="Ano do último mês completo considerado.")
    mes_atual_mes: int = Field(description="Número do último mês completo considerado.")
    mes_anterior_ano: int = Field(description="Ano do mês completo imediatamente anterior.")
    mes_anterior_mes: int = Field(description="Número do mês completo imediatamente anterior.")
    total_casos_2_meses: int = Field(description="Total de casos notificados nos dois meses completos.")
    casos_com_uti_2_meses: int = Field(description="Total de casos com UTI = 1 nos dois meses completos.")
    taxa_ocupacao_uti_percentual: float | None = Field(
        description="Taxa de ocupação de UTI no período. None se não houver casos nos dois meses."
    )


class CovidVaccinationRateMetric(BaseModel):
    sg_uf_not: str = Field(description="Sigla da UF ou BRASIL para todo o Brasil.")
    mes_atual_ano: int = Field(description="Ano do último mês completo considerado.")
    mes_atual_mes: int = Field(description="Número do último mês completo considerado.")
    mes_anterior_ano: int = Field(description="Ano do mês completo imediatamente anterior.")
    mes_anterior_mes: int = Field(description="Número do mês completo imediatamente anterior.")
    total_casos_2_meses: int = Field(description="Total de casos notificados nos dois meses completos.")
    casos_vacinados_2_meses: int = Field(
        description="Total de casos com VACINA_COV = 1 nos dois meses completos."
    )
    taxa_vacinacao_percentual: float | None = Field(
        description="Taxa de vacinação COVID no período. None se não houver casos nos dois meses."
    )


class SRAGMetricsResponse(BaseModel):
    sg_uf_not: str = Field(description="Sigla da UF ou BRASIL para todo o Brasil.")
    taxa_aumento_casos: CaseIncreaseRateMetric = Field(description="Taxa de aumento de casos.")
    taxa_mortalidade: MortalityRateMetric = Field(description="Taxa de mortalidade.")
    taxa_ocupacao_uti: UtiOccupancyRateMetric = Field(description="Taxa de ocupação de UTI.")
    taxa_vacinacao_populacao: CovidVaccinationRateMetric = Field(
        description="Taxa de vacinação da população."
    )


class DailyCasePoint(BaseModel):
    data: date = Field(description="Data da notificação.")
    total_casos: int = Field(description="Total de casos notificados no dia.")


class DailyCasesSeriesResponse(BaseModel):
    sg_uf_not: str = Field(description="Sigla da UF ou BRASIL para todo o Brasil.")
    data_inicio: date = Field(description="Primeiro dia da série (inclusivo).")
    data_fim: date = Field(description="Último dia da série (inclusivo).")
    pontos: list[DailyCasePoint] = Field(description="Contagem diária de casos.")


class MonthlyCasePoint(BaseModel):
    ano: int = Field(description="Ano de notificação.")
    mes: int = Field(description="Mês de notificação.")
    total_casos: int = Field(description="Total de casos notificados no mês.")


class MonthlyCasesSeriesResponse(BaseModel):
    sg_uf_not: str = Field(description="Sigla da UF ou BRASIL para todo o Brasil.")
    pontos: list[MonthlyCasePoint] = Field(description="Contagem mensal de casos.")
