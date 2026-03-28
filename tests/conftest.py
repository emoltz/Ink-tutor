"""
Shared fixtures and import-time patches for the InkTutor test suite.
"""
import sys
from unittest.mock import MagicMock

import pytest

# ── Patch hardware/heavy deps before any module import ───────────────────────
# bleak is a Mac-only BLE library; mock it so pen_host can be imported anywhere.
sys.modules.setdefault("bleak", MagicMock())


# ── Common fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def sample_dot():
    return {"x": 100, "y": 200, "pressure": 512, "ts": 1700000000.0, "type": "dot"}


@pytest.fixture
def sample_dots():
    return [
        {"x": 100, "y": 200, "pressure": 512, "ts": 1700000000.0, "type": "dot"},
        {"x": 200, "y": 300, "pressure": 600, "ts": 1700000001.0, "type": "dot"},
        {"x": 150, "y": 250, "pressure": 480, "ts": 1700000002.0, "type": "dot"},
    ]


@pytest.fixture
def strokes_file(tmp_path):
    """A temporary strokes.jsonl file path."""
    return tmp_path / "strokes.jsonl"
