"""
dashboard.py  —  real-time pen monitoring dashboard
Tails strokes.jsonl and ai_responses.jsonl, streams updates to browser via WebSocket.
Run with: uvicorn dashboard:app --host 0.0.0.0 --port 8080
"""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("dashboard")

app = FastAPI()

STROKE_FILE = Path("/tmp/inktutor/strokes.jsonl")
AI_LOG_FILE = Path("/tmp/inktutor/ai_responses.jsonl")

POLL_INTERVAL = 0.05  # 50ms → ~20 FPS


def read_lines_from(filepath: Path, position: int) -> tuple[list[dict], int]:
    """Read new JSON lines from a file starting at the given byte position."""
    if not filepath.exists():
        return [], position
    lines = []
    try:
        with open(filepath, "r") as f:
            f.seek(position)
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        log.warning("Skipping malformed line in %s: %s — %r", filepath.name, e, line[:80])
            new_position = f.tell()
    except OSError as e:
        log.error("Failed to read %s: %s", filepath, e)
        return [], position
    return lines, new_position


@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "dashboard.html"
    return HTMLResponse(content=html_path.read_text())


@app.post("/clear")
async def clear_session():
    """Truncate stroke and AI log files to start a fresh session."""
    for path in (STROKE_FILE, AI_LOG_FILE):
        if path.exists():
            try:
                path.write_text("")
                log.info("Cleared %s", path)
            except OSError as e:
                log.error("Failed to clear %s: %s", path, e)
    return {"status": "cleared"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Send full history on connect
    stroke_pos = 0
    ai_pos = 0

    history_dots, stroke_pos = read_lines_from(STROKE_FILE, 0)
    if history_dots:
        await websocket.send_json({"type": "dots", "data": history_dots})

    history_ai, ai_pos = read_lines_from(AI_LOG_FILE, 0)
    if history_ai:
        await websocket.send_json({"type": "ai_response", "data": history_ai})

    log.info("WebSocket client connected")
    try:
        while True:
            new_dots, stroke_pos = read_lines_from(STROKE_FILE, stroke_pos)
            new_ai, ai_pos = read_lines_from(AI_LOG_FILE, ai_pos)

            if new_dots:
                await websocket.send_json({"type": "dots", "data": new_dots})
            if new_ai:
                await websocket.send_json({"type": "ai_response", "data": new_ai})

            await asyncio.sleep(POLL_INTERVAL)
    except WebSocketDisconnect:
        log.info("WebSocket client disconnected")
    except Exception:
        log.exception("Unexpected error in WebSocket handler")
