import json
import threading
from tkinter import messagebox
from customtkinter import filedialog
from storage import load_config, save_config
import downloader

import customtkinter as ctk

from theme import INK, LINE, PAPER, DIM, BRASS, MOSS, RUST
from storage import lock, save_links
from downloader import download, QUALITY_OPTIONS, DEFAULT_QUALITY, DOWNLOAD_DIR_NAME

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

MONO = "Consolas"


class App:
    def __init__(self, root, links):
        self.root = root
        self.links = links
        self.last_state = None
        self.selected_urls = set()
        self.downloading_urls = set()
        self.progress_bars = {}  
        self.known_count = len(links)
        self.config = load_config()
        saved_dir = self.config.get("download_dir")
        if saved_dir:
            downloader.set_download_dir(saved_dir)

        root.title("DWvideos")
        root.geometry("440x660")
        root.configure(fg_color=INK)

        self._build_header()
        self._build_quality_selector()
        self._build_list()
        self._build_actions()

        self.refresh_list(force=True)
        self.poll_updates()

    # ---------- arayüz kurulumu ----------

    def _build_header(self):
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 4))

        top_row = ctk.CTkFrame(header, fg_color="transparent")
        top_row.pack(fill="x")

        ctk.CTkLabel(top_row, text="CLIPBOARD.DOWNLOADER", text_color=PAPER,
                     font=ctk.CTkFont(family=MONO, size=15, weight="bold")).pack(side="left")

        self.state_label = ctk.CTkLabel(top_row, text="[ HAZIR ]", text_color=DIM,
                                         font=ctk.CTkFont(family=MONO, size=11, weight="bold"))
        self.state_label.pack(side="right")

    def _build_quality_selector(self):
        frame = ctk.CTkFrame(self.root, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(10, 10))

        ctk.CTkLabel(frame, text="KALİTE", text_color=DIM,
                     font=ctk.CTkFont(family=MONO, size=10)).pack(side="left", padx=(0, 8))

        self.quality_var = ctk.StringVar(value=DEFAULT_QUALITY)
        dropdown = ctk.CTkOptionMenu(frame, values=list(QUALITY_OPTIONS.keys()),
                                      variable=self.quality_var,
                                      fg_color=LINE, button_color=LINE,
                                      button_hover_color=BRASS,
                                      text_color=PAPER, dropdown_fg_color="#111113",
                                      dropdown_text_color=PAPER, dropdown_hover_color=LINE,
                                      font=ctk.CTkFont(family=MONO, size=11),
                                      corner_radius=2, width=112, height=26)
        dropdown.pack(side="left")

        current_dir = self.config.get("download_dir", f"~/Desktop/{DOWNLOAD_DIR_NAME}")

        self.folder_btn = ctk.CTkButton(frame, text=self._shorten_path(current_dir), 
                                        fg_color="transparent", text_color=BRASS,
                                        border_width=1, border_color=LINE, hover_color=LINE,
                                        font=ctk.CTkFont(family=MONO, size=10),
                                        width=120, height=26, command=self.choose_folder)
        self.folder_btn.pack(side="right")

    def _shorten_path(self, path):
        path_str = str(path)
        return path_str if len(path_str) < 20 else "..." + path_str[-17:]

    def choose_folder(self):
        # parent=self.root ekledik, böylece klasör seçici penceresi uygulamanın arkasına saklanmayacak!
        folder = filedialog.askdirectory(parent=self.root, title="İndirme Klasörü Seç")
        if folder:
            downloader.set_download_dir(folder)
            self.config["download_dir"] = folder
            save_config(self.config)
            self.folder_btn.configure(text=self._shorten_path(folder))

    def _build_list(self):
        self.list_frame = ctk.CTkScrollableFrame(
            self.root, fg_color=INK, corner_radius=0,
            scrollbar_button_color=LINE, scrollbar_button_hover_color=BRASS,
        )
        self.list_frame.pack(fill="both", expand=True, padx=16, pady=(0, 4))

    def _build_actions(self):
        btn_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=16)

        self._make_button(btn_frame, "[ İNDİR ]", self.download_selected, BRASS).pack(
            side="left", expand=True, fill="x", padx=3)
        self._make_button(btn_frame, "[ HEPSİNİ İNDİR ]", self.download_all, BRASS).pack(
            side="left", expand=True, fill="x", padx=3)
        self._make_button(btn_frame, "[ SİL ]", self.delete_selected, RUST).pack(
            side="left", expand=True, fill="x", padx=3)

    def _make_button(self, parent, text, cmd, color):
        return ctk.CTkButton(parent, text=text, command=cmd,
                              fg_color="transparent", text_color=color,
                              hover_color=self._blend(color, INK, 0.82),
                              border_width=1, border_color=color,
                              corner_radius=2,
                              font=ctk.CTkFont(family=MONO, size=11, weight="bold"),
                              height=36)

    @staticmethod
    def _blend(hex_a, hex_b, t):
        a = hex_a.lstrip("#")
        b = hex_b.lstrip("#")
        ar, ag, ab = (int(a[i:i + 2], 16) for i in (0, 2, 4))
        br, bg, bb = (int(b[i:i + 2], 16) for i in (0, 2, 4))
        r = round(ar + (br - ar) * t)
        g = round(ag + (bg - ag) * t)
        bl = round(ab + (bb - ab) * t)
        return f"#{r:02x}{g:02x}{bl:02x}"

    # ---------- liste güncelleme ----------

    def refresh_list(self, force=False):
        with lock:
            state = json.dumps(self.links)
        if not force and state == self.last_state:
            return
        self.last_state = state

        for widget in self.list_frame.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass

        with lock:
            snapshot = list(self.links)

        present_urls = {item["url"] for item in snapshot}
        self.selected_urls &= present_urls

        if not snapshot:
            ctk.CTkLabel(self.list_frame,
                         text="KAYIT YOK — yakalamak için bir video linki kopyala.",
                         text_color=DIM, anchor="w",
                         font=ctk.CTkFont(family=MONO, size=11)).pack(fill="x", pady=20)
            return

        for i, item in enumerate(snapshot):
            self._build_row(item, i).pack(fill="x")
            if i < len(snapshot) - 1:
                ctk.CTkFrame(self.list_frame, height=1, fg_color=LINE,
                             corner_radius=0).pack(fill="x", padx=2)

    def _build_row(self, item, index):
        url = item["url"]
        done = item["downloaded"]
        is_checked = url in self.selected_urls
        is_downloading = url in self.downloading_urls

        row = ctk.CTkFrame(self.list_frame, fg_color="transparent", corner_radius=0)
        row.grid_columnconfigure(3, weight=1)

        bar = ctk.CTkFrame(row, width=3, height=1, fg_color=(BRASS if is_checked else INK),
                            corner_radius=0)
        bar.grid(row=0, column=0, rowspan=2, sticky="ns")

        check_char = "×" if is_checked else " "
        check_lbl = ctk.CTkLabel(row, text=f"[{check_char}]",
                                  text_color=BRASS if is_checked else DIM,
                                  font=ctk.CTkFont(family=MONO, size=12), width=30)
        check_lbl.grid(row=0, column=1, rowspan=2, padx=(10, 4), pady=8)

        num_lbl = ctk.CTkLabel(row, text=f"{index + 1:02d}", text_color=DIM, anchor="w",
                                font=ctk.CTkFont(family=MONO, size=11), width=24)
        num_lbl.grid(row=0, column=2, sticky="w", pady=(9, 0))

        url_lbl = ctk.CTkLabel(row, text=url, text_color=PAPER, anchor="w",
                                font=ctk.CTkFont(family=MONO, size=11))
        url_lbl.grid(row=0, column=3, sticky="ew", padx=(4, 12), pady=(9, 0))

        if is_downloading:
            tag_text, tag_color = "[AKTARILIYOR]", BRASS
        elif done:
            tag_text, tag_color = "[İNDİRİLDİ]", MOSS
        else:
            tag_text, tag_color = "[BEKLİYOR]", DIM
        tag_lbl = ctk.CTkLabel(row, text=tag_text, text_color=tag_color, anchor="w",
                                font=ctk.CTkFont(family=MONO, size=9))
        tag_lbl.grid(row=1, column=3, sticky="w", padx=(4, 12), pady=(0, 9))

        for widget in (row, check_lbl, num_lbl, url_lbl, tag_lbl):
            widget.bind("<Button-1>", lambda e, u=url: self._toggle_selected(u))

        progress = ctk.CTkProgressBar(row, height=2, fg_color=INK, progress_color=BRASS)
        progress.set(0)
        progress.grid(row=2, column=1, columnspan=3, sticky="we", padx=(10, 12), pady=(0, 5))
        progress.grid_remove()  # Sadece indirme başlarken görünür olacak
        self.progress_bars[url] = progress  # Çubuğu url ile eşleştirerek sakla
        
        # O çubuğun üstüne tıklanınca da seçme işlemi çalışsın
        progress.bind("<Button-1>", lambda e, u=url: self._toggle_selected(u))

        return row

    def _toggle_selected(self, url):
        if url in self.selected_urls:
            self.selected_urls.discard(url)
        else:
            self.selected_urls.add(url)
        self.refresh_list(force=True)

    def poll_updates(self):
        with lock:
            current_count = len(self.links)
        if current_count > self.known_count and not self.downloading_urls:
            self._flash_capture()
        self.known_count = current_count

        self.refresh_list()
        self.root.after(1000, self.poll_updates)

    def _flash_capture(self):
        self.state_label.configure(text="[ YAKALANDI ]", text_color=BRASS)
        self.root.after(700, self._reset_state_label)

    def _reset_state_label(self):
        if not self.downloading_urls:
            self.state_label.configure(text="[ HAZIR ]", text_color=DIM)

    # ---------- indirme / silme aksiyonları ----------

    def download_selected(self):
        with lock:
            targets = [item["url"] for item in self.links if item["url"] in self.selected_urls]
        if not targets:
            messagebox.showinfo("Bilgi", "Önce en az bir link işaretle.")
            return
        threading.Thread(target=self._run_downloads, args=(targets,), daemon=True).start()

    def download_all(self):
        with lock:
            targets = [item["url"] for item in self.links if not item["downloaded"]]
        if not targets:
            return
        threading.Thread(target=self._run_downloads, args=(targets,), daemon=True).start()

    def _run_downloads(self, urls):
        quality = self.quality_var.get()
        self.downloading_urls.update(urls)
        
        # Thread içinden ana GUI'yi güvenle güncellemek için yardımcı
        def update_ui(cb):
            self.root.after(0, cb)
            
        update_ui(lambda: self.state_label.configure(text="[ AKTARILIYOR ]", text_color=BRASS))
        update_ui(lambda: self.refresh_list(force=True))

        for url in urls:
            target_item = next((i for i in self.links if i["url"] == url), None)
            
            # İndirme başlarken çubuğu göster ve sıfırla
            update_ui(lambda u=url: (self.progress_bars[u].set(0), self.progress_bars[u].grid()) if u in self.progress_bars else None)

            def progress_hook(pct, u=url):
                if u in self.progress_bars:
                    update_ui(lambda: self.progress_bars[u].set(pct))

            # Downloader'a callback'i paslıyoruz
            ok, err = downloader.download(url, quality, progress_callback=progress_hook)
            
            self.downloading_urls.discard(url)
            
            # İndirme bitince çubuğu tekrar gizle
            update_ui(lambda u=url: self.progress_bars[u].grid_remove() if u in self.progress_bars else None)
                
            if ok:
                with lock:
                    if target_item:
                        target_item["downloaded"] = True
                    save_links(self.links)
                self.selected_urls.discard(url)
            else:
                update_ui(lambda u=url, e=err: messagebox.showerror("Hata", f"{u}\n\n{e}"))
                
            update_ui(lambda: self.refresh_list(force=True))

        update_ui(lambda: self.state_label.configure(text="[ HAZIR ]", text_color=DIM))

    def delete_selected(self):
        if not self.selected_urls:
            messagebox.showinfo("Bilgi", "Önce en az bir link işaretle.")
            return
        with lock:
            self.links[:] = [item for item in self.links if item["url"] not in self.selected_urls]
            save_links(self.links)
        self.selected_urls.clear()
        self.refresh_list(force=True)