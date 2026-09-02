# Multi-architecture Dockerfile for Core AI (Linux, Homelab, SBC, Automotive)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies for audio, build tools, and sqlite
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libportaudio2 \
    libasound2-dev \
    libsndfile1 \
    ffmpeg \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir pytest

# Copy application source code
COPY . .

# Ensure log and dynamic tool directories exist
RUN mkdir -p logs tools/dynamic config

# Default port exposure for upcoming Web/WebSocket/REST gateways
EXPOSE 8000 6379

CMD ["python", "main.py"]
