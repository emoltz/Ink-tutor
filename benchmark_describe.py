#!/usr/bin/env python3
"""
Benchmark the describe graph across multiple model configs.
Each run is traced to Langfuse with model metadata for latency comparison.

Usage (inside Docker or on host with deps installed):
    python benchmark_describe.py [--image path/to/image.png]
"""

import argparse
import base64
import io
import os
import time
import uuid

from PIL import Image, ImageDraw, ImageFont

from ai_connect import AnthropicConfig, OpenAIConfig, OpenRouterConfig, LLMModels
from ai_graph import GraphNode, TutorGraph
from nodes import RAW_DESCRIBE_PROMPT

try:
    from langfuse.langchain import CallbackHandler as LangfuseCallback
    from langfuse.types import TraceContext
    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Model configs to benchmark
# ---------------------------------------------------------------------------
BENCHMARK_MODELS: list[tuple[str, object]] = [
    ("anthropic/claude-sonnet-4-6",      AnthropicConfig(model="claude-sonnet-4-6")),
    ("anthropic/claude-haiku-4-5",       AnthropicConfig(model="claude-haiku-4-5")),
    ("openai/gpt-5-mini",                OpenAIConfig(model="gpt-5-mini")),
    ("openai/gpt-5.4-mini",              OpenAIConfig(model="gpt-5.4-mini")),
    ("openai/gpt-5.4-nano",              OpenAIConfig(model="gpt-5.4-nano")),
    ("openrouter/mistral-3b",            OpenRouterConfig(model=LLMModels.MISTRAL_3B)),
    ("openrouter/gemini-3-flash",        OpenRouterConfig(model=LLMModels.GEMINI_3_FLASH_PREVIEW)),
    ("openrouter/gemini-3.1-flash-lite", OpenRouterConfig(model=LLMModels.GEMINI_3_1_FLASH_LITE_PREVIEW)),
]


def make_test_image() -> str:
    """Generate a simple math problem image; return base64-encoded PNG."""
    img = Image.new("RGB", (1200, 900), color="white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 80)
    except (IOError, OSError):
        font = ImageFont.load_default()
    draw.text((100, 200), "3/4 + 1/6 = ?", fill="black", font=font)
    draw.line([(80, 380), (600, 380)], fill="black", width=4)
    draw.text((100, 420), "Step 1:  3/4 = 9/12", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def load_image(path: str) -> str:
    """Load an existing image file and return base64-encoded PNG."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def build_describe_graph_for(config) -> TutorGraph:
    node = GraphNode(
        name="describe",
        system_prompt=RAW_DESCRIBE_PROMPT,
        config=config,
    )
    return (
        TutorGraph()
        .add_node(node)
        .set_entry("describe")
        .add_edge("describe", "end")
    )


def run_benchmark(image_b64: str) -> None:
    run_id = str(uuid.uuid4())[:8]

    lf = None
    if _LANGFUSE_AVAILABLE and os.getenv("LANGFUSE_PUBLIC_KEY"):
        from langfuse import Langfuse
        lf = Langfuse()

    print(f"\n{'='*60}")
    print(f"Benchmark run: {run_id}")
    print(f"Langfuse tracing: {'enabled' if lf else 'disabled'}")
    print(f"Models to test: {len(BENCHMARK_MODELS)}")
    print(f"{'='*60}\n")

    results = []
    for label, config in BENCHMARK_MODELS:
        print(f"Running: {label} ...")
        graph = build_describe_graph_for(config)

        t0 = time.perf_counter()
        try:
            if lf:
                with lf.start_as_current_observation(
                    name=label,
                    as_type="chain",
                    metadata={"model_label": label, "benchmark_run_id": run_id},
                ):
                    trace_id = lf.get_current_trace_id() or ""
                    handler = LangfuseCallback(
                        trace_context=TraceContext(trace_id=trace_id)
                    )
                    response = graph.run(
                        image_b64=image_b64,
                        prompt="Describe what you see.",
                        metadata={"model_label": label, "benchmark_run_id": run_id},
                        callbacks=[handler],
                    )
            else:
                response = graph.run(
                    image_b64=image_b64,
                    prompt="Describe what you see.",
                    metadata={"model_label": label, "benchmark_run_id": run_id},
                )
            elapsed = time.perf_counter() - t0
            status = "ok"
        except Exception as e:
            elapsed = time.perf_counter() - t0
            response = f"ERROR: {e}"
            status = "error"

        results.append((label, elapsed, status, response))
        print(f"  {elapsed:.2f}s  [{status}]  {response[:80]!r}\n")

    if lf:
        lf.flush()

    # Summary table sorted by latency
    print(f"\n{'='*60}")
    print(f"SUMMARY  (run {run_id})")
    print(f"{'='*60}")
    print(f"{'Model':<45} {'Latency':>8}  Status")
    print(f"{'-'*45} {'-'*8}  {'-'*6}")
    for label, elapsed, status, _ in sorted(results, key=lambda r: r[1]):
        print(f"{label:<45} {elapsed:>7.2f}s  {status}")
    print()
    if lf:
        print(f"Langfuse: search traces with metadata.benchmark_run_id = {run_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark describe graph across models")
    parser.add_argument("--image", default=None, help="Path to PNG to use (default: synthetic)")
    args = parser.parse_args()

    if args.image:
        print(f"Using image: {args.image}")
        image_b64 = load_image(args.image)
    else:
        print("Generating synthetic test image (math problem)...")
        image_b64 = make_test_image()

    run_benchmark(image_b64)


if __name__ == "__main__":
    main()
