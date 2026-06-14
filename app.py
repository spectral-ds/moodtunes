# MoodTunes - Flask Web Application


import os
from flask import Flask, render_template, request, jsonify
from mood_engine import (
    get_playlist, get_art_url, get_mood_stats,
    MOOD_EMOJIS, MOOD_COLORS, MOOD_DESC
)

app = Flask(__name__)
MOODS = ["Happy", "Sad", "Energetic", "Calm", "Angry"]


@app.route("/")
def index():
    return render_template("index.html",
        moods=MOODS, mood_emojis=MOOD_EMOJIS,
        mood_colors=MOOD_COLORS, mood_desc=MOOD_DESC,
        stats=get_mood_stats())


@app.route("/playlist/<mood>")
def playlist(mood):
    if mood not in MOODS:
        return render_template("index.html",
            moods=MOODS, mood_emojis=MOOD_EMOJIS,
            mood_colors=MOOD_COLORS, mood_desc=MOOD_DESC,
            stats=get_mood_stats())
    songs = get_playlist(mood, n=20)
    return render_template("playlist.html",
        mood=mood, emoji=MOOD_EMOJIS[mood],
        color=MOOD_COLORS[mood], desc=MOOD_DESC[mood],
        songs=songs, moods=MOODS,
        mood_emojis=MOOD_EMOJIS, mood_colors=MOOD_COLORS)


@app.route("/api/cover")
def api_cover():
    """
    Browser calls this for songs whose art wasn't ready when page loaded.
    Returns cached URL instantly if available, or fetches now.
    """
    track  = request.args.get("track", "").strip()
    artist = request.args.get("artist", "").strip()
    if not track or not artist:
        return jsonify({"url": ""})
    url  = get_art_url(track, artist)
    resp = jsonify({"url": url})
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/health")
def health():
    from mood_engine import df, _art
    return jsonify({"status": "ok", "songs": len(df), "art_cached": len(_art)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
