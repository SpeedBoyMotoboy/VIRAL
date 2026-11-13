FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV VIRAL_HOST=0.0.0.0 \
    VIRAL_PORT=5000 \
    VIRAL_DOWNLOAD_DIR=/data/downloads \
    PYTHONUNBUFFERED=1

EXPOSE 5000
CMD ["python", "-m", "viral", "web"]
