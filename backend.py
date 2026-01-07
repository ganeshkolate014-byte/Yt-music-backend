import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import yt_dlp
from functools import lru_cache

# --- CONFIGURATION ---
app = FastAPI(title="Advanced Music Backend", description="Spotify Clone with Charts, Albums & Caching")
yt = YTMusic() # Default locale is usually US, can be set to 'IN' if needed.

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Advanced yt-dlp configuration
ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'extract_flat': True,
    'skip_download': True,
    'geo_bypass': True,
}

# --- HELPER FUNCTIONS ---
def clean_data(data, data_type="song"):
    """
    Ek universal cleaner jo Song, Album, aur Playlist ka data standardize karta hai.
    """
    thumbnails = data.get("thumbnails", [])
    artists = data.get("artists", [])
    
    # Handle different artist structures
    artist_name = "Unknown"
    if isinstance(artists, list) and len(artists) > 0:
        artist_name = artists[0].get("name", "Unknown")
    elif isinstance(artists, dict):
        artist_name = artists.get("name", "Unknown")

    item = {
        "id": data.get("videoId") or data.get("browseId"),
        "title": data.get("title"),
        "subtitle": artist_name, # Artist name or description
        "image": thumbnails[-1]["url"] if thumbnails else None,
        "type": data_type
    }
    
    # Extra data based on type
    if data_type == "song":
        item["album"] = data.get("album", {}).get("name") if data.get("album") else None
        item["duration"] = data.get("duration")
    
    return item

# --- CACHING (Performance Booster) ---
# Ye function recent searches ko memory me save karega taaki speed tez ho
@lru_cache(maxsize=100)
def cached_search(query: str, filter_type: str):
    return yt.search(query, filter=filter_type)

# --- API ENDPOINTS ---

@app.get("/")
def root():
    return {"status": "Online", "features": ["Charts", "Search", "Stream", "Albums", "Playlists"]}

# 1. HOME / CHARTS (New!)
@app.get("/home")
def get_home_data():
    """Returns Top Charts. If Charts fail, returns Trending Search results."""
    try:
        # Koshish karo Charts lane ki India ke liye
        charts = yt.get_charts(country="IN")
        
        trending = {
            "top_songs": [clean_data(s, "song") for s in charts.get("songs", {}).get("items", [])[:10]],
            "top_videos": [clean_data(v, "video") for v in charts.get("videos", {}).get("items", [])[:10]],
            "trending_albums": [clean_data(a, "album") for a in charts.get("trending", {}).get("items", [])[:10]]
        }
        return trending

    except Exception:
        # Agar Charts fail ho jaye (Error aaye), toh hum 'Trending' search karke bhej denge
        # Taaki App khali na dikhe (Fallback)
        print("Charts failed, switching to Search Fallback...")
        fallback_songs = yt.search("Top Trending Songs India", filter="songs")
        fallback_albums = yt.search("Top Hit Albums India", filter="albums")
        
        return {
            "top_songs": [clean_data(s, "song") for s in fallback_songs[:10]],
            "top_videos": [], # Video search avoid karte hain speed ke liye
            "trending_albums": [clean_data(a, "album") for a in fallback_albums[:10]]
        }

# 2. ADVANCED SEARCH
@app.get("/search")
def search(query: str, type: str = Query("songs", enum=["songs", "albums", "playlists", "videos"])):
    """
    Search for Songs, Albums, or Playlists.
    Usage: /search?query=Arijit&type=albums
    """
    try:
        # Using cached search for speed
        results = cached_search(query, type)
        
        # Clean results based on type
        cleaned_results = []
        for res in results:
            # Result type determine karna
            dtype = "song"
            if "album" in res.get("resultType", "") or type == "albums": dtype = "album"
            elif "playlist" in res.get("resultType", "") or type == "playlists": dtype = "playlist"
            
            cleaned_results.append(clean_data(res, dtype))
            
        return cleaned_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. STREAM (Audio URL)
@app.get("/play/{video_id}")
def get_stream(video_id: str):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "stream_url": info.get("url"),
                "title": info.get("title"),
                "duration_seconds": info.get("duration"),
                "thumbnail": info.get("thumbnail")
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Stream not found")

# 4. ALBUM DETAILS (New!)
@app.get("/album/{browse_id}")
def get_album(browse_id: str):
    """Get all songs from an Album."""
    try:
        album = yt.get_album(browse_id)
        return {
            "title": album.get("title"),
            "artist": album.get("artists", [{}])[0].get("name"),
            "image": album.get("thumbnails", [{}])[-1].get("url"),
            "tracks": [clean_data(t, "song") for t in album.get("tracks", [])]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Album not found")

# 5. PLAYLIST DETAILS (New!)
@app.get("/playlist/{playlist_id}")
def get_playlist(playlist_id: str):
    """Get all songs from a Playlist."""
    try:
        playlist = yt.get_playlist(playlist_id)
        return {
            "title": playlist.get("title"),
            "author": playlist.get("author", {}).get("name"),
            "image": playlist.get("thumbnails", [{}])[-1].get("url"),
            "tracks": [clean_data(t, "song") for t in playlist.get("tracks", []) if t.get("videoId")]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Playlist not found")

# 6. ARTIST DETAILS
@app.get("/artist/{channel_id}")
def get_artist_details(channel_id: str):
    try:
        artist = yt.get_artist(channel_id)
        return {
            "name": artist["name"],
            "description": artist.get("description"),
            "image": artist.get("thumbnails", [{}])[-1].get("url"),
            "top_songs": [clean_data(s, "song") for s in artist.get("songs", {}).get("results", [])]
        }
    except Exception:
        raise HTTPException(status_code=404, detail="Artist not found")

# 7. RECOMMENDATIONS
@app.get("/recommend/{video_id}")
def get_recommendations(video_id: str):
    try:
        watch_playlist = yt.get_watch_playlist(video_id)
        tracks = watch_playlist.get("tracks", [])
        return [clean_data(t, "song") for t in tracks[1:] if "videoId" in t]
    except Exception:
        return []

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
