# InkTutor

An AI math tutor for 6th graders. A smart pen captures handwriting on Ncode paper, AI watches the work in real time, and speaks Socratic feedback through audio — no screen required.

## How It Works

A LAMY Safari Ncode pen transmits stroke data via Bluetooth. A host script receives the dots and writes them to a shared file. A Docker container watches that file, and when the pen has been idle for a few seconds, renders the strokes as an image and sends it to Claude for analysis. The AI speaks one short coaching question back to the student.

```
Mac Host (pen_host.py)           Docker Container (tutor.py)
──────────────────────────────   ──────────────────────────────
BLE → Neo LAMY pen               reads /tmp/inktutor/strokes.jsonl
writes stroke dots as JSONL ──► detects pause → renders PNG
                                 → Claude vision API → TTS audio
```

A browser dashboard at `http://localhost:8080` shows live pen strokes, stats, and AI response history.

## Requirements

- Mac (BLE required for pen host)
- Docker Desktop
- LAMY Safari All Black Ncode pen (NWP-F80)
- Neo Ncode paper (or printed Ncode PDF)
- Anthropic API key

## Setup

```bash
# 1. Copy env file and add your API keys
cp .env.example .env

# 2. Start the AI tutor + dashboard
docker-compose up

# 3. In a separate terminal, run the pen listener on the host
pip install bleak
python pen_host.py

# 4. Turn on the LAMY pen and write on Ncode paper
```

The dashboard is available at **http://localhost:8080**.

## Testing Without a Pen

Append dot events manually to simulate pen input:

```bash
echo '{"x":100,"y":200,"pressure":500,"ts":'$(date +%s.%N)',"type":"dot"}' >> /tmp/inktutor/strokes.jsonl
```

## Configuration

| Variable                  | Default   | Description                        |
|---------------------------|-----------|------------------------------------|
| `ANTHROPIC_API_KEY`       | required  | Claude API key                     |
| `PAUSE_THRESHOLD_SECONDS` | `3.0`     | Idle time (seconds) before AI fires|
| `TTS_ENGINE`              | `pyttsx3` | `pyttsx3` (offline) or `elevenlabs`|
| `ELEVENLABS_API_KEY`      | —         | Required if using ElevenLabs TTS   |
| `ELEVENLABS_VOICE_ID`     | `Rachel`  | ElevenLabs voice name              |

## Switching AI Provider

Edit the `AIConnect` instantiation in `tutor.py`. Anthropic, OpenAI, and OpenRouter are supported via `ai_connect.py`. See `CLAUDE.md` for examples.

## Hardware

- **Pen:** LAMY Safari All Black Ncode (NWP-F80) — ~$169
- **Paper:** Neo Ncode notebooks, or print Ncode PDF on a PostScript color laser
- **Neo SDK:** https://github.com/NeoSmartpen
