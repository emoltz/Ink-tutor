"""
ai_connect.py — provider-agnostic AI vision client built on LangChain.

Supported providers:
  AnthropicConfig   — Claude via Anthropic API
  OpenAIConfig      — GPT via OpenAI API
  OpenRouterConfig  — Any model via OpenRouter (uses OpenAI-compatible API)

Usage:
    from ai_connect import AIConnect, AnthropicConfig

    ai = AIConnect(
        system_prompt=SYSTEM_PROMPT,
        config=AnthropicConfig(api_key="sk-ant-..."),
    )
    response = ai.ask(image_b64="...", prompt="The student is solving: 3/4 + 1/6")

OpenRouter example:
    ai = AIConnect(
        system_prompt=SYSTEM_PROMPT,
        config=OpenRouterConfig(
            api_key="sk-or-...",
            model="google/gemini-flash-1.5",
        ),
    )
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

try:
    from langfuse.langchain import CallbackHandler as LangfuseCallback
    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False


# ── Provider config dataclasses ──────────────────────────────────────────────

@dataclass
class AnthropicConfig:
    api_key: str
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 100


@dataclass
class OpenAIConfig:
    api_key: str
    model: str = "gpt-4o"
    max_tokens: int = 100


@dataclass
class OpenRouterConfig:
    api_key: str
    model: str = "anthropic/claude-sonnet-4-6"
    max_tokens: int = 100
    base_url: str = "https://openrouter.ai/api/v1"
    referer: str = "https://github.com/inktutor"
    app_title: str = "InkTutor"


ProviderConfig = AnthropicConfig | OpenAIConfig | OpenRouterConfig


# ── LLM factory ──────────────────────────────────────────────────────────────

def _build_llm(config: ProviderConfig):
    if isinstance(config, AnthropicConfig):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=config.model,
            max_tokens=config.max_tokens,
            anthropic_api_key=config.api_key,
        )

    if isinstance(config, OpenAIConfig):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.model,
            max_tokens=config.max_tokens,
            openai_api_key=config.api_key,
        )

    if isinstance(config, OpenRouterConfig):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.model,
            max_tokens=config.max_tokens,
            openai_api_key=config.api_key,
            openai_api_base=config.base_url,
            default_headers={
                "HTTP-Referer": config.referer,
                "X-Title": config.app_title,
            },
        )

    raise TypeError(f"Unsupported config type: {type(config)}")


# ── Main class ────────────────────────────────────────────────────────────────

class AIConnect:
    def __init__(self, system_prompt: str, config: ProviderConfig):
        """
        Args:
            system_prompt: Instruction context sent with every request.
            config:        One of AnthropicConfig, OpenAIConfig, or OpenRouterConfig.
        """
        self.system_prompt = system_prompt
        self._llm = _build_llm(config)
        self._langfuse_handler = None
        if _LANGFUSE_AVAILABLE and os.getenv("LANGFUSE_PUBLIC_KEY"):
            self._langfuse_handler = LangfuseCallback()

    def ask(self, image_b64: str, prompt: str, metadata: dict | None = None) -> str:
        """Send a base64-encoded PNG and a text prompt; return the response."""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=[
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
                {"type": "text", "text": prompt},
            ]),
        ]
        invoke_config: dict = {}
        if self._langfuse_handler:
            invoke_config["callbacks"] = [self._langfuse_handler]
            invoke_config["run_name"] = "ink-tutor-analysis"
            if metadata:
                invoke_config["metadata"] = metadata
        response = self._llm.invoke(messages, config=invoke_config or None)
        return response.content.strip()
