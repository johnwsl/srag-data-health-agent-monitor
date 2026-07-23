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
    PIPELINE_TIMEOUT_SECONDS,
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
        padding: 1.25rem 1rem 2rem;
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
        margin-top: 0.5rem;
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
    .srag-chat-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 0.75rem;
    }
    """
)

ui.tags.script(
    """
    (() => {
      const scrollChatToBottom = () => {
        const log = document.getElementById("srag-chat-log");
        if (!log) return;
        log.scrollTop = log.scrollHeight;
      };

      const scheduleScroll = () => {
        requestAnimationFrame(() => {
          scrollChatToBottom();
          // Segundo passe apos layout do Shiny/Plotly.
          setTimeout(scrollChatToBottom, 50);
        });
      };

      const observer = new MutationObserver(scheduleScroll);
      const start = () => {
        observer.observe(document.body, { childList: true, subtree: true });
        scheduleScroll();
      };

      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
      } else {
        start();
      }
    })();
    """
)

pipeline_phase = reactive.Value("checking")
pipeline_error = reactive.Value("")
report_data = reactive.Value(None)
report_generating = reactive.Value(False)
chat_session_id = reactive.Value(str(uuid.uuid4()))
chat_messages = reactive.Value([])
chat_error = reactive.Value("")
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
async def chat_task(session_id: str, message: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=PIPELINE_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _api_url("/agents/chat"),
                json={
                    "session_id": session_id,
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


@reactive.effect
@reactive.event(input.nova_conversa)
def reset_chat_session() -> None:
    chat_session_id.set(str(uuid.uuid4()))
    chat_messages.set([])
    chat_error.set("")
    chat_awaiting_reply.set(False)
    report_generating.set(False)


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
    lowered = message.casefold()
    report_generating.set(
        any(
            hint in lowered
            for hint in ("relatório", "relatorio", "resumo executivo", "painel completo")
        )
    )
    ui.update_text_area("chat_message", value="")
    chat_task.invoke(chat_session_id.get(), message)


@reactive.effect
def consume_chat_task_result() -> None:
    if not chat_awaiting_reply.get():
        return
    if chat_task.status() == "running":
        return
    if chat_task.status() != "success":
        if chat_task.status() == "error":
            chat_awaiting_reply.set(False)
            report_generating.set(False)
            try:
                chat_task.result()
            except Exception as error:  # noqa: BLE001
                chat_error.set(str(error))
        return

    result = chat_task.result()
    chat_awaiting_reply.set(False)
    report_generating.set(False)
    if not result["ok"]:
        chat_error.set(result["error"])
        return

    data = result["data"]
    if data.get("session_id"):
        chat_session_id.set(data["session_id"])

    tools = data.get("tools_used") or []
    # So atualiza a secao de relatorio quando um novo report veio nesta rodada.
    if data.get("report"):
        report_data.set(data["report"])

    history = list(chat_messages.get())
    history.append(
        {
            "role": "assistant",
            "content": data.get("reply") or "",
            "tools_used": tools,
        }
    )
    chat_messages.set(history)


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
    report = report_data.get()
    if not report:
        return None
    charts = report.get("charts") or []
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
        ui.h2("Agente Chatbot - Monitor de Saúde SRAG", class_="srag-page-title")
        ui.p(
            "Peça análises ou um relatório executivo no chatbot — informe uma UF (ex.: SP, Pernambuco e etc.) ou Brasil.",
            class_="srag-page-subtitle",
        )

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

    with ui.card(class_="srag-chat-section"):
        ui.card_header("Chatbot")

        @render.ui
        def chat_panel():
            if pipeline_phase.get() != "ready":
                return ui.p(
                    "Aguarde a preparação dos dados para usar o chatbot.",
                    class_="srag-page-subtitle",
                )

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
                        "Pergunte sobre métricas/tendências ou peça um relatório executivo "
                        "citando a UF (ex.: SP, Pernambuco e etc.) ou Brasil. O relatório completo aparece na seção abaixo.",
                        class_="srag-page-subtitle",
                    )
                )
            else:
                body.append(ui.div(*bubbles, class_="srag-chat-log", id="srag-chat-log"))

            if chat_error.get():
                body.append(ui.p(chat_error.get(), class_="srag-error"))

            body.append(ui.p(f"Sessão: {chat_session_id.get()}", class_="srag-chat-meta"))
            return ui.div(*body)

        ui.input_text_area(
            "chat_message",
            label="Mensagem",
            placeholder='Ex.: "Gere o relatório executivo de SP" ou "Como está a mortalidade no Brasil?"',
            rows=3,
            width="100%",
        )
        with ui.div(class_="srag-chat-actions"):
            ui.input_action_button("enviar_chat", "Enviar mensagem", class_="btn-primary")
            ui.input_action_button("nova_conversa", "Nova conversa", class_="btn-outline-secondary")

    with ui.card(class_="srag-report-section"):
        ui.card_header("Relatório gerado por IA")

        @render.ui
        def report_panel():
            if pipeline_phase.get() != "ready":
                return ui.p(
                    "Aguarde a preparação dos dados para gerar o relatório.",
                    class_="srag-page-subtitle",
                )

            if report_generating.get():
                loading = ui.div(
                    ui.strong("Gerando relatório..."),
                    ui.p(
                        "A IA está consolidando dados oficiais e notícias recentes.",
                        style="margin-bottom: 0;",
                    ),
                    class_="srag-loading",
                )
                report = report_data.get()
                if not report:
                    return loading
                # Mantem o relatorio anterior visivel enquanto um novo e gerado.
                charts = report.get("charts") or []
                caveat = next((chart.get("caveat") for chart in charts if chart.get("caveat")), None)
                children = [
                    loading,
                    ui.div(
                        ui.markdown(report.get("resumo_executivo") or ""),
                        class_="srag-report-text",
                        style="margin-top: 1rem;",
                    ),
                ]
                if caveat:
                    children.append(ui.p(caveat, class_="srag-report-caveat"))
                return ui.div(*children)

            report = report_data.get()
            if not report:
                return ui.p(
                    "Peça um relatório no chatbot (ex.: \"Gere o relatório executivo de SP\" "
                    "ou \"Resumo executivo do Brasil\"). O texto completo aparece aqui, não no chat.",
                    class_="srag-page-subtitle",
                )

            charts = report.get("charts") or []
            caveat = next((chart.get("caveat") for chart in charts if chart.get("caveat")), None)
            children = [
                ui.div(
                    ui.markdown(report.get("resumo_executivo") or ""),
                    class_="srag-report-text",
                )
            ]
            if caveat:
                children.append(ui.p(caveat, class_="srag-report-caveat"))
            return ui.div(*children)

        with ui.div(class_="srag-report-charts"):
            with ui.layout_columns(col_widths=(6, 6)):
                with ui.card(full_screen=True):
                    ui.card_header("Gráfico do relatório — casos diários (últimos 30 dias)")

                    @render_plotly
                    def report_chart_casos_diarios():
                        return _figure_from_chart_spec(
                            _find_report_chart("casos_diarios"),
                            "Peça um relatório no chatbot para visualizar o gráfico diário.",
                        )

                with ui.card(full_screen=True):
                    ui.card_header("Gráfico do relatório — casos mensais (últimos 12 meses)")

                    @render_plotly
                    def report_chart_casos_mensais():
                        return _figure_from_chart_spec(
                            _find_report_chart("casos_mensais"),
                            "Peça um relatório no chatbot para visualizar o gráfico mensal.",
                        )