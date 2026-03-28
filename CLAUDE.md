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
├── requirements.txt    anthropic, Pillow, pyttsx3, elevenlabs, bleak
├── .env.example        copy to .env, add API keys
├── pen_host.py         runs on Mac host — BLE pen listener
└── tutor.py            runs in Docker — AI tutor loop
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
- Sends the PNG + problem text to an AI vision model via LangChain
- Provider/model configured via `AI_PROVIDER` / `AI_MODEL` env vars
- Speaks the response via `pyttsx3` (default) or ElevenLabs
- Resets idle timer after each AI call

## Environment Variables

| Variable                  | Default                          | Description                                              |
|---------------------------|----------------------------------|----------------------------------------------------------|
| `AI_PROVIDER`             | `anthropic`                      | `anthropic`, `openai`, or `openrouter`                   |
| `AI_MODEL`                | provider default                 | Model ID override (e.g. `gpt-4o`, `google/gemini-flash-1.5`) |
| `ANTHROPIC_API_KEY`       | required for anthropic provider  | Claude API key                                           |
| `OPENAI_API_KEY`          | required for openai provider     | OpenAI API key                                           |
| `OPENROUTER_API_KEY`      | required for openrouter provider | OpenRouter API key                                       |
| `OPENROUTER_BASE_URL`     | `https://openrouter.ai/api/v1`   | Override OpenRouter base URL                             |
| `OPENROUTER_REFERER`      | `https://github.com/inktutor`    | HTTP-Referer header sent to OpenRouter                   |
| `OPENROUTER_APP_TITLE`    | `InkTutor`                       | X-Title header sent to OpenRouter                        |
| `PAUSE_THRESHOLD_SECONDS` | `3.0`                            | Idle time before AI fires                                |
| `TTS_ENGINE`              | `pyttsx3`                        | `pyttsx3` or `elevenlabs`                                |
| `ELEVENLABS_API_KEY`      | —                                | Required if TTS_ENGINE=elevenlabs                        |
| `ELEVENLABS_VOICE_ID`     | `Rachel`                         | ElevenLabs voice                                         |

## AI Tutor Behaviour

The system prompt instructs Claude to:
- Ask **one** short Socratic question only — never give the answer
- Respond with just `OK` if the work looks correct (triggers silence)
- Keep responses under 15 words
- Identify the exact step where an error occurred
- Sound like a friendly older student, not a teacher

Tweak the system prompt in `tutor.py` → `SYSTEM_PROMPT` to adjust behaviour.
This is the highest-leverage thing to iterate on.

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

## Hardware

- **Pen:** LAMY Safari All Black Ncode (NWP-F80) — ~$169 on Amazon
- **Paper:** Neo Ncode notebooks, or print Ncode PDF on a PostScript
  color laser printer (free from Neo's GitHub)
- **Neo SDK:** https://github.com/NeoSmartpen
- **Python BLE lib:** https://github.com/hbldh/bleak
