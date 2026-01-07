# Python ka lightweight version
FROM python:3.9-slim

# System update karo aur FFmpeg + Node.js install karo
# Node.js zaroori hai yt-dlp ki speed badhane ke liye
RUN apt-get update && \
    apt-get install -y ffmpeg nodejs && \
    rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Dependencies install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Saara code copy
COPY . .

# Port expose
EXPOSE 8000

# Server start
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
