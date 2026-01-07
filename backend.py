import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import yt_dlp
from functools import lru_cache

# --- CONFIGURATION ---
app = FastAPI(title="Simple Music API", description="Search (Pages), Stream & Recommend")
yt = YTMusic(location="IN") 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- UNLIMITED DOWNLOAD SETTINGS ---
ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'extract_flat': True,
    'skip_download': True,
    'geo_bypass': True,
    'cookiefile': 'cookies.txt', # Cookies file zaroori hai
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

# --- CACHING (Important for Pagination) ---
# Hum ek baar me 100 gaane fetch karke cache me rakhenge
# Taaki jab tu Page 2 maange, to wapas YouTube ke paas na jana pade (Fast Speed)
@lru_cache(maxsize=50)
def get_cached_results(query: str):
    return yt.search(query, filter="songs", limit=100)

# --- 1. ROOT DOCS ---
@app.get("/")
def root(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "status": "Online 🚀",
        "endpoints": {
            "1. Search (Page 1)": f"{base_url}/search/Arijit/1",
            "2. Search (Page 2)": f"{base_url}/search/Arijit/2",
            "3. Play Song": f"{base_url}/play/VIDEO_ID",
            "4. Recommendations": f"{base_url}/recommend/VIDEO_ID"
        }
    }

# --- 2. SEARCH WITH PAGINATION ---
@app.get("/search/{query}/{page}")
def search_with_pages(query: str, page: int):
    try:
        # Ek baar me 100 results laate hain
        all_results = get_cached_results(query)
        
        # Pagination Logic (20 songs per page)
        items_per_page = 20
        start = (page - 1) * items_per_page
        end = start + items_per_page
        
        # Slice the results based on page number
        page_results = all_results[start:end]
        
        if not page_results:
            return {"message": "No more results found on this page."}

        return [clean_data(res) for res in page_results]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. PLAY / STREAM ---
@app.get("/play/{video_id}")
def get_stream(video_id: str):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "id": video_id,
                "stream_url": info.get("url"),
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration")
            }
    except Exception:
        raise HTTPException(status_code=500, detail="Audio Stream Failed")

# --- 4. RECOMMENDATIONS ---
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
