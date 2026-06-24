"""Two-step skill-graph pipeline: describe (vision) -> create_graph (text)."""

from __future__ import annotations

import json
import re

from ai_graph import TutorGraph

from .models import SkillEdge, SkillGraph, SkillNode
from .nodes import create_graph_node, describe_node
from .prompts import DESCRIBE_PROMPT


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "skill"


def parse_skill_graph(text: str) -> SkillGraph:
    """Accept plain JSON or fenced JSON, then drop malformed edges."""
    data = json.loads(text[text.find("{") : text.rfind("}") + 1])

    nodes: list[SkillNode] = []
    ids: set[str] = set()
    for node in data.get("nodes", []):
        label = str(node.get("label") or node.get("id") or "").strip()
        if not label:
            continue
        node_id = _slug(str(node.get("id") or label))
        if node_id in ids:
            continue
        ids.add(node_id)
        nodes.append(
            SkillNode(
                id=node_id,
                label=label,
                description=node.get("description"),
            )
        )

    edges = []
    for edge in data.get("edges", []):
        source = _slug(edge.get("source", ""))
        target = _slug(edge.get("target", ""))
        if source in ids and target in ids and source != target:
            edges.append(SkillEdge(source=source, target=target, label=edge.get("label")))
    return SkillGraph(nodes=nodes, edges=edges)


def build_worksheet_graph() -> TutorGraph:
    return (
        TutorGraph()
        .add_node(describe_node())
        .add_node(create_graph_node())
        .set_entry("describe")
        .add_edge("describe", "create_graph")
        .add_edge("create_graph", "end")
    )


def describe_skills(image_b64: str) -> SkillGraph:
    text = build_worksheet_graph().run(image_b64=image_b64, prompt=DESCRIBE_PROMPT)
    return parse_skill_graph(text)
