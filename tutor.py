"""
tutor.py  —  runs inside Docker
Reads stroke events from /tmp/inktutor/strokes.jsonl,
renders them as an image, calls Claude vision, speaks the response.
"""

import asyncio
import base64
import json
import os
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from nodes import build_graph

# ── Config ──────────────────────────────────────────────────────────────────
STROKE_FILE         = Path("/tmp/inktutor/strokes.jsonl")
AI_LOG_FILE         = Path("/tmp/inktutor/ai_responses.jsonl")
PAUSE_THRESHOLD     = float(os.getenv("PAUSE_THRESHOLD_SECONDS", "3.0"))
CANVAS_SIZE         = (1200, 900)
DOT_RADIUS          = 3
TTS_ENGINE          = os.getenv("TTS_ENGINE", "pyttsx3")

# ── Stroke buffer ────────────────────────────────────────────────────────────
strokes: list[dict] = []
last_dot_time: float = 0.0
file_position: int = 0


def read_new_dots() -> list[dict]:
    """Read any new dot events appended to the stroke file."""
    global file_position
    if not STROKE_FILE.exists():
        return []
    dots = []
    try:
        with open(STROKE_FILE, "r") as f:
            f.seek(file_position)
            for line in f:
                line = line.strip()
                if line:
                    try:
                        dots.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            file_position = f.tell()
    except OSError as e:
        print(f"Warning: could not read stroke file: {e}")
    return dots


def render_strokes(dots: list[dict]) -> str:
    """Render dot list to a base64-encoded PNG."""
    img = Image.new("RGB", CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(img)

    if dots:
        # Normalise coordinates to canvas
        xs = [d["x"] for d in dots if "x" in d]
        ys = [d["y"] for d in dots if "y" in d]
        if not xs or not ys:
            print("Warning: dots missing x/y fields — rendering blank canvas")
        else:
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            x_range = max(x_max - x_min, 1)
            y_range = max(y_max - y_min, 1)

            padding = 80
            w = CANVAS_SIZE[0] - padding * 2
            h = CANVAS_SIZE[1] - padding * 2

            for dot in dots:
                try:
                    cx = padding + int((dot["x"] - x_min) / x_range * w)
                    cy = padding + int((dot["y"] - y_min) / y_range * h)
                    r = DOT_RADIUS
                    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="black")
                except (KeyError, ValueError, ZeroDivisionError) as e:
                    print(f"Warning: skipping malformed dot {dot}: {e}")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode()



def log_ai_response(feedback: str, dot_count: int):
    """Append AI response to log file for dashboard consumption."""
    entry = {"ts": time.time(), "feedback": feedback, "dot_count": dot_count}
    try:
        with open(AI_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"Warning: could not write AI log: {e}")


SPEECH_FILE = Path("/tmp/inktutor/speech.wav")


def speak(text: str):
    """Write TTS audio to a shared file; the host plays it."""
    if text.upper() == "OK":
        return  # AI said nothing to say — stay silent

    try:
        if TTS_ENGINE == "elevenlabs":
            from elevenlabs import ElevenLabs
            api_key = os.environ.get("ELEVENLABS_API_KEY")
            if not api_key:
                print("Warning: ELEVENLABS_API_KEY not set — skipping speech")
                return
            client = ElevenLabs(api_key=api_key)
            audio = client.generate(
                text=text,
                voice=os.getenv("ELEVENLABS_VOICE_ID", "Rachel"),
                model="eleven_monolingual_v1",
            )
            SPEECH_FILE.write_bytes(b"".join(audio))
        else:
            import subprocess
            # espeak-ng writes directly to WAV; no audio device needed in Docker
            subprocess.run(
                ["espeak-ng", "-w", str(SPEECH_FILE), "-s", "160", text],
                check=True,
            )
    except Exception as e:
        print(f"Warning: TTS failed ({TTS_ENGINE}): {e}")


# ── Main loop ────────────────────────────────────────────────────────────────
async def main():
    global last_dot_time

    graph = build_graph()

    # Hardcoded for now — later read from worksheet QR code
    current_problem = "Solve: 3/4 + 1/6"

    print(f"InkTutor ready. Problem: {current_problem}")
    print(f"Watching {STROKE_FILE} for strokes...")
    print(f"Pause threshold: {PAUSE_THRESHOLD}s\n")

    while True:
        new_dots = read_new_dots()

        if new_dots:
            strokes.extend(new_dots)
            last_dot_time = time.time()

        elif strokes and last_dot_time:
            idle = time.time() - last_dot_time

            if idle >= PAUSE_THRESHOLD:
                print(f"Pause detected ({idle:.1f}s). Analysing work...")
                last_dot_time = 0.0  # reset immediately so a failure doesn't re-fire
                try:
                    image_b64 = render_strokes(strokes)
                    prompt = f"The student is solving: {current_problem}\nWhat do you see in their work so far?"
                    feedback = graph.run(
                        image_b64=image_b64,
                        prompt=prompt,
                        metadata={"problem": current_problem, "dot_count": len(strokes)},
                    )
                    log_ai_response(feedback, len(strokes))
                    print(f"AI: {feedback}")
                    speak(feedback)
                except Exception as e:
                    print(f"Error during AI analysis: {e}")

        await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down.")
    except Exception as e:
        print(f"Fatal error: {e}")
        raise
