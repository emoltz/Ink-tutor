"""
dashboard.py  —  real-time pen monitoring dashboard
Tails strokes.jsonl and ai_responses.jsonl, streams updates to browser via WebSocket.
Run with: uvicorn dashboard:app --host 0.0.0.0 --port 8080
"""

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

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
                    except json.JSONDecodeError:
                        pass
            new_position = f.tell()
    except OSError:
        return [], position
    return lines, new_position


@app.get("/")
async def index():
    html_path = Path(__file__).parent / "static" / "dashboard.html"
    try:
        return HTMLResponse(content=html_path.read_text())
    except OSError as e:
        return HTMLResponse(
            content=f"<pre>Dashboard UI not found: {e}</pre>", status_code=500
        )


@app.post("/inject")
async def inject_dot(dot: dict):
    """Append a simulated dot to the stroke file (for draw mode)."""
    try:
        STROKE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with STROKE_FILE.open("a") as f:
            f.write(json.dumps(dot) + "\n")
    except OSError as e:
        return {"status": "error", "detail": str(e)}
    return {"status": "ok"}


@app.post("/clear")
async def clear_session():
    """Truncate stroke and AI log files to start a fresh session."""
    try:
        for path in (STROKE_FILE, AI_LOG_FILE):
            if path.exists():
                path.write_text("")
    except OSError as e:
        return {"status": "error", "detail": str(e)}
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
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()
