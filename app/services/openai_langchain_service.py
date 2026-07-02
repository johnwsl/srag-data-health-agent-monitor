import os
from collections.abc import Sequence


class OpenAILangChainService:
    """Encapsula interacoes simples com um chat model da OpenAI via LangChain."""

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
