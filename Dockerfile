# Python ka lightweight version use kar rahe hain
FROM python:3.9-slim

# System dependencies update karo aur FFmpeg install karo
# yt-dlp ke liye FFmpeg zaroori hai
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Working directory set karo
WORKDIR /app

# Requirements file copy karo aur install karo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Saara code copy karo
COPY . .

# Port expose karo (Render ke liye zaroori hai)
EXPOSE 8000

# Server start karne ki command
CMD ["uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"]
