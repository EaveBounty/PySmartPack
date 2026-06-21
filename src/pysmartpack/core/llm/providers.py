"""LLM provider clients over stdlib HTTP (no SDK dependency required).

Each client exposes ``chat(messages) -> str``. Errors raise :class:`LLMError`
so the advisor can fall back to rules gracefully.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import List

from ..models import LLMConfig


class LLMError(RuntimeError):
    pass


def _post_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json", **headers,
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        raise LLMError(f"HTTP {exc.code}: {body}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LLMError(f"网络错误: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMError(f"响应非 JSON: {exc}") from exc


class LLMClient:
    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg

    def chat(self, messages: List[dict]) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class OpenAIClient(LLMClient):
    """OpenAI Chat Completions. Also the base for OpenAI-compatible vendors."""

    DEFAULT_BASE = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"
    PROVIDER_LABEL = "OpenAI"

    def chat(self, messages: List[dict]) -> str:
        base = self.cfg.base_url.rstrip("/") or self.DEFAULT_BASE
        if not self.cfg.api_key:
            raise LLMError(f"缺少 {self.PROVIDER_LABEL} API Key")
        payload = {
            "model": self.cfg.model or self.DEFAULT_MODEL,
            "messages": messages,
            "temperature": self.cfg.temperature,
            "response_format": {"type": "json_object"},
        }
        data = _post_json(f"{base}/chat/completions", payload,
                          {"Authorization": f"Bearer {self.cfg.api_key}"},
                          self.cfg.timeout)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"{self.PROVIDER_LABEL} 响应缺字段: {exc}") from exc


class DeepSeekClient(OpenAIClient):
    """DeepSeek is OpenAI-compatible (Bearer auth, /chat/completions, JSON mode).

    Default provider. ``deepseek-chat`` (DeepSeek-V3) supports JSON output mode;
    ``deepseek-reasoner`` (DeepSeek-R1) is also selectable via the model field.
    """

    DEFAULT_BASE = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-chat"
    PROVIDER_LABEL = "DeepSeek"


class AnthropicClient(LLMClient):
    def chat(self, messages: List[dict]) -> str:
        base = self.cfg.base_url.rstrip("/") or "https://api.anthropic.com/v1"
        if not self.cfg.api_key:
            raise LLMError("缺少 Anthropic API Key")
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        convo = [m for m in messages if m["role"] != "system"]
        payload = {
            "model": self.cfg.model or "claude-3-5-sonnet-latest",
            "max_tokens": 1024,
            "temperature": self.cfg.temperature,
            "system": system,
            "messages": convo,
        }
        data = _post_json(f"{base}/messages", payload, {
            "x-api-key": self.cfg.api_key,
            "anthropic-version": "2023-06-01",
        }, self.cfg.timeout)
        try:
            return data["content"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Anthropic 响应缺字段: {exc}") from exc


class OllamaClient(LLMClient):
    def chat(self, messages: List[dict]) -> str:
        base = self.cfg.base_url.rstrip("/") or "http://localhost:11434"
        payload = {
            "model": self.cfg.model or "llama3.1",
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.cfg.temperature},
            "format": "json",
        }
        data = _post_json(f"{base}/api/chat", payload, {}, self.cfg.timeout)
        try:
            return data["message"]["content"]
        except KeyError as exc:
            raise LLMError(f"Ollama 响应缺字段: {exc}") from exc


_PROVIDERS = {
    "deepseek": DeepSeekClient,
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "ollama": OllamaClient,
}


def create_client(cfg: LLMConfig) -> LLMClient:
    provider = (cfg.provider or "deepseek").lower()
    cls = _PROVIDERS.get(provider)
    if cls is None:
        raise LLMError(f"未知的 LLM 提供方: {cfg.provider}")
    return cls(cfg)
