"""Worksheet PDF -> skill graph endpoint."""

from __future__ import annotations

import base64
import json
import re
from io import BytesIO

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from PIL import Image

from ai_connect import OpenRouterConfig, OpenRouterVisionModel
from ai_graph import GraphNode

router = APIRouter(tags=["worksheet"])

MAX_PDF_BYTES = 20 * 1024 * 1024
SKILL_PROMPT = """Look at this math worksheet. Return only JSON:
{"nodes":[{"id":"snake_case","label":"Skill","description":"short"}],"edges":[{"source":"prereq_id","target":"skill_id","label":"relationship"}]}
Edges point prerequisite -> dependent. Edge label is a short phrase describing the dependency (e.g. "required for"). Include only skills needed for this worksheet."""


class SkillNode(BaseModel):
    id: str
    label: str
    description: str | None = None


class SkillEdge(BaseModel):
    source: str
    target: str
    label: str | None = None


class SkillGraph(BaseModel):
    nodes: list[SkillNode] = Field(default_factory=list)
    edges: list[SkillEdge] = Field(default_factory=list)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "skill"


def parse_skill_graph(text: str) -> SkillGraph:
    """Accept plain JSON or fenced JSON, then drop malformed edges."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
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


def render_pdf(pdf_bytes: bytes) -> str:
    """Render first page to base64 PNG."""
    try:
        import fitz
    except ImportError as exc:  # pragma: no cover - deployment config
        raise RuntimeError("Install pymupdf to render PDFs") from exc

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.page_count == 0:
            raise ValueError("PDF has no pages")
        pix = doc.load_page(0).get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        image = Image.open(BytesIO(pix.tobytes("png"))).convert("RGB")
        out = BytesIO()
        image.save(out, format="PNG")
        return base64.b64encode(out.getvalue()).decode("ascii")
    finally:
        doc.close()


def describe_skills(image_b64: str) -> SkillGraph:
    node = GraphNode(
        name="skills",
        system_prompt=SKILL_PROMPT,
        config=OpenRouterConfig(
            model=OpenRouterVisionModel.GEMINI_3_1_FLASH_LITE_PREVIEW,
            max_tokens=10000,
        ),
    )
    result = node({"image_b64": image_b64, "prompt": SKILL_PROMPT})
    return parse_skill_graph(result["response"])


@router.post("/worksheet", response_model=SkillGraph)
async def worksheet(request: Request) -> SkillGraph:
    pdf = await request.body()
    if not pdf:
        raise HTTPException(400, "Request body is empty")
    if len(pdf) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF is too large")
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(415, "Send raw PDF bytes")

    try:
        graph= describe_skills(render_pdf(pdf))
        print("Graph:" + str(graph))
        return graph
    except json.JSONDecodeError as exc:
        raise HTTPException(502, "Model returned invalid JSON") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc
