"""Tests for tutor.py — render_strokes, read_new_dots, log_ai_response."""

import base64
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import tutor

# ── render_strokes ────────────────────────────────────────────────────────────


class TestRenderStrokes:
    def test_returns_string(self, sample_dots):
        result = tutor.render_strokes(sample_dots)
        assert isinstance(result, str)

    def test_result_is_valid_base64(self, sample_dots):
        result = tutor.render_strokes(sample_dots)
        decoded = base64.standard_b64decode(result)
        assert len(decoded) > 0

    def test_output_is_png(self, sample_dots):
        result = tutor.render_strokes(sample_dots)
        raw = base64.standard_b64decode(result)
        # PNG magic bytes: \x89PNG
        assert raw[:4] == b"\x89PNG"

    def test_empty_dots_produces_white_canvas(self):
        result = tutor.render_strokes([])
        raw = base64.standard_b64decode(result)
        assert raw[:4] == b"\x89PNG"

    def test_single_dot(self):
        dots = [{"x": 500, "y": 400, "pressure": 512, "ts": 0.0, "type": "dot"}]
        result = tutor.render_strokes(dots)
        assert base64.standard_b64decode(result)[:4] == b"\x89PNG"

    def test_all_same_coordinates_no_crash(self):
        # x_range and y_range would be 0 — handled by max(..., 1)
        dots = [{"x": 100, "y": 100, "pressure": 512, "ts": 0.0, "type": "dot"}] * 5
        result = tutor.render_strokes(dots)
        assert base64.standard_b64decode(result)[:4] == b"\x89PNG"


# ── read_new_dots ─────────────────────────────────────────────────────────────


class TestReadNewDots:
    def test_returns_empty_when_file_missing(self, tmp_path, monkeypatch):
        missing = tmp_path / "nope.jsonl"
        monkeypatch.setattr(tutor, "STROKE_FILE", missing)
        monkeypatch.setattr(tutor, "file_position", 0)
        assert tutor.read_new_dots() == []

    def test_reads_dots_from_file(self, strokes_file, monkeypatch, sample_dot):
        strokes_file.write_text(json.dumps(sample_dot) + "\n")
        monkeypatch.setattr(tutor, "STROKE_FILE", strokes_file)
        monkeypatch.setattr(tutor, "file_position", 0)

        dots = tutor.read_new_dots()
        assert len(dots) == 1
        assert dots[0]["x"] == sample_dot["x"]
        assert dots[0]["y"] == sample_dot["y"]

    def test_reads_multiple_dots(self, strokes_file, monkeypatch, sample_dots):
        content = "".join(json.dumps(d) + "\n" for d in sample_dots)
        strokes_file.write_text(content)
        monkeypatch.setattr(tutor, "STROKE_FILE", strokes_file)
        monkeypatch.setattr(tutor, "file_position", 0)

        dots = tutor.read_new_dots()
        assert len(dots) == len(sample_dots)

    def test_advances_file_position(self, strokes_file, monkeypatch, sample_dot):
        strokes_file.write_text(json.dumps(sample_dot) + "\n")
        monkeypatch.setattr(tutor, "STROKE_FILE", strokes_file)
        monkeypatch.setattr(tutor, "file_position", 0)

        tutor.read_new_dots()
        assert tutor.file_position > 0

    def test_incremental_reads_no_duplicates(
        self, strokes_file, monkeypatch, sample_dots
    ):
        monkeypatch.setattr(tutor, "STROKE_FILE", strokes_file)
        monkeypatch.setattr(tutor, "file_position", 0)

        # Write first dot, read it
        strokes_file.write_text(json.dumps(sample_dots[0]) + "\n")
        first = tutor.read_new_dots()
        assert len(first) == 1

        # Append second dot, read again — should only get the new one
        with open(strokes_file, "a") as f:
            f.write(json.dumps(sample_dots[1]) + "\n")
        second = tutor.read_new_dots()
        assert len(second) == 1
        assert second[0]["x"] == sample_dots[1]["x"]

    def test_skips_invalid_json_lines(self, strokes_file, monkeypatch, sample_dot):
        strokes_file.write_text("not valid json\n" + json.dumps(sample_dot) + "\n")
        monkeypatch.setattr(tutor, "STROKE_FILE", strokes_file)
        monkeypatch.setattr(tutor, "file_position", 0)

        dots = tutor.read_new_dots()
        assert len(dots) == 1


# ── log_ai_response ───────────────────────────────────────────────────────────


class TestLogAiResponse:
    def test_creates_file_and_writes_entry(self, tmp_path, monkeypatch):
        log_file = tmp_path / "ai_responses.jsonl"
        monkeypatch.setattr(tutor, "AI_LOG_FILE", log_file)

        tutor.log_ai_response("What step did you try next?", 42)

        assert log_file.exists()
        entry = json.loads(log_file.read_text().strip())
        assert entry["feedback"] == "What step did you try next?"
        assert entry["dot_count"] == 42
        assert "ts" in entry

    def test_appends_multiple_entries(self, tmp_path, monkeypatch):
        log_file = tmp_path / "ai_responses.jsonl"
        monkeypatch.setattr(tutor, "AI_LOG_FILE", log_file)

        tutor.log_ai_response("First question?", 10)
        tutor.log_ai_response("Second question?", 20)

        lines = [l for l in log_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["feedback"] == "First question?"
        assert json.loads(lines[1])["feedback"] == "Second question?"

    def test_entry_has_timestamp(self, tmp_path, monkeypatch):
        log_file = tmp_path / "ai_responses.jsonl"
        monkeypatch.setattr(tutor, "AI_LOG_FILE", log_file)

        tutor.log_ai_response("Hmm?", 5)
        entry = json.loads(log_file.read_text().strip())
        assert isinstance(entry["ts"], float)
        assert entry["ts"] > 0
