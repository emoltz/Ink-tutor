"""
ai_graph.py — LangGraph integration layer for InkTutor.

Builds on ai_connect.py's provider configs and LLM factory to create
multi-node graphs where each node can use a different model, system prompt,
and routing logic.

Simple single-node usage (equivalent to AIConnect.ask):

    from ai_graph import TutorGraph, GraphNode
    from ai_connect import AnthropicConfig

    graph = (TutorGraph()
        .add_node(GraphNode(
            name="tutor",
            system_prompt="You are a math tutor.",
            config=AnthropicConfig(api_key="sk-ant-..."),
        ))
        .set_entry("tutor")
        .add_edge("tutor", "end"))

    response = graph.run(image_b64="...", prompt="What do you see?")

Multi-node with conditional routing:

    from ai_graph import TutorGraph, GraphNode
    from ai_connect import AnthropicConfig, OpenRouterConfig, OPENROUTER_VISION_MODELS

    analyzer = GraphNode(
        name="analyze",
        system_prompt="Respond OK if correct, ERROR if wrong.",
        config=OpenRouterConfig(
            api_key="sk-or-...",
            model=OPENROUTER_VISION_MODELS["gemini-2.5-flash"],
        ),
    )
    tutor = GraphNode(
        name="tutor",
        system_prompt="Ask one Socratic question about the error.",
        config=AnthropicConfig(api_key="sk-ant-...", max_tokens=200),
    )

    def route(state):
        return "ok" if state["response"].strip().upper() == "OK" else "needs_help"

    graph = (TutorGraph()
        .add_node(analyzer)
        .add_node(tutor)
        .set_entry("analyze")
        .add_conditional_edge("analyze", route, {"ok": "end", "needs_help": "tutor"})
        .add_edge("tutor", "end"))

    response = graph.run(image_b64="...", prompt="Solve 3/4 + 1/6")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from ai_connect import ProviderConfig, _build_llm


# ── Graph state ─────────────────────────────────────────────────────────────

class TutorState(TypedDict, total=False):
    """State that flows through every node in the graph."""

    # Inputs — set before the graph runs
    image_b64: str
    prompt: str
    metadata: dict[str, Any]

    # Outputs — written by nodes
    response: str                    # current / final text response
    route: str                       # routing key for conditional edges
    node_outputs: dict[str, str]     # per-node output history keyed by node name


# ── Graph node ──────────────────────────────────────────────────────────────

@dataclass
class GraphNode:
    """A single node in the tutoring graph.

    Each node wraps its own LLM (built from a ProviderConfig) and system
    prompt.  When called by LangGraph it reads ``image_b64`` and ``prompt``
    from state, invokes the LLM with a vision message, and writes the result
    back to state.

    Args:
        name:            Unique identifier used as the LangGraph node name.
        system_prompt:   System message sent with every request to this node's LLM.
        config:          Provider config (AnthropicConfig, OpenAIConfig, OpenRouterConfig).
        output_key:      State key to write the LLM response to (default ``"response"``).
        input_formatter: Optional callable ``(state) -> (image_b64, prompt)`` for
                         custom input extraction.  Defaults to reading directly
                         from ``state["image_b64"]`` and ``state["prompt"]``.
    """

    name: str
    system_prompt: str
    config: ProviderConfig
    output_key: str = "response"
    input_formatter: Callable[[TutorState], tuple[str, str]] | None = None

    def __post_init__(self) -> None:
        self._llm = _build_llm(self.config)

    def __call__(self, state: TutorState, config: RunnableConfig = None) -> dict:
        if self.input_formatter:
            image_b64, prompt = self.input_formatter(state)
        else:
            image_b64 = state["image_b64"]
            prompt = state["prompt"]

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

        result = self._llm.invoke(messages, config=config)
        text = result.content.strip()

        node_outputs = dict(state.get("node_outputs") or {})
        node_outputs[self.name] = text

        return {self.output_key: text, "node_outputs": node_outputs}


# ── Graph builder ───────────────────────────────────────────────────────────

class TutorGraph:
    """Fluent builder for LangGraph pipelines of ``GraphNode`` instances.

    Example::

        graph = (TutorGraph()
            .add_node(my_node)
            .set_entry("my_node")
            .add_edge("my_node", "end"))
        response = graph.run(image_b64, prompt)
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode | Callable] = {}
        self._edges: list[tuple[str, str]] = []
        self._conditional_edges: list[
            tuple[str, Callable[[TutorState], str], dict[str, str]]
        ] = []
        self._entry_point: str | None = None

    # -- builder methods (return self for chaining) --

    def add_node(self, node: GraphNode) -> TutorGraph:
        """Register a node.  Uses ``node.name`` as the graph key."""
        self._nodes[node.name] = node
        return self

    def set_entry(self, node_name: str) -> TutorGraph:
        """Set the entry-point node (must be added first)."""
        self._entry_point = node_name
        return self

    def add_edge(self, from_node: str, to_node: str) -> TutorGraph:
        """Add a static edge.  Use ``"end"`` as *to_node* to terminate."""
        self._edges.append((from_node, to_node))
        return self

    def add_conditional_edge(
        self,
        from_node: str,
        router: Callable[[TutorState], str],
        path_map: dict[str, str],
    ) -> TutorGraph:
        """Add a conditional edge.

        *router* receives the current state and returns a string key.
        *path_map* maps those keys to node names (use ``"end"`` for ``END``).
        """
        self._conditional_edges.append((from_node, router, path_map))
        return self

    # -- compilation --

    def compile(self):
        """Build and return a compiled LangGraph ``CompiledGraph``."""
        if not self._entry_point:
            raise ValueError("No entry point set — call set_entry() first")

        graph = StateGraph(TutorState)

        for name, node in self._nodes.items():
            graph.add_node(name, node)

        graph.set_entry_point(self._entry_point)

        for src, dst in self._edges:
            graph.add_edge(src, END if dst == "end" else dst)

        for src, router, path_map in self._conditional_edges:
            resolved = {k: (END if v == "end" else v) for k, v in path_map.items()}
            graph.add_conditional_edges(src, router, resolved)

        return graph.compile()

    # -- convenience runner --

    def run(
        self,
        image_b64: str,
        prompt: str,
        metadata: dict[str, Any] | None = None,
        callbacks: list | None = None,
    ) -> str:
        """Compile the graph, run it, and return the final ``response`` string.

        Args:
            image_b64:  Base64-encoded PNG image.
            prompt:     Text prompt.
            metadata:   Optional metadata dict passed through state.
            callbacks:  Optional LangChain callbacks (e.g. Langfuse).
        """
        compiled = self.compile()
        initial_state: TutorState = {
            "image_b64": image_b64,
            "prompt": prompt,
            "metadata": metadata or {},
        }
        invoke_config: dict[str, Any] = {}
        if callbacks:
            invoke_config["callbacks"] = callbacks
        final_state = compiled.invoke(
            initial_state, config=invoke_config or None
        )
        return final_state.get("response", "")
