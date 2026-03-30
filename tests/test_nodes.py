"""Tests for nodes.py — prompt definitions and graph wiring."""

import os
from unittest.mock import MagicMock, patch

import pytest

from ai_connect import AnthropicConfig

_FAKE_ENV = {
    "OPENROUTER_API_KEY": "fake-or-key",
    "ANTHROPIC_API_KEY": "fake-ant-key",
}


def _mock_build_llm(response_text="mock response"):
    """Return a patched _build_llm that produces a mock LLM."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=response_text)
    return patch("ai_graph._build_llm", return_value=mock_llm), mock_llm


class TestPrompts:
    def test_analyze_prompt_requires_status_line(self):
        from nodes import ANALYZE_PROMPT

        assert "STATUS: CORRECT" in ANALYZE_PROMPT
        assert "STATUS: ERROR" in ANALYZE_PROMPT

    def test_tutor_prompt_references_status(self):
        from nodes import TUTOR_PROMPT

        assert "STATUS: CORRECT" in TUTOR_PROMPT
        assert "STATUS: ERROR" in TUTOR_PROMPT

    def test_tutor_prompt_limits_words(self):
        from nodes import TUTOR_PROMPT

        assert "15 words" in TUTOR_PROMPT


class TestBuildGraph:
    def _build(self):
        patcher, _ = _mock_build_llm()
        with patcher, patch.dict(os.environ, _FAKE_ENV):
            from nodes import build_graph

            return build_graph()

    def test_returns_tutor_graph(self):
        from ai_graph import TutorGraph

        graph = self._build()
        assert isinstance(graph, TutorGraph)

    def test_graph_has_expected_nodes(self):
        graph = self._build()
        assert "analyze" in graph._nodes
        assert "tutor" in graph._nodes

    def test_entry_point_is_analyze(self):
        graph = self._build()
        assert graph._entry_point == "analyze"

    def test_tutor_node_uses_input_formatter(self):
        graph = self._build()
        tutor_node = graph._nodes["tutor"]
        assert tutor_node.input_formatter is not None

    def test_tutor_input_formatter_builds_prompt(self):
        graph = self._build()
        tutor_node = graph._nodes["tutor"]
        state = {
            "prompt": "Solve: 3/4 + 1/6",
            "node_outputs": {
                "analyze": "STATUS: ERROR\nStudent wrote 3/4 + 1/6 = 4/10"
            },
        }
        image, text = tutor_node.input_formatter(state)
        assert image == ""
        assert "Solve: 3/4 + 1/6" in text
        assert "STATUS: ERROR" in text
