"""Tests for dashboard.py — read_lines_from utility and FastAPI routes."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard import app, read_lines_from


# ── read_lines_from ───────────────────────────────────────────────────────────

class TestReadLinesFrom:
    def test_missing_file_returns_empty_and_same_position(self, tmp_path):
        missing = tmp_path / "nope.jsonl"
        lines, pos = read_lines_from(missing, 0)
        assert lines == []
        assert pos == 0

    def test_reads_all_lines_from_position_zero(self, tmp_path):
        f = tmp_path / "data.jsonl"
        entries = [{"x": 1}, {"x": 2}, {"x": 3}]
        f.write_text("".join(json.dumps(e) + "\n" for e in entries))

        lines, pos = read_lines_from(f, 0)
        assert len(lines) == 3
        assert lines[0]["x"] == 1
        assert lines[2]["x"] == 3
        assert pos > 0

    def test_incremental_read_returns_only_new_lines(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text(json.dumps({"x": 1}) + "\n")

        _, pos = read_lines_from(f, 0)

        with open(f, "a") as fh:
            fh.write(json.dumps({"x": 2}) + "\n")

        lines, new_pos = read_lines_from(f, pos)
        assert len(lines) == 1
        assert lines[0]["x"] == 2
        assert new_pos > pos

    def test_no_new_data_returns_empty_list(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text(json.dumps({"x": 1}) + "\n")

        _, pos = read_lines_from(f, 0)
        lines, pos2 = read_lines_from(f, pos)
        assert lines == []
        assert pos2 == pos

    def test_skips_invalid_json_lines(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text("bad line\n" + json.dumps({"x": 5}) + "\n")

        lines, _ = read_lines_from(f, 0)
        assert len(lines) == 1
        assert lines[0]["x"] == 5

    def test_empty_file_returns_empty_list(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        lines, pos = read_lines_from(f, 0)
        assert lines == []


# ── FastAPI routes ────────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with file paths redirected to tmp_path."""
    import dashboard

    monkeypatch.setattr(dashboard, "STROKE_FILE", tmp_path / "strokes.jsonl")
    monkeypatch.setattr(dashboard, "AI_LOG_FILE", tmp_path / "ai_responses.jsonl")

    return TestClient(app)


class TestDashboardRoutes:
    def test_index_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_index_returns_html(self, client):
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_clear_returns_cleared_status(self, tmp_path, monkeypatch):
        import dashboard

        stroke_file = tmp_path / "strokes.jsonl"
        ai_file = tmp_path / "ai_responses.jsonl"
        stroke_file.write_text('{"x":1}\n')
        ai_file.write_text('{"ts":1}\n')

        monkeypatch.setattr(dashboard, "STROKE_FILE", stroke_file)
        monkeypatch.setattr(dashboard, "AI_LOG_FILE", ai_file)

        c = TestClient(app)
        response = c.post("/clear")
        assert response.status_code == 200
        assert response.json()["status"] == "cleared"

    def test_clear_truncates_files(self, tmp_path, monkeypatch):
        import dashboard

        stroke_file = tmp_path / "strokes.jsonl"
        ai_file = tmp_path / "ai_responses.jsonl"
        stroke_file.write_text('{"x":1}\n')
        ai_file.write_text('{"ts":1}\n')

        monkeypatch.setattr(dashboard, "STROKE_FILE", stroke_file)
        monkeypatch.setattr(dashboard, "AI_LOG_FILE", ai_file)

        c = TestClient(app)
        c.post("/clear")

        assert stroke_file.read_text() == ""
        assert ai_file.read_text() == ""

    def test_clear_with_missing_files_does_not_crash(self, tmp_path, monkeypatch):
        import dashboard

        monkeypatch.setattr(dashboard, "STROKE_FILE", tmp_path / "missing_strokes.jsonl")
        monkeypatch.setattr(dashboard, "AI_LOG_FILE", tmp_path / "missing_ai.jsonl")

        c = TestClient(app)
        response = c.post("/clear")
        assert response.status_code == 200
