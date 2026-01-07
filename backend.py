import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse # Streaming ke liye zaroori
from ytmusicapi import YTMusic
import yt_dlp
import requests
from functools import lru_cache

# --- CONFIGURATION ---
app = FastAPI(title="Proxy Music API", description="Fixes NotSupportedError via Server Proxy")
yt = YTMusic(location="IN") 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- YT-DLP SETTINGS ---
ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'cookiefile': 'cookies.txt',
    # Android Client use karenge taaki block na ho
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
        },
    },
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
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

# --- CACHING ---
@lru_cache(maxsize=50)
def get_cached_search(query: str):
    return yt.search(query, filter="songs", limit=100)

# --- 1. ROOT ---
@app.get("/")
def root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "Online (Proxy Mode) 🛡️",
        "msg": "Fixed 'NotSupportedError' by streaming through server.",
        "endpoints": {
            "search": f"{base_url}/search/Diljit/1",
            "play": f"{base_url}/play/VIDEO_ID",
            "stream": f"{base_url}/stream/VIDEO_ID"
        }
    }

# --- 2. SEARCH ---
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

# --- 3. PLAY (METADATA + PROXY LINK) ---
@app.get("/play/{video_id}")
def get_play_data(video_id: str, request: Request):
    """
    Ye endpoint ab Direct Link nahi dega.
    Ye hamare naye '/stream' endpoint ka link dega.
    """
    try:
        base_url = str(request.base_url).rstrip("/")
        
        # Metadata fetch karne ke liye hum ytmusicapi use kar sakte hain ya cache
        # Fast response ke liye bas proxy URL bana ke bhej dete hain
        # Frontend wese bhi /search se title/image le chuka hota hai
        
        return {
            "id": video_id,
            # MAGIC LINK: Ab phone seedha YouTube ke paas nahi, hamare server ke paas aayega
            "stream_url": f"{base_url}/stream/{video_id}", 
            "title": "Playing via Proxy",
            "thumbnail": None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 4. STREAM (THE REAL FIX) ---
@app.get("/stream/{video_id}")
def stream_audio(video_id: str):
    """
    Ye function Server ban kar YouTube se data lega aur Phone ko pass karega.
    """
    try:
        # 1. Asli YouTube Link nikalna (yt-dlp se)
        direct_url = None
        
        # Pehle Piped API try karte hain (Fast)
        try:
            piped_url = f"https://pipedapi.kavin.rocks/streams/{video_id}"
            resp = requests.get(piped_url, timeout=3)
            data = resp.json()
            for stream in data.get("audioStreams", []):
                if stream.get("mimeType") == "audio/mp4":
                    direct_url = stream["url"]
                    break
        except:
            pass
        
        # Agar Piped fail ho, to yt-dlp use karo (Reliable)
        if not direct_url:
            full_url = f"https://www.youtube.com/watch?v={video_id}"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(full_url, download=False)
                direct_url = info.get("url")

        if not direct_url:
            raise HTTPException(status_code=404, detail="Could not extract audio")

        # 2. Audio Data Stream karna (Server -> Phone)
        def iterfile():
            # YouTube se data maango
            with requests.get(direct_url, stream=True) as r:
                for chunk in r.iter_content(chunk_size=1024*64): # 64KB chunks
                    yield chunk

        # 3. Phone ko data bhejo "audio/mp4" header ke saath
        return StreamingResponse(iterfile(), media_type="audio/mp4")

    except Exception as e:
        print(f"Streaming Error: {e}")
        raise HTTPException(status_code=500, detail="Stream failed")

# --- 5. RECOMMEND ---
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
