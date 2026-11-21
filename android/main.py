# DWvideos - Android sürümü (Kivy)
# Kullanım: YouTube/TikTok/Instagram'da Paylaş -> DWvideos  ya da linki yapıştır -> İNDİR.
# Videolar galeride "DWvideos" albümüne, sesler müzik uygulamasına düşer.

import json
import os
import threading
import traceback

import certifi

# Android'de Python sistem sertifikalarını bulamıyor -> certifi'nin listesini göster
os.environ.setdefault("SSL_CERT_FILE", certifi.where())

from kivy.app import App
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

import platform_android as plat
from downloader import (QUALITY_OPTIONS, DEFAULT_QUALITY, DownloadError,
                        download, extract_url)

# masaüstü sürümündeki tema
INK = (0.039, 0.039, 0.043, 1)     # zemin
LINE = (0.137, 0.137, 0.149, 1)    # kenarlık
PAPER = (1, 1, 1, 1)               # metin
DIM = (0.55, 0.55, 0.57, 1)        # ikincil metin
BRASS = (0.757, 0.565, 0.31, 1)    # vurgu
MOSS = (0.498, 0.58, 0.443, 1)     # başarılı
RUST = (0.659, 0.314, 0.227, 1)    # hata

Window.clearcolor = INK
# Klavye açılınca ekran yukarı kaysın, kutu klavyenin altında kalmasın
Window.softinput_mode = "below_target"


def rounded_bg(widget, color, radius=dp(14)):
    with widget.canvas.before:
        c = Color(*color)
        r = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[radius])
    widget.bind(pos=lambda w, v: setattr(r, "pos", v), size=lambda w, v: setattr(r, "size", v))
    return c


class BigButton(Button):
    def __init__(self, bg=LINE, fg=PAPER, **kw):
        kw.setdefault("font_size", sp(20))
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(60))
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), color=fg, bold=True, **kw)
        self._bg = rounded_bg(self, bg)
        self._base = bg
        self.bind(state=self._press)

    def _press(self, *_):
        k = 0.75 if self.state == "down" else 1.0
        self._bg.rgba = (self._base[0] * k, self._base[1] * k, self._base[2] * k, 1)

    def set_bg(self, bg):
        self._base = bg
        self._bg.rgba = bg


class Option(SpinnerOption):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.background_normal = ""
        self.background_color = LINE
        self.font_size = sp(20)
        self.height = dp(56)


class Root(BoxLayout):
    def __init__(self, app, **kw):
        # Üstte 36dp boşluk: saat/şarj çubuğunun altında kalmasın
        super().__init__(orientation="vertical", padding=[dp(20), dp(36), dp(20), dp(20)],
                         spacing=dp(14), **kw)
        self.app = app

        self.add_widget(Label(text="[b]DWvideos[/b]", markup=True, font_size=sp(34), color=BRASS,
                              size_hint_y=None, height=dp(56)))
        self.add_widget(self._wrap_label(
            "YouTube, TikTok, Instagram'da [b]Paylaş → DWvideos[/b]'a bas\nya da linki aşağıya yapıştır.",
            DIM, sp(16), dp(52)))

        self.url = TextInput(hint_text="Video linki", multiline=False, font_size=sp(18),
                             size_hint_y=None, height=dp(56), padding=[dp(14), dp(16)],
                             background_normal="", background_active="",
                             background_color=LINE, foreground_color=PAPER,
                             hint_text_color=DIM, cursor_color=BRASS)
        self.add_widget(self.url)

        row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(12))
        paste = BigButton(text="Yapıştır", height=dp(56))
        paste.bind(on_release=lambda *_: self.paste())
        clear = BigButton(text="Temizle", height=dp(56))
        clear.bind(on_release=lambda *_: setattr(self.url, "text", ""))
        row.add_widget(paste)
        row.add_widget(clear)
        self.add_widget(row)

        self.add_widget(Label(text="Kalite", font_size=sp(16), color=DIM, size_hint_y=None,
                              height=dp(22), halign="left", text_size=(Window.width - dp(40), None)))
        self.quality = Spinner(text=app.saved_quality(), values=list(QUALITY_OPTIONS.keys()),
                               option_cls=Option, font_size=sp(20), size_hint_y=None, height=dp(56),
                               background_normal="", background_color=LINE, color=PAPER)
        self.quality.bind(text=lambda _, v: app.save_quality(v))
        self.add_widget(self.quality)

        self.go = BigButton(text="İNDİR", bg=BRASS, fg=INK, font_size=sp(26), height=dp(78))
        self.go.bind(on_release=lambda *_: self.start())
        self.add_widget(self.go)

        self.bar = ProgressBar(max=1.0, value=0, size_hint_y=None, height=dp(24))
        self.add_widget(self.bar)

        self.status = self._wrap_label("", PAPER, sp(17), dp(110))
        self.add_widget(self.status)

        self.add_widget(Widget())  # kalan boşluğu doldur
        self.add_widget(self._wrap_label("Videolar: Galeri → DWvideos albümü\nSesler: Müzik → DWvideos",
                                         DIM, sp(14), dp(44)))

    def _wrap_label(self, text, color, size, height):
        lbl = Label(text=text, markup=True, color=color, font_size=size, size_hint_y=None,
                    height=height, halign="center", valign="middle")
        lbl.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
        return lbl

    # ------------------------------------------------------------ eylemler

    def paste(self):
        link = extract_url(Clipboard.paste() or "")
        if link:
            self.url.text = link
            self.say("Link yapıştırıldı. [b]İNDİR[/b]'e bas.", PAPER)
        else:
            self.say("Panoda link yok. Önce videonun linkini kopyala.", RUST)

    def set_link(self, text, auto=False):
        link = extract_url(text)
        if not link:
            return
        self.url.text = link
        if auto and not self.app.busy:
            self.start()
        elif not self.app.busy:
            self.say("Link geldi. [b]İNDİR[/b]'e bas.", PAPER)

    def say(self, text, color=PAPER):
        self.status.text = text
        self.status.color = color

    def start(self):
        if self.app.busy:
            return
        link = extract_url(self.url.text)
        if not link:
            self.say("Önce bir video linki yapıştır.", RUST)
            return
        self.app.busy = True
        self.go.text = "İNDİRİLİYOR..."
        self.go.set_bg(LINE)
        self.go.color = DIM
        self.bar.value = 0
        self.say("Hazırlanıyor... Bitene kadar uygulamayı kapatma.", PAPER)
        plat.keep_screen_on(True)
        threading.Thread(target=self._worker, args=(link, self.quality.text), daemon=True).start()

    def _worker(self, link, quality):
        try:
            path = download(link, quality, self.app.dirs,
                            progress=lambda f: Clock.schedule_once(lambda dt: self._progress(f)),
                            mux=plat.mux, remux=plat.remux)
            plat.add_to_gallery(path)
            Clock.schedule_once(lambda dt: self._done(path, None))
        except DownloadError as e:
            msg = str(e)
            Clock.schedule_once(lambda dt: self._done(None, msg))
        except Exception as e:
            traceback.print_exc()
            msg = f"Beklenmeyen hata: {str(e)[-200:]}"
            Clock.schedule_once(lambda dt: self._done(None, msg))
        finally:
            plat.detach_thread()

    def _progress(self, f):
        self.bar.value = f
        self.say(f"İndiriliyor... %{int(f * 100)}\nBitene kadar uygulamayı kapatma.", PAPER)

    def _done(self, path, err):
        self.app.busy = False
        plat.keep_screen_on(False)
        self.go.text = "İNDİR"
        self.go.set_bg(BRASS)
        self.go.color = INK
        if err:
            self.bar.value = 0
            self.say("[b]Olmadı:[/b] " + err, RUST)
        else:
            self.bar.value = 1
            where = "Müzik" if os.path.dirname(path).endswith(os.path.join("Music", "DWvideos")) \
                else "Galeri"
            self.say(f"[b]Tamam![/b] {where} → DWvideos'a kaydedildi.\n{os.path.basename(path)}", MOSS)
            self.url.text = ""


class DWvideosApp(App):
    title = "DWvideos"
    busy = False

    def build(self):
        self.icon = "icon.png"
        self._cfg_path = os.path.join(self.user_data_dir, "ayarlar.json")
        self.dirs = plat.get_dirs()
        self.root_w = Root(self)
        plat.bind_new_intent(lambda t: Clock.schedule_once(lambda dt: self.root_w.set_link(t, auto=False)))
        return self.root_w

    def on_start(self):
        shared = plat.shared_text_from_intent()
        if shared:
            self.root_w.set_link(shared)

    def on_pause(self):
        return True  # arka plana alınınca kapanma, indirme devam etsin

    # ------------------------------------------------------------ ayar

    def saved_quality(self):
        try:
            with open(self._cfg_path, encoding="utf-8") as f:
                q = json.load(f).get("quality")
            if q in QUALITY_OPTIONS:
                return q
        except Exception:
            pass
        return DEFAULT_QUALITY

    def save_quality(self, q):
        try:
            with open(self._cfg_path, "w", encoding="utf-8") as f:
                json.dump({"quality": q}, f)
        except Exception:
            pass


if __name__ == "__main__":
    DWvideosApp().run()
