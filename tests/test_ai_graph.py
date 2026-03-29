"""Tests for ai_graph.py — GraphNode, TutorGraph builder, and routing."""
import sys
from unittest.mock import MagicMock, patch

import pytest

from ai_connect import AnthropicConfig, OpenAIConfig


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mock_build_llm(response_text="  Some feedback  "):
    """Return a patched _build_llm that produces a mock LLM."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content=response_text)
    return patch("ai_graph._build_llm", return_value=mock_llm), mock_llm


def _make_node(name="tutor", response_text="  Some feedback  ", **kwargs):
    """Build a GraphNode with a mocked LLM."""
    patcher, mock_llm = _mock_build_llm(response_text)
    with patcher:
        from ai_graph import GraphNode
        node = GraphNode(
            name=name,
            system_prompt="You are a tutor.",
            config=AnthropicConfig(api_key="fake"),
            **kwargs,
        )
    node._llm = mock_llm
    return node


# ── GraphNode ────────────────────────────────────────────────────────────────

class TestGraphNode:
    def test_builds_llm_on_init(self):
        patcher, mock_llm = _mock_build_llm()
        with patcher as mock_factory:
            from ai_graph import GraphNode
            node = GraphNode(
                name="n", system_prompt="sp",
                config=AnthropicConfig(api_key="k"),
            )
        mock_factory.assert_called_once()

    def test_call_returns_stripped_response(self):
        node = _make_node(response_text="  Hello!  ")
        result = node({"image_b64": "img", "prompt": "p"})
        assert result["response"] == "Hello!"

    def test_call_stores_in_node_outputs(self):
        node = _make_node(name="analyzer", response_text="OK")
        result = node({"image_b64": "img", "prompt": "p"})
        assert result["node_outputs"]["analyzer"] == "OK"

    def test_call_preserves_existing_node_outputs(self):
        node = _make_node(name="second")
        state = {
            "image_b64": "img", "prompt": "p",
            "node_outputs": {"first": "earlier"},
        }
        result = node(state)
        assert result["node_outputs"]["first"] == "earlier"
        assert result["node_outputs"]["second"] == "Some feedback"

    def test_custom_output_key(self):
        node = _make_node(output_key="analysis")
        result = node({"image_b64": "img", "prompt": "p"})
        assert "analysis" in result
        assert result["analysis"] == "Some feedback"

    def test_input_formatter(self):
        def fmt(state):
            return state["image_b64"], "custom: " + state["prompt"]

        node = _make_node(input_formatter=fmt)
        node({"image_b64": "img", "prompt": "original"})

        args, _ = node._llm.invoke.call_args
        messages = args[0]
        text_block = next(b for b in messages[1].content if b.get("type") == "text")
        assert text_block["text"] == "custom: original"

    def test_passes_config_to_llm(self):
        node = _make_node()
        fake_config = {"callbacks": [MagicMock()]}
        node({"image_b64": "img", "prompt": "p"}, config=fake_config)
        _, kwargs = node._llm.invoke.call_args
        assert kwargs.get("config") is fake_config

    def test_sends_system_and_human_messages(self):
        from langchain_core.messages import HumanMessage, SystemMessage

        node = _make_node()
        node({"image_b64": "img", "prompt": "check"})

        args, _ = node._llm.invoke.call_args
        messages = args[0]
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)
        assert messages[0].content == "You are a tutor."

    def test_embeds_image_in_message(self):
        node = _make_node()
        node({"image_b64": "base64data", "prompt": "p"})

        args, _ = node._llm.invoke.call_args
        human_msg = args[0][1]
        img_block = next(b for b in human_msg.content if b.get("type") == "image_url")
        assert "base64data" in img_block["image_url"]["url"]


# ── TutorGraph builder ──────────────────────────────────────────────────────

class TestTutorGraphBuilder:
    def test_compile_raises_without_entry(self):
        from ai_graph import TutorGraph
        graph = TutorGraph()
        with pytest.raises(ValueError, match="entry point"):
            graph.compile()

    def test_add_node_returns_self(self):
        from ai_graph import TutorGraph
        graph = TutorGraph()
        node = _make_node()
        assert graph.add_node(node) is graph

    def test_set_entry_returns_self(self):
        from ai_graph import TutorGraph
        graph = TutorGraph()
        assert graph.set_entry("x") is graph

    def test_add_edge_returns_self(self):
        from ai_graph import TutorGraph
        graph = TutorGraph()
        assert graph.add_edge("a", "b") is graph

    def test_add_conditional_edge_returns_self(self):
        from ai_graph import TutorGraph
        graph = TutorGraph()
        assert graph.add_conditional_edge("a", lambda s: "x", {"x": "b"}) is graph

    def test_fluent_chaining(self):
        from ai_graph import TutorGraph
        node = _make_node()
        graph = (TutorGraph()
            .add_node(node)
            .set_entry("tutor")
            .add_edge("tutor", "end"))
        assert isinstance(graph, TutorGraph)


# ── TutorGraph.run (integration with mocked LLMs) ───────────────────────────

class TestTutorGraphRun:
    def test_single_node_returns_response(self):
        from ai_graph import TutorGraph
        node = _make_node(response_text="What step is next?")
        graph = (TutorGraph()
            .add_node(node)
            .set_entry("tutor")
            .add_edge("tutor", "end"))
        result = graph.run(image_b64="img", prompt="Solve 3/4+1/6")
        assert result == "What step is next?"

    def test_single_node_passes_metadata(self):
        from ai_graph import TutorGraph
        node = _make_node()
        graph = (TutorGraph()
            .add_node(node)
            .set_entry("tutor")
            .add_edge("tutor", "end"))
        # Should not raise
        graph.run(image_b64="img", prompt="p", metadata={"problem": "test"})

    def test_conditional_routing_takes_end_path(self):
        from ai_graph import TutorGraph

        analyzer = _make_node(name="analyze", response_text="OK")
        tutor = _make_node(name="tutor", response_text="Hmm, check that step")

        def route(state):
            return "ok" if state["response"].strip().upper() == "OK" else "needs_help"

        graph = (TutorGraph()
            .add_node(analyzer)
            .add_node(tutor)
            .set_entry("analyze")
            .add_conditional_edge("analyze", route, {
                "ok": "end",
                "needs_help": "tutor",
            })
            .add_edge("tutor", "end"))

        result = graph.run(image_b64="img", prompt="p")
        # Analyzer said OK → route to end → tutor never called
        assert result == "OK"
        tutor._llm.invoke.assert_not_called()

    def test_conditional_routing_takes_help_path(self):
        from ai_graph import TutorGraph

        analyzer = _make_node(name="analyze", response_text="ERROR")
        tutor = _make_node(name="tutor", response_text="What did you get for step 2?")

        def route(state):
            return "ok" if state["response"].strip().upper() == "OK" else "needs_help"

        graph = (TutorGraph()
            .add_node(analyzer)
            .add_node(tutor)
            .set_entry("analyze")
            .add_conditional_edge("analyze", route, {
                "ok": "end",
                "needs_help": "tutor",
            })
            .add_edge("tutor", "end"))

        result = graph.run(image_b64="img", prompt="p")
        assert result == "What did you get for step 2?"
        tutor._llm.invoke.assert_called_once()

    def test_multi_node_sequential(self):
        from ai_graph import TutorGraph

        first = _make_node(name="first", response_text="step-one-done")
        second = _make_node(name="second", response_text="final answer")

        graph = (TutorGraph()
            .add_node(first)
            .add_node(second)
            .set_entry("first")
            .add_edge("first", "second")
            .add_edge("second", "end"))

        result = graph.run(image_b64="img", prompt="p")
        assert result == "final answer"
        first._llm.invoke.assert_called_once()
        second._llm.invoke.assert_called_once()

    def test_different_configs_per_node(self):
        """Each node can use a different provider config."""
        from ai_graph import TutorGraph, GraphNode

        patcher1, llm1 = _mock_build_llm("from-anthropic")
        patcher2, llm2 = _mock_build_llm("from-openai")

        with patcher1:
            node1 = GraphNode(
                name="claude", system_prompt="sp",
                config=AnthropicConfig(api_key="k1"),
            )
        node1._llm = llm1

        with patcher2:
            node2 = GraphNode(
                name="gpt", system_prompt="sp",
                config=OpenAIConfig(api_key="k2"),
            )
        node2._llm = llm2

        graph = (TutorGraph()
            .add_node(node1)
            .add_node(node2)
            .set_entry("claude")
            .add_edge("claude", "gpt")
            .add_edge("gpt", "end"))

        result = graph.run(image_b64="img", prompt="p")
        assert result == "from-openai"
        llm1.invoke.assert_called_once()
        llm2.invoke.assert_called_once()


# ── TutorState typing ───────────────────────────────────────────────────────

class TestTutorState:
    def test_is_typed_dict(self):
        from ai_graph import TutorState
        # total=False means all keys are optional
        state: TutorState = {}
        assert isinstance(state, dict)

    def test_accepts_all_expected_keys(self):
        from ai_graph import TutorState
        state: TutorState = {
            "image_b64": "abc",
            "prompt": "hello",
            "metadata": {"k": "v"},
            "response": "resp",
            "route": "ok",
            "node_outputs": {"n": "out"},
        }
        assert state["response"] == "resp"
