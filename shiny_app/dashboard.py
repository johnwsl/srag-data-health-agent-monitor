import sys
import uuid
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
    .srag-report-charts {
        margin-top: 1rem;
    }
    .srag-report-caveat {
        color: #6c757d;
        font-size: 0.85rem;
        margin-top: 0.5rem;
        margin-bottom: 0;
    }
    .srag-chat-section {
        margin-top: 1.25rem;
    }
    .srag-chat-log {
        max-height: 360px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        margin-bottom: 1rem;
    }
    .srag-chat-bubble {
        border-radius: 0.5rem;
        padding: 0.75rem 1rem;
        line-height: 1.45;
        white-space: pre-wrap;
    }
    .srag-chat-user {
        background: #e7f1ff;
        border: 1px solid #b6d4fe;
        align-self: flex-end;
        max-width: 85%;
    }
    .srag-chat-assistant {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        align-self: flex-start;
        max-width: 95%;
    }
    .srag-chat-meta {
        color: #6c757d;
        font-size: 0.8rem;
        margin-top: 0.35rem;
        margin-bottom: 0;
    }
    .srag-chat-tools {
        font-size: 0.8rem;
        color: #495057;
        margin-top: 0.35rem;
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
    ui.input_action_button("gerar_relatorio", "Gerar Relatório por IA", class_="btn-primary")
    ui.input_action_button("nova_conversa", "Nova conversa do chat", class_="btn-outline-secondary")


pipeline_phase = reactive.Value("checking")
pipeline_error = reactive.Value("")
report_error = reactive.Value("")
chat_session_id = reactive.Value(str(uuid.uuid4()))
chat_messages = reactive.Value([])
chat_charts = reactive.Value([])
chat_error = reactive.Value("")
chat_tools_used = reactive.Value([])
chat_awaiting_reply = reactive.Value(False)


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


@reactive.extended_task
async def chat_task(session_id: str, estado: str, message: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=PIPELINE_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _api_url("/agents/chat"),
                json={
                    "session_id": session_id,
                    "estado_contexto": estado,
                    "message": message,
                },
            )
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


@reactive.effect
@reactive.event(input.nova_conversa)
def reset_chat_session() -> None:
    chat_session_id.set(str(uuid.uuid4()))
    chat_messages.set([])
    chat_charts.set([])
    chat_tools_used.set([])
    chat_error.set("")
    chat_awaiting_reply.set(False)


@reactive.effect
@reactive.event(input.enviar_chat)
def trigger_chat_message() -> None:
    if pipeline_phase.get() != "ready":
        chat_error.set("Aguarde a conclusão do pipeline antes de usar o chat.")
        return

    if chat_awaiting_reply.get() or chat_task.status() == "running":
        chat_error.set("Aguarde a resposta atual do chatbot.")
        return

    message = (input.chat_message() or "").strip()
    if not message:
        chat_error.set("Digite uma mensagem para o chatbot.")
        return

    chat_error.set("")
    history = list(chat_messages.get())
    history.append({"role": "user", "content": message})
    chat_messages.set(history)
    chat_awaiting_reply.set(True)
    ui.update_text_area("chat_message", value="")
    chat_task.invoke(chat_session_id.get(), input.estado(), message)


@reactive.effect
def consume_chat_task_result() -> None:
    if not chat_awaiting_reply.get():
        return
    if chat_task.status() == "running":
        return
    if chat_task.status() != "success":
        if chat_task.status() == "error":
            chat_awaiting_reply.set(False)
            try:
                chat_task.result()
            except Exception as error:  # noqa: BLE001
                chat_error.set(str(error))
        return

    result = chat_task.result()
    chat_awaiting_reply.set(False)
    if not result["ok"]:
        chat_error.set(result["error"])
        return

    data = result["data"]
    if data.get("session_id"):
        chat_session_id.set(data["session_id"])

    history = list(chat_messages.get())
    history.append(
        {
            "role": "assistant",
            "content": data.get("reply") or "",
            "tools_used": data.get("tools_used") or [],
        }
    )
    chat_messages.set(history)
    chat_charts.set(data.get("charts") or [])
    chat_tools_used.set(data.get("tools_used") or [])


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


def _find_report_chart(chart_id: str) -> dict | None:
    if generate_report_task.status() != "success":
        return None
    result = generate_report_task.result()
    if not result.get("ok"):
        return None
    charts = result.get("data", {}).get("charts") or []
    for chart in charts:
        if chart.get("id") == chart_id:
            return chart
    return None


def _find_chat_chart(chart_id: str) -> dict | None:
    charts = chat_charts.get() or []
    for chart in charts:
        if chart.get("id") == chart_id:
            return chart
    return None


def _figure_from_chart_spec(chart: dict | None, empty_message: str) -> go.Figure:
    if not chart:
        return _empty_figure(empty_message)

    data = chart.get("data") or []
    x_field = chart.get("x", {}).get("field", "x")
    y_field = chart.get("y", {}).get("field", "y")
    x_label = chart.get("x", {}).get("label", "")
    y_label = chart.get("y", {}).get("label", "")
    xs = [point.get(x_field) for point in data]
    ys = [point.get(y_field) for point in data]

    if chart.get("type") == "bar":
        fig = go.Figure(
            data=[
                go.Bar(
                    x=xs,
                    y=ys,
                    marker_color="#198754",
                    name=y_label or "Casos",
                )
            ]
        )
    else:
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=xs,
                    y=ys,
                    mode="lines+markers",
                    line=dict(color="#0d6efd", width=2),
                    marker=dict(size=5),
                    name=y_label or "Casos",
                )
            ]
        )

    fig.update_layout(
        title=dict(text=chart.get("title") or "", font=dict(size=14)),
        height=320,
        margin=dict(t=40, r=20, l=20, b=20),
        xaxis_title=x_label,
        yaxis_title=y_label,
        showlegend=False,
    )
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
                        f"Período analisado (para o cálculo das métricas): {_period_label(data)}",
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
                    "Clique em 'Gerar Relatório por IA' para produzir um resumo executivo do estado selecionado.",
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

                charts = result["data"].get("charts") or []
                caveat = next((chart.get("caveat") for chart in charts if chart.get("caveat")), None)
                children = [
                    ui.div(
                        ui.markdown(result["data"]["resumo_executivo"]),
                        class_="srag-report-text",
                    )
                ]
                if caveat:
                    children.append(ui.p(caveat, class_="srag-report-caveat"))
                return ui.div(*children)

            if task_status == "error":
                try:
                    generate_report_task.result()
                except Exception as error:  # noqa: BLE001
                    return ui.p(str(error), class_="srag-error")

            return ui.p("Não foi possível gerar o relatório.", class_="srag-error")

        with ui.div(class_="srag-report-charts"):
            with ui.layout_columns(col_widths=(6, 6)):
                with ui.card(full_screen=True):
                    ui.card_header("Gráfico do relatório — casos diários")

                    @render_plotly
                    def report_chart_casos_diarios():
                        return _figure_from_chart_spec(
                            _find_report_chart("casos_diarios"),
                            "Gere o relatório para visualizar o gráfico diário.",
                        )

                with ui.card(full_screen=True):
                    ui.card_header("Gráfico do relatório — casos mensais")

                    @render_plotly
                    def report_chart_casos_mensais():
                        return _figure_from_chart_spec(
                            _find_report_chart("casos_mensais"),
                            "Gere o relatório para visualizar o gráfico mensal.",
                        )

    with ui.card(class_="srag-chat-section"):
        ui.card_header("Chatbot SRAG (LangGraph)")

        @render.ui
        def chat_panel():
            if pipeline_phase.get() != "ready":
                return ui.p("Aguarde a preparação dos dados para usar o chatbot.", class_="srag-page-subtitle")

            bubbles = []
            for item in chat_messages.get():
                role = item.get("role")
                css = "srag-chat-bubble srag-chat-user" if role == "user" else "srag-chat-bubble srag-chat-assistant"
                label = "Você" if role == "user" else "Assistente"
                children = [ui.strong(label), ui.p(item.get("content") or "", style="margin-bottom: 0;")]
                tools = item.get("tools_used") or []
                if tools:
                    children.append(ui.p(f"Tools: {', '.join(tools)}", class_="srag-chat-tools"))
                bubbles.append(ui.div(*children, class_=css))

            if chat_awaiting_reply.get() or chat_task.status() == "running":
                bubbles.append(
                    ui.div(
                        ui.strong("Assistente"),
                        ui.p("Consultando tools e gerando resposta...", style="margin-bottom: 0;"),
                        class_="srag-chat-bubble srag-chat-assistant srag-loading",
                    )
                )

            body = []
            if not bubbles:
                body.append(
                    ui.p(
                        "Pergunte sobre métricas, tendências ou peça um gráfico. "
                        "O contexto geográfico segue o estado selecionado no filtro.",
                        class_="srag-page-subtitle",
                    )
                )
            else:
                body.append(ui.div(*bubbles, class_="srag-chat-log"))

            if chat_error.get():
                body.append(ui.p(chat_error.get(), class_="srag-error"))

            body.append(ui.p(f"Sessão: {chat_session_id.get()}", class_="srag-chat-meta"))
            return ui.div(*body)

        ui.input_text_area(
            "chat_message",
            label="Mensagem",
            placeholder="Ex.: Compare mortalidade e UTI em SP e mostre o gráfico mensal",
            rows=3,
            width="100%",
        )
        ui.input_action_button("enviar_chat", "Enviar mensagem", class_="btn-primary")

        with ui.div(class_="srag-report-charts"):
            with ui.layout_columns(col_widths=(6, 6)):
                with ui.card(full_screen=True):
                    ui.card_header("Gráfico do chat — casos diários")

                    @render_plotly
                    def chat_chart_casos_diarios():
                        return _figure_from_chart_spec(
                            _find_chat_chart("casos_diarios"),
                            "Peça um gráfico diário no chat para visualizar aqui.",
                        )

                with ui.card(full_screen=True):
                    ui.card_header("Gráfico do chat — casos mensais")

                    @render_plotly
                    def chat_chart_casos_mensais():
                        return _figure_from_chart_spec(
                            _find_chat_chart("casos_mensais"),
                            "Peça um gráfico mensal no chat para visualizar aqui.",
                        )
