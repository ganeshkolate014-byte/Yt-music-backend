import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ytmusicapi import YTMusic
import yt_dlp
import requests

# 1. Setup
app = FastAPI()
yt = YTMusic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# yt-dlp configuration (Simple version)
ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# 2. Helper to clean song data
def clean_song(data):
    return {
        "id": data.get("videoId"),
        "title": data.get("title"),
        "artist": data.get("artists")[0]["name"] if data.get("artists") else "Unknown",
        "thumbnail": data.get("thumbnails")[-1]["url"] if data.get("thumbnails") else None,
        "duration": data.get("duration")
    }

# 3. Search Endpoint
@app.get("/search")
def search(q: str):
    results = yt.search(q, filter="songs")
    return [clean_song(s) for s in results]

# 4. Stream Logic (Direct)
@app.get("/stream/{video_id}")
def stream_audio(video_id: str):
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info['url']
            
        def iter_stream():
            resp = requests.get(audio_url, stream=True)
            for chunk in resp.iter_content(chunk_size=1024*16):
                yield chunk

        return StreamingResponse(iter_stream(), media_type="audio/mpeg")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 5. Get Recommendations
@app.get("/recommend/{video_id}")
def recommend(video_id: str):
    playlist = yt.get_watch_playlist(video_id)
    return [clean_song(t) for t in playlist.get("tracks", []) if "videoId" in t]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
