import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ytmusicapi import YTMusic
import yt_dlp
import requests
from functools import lru_cache

# --- CONFIGURATION ---
app = FastAPI(title="Pure Audio API", description="Strict Audio-Only Streaming")
yt = YTMusic(location="IN") 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- STRICT AUDIO SETTINGS ---
ydl_opts = {
    # CHANGE 1: 'best' hata diya. Ab ye galti se bhi video nahi uthayega.
    'format': 'bestaudio', 
    'quiet': True,
    'noplaylist': True,
    'cookiefile': 'cookies.txt',
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
        },
    },
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
}

# --- HELPER ---
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

# --- ENDPOINTS ---

@app.get("/")
def root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "Online (Audio Only Mode) 🎵",
        "endpoints": {
            "search": f"{base_url}/search/Diljit/1",
            "play": f"{base_url}/play/VIDEO_ID",
            "stream": f"{base_url}/stream/VIDEO_ID"
        }
    }

@app.get("/search/{query}/{page}")
def search_with_pages(query: str, page: int):
    try:
        all_results = get_cached_search(query)
        items_per_page = 20
        start = (page - 1) * items_per_page
        end = start + items_per_page
        
        page_results = all_results[start:end]
        if not page_results:
            return {"message": "No more results."}
        return [clean_data(res) for res in page_results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/play/{video_id}")
def get_play_data(video_id: str, request: Request):
    try:
        base_url = str(request.base_url).rstrip("/")
        return {
            "id": video_id,
            "stream_url": f"{base_url}/stream/{video_id}", 
            "title": "Audio Stream",
            "thumbnail": None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream/{video_id}")
def stream_audio(video_id: str):
    try:
        direct_url = None
        
        # 1. Try Piped API (Strict Audio Only)
        try:
            piped_url = f"https://pipedapi.kavin.rocks/streams/{video_id}"
            resp = requests.get(piped_url, timeout=3)
            data = resp.json()
            
            # Sirf 'audioStreams' check karenge (VideoStreams ko ignore)
            for stream in data.get("audioStreams", []):
                # M4A/MP4 audio prefer karenge
                if stream.get("mimeType") == "audio/mp4":
                    direct_url = stream["url"]
                    break
            
            # Agar MP4 audio na mile, koi bhi audio utha lo
            if not direct_url and data.get("audioStreams"):
                direct_url = data["audioStreams"][0]["url"]
                
        except:
            pass
        
        # 2. Try yt-dlp (Strict Audio Only)
        if not direct_url:
            full_url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(full_url, download=False)
                # Ensure we got a direct url
                direct_url = info.get("url")

        if not direct_url:
            raise HTTPException(status_code=404, detail="Audio not found")

        # 3. Stream Proxy
        def iterfile():
            with requests.get(direct_url, stream=True) as r:
                for chunk in r.iter_content(chunk_size=1024*64):
                    yield chunk

        # Content-Type header 'audio/mp4' set kiya taaki browser video na samjhe
        return StreamingResponse(iterfile(), media_type="audio/mp4")

    except Exception as e:
        print(f"Streaming Error: {e}")
        raise HTTPException(status_code=500, detail="Stream failed")

@app.get("/recommend/{video_id}")
def get_recommendations(video_id: str):
    try:
        watch_playlist = yt.get_watch_playlist(video_id)
        tracks = watch_playlist.get("tracks", [])
        return [clean_data(t) for t in tracks if "videoId" in t]
    except Exception:
        return []

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
