import os
import shutil
import subprocess
import sys
from pathlib import Path
import imageio_ffmpeg
import re
import requests
import yt_dlp

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
FFMPEG_AVAILABLE = True

DOWNLOAD_DIR_NAME = "DWcvideos"

def _get_desktop_path() -> Path:
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if onedrive:
        candidate = Path(onedrive) / "Desktop"
        if candidate.exists():
            return candidate
    return Path.home() / "Desktop"

DOWNLOAD_DIR = _get_desktop_path() / DOWNLOAD_DIR_NAME

QUALITY_OPTIONS = {
    "144p": 144,
    "240p": 240,
    "360p": 360,
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "1440p": 1440,
    "En iyi (sınırsız)": None,
    "Sadece Ses (MP3)": "audio_only",
}
DEFAULT_QUALITY = "1080p"
COOKIES_BROWSER = "brave"

def set_download_dir(new_path):
    global DOWNLOAD_DIR
    DOWNLOAD_DIR = Path(new_path)

def _build_format(height):
    if height is None:
        return "bv*+ba/b"
    return f"bv*[height<={height}]+ba/b[height<={height}]/b"

def _download_tiktok_direct(url, quality, progress_callback=None):
    """TikTok videolarını sesli, filigransız, H.264 formatında ve codec hatasız indirir."""
    api_url = "https://www.tikwm.com/api/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    
    resp = requests.post(api_url, data={"url": url, "count": 12, "cursor": 0, "web": 1, "hd": 1}, headers=headers, timeout=15)
    data = resp.json()
    
    if data.get("code") != 0:
        return False, data.get("msg", "TikTok videosu bulunamadı.")
    
    video_data = data.get("data", {})
    title = video_data.get("title", "tiktok_video")
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:60].strip() or "tiktok_video"
    
    if quality == "audio_only":
        download_url = video_data.get("music")
        ext = "mp3"
    else:
        download_url = video_data.get("hdplay") or video_data.get("play")
        ext = "mp4"

    if not download_url:
        return False, "İndirme bağlantısı alınamadı."

    if download_url.startswith("/"):
        download_url = f"https://www.tikwm.com{download_url}"

    file_path = DOWNLOAD_DIR / f"{safe_title}.{ext}"

    # Eğer sadece ses istenmediyse, videoyu önce geçici dosyaya indirip ffmpeg ile H.264'e çevirelim
    if quality == "audio_only":
        with requests.get(download_url, stream=True, headers=headers, timeout=30) as r:
            r.raise_for_status()
            total_length = int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_length > 0:
                            progress_callback(downloaded / total_length)
    else:
        temp_input = DOWNLOAD_DIR / f"temp_in_{safe_title}.mp4"
        with requests.get(download_url, stream=True, headers=headers, timeout=30) as r:
            r.raise_for_status()
            total_length = int(r.headers.get('content-length', 0))
            downloaded = 0
            with open(temp_input, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_length > 0:
                            progress_callback(downloaded / total_length)

        # FFmpeg ile H.264 (libx264) formatına yeniden kodla (Codec hatasını %100 çözer)
        cmd = [
            FFMPEG_EXE, "-y",
            "-i", str(temp_input),
            "-c:v", "libx264",
            "-crf", "23",
            "-c:a", "aac",
            str(file_path)
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception as e:
            if temp_input.exists():
                temp_input.unlink()
            return False, f"Video dönüştürme hatası: {str(e)}"
        
        if temp_input.exists():
            temp_input.unlink()

    return True, None


def download(url, quality=DEFAULT_QUALITY, progress_callback=None):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    height = QUALITY_OPTIONS.get(quality)
    output_template = str(DOWNLOAD_DIR / "%(title)s.%(ext)s")

    # 1. TİKTOK İÇİN ÖZEL AKIŞ
    if "tiktok.com" in url.lower():
        try:
            return _download_tiktok_direct(url, quality, progress_callback)
        except Exception as e:
            return False, f"TikTok indirme hatası: {str(e)[-150:]}"

    # 2. DİĞER PLATFORMLAR İÇİN YT-DLP AKIŞI
    ydl_opts = {
        'outtmpl': output_template,
        'ffmpeg_location': FFMPEG_EXE,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
    }

    if height == "audio_only":
        ydl_opts['format'] = 'ba/bestaudio'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['format'] = _build_format(height)

    if progress_callback:
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate')
                    if total:
                        progress_callback(d['downloaded_bytes'] / total)
                except Exception:
                    pass
        ydl_opts['progress_hooks'] = [progress_hook]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # yt-dlp'nin oluşturduğu dosya adını alalım
            filename = ydl.prepare_filename(info)
            if height == "audio_only":
                filename = os.path.splitext(filename)[0] + ".mp3"
            elif not filename.endswith(".mp4"):
                filename = os.path.splitext(filename)[0] + ".mp4"
            return True, filename
    except Exception as e:
        err_msg = str(e)
        if "Unexpected response" in err_msg or "Sign in" in err_msg:
            try:
                ydl_opts['cookiesfrombrowser'] = (COOKIES_BROWSER,)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    if height == "audio_only":
                        filename = os.path.splitext(filename)[0] + ".mp3"
                    elif not filename.endswith(".mp4"):
                        filename = os.path.splitext(filename)[0] + ".mp4"
                    return True, filename
            except Exception as e2:
                return False, f"İndirilemedi: {str(e2)[-150:]}"
                
        return False, err_msg[-150:]