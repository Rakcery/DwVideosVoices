# Android'e özel işler: klasörler, galeriye ekleme, görüntü+ses birleştirme, Paylaş menüsü.
# pyjnius = Python'dan Android'in Java sınıflarını çağırmaya yarayan köprü.
# Bilgisayarda test ederken (Android değilken) yedek davranışlar devreye giriyor.

import os

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ

if IS_ANDROID:
    from jnius import autoclass
    from android.runnable import run_on_ui_thread

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Environment = autoclass("android.os.Environment")
    Intent = autoclass("android.content.Intent")
    MediaScannerConnection = autoclass("android.media.MediaScannerConnection")
    MediaExtractor = autoclass("android.media.MediaExtractor")
    MediaMuxer = autoclass("android.media.MediaMuxer")
    MuxerOutputFormat = autoclass("android.media.MediaMuxer$OutputFormat")
    MediaFormat = autoclass("android.media.MediaFormat")
    BufferInfo = autoclass("android.media.MediaCodec$BufferInfo")
    ByteBuffer = autoclass("java.nio.ByteBuffer")
    WindowManagerLP = autoclass("android.view.WindowManager$LayoutParams")
else:
    def run_on_ui_thread(f):
        return f


# ---------------------------------------------------------------- klasörler

def get_dirs():
    if not IS_ANDROID:
        base = os.path.abspath("dw_test_out")
        return {"work": os.path.join(base, "work"),
                "video": os.path.join(base, "Movies", "DWvideos"),
                "audio": os.path.join(base, "Music", "DWvideos")}

    ctx = PythonActivity.mActivity
    movies = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES).getAbsolutePath()
    music = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MUSIC).getAbsolutePath()
    dirs = {
        # Geçici dosyalar uygulamanın kendi önbelleğinde: Movies'e .part dosyası yazmak yasak
        "work": os.path.join(ctx.getCacheDir().getAbsolutePath(), "dl"),
        "video": os.path.join(movies, "DWvideos"),
        "audio": os.path.join(music, "DWvideos"),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    return dirs


# ---------------------------------------------------------------- galeri

def add_to_gallery(path):
    """MediaStore'a 'yeni dosya var' der -> galeride / müzik uygulamasında görünür."""
    if not IS_ANDROID:
        return
    MediaScannerConnection.scanFile(PythonActivity.mActivity, [path], None, None)


# ---------------------------------------------------------------- birleştirme

_BUF_SIZE = 8 * 1024 * 1024  # 8 MB: 1080p anahtar kareler için bol bol yeter


def _open_tracks(path, wanted):
    """Dosyadaki izleri açar. wanted: ("video/",) veya ("audio/",) veya ikisi.
    Dönüş: [(extractor, track_index, MediaFormat), ...]"""
    out = []
    probe = MediaExtractor()
    probe.setDataSource(path)
    count = probe.getTrackCount()
    for i in range(count):
        fmt = probe.getTrackFormat(i)
        mime = fmt.getString(MediaFormat.KEY_MIME) or ""
        if mime.startswith(wanted):
            ex = MediaExtractor()
            ex.setDataSource(path)
            ex.selectTrack(i)
            out.append((ex, fmt))
            wanted = tuple(w for w in wanted if not mime.startswith(w))  # her türden bir iz yeter
            if not wanted:
                break
    probe.release()
    return out


def _write_interleaved(muxer, tracks):
    """İzleri zaman sırasına göre sırayla yazar (video ve ses karışık, oynatıcılar sever)."""
    buf = ByteBuffer.allocate(_BUF_SIZE)
    info = BufferInfo()
    states = [[ex, t, ex.getSampleTime()] for ex, t in tracks]
    while True:
        alive = [s for s in states if s[2] >= 0]
        if not alive:
            break
        s = min(alive, key=lambda x: x[2])
        ex, t = s[0], s[1]
        size = ex.readSampleData(buf, 0)
        if size < 0:
            s[2] = -1
            continue
        info.set(0, size, ex.getSampleTime(), ex.getSampleFlags())
        muxer.writeSampleData(t, buf, info)
        ex.advance()
        s[2] = ex.getSampleTime()


def _mux_from(sources, out_path):
    """sources: [(dosya, ("video/",)), (dosya, ("audio/",))] gibi."""
    opened = []
    for path, wanted in sources:
        opened += _open_tracks(path, wanted)
    if not opened:
        raise RuntimeError("Dosyada okunabilir iz yok")
    muxer = MediaMuxer(out_path, MuxerOutputFormat.MUXER_OUTPUT_MPEG_4)
    try:
        tracks = []
        for ex, fmt in opened:
            tracks.append((ex, muxer.addTrack(fmt)))
        muxer.start()
        _write_interleaved(muxer, tracks)
        muxer.stop()
    finally:
        muxer.release()
        for ex, _ in opened:
            ex.release()


def mux(video_path, audio_path, out_path):
    """Ayrı gelen görüntü + sesi tek mp4 yapar. Yeniden kodlama yok, saniyeler sürer."""
    if not IS_ANDROID:
        raise RuntimeError("Birleştirme sadece Android'de")
    _mux_from([(video_path, ("video/",)), (audio_path, ("audio/",))], out_path)


def remux(in_path, out_path):
    """MPEG-TS gibi kutudaki videoyu temiz mp4 kutusuna aktarır."""
    if not IS_ANDROID:
        raise RuntimeError("Sadece Android'de")
    _mux_from([(in_path, ("video/", "audio/"))], out_path)


# ---------------------------------------------------------------- Paylaş menüsü

def shared_text_from_intent(intent=None):
    """Uygulama 'Paylaş' ile açıldıysa paylaşılan metni (linki) döndürür."""
    if not IS_ANDROID:
        return None
    try:
        if intent is None:
            intent = PythonActivity.mActivity.getIntent()
        if intent is None or intent.getAction() != Intent.ACTION_SEND:
            return None
        text = intent.getStringExtra(Intent.EXTRA_TEXT)
        # Aynı paylaşımı uygulama tekrar öne gelince bir daha işlememek için temizle
        intent.setAction("dwvideos.HANDLED")
        return text
    except Exception:
        return None


def bind_new_intent(callback):
    """Uygulama zaten açıkken yeni bir paylaşım gelirse callback(metin) çağrılır."""
    if not IS_ANDROID:
        return
    from android import activity

    def _on_new_intent(intent):
        text = shared_text_from_intent(intent)
        if text:
            callback(text)

    activity.bind(on_new_intent=_on_new_intent)


# ---------------------------------------------------------------- ekran

@run_on_ui_thread
def keep_screen_on(on):
    """İndirirken ekran kapanmasın -> Android uygulamayı uyutmasın."""
    if not IS_ANDROID:
        return
    win = PythonActivity.mActivity.getWindow()
    if on:
        win.addFlags(WindowManagerLP.FLAG_KEEP_SCREEN_ON)
    else:
        win.clearFlags(WindowManagerLP.FLAG_KEEP_SCREEN_ON)


def detach_thread():
    """Arka plan thread'i bitmeden önce çağrılmalı, yoksa pyjnius çökertir."""
    if IS_ANDROID:
        try:
            from jnius import detach
            detach()
        except Exception:
            pass
