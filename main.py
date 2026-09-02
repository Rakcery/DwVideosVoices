import threading
import customtkinter as ctk
import ctypes  # Windows görev çubuğu ikonunu zorlamak için gerekli

from storage import load_links
from clipboard_watcher import watch_clipboard
from gui import App

def main():
    try:
        app_id = "dwvideos.downloader.app.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass

    links = load_links()

    watcher = threading.Thread(target=watch_clipboard, args=(links,), daemon=True)
    watcher.start()

    root = ctk.CTk()
    
    # Sol üstteki ve görev çubuğundaki ikonu senin .ico dosyanla değiştirir
    try:
        root.iconbitmap("icon.ico")
    except Exception:
        pass  # İkon dosyası bulunamazsa program çökmesin diye

    App(root, links)
    root.mainloop()

if __name__ == "__main__":
    main()