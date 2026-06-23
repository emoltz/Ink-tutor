import json

from fastapi.testclient import TestClient

from api.main import app
from api.routers import worksheet


def test_parse_skill_graph_drops_bad_edges():
    graph = worksheet.parse_skill_graph(
        "```json\n"
        + json.dumps(
            {
                "nodes": [{"id": "Fractions", "label": "Fractions"}],
                "edges": [
                    {"source": "fractions", "target": "missing"},
                    {"source": "fractions", "target": "fractions"},
                ],
            }
        )
        + "\n```"
    )

    assert graph.nodes[0].id == "fractions"
    assert graph.edges == []


def test_worksheet_requires_pdf():
    response = TestClient(app).post("/worksheet", content=b"nope")
    assert response.status_code == 415


def test_worksheet_returns_skill_graph(monkeypatch):
    monkeypatch.setattr(worksheet, "render_pdf", lambda _: "image")
    monkeypatch.setattr(
        worksheet,
        "describe_skills",
        lambda _: worksheet.SkillGraph(
            nodes=[worksheet.SkillNode(id="fractions", label="Fractions")], edges=[]
        ),
    )

    response = TestClient(app).post("/worksheet", content=b"%PDF-1.7")

    assert response.status_code == 200
    assert response.json()["nodes"][0]["id"] == "fractions"
