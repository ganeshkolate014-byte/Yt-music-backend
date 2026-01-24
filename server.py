from fastapi import FastAPI, Form
from fastapi.responses import StreamingResponse
import subprocess

app = FastAPI()

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

    # yt-dlp stdout pipe
    cmd = [
        "yt-dlp",
        "-f", fmt,
        "-o", "-",   # "-" means stdout
        url
    ]
    
    # subprocess stdout streaming
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # StreamingResponse to frontend
    return StreamingResponse(process.stdout, media_type="video/mp4", headers={
        "Content-Disposition": "attachment; filename=video.mp4"
    })
