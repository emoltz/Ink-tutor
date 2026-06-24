"""Worksheet PDF -> skill graph endpoint (thin HTTP layer)."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from api.services.worksheet import MAX_PDF_BYTES, SkillGraph, describe_skills, render_pdf

router = APIRouter(tags=["worksheet"])


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
        return describe_skills(render_pdf(pdf))
    except json.JSONDecodeError as exc:
        raise HTTPException(502, "Model returned invalid JSON") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc
