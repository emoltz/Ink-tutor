"""
nodes.py — AI pipeline node definitions for InkTutor.

Defines the system prompts and graph wiring for the two-node pipeline:
  1. analyze — image analysis of student handwriting (vision model)
  2. tutor   — Socratic feedback based on the analysis (text model)

This is the highest-leverage file to iterate on when tuning AI behaviour.
"""

from ai_connect import AnthropicConfig, OpenRouterConfig, OPENROUTER_VISION_MODELS
from ai_graph import TutorGraph, GraphNode

ANALYZE_PROMPT = """You are an image analysis assistant looking at a 6th grader's
handwritten math work on paper.

Your first line MUST be exactly one of:
  STATUS: CORRECT
  STATUS: ERROR

Then on the following lines, describe what the student wrote.

Rules:
- List each step the student has written: numbers, symbols, operations.
- If there is an error, identify the exact step and what went wrong.
- Be factual and concise. No opinions, no questions, no encouragement.
"""

TUTOR_PROMPT = """You are a warm, patient math tutor helping a 6th grade student.
You will receive a description of what the student has written so far.
The first line is a status: either "STATUS: CORRECT" or "STATUS: ERROR".

Rules:
- If the status is CORRECT, respond with just "OK".
- If the status is ERROR, ask ONE short Socratic question to guide the student.
  Never give the answer directly.
- Keep responses under 15 words.
- Sound like a friendly older student, not a teacher.
"""


def build_graph() -> TutorGraph:
    """Build the 2-node pipeline: analyze image → Socratic tutor."""
    analyzer = GraphNode(
        name="analyze",
        system_prompt=ANALYZE_PROMPT,
        config=OpenRouterConfig(model=OPENROUTER_VISION_MODELS["gemini-2.5-flash"]),
    )
    tutor = GraphNode(
        name="tutor",
        system_prompt=TUTOR_PROMPT,
        config=AnthropicConfig(model="claude-haiku-4-5"),
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
