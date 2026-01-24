from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
import subprocess, os

app = FastAPI()

# Allow requests from any frontend (or specify your domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "./downloads"  # Render container me storage volatile
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

QUALITY_MAP = {
    "144": "bv*[height<=144]+ba/b",
    "240": "bv*[height<=240]+ba/b",
    "360": "bv*[height<=360]+ba/b",
    "480": "bv*[height<=480]+ba/b",
    "720": "bv*[height<=720]+ba/b",
    "1080": "bv*[height<=1080]+ba/b",
}

@app.post("/download")
def download(url: str = Form(...), quality: str = Form(...)):
    fmt = QUALITY_MAP.get(quality)
    if not fmt:
        return {"error": "Invalid quality"}

    # WARNING: Render file system is ephemeral
    # After container restart, files will disappear
    cmd = [
        "yt-dlp",
        "-f", fmt,
        "-o", f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        url
    ]
    subprocess.Popen(cmd)
    return {"status": "Download started"}
