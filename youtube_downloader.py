import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import re
import os
import json
import threading
from queue import Queue
import yt_dlp

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Downloader - \GOD MODE/ Edition")
        self.root.geometry("600x500")
        self.queue = Queue()

        # URL input
        tk.Label(root, text="YouTube URL (Video or Playlist):").pack(pady=5)
        self.url_entry = tk.Entry(root, width=60)
        self.url_entry.pack(pady=5)

        # Format selection
        tk.Label(root, text="Select Format:").pack(pady=5)
        self.format_combo = ttk.Combobox(root, state="readonly", width=30)
        self.format_combo.pack(pady=5)

        # Buttons
        self.fetch_button = tk.Button(root, text="Fetch Formats", command=self.fetch_formats)
        self.fetch_button.pack(pady=5)
        self.download_button = tk.Button(root, text="Download", command=self.start_download, state="disabled")
        self.download_button.pack(pady=5)

        # Progress bar
        self.progress = ttk.Progressbar(root, length=400, mode="determinate")
        self.progress.pack(pady=10)

        # Status area
        self.status_text = scrolledtext.ScrolledText(root, height=10, width=60, wrap=tk.WORD)
        self.status_text.pack(pady=10)
        self.status_text.config(state="disabled")

        # Output path
        self.output_path = os.path.join(os.getcwd(), "downloads")
        os.makedirs(self.output_path, exist_ok=True)

    def log(self, message):
        """Log messages to status area."""
        self.status_text.config(state="normal")
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state="disabled")
        self.root.update()

    def validate_youtube_url(self, url):
        """Check if the URL is a valid YouTube link."""
        youtube_regex = (
            r'(https?://)?(www\.)?'
            r'(youtube\.com|youtu\.be)/'
            r'(watch\?v=|embed/|v/|.+\?v=|playlist\?list=)?([^&=%\?]{11,})'
        )
        return re.match(youtube_regex, url) is not None

    def fetch_formats(self):
        """Fetch available formats for the video or playlist."""
        url = self.url_entry.get().strip()
        if not self.validate_youtube_url(url):
            self.log("That's not a valid YouTube URL, dumbass.")
            return

        self.fetch_button.config(state="disabled")
        self.download_button.config(state="disabled")
        self.format_combo["values"] = []
        self.log("Fetching formats, hold tight...")

        threading.Thread(target=self._fetch_formats_thread, args=(url,), daemon=True).start()

    def _fetch_formats_thread(self, url):
        """Run format fetching in a separate thread."""
        try:
            # Check if it's a playlist
            ydl_opts = {"quiet": True, "extract_flat": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if "entries" in info:
                    self.log(f"Playlist detected: {info.get('title', 'Unknown Playlist')}")
                    video_urls = [entry["url"] for entry in info["entries"]]
                else:
                    video_urls = [url]

            # Fetch formats for the first video (for simplicity)
            cmd = ["yt-dlp", "--list-formats", video_urls[0]]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.log(f"Error fetching formats: {result.stderr}")
                return

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
            self.queue.put(formats)

        except Exception as e:
            self.queue.put(f"Shit hit the fan while fetching formats: {e}")

        self.root.after(100, self._process_queue)

    def _process_queue(self):
        """Process results from the queue."""
        try:
            result = self.queue.get_nowait()
            if isinstance(result, str):
                self.log(result)
            else:
                self.format_combo["values"] = [f["resolution"] for f in result]
                self.formats = result
                if result:
                    self.format_combo.current(0)
                    self.download_button.config(state="normal")
                self.log("Formats fetched. Pick one and hit Download.")
        except:
            pass
        finally:
            self.fetch_button.config(state="normal")

    def start_download(self):
        """Start downloading the selected format."""
        url = self.url_entry.get().strip()
        if not self.validate_youtube_url(url):
            self.log("That's not a valid YouTube URL, dumbass.")
            return

        selected_format = self.formats[self.format_combo.current()]
        self.download_button.config(state="disabled")
        self.fetch_button.config(state="disabled")
        self.progress["value"] = 0
        self.log(f"Starting download for {selected_format['resolution']}...")

        threading.Thread(target=self._download_thread, args=(url, selected_format), daemon=True).start()

    def _download_thread(self, url, selected_format):
        """Run download in a separate thread."""
        try:
            # Check if it's a playlist
            ydl_opts = {"quiet": True, "extract_flat": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if "entries" in info:
                    video_urls = [entry["url"] for entry in info["entries"]]
                    self.log(f"Downloading playlist: {info.get('title', 'Unknown Playlist')}")
                else:
                    video_urls = [url]

            # Download each video
            for i, video_url in enumerate(video_urls, 1):
                self.log(f"Processing video {i}/{len(video_urls)}...")
                self._download_single_video(video_url, selected_format, i, len(video_urls))

            self.queue.put("All downloads complete!")

        except Exception as e:
            self.queue.put(f"Shit hit the fan: {e}")

        self.root.after(100, self._process_queue_download)

    def _download_single_video(self, url, selected_format, video_num, total_videos):
        """Download a single video with progress."""
        ydl_opts = {
            "outtmpl": os.path.join(self.output_path, f"%(title)s_{selected_format['resolution']}.%(ext)s"),
            "progress_hooks": [self._progress_hook],
            "quiet": True,
            "merge_output_format": "mp4" if selected_format["id"] != "bestaudio" else None,
        }
        if selected_format["id"] == "bestaudio":
            ydl_opts["format"] = "bestaudio"
            ydl_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
        else:
            ydl_opts["format"] = f"{selected_format['id']}+bestaudio[ext=m4a]/best[ext=mp4]"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            output_file = ydl.prepare_filename(info).replace(".webm", ".mp4").replace(".m4a", ".mp3")
            self.queue.put(f"Video {video_num}/{total_videos} done: {output_file}")

    def _progress_hook(self, d):
        """Update progress bar."""
        if d["status"] == "downloading":
            percent = d.get("downloaded_bytes", 0) / d.get("total_bytes", 1) * 100
            self.progress["value"] = percent
            self.root.update()
        elif d["status"] == "finished":
            self.progress["value"] = 100

    def _process_queue_download(self):
        """Process download queue."""
        try:
            message = self.queue.get_nowait()
            self.log(message)
            if "All downloads complete" in message:
                self.download_button.config(state="normal")
                self.fetch_button.config(state="normal")
        except:
            pass
        self.root.after(100, self._process_queue_download)

if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()