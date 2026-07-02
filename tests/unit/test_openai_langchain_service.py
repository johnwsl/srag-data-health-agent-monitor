from types import SimpleNamespace

import pytest

from app.services.openai_langchain_service import OpenAILangChainService


class FakeChatOpenAI:
    def __init__(self, *, api_key: str, model: str, temperature: float) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.calls: list[list[tuple[str, str]]] = []

    def invoke(self, messages):
        self.calls.append(list(messages))
        return SimpleNamespace(content="resposta simulada")


def test_service_builds_client_from_constructor_args(monkeypatch):
    monkeypatch.setattr(
        "app.services.openai_langchain_service.OpenAILangChainService._build_client",
        lambda self: FakeChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
        ),
    )

    service = OpenAILangChainService(
        api_key="test-key",
        model="gpt-test",
        temperature=0.3,
    )

    assert service._client.api_key == "test-key"
    assert service._client.model == "gpt-test"
    assert service._client.temperature == 0.3


def test_ask_sends_system_and_human_messages(monkeypatch):
    monkeypatch.setattr(
        "app.services.openai_langchain_service.OpenAILangChainService._build_client",
        lambda self: FakeChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
        ),
    )

    service = OpenAILangChainService(api_key="test-key")
    response = service.ask("Como esta a SRAG?", system_prompt="Responda em portugues.")

    assert response == "resposta simulada"
    assert service._client.calls == [
        [("system", "Responda em portugues."), ("human", "Como esta a SRAG?")]
    ]


def test_ask_messages_accepts_multiple_roles(monkeypatch):
    monkeypatch.setattr(
        "app.services.openai_langchain_service.OpenAILangChainService._build_client",
        lambda self: FakeChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature,
        ),
    )

    service = OpenAILangChainService(api_key="test-key")
    response = service.ask_messages(
        [
            ("system", "Voce e um analista."),
            ("human", "Resuma os dados."),
        ]
    )

    assert response == "resposta simulada"
    assert service._client.calls == [[("system", "Voce e um analista."), ("human", "Resuma os dados.")]]


def test_service_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAILangChainService()
