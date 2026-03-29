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

from ai_connect import AnthropicConfig
from ai_graph import TutorGraph, GraphNode

# ── Config ──────────────────────────────────────────────────────────────────
STROKE_FILE         = Path("/tmp/inktutor/strokes.jsonl")
AI_LOG_FILE         = Path("/tmp/inktutor/ai_responses.jsonl")
PAUSE_THRESHOLD     = float(os.getenv("PAUSE_THRESHOLD_SECONDS", "3.0"))
CANVAS_SIZE         = (1200, 900)
DOT_RADIUS          = 3
TTS_ENGINE          = os.getenv("TTS_ENGINE", "pyttsx3")

ANALYZE_PROMPT = """You are an image analysis assistant looking at a 6th grader's
handwritten math work on paper.

Rules:
- Describe exactly what the student has written: numbers, symbols, steps.
- Note which step they are on and whether each step looks correct or has an error.
- If there is an error, identify the exact step and what went wrong.
- If all work so far is correct, say "All steps correct so far."
- Be factual and concise. No opinions, no questions, no encouragement.
"""

TUTOR_PROMPT = """You are a warm, patient math tutor helping a 6th grade student.
You will receive a description of what the student has written so far.

Rules:
- Ask ONE short Socratic question only. Never give the answer directly.
- If the description says all steps are correct, respond with just "OK".
- If there is an error, guide the student to find it themselves.
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



def log_ai_response(feedback: str, dot_count: int):
    """Append AI response to log file for dashboard consumption."""
    entry = {"ts": time.time(), "feedback": feedback, "dot_count": dot_count}
    with open(AI_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


SPEECH_FILE = Path("/tmp/inktutor/speech.wav")


def speak(text: str):
    """Write TTS audio to a shared file; the host plays it."""
    if text.upper() == "OK":
        return  # AI said nothing to say — stay silent

    if TTS_ENGINE == "elevenlabs":
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
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


# ── Main loop ────────────────────────────────────────────────────────────────
def build_graph() -> TutorGraph:
    """Build the 2-node pipeline: analyze image → Socratic tutor."""
    analyzer = GraphNode(
        name="analyze",
        system_prompt=ANALYZE_PROMPT,
        config=AnthropicConfig(),
    )
    tutor = GraphNode(
        name="tutor",
        system_prompt=TUTOR_PROMPT,
        config=AnthropicConfig(),
        input_formatter=lambda state: (
            "",  # text-only — no image needed
            f"The student is solving: {state['prompt']}\n\n"
            f"Description of their work:\n{state['node_outputs']['analyze']}",
        ),
    )
    return (TutorGraph()
        .add_node(analyzer)
        .add_node(tutor)
        .set_entry("analyze")
        .add_edge("analyze", "tutor")
        .add_edge("tutor", "end"))


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
                last_dot_time = 0.0  # reset so we don't fire again immediately

        await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
