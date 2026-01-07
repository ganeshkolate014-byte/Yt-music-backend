import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import yt_dlp
from functools import lru_cache

# --- CONFIGURATION ---
app = FastAPI(title="Advanced Music Backend", description="Spotify Clone with Charts, Albums & Caching")
yt = YTMusic(location="IN") # Location IN set kiya taki charts India ke aayein

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
    thumbnails = data.get("thumbnails", [])
    artists = data.get("artists", [])
    
    artist_name = "Unknown"
    if isinstance(artists, list) and len(artists) > 0:
        artist_name = artists[0].get("name", "Unknown")
    elif isinstance(artists, dict):
        artist_name = artists.get("name", "Unknown")

    item = {
        "id": data.get("videoId") or data.get("browseId"),
        "title": data.get("title"),
        "subtitle": artist_name,
        "image": thumbnails[-1]["url"] if thumbnails else None,
        "type": data_type
    }
    
    if data_type == "song":
        item["album"] = data.get("album", {}).get("name") if data.get("album") else None
        item["duration"] = data.get("duration")
    
    return item

@lru_cache(maxsize=100)
def cached_search(query: str, filter_type: str):
    return yt.search(query, filter=filter_type)

# --- UPDATED ROOT ENDPOINT ---
@app.get("/")
def root():
    """
    Documentation Endpoint showing all available API routes with examples.
    """
    base_url = "https://yt-music-backend-qww6.onrender.com"
    
    return {
        "app_status": "Online 🟢",
        "documentation": "API Endpoints & Examples",
        "endpoints": {
            "1_home": {
                "description": "Get Top Charts & Trending Albums (India)",
                "method": "GET",
                "example_url": f"{base_url}/home",
                "response_format": "{ top_songs: [], top_videos: [], trending_albums: [] }"
            },
            "2_search": {
                "description": "Search for Songs, Albums, Playlists or Videos",
                "method": "GET",
                "params": ["query", "type (optional: songs, albums, playlists)"],
                "example_url": f"{base_url}/search?query=Arijit+Singh&type=songs",
                "response_format": "[ { id, title, subtitle, image, type } ]"
            },
            "3_play": {
                "description": "Get Stream URL (Direct Audio Link)",
                "method": "GET",
                "params": ["video_id"],
                "example_url": f"{base_url}/play/5Eqb_-j3FDA",
                "response_format": "{ stream_url, title, duration_seconds, thumbnail }"
            },
            "4_album_details": {
                "description": "Get all songs inside an Album",
                "method": "GET",
                "params": ["browse_id"],
                "example_url": f"{base_url}/album/MPREb_Bqt41502", 
                "response_format": "{ title, artist, tracks: [] }"
            },
            "5_playlist_details": {
                "description": "Get all songs inside a Playlist",
                "method": "GET",
                "params": ["playlist_id"],
                "example_url": f"{base_url}/playlist/RDCLAK5uy_kmPRjHDECIcuVwnKsx2Ng7FYHOaJ1alYo",
                "response_format": "{ title, author, tracks: [] }"
            },
            "6_artist_details": {
                "description": "Get Artist Profile & Top Songs",
                "method": "GET",
                "params": ["channel_id"],
                "example_url": f"{base_url}/artist/UC49VRoQIczpJLPGjwlhQJ-g",
                "response_format": "{ name, description, top_songs: [] }"
            },
            "7_recommendations": {
                "description": "Get 'Up Next' songs based on a video ID",
                "method": "GET",
                "params": ["video_id"],
                "example_url": f"{base_url}/recommend/5Eqb_-j3FDA",
                "response_format": "[ { id, title, subtitle... } ]"
            }
        }
    }

# --- OTHER ENDPOINTS ---

@app.get("/home")
def get_home_data():
    try:
        charts = yt.get_charts(country="IN")
        trending = {
            "top_songs": [clean_data(s, "song") for s in charts.get("songs", {}).get("items", [])[:10]],
            "top_videos": [clean_data(v, "video") for v in charts.get("videos", {}).get("items", [])[:10]],
            "trending_albums": [clean_data(a, "album") for a in charts.get("trending", {}).get("items", [])[:10]]
        }
        return trending
    except Exception:
        fallback_songs = yt.search("Top Trending Songs India", filter="songs")
        fallback_albums = yt.search("Top Hit Albums India", filter="albums")
        return {
            "top_songs": [clean_data(s, "song") for s in fallback_songs[:10]],
            "top_videos": [],
            "trending_albums": [clean_data(a, "album") for a in fallback_albums[:10]]
        }

@app.get("/search")
def search(query: str, type: str = Query("songs", enum=["songs", "albums", "playlists", "videos"])):
    try:
        results = cached_search(query, type)
        cleaned_results = []
        for res in results:
            dtype = "song"
            if "album" in res.get("resultType", "") or type == "albums": dtype = "album"
            elif "playlist" in res.get("resultType", "") or type == "playlists": dtype = "playlist"
            cleaned_results.append(clean_data(res, dtype))
        return cleaned_results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@app.get("/album/{browse_id}")
def get_album(browse_id: str):
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

@app.get("/playlist/{playlist_id}")
def get_playlist(playlist_id: str):
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
    
