import uuid
from typing import Any

from app.models.chart import ChartSpec
from app.services.agent_tools import build_srag_agent_tools
from app.services.chart_spec_service import ChartSpecService
from app.services.openai_langchain_service import OpenAILangChainService
from app.services.srag_metrics_api_service import SragMetricsApiLangChainService
from app.services.tavily_news_service import TavilyNewsLangChainService


class SragChatAgent:
    """Chatbot autonomo de SRAG orquestrado com LangGraph (create_react_agent)."""

    SYSTEM_PROMPT = (
        "Voce e um assistente analitico de saude publica especializado em SRAG no Brasil. "
        "Converse com analistas de forma objetiva, em portugues. "
        "Use as ferramentas disponiveis para obter dados oficiais e noticias; nao invente numeros. "
        "Quando fizer sentido, chame gerar_especificacao_grafico para produzir graficos oficiais. "
        "Importante sobre vies temporal: dados recentes sofrem atraso de digitacao/notificacao. "
        "Nao interprete queda abrupta no fim da serie como reducao real sem mencionar incompleteness. "
        "Se a pergunta estiver fora de SRAG/saude respiratoria no Brasil, recuse educadamente. "
        "Separe claramente dados oficiais de noticias quando ambos aparecerem na resposta."
    )

    def __init__(
        self,
        llm_service: OpenAILangChainService | None = None,
        metrics_service: SragMetricsApiLangChainService | None = None,
        news_service: TavilyNewsLangChainService | None = None,
        chart_spec_service: ChartSpecService | None = None,
        checkpointer=None,
        graph=None,
    ) -> None:
        self.llm_service = llm_service or OpenAILangChainService()
        self.metrics_service = metrics_service or SragMetricsApiLangChainService()
        self.news_service = news_service or TavilyNewsLangChainService()
        self.chart_spec_service = chart_spec_service or ChartSpecService()
        self._checkpointer = checkpointer
        self._graph = graph

    def _get_checkpointer(self):
        if self._checkpointer is None:
            try:
                from langgraph.checkpoint.memory import MemorySaver
            except ImportError as exc:
                raise ImportError(
                    "Dependencia ausente. Instale 'langgraph' para usar SragChatAgent."
                ) from exc
            self._checkpointer = MemorySaver()
        return self._checkpointer

    def _build_graph(self):
        try:
            from langgraph.prebuilt import create_react_agent
        except ImportError as exc:
            raise ImportError(
                "Dependencia ausente. Instale 'langgraph' para usar SragChatAgent."
            ) from exc

        tools = build_srag_agent_tools(
            self.metrics_service,
            self.news_service,
            self.chart_spec_service,
        )
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
        # Preserva ordem e remove duplicatas consecutivas excessivas mantendo unica ocorrencia.
        seen: set[str] = set()
        ordered: list[str] = []
        for name in used:
            if name not in seen:
                seen.add(name)
                ordered.append(name)
        return ordered

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

        estado = (estado_contexto or "BRASIL").strip().upper()
        thread_id = (session_id or "").strip() or self._new_session_id()

        pipeline_status = self.metrics_service.ensure_pipeline_ready()
        self.chart_spec_service.reset_generated_charts()

        human_content = (
            f"[Contexto geografico padrao: {estado}]\n"
            f"[Status da pipeline: {pipeline_status}]\n\n"
            f"{texto}"
        )

        graph = self._get_graph()
        result = graph.invoke(
            {"messages": [{"role": "user", "content": human_content}]},
            config={"configurable": {"thread_id": thread_id}},
        )

        messages = list(result.get("messages") or [])
        reply = ""
        for message_item in reversed(messages):
            message_type = getattr(message_item, "type", None)
            if message_type == "ai" and not (getattr(message_item, "tool_calls", None) or []):
                reply = self._extract_text(getattr(message_item, "content", ""))
                break
            if message_type == "ai" and not reply:
                reply = self._extract_text(getattr(message_item, "content", ""))

        charts: list[ChartSpec] = list(self.chart_spec_service.generated_charts)
        tools_used = self._extract_tools_used(messages)

        return {
            "session_id": thread_id,
            "estado_contexto": estado,
            "reply": reply.strip() or "Nao foi possivel gerar uma resposta nesta rodada.",
            "charts": charts,
            "tools_used": tools_used,
        }
