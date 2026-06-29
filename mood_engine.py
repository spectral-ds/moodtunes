# MoodTunes - Mood Engine


import os
import time
import threading
import requests
import urllib3
import pandas as pd

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE     = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE, "cache", "songs_with_moods.csv")

MOOD_EMOJIS = {
    "Happy":     "😊",
    "Sad":       "😢",
    "Energetic": "⚡",
    "Calm":      "😌",
    "Angry":     "😤",
}
MOOD_COLORS = {
    "Happy":     "#FFD700",
    "Sad":       "#4488FF",
    "Energetic": "#FF4500",
    "Calm":      "#1DB954",
    "Angry":     "#DC143C",
}
MOOD_DESC = {
    "Happy":     "Upbeat and cheerful songs to brighten your day",
    "Sad":       "Mellow and emotional songs for quiet moments",
    "Energetic": "High-energy tracks to get you moving",
    "Calm":      "Soft and acoustic songs to help you relax",
    "Angry":     "Intense and powerful tracks to let it out",
}

#Load data
print("Loading MoodTunes engine...")
df = pd.read_csv(CSV_PATH)
df = df.dropna(subset=["track_name", "artists", "mood"])
df = (df.sort_values("popularity", ascending=False)
        .drop_duplicates(subset=["track_name", "artists"])
        .reset_index(drop=True))
print(f"  Loaded {len(df):,} unique songs")

#In-memory art cache
_art: dict = {}
_lock = threading.Lock()


def _itunes(term: str) -> str:
    try:
        r = requests.get(
            "https://itunes.apple.com/search",
            params={"term": term, "media": "music",
                    "limit": 3, "entity": "song"},
            timeout=8, verify=False,
        )
        if r.status_code == 200:
            for item in r.json().get("results", []):
                url = item.get("artworkUrl100", "")
                if url:
                    return url.replace("100x100bb", "600x600bb")
    except Exception:
        pass
    return ""


def _fetch_art(track: str, artist: str) -> str:
    """Fetch from iTunes with two strategies. Cached in memory."""
    key = f"{track}|{artist}".lower()
    with _lock:
        if key in _art:
            return _art[key]

    clean = artist.split(";")[0].split("feat")[0].strip()
    url   = _itunes(f"{track} {clean}") or _itunes(track)

    with _lock:
        _art[key] = url
    return url


def _warm_cache(songs: list):
    """
    Background thread: fetch art for a list of songs sequentially.
    150ms gap keeps us well under iTunes rate limit.
    """
    for s in songs:
        key = f"{s['track_name']}|{s['artists']}".lower()
        with _lock:
            if key in _art:
                continue
        _fetch_art(s["track_name"], s["artists"])
        time.sleep(0.15)


def get_playlist(mood: str, n: int = 20) -> list:
    """
    Return songs immediately with whatever art is cached.
    Missing art is fetched in the background — browser polls /api/cover.
    """
    if mood not in MOOD_EMOJIS:
        return []

    subset = (
        df[df["mood"] == mood]
        .sort_values("popularity", ascending=False)
        .head(n)
    )

    songs = []
    for _, row in subset.iterrows():
        track  = str(row["track_name"])
        artist = str(row["artists"]).split(";")[0].strip()
        key    = f"{track}|{artist}".lower()

        with _lock:
            art = _art.get(key)  # None = not fetched yet, "" = tried and failed

        songs.append({
            "track_name":   track,
            "artists":      artist,
            "genre":        str(row.get("track_genre", "")),
            "popularity":   int(row["popularity"]),
            "valence":      round(float(row["valence"]), 2),
            "energy":       round(float(row["energy"]), 2),
            "danceability": round(float(row["danceability"]), 2),
            "tempo":        int(float(row["tempo"])),
            "mood":         mood,
            "art_url":      art or "",  # empty if not fetched yet
            "art_pending":  art is None, # True = browser should poll
        })

    # Kick off background fetch for any missing art
    pending = [s for s in songs if s["art_pending"]]
    if pending:
        threading.Thread(
            target=_warm_cache, args=(pending,), daemon=True
        ).start()

    return songs


def get_art_url(track: str, artist: str) -> str:
    """Called by /api/cover — returns cached URL or fetches now."""
    return _fetch_art(track, artist)


def get_mood_stats() -> dict:
    return df["mood"].value_counts().to_dict()


# Pre-warm top songs per mood on startup
def _startup_warm():
    """Fetch art for top 5 songs per mood in background at startup."""
    time.sleep(8)  # wait for Flask to finish starting
    for mood in MOOD_EMOJIS:
        subset = df[df["mood"] == mood].nlargest(20, "popularity")
        for _, row in subset.iterrows():
            track  = str(row["track_name"])
            artist = str(row["artists"]).split(";")[0].strip()
            _fetch_art(track, artist)
            time.sleep(0.3)
    print("Startup art pre-warm done")

threading.Thread(target=_startup_warm, daemon=True).start()
