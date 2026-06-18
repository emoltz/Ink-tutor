FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    espeak-ng \
    espeak-ng-data \
    libespeak-ng1 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tutor.py .
COPY ai_connect.py .
COPY ai_graph.py .
COPY dashboard.py .
COPY api/ api/
COPY static/ static/

CMD ["python", "tutor.py"]
