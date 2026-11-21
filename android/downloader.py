# DWvideos - Android indirme çekirdeği
# Masaüstü sürümünden farkları:
#   - ffmpeg yok. Görüntü + ses ayrı geldiğinde Android'in kendi MediaMuxer'ı ile
#     birleştiriliyor (yeniden kodlama yok, sadece kutuya koyma -> hızlı).
#   - requests yerine standart kütüphane (urllib) -> APK'da derleme derdi yok.
#   - Çıktı: videolar Movies/DWvideos, sesler Music/DWvideos (galeri / müzik uygulaması görür).

import json
import os
import re
import shutil
import ssl
import urllib.parse
import urllib.request

import certifi

QUALITY_OPTIONS = {
    "360p": 360,
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "Sadece Ses": "audio",
}
DEFAULT_QUALITY = "720p"

UA = ("Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36")
SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# MP4 kutusuna Android'in sorunsuz koyabildiği codec'ler
VIDEO_CODECS = ("avc1", "avc3", "h264", "hev1", "hvc1", "h265")
AUDIO_CODECS = ("mp4a", "aac")


class DownloadError(Exception):
    """Kullanıcıya gösterilecek, anlaşılır hata."""


# ---------------------------------------------------------------- yardımcılar

URL_RE = re.compile(r"https?://[^\s<>\"']+")


def extract_url(text):
    """Paylaşılan metnin içinden ilk linki çeker.
    TikTok/Instagram bazen 'Şu videoya bak! https://...' gibi metin yolluyor."""
    if not text:
        return None
    m = URL_RE.search(text)
    return m.group(0).rstrip(").,;!") if m else None


def safe_name(title):
    name = re.sub(r'[\\/*?:"<>|\r\n\t]', "", title or "").strip()
    return name[:80].strip() or "video"


def unique_path(folder, name, ext):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{name}.{ext}")
    i = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{name} ({i}).{ext}")
        i += 1
    return path


def _codec_ok(codec, allowed):
    return bool(codec) and codec != "none" and codec.lower().startswith(allowed)


def _proto_rank(f):
    # Düz https dosyası > HLS parçaları > geri kalanlar
    p = (f.get("protocol") or "")
    if p in ("https", "http"):
        return 2
    if p.startswith("m3u8"):
        return 1
    return 0


def pick_formats(formats, max_height):
    """yt-dlp'nin format listesinden plan çıkarır.

    Dönüş:
      ("split", video_id, audio_id)  -> ayrı görüntü + ses, telefonda birleştirilecek
      ("single", format_id)          -> görüntü ve ses zaten tek dosyada
      None                           -> uygun bir şey yok, yt-dlp'nin kendi seçimine bırak
    """
    def h(f):
        return f.get("height") or 0

    videos, audios, singles = [], [], []
    for f in formats or []:
        v, a = f.get("vcodec"), f.get("acodec")
        if f.get("format_note") == "storyboard" or (f.get("ext") == "mhtml"):
            continue
        has_v = v not in (None, "none")
        has_a = a not in (None, "none")
        if has_v and not has_a and _codec_ok(v, VIDEO_CODECS) and h(f) <= max_height:
            videos.append(f)
        elif has_a and not has_v and _codec_ok(a, AUDIO_CODECS):
            audios.append(f)
        elif has_v and has_a and (h(f) <= max_height or not f.get("height")):
            # Codec bilgisi olmayan tek dosyaları da kabul et (Instagram/Twitter böyle)
            if _codec_ok(v, VIDEO_CODECS) or v is None or f.get("ext") == "mp4":
                singles.append(f)

    def vkey(f):
        return (h(f), _proto_rank(f), f.get("tbr") or 0)

    best_v = max(videos, key=vkey, default=None)
    best_a = max(audios, key=lambda f: (_proto_rank(f), f.get("abr") or f.get("tbr") or 0), default=None)
    best_s = max(singles, key=vkey, default=None)

    if best_v and best_a and (best_s is None or h(best_v) > h(best_s)):
        return ("split", best_v["format_id"], best_a["format_id"])
    if best_s:
        return ("single", best_s["format_id"])
    return None


def pick_audio(formats):
    audios = [f for f in formats or []
              if f.get("vcodec") in (None, "none") and _codec_ok(f.get("acodec"), AUDIO_CODECS)]
    best = max(audios, key=lambda f: (_proto_rank(f), f.get("abr") or f.get("tbr") or 0), default=None)
    return best["format_id"] if best else None


# ---------------------------------------------------------------- TikTok

def _http(url, data=None, timeout=30):
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX)


def _stream_to_file(url, path, progress):
    with _http(url, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        with open(path, "wb") as f:
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    progress(done / total)


def _download_tiktok(url, audio_only, dirs, progress):
    with _http("https://www.tikwm.com/api/", data={"url": url, "hd": 1}, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("code") != 0:
        raise DownloadError("TikTok videosu bulunamadı: " + str(data.get("msg", "")))

    v = data.get("data") or {}
    name = safe_name(v.get("title") or "tiktok_video")
    link = v.get("music") if audio_only else (v.get("hdplay") or v.get("play"))
    if not link:
        raise DownloadError("TikTok indirme bağlantısı alınamadı.")
    if link.startswith("/"):
        link = "https://www.tikwm.com" + link

    if audio_only:
        out = unique_path(dirs["audio"], name, "mp3")
    else:
        out = unique_path(dirs["video"], name, "mp4")
    tmp = os.path.join(dirs["work"], "tiktok.part")
    _stream_to_file(link, tmp, progress)
    shutil.move(tmp, out)
    return out


# ---------------------------------------------------------------- ana akış

def download(url, quality, dirs, progress=lambda x: None, mux=None, remux=None):
    """
    url      : video linki
    quality  : QUALITY_OPTIONS anahtarı
    dirs     : {"work": geçici klasör, "video": Movies/DWvideos, "audio": Music/DWvideos}
    progress : 0.0-1.0 arası ilerleme bildirimi
    mux      : mux(video_yolu, ses_yolu, çıktı_yolu)  -> ayrı görüntü+sesi tek mp4 yapar
    remux    : remux(girdi, çıktı) -> TS/HLS gibi dosyaları temiz mp4'e çevirir (opsiyonel)
    Dönüş: kaydedilen dosyanın yolu
    """
    import yt_dlp  # geç import: hata olursa uygulama çökmesin, ekranda yazsın

    url = extract_url(url) or url.strip()
    if not url.startswith("http"):
        raise DownloadError("Geçerli bir link değil.")

    target = QUALITY_OPTIONS.get(quality, 720)
    audio_only = target == "audio"
    os.makedirs(dirs["work"], exist_ok=True)

    if "tiktok.com" in url.lower():
        try:
            return _download_tiktok(url, audio_only, dirs, progress)
        except DownloadError:
            raise
        except Exception as e:
            raise DownloadError(f"TikTok indirme hatası: {str(e)[-150:]}")

    # aşama: (başlangıç, bitiş) -> ilerleme çubuğunu parçalara bölmek için
    stage = {"lo": 0.0, "hi": 1.0}

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                frac = min(d.get("downloaded_bytes", 0) / total, 1.0)
            elif d.get("fragment_count"):
                frac = (d.get("fragment_index") or 0) / d["fragment_count"]
            else:
                return
            progress(stage["lo"] + (stage["hi"] - stage["lo"]) * frac)

    base = {
        "quiet": True,
        "noprogress": True,
        "no_warnings": True,
        "noplaylist": True,
        "cachedir": False,
        "outtmpl": os.path.join(dirs["work"], "%(id)s.f%(format_id)s.%(ext)s"),
        "progress_hooks": [hook],
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
        "http_headers": {"User-Agent": UA},
    }

    def get_info(extra=None):
        opts = dict(base)
        if extra:
            opts.update(extra)
        o = dict(opts)
        o["format"] = "bv*+ba/b/bv*/ba"  # sadece bilgi almak için, her zaman bir şey eşleşsin
        with yt_dlp.YoutubeDL(o) as y:
            info = y.extract_info(url, download=False)
        if info.get("_type") in ("playlist", "multi_video"):
            entries = [e for e in (info.get("entries") or []) if e]
            if not entries:
                raise DownloadError("Linkte video bulunamadı.")
            info = entries[0]
        return _clean_info(info), opts

    def fetch(info, opts, fmt, lo, hi):
        stage["lo"], stage["hi"] = lo, hi
        o = dict(opts)
        o["format"] = fmt
        with yt_dlp.YoutubeDL(o) as y:
            res = y.process_ie_result(dict(info), download=True)
            reqs = res.get("requested_downloads") or []
            path = reqs[0].get("filepath") if reqs else None
            return path or y.prepare_filename(res)

    # YouTube JS motoru (deno) olmadan bazı istemcilerde format çıkmayabiliyor.
    # Önce varsayılan, olmazsa JS istemeyen başka istemcilerle tekrar dene.
    attempts = [None, {"extractor_args": {"youtube": {"player_client": ["android_vr", "ios"]}}}]
    is_youtube = any(k in url for k in ("youtube.com", "youtu.be"))
    last_err = None

    for extra in (attempts if is_youtube else [None]):
        try:
            info, opts = get_info(extra)
            title = safe_name(info.get("title"))
            formats = info.get("formats") or []

            if audio_only:
                aid = pick_audio(formats)
                path = fetch(info, opts, aid or "ba/b", 0.0, 0.98)
                ext = os.path.splitext(path)[1].lstrip(".").lower() or "m4a"
                if ext == "mp4":
                    ext = "m4a"
                out = unique_path(dirs["audio"], title, ext)
                shutil.move(path, out)
                return out

            plan = pick_formats(formats, target)
            if plan and plan[0] == "split" and mux:
                v = fetch(info, opts, plan[1], 0.0, 0.75)
                a = fetch(info, opts, plan[2], 0.75, 0.97)
                out = unique_path(dirs["video"], title, "mp4")
                try:
                    mux(v, a, out)
                except Exception as e:
                    if os.path.exists(out):
                        os.remove(out)
                    raise DownloadError(f"Görüntü ve ses birleştirilemedi: {e}")
                finally:
                    for p in (v, a):
                        if p and os.path.exists(p):
                            os.remove(p)
                progress(1.0)
                return out

            fmt = plan[1] if plan and plan[0] == "single" else f"b[height<={target}]/b"
            path = fetch(info, opts, fmt, 0.0, 0.97)
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "mp4"
            needs_remux = remux is not None and (ext != "mp4" or _looks_like_ts(path))
            if needs_remux:
                out = unique_path(dirs["video"], title, "mp4")
                try:
                    remux(path, out)
                    os.remove(path)
                except Exception:
                    # Birleştirici bu codec'i kabul etmedi (ör. webm/vp9): dosyayı olduğu gibi bırak
                    if os.path.exists(out):
                        os.remove(out)
                    out = unique_path(dirs["video"], title, ext)
                    shutil.move(path, out)
            else:
                out = unique_path(dirs["video"], title, ext)
                shutil.move(path, out)
            progress(1.0)
            return out

        except DownloadError as e:
            last_err = e
        except Exception as e:
            last_err = e
        _cleanup(dirs["work"])

    msg = str(last_err) if last_err else "Bilinmeyen hata"
    if "Sign in" in msg or "confirm" in msg.lower():
        raise DownloadError("YouTube bu videoyu giriş yapmadan vermiyor (yaş sınırı / bot kontrolü).")
    if "Requested format is not available" in msg:
        raise DownloadError("Bu video için telefonda oynayan bir format bulunamadı. Başka kalite dene.")
    if "Unsupported URL" in msg:
        raise DownloadError("Bu site desteklenmiyor.")
    raise DownloadError(msg[-200:])


def _clean_info(info):
    """yt-dlp bilgi alırken seçtiği formatın alanlarını (url, format_id...) ana bilgiye yazıyor.
    Bunlar kalırsa ikinci seferde seçtiğimiz format yerine o birleşik adrese gidiyor -> temizle."""
    drop = {"requested_formats", "requested_downloads", "requested_subtitles", "format",
            "format_id", "url", "manifest_url", "ext", "protocol", "fragments", "fragment_base_url"}
    for f in info.get("formats") or []:
        drop.update(f.keys())
    keep = {"id", "title", "formats", "extractor", "extractor_key", "webpage_url",
            "original_url", "webpage_url_basename", "webpage_url_domain", "duration",
            "thumbnails", "uploader", "_type", "_version"}
    return {k: v for k, v in info.items() if k in keep or k not in drop}


def _looks_like_ts(path):
    """HLS'ten gelen dosya bazen .mp4 adlı ama içi MPEG-TS oluyor (0x47 ile başlar)."""
    try:
        with open(path, "rb") as f:
            head = f.read(189)
        return len(head) >= 189 and head[0] == 0x47 and head[188] == 0x47
    except OSError:
        return False


def _cleanup(work):
    try:
        for n in os.listdir(work):
            if n.endswith((".part", ".ytdl")) or ".f" in n:
                try:
                    os.remove(os.path.join(work, n))
                except OSError:
                    pass
    except OSError:
        pass
