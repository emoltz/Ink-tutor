"""Skill-graph schema for the worksheet endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
