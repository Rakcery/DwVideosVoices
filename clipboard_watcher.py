import re
import time

import pyperclip

from storage import lock, save_links

URL_PATTERN = re.compile(r'https?://[^\s]+')


def watch_clipboard(links):
    """Ayrı bir thread'de çalışır, clipboard değişince linki yakalar."""
    last_value = ""
    while True:
        try:
            current = pyperclip.paste()
        except Exception:
            time.sleep(1)
            continue

        if current != last_value:
            last_value = current
            match = URL_PATTERN.search(current)
            if match:
                url = match.group(0)
                with lock:
                    if url not in [item["url"] for item in links]:
                        links.append({"url": url, "downloaded": False})
                        save_links(links)
        time.sleep(0.7)
