import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from ytmusicapi import YTMusic
import yt_dlp
from functools import lru_cache

# --- CONFIGURATION ---
app = FastAPI(title="Music Backend", description="Spotify Clone API")
yt = YTMusic(location="IN") 

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# yt-dlp configuration
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

# --- ROOT ENDPOINT WITH AI INSTRUCTIONS ---
@app.get("/")
def root():
    """
    Returns instructions for AI on how to integrate this API.
    """
    base_url = "https://yt-music-backend-qww6.onrender.com"
    
    return {
        "status": "Online",
        "message": "Use the prompts below to integrate this API into your app.",
        "integration_guide": {
            "base_url": base_url,
            "endpoints": {
                "search": f"{base_url}/search?query=SONG_NAME&type=songs|albums|playlists",
                "play": f"{base_url}/play/VIDEO_ID",
                "album": f"{base_url}/album/BROWSE_ID",
                "playlist": f"{base_url}/playlist/PLAYLIST_ID",
                "artist": f"{base_url}/artist/CHANNEL_ID",
                "recommend": f"{base_url}/recommend/VIDEO_ID"
            }
        },
        "prompt_for_ai": f"I have a music backend API running at {base_url}. It returns JSON data. Please build a frontend that uses the '/search' endpoint to find music, lists the results, and when a user clicks a song, use the '/play' endpoint to get the 'stream_url' and play it in an audio player. Also handle Album and Playlist views using their respective endpoints."
    }

# --- API ENDPOINTS ---

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
