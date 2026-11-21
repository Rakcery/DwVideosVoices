# DWvideos - Android

Masaüstü DWvideos'un telefon sürümü. ffmpeg yok; görüntü ve ses ayrı gelirse
Android'in kendi MediaMuxer'ı ile birleştiriliyor.

- Videolar: Galeri → DWvideos (Movies/DWvideos)
- Sesler: Müzik → DWvideos (Music/DWvideos)
- YouTube / TikTok / Instagram'da Paylaş → DWvideos

## APK derleme
GitHub → Actions → "APK Derle" → Run workflow. Bitince sayfanın altındaki
`DWvideos-apk` dosyasını indir, içindeki .apk'yı telefona at.

YouTube bozulursa: Actions'tan tekrar derle, en yeni yt-dlp ile yeni APK çıkar.
