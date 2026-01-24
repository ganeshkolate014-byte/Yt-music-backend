import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ytmusicapi import YTMusic
import yt_dlp
import requests

# --- SETUP ---
app = FastAPI()
yt = YTMusic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SIMPLE YT-DLP CONFIG WITH COOKIES ---
ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'cookiefile': 'cookies.txt',  # <--- Aapki cookies file ka path
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def clean_song(data):
    """Data ko simplify karne ke liye helper function"""
    return {
        "id": data.get("videoId"),
        "title": data.get("title"),
        "artist": data.get("artists")[0]["name"] if data.get("artists") else "Unknown",
        "thumbnail": data.get("thumbnails")[-1]["url"] if data.get("thumbnails") else None,
    }

# --- ENDPOINTS ---

@app.get("/search")
def search(q: str):
    """Gaane dhundne ke liye"""
    try:
        results = yt.search(q, filter="songs")
        return [clean_song(s) for s in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")

@app.get("/stream/{video_id}")
def stream_audio(video_id: str):
    """Direct audio stream karne ke liye"""
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info['url']
            
        def iter_stream():
            # Headers taaki connection drop na ho
            headers = {'User-Agent': ydl_opts['user_agent']}
            resp = requests.get(audio_url, stream=True, headers=headers)
            for chunk in resp.iter_content(chunk_size=1024*64): # 64KB chunks for stability
                yield chunk

        return StreamingResponse(iter_stream(), media_type="audio/mpeg")
    
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Stream generation failed")

@app.get("/recommend/{video_id}")
def recommend(video_id: str):
    """Suggested gaane dikhane ke liye"""
    try:
        playlist = yt.get_watch_playlist(video_id)
        return [clean_song(t) for t in playlist.get("tracks", []) if "videoId" in t]
    except:
        return []

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
