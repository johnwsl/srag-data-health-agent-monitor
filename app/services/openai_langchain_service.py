import os
from collections.abc import Sequence
from typing import Any


class OpenAILangChainService:
    """Encapsula interacoes com um chat model da OpenAI via LangChain."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.temperature = (
            temperature if temperature is not None else float(os.getenv("OPENAI_TEMPERATURE", "0"))
        )

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY nao configurada.")

        self._client = self._build_client()

    def get_model(self):
        """Retorna o chat model LangChain (ex.: para LangGraph)."""
        return self._client

    def _build_client(self):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise ImportError(
                "Dependencia ausente. Instale 'langchain-openai' para usar OpenAILangChainService."
            ) from exc

        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
        )

    def ask(self, query: str, system_prompt: str | None = None) -> str:
        """Envia uma pergunta para a LLM e retorna apenas o texto da resposta."""
        messages = []

        if system_prompt:
            messages.append(("system", system_prompt))

        messages.append(("human", query))
        response = self._client.invoke(messages)
        return self._extract_text(response)

    def ask_messages(self, messages: Sequence[tuple[str, str]]) -> str:
        """Envia uma lista de mensagens no formato (role, content)."""
        response = self._client.invoke(list(messages))
        return self._extract_text(response)

    def run_with_tools(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tools: Sequence[Any],
        max_iterations: int = 8,
    ) -> str:
        """Executa um loop de tool calling ate a LLM responder sem novas tools."""
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
        except ImportError as exc:
            raise ImportError(
                "Dependencia ausente. Instale 'langchain-core' para usar run_with_tools()."
            ) from exc

        if not tools:
            return self.ask(user_prompt, system_prompt=system_prompt)

        llm_with_tools = self._client.bind_tools(list(tools))
        tool_map = {tool.name: tool for tool in tools}
        messages: list[Any] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        for _ in range(max_iterations):
            ai_message = llm_with_tools.invoke(messages)
            messages.append(ai_message)

            tool_calls = getattr(ai_message, "tool_calls", None) or []
            if not tool_calls:
                return self._extract_text(ai_message)

            if not isinstance(ai_message, AIMessage):
                messages[-1] = AIMessage(
                    content=getattr(ai_message, "content", ""),
                    tool_calls=tool_calls,
                )

            for tool_call in tool_calls:
                name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
                args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                call_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", name)

                tool = tool_map.get(name)
                if tool is None:
                    result = f"Tool desconhecida: {name}"
                else:
                    try:
                        result = tool.invoke(args or {})
                    except Exception as error:  # noqa: BLE001
                        result = f"Erro ao executar {name}: {error}"

                messages.append(
                    ToolMessage(
                        content=result if isinstance(result, str) else str(result),
                        tool_call_id=str(call_id),
                    )
                )

        return (
            "Nao foi possivel concluir o raciocinio com as ferramentas no limite de iteracoes. "
            "Tente novamente."
        )

    @staticmethod
    def _extract_text(response) -> str:
        content = getattr(response, "content", response)

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
