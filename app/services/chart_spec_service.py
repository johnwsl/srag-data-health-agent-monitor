from typing import Any

from app.models.chart import REPORT_NOTIFICATION_DELAY_CAVEAT, ChartAxisSpec, ChartSpec


class ChartSpecService:
    """Monta ChartSpec a partir de payloads oficiais da API SRAG."""

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
