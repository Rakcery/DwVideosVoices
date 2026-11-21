[app]
title = DWvideos
package.name = dwvideos
package.domain = com.ryuzakisnot
source.dir = .
source.include_exts = py,png,xml
source.exclude_dirs = bin,.buildozer,dw_test_out
version = 1.0

# Python paketleri. openssl: https için, sqlite3/liblzma: yt-dlp'nin istediği standart modüller
requirements = python3,kivy==2.3.1,pyjnius,android,openssl,sqlite3,liblzma,certifi,yt-dlp

icon.filename = %(source.dir)s/icon.png
orientation = portrait
fullscreen = 0

# Sadece internet. Android 11+ Movies/Music'e kendi dosyasını izinsiz yazabiliyor.
android.permissions = INTERNET
# 34 = Android 14'ü hedefle. Android 15'te sorunsuz kurulur, 35'in "kenardan kenara" zorunluluğu da bulaşmaz.
android.api = 34
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.manifest.intent_filters = intent_filters.xml
# Paylaşımla tekrar açılınca yeni pencere açmasın, mevcut uygulamaya gelsin
android.manifest.launch_mode = singleTask
android.enable_androidx = True

[buildozer]
log_level = 2
warn_on_root = 1
