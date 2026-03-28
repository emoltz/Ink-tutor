FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    espeak \
    libespeak1 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tutor.py .

CMD ["python", "tutor.py"]
