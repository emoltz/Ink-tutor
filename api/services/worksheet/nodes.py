"""GraphNode definitions for the worksheet pipeline."""

from __future__ import annotations

from ai_connect import AnthropicConfig, OpenRouterConfig, LLMModels
from ai_graph import GraphNode

from .prompts import DESCRIBE_PROMPT, GRAPH_PROMPT


def describe_node() -> GraphNode:
    """Vision: read the worksheet and name the techniques it exercises."""
    return GraphNode(
        name="describe",
        system_prompt=DESCRIBE_PROMPT,
        config=OpenRouterConfig(
            model=LLMModels.GEMINI_3_1_FLASH_LITE_PREVIEW,
            max_tokens=2000,
        ),
    )


def create_graph_node() -> GraphNode:
    """Text reasoning: build the prerequisite skill graph from the description."""
    return GraphNode(
        name="create_graph",
        system_prompt=GRAPH_PROMPT,
        # text-only: empty image_b64 -> no vision block; feed describe's output
        config=AnthropicConfig(model=LLMModels.CLAUDE_SONNET, max_tokens=4000),
        input_formatter=lambda s: ("", s["node_outputs"]["describe"]),
    )
