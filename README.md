# DW Videos & Voices

Video ve ses içeriklerini kolay bir şekilde indirip yönetmek için geliştirilmiş, Python tabanlı masaüstü uygulaması.

## ✨ Özellikler

* 🎥 Desteklenen platformlardan video indirme
* 🎵 Videolardan yalnızca ses indirme
* 📋 Kopyalanan bağlantıları otomatik olarak algılama
* 🖥️ Kullanıcı dostu grafik arayüz (GUI)
* ⚙️ İndirme ayarlarını yapılandırabilme
* 💾 İndirilen içerikleri yerel olarak yönetme
* 🚀 Hafif ve kullanımı kolay yapı

## 📁 Proje Yapısı

```text
DwVideosVoices/
│
├── main.py                 # Uygulamanın başlangıç noktası
├── gui.py                  # Grafik kullanıcı arayüzü
├── downloader.py           # Video ve ses indirme işlemleri
├── clipboard_watcher.py    # Pano bağlantılarını takip eder
├── storage.py              # Yerel veri ve depolama işlemleri
├── theme.py                # Uygulama teması ve görünümü
├── config.json             # Uygulama ayarları
├── links.json              # Kaydedilen bağlantılar/veriler
├── icon.ico                # Uygulama ikonu
└── DWvideos.spec           # PyInstaller yapılandırması
```

## 🛠️ Gereksinimler

* Python 3.10 veya üzeri
* Windows
* Gerekli Python kütüphaneleri

## 📥 Kurulum

Öncelikle projeyi bilgisayarınıza klonlayın:

```bash
git clone https://github.com/Rakcery/DwVideosVoices.git
cd DwVideosVoices
```

Daha sonra gerekli Python kütüphanelerini yükleyin:

```bash
pip install -r requirements.txt
```

## ▶️ Uygulamayı Çalıştırma

Uygulamayı başlatmak için:

```bash
python main.py
```

Komut çalıştırıldığında uygulamanın grafik arayüzü açılacaktır.

## 📦 EXE Oluşturma

Projeyi Python yüklü olmayan bilgisayarlarda da çalıştırabilmek için PyInstaller kullanarak `.exe` dosyası oluşturabilirsiniz.

```bash
pyinstaller DWvideos.spec
```

İşlem tamamlandıktan sonra oluşturulan uygulamayı `dist` klasörü içerisinde bulabilirsiniz.

## ⚙️ Çalışma Mantığı

Uygulama, kullanıcının panosuna kopyaladığı bağlantıları algılayarak indirme işlemini kolaylaştırır.

Kullanıcı, grafik arayüz üzerinden indirme işlemlerini yönetebilir ve video veya ses formatında içerik indirebilir.

Proje içerisindeki farklı işlemler ayrı Python dosyalarına bölünerek daha düzenli ve yönetilebilir bir yapı oluşturulmuştur.

## ⚠️ Yasal Uyarı

Bu proje eğitim ve kişisel kullanım amacıyla geliştirilmiştir.

İndirdiğiniz içeriklerin kullanım haklarına sahip olduğunuzdan veya gerekli izinlere sahip olduğunuzdan emin olun. Kullandığınız platformların kullanım koşullarına ve telif hakkı yasalarına uyun.

## 📄 Lisans

Bu proje şu anda herhangi bir açık kaynak lisansı belirtmemektedir.
