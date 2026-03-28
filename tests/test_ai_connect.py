"""Tests for ai_connect.py — AIConnect class and _build_llm factory."""
import sys
from unittest.mock import MagicMock, patch

import pytest

from ai_connect import AIConnect, AnthropicConfig, OpenAIConfig, OpenRouterConfig, _build_llm


# ── _build_llm factory ────────────────────────────────────────────────────────

class TestBuildLlm:
    def test_anthropic_config_returns_chat_anthropic(self):
        mock_cls = MagicMock()
        with patch.dict(sys.modules, {"langchain_anthropic": MagicMock(ChatAnthropic=mock_cls)}):
            result = _build_llm(AnthropicConfig(api_key="fake-key"))
        mock_cls.assert_called_once()
        assert result is mock_cls.return_value

    def test_openai_config_returns_chat_openai(self):
        mock_cls = MagicMock()
        with patch.dict(sys.modules, {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
            result = _build_llm(OpenAIConfig(api_key="fake-key"))
        mock_cls.assert_called_once()
        assert result is mock_cls.return_value

    def test_openrouter_config_returns_chat_openai(self):
        mock_cls = MagicMock()
        with patch.dict(sys.modules, {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
            result = _build_llm(OpenRouterConfig(api_key="fake-key"))
        mock_cls.assert_called_once()
        assert result is mock_cls.return_value

    def test_openrouter_passes_base_url(self):
        mock_cls = MagicMock()
        with patch.dict(sys.modules, {"langchain_openai": MagicMock(ChatOpenAI=mock_cls)}):
            _build_llm(OpenRouterConfig(api_key="k", base_url="https://custom.ai/v1"))
        _, kwargs = mock_cls.call_args
        assert kwargs.get("openai_api_base") == "https://custom.ai/v1"

    def test_unsupported_config_raises_type_error(self):
        with pytest.raises(TypeError):
            _build_llm("not-a-config")


# ── AIConnect ─────────────────────────────────────────────────────────────────

class TestAIConnect:
    def _make_ai(self, system_prompt="You are a tutor."):
        """Build an AIConnect with a mocked LLM."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="  What did you try?  ")

        with patch("ai_connect._build_llm", return_value=mock_llm):
            ai = AIConnect(system_prompt=system_prompt, config=AnthropicConfig(api_key="x"))

        ai._llm = mock_llm  # keep reference for assertions
        return ai

    def test_stores_system_prompt(self):
        ai = self._make_ai(system_prompt="Hello!")
        assert ai.system_prompt == "Hello!"

    def test_ask_returns_stripped_string(self):
        ai = self._make_ai()
        result = ai.ask(image_b64="abc123", prompt="What is this?")
        assert result == "What did you try?"

    def test_ask_calls_llm_invoke(self):
        ai = self._make_ai()
        ai.ask(image_b64="abc123", prompt="Solve this")
        ai._llm.invoke.assert_called_once()

    def test_ask_passes_system_and_human_messages(self):
        from langchain_core.messages import HumanMessage, SystemMessage

        ai = self._make_ai(system_prompt="Be kind.")
        ai.ask(image_b64="img_data", prompt="What is 2+2?")

        args, _ = ai._llm.invoke.call_args
        messages = args[0]
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        assert messages[0].content == "Be kind."

    def test_ask_embeds_image_in_message(self):
        ai = self._make_ai()
        ai.ask(image_b64="mybase64data", prompt="Check this")

        args, _ = ai._llm.invoke.call_args
        human_msg = args[0][1]
        content_blocks = human_msg.content
        image_block = next(b for b in content_blocks if b.get("type") == "image_url")
        assert "mybase64data" in image_block["image_url"]["url"]

    def test_ask_includes_prompt_text(self):
        ai = self._make_ai()
        ai.ask(image_b64="img", prompt="The student solved: 3/4+1/6")

        args, _ = ai._llm.invoke.call_args
        human_msg = args[0][1]
        text_block = next(b for b in human_msg.content if b.get("type") == "text")
        assert "3/4+1/6" in text_block["text"]


# ── Config dataclasses ────────────────────────────────────────────────────────

class TestConfigDefaults:
    def test_anthropic_default_model(self):
        c = AnthropicConfig(api_key="k")
        assert "claude" in c.model.lower()

    def test_openai_default_model(self):
        c = OpenAIConfig(api_key="k")
        assert c.model == "gpt-4o"

    def test_openrouter_has_base_url(self):
        c = OpenRouterConfig(api_key="k")
        assert c.base_url.startswith("https://")
