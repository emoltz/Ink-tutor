"""
ai_connect.py — provider-agnostic AI vision client.

Supported providers: "anthropic", "openai"

Usage:
    ai = AIConnect(system_prompt=SYSTEM_PROMPT)
    response = ai.ask(image_b64="...", prompt="The student is solving: 3/4 + 1/6")
"""

import os


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
            provider:      "anthropic" or "openai". Defaults to env var
                           AI_PROVIDER, then "anthropic".
            model:         Model ID. Defaults to env var AI_MODEL, then a
                           sensible default per provider.
            max_tokens:    Maximum tokens in the response.
        """
        self.system_prompt = system_prompt
        self.provider = (provider or os.getenv("AI_PROVIDER", "anthropic")).lower()
        self.max_tokens = max_tokens

        if model:
            self.model = model
        elif os.getenv("AI_MODEL"):
            self.model = os.environ["AI_MODEL"]
        elif self.provider == "openai":
            self.model = "gpt-4o"
        else:
            self.model = "claude-sonnet-4-6"

    def ask(self, image_b64: str, prompt: str) -> str:
        """Send a base64-encoded PNG and a text prompt; return the response."""
        if self.provider == "openai":
            return self._ask_openai(image_b64, prompt)
        return self._ask_anthropic(image_b64, prompt)

    # ── Anthropic ────────────────────────────────────────────────────────────

    def _ask_anthropic(self, image_b64: str, prompt: str) -> str:
        import anthropic

        client = anthropic.Anthropic()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return response.content[0].text.strip()

    # ── OpenAI ───────────────────────────────────────────────────────────────

    def _ask_openai(self, image_b64: str, prompt: str) -> str:
        import openai

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
        )
        return response.choices[0].message.content.strip()
