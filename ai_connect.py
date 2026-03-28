"""
ai_connect.py — provider-agnostic AI vision client built on LangChain.

Supported providers (set via AI_PROVIDER env var or constructor arg):
  "anthropic"   — Claude via Anthropic API  (requires ANTHROPIC_API_KEY)
  "openai"      — GPT via OpenAI API        (requires OPENAI_API_KEY)
  "openrouter"  — Any model via OpenRouter  (requires OPENROUTER_API_KEY)

Usage:
    ai = AIConnect(system_prompt=SYSTEM_PROMPT)
    response = ai.ask(image_b64="...", prompt="The student is solving: 3/4 + 1/6")

OpenRouter examples:
    # Use a specific model on OpenRouter
    AI_PROVIDER=openrouter AI_MODEL=anthropic/claude-sonnet-4-6 python tutor.py
    AI_PROVIDER=openrouter AI_MODEL=google/gemini-flash-1.5 python tutor.py
    AI_PROVIDER=openrouter AI_MODEL=meta-llama/llama-3.2-90b-vision-instruct python tutor.py
"""

import os

from langchain_core.messages import HumanMessage, SystemMessage

# Default models per provider
_DEFAULTS = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "openrouter": "anthropic/claude-sonnet-4-6",
}


def _build_llm(provider: str, model: str, max_tokens: int):
    """Instantiate a LangChain chat model for the given provider."""
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            max_tokens=max_tokens,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            max_tokens=max_tokens,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )

    if provider == "openrouter":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            max_tokens=max_tokens,
            openai_api_key=os.environ.get("OPENROUTER_API_KEY"),
            openai_api_base=os.environ.get(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ),
            default_headers={
                "HTTP-Referer": os.environ.get("OPENROUTER_REFERER", "https://github.com/inktutor"),
                "X-Title": os.environ.get("OPENROUTER_APP_TITLE", "InkTutor"),
            },
        )

    raise ValueError(
        f"Unknown provider {provider!r}. Choose 'anthropic', 'openai', or 'openrouter'."
    )


class AIConnect:
    def __init__(
        self,
        system_prompt: str,
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int = 100,
    ):
        """
        Args:
            system_prompt: Instruction context sent with every request.
            provider:      "anthropic", "openai", or "openrouter". Defaults to
                           env var AI_PROVIDER, then "anthropic".
            model:         Model ID. Defaults to env var AI_MODEL, then a
                           sensible default per provider.
            max_tokens:    Maximum tokens in the response.
        """
        self.system_prompt = system_prompt
        self.provider = (provider or os.getenv("AI_PROVIDER", "anthropic")).lower()

        if model:
            self.model = model
        elif os.getenv("AI_MODEL"):
            self.model = os.environ["AI_MODEL"]
        else:
            self.model = _DEFAULTS.get(self.provider, "claude-sonnet-4-6")

        self._llm = _build_llm(self.provider, self.model, max_tokens)

    def ask(self, image_b64: str, prompt: str) -> str:
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
        response = self._llm.invoke(messages)
        return response.content.strip()
