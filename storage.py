import json
import os
import threading
from pathlib import Path

# 1. Uygulama verileri için gizli AppData klasörünü ayarla ve oluştur
app_data_dir = Path(os.getenv('APPDATA')) / "DWvideos"
app_data_dir.mkdir(parents=True, exist_ok=True)

# 2. Dosya yollarını güncelleyerek bu gizli klasöre bağla
LIST_FILE = str(app_data_dir / "links.json")
CONFIG_FILE = str(app_data_dir / "config.json")

# GUI ve clipboard izleyici thread'i aynı listeye dokunuyor, o yüzden
# her okuma/yazmada bu lock kullanılıyor.
lock = threading.Lock()

def load_links():
    if os.path.exists(LIST_FILE):
        try:
            with open(LIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

def save_links(links):
    with open(LIST_FILE, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=2)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)