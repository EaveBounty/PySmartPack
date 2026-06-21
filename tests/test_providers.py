import pytest

from pysmartpack.core.llm.providers import (
    DeepSeekClient,
    LLMError,
    OllamaClient,
    OpenAIClient,
    create_client,
)
from pysmartpack.core.models import LLMConfig


def test_deepseek_is_default_provider():
    cfg = LLMConfig()
    assert cfg.provider == "deepseek"
    assert cfg.model == "deepseek-chat"


def test_create_client_defaults_to_deepseek():
    client = create_client(LLMConfig())
    assert isinstance(client, DeepSeekClient)
    assert client.DEFAULT_BASE == "https://api.deepseek.com"
    assert client.DEFAULT_MODEL == "deepseek-chat"


def test_deepseek_is_openai_compatible():
    # DeepSeek reuses the OpenAI Chat Completions implementation.
    assert issubclass(DeepSeekClient, OpenAIClient)


def test_create_client_other_providers():
    assert isinstance(create_client(LLMConfig(provider="openai")), OpenAIClient)
    assert isinstance(create_client(LLMConfig(provider="ollama")), OllamaClient)


def test_unknown_provider_raises():
    with pytest.raises(LLMError):
        create_client(LLMConfig(provider="does-not-exist"))
