# InkTutor

An AI math tutor for 6th graders. A smart pen captures handwriting, AI watches the work in real time, and speaks Socratic feedback through audio.

## How It Works

A pen transmits stroke or sensor data via Bluetooth. A host script receives the data and writes it to a shared file. A Docker container watches that file, and when the pen has been idle for a few seconds, renders the strokes as an image and sends it to Claude for analysis. The AI speaks one short coaching question back to the student.

```
Mac Host (pen_host.py)           Docker (tutor + dashboard + api)
──────────────────────────────   ──────────────────────────────
BLE → pen (Ncode or custom)      reads /tmp/inktutor/strokes.jsonl
writes stroke dots as JSONL ──► detects pause → renders PNG
                                 → Claude vision API → TTS audio

                                 dashboard  → http://localhost:8080
                                 REST API   → http://localhost:8000
```

## Requirements

- Mac (BLE required for pen host)
- Docker Desktop
- Pen: LAMY Safari Ncode (NWP-F80) **or** custom ESP32 pen (`ink-tutor-firmware/`)
- Anthropic API key

## Setup

```bash
# 1. Copy env file and add your API keys
cp .env.example .env

# 2. Start all services (tutor + dashboard + API)
docker-compose up

# 3. In a separate terminal, run the pen listener on the host
pip install bleak
python pen_host.py

# 4. Turn on the pen and write
```

| Service   | URL                       | Description                        |
|-----------|---------------------------|------------------------------------|
| Dashboard | http://localhost:8080     | Live strokes, stats, AI log        |
| API       | http://localhost:8000     | REST API (worksheet/attempt routes)|
| API docs  | http://localhost:8000/docs| Auto-generated OpenAPI docs        |

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

Edit the `GraphNode` configs in `nodes.py`. See `CLAUDE.md` for examples.

## Hardware

### Option A — LAMY Safari Ncode pen (NWP-F80)
- ~$169 on Amazon
- Neo Ncode notebooks, or print Ncode PDF on a PostScript color laser
- Neo SDK: https://github.com/NeoSmartpen

### Option B — Custom ESP32 pen (`ink-tutor-firmware/`)
- ESP32 dev board + BMI270 IMU + FSR pressure sensor
- PlatformIO project — flash with `pio run --target upload`
- Streams `{fsr, ax, ay, az, gx, gy, gz}` JSON over BLE at 20 Hz
