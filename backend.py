
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ytmusicapi import YTMusic
import yt_dlp
import requests
import random
from functools import lru_cache

# --- CONFIGURATION ---
app = FastAPI(title="Ultra Stable Music API", description="Multi-Server Fallback System")
yt = YTMusic(location="IN") 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- NEW YT-DLP SETTINGS (iOS Client) ---
ydl_opts = {
    'format': 'bestaudio', 
    'quiet': True,
    'noplaylist': True,
    'cookiefile': 'cookies.txt',
    # iOS client audio ke liye best hai server par
    'extractor_args': {
        'youtube': {
            'player_client': ['ios', 'web'],
        },
    },
    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
}

# --- MULTI-SERVER PIPED API LIST ---
# Agar ek server band hua, toh agla use hoga
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.streampunk.xyz",
    "https://pipedapi.drgns.space",
    "https://api.piped.projectsegfau.lt",
    "https://pipedapi.leptons.xyz"
]

def clean_data(data):
    thumbnails = data.get("thumbnails", [])
    artists = data.get("artists", [])
    artist_name = "Unknown"
    if isinstance(artists, list) and len(artists) > 0:
        artist_name = artists[0].get("name", "Unknown")
    elif isinstance(artists, dict):
        artist_name = artists.get("name", "Unknown")
    return {
        "id": data.get("videoId"),
        "title": data.get("title"),
        "subtitle": artist_name,
        "image": thumbnails[-1]["url"] if thumbnails else None,
        "duration": data.get("duration")
    }

@lru_cache(maxsize=50)
def get_cached_search(query: str):
    return yt.search(query, filter="songs", limit=100)

@app.get("/")
def root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "Online (Multi-Server Mode) 🛡️",
        "endpoints": {"search": f"{base_url}/search/Arijit/1", "play": f"{base_url}/play/VIDEO_ID"}
    }

@app.get("/search/{query}/{page}")
def search_with_pages(query: str, page: int):
    try:
        all_results = get_cached_search(query)
        start = (page - 1) * 20
        page_results = all_results[start : start + 20]
        if not page_results: return {"message": "No more results."}
        return [clean_data(res) for res in page_results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/play/{video_id}")
def get_play_data(video_id: str, request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "id": video_id,
        "stream_url": f"{base_url}/stream/{video_id}", 
        "title": "Audio Stream",
        "thumbnail": None
    }

@app.get("/stream/{video_id}")
def stream_audio(video_id: str):
    print(f"Attempting to stream: {video_id}")
    direct_url = None
    
    # 1. TRY ALL PIPED SERVERS (Fastest)
    for api_base in PIPED_INSTANCES:
        try:
            print(f"Trying Piped Server: {api_base}")
            resp = requests.get(f"{api_base}/streams/{video_id}", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                # Sirf MP4/M4A Audio dhundo
                for stream in data.get("audioStreams", []):
                    if stream.get("mimeType") == "audio/mp4":
                        direct_url = stream["url"]
                        break
                if direct_url:
                    print("Found URL via Piped!")
                    break
        except:
            continue
    
    # 2. FALLBACK TO YT-DLP (If Piped fails)
    if not direct_url:
        print("Piped failed. Switching to yt-dlp (iOS Mode)...")
        try:
            full_url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(full_url, download=False)
                direct_url = info.get("url")
        except Exception as e:
            print(f"yt-dlp error: {e}")

    if not direct_url:
        print("All methods failed.")
        raise HTTPException(status_code=404, detail="Audio not found")

    # 3. STREAM PROXY
    def iterfile():
        try:
            # Headers zaroori hain taki YouTube request reject na kare
            headers = {'User-Agent': 'Mozilla/5.0'}
            with requests.get(direct_url, stream=True, headers=headers, timeout=10) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    yield chunk
        except Exception as e:
            print(f"Stream interrupted: {e}")

    return StreamingResponse(iterfile(), media_type="audio/mp4")

@app.get("/recommend/{video_id}")
def get_recommendations(video_id: str):
    try:
        watch_playlist = yt.get_watch_playlist(video_id)
        return [clean_data(t) for t in watch_playlist.get("tracks", []) if "videoId" in t]
    except: return []

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
