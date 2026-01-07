import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import yt_dlp
from functools import lru_cache

# --- CONFIGURATION ---
app = FastAPI(title="Fast Music API", description="Cached Stream & Search (Optimized)")
yt = YTMusic(location="IN") 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. SETTINGS FOR SEARCH (Not used by yt-dlp here, but kept for ref) ---
search_opts = {
    'quiet': True,
    'noplaylist': True,
    'extract_flat': True,
    'skip_download': True,
    'geo_bypass': True,
    'cookiefile': 'cookies.txt', 
}

# --- 2. SETTINGS FOR PLAY (THE FIX IS HERE) ---
play_opts = {
    'format': 'bestaudio[ext=m4a]/bestaudio/best', # M4A is faster
    'quiet': True,
    'noplaylist': True,
    'extract_flat': False, # Must be False for streaming
    'skip_download': True,
    'geo_bypass': True,
    'cookiefile': 'cookies.txt', # Cookies zaroori hain
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    
    # --- MAGIC FIX FOR WARNINGS & SPEED ---
    # Ye Android client use karega jo "SABR" error bypass karta hai
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
        },
    },
}

# --- HELPER FUNCTION ---
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

# --- CACHING LOGIC ---

# Search Cache (Fastest way using ytmusicapi)
@lru_cache(maxsize=50)
def get_cached_search(query: str):
    return yt.search(query, filter="songs", limit=100)

# Play Link Cache (With Fix applied via play_opts)
@lru_cache(maxsize=100)
def get_cached_stream_url(video_id: str):
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(play_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "id": video_id,
            "stream_url": info.get("url"),
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration")
        }

# --- ENDPOINTS ---

@app.get("/")
def root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "Online (Optimized Mode) ⚡",
        "endpoints": {
            "1. Search": f"{base_url}/search/Diljit/1",
            "2. Play (Cached)": f"{base_url}/play/VIDEO_ID",
            "3. Recommend": f"{base_url}/recommend/VIDEO_ID"
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
            return {"message": "No more results found."}

        return [clean_data(res) for res in page_results]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/play/{video_id}")
def get_stream(video_id: str):
    try:
        # Try from Cache first
        return get_cached_stream_url(video_id)
    except Exception:
        # Agar error aaye (link expire etc), toh cache clear karke retry karo
        print("Stream Error or Expired Link. Retrying...")
        get_cached_stream_url.cache_clear()
        try:
            return get_cached_stream_url(video_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Stream failed after retry.")

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
