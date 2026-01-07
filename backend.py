import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import yt_dlp
from functools import lru_cache

# --- CONFIGURATION ---
app = FastAPI(title="Easy Music API", description="Search, Stream & Recommendations")
yt = YTMusic(location="IN") 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'extract_flat': True,
    'skip_download': True,
    'geo_bypass': True,
}

# --- HELPER FUNCTION ---
def clean_data(data, data_type="song"):
    thumbnails = data.get("thumbnails", [])
    artists = data.get("artists", [])
    
    artist_name = "Unknown"
    if isinstance(artists, list) and len(artists) > 0:
        artist_name = artists[0].get("name", "Unknown")
    elif isinstance(artists, dict):
        artist_name = artists.get("name", "Unknown")

    # ID extraction logic
    final_id = data.get("videoId") or data.get("browseId")

    return {
        "id": final_id,  # Sabse upar ID dikhegi
        "title": data.get("title"),
        "subtitle": artist_name,
        "image": thumbnails[-1]["url"] if thumbnails else None,
        "type": data_type,
        "duration": data.get("duration") if data_type == "song" else None
    }

@lru_cache(maxsize=50)
def cached_search(query: str, filter_type: str):
    return yt.search(query, filter=filter_type)

# --- 1. SMART ROOT DOCS ---
@app.get("/")
def root(request: Request):
    """
    Automatic Documentation with EASY URLs.
    """
    base_url = str(request.base_url).rstrip("/")
    
    return {
        "status": "Online 🚀",
        "endpoints": {
            "1. Search Song": f"{base_url}/search/Kesariya",
            "2. Search Album": f"{base_url}/search/albums/Animal",
            "3. Search Playlist": f"{base_url}/search/playlists/GlobalHits",
            "4. Get Recommendations (Up Next)": f"{base_url}/recommend/VIDEO_ID",
            "5. Play Song": f"{base_url}/play/VIDEO_ID",
        }
    }

# --- 2. EASY SEARCH ENDPOINTS ---

# Case A: Sirf naam likha to 'Song' samjhega
# Example: /search/Tum Hi Ho
@app.get("/search/{name}")
def search_song_only(name: str):
    try:
        results = cached_search(name, "songs")
        return [clean_data(res, "song") for res in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Case B: Type bhi batana hai (albums/playlists)
# Example: /search/albums/Rockstar
@app.get("/search/{type}/{name}")
def search_with_type(type: str, name: str):
    try:
        valid_types = ["songs", "albums", "playlists", "videos"]
        if type not in valid_types:
            return {"error": f"Invalid type. Use: {valid_types}"}

        results = cached_search(name, type)
        
        clean_list = []
        for res in results:
            dtype = "song"
            if "album" in res.get("resultType", "") or type == "albums": dtype = "album"
            elif "playlist" in res.get("resultType", "") or type == "playlists": dtype = "playlist"
            
            clean_list.append(clean_data(res, dtype))
            
        return clean_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- 3. RECOMMENDATIONS (NEW) ---
# Example: /recommend/5Eqb_-j3FDA
@app.get("/recommend/{video_id}")
def get_recommendations(video_id: str):
    try:
        # Watch playlist se "Up Next" songs nikalna
        watch_playlist = yt.get_watch_playlist(video_id)
        tracks = watch_playlist.get("tracks", [])
        
        # Pehla track usually same song hota hai, usko hata sakte hain ya rakh sakte hain
        # Yahan main saare bhej raha hu
        return [clean_data(t, "song") for t in tracks if "videoId" in t]
    except Exception:
        return []

# --- 4. OTHER ENDPOINTS ---

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

@app.get("/album/{browse_id}")
def get_album(browse_id: str):
    try:
        album = yt.get_album(browse_id)
        return {
            "id": browse_id,
            "title": album.get("title"),
            "artist": album.get("artists", [{}])[0].get("name"),
            "image": album.get("thumbnails", [{}])[-1].get("url"),
            "tracks": [clean_data(t, "song") for t in album.get("tracks", [])]
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Album Not Found")

@app.get("/playlist/{playlist_id}")
def get_playlist(playlist_id: str):
    try:
        pl = yt.get_playlist(playlist_id)
        return {
            "id": playlist_id,
            "title": pl.get("title"),
            "author": pl.get("author", {}).get("name"),
            "image": pl.get("thumbnails", [{}])[-1].get("url"),
            "tracks": [clean_data(t, "song") for t in pl.get("tracks", []) if t.get("videoId")]
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Playlist Not Found")

@app.get("/artist/{channel_id}")
def get_artist(channel_id: str):
    try:
        artist = yt.get_artist(channel_id)
        return {
            "id": channel_id,
            "name": artist["name"],
            "image": artist.get("thumbnails", [{}])[-1].get("url"),
            "top_songs": [clean_data(s, "song") for s in artist.get("songs", {}).get("results", [])]
        }
    except Exception:
        raise HTTPException(status_code=404, detail="Artist Not Found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
