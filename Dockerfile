# Base image
FROM python:3.11-slim

# Install ffmpeg (required by yt-dlp for merging audio+video)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy files
COPY requirements.txt .
COPY server.py .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create downloads folder
RUN mkdir downloads

# Expose port (Render provides $PORT env)
ENV PORT=10000

# Command
CMD ["gunicorn", "server:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:$PORT", "--workers", "1"]
