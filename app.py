from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import re
import subprocess
from pathlib import Path

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for front-end requests

# Output path for downloads
output_path = os.path.join(os.getcwd(), "downloads")
os.makedirs(output_path, exist_ok=True)

def validate_youtube_url(url):
    """Check if the URL is a valid YouTube link."""
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube\.com|youtu\.be)/'
        r'(watch\?v=|embed/|v/|.+\?v=|playlist\?list=)?([^&=%\?]{11,})'
    )
    return re.match(youtube_regex, url) is not None

@app.route('/')
def serve_index():
    """Serve the front-end HTML."""
    return send_file('index.html')

@app.route('/favicon.ico')
def serve_favicon():
    """Serve the favicon."""
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/api/formats', methods=['POST'])
def fetch_formats():
    """Fetch available formats for a YouTube URL."""
    data = request.get_json()
    url = data.get('url')
    
    if not url or not validate_youtube_url(url):
        return jsonify({'error': 'Invalid YouTube URL'}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "http_headers": {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_urls = [entry["url"] for entry in info["entries"]] if "entries" in info else [url]

        cmd = ["yt-dlp", "--list-formats", "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36", video_urls[0]]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return jsonify({'error': f'Error fetching formats: {result.stderr}'}), 500

        formats = []
        audio_only = {"id": "bestaudio", "resolution": "MP3 (Audio Only)"}
        formats.append(audio_only)
        lines = result.stdout.splitlines()
        for line in lines:
            if "mp4" in line and "x" in line and "audio only" not in line:
                parts = line.split()
                format_id = parts[0]
                resolution = next((p for p in parts if "x" in p), None)
                if resolution:
                    formats.append({"id": format_id, "resolution": resolution})

        formats.sort(key=lambda x: int(x["resolution"].split("x")[1]) if "x" in x["resolution"] else 0, reverse=True)
        return jsonify({'formats': formats})

    except Exception as e:
        return jsonify({'error': f'Error fetching formats: {str(e)}'}), 500
        
@app.route('/api/download', methods=['POST'])
def download_video():
    """Download a YouTube video in the selected format."""
    data = request.get_json()
    url = data.get('url')
    format_id = data.get('format_id')
    
    if not url or not validate_youtube_url(url):
        return jsonify({'error': 'Invalid YouTube URL'}), 400
    if not format_id:
        return jsonify({'error': 'No format selected'}), 400

    try:
        ydl_opts = {
            "outtmpl": os.path.join(output_path, "%(title)s_%(resolution)s.%(ext)s"),
            "quiet": True,
            "merge_output_format": "mp4" if format_id != "bestaudio" else None,
        }
        if format_id == "bestaudio":
            ydl_opts["format"] = "bestaudio"
            ydl_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
        else:
            ydl_opts["format"] = f"{format_id}+bestaudio[ext=m4a]/best[ext=mp4]"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            output_file = ydl.prepare_filename(info).replace(".webm", ".mp4").replace(".m4a", ".mp3")
        
        # Return the file path as a downloadable link
        filename = os.path.basename(output_file)
        return jsonify({
            'downloadUrl': f'/downloads/{filename}',
            'filename': filename
        })

    except Exception as e:
        return jsonify({'error': f'Error downloading video: {str(e)}'}), 500

@app.route('/downloads/<filename>')
def serve_file(filename):
    """Serve the downloaded file."""
    file_path = os.path.join(output_path, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
