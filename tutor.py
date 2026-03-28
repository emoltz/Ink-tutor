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

import anthropic
from PIL import Image, ImageDraw

# ── Config ──────────────────────────────────────────────────────────────────
STROKE_FILE         = Path("/tmp/inktutor/strokes.jsonl")
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


def call_ai(image_b64: str, problem: str) -> str:
    """Send the rendered stroke image to Claude and get tutor feedback."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=100,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": f"The student is solving: {problem}\nWhat do you see in their work so far?"
                }
            ],
        }],
    )
    return response.content[0].text.strip()


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
                image_b64 = render_strokes(strokes)
                feedback = call_ai(image_b64, current_problem)
                print(f"AI: {feedback}")
                speak(feedback)
                last_dot_time = 0.0  # reset so we don't fire again immediately

        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
