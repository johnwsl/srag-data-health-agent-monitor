import json
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.config import SRAG_BRASIL_CODE, SRAG_STATE_CODES
from app.models.chart import ChartSpec
from app.services.agent_tools import build_srag_agent_tools
from app.services.chart_spec_service import ChartSpecService
from app.services.openai_langchain_service import OpenAILangChainService
from app.services.srag_metrics_api_service import SragMetricsApiLangChainService
from app.services.tavily_news_service import TavilyNewsLangChainService


class ReportToolInput(BaseModel):
    estado: str = Field(
        description="Sigla da UF (ex.: SP, RJ) ou BRASIL. Inferir a partir da mensagem do usuario."
    )


class SragLangGraphAgent:
    """Orquestrador unico LangGraph para chat e relatorio (tools + Tavily)."""

    SYSTEM_PROMPT = (
        "Voce e um assistente analitico de saude publica especializado em SRAG no Brasil. "
        "Use as ferramentas disponiveis para obter dados oficiais e noticias; nao invente numeros. "
        "Tools: consultar_metricas_srag, consultar_serie_temporal, gerar_especificacao_grafico, "
        "buscar_noticias_srag (Tavily) e gerar_relatorio_executivo. "
        "Identifique UF (sigla) ou BRASIL mencionados pelo usuario e use esse escopo nas tools. "
        "Nas respostas do chat que usem metricas oficiais, informe explicitamente o escopo "
        "(UF ou BRASIL) e o periodo analisado (ex.: 05/2026 -> 06/2026), usando os campos "
        "mes_anterior_* e mes_atual_* retornados pelas tools — nao invente o periodo. "
        "Se o usuario pedir relatorio, resumo executivo ou painel completo, chame "
        "gerar_relatorio_executivo com o estado correto. "
        "IMPORTANTE: NUNCA cole o texto completo do relatorio na resposta do chat. "
        "No chat, apenas confirme de forma breve que o relatorio foi gerado e sera exibido "
        "na secao 'Relatorio gerado por IA', mencionando escopo e periodo quando disponiveis. "
        "Para perguntas pontuais (sem pedido de relatorio), responda no chat com base nas tools. "
        "Importante sobre vies temporal: dados recentes sofrem atraso de digitacao/notificacao. "
        "Nao interprete queda abrupta no fim da serie como reducao real sem mencionar incompleteness. "
        "Se a pergunta estiver fora de SRAG/saude respiratoria no Brasil, recuse educadamente."
    )

    def __init__(
        self,
        llm_service: OpenAILangChainService | None = None,
        metrics_service: SragMetricsApiLangChainService | None = None,
        news_service: TavilyNewsLangChainService | None = None,
        chart_spec_service: ChartSpecService | None = None,
        checkpointer=None,
        graph=None,
        max_chars: int = 4000,
    ) -> None:
        self.llm_service = llm_service or OpenAILangChainService()
        self.metrics_service = metrics_service or SragMetricsApiLangChainService()
        self.news_service = news_service or TavilyNewsLangChainService()
        self.chart_spec_service = chart_spec_service or ChartSpecService()
        self._checkpointer = checkpointer
        self._graph = graph
        self.max_chars = max_chars
        self.last_report: dict[str, Any] | None = None

    def _get_checkpointer(self):
        if self._checkpointer is None:
            try:
                from langgraph.checkpoint.memory import MemorySaver
            except ImportError as exc:
                raise ImportError(
                    "Dependencia ausente. Instale 'langgraph' para usar SragLangGraphAgent."
                ) from exc
            self._checkpointer = MemorySaver()
        return self._checkpointer

    def _normalize_estado(self, estado: str) -> str:
        scope = (estado or SRAG_BRASIL_CODE).strip().upper()
        if scope != SRAG_BRASIL_CODE and scope not in SRAG_STATE_CODES:
            raise ValueError(f"UF invalida: {scope}. Use uma sigla valida ou BRASIL.")
        return scope

    def _compose_executive_report(self, estado: str) -> dict[str, Any]:
        scope = self._normalize_estado(estado)
        self.metrics_service.ensure_pipeline_ready()
        payload = self.metrics_service.get_full_metrics_data(scope)
        news_data = self.news_service.buscar_noticias()
        charts = self.chart_spec_service.from_metrics_payload(payload)
        self.chart_spec_service.generated_charts = list(charts)

        system_prompt = (
            "Voce e um analista de saude publica. Produza um resumo executivo em portugues, "
            "com no maximo 4000 caracteres, separando claramente 'Dados oficiais' e 'Noticias'. "
            "No inicio, informe o escopo (UF ou BRASIL) e o periodo analisado "
            "(mes_anterior -> mes_atual das metricas). "
            "Mostre as 4 metricas principais e tendencias. Nao invente dados. "
            "Mencione atraso de notificacao se a serie recente parecer incompleta."
        )
        user_prompt = (
            f"Estado consultado: {scope}\n\n"
            "Dados oficiais da API SRAG:\n"
            f"{json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
            "Noticias recentes coletadas:\n"
            f"{news_data}\n\n"
            "Escreva o resumo executivo solicitado."
        )
        text = self.llm_service.ask(user_prompt, system_prompt=system_prompt)
        return {
            "estado": scope,
            "resumo_executivo": self._limit_text(text),
            "charts": charts,
        }

    def _report_tool(self):
        try:
            from langchain_core.tools import StructuredTool
        except ImportError as exc:
            raise ImportError(
                "Dependencia ausente. Instale 'langchain-core' para usar gerar_relatorio_executivo."
            ) from exc

        def gerar_relatorio_executivo(estado: str) -> str:
            try:
                composed = self._compose_executive_report(estado)
            except ValueError as error:
                return str(error)
            except Exception as error:  # noqa: BLE001
                return f"Erro ao gerar relatorio executivo: {error}"

            self.last_report = {
                "estado": composed["estado"],
                "resumo_executivo": composed["resumo_executivo"],
                "charts": composed["charts"],
            }
            return (
                f"Relatorio executivo para {composed['estado']} gerado com sucesso. "
                "NAO cole o texto completo na resposta do chat. "
                "Confirme apenas que o relatorio esta disponivel na secao "
                "'Relatorio gerado por IA'."
            )

        return StructuredTool.from_function(
            func=gerar_relatorio_executivo,
            name="gerar_relatorio_executivo",
            description=(
                "Gera o relatorio executivo completo de SRAG para uma UF ou BRASIL. "
                "O texto completo sera exibido na secao Relatorio gerado por IA do dashboard; "
                "nao deve ser colado no chat."
            ),
            args_schema=ReportToolInput,
        )

    def _build_graph(self):
        try:
            from langgraph.prebuilt import create_react_agent
        except ImportError as exc:
            raise ImportError(
                "Dependencia ausente. Instale 'langgraph' para usar SragLangGraphAgent."
            ) from exc

        tools = [
            *build_srag_agent_tools(
                self.metrics_service,
                self.news_service,
                self.chart_spec_service,
            ),
            self._report_tool(),
        ]
        return create_react_agent(
            self.llm_service.get_model(),
            tools,
            prompt=self.SYSTEM_PROMPT,
            checkpointer=self._get_checkpointer(),
        )

    def _get_graph(self):
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    @staticmethod
    def _new_session_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part)
        return str(content)

    @staticmethod
    def _extract_tools_used(messages: list[Any]) -> list[str]:
        used: list[str] = []
        for message in messages:
            tool_calls = getattr(message, "tool_calls", None) or []
            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    name = tool_call.get("name")
                else:
                    name = getattr(tool_call, "name", None)
                if name:
                    used.append(str(name))

        seen: set[str] = set()
        ordered: list[str] = []
        for name in used:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

    def _limit_text(self, text: str) -> str:
        compact = text.strip()
        if len(compact) <= self.max_chars:
            return compact

        truncated = compact[: self.max_chars - 3].rstrip()
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        return f"{truncated}..."

    def _extract_reply(self, messages: list[Any]) -> str:
        reply = ""
        for message_item in reversed(messages):
            message_type = getattr(message_item, "type", None)
            if message_type == "ai" and not (getattr(message_item, "tool_calls", None) or []):
                reply = self._extract_text(getattr(message_item, "content", ""))
                break
            if message_type == "ai" and not reply:
                reply = self._extract_text(getattr(message_item, "content", ""))
        return reply.strip() or "Nao foi possivel gerar uma resposta nesta rodada."

    def _invoke(
        self,
        *,
        human_content: str,
        thread_id: str,
        estado: str,
    ) -> dict[str, Any]:
        pipeline_status = self.metrics_service.ensure_pipeline_ready()
        self.chart_spec_service.reset_generated_charts()

        content = (
            f"[Contexto geografico inicial: {estado}]\n"
            f"[Status da pipeline: {pipeline_status}]\n"
            "Identifique UF ou BRASIL na mensagem do usuario quando relevante.\n\n"
            f"{human_content}"
        )

        result = self._get_graph().invoke(
            {"messages": [{"role": "user", "content": content}]},
            config={"configurable": {"thread_id": thread_id}},
        )
        messages = list(result.get("messages") or [])

        return {
            "session_id": thread_id,
            "estado_contexto": estado,
            "reply": self._extract_reply(messages),
            "charts": list(self.chart_spec_service.generated_charts),
            "tools_used": self._extract_tools_used(messages),
        }

    def chat(
        self,
        message: str,
        *,
        session_id: str | None = None,
        estado_contexto: str = "BRASIL",
    ) -> dict[str, Any]:
        texto = (message or "").strip()
        if not texto:
            raise ValueError("A mensagem do chat nao pode ser vazia.")

        estado = (estado_contexto or SRAG_BRASIL_CODE).strip().upper()
        thread_id = (session_id or "").strip() or self._new_session_id()
        self.last_report = None

        result = self._invoke(human_content=texto, thread_id=thread_id, estado=estado)
        report = self.last_report
        if report is not None:
            result["estado_contexto"] = report["estado"]
            # Graficos do relatorio ficam apenas em result["report"], nao no chat.
            result["charts"] = []

        result["report"] = report
        return result

    def generate_executive_summary(self, estado: str) -> dict[str, Any]:
        composed = self._compose_executive_report(estado)
        return {
            "resumo_executivo": composed["resumo_executivo"],
            "charts": composed["charts"],
            "tools_used": ["gerar_relatorio_executivo"],
            "session_id": f"report-{composed['estado']}-{self._new_session_id()}",
        }
