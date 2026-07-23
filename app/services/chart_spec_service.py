from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.models.chart import REPORT_NOTIFICATION_DELAY_CAVEAT, ChartAxisSpec, ChartSpec


class ChartToolInput(BaseModel):
    estado: str = Field(description="Sigla da UF (ex.: SP, RJ) ou BRASIL.")
    serie: Literal["diaria", "mensal"] = Field(
        description="Serie a plotar: 'diaria' (linha) ou 'mensal' (barras)."
    )


class ChartSpecService:
    """Monta ChartSpec a partir de payloads oficiais da API SRAG."""

    def __init__(self) -> None:
        self.generated_charts: list[ChartSpec] = []

    def reset_generated_charts(self) -> None:
        self.generated_charts = []

    def from_metrics_payload(self, payload: dict[str, Any]) -> list[ChartSpec]:
        estado = str(payload.get("sg_uf_not", "BRASIL")).upper()
        charts: list[ChartSpec] = []

        daily = payload.get("casos_diarios")
        if isinstance(daily, dict):
            charts.append(self.from_daily_cases(daily, estado=estado))

        monthly = payload.get("casos_mensais")
        if isinstance(monthly, dict):
            charts.append(self.from_monthly_cases(monthly, estado=estado))

        return charts

    def from_daily_cases(self, payload: dict[str, Any], estado: str | None = None) -> ChartSpec:
        scope = (estado or str(payload.get("sg_uf_not", "BRASIL"))).upper()
        pontos = payload.get("pontos") or []
        data = [
            {
                "data": str(point.get("data", "")),
                "casos": int(point.get("total_casos", 0) or 0),
            }
            for point in pontos
            if isinstance(point, dict)
        ]

        return ChartSpec(
            id="casos_diarios",
            type="line",
            title=f"Casos diários de SRAG — {scope}",
            x=ChartAxisSpec(field="data", label="Data"),
            y=ChartAxisSpec(field="casos", label="Notificações"),
            data=data,
            source=f"GET /metrics/{scope}/casos-diarios",
            caveat=REPORT_NOTIFICATION_DELAY_CAVEAT,
        )

    def from_monthly_cases(self, payload: dict[str, Any], estado: str | None = None) -> ChartSpec:
        scope = (estado or str(payload.get("sg_uf_not", "BRASIL"))).upper()
        pontos = payload.get("pontos") or []
        data = [
            {
                "label": f"{int(point.get('mes', 0)):02d}/{int(point.get('ano', 0))}",
                "casos": int(point.get("total_casos", 0) or 0),
            }
            for point in pontos
            if isinstance(point, dict)
        ]

        return ChartSpec(
            id="casos_mensais",
            type="bar",
            title=f"Casos mensais de SRAG — {scope}",
            x=ChartAxisSpec(field="label", label="Mês"),
            y=ChartAxisSpec(field="casos", label="Notificações"),
            data=data,
            source=f"GET /metrics/{scope}/casos-mensais",
            caveat=REPORT_NOTIFICATION_DELAY_CAVEAT,
        )

    def _remember_chart(self, chart: ChartSpec) -> ChartSpec:
        self.generated_charts = [item for item in self.generated_charts if item.id != chart.id]
        self.generated_charts.append(chart)
        return chart

    def as_tool(self, metrics_service):
        def gerar_especificacao_grafico(estado: str, serie: Literal["diaria", "mensal"]) -> str:
            scope = estado.strip().upper()
            try:
                if serie == "diaria":
                    payload = metrics_service.get_daily_cases(scope)
                    chart = self.from_daily_cases(payload, estado=scope)
                elif serie == "mensal":
                    payload = metrics_service.get_monthly_cases(scope)
                    chart = self.from_monthly_cases(payload, estado=scope)
                else:
                    return "Serie invalida. Use 'diaria' ou 'mensal'."
            except Exception as error:  # noqa: BLE001
                return f"Erro ao gerar especificacao de grafico: {error}"

            self._remember_chart(chart)
            return chart.model_dump_json()

        return StructuredTool.from_function(
            func=gerar_especificacao_grafico,
            name="gerar_especificacao_grafico",
            description=(
                "Gera a especificacao oficial (ChartSpec) de um grafico de SRAG para uma UF "
                "ou BRASIL. Use serie='diaria' para linha dos ultimos 30 dias ou "
                "serie='mensal' para barras dos ultimos 12 meses. Nao inventa dados."
            ),
            args_schema=ChartToolInput,
        )
