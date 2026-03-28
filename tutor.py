"""
tutor.py  —  runs inside Docker
Reads stroke events from /tmp/inktutor/strokes.jsonl,
renders them as an image, calls Claude vision, speaks the response.
"""

import asyncio
import base64
import json
import logging
import os
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from ai_connect import AIConnect, AnthropicConfig

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("tutor")

# ── Config ──────────────────────────────────────────────────────────────────
STROKE_FILE         = Path("/tmp/inktutor/strokes.jsonl")
AI_LOG_FILE         = Path("/tmp/inktutor/ai_responses.jsonl")
PAUSE_THRESHOLD     = float(os.getenv("PAUSE_THRESHOLD_SECONDS", "3.0"))
CANVAS_SIZE         = (1200, 900)
DOT_RADIUS          = 3
TTS_ENGINE          = os.getenv("TTS_ENGINE", "pyttsx3")

SYSTEM_PROMPT = """You are a warm, patient math tutor watching a 6th grade student
work through a problem on paper. You can see their handwritten work so far.

Rules:
- Ask ONE short Socratic question only. Never give the answer directly.
- If the work looks correct so far, say nothing (respond with just "OK").
- If you see an error, identify the exact step where it went wrong.
- Keep responses under 15 words.
- Sound like a friendly older student, not a teacher.
"""

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
                    except json.JSONDecodeError as e:
                        log.warning("Skipping malformed stroke line: %s — %r", e, line[:80])
            file_position = f.tell()
    except OSError as e:
        log.error("Failed to read stroke file %s: %s", STROKE_FILE, e)
    return dots


def render_strokes(dots: list[dict]) -> str:
    """Render dot list to a base64-encoded PNG."""
    img = Image.new("RGB", CANVAS_SIZE, "white")
    draw = ImageDraw.Draw(img)

    if dots:
        # Normalise coordinates to canvas
        xs = [d["x"] for d in dots]
        ys = [d["y"] for d in dots]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        x_range = max(x_max - x_min, 1)
        y_range = max(y_max - y_min, 1)

        padding = 80
        w = CANVAS_SIZE[0] - padding * 2
        h = CANVAS_SIZE[1] - padding * 2

        for dot in dots:
            cx = padding + int((dot["x"] - x_min) / x_range * w)
            cy = padding + int((dot["y"] - y_min) / y_range * h)
            r = DOT_RADIUS
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="black")

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
        log.error("Failed to write AI response log %s: %s", AI_LOG_FILE, e)


def speak(text: str):
    """Speak text using the configured TTS engine."""
    if text.upper() == "OK":
        return  # AI said nothing to say — stay silent

    if TTS_ENGINE == "elevenlabs":
        from elevenlabs import ElevenLabs, play
        client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
        audio = client.generate(
            text=text,
            voice=os.getenv("ELEVENLABS_VOICE_ID", "Rachel"),
            model="eleven_monolingual_v1",
        )
        play(audio)
    else:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", 160)
        engine.say(text)
        engine.runAndWait()


# ── Main loop ────────────────────────────────────────────────────────────────
async def main():
    global last_dot_time

    ai = AIConnect(
        system_prompt=SYSTEM_PROMPT,
        config=AnthropicConfig(api_key=os.environ["ANTHROPIC_API_KEY"]),
    )

    # Hardcoded for now — later read from worksheet QR code
    current_problem = "Solve: 3/4 + 1/6"

    log.info("InkTutor ready. Problem: %s", current_problem)
    log.info("Watching %s for strokes...", STROKE_FILE)
    log.info("Pause threshold: %ss", PAUSE_THRESHOLD)

    while True:
        new_dots = read_new_dots()

        if new_dots:
            strokes.extend(new_dots)
            last_dot_time = time.time()
            log.debug("Received %d new dot(s), total: %d", len(new_dots), len(strokes))

        elif strokes and last_dot_time:
            idle = time.time() - last_dot_time

            if idle >= PAUSE_THRESHOLD:
                log.info("Pause detected (%.1fs, %d dots). Analysing work...", idle, len(strokes))
                try:
                    image_b64 = render_strokes(strokes)
                    prompt = f"The student is solving: {current_problem}\nWhat do you see in their work so far?"
                    feedback = ai.ask(image_b64, prompt)
                    log_ai_response(feedback, len(strokes))
                    log.info("AI response: %s", feedback)
                    speak(feedback)
                except Exception:
                    log.exception("AI analysis failed")
                finally:
                    last_dot_time = 0.0  # reset so we don't fire again immediately

        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
