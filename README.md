# Premier Video & Media Player 🎬🖼️

Modern, güçlü ve şık bir masaüstü medya oynatıcı ve görüntüleyici. PyQt6 mimarisi üzerine inşa edilmiş olup, hem gelişmiş video oynatma hem de yüksek çözünürlüklü görsel inceleme yetenekleri sunar.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green?logo=qt)
![FFmpeg](https://img.shields.io/badge/Backend-FFmpeg-red?logo=ffmpeg)
![License](https://img.shields.io/badge/License-MIT-purple)

---

## ✨ Özellikler (Features)

- 🎥 **Geniş Medya Desteği**:
  - **Video**: `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.ts`, `.m2ts`, `.ogv`, `.3gp`
  - **Görseller**: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.gif`, `.tiff`, `.svg`, `.jfif`, `.avif`
- 🎞️ **YouTube Tarzı Zaman Çizelgesi Önizlemesi (Seek Bar Hover Preview)**:
  - İlerleme çubuğunda fareyi gezdirdiğinizde saniyeye göre arka planda FFmpeg ile anlık kare önizlemesi (thumbnail tooltip).
- 📂 **Akıllı Galeri & Dizin Gezgini (Drawer)**:
  - Klasördeki tüm video ve fotoğrafları otomatik listeler.
  - Yatay fare tekerleği (wheel) ile kaydırılabilir önizleme kartları.
  - Üst dizine çıkış ve alt klasörler arasında anında geçiş desteği.
- 🔍 **Gelişmiş Zoom & Pan Desteği**:
  - Fare tekerleği ile sınırsız yakınlaştırma / uzaklaştırma.
  - Sürükle-bırak (pan) ile görüntü üzerinde rahatça gezinme.
  - Otomatik merkezleme ve sıfırlama (`Reset Zoom`).
  - 🔄 90° açılarla anlık video ve görsel döndürme.
- 🎨 **Görsel Efekt ve Ayar Paneli**:
  - Netlik (NumPy tabanlı Unsharp Mask filtresi)
  - Bulanıklık (Blur)
  - Renklendirme ve parlaklık ayarları
- 🎧 **Ses & İz Seçimi**:
  - Çoklu ses kanalı / dil izi (Audio Track) seçimi.
  - Hassas ses düzeyi ve sessize alma (Mute).
- 📸 **Anlık Ekran Görüntüsü (Screenshot)**:
  - İzlediğiniz anın yüksek kaliteli ekran karesini doğrudan `Pictures` klasörüne kaydeder.
- 🔖 **Kalıcı Yer İmleri (Bookmarks)**:
  - Videolarda önemli anları zaman damgası ve açıklama ile kaydedip tek tıkla geri dönme.
- 🔁 **Oynatma Modları & Hız**:
  - Tekrar modları (Tek video döngüsü, Tüm liste döngüsü, Kapalı).
  - 0.25x ile 2.0x arasında oynatma hızı ayarı.
  - Kaldığı yerden devam etme (Resume playback).

---

## 🚀 Kurulum (Installation)

### 1. Gereksinimler
Sisteminizde **Python 3.10+** ve video önizleme/kare işleme için **FFmpeg** kurulu olmalıdır.

#### Ubuntu / Debian:
```bash
sudo apt update
sudo apt install python3 python3-pip ffmpeg
```

#### Arch Linux:
```bash
sudo pacman -S python python-pip ffmpeg
```

#### macOS:
```bash
brew install python ffmpeg
```

#### Windows:
- Python ve [FFmpeg](https://ffmpeg.org/download.html) kurun ve ortam değişkenlerine (PATH) ekleyin.

### 2. Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

---

## 🎮 Çalıştırma (Usage)

Uygulamayı başlatmak için:
```bash
python3 main.py
```

İster menüden **Dosya > Medya Aç** diyerek, ister doğrudan dosya ya da klasörü pencereye **sürükleyip bırakarak (Drag & Drop)** kullanmaya başlayabilirsiniz.

---

## ⌨️ Klavye Kısayolları (Shortcuts)

| Tuş / Kısayol | İşlev |
|:---|:---|
| `Space` | Oynat / Duraklat (veya sonraki resme geç) |
| `F` / `F11` | Tam Ekran (Fullscreen) Aç / Kapat |
| `Esc` | Tam Ekrandan Çık |
| `Sol / Sağ Ok` | 5 saniye geri / ileri sar |
| `Yukarı / Aşağı Ok` | Ses artır / azalt |
| `M` | Sesi Aç / Kapat (Mute) |
| `R` | Son kalınan noktadan devam et (Resume) |
| `Alt + R` | 90° Sağa Döndür |
| `S` | Ekran Görüntüsü Al |
| `Ctrl + O` | Dosya Aç |
| `Ctrl + Shift + O` | Klasör Aç |

---

## 📁 Proje Yapısı (Project Structure)

```text
├── main.py              # Uygulama başlangıç noktası & çevre değişkenleri
├── player.py            # Ana VideoPlayer sınıfı & medya döngü mantığı
├── player_ui.py         # Kullanıcı arayüzü bileşenleri, menüler & drawer
├── player_settings.py   # Görsel efektler & ayarlar yan paneli
├── player_widgets.py    # Özel bileşenler (VideoPreviewWorker, JumpSlider, Zoom/Pan view)
├── requirements.txt     # Python paket bağımlılıkları
├── index.html           # Alternatif web oynatıcı demosu
├── style.css            # Web arayüzü stilleri
└── script.js            # Web oynatıcı mantığı
```

---

## 📄 Lisans
Bu proje açık kaynaklıdır ve MIT Lisansı kapsamında sunulmaktadır.
