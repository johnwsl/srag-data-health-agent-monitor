import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import httpx
from shiny import reactive
from shiny.express import input, render, ui

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
    """
)

with ui.sidebar(title="Filtros", width=280):
    ui.input_select(
        "estado",
        "Estado / escopo",
        choices=STATE_CHOICES,
        selected=SRAG_BRASIL_CODE,
    )


pipeline_phase = reactive.Value("checking")
pipeline_error = reactive.Value("")


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
