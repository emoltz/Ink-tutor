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
    from ai_connect import AIConnect, OpenRouterConfig, OpenRouterVisionModel

    # Use any member from OpenRouterVisionModel, or pass an OpenRouter model ID directly:
    ai = AIConnect(
        system_prompt=SYSTEM_PROMPT,
        config=OpenRouterConfig(
            api_key="sk-or-...",
            model=OpenRouterVisionModel.GEMINI_3_FLASH_PREVIEW,   # fast and cheap
            # model=OpenRouterVisionModel.CLAUDE_SONNET_4_6        # Anthropic alternative
            # model="anthropic/claude-opus-4-6"                    # or pass ID directly
        ),
    )
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

from langchain_core.messages import HumanMessage, SystemMessage

try:
    from langfuse.langchain import CallbackHandler as LangfuseCallback

    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False


# ── OpenRouter vision models ──────────────────────────────────────
# All models listed here support base64-encoded image input.
# Values are OpenRouter model IDs; pass them as OpenRouterConfig(model=...).
class OpenRouterVisionModel(StrEnum):
    # Anthropic — Claude 4 family (all support vision)
    CLAUDE_OPUS_4_6 = "anthropic/claude-opus-4-6"  # most capable, highest cost
    CLAUDE_SONNET_4_6 = (
        "anthropic/claude-sonnet-4-6"  # default; best speed/cost balance
    )
    CLAUDE_HAIKU_4_5 = "anthropic/claude-haiku-4-5"  # fastest, lowest cost
    # Google — Gemini family
    GEMINI_3_FLASH_PREVIEW = "google/gemini-3-flash-preview"
    GEMINI_3_1_FLASH_LITE_PREVIEW = ("google/gemini-3.1-flash-lite-preview",)
    # Mistral — vision-capable small models
    MISTRAL_SMALL_3_2 = (
        "mistralai/mistral-small-3.2-24b-instruct"  # latest, vision + tool calling
    )
    MISTRAL_SMALL_3_1 = "mistralai/mistral-small-3.1-24b-instruct"  # solid, widely used


# ── Provider config dataclasses ──────────────────────────────────────────────


@dataclass
class AnthropicConfig:
    api_key: str | None = None
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 100

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ["ANTHROPIC_API_KEY"]


@dataclass
class OpenAIConfig:
    api_key: str | None = None
    model: str = "gpt-5-mini"
    max_tokens: int = 100

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ["OPENAI_API_KEY"]


@dataclass
class OpenRouterConfig:
    api_key: str | None = None
    model: str = "anthropic/claude-sonnet-4-6"
    max_tokens: int = 100
    base_url: str = "https://openrouter.ai/api/v1"
    referer: str = "https://github.com/inktutor"
    app_title: str = "InkTutor"

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ["OPENROUTER_API_KEY"]


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
            try:
                self._langfuse_handler = LangfuseCallback()
            except Exception as e:
                print(f"Warning: Langfuse init failed, tracing disabled: {e}")

    def ask(self, image_b64: str, prompt: str, metadata: dict | None = None) -> str:
        """Send a base64-encoded PNG and a text prompt; return the response."""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                    {"type": "text", "text": prompt},
                ]
            ),
        ]
        invoke_config: dict | None = None
        if self._langfuse_handler:
            invoke_config = {
                "callbacks": [self._langfuse_handler],
                "run_name": "ink-tutor-analysis",
            }
            if metadata:
                invoke_config["metadata"] = metadata
        try:
            response = self._llm.invoke(messages, config=invoke_config)
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}") from e

        try:
            return response.content.strip()
        except AttributeError as e:
            raise RuntimeError(f"Unexpected LLM response format: {e}") from e

    def flush(self) -> None:
        """Flush pending Langfuse traces. Call before process exit."""
        if self._langfuse_handler:
            self._langfuse_handler.flush()

    def __del__(self) -> None:
        self.flush()
