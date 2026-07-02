import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx
import plotly.graph_objects as go
from shiny import reactive
from shiny.express import input, render, ui
from shinywidgets import render_plotly

from shiny_app.constants import (
    API_BASE_URL,
    METRIC_LABELS,
    PIPELINE_TIMEOUT_SECONDS,
    SRAG_BRASIL_CODE,
    STATE_CHOICES,
)

ui.page_opts(
    title="",
    window_title="SRAG",
    fillable=True,
)

ui.tags.style(
    """
    .srag-main {
        max-width: 1100px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }
    .bslib-sidebar-layout > .navbar .navbar-brand {
        display: none;
    }
    .srag-header {
        margin-bottom: 1.25rem;
    }
    .srag-page-title {
        font-weight: 600;
        margin-bottom: 0.35rem;
        font-size: 1.75rem;
    }
    .srag-page-subtitle {
        color: #6c757d;
        margin-bottom: 0;
        font-size: 0.95rem;
    }
    .srag-error { color: #b02a37; font-weight: 500; margin-bottom: 0; }
    .srag-overlay {
        position: fixed;
        inset: 0;
        z-index: 9999;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 255, 255, 0.72);
        backdrop-filter: blur(2px);
    }
    .srag-overlay-message {
        background: #ffffff;
        border: 1px solid #b6d4fe;
        border-radius: 0.5rem;
        padding: 1.25rem 2rem;
        font-weight: 600;
        font-size: 1.125rem;
        color: #084298;
        box-shadow: 0 8px 32px rgba(13, 110, 253, 0.15);
    }
    .srag-loading {
        background: #e7f1ff;
        border: 1px solid #b6d4fe;
        border-radius: 0.5rem;
        padding: 1rem 1.25rem;
        color: #084298;
    }
    .srag-status-info {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem 1.5rem;
        align-items: center;
    }
    .srag-status-badge {
        display: inline-block;
        background: #e9ecef;
        border-radius: 999px;
        padding: 0.25rem 0.75rem;
        font-size: 0.875rem;
        font-weight: 600;
    }
    .srag-status-period {
        color: #495057;
        margin-bottom: 0;
    }
    .srag-metrics-table {
        margin-top: 1.25rem;
    }
    .srag-metrics-table .dataframe tbody td {
        font-size: 0.875rem;
        vertical-align: middle;
    }
    .srag-charts-section {
        margin-top: 1.25rem;
    }
    .srag-report-section {
        margin-top: 1.25rem;
    }
    .srag-report-text {
        white-space: pre-wrap;
        line-height: 1.5;
        color: #212529;
        margin-bottom: 0;
    }
    """
)

with ui.sidebar(title="Filtros", width=280):
    ui.input_select(
        "estado",
        "Estado / escopo",
        choices=STATE_CHOICES,
        selected="SP",
    )
    ui.input_action_button("gerar_relatorio", "Gerar relatório", class_="btn-primary")


pipeline_phase = reactive.Value("checking")
pipeline_error = reactive.Value("")
report_error = reactive.Value("")


def _api_url(path: str) -> str:
    return f"{API_BASE_URL.rstrip('/')}{path}"


def _fetch_pipeline_status() -> dict:
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(_api_url("/datasets/status"))
            response.raise_for_status()
            return {"ok": True, "data": response.json()}
    except httpx.HTTPStatusError as error:
        detail = error.response.text
        return {"ok": False, "error": f"HTTP {error.response.status_code}: {detail}"}
    except httpx.RequestError as error:
        return {"ok": False, "error": f"Falha ao conectar à API: {error}"}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": str(error)}


@reactive.extended_task
async def run_pipeline_task() -> dict:
    try:
        async with httpx.AsyncClient(timeout=PIPELINE_TIMEOUT_SECONDS) as client:
            response = await client.post(_api_url("/datasets/pipeline"))
            response.raise_for_status()
            return {"ok": True, "data": response.json()}
    except httpx.HTTPStatusError as error:
        detail = error.response.text
        return {"ok": False, "error": f"HTTP {error.response.status_code}: {detail}"}
    except httpx.RequestError as error:
        return {"ok": False, "error": f"Falha ao conectar à API: {error}"}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": str(error)}


@reactive.extended_task
async def generate_report_task(estado: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=PIPELINE_TIMEOUT_SECONDS) as client:
            response = await client.post(_api_url("/agents/report"), json={"estado": estado})
            response.raise_for_status()
            return {"ok": True, "data": response.json()}
    except httpx.HTTPStatusError as error:
        detail = error.response.text
        return {"ok": False, "error": f"HTTP {error.response.status_code}: {detail}"}
    except httpx.RequestError as error:
        return {"ok": False, "error": f"Falha ao conectar à API: {error}"}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": str(error)}


@reactive.calc
def pipeline_overlay_visible() -> bool:
    phase = pipeline_phase.get()
    if phase in ("checking", "loading"):
        return True
    if phase == "running":
        return run_pipeline_task.status() == "running"
    return False


@reactive.effect
def pipeline_orchestrator() -> None:
    phase = pipeline_phase.get()

    if phase == "checking":
        status = _fetch_pipeline_status()
        if not status["ok"]:
            pipeline_error.set(status["error"])
            pipeline_phase.set("error")
            return

        if status["data"]["ready"]:
            pipeline_phase.set("ready")
            return

        pipeline_phase.set("loading")
        return

    if phase == "loading":
        run_pipeline_task.invoke()
        pipeline_phase.set("running")
        return

    if phase == "running":
        task_status = run_pipeline_task.status()
        if task_status == "running":
            return

        if task_status == "success":
            result = run_pipeline_task.result()
            if result["ok"]:
                pipeline_phase.set("ready")
            else:
                pipeline_error.set(result["error"])
                pipeline_phase.set("error")
            return

        if task_status == "error":
            try:
                run_pipeline_task.result()
            except Exception as error:  # noqa: BLE001
                pipeline_error.set(str(error))
            pipeline_phase.set("error")


@reactive.calc
def metrics_payload() -> dict:
    if pipeline_phase.get() != "ready":
        return {"ok": False, "error": "Aguardando conclusão do pipeline."}
    estado = input.estado()
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(_api_url(f"/metrics/{estado}"))
            response.raise_for_status()
            return {"ok": True, "data": response.json()}
    except httpx.HTTPStatusError as error:
        detail = error.response.text
        return {"ok": False, "error": f"HTTP {error.response.status_code}: {detail}"}
    except httpx.RequestError as error:
        return {"ok": False, "error": f"Falha ao conectar à API: {error}"}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": str(error)}


def _fetch_series(path: str) -> dict:
    if pipeline_phase.get() != "ready":
        return {"ok": False, "error": "Aguardando conclusão do pipeline."}
    estado = input.estado()
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(_api_url(f"/metrics/{estado}{path}"))
            response.raise_for_status()
            return {"ok": True, "data": response.json()}
    except httpx.HTTPStatusError as error:
        detail = error.response.text
        return {"ok": False, "error": f"HTTP {error.response.status_code}: {detail}"}
    except httpx.RequestError as error:
        return {"ok": False, "error": f"Falha ao conectar à API: {error}"}
    except Exception as error:  # noqa: BLE001
        return {"ok": False, "error": str(error)}


@reactive.calc
def daily_cases_payload() -> dict:
    return _fetch_series("/casos-diarios")


@reactive.calc
def monthly_cases_payload() -> dict:
    return _fetch_series("/casos-mensais")


@reactive.effect
@reactive.event(input.gerar_relatorio)
def trigger_report_generation() -> None:
    if pipeline_phase.get() != "ready":
        report_error.set("Aguarde a conclusão do pipeline antes de gerar o relatório.")
        return

    report_error.set("")
    generate_report_task.invoke(input.estado())


def _format_rate(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "N/D"
    if signed:
        return f"{value:+.1f}%"
    return f"{value:.1f}%"


def _period_label(payload: dict) -> str:
    reference = payload["taxa_aumento_casos"]
    return (
        f"{reference['mes_anterior_mes']:02d}/{reference['mes_anterior_ano']} → "
        f"{reference['mes_atual_mes']:02d}/{reference['mes_atual_ano']}"
    )


def _build_metrics_rows(data: dict) -> list[dict[str, str]]:
    aumento = data["taxa_aumento_casos"]
    mortalidade = data["taxa_mortalidade"]
    uti = data["taxa_ocupacao_uti"]
    vacinacao = data["taxa_vacinacao_populacao"]

    return [
        {
            "métrica": METRIC_LABELS["taxa_aumento_casos"],
            "valor": _format_rate(aumento["taxa_aumento_percentual"], signed=True),
        },
        {
            "métrica": METRIC_LABELS["taxa_mortalidade"],
            "valor": _format_rate(mortalidade["taxa_mortalidade_percentual"]),
        },
        {
            "métrica": METRIC_LABELS["taxa_ocupacao_uti"],
            "valor": _format_rate(uti["taxa_ocupacao_uti_percentual"]),
        },
        {
            "métrica": METRIC_LABELS["taxa_vacinacao_populacao"],
            "valor": _format_rate(vacinacao["taxa_vacinacao_percentual"]),
        },
    ]


def _pipeline_overlay_ui():
    return ui.div(
        ui.div("Obtendo os dados - espere um momento...", class_="srag-overlay-message"),
        class_="srag-overlay",
    )


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color="#6c757d"),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(height=320, margin=dict(t=30, r=20, l=20, b=20))
    return fig


with ui.div():
    @render.ui
    def pipeline_overlay():
        if pipeline_overlay_visible():
            return _pipeline_overlay_ui()
        return ui.div(style="display: none;")


with ui.div(class_="srag-main"):
    with ui.div(class_="srag-header"):
        ui.h2("Monitor de Saúde SRAG", class_="srag-page-title")
        ui.p(
            "Indicadores dos dois últimos meses completos com dados disponíveis.",
            class_="srag-page-subtitle",
        )

    with ui.card(class_="srag-status-card"):
        @render.ui
        def pipeline_status_banner():
            if pipeline_phase.get() != "error":
                return ui.div()

            return ui.div(
                ui.strong("Não foi possível preparar os dados."),
                ui.p(pipeline_error.get(), class_="srag-error"),
                ui.p(
                    "Verifique se a API está em execução e tente recarregar a página.",
                    style="margin-bottom: 0;",
                ),
                class_="srag-loading",
            )

        @render.ui
        def status_banner():
            if pipeline_phase.get() != "ready":
                return ui.div()

            result = metrics_payload()
            if not result["ok"]:
                return ui.div(
                    ui.strong("Não foi possível carregar as métricas."),
                    ui.p(result["error"], class_="srag-error"),
                    ui.p(
                        "Verifique se a API está em execução e se o ETL foi concluído.",
                        style="margin-bottom: 0;",
                    ),
                )

            data = result["data"]
            return ui.div(
                ui.div(
                    ui.span(f"Escopo: {data['sg_uf_not']}", class_="srag-status-badge"),
                    ui.p(
                        f"Período analisado: {_period_label(data)}",
                        class_="srag-status-period",
                    ),
                    class_="srag-status-info",
                ),
            )

    with ui.card(class_="srag-metrics-table"):
        @render.data_frame
        def metrics_table():
            import pandas as pd

            result = metrics_payload()
            if not result["ok"]:
                return pd.DataFrame({"mensagem": [result["error"]]})

            return pd.DataFrame(_build_metrics_rows(result["data"]))

    with ui.div(class_="srag-charts-section"):
        with ui.layout_columns(col_widths=(6, 6)):
            with ui.card(full_screen=True):
                ui.card_header("Casos diários (últimos 30 dias)")

                @render_plotly
                def chart_casos_diarios():
                    result = daily_cases_payload()
                    if not result["ok"]:
                        return _empty_figure("Sem dados para exibir.")

                    pontos = result["data"]["pontos"]
                    fig = go.Figure(
                        data=[
                            go.Scatter(
                                x=[point["data"] for point in pontos],
                                y=[point["total_casos"] for point in pontos],
                                mode="lines+markers",
                                line=dict(color="#0d6efd", width=2),
                                marker=dict(size=5),
                                name="Casos",
                            )
                        ]
                    )
                    fig.update_layout(
                        height=320,
                        margin=dict(t=20, r=20, l=20, b=20),
                        xaxis_title="Data",
                        yaxis_title="Casos",
                        showlegend=False,
                    )
                    return fig

            with ui.card(full_screen=True):
                ui.card_header("Casos mensais (últimos 12 meses)")

                @render_plotly
                def chart_casos_mensais():
                    result = monthly_cases_payload()
                    if not result["ok"]:
                        return _empty_figure("Sem dados para exibir.")

                    pontos = result["data"]["pontos"]
                    labels = [f"{point['mes']:02d}/{point['ano']}" for point in pontos]
                    fig = go.Figure(
                        data=[
                            go.Bar(
                                x=labels,
                                y=[point["total_casos"] for point in pontos],
                                marker_color="#198754",
                                name="Casos",
                            )
                        ]
                    )
                    fig.update_layout(
                        height=320,
                        margin=dict(t=20, r=20, l=20, b=20),
                        xaxis_title="Mês",
                        yaxis_title="Casos",
                        showlegend=False,
                    )
                    return fig

    with ui.card(class_="srag-report-section"):
        ui.card_header("Relatório gerado por IA")

        @render.ui
        def report_panel():
            if pipeline_phase.get() != "ready":
                return ui.p("Aguarde a preparação dos dados para gerar o relatório.", class_="srag-page-subtitle")

            if report_error.get():
                return ui.p(report_error.get(), class_="srag-error")

            task_status = generate_report_task.status()
            if task_status == "initial":
                return ui.p(
                    "Clique em 'Gerar relatório' para produzir um resumo executivo do estado selecionado.",
                    class_="srag-page-subtitle",
                )

            if task_status == "running":
                return ui.div(
                    ui.strong("Gerando relatório..."),
                    ui.p("A IA está consolidando dados oficiais e notícias recentes.", style="margin-bottom: 0;"),
                    class_="srag-loading",
                )

            if task_status == "success":
                result = generate_report_task.result()
                if not result["ok"]:
                    return ui.p(result["error"], class_="srag-error")
                return ui.p(result["data"]["resumo_executivo"], class_="srag-report-text")

            if task_status == "error":
                try:
                    generate_report_task.result()
                except Exception as error:  # noqa: BLE001
                    return ui.p(str(error), class_="srag-error")

            return ui.p("Não foi possível gerar o relatório.", class_="srag-error")
