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
    from ai_connect import AIConnect, OpenRouterConfig, OPENROUTER_VISION_MODELS

    # Use any key from OPENROUTER_VISION_MODELS, or pass an OpenRouter model ID directly:
    ai = AIConnect(
        system_prompt=SYSTEM_PROMPT,
        config=OpenRouterConfig(
            api_key="sk-or-...",
            model=OPENROUTER_VISION_MODELS["gemini-2.5-flash"],  # fast and cheap
            # model=OPENROUTER_VISION_MODELS["gpt-4o"]           # OpenAI alternative
            # model="anthropic/claude-opus-4-6"                  # or pass ID directly
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


# ── Known-good OpenRouter vision models ──────────────────────────────────────
# All models listed here support base64-encoded image input.
# Values are OpenRouter model IDs; pass them as OpenRouterConfig(model=...).
OPENROUTER_VISION_MODELS: dict[str, str] = {
    # Anthropic — Claude 4 family (all support vision)
    "claude-opus-4-6":   "anthropic/claude-opus-4-6",               # most capable, highest cost
    "claude-sonnet-4-6": "anthropic/claude-sonnet-4-6",             # default; best speed/cost balance
    "claude-haiku-4-5":  "anthropic/claude-haiku-4-5",              # fastest, lowest cost
    # Google — Gemini family
    "gemini-3-pro":      "google/gemini-3-pro-preview",             # latest top-tier, highest cost
    "gemini-3-flash":    "google/gemini-3-flash-preview",           # latest fast model
    "gemini-2.5-pro":    "google/gemini-2.5-pro-preview",           # strong reasoning, 1M context
    "gemini-2.5-flash":  "google/gemini-2.5-flash",                 # fast and cheap, very capable
    "gemini-2.0-flash":  "google/gemini-2.0-flash-001",             # stable 2.0 Flash checkpoint
    # OpenAI
    "gpt-4o":            "openai/gpt-4o",                           # strong vision, widely tested
    "gpt-4o-mini":       "openai/gpt-4o-mini",                      # lightweight, cost-effective
    "o4-mini":           "openai/o4-mini",                          # fast reasoning + vision
    # Meta — Llama 4 multimodal
    "llama-4-maverick":  "meta-llama/llama-4-maverick",             # large MoE, strong reasoning
    "llama-4-scout":     "meta-llama/llama-4-scout",                # 10M context, efficient
    # Mistral — vision-capable small models
    "mistral-small-3.2": "mistralai/mistral-small-3.2-24b-instruct",  # latest, vision + tool calling
    "mistral-small-3.1": "mistralai/mistral-small-3.1-24b-instruct",  # solid, widely used
}


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
    model: str = "gpt-4o"
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
