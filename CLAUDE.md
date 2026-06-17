# InkTutor — CLAUDE.md

AI math tutor for 6th graders. Smart pen captures strokes on Ncode paper,
AI watches the work in real time, speaks feedback through audio. No screen.

## Architecture

```
Mac Host (pen_host.py)            Docker Container (tutor.py)
──────────────────────────────    ──────────────────────────────
bleak BLE → Neo LAMY pen          reads /tmp/inktutor/strokes.jsonl
writes stroke dots as JSONL  ───► buffers strokes
                                  detects pause (default 3s)
                                  renders strokes → PNG
                                  calls Claude vision API
                                  speaks response via TTS
                                  logs AI responses → ai_responses.jsonl

                                  Docker Container (dashboard.py)
                                  ──────────────────────────────
                                  FastAPI + WebSocket on port 8080
                                  tails strokes.jsonl (live dots)
                                  tails ai_responses.jsonl (AI log)
                                  streams to browser in real time
```

Bluetooth cannot pass through Docker Desktop on Mac. The BLE script runs
on the host and communicates with the container via a shared file at
`/tmp/inktutor/strokes.jsonl`.

## File Structure

```
inktutor/
├── CLAUDE.md           this file
├── Dockerfile          Python 3.12-slim, audio/TTS deps
├── docker-compose.yml  mounts ./:/app and /tmp/inktutor
├── requirements.txt    anthropic, Pillow, pyttsx3, elevenlabs, bleak, fastapi
├── .env.example        copy to .env, add API keys
├── pen_host.py         runs on Mac host — BLE pen listener
├── tutor.py            runs in Docker — AI tutor loop
├── nodes.py            AI pipeline node definitions and prompts
├── ai_graph.py         LangGraph multi-node pipeline layer
├── dashboard.py        runs in Docker — real-time monitoring dashboard
├── static/
│   └── dashboard.html  single-page dashboard frontend
└── ios/
    └── ink-tutor-ios/  SwiftUI iPad app (Xcode project)
        ├── InkTutorApp.swift       app entry point, SwiftData container
        ├── Models/
        │   └── Sheet.swift         @Model: title, createdAt, drawingData, pdfData
        └── Views/
            ├── HomeView.swift      grid of Sheet cards, create/delete
            ├── CanvasEditor.swift  PDF background + PencilKit overlay, toolbar
            ├── CanvasView.swift    UIViewRepresentable wrapping PKCanvasView
            └── PDFBackgroundView.swift  renders PDF page as canvas background
```

## Running the Project

```bash
# 1. Copy and fill in env
cp .env.example .env

# 2. Start the AI tutor container
docker-compose up

# 3. In a second terminal, start the pen listener on the host
pip install bleak
python pen_host.py

# 4. Turn on the LAMY pen and write on Ncode paper
```

The dashboard starts automatically with `docker-compose up` and is available
at **http://localhost:8080**. It shows live pen strokes, stats, and AI
response history. Click **Clear** to reset for a new session.

To test without the pen, append dots manually:
```bash
echo '{"x":100,"y":200,"pressure":500,"ts":'$(date +%s.%N)',"type":"dot"}' >> /tmp/inktutor/strokes.jsonl
```

## Key Files

### pen_host.py
- Scans for Neo pen via BLE using `bleak`
- Parses raw dot packets into `{x, y, pressure, ts, type}` dicts
- Appends each dot as a JSON line to `/tmp/inktutor/strokes.jsonl`
- Runs on Mac host only — never inside Docker

### tutor.py
- Tails `strokes.jsonl` using a file position cursor (non-blocking)
- Accumulates dots into a stroke buffer
- Fires when pen has been idle for `PAUSE_THRESHOLD_SECONDS`
- Renders dots onto a white 1200×900 canvas using Pillow
- Runs the AI graph from `nodes.py` and speaks the response
- Speaks the response via `pyttsx3` (default) or ElevenLabs
- Logs each AI response to `/tmp/inktutor/ai_responses.jsonl` for the dashboard
- Resets idle timer after each AI call

### nodes.py
- Defines `ANALYZE_PROMPT` and `TUTOR_PROMPT` — the system prompts that
  control AI behaviour (highest-leverage thing to iterate on)
- `build_graph()` wires up the 2-node pipeline: analyze (vision) → tutor (text)
- Analyzer uses OpenRouter (Gemini Flash), tutor uses Anthropic (Haiku)

### dashboard.py
- FastAPI app with a WebSocket endpoint (`/ws`) on port 8080
- Tails `strokes.jsonl` and `ai_responses.jsonl` at 50ms intervals
- Sends full stroke history on client connect, then streams new dots
- `POST /clear` truncates both JSONL files for a fresh session
- Frontend (`static/dashboard.html`) renders strokes on an HTML5 Canvas,
  shows live stats (dot count, dots/sec, avg pressure, pause status),
  and a scrollable AI response log

## Environment Variables

| Variable                  | Default   | Description                       |
|---------------------------|-----------|-----------------------------------|
| `ANTHROPIC_API_KEY`       | required  | Claude API key (read in tutor.py) |
| `PAUSE_THRESHOLD_SECONDS` | `3.0`     | Idle time before AI fires         |
| `TTS_ENGINE`              | `pyttsx3` | `pyttsx3` or `elevenlabs`         |
| `ELEVENLABS_API_KEY`      | —         | Required if TTS_ENGINE=elevenlabs |
| `ELEVENLABS_VOICE_ID`     | `Rachel`  | ElevenLabs voice                  |

## Switching AI Provider

Edit the `GraphNode` configs in `nodes.py`. All provider config classes live in `ai_connect.py`:

```python
from ai_connect import AnthropicConfig, OpenAIConfig, OpenRouterConfig, OpenRouterVisionModel

# Anthropic
config=AnthropicConfig(model="claude-haiku-4-5")

# OpenAI
config=OpenAIConfig(model="gpt-4o")

# OpenRouter — swap any vision model without changing anything else
config=OpenRouterConfig(model=OpenRouterVisionModel.GEMINI_3_1_FLASH_LITE_PREVIEW)
```

## LangGraph Multi-Node Pipelines

For multi-step AI workflows, use `ai_graph.py` which layers LangGraph on top
of `ai_connect.py`. Each graph node gets its own model, system prompt, and
config — swap models per-node with zero friction.

### Single node (equivalent to AIConnect.ask)

```python
from ai_graph import TutorGraph, GraphNode
from ai_connect import AnthropicConfig

graph = (TutorGraph()
    .add_node(GraphNode(
        name="tutor",
        system_prompt=SYSTEM_PROMPT,
        config=AnthropicConfig(api_key="sk-ant-..."),
    ))
    .set_entry("tutor")
    .add_edge("tutor", "end"))

response = graph.run(image_b64="...", prompt="What do you see?")
```

### Multi-node with conditional routing

Use a cheap/fast model for triage, then route to a stronger model only when
the student needs help:

```python
from ai_graph import TutorGraph, GraphNode
from ai_connect import AnthropicConfig, OpenRouterConfig, OPENROUTER_VISION_MODELS

analyzer = GraphNode(
    name="analyze",
    system_prompt="Respond OK if correct, ERROR if wrong.",
    config=OpenRouterConfig(
        api_key="sk-or-...",
        model=OPENROUTER_VISION_MODELS["gemini-2.5-flash"],
    ),
)
tutor = GraphNode(
    name="tutor",
    system_prompt=SYSTEM_PROMPT,
    config=AnthropicConfig(api_key="sk-ant-...", max_tokens=200),
)

def route(state):
    return "ok" if state["response"].strip().upper() == "OK" else "needs_help"

graph = (TutorGraph()
    .add_node(analyzer)
    .add_node(tutor)
    .set_entry("analyze")
    .add_conditional_edge("analyze", route, {"ok": "end", "needs_help": "tutor"})
    .add_edge("tutor", "end"))
```

### Key concepts

- **`TutorState`** — TypedDict flowing through every node (image, prompt,
  response, route, per-node outputs)
- **`GraphNode`** — callable dataclass wrapping its own LLM + system prompt.
  Accepts an optional `input_formatter` for custom input extraction.
- **`TutorGraph`** — fluent builder: `add_node()`, `set_entry()`,
  `add_edge()`, `add_conditional_edge()`, `compile()`, `run()`
- Routing is done via plain Python functions — no LLM call needed for simple
  cases like checking if the response is "OK"
- `node_outputs` dict in state gives access to every node's output by name
- Pass `callbacks` to `graph.run()` for Langfuse integration

## AI Tutor Behaviour

The system prompt instructs Claude to:
- Ask **one** short Socratic question only — never give the answer
- Respond with just `OK` if the work looks correct (triggers silence)
- Keep responses under 15 words
- Identify the exact step where an error occurred
- Sound like a friendly older student, not a teacher

Tweak the system prompts in `nodes.py` (`ANALYZE_PROMPT`, `TUTOR_PROMPT`)
to adjust behaviour. This is the highest-leverage thing to iterate on.

## Swapping TTS

Default is `pyttsx3` — offline, no API key, robotic voice. Fine for testing.
To upgrade to ElevenLabs:

```bash
# In .env:
TTS_ENGINE=elevenlabs
ELEVENLABS_API_KEY=your_key
ELEVENLABS_VOICE_ID=Rachel
```

## Changing the Problem

Currently hardcoded in `tutor.py`:

```python
current_problem = "Solve: 3/4 + 1/6"
```

Next step: read from a QR code in the corner of the worksheet. Use a
separate phone scan at session start, or a small webcam pointed at the paper.

## Known Issues / Next Steps

- **BLE UUIDs** in `pen_host.py` may need adjustment for the LAMY Safari
  specifically. If the pen connects but no dots arrive, check UUIDs against
  the Neo SDK on GitHub: https://github.com/NeoSmartpen/Windows-SDK2.0
- **Stroke rendering** is naive (dots only, no line interpolation). Add line
  segments between consecutive dots for cleaner images and better AI reads.
- **Pause threshold** (3s) is a starting point. Tune based on a real student
  writing — too low fires mid-thought, too high feels unresponsive.
- **Audio playback** inside Docker on Mac may not work out of the box.
  Fallback: write TTS audio to a file in `/tmp/inktutor` and play it from
  the host.

## iOS App (iPad)

The `ios/` directory contains a SwiftUI iPad app — the v1 student-facing interface. It replaces the original "no screen" design with an iPad canvas where students work on imported worksheets using Apple Pencil.

### What it does (current scaffold)
- **HomeView** — grid of `Sheet` cards (SwiftData), create blank or PDF-backed sheets, delete via context menu
- **CanvasEditor** — import a PDF worksheet (`fileImporter`), renders it as a background layer, draws Apple Pencil ink on top via PencilKit; pen/eraser toggle and undo in toolbar
- **Sheet model** — `@Model` with `title`, `createdAt`, `drawingData` (PKDrawing bytes), and optional `pdfData` (imported PDF)
- Ink saved to SwiftData on view disappear; PDF and drawing restored on appear

### v1 target architecture (planned, not yet built)
- `POST /worksheet` — upload PDF → backend tags skills with `tag_skills` node (vision), returns `{worksheet_id, skills}`
- `POST /attempt` — on pen-idle pause, render canvas + PDF → PNG, POST to backend → `{events, intent}`
- Backend runs `diagnose` (vision) → `decide` (text) nodes in `nodes.py`
- On-device: Apple Foundation Models (iOS 27+) generates practice problems from `intent` and voices feedback; FM image input used for page-aware triage (decide if there's enough work to diagnose before sending to backend)
- New problems rendered onto a fresh sheet in-app

### Running the iOS app
Open `ios/ink-tutor-ios/ink-tutor-ios.xcodeproj` in Xcode, target an iPad or iPad simulator running iOS 18+. No additional dependencies — pure SwiftUI + PencilKit + SwiftData.

For the full backend loop, the iPad must reach the Docker backend over LAN (`http://<mac-ip>:8080`).

## Hardware

- **Pen:** LAMY Safari All Black Ncode (NWP-F80) — ~$169 on Amazon
- **Paper:** Neo Ncode notebooks, or print Ncode PDF on a PostScript
  color laser printer (free from Neo's GitHub)
- **Neo SDK:** https://github.com/NeoSmartpen
- **Python BLE lib:** https://github.com/hbldh/bleak
