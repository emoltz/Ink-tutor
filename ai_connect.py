"""
ai_connect.py — provider configs and LLM factory for InkTutor.

Supported providers:
  AnthropicConfig   — Claude via Anthropic API
  OpenAIConfig      — GPT via OpenAI API
  OpenRouterConfig  — Any model via OpenRouter (uses OpenAI-compatible API)

Used by ai_graph.py's GraphNode to build LangChain LLM instances.
API keys are read from environment variables when not passed explicitly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum


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
    GEMINI_3_1_FLASH_LITE_PREVIEW = "google/gemini-3.1-flash-lite-preview"
    # Mistral — vision-capable small models
    MISTRAL_SMALL_3_2 = (
        "mistralai/mistral-small-3.2-24b-instruct"  # latest, vision + tool calling
    )
    MISTRAL_SMALL_3_1 = "mistralai/mistral-small-3.1-24b-instruct"  # solid, widely used
    MISTRAL_3B = "mistralai/ministral-3b-2512"


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
        from langchain_openrouter import ChatOpenRouter

        return ChatOpenRouter(
            model=config.model,
            max_tokens=config.max_tokens,
            openrouter_api_key=config.api_key,
        )

    raise TypeError(f"Unsupported config type: {type(config)}")
