import sys
import os
import subprocess
import json
from pathlib import Path

# Ses çıkışını Bluetooth kulaklığa zorla
try:
    sinks_out = subprocess.check_output(["pactl", "list", "short", "sinks"]).decode()
    bt_sink = [b.split()[1] for b in sinks_out.splitlines() if "bluez_output" in b]
    if bt_sink:
        os.environ["PIPEWIRE_NODE"] = bt_sink[0]
        os.environ["PULSE_SINK"] = bt_sink[0]
except Exception:
    pass

# FFmpeg Vulkan sorunlarını engelle
os.environ["VK_ICD_FILENAMES"] = ""

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QSlider, QFileDialog, QLabel, QGraphicsView, QGraphicsScene,
    QSizePolicy, QComboBox, QMessageBox, QProgressBar, QFrame, QToolTip,
    QDialog, QSplitter, QScrollArea, QGroupBox
)
from PyQt6.QtWidgets import (
    QGraphicsEffect, QGraphicsBlurEffect, QGraphicsColorizeEffect,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtCore import Qt, QUrl, QRectF, QTimer, QSettings, pyqtSignal
from PyQt6.QtGui import (
    QIcon, QTransform, QWheelEvent, QMouseEvent, QKeySequence,
    QShortcut, QAction, QFont, QPalette, QColor, QPainter
)
from functools import partial

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QImage, QPixmap

class SharpenEffect(QGraphicsEffect):
    """Unsharp mask ile gerçek netlik artırma efekti (numpy tabanlı)."""
    def __init__(self, strength=0):
        super().__init__()
        self._strength = strength  # 1–10

    def set_strength(self, v):
        self._strength = max(0, v)
        self.update()

    def draw(self, painter):
        from PyQt6.QtCore import QPoint
        pixmap, offset = self.sourcePixmap()
        if pixmap.isNull():
            painter.drawPixmap(offset, pixmap)
            return
        if self._strength == 0 or not _NUMPY_AVAILABLE:
            painter.drawPixmap(offset, pixmap)
            return

        img = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        w, h = img.width(), img.height()
        ptr = img.bits()
        ptr.setsize(h * w * 4)
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w, 4)).copy()

        # Unsharp mask: sharpened = original + strength * (original - gaussian_blur)
        flt = arr[:, :, :3].astype(np.float32)
        # Simple 3x3 gaussian blur via separable filter
        k = np.array([0.25, 0.5, 0.25], dtype=np.float32)
        blurred = np.apply_along_axis(
            lambda x: np.convolve(x, k, mode='same'), axis=0,
            arr=np.apply_along_axis(lambda x: np.convolve(x, k, mode='same'), axis=1, arr=flt)
        )
        strength = self._strength * 0.4  # max ~4.0
        sharpened = flt + strength * (flt - blurred)
        arr[:, :, :3] = np.clip(sharpened, 0, 255).astype(np.uint8)

        result = QImage(arr.tobytes(), w, h, w * 4, QImage.Format.Format_ARGB32)
        painter.drawImage(offset, result)



class JumpSlider(QSlider):
    """Tıklanan yere atlayan slider"""
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(self.value())
        super().mousePressEvent(event)

class CustomGraphicsView(QGraphicsView):
    """Zoom ve pan desteği olan graphics view"""
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setOptimizationFlags(QGraphicsView.OptimizationFlag.DontSavePainterState)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.zoom_factor = 1.0
        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
        
    def wheelEvent(self, event: QWheelEvent):
        # Orta tuş kaymasıyla zoom (Ctrl gereksinimi kaldırıldı)
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        event.accept()

    def zoom_in(self):
        self.scale(1.2, 1.2)
        self.zoom_factor *= 1.2

    def zoom_out(self):
        if self.zoom_factor > 0.2:
            self.scale(1 / 1.2, 1 / 1.2)
            self.zoom_factor /= 1.2

    def reset_zoom(self):
        self.setTransform(QTransform())
        self.zoom_factor = 1.0
        self.fitInView(self.scene().items()[0], Qt.AspectRatioMode.KeepAspectRatio)

class VideoPlayer(QMainWindow):
    """Ana video oynatıcı sınıfı"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Premium Video Oynatıcı - Gelişmiş Sürüm")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(800, 600)
        
        # Ayarlar
        self.settings = QSettings('VideoPlayer', 'Settings')
        self.load_settings()
        
        # Media Player
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
        self.audio_output.setVolume(self.volume_level)
        self.media_player.setAudioOutput(self.audio_output)
        
        # Video item
        self.video_item = QGraphicsVideoItem()
        self.scene = QGraphicsScene(self)
        self.scene.addItem(self.video_item)
        self.graphics_view = CustomGraphicsView(self.scene)
        self.media_player.setVideoOutput(self.video_item)
        
        # Değişkenler
        self.is_slider_pressed = False
        self.is_fullscreen = False
        self.playlist = []
        self.current_playlist_index = -1
        self.subtitle_tracks = []
        self.current_subtitle_index = -1
        self.rotation_angle = 0
        self.brightness = 100
        self.contrast = 100
        self.saturation = 100
        self.sharpness = 0
        
        # UI oluştur
        self.init_ui()
        self.create_shortcuts()
        self.setup_stylesheet()
        
        # Sinyaller
        self.media_player.errorOccurred.connect(self.handle_error)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.playbackStateChanged.connect(self.playback_state_changed)
        self.video_item.nativeSizeChanged.connect(self.video_size_changed)
        
        # Cihaz listesi
        self.system_devices = QMediaDevices(self)
        self.system_devices.audioOutputsChanged.connect(self.refresh_audio_devices_list)
        self.refresh_audio_devices_list()
        
        # Otomatik kaydetme için timer
        self.save_timer = QTimer()
        self.save_timer.timeout.connect(self.save_current_position)
        self.save_timer.start(30000)  # Her 30 saniyede bir kaydet
        
    def init_ui(self):
        """Kullanıcı arayüzünü oluştur"""
        # Merkez widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Menü çubuğu
        self.create_menu_bar()

        # Video + Ayarlar paneli (yatay splitter)
        from PyQt6.QtWidgets import QSplitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: rgba(255, 255, 255, 0.1); width: 1px; }")
        self.splitter.addWidget(self.graphics_view)

        # Gömülü ayarlar paneli
        self.settings_panel = self.create_settings_panel()
        self.settings_panel.setVisible(False)
        self.splitter.addWidget(self.settings_panel)
        self.splitter.setSizes([1200, 300])

        main_layout.addWidget(self.splitter, stretch=1)

        # Kontrol paneli
        controls_panel = self.create_controls_panel()
        main_layout.addWidget(controls_panel)

        # Durum çubuğu
        self.statusBar().showMessage("Hazır")
        self.statusBar().setStyleSheet("QStatusBar { background-color: #0f172a; color: #94a3b8; border-top: 1px solid rgba(255, 255, 255, 0.1); font-family: 'JetBrains Mono'; }")

        central_widget.setLayout(main_layout)

    def create_settings_panel(self):
        """Sağ taraf gömülü ayarlar paneli"""
        from PyQt6.QtWidgets import QScrollArea, QGroupBox
        
        panel = QFrame()
        panel.setFixedWidth(280)
        panel.setStyleSheet("""
            QFrame { background-color: #0f172a; border-left: 1px solid rgba(255, 255, 255, 0.1); }
            QLabel { color: #f8fafc; font-size: 12px; font-family: 'Inter'; }
            QGroupBox { color: #cbd5e1; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px;
                        margin-top: 12px; padding-top: 16px; font-size: 12px; font-family: 'Inter'; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 6px; }
            QSlider::groove:horizontal { height: 6px; background: rgba(255, 255, 255, 0.15); border-radius: 3px; }
            QSlider::handle:horizontal { background: #6366f1; width: 16px; height: 16px;
                                         margin: -5px 0; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #818cf8; }
            QSlider::sub-page:horizontal { background: #6366f1; border-radius: 3px; }
            QPushButton { background-color: rgba(255, 255, 255, 0.05); color: #cbd5e1; border: 1px solid transparent;
                          border-radius: 6px; padding: 6px 12px; font-size: 12px; font-family: 'Inter'; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); color: #f8fafc; border-color: rgba(255, 255, 255, 0.2); }
            QPushButton:checked { background-color: rgba(99, 102, 241, 0.15); color: #818cf8; border-color: rgba(99, 102, 241, 0.3); }
        """)

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Başlık
        title_bar = QFrame()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("QFrame { background-color: rgba(15, 23, 42, 0.8); border-bottom: 1px solid rgba(255, 255, 255, 0.1); }")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 8, 0)
        title_lbl = QLabel("⚙️  Video Ayarları")
        title_lbl.setStyleSheet("color: #f8fafc; font-weight: 600; font-size: 13px; font-family: 'Inter';")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #94a3b8; font-size: 14px; } QPushButton:hover { color: #ef4444; }")
        close_btn.clicked.connect(lambda: self.settings_panel.setVisible(False))
        title_layout.addWidget(title_lbl)
        title_layout.addStretch()
        title_layout.addWidget(close_btn)
        outer.addWidget(title_bar)

        # Scrollable içerik
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        content = QWidget()
        content.setStyleSheet("QWidget { background: transparent; }")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        def make_slider_row(name, min_v, max_v, default, callback):
            box = QGroupBox(name)
            bl = QVBoxLayout(box)
            bl.setContentsMargins(8, 4, 8, 8)
            row = QHBoxLayout()
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(min_v, max_v)
            sl.setValue(default)
            val_lbl = QLabel(f"{default}")
            val_lbl.setFixedWidth(32)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            sl.valueChanged.connect(lambda v: (val_lbl.setText(str(v)), callback(v)))
            row.addWidget(sl)
            row.addWidget(val_lbl)
            bl.addLayout(row)
            return box, sl

        # ── 1. Netlik / Bulanıklık ──
        self._sharpen_effect = None
        self.blur_effect = None

        def apply_sharpness(v):
            """v < 0 → keskinlik artırma, v > 0 → bulanıklık"""
            self.video_item.setGraphicsEffect(None)
            self._sharpen_effect = None
            self.blur_effect = None
            if v < 0:
                eff = SharpenEffect()
                eff.set_strength(-v)  # 1–30
                self._sharpen_effect = eff
                self.video_item.setGraphicsEffect(eff)
            elif v > 0:
                eff = QGraphicsBlurEffect()
                eff.setBlurRadius(v)
                self.blur_effect = eff
                self.video_item.setGraphicsEffect(eff)

        sharp_box = QGroupBox("🔬 Netlik / Bulanıklık")
        sbl = QVBoxLayout(sharp_box)
        sbl.setContentsMargins(8, 4, 8, 10)
        hint_lbl = QLabel("◀ Daha Keskin  ──────  Daha Bulanık ▶")
        hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_lbl.setStyleSheet("font-size: 10px; color: #8b949e;")
        sharp_row = QHBoxLayout()
        self.sharp_slider = QSlider(Qt.Orientation.Horizontal)
        self.sharp_slider.setRange(-30, 30)
        self.sharp_slider.setValue(0)
        self.sharp_val_lbl = QLabel("0")
        self.sharp_val_lbl.setFixedWidth(28)
        self.sharp_val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.sharp_slider.valueChanged.connect(lambda v: (self.sharp_val_lbl.setText(str(v)), apply_sharpness(v)))
        sharp_row.addWidget(self.sharp_slider)
        sharp_row.addWidget(self.sharp_val_lbl)
        sbl.addWidget(hint_lbl)
        sbl.addLayout(sharp_row)

        # Render kalite butonu
        quality_row = QHBoxLayout()
        hq_btn = QPushButton("⬛ HD Render Kalitesi")
        hq_btn.setCheckable(True)
        hq_btn.setChecked(True)
        def toggle_hq(checked):
            if checked:
                self.graphics_view.setRenderHints(
                    QPainter.RenderHint.Antialiasing |
                    QPainter.RenderHint.SmoothPixmapTransform |
                    QPainter.RenderHint.TextAntialiasing
                )
            else:
                self.graphics_view.setRenderHints(QPainter.RenderHint(0))
        hq_btn.toggled.connect(toggle_hq)
        quality_row.addWidget(hq_btn)
        sbl.addLayout(quality_row)
        layout.addWidget(sharp_box)

        # numpy durumu etiketi
        if not _NUMPY_AVAILABLE:
            warn = QLabel("⚠ numpy yüklü değil — netlik efekti devre dışı.\n  pip install numpy ile kurun.")
            warn.setStyleSheet("color: #f85149; font-size: 10px;")
            warn.setWordWrap(True)
            layout.addWidget(warn)

        self.blur_slider = self.sharp_slider  # reset_video_settings için alias


        # ── 2. Saydamlık (Opaklık) ──
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(1.0)
        def apply_opacity(v):
            self.video_item.setOpacity(v / 100.0)
        box, self.opacity_slider = make_slider_row("🫙 Saydamlık", 10, 100, 100, apply_opacity)
        layout.addWidget(box)

        # ── 3. Yakınlaştırma / Zoom ──
        def apply_zoom(v):
            factor = v / 100.0
            self.video_item.resetTransform()
            rect = self.video_item.boundingRect()
            self.video_item.setTransformOriginPoint(rect.width()/2, rect.height()/2)
            self.video_item.setScale(factor)
        box, self.zoom_slider = make_slider_row("🔎 Zoom", 50, 300, 100, apply_zoom)
        layout.addWidget(box)

        # ── 4. Döndürme ──
        def apply_rotation(v):
            rect = self.video_item.boundingRect()
            self.video_item.setTransformOriginPoint(rect.width()/2, rect.height()/2)
            self.video_item.setRotation(v)
            self.rotation_angle = v
        box, self.rotation_slider = make_slider_row("🔄 Döndürme (°)", -180, 180, 0, apply_rotation)
        layout.addWidget(box)

        # ── 5. Oynatma Hızı ──
        def apply_speed(v):
            speed = v / 100.0
            self.media_player.setPlaybackRate(speed)
            self.speed_label.setText(f"⚡{speed:.2f}x")
        box, self.speed_slider = make_slider_row("⚡ Oynatma Hızı (×100)", 25, 400, 100, apply_speed)
        layout.addWidget(box)

        # ── 6. Ses Seviyesi ──
        def apply_volume_panel(v):
            self.audio_output.setVolume(v / 100.0)
            self.volume_level = v / 100.0
        box, self.vol_slider_panel = make_slider_row("🔊 Ses Seviyesi", 0, 150, 100, apply_volume_panel)
        layout.addWidget(box)

        # ── Toggle butonları ──
        toggle_box = QGroupBox("🎨 Görsel Efektler")
        tl = QVBoxLayout(toggle_box)
        tl.setContentsMargins(8, 4, 8, 8)
        tl.setSpacing(6)

        # ── 7. Gri Ton ──
        self.grayscale_btn = QPushButton("⬛ Gri Ton")
        self.grayscale_btn.setCheckable(True)
        self._grayscale_effect = None
        def toggle_grayscale(checked):
            if checked:
                eff = QGraphicsColorizeEffect()
                eff.setColor(QColor(128, 128, 128))
                eff.setStrength(1.0)
                self._grayscale_effect = eff
                self.video_item.setGraphicsEffect(eff)
            else:
                self.video_item.setGraphicsEffect(None)
                self._grayscale_effect = None
        self.grayscale_btn.toggled.connect(toggle_grayscale)
        tl.addWidget(self.grayscale_btn)

        # ── 8. Renk Tonu (Warm/Cool) ──
        tint_row = QHBoxLayout()
        warm_btn = QPushButton("🟠 Sıcak")
        cool_btn = QPushButton("🔵 Soğuk")
        normal_tint_btn = QPushButton("⚪ Normal")
        def set_tint(color):
            eff = QGraphicsColorizeEffect()
            eff.setColor(color)
            eff.setStrength(0.3)
            self.video_item.setGraphicsEffect(eff)
        def clear_tint():
            self.video_item.setGraphicsEffect(None)
        warm_btn.clicked.connect(lambda: set_tint(QColor(255, 160, 80)))
        cool_btn.clicked.connect(lambda: set_tint(QColor(80, 160, 255)))
        normal_tint_btn.clicked.connect(clear_tint)
        tint_row.addWidget(warm_btn)
        tint_row.addWidget(cool_btn)
        tint_row.addWidget(normal_tint_btn)
        tl.addLayout(tint_row)

        # ── 9. Yatay / Dikey Ayna ──
        flip_row = QHBoxLayout()
        self.flip_h = False
        self.flip_v = False
        def update_flip():
            t = QTransform()
            t.scale(-1 if self.flip_h else 1, -1 if self.flip_v else 1)
            rect = self.video_item.boundingRect()
            if self.flip_h:
                t = QTransform().translate(rect.width(), 0).scale(-1, 1)
            if self.flip_v:
                t2 = QTransform().translate(0, rect.height()).scale(1, -1)
                t = t * t2
            self.video_item.setTransform(t)
        flip_h_btn = QPushButton("↔ Yatay Ayna")
        flip_h_btn.setCheckable(True)
        flip_v_btn = QPushButton("↕ Dikey Ayna")
        flip_v_btn.setCheckable(True)
        def toggle_flip_h(c): self.flip_h = c; update_flip()
        def toggle_flip_v(c): self.flip_v = c; update_flip()
        flip_h_btn.toggled.connect(toggle_flip_h)
        flip_v_btn.toggled.connect(toggle_flip_v)
        flip_row.addWidget(flip_h_btn)
        flip_row.addWidget(flip_v_btn)
        tl.addLayout(flip_row)

        layout.addWidget(toggle_box)

        # ── 10. Renk Yoğunluğu (Colorize Strength) ──
        self._color_eff = None
        self._color_target = QColor(255, 100, 100)
        def apply_colorize(v):
            if v == 0:
                self.video_item.setGraphicsEffect(None)
                self._color_eff = None
            else:
                if self._color_eff is None:
                    self._color_eff = QGraphicsColorizeEffect()
                    self._color_eff.setColor(self._color_target)
                    self.video_item.setGraphicsEffect(self._color_eff)
                self._color_eff.setStrength(v / 100.0)
        box, self.colorize_slider = make_slider_row("🎨 Renk Yoğunluğu", 0, 100, 0, apply_colorize)
        layout.addWidget(box)

        # ── 11. Gölge Efekti ──
        self._shadow_eff = None
        def apply_shadow(v):
            if v == 0:
                self.video_item.setGraphicsEffect(None)
                self._shadow_eff = None
            else:
                if self._shadow_eff is None:
                    self._shadow_eff = QGraphicsDropShadowEffect()
                    self._shadow_eff.setColor(QColor(0, 0, 0, 200))
                    self._shadow_eff.setOffset(0, 0)
                    self.video_item.setGraphicsEffect(self._shadow_eff)
                self._shadow_eff.setBlurRadius(v)
        box, self.shadow_slider = make_slider_row("🌑 Gölge / Vinjyet", 0, 60, 0, apply_shadow)
        layout.addWidget(box)

        # ── Sıfırla butonu ──
        layout.addSpacing(8)
        reset_btn = QPushButton("🔄  Tüm Ayarları Sıfırla")
        reset_btn.setStyleSheet("""QPushButton { background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); padding: 10px; border-radius: 8px; font-family: 'Inter'; font-weight: 500; color: #f8fafc; }
                                   QPushButton:hover { background-color: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.3); color: #ef4444; }""")
        reset_btn.clicked.connect(self.reset_video_settings)
        layout.addWidget(reset_btn)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)
        return panel

    def reset_video_settings(self):
        """Tüm ayarları sıfırla"""
        self.video_item.setGraphicsEffect(None)
        self.video_item.setOpacity(1.0)
        self.video_item.setRotation(0)
        self.video_item.setScale(1.0)
        self.video_item.setTransform(QTransform())
        self.rotation_angle = 0
        self.media_player.setPlaybackRate(1.0)
        self.speed_label.setText("⚡1.00x")
        self.blur_effect = None
        self._grayscale_effect = None
        self._color_eff = None
        self._shadow_eff = None
        self.flip_h = False
        self.flip_v = False
        # Slider'ları sıfırla
        for sl, default in [
            (self.blur_slider, 0), (self.opacity_slider, 100),
            (self.zoom_slider, 100), (self.rotation_slider, 0),
            (self.speed_slider, 100), (self.colorize_slider, 0),
            (self.shadow_slider, 0),
        ]:
            sl.blockSignals(True)
            sl.setValue(default)
            sl.blockSignals(False)
        self.statusBar().showMessage("Tüm ayarlar sıfırlandı", 2000)


    def create_menu_bar(self):
        """Menü çubuğunu oluştur"""
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar { background-color: #0f172a; color: #f8fafc; border-bottom: 1px solid rgba(255, 255, 255, 0.1); font-family: 'Inter'; font-size: 12px; }
            QMenuBar::item { padding: 6px 10px; border-radius: 4px; margin-left: 4px; }
            QMenuBar::item:selected { background-color: rgba(255, 255, 255, 0.1); }
            QMenu { background-color: #0f172a; color: #f8fafc; border: 1px solid rgba(255, 255, 255, 0.1); font-family: 'Inter'; font-size: 12px; padding: 4px; }
            QMenu::item { padding: 6px 20px 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #6366f1; }
        """)
        
        # Dosya menüsü
        file_menu = menubar.addMenu("📁 Dosya")
        
        open_action = QAction("🎬 Video Aç", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        open_folder_action = QAction("📂 Klasör Aç", self)
        open_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)
        
        file_menu.addSeparator()
        
        load_subtitle_action = QAction("📝 Altyazı Yükle", self)
        load_subtitle_action.setShortcut(QKeySequence("Ctrl+L"))
        load_subtitle_action.triggered.connect(self.load_subtitle)
        file_menu.addAction(load_subtitle_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("🚪 Çıkış", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Görünüm menüsü
        view_menu = menubar.addMenu("👁️ Görünüm")
        
        fullscreen_action = QAction("🖥️ Tam Ekran", self)
        fullscreen_action.setShortcut(QKeySequence("F11"))
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        view_menu.addSeparator()
        
        rotate_cw_action = QAction("🔄 Sağa Döndür (Alt+R)", self)
        rotate_cw_action.setShortcut(QKeySequence("Alt+R"))
        rotate_cw_action.triggered.connect(lambda: self.rotate_video(90))
        view_menu.addAction(rotate_cw_action)
        
        rotate_ccw_action = QAction("🔄 Sola Döndür (Alt+L)", self)
        rotate_ccw_action.setShortcut(QKeySequence("Alt+L"))
        rotate_ccw_action.triggered.connect(lambda: self.rotate_video(-90))
        view_menu.addAction(rotate_ccw_action)
        
        view_menu.addSeparator()
        
        video_settings_action = QAction("⚙️ Video Ayarları", self)
        video_settings_action.triggered.connect(self.show_video_settings)
        view_menu.addAction(video_settings_action)
        
        view_menu.addSeparator()
        
        zoom_in_action = QAction("🔍 Yakınlaştır (+)", self)
        zoom_in_action.setShortcut(QKeySequence("Ctrl++"))
        zoom_in_action.triggered.connect(self.graphics_view.zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction("🔍 Uzaklaştır (-)", self)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self.graphics_view.zoom_out)
        view_menu.addAction(zoom_out_action)
        
        reset_zoom_action = QAction("🔄 Sıfırla", self)
        reset_zoom_action.setShortcut(QKeySequence("Ctrl+0"))
        reset_zoom_action.triggered.connect(self.graphics_view.reset_zoom)
        view_menu.addAction(reset_zoom_action)
        
        # Oynatma menüsü
        play_menu = menubar.addMenu("▶ Oynatma")
        
        prev_action = QAction("⏮ Önceki", self)
        prev_action.setShortcut(QKeySequence("Ctrl+Left"))
        prev_action.triggered.connect(self.previous_video)
        play_menu.addAction(prev_action)
        
        next_action = QAction("⏭ Sonraki", self)
        next_action.setShortcut(QKeySequence("Ctrl+Right"))
        next_action.triggered.connect(self.next_video)
        play_menu.addAction(next_action)
        
        play_menu.addSeparator()
        
        speed_menu = play_menu.addMenu("⚡ Oynatma Hızı")
        speeds = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
        for speed in speeds:
            action = QAction(f"{speed}x", self)
            action.triggered.connect(partial(self.set_playback_speed, speed))
            speed_menu.addAction(action)
        
        # Yardım menüsü
        help_menu = menubar.addMenu("❓ Yardım")
        
        about_action = QAction("ℹ️ Hakkında", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        shortcuts_action = QAction("⌨️ Kısayollar", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
    def create_controls_panel(self):
        """Kontrol panelini oluştur"""
        controls_panel = QFrame()
        controls_panel.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)
        
        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(15, 10, 15, 15)
        controls_layout.setSpacing(10)
        
        # Progress bar ve zaman
        progress_layout = QHBoxLayout()
        self.position_slider = JumpSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.position_slider.sliderPressed.connect(self.slider_pressed)
        self.position_slider.sliderReleased.connect(self.slider_released)
        self.position_slider.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self.time_label = QLabel("00:00:00 / 00:00:00")
        self.time_label.setMinimumWidth(150)
        
        progress_layout.addWidget(self.position_slider)
        progress_layout.addWidget(self.time_label)
        controls_layout.addLayout(progress_layout)
        
        # Butonlar
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        # Aç butonu
        self.open_button = QPushButton("📂 Aç")
        self.open_button.clicked.connect(self.open_file)
        self.open_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 8px 16px;
                font-family: 'Inter';
                font-weight: 600;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.3); }
        """)
        buttons_layout.addWidget(self.open_button)
        
        # Önceki video
        self.prev_button = QPushButton("⏮")
        self.prev_button.clicked.connect(self.previous_video)
        self.prev_button.setToolTip("Önceki video (Ctrl+Sol)")
        buttons_layout.addWidget(self.prev_button)
        
        # Geri sar
        self.rewind_button = QPushButton("⏪ 10s")
        self.rewind_button.clicked.connect(lambda: self.seek_relative(-10))
        buttons_layout.addWidget(self.rewind_button)
        
        # Oynat/Duraklat
        self.play_button = QPushButton("▶")
        self.play_button.setFixedSize(40, 40)
        self.play_button.clicked.connect(self.play_video)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #6366f1;
                color: white;
                border: none;
                border-radius: 20px;
                font-size: 16px;
            }
            QPushButton:hover { background-color: #818cf8; }
        """)
        buttons_layout.addWidget(self.play_button)
        
        # İleri sar
        self.forward_button = QPushButton("30s ⏩")
        self.forward_button.clicked.connect(lambda: self.seek_relative(30))
        buttons_layout.addWidget(self.forward_button)
        
        # Sonraki video
        self.next_button = QPushButton("⏭")
        self.next_button.clicked.connect(self.next_video)
        self.next_button.setToolTip("Sonraki video (Ctrl+Sağ)")
        buttons_layout.addWidget(self.next_button)
        
        buttons_layout.addSpacing(10)
        
        # Ses kontrolü
        self.volume_button = QPushButton("🔊")
        self.volume_button.setFixedWidth(40)
        self.volume_button.clicked.connect(self.toggle_mute)
        buttons_layout.addWidget(self.volume_button)
        
        self.volume_slider = JumpSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.volume_level * 100))
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.set_volume)
        buttons_layout.addWidget(self.volume_slider)
        
        # Ses cihazı seçici
        self.audio_combo = QComboBox()
        self.audio_combo.setMinimumWidth(200)
        self.audio_combo.currentIndexChanged.connect(self.change_audio_device)
        buttons_layout.addWidget(self.audio_combo)
        
        # Altyazı seçici
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.setMinimumWidth(150)
        self.subtitle_combo.addItem("Altyazı Yok")
        self.subtitle_combo.currentIndexChanged.connect(self.change_subtitle)
        buttons_layout.addWidget(self.subtitle_combo)
        
        buttons_layout.addStretch()
        
        # Oynatma hızı
        self.speed_label = QLabel("1.0x")
        self.speed_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.speed_label.mousePressEvent = self.show_speed_menu
        buttons_layout.addWidget(self.speed_label)
        
        buttons_layout.addSpacing(10)
        
        # Zoom kontrolü
        self.zoom_out_btn = QPushButton("🔍-")
        self.zoom_out_btn.clicked.connect(self.graphics_view.zoom_out)
        self.zoom_out_btn.setToolTip("Uzaklaştır (Ctrl+-)")
        buttons_layout.addWidget(self.zoom_out_btn)
        
        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.clicked.connect(self.graphics_view.zoom_in)
        self.zoom_in_btn.setToolTip("Yakınlaştır (Ctrl++)")
        buttons_layout.addWidget(self.zoom_in_btn)
        
        self.zoom_reset_btn = QPushButton("🔄")
        self.zoom_reset_btn.clicked.connect(self.graphics_view.reset_zoom)
        self.zoom_reset_btn.setToolTip("Zoom'u sıfırla (Ctrl+0)")
        buttons_layout.addWidget(self.zoom_reset_btn)
        
        # Tam ekran butonu
        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setFixedWidth(40)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_btn.setToolTip("Tam ekran (F11)")
        buttons_layout.addWidget(self.fullscreen_btn)
        
        controls_layout.addLayout(buttons_layout)
        controls_panel.setLayout(controls_layout)
        
        return controls_panel
        
    def create_shortcuts(self):
        """Klavye kısayollarını oluştur"""
        shortcuts = {
            'Space': self.play_video,
            'Right': lambda: self.seek_relative(30),
            'Left': lambda: self.seek_relative(-10),
            'Up': lambda: self.volume_slider.setValue(min(100, self.volume_slider.value() + 5)),
            'Down': lambda: self.volume_slider.setValue(max(0, self.volume_slider.value() - 5)),
            'M': self.toggle_mute,
            'F': self.toggle_fullscreen,
            'Ctrl+Left': self.previous_video,
            'Ctrl+Right': self.next_video,
            'Ctrl+Up': lambda: self.set_playback_speed(self.media_player.playbackRate() + 0.1),
            'Ctrl+Down': lambda: self.set_playback_speed(max(0.25, self.media_player.playbackRate() - 0.1)),
        }
        
        for key, func in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(func)
            
    def setup_stylesheet(self):
        """Ana stil sayfasını ayarla"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #020617;
            }
            QPushButton {
                background-color: transparent;
                color: #cbd5e1;
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                font-family: 'Inter';
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: #f8fafc;
                border-color: rgba(255, 255, 255, 0.2);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.05);
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: rgba(255, 255, 255, 0.15);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #6366f1;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #818cf8;
            }
            QSlider::sub-page:horizontal {
                background: #6366f1;
                border-radius: 3px;
            }
            QComboBox {
                background-color: rgba(255, 255, 255, 0.05);
                color: #f8fafc;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 6px 12px;
                font-family: 'Inter';
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #cbd5e1;
                margin-right: 8px;
            }
            QLabel {
                color: #cbd5e1;
                font-family: 'Inter';
            }
        """)
        
    def open_file(self):
        """Video dosyası aç"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Video Seç",
            self.settings.value('last_path', ''),
            "Video Dosyaları (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v);;Tüm Dosyalar (*.*)"
        )
        
        if file_name:
            self.settings.setValue('last_path', os.path.dirname(file_name))
            self.playlist = [file_name]
            self.current_playlist_index = 0
            self.load_video(file_name)
            
    def open_folder(self):
        """Klasördeki tüm videoları aç"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Video Klasörü Seç",
            self.settings.value('last_path', '')
        )
        
        if folder:
            self.settings.setValue('last_path', folder)
            video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
            self.playlist = []
            
            for file in Path(folder).iterdir():
                if file.suffix.lower() in video_extensions:
                    self.playlist.append(str(file))
                    
            if self.playlist:
                self.playlist.sort()
                self.current_playlist_index = 0
                self.load_video(self.playlist[0])
                self.statusBar().showMessage(f"{len(self.playlist)} video yüklendi")
                
    def load_video(self, file_path):
        """Videoyu yükle"""
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        self.play_button.setText("⏸")
        self.media_player.play()
        self.set_volume(self.volume_slider.value())
        self.graphics_view.reset_zoom()
        
        # Kaydedilmiş konumu yükle
        saved_position = self.settings.value(f'position_{file_path}', 0, type=int)
        if saved_position > 5000:  # 5 saniyeden fazla ise
            reply = QMessageBox.question(
                self,
                "Devam Et",
                f"Bu videoyu {saved_position//1000} saniye önce izlemiştiniz. Kaldığınız yerden devam etmek ister misiniz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.media_player.setPosition(saved_position)
                
        self.setWindowTitle(f"Premium Video Oynatıcı - {os.path.basename(file_path)}")
        self.statusBar().showMessage(f"Oynatılıyor: {os.path.basename(file_path)}")
        
    def play_video(self):
        """Videoyu oynat/duraklat"""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_button.setText("▶")
        else:
            self.media_player.play()
            self.play_button.setText("⏸")
            
    def previous_video(self):
        """Önceki videoya geç"""
        if self.playlist and self.current_playlist_index > 0:
            self.current_playlist_index -= 1
            self.load_video(self.playlist[self.current_playlist_index])
            
    def next_video(self):
        """Sonraki videoya geç"""
        if self.playlist and self.current_playlist_index < len(self.playlist) - 1:
            self.current_playlist_index += 1
            self.load_video(self.playlist[self.current_playlist_index])
            
    def seek_relative(self, seconds):
        """Belirtilen saniye kadar ileri/geri sar"""
        if self.media_player.duration() > 0:
            new_pos = self.media_player.position() + (seconds * 1000)
            new_pos = max(0, min(new_pos, self.media_player.duration()))
            self.media_player.setPosition(new_pos)
            
    def set_playback_speed(self, speed):
        """Oynatma hızını ayarla"""
        self.media_player.setPlaybackRate(speed)
        self.speed_label.setText(f"{speed}x")
        self.statusBar().showMessage(f"Oynatma hızı: {speed}x", 2000)
        
    def set_volume(self, volume):
        """Ses seviyesini ayarla"""
        self.volume_level = volume / 100.0
        self.audio_output.setVolume(self.volume_level)
        
        # Ses simgesini güncelle
        if volume == 0:
            self.volume_button.setText("🔇")
        elif volume < 30:
            self.volume_button.setText("🔈")
        elif volume < 70:
            self.volume_button.setText("🔉")
        else:
            self.volume_button.setText("🔊")
            
    def toggle_mute(self):
        """Sesi aç/kapa"""
        self.audio_output.setMuted(not self.audio_output.isMuted())
        self.volume_button.setText("🔇" if self.audio_output.isMuted() else "🔊")
        
    def rotate_video(self, angle):
        """Videoyu döndür"""
        self.rotation_angle = (self.rotation_angle + angle) % 360
        
        # Dönüşüm merkezini ayarla
        rect = self.video_item.boundingRect()
        self.video_item.setTransformOriginPoint(rect.width() / 2, rect.height() / 2)
        self.video_item.setRotation(self.rotation_angle)
        
        # Görünümü sığdır
        self.graphics_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)
        self.statusBar().showMessage(f"Döndürüldü: {self.rotation_angle}°", 2000)

    def toggle_fullscreen(self):
        """Tam ekran modunu aç/kapa"""
        if self.is_fullscreen:
            self.showNormal()
            self.menuBar().show()
            self.statusBar().show()
            self.fullscreen_btn.setText("⛶")
        else:
            self.showFullScreen()
            self.menuBar().hide()
            self.statusBar().hide()
            self.fullscreen_btn.setText("✖")
        self.is_fullscreen = not self.is_fullscreen
        
    def load_subtitle(self):
        """Altyazı dosyası yükle"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Altyazı Seç",
            "",
            "Altyazı Dosyaları (*.srt *.ass *.ssa *.vtt);;Tüm Dosyalar (*.*)"
        )
        
        if file_name:
            # Not: QMediaPlayer doğrudan altyazı desteği için ek kod gerekli
            # Bu basit bir placeholder
            self.subtitle_tracks.append(file_name)
            self.subtitle_combo.addItem(os.path.basename(file_name))
            self.statusBar().showMessage(f"Altyazı yüklendi: {os.path.basename(file_name)}")
            
    def change_subtitle(self, index):
        """Altyazı değiştir"""
        if index == 0:
            self.current_subtitle_index = -1
            self.statusBar().showMessage("Altyazı kapatıldı", 2000)
        elif index - 1 < len(self.subtitle_tracks):
            self.current_subtitle_index = index - 1
            self.statusBar().showMessage(f"Altyazı: {os.path.basename(self.subtitle_tracks[self.current_subtitle_index])}", 2000)
            
    def refresh_audio_devices_list(self):
        """Ses cihazları listesini yenile"""
        current_id = None
        if self.audio_combo.currentIndex() > 0:
            device = self.audio_combo.itemData(self.audio_combo.currentIndex())
            if device:
                current_id = device.id()
                
        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        
        # Sistem varsayılanı
        self.audio_combo.addItem("💻 Sistem Varsayılanı", None)
        
        for device in QMediaDevices.audioOutputs():
            self.audio_combo.addItem(f"🔊 {device.description()}", device)
            if current_id and device.id() == current_id:
                self.audio_combo.setCurrentIndex(self.audio_combo.count() - 1)
                
        self.audio_combo.blockSignals(False)
        
    def change_audio_device(self, index):
        """Ses cihazını değiştir"""
        device = self.audio_combo.itemData(index)
        volume = self.volume_slider.value() / 100.0
        
        if index == 0 or not device:
            self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
        else:
            self.audio_output.setDevice(device)
            
        self.audio_output.setVolume(volume)
        self.statusBar().showMessage(f"Ses cihazı değiştirildi", 2000)
        
    def show_speed_menu(self, event):
        """Oynatma hızı menüsünü göster"""
        menu = self.speed_label.parent().contextMenu()
        if not menu:
            from PyQt6.QtWidgets import QMenu
            menu = QMenu()
            speeds = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
            for speed in speeds:
                action = menu.addAction(f"{speed}x")
                action.triggered.connect(partial(self.set_playback_speed, speed))
        menu.exec(self.speed_label.mapToGlobal(event.pos()))
        
    def save_current_position(self):
        """Geçerli videonun konumunu kaydet"""
        if self.media_player.source().isLocalFile():
            file_path = self.media_player.source().toLocalFile()
            position = self.media_player.position()
            if position > 5000:  # 5 saniyeden fazla ise kaydet
                self.settings.setValue(f'position_{file_path}', position)
                
    def load_settings(self):
        """Ayarları yükle"""
        self.volume_level = self.settings.value('volume', 1.0, type=float)
        self.last_window_geometry = self.settings.value('geometry', None)
        if self.last_window_geometry:
            self.restoreGeometry(self.last_window_geometry)
            
    def save_settings(self):
        """Ayarları kaydet"""
        self.settings.setValue('volume', self.volume_level)
        self.settings.setValue('geometry', self.saveGeometry())
        
    def video_size_changed(self, size):
        """Video boyutu değiştiğinde"""
        if size.isValid():
            self.video_item.setSize(size)
            self.scene.setSceneRect(QRectF(0, 0, size.width(), size.height()))
            self.graphics_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)
            
    def position_changed(self, position):
        """Video konumu değiştiğinde"""
        if not self.is_slider_pressed:
            self.position_slider.setValue(position)
        self.update_time_label(position, self.media_player.duration())
        
    def duration_changed(self, duration):
        """Video süresi değiştiğinde"""
        self.position_slider.setRange(0, duration)
        
    def playback_state_changed(self, state):
        """Oynatma durumu değiştiğinde"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setText("⏸")
        else:
            self.play_button.setText("▶")
            
    def slider_pressed(self):
        """Slider'a basıldığında"""
        self.is_slider_pressed = True
        
    def slider_released(self):
        """Slider bırakıldığında"""
        self.is_slider_pressed = False
        self.media_player.setPosition(self.position_slider.value())
        
    def set_position(self, position):
        """Video konumunu ayarla"""
        self.media_player.setPosition(position)
        
    def update_time_label(self, current_ms, total_ms):
        """Zaman etiketini güncelle"""
        def format_time(ms):
            seconds = ms // 1000
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60
            if hours > 0:
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            return f"{minutes:02d}:{seconds:02d}"
            
        self.time_label.setText(f"{format_time(current_ms)} / {format_time(total_ms)}")
        
    def handle_error(self):
        """Hata durumunu işle"""
        error_string = self.media_player.errorString()
        if error_string:
            self.statusBar().showMessage(f"Hata: {error_string}", 5000)
            print(f"Media Player Error: {error_string}")

    def show_video_settings(self):
        """Video ayarları panelini aç/kapat"""
        visible = not self.settings_panel.isVisible()
        self.settings_panel.setVisible(visible)
        if visible:
            self.splitter.setSizes([900, 280])
        self.statusBar().showMessage("Video ayarları " + ("açıldı" if visible else "kapatıldı"), 1500)

    def show_about(self):
        """Hakkında penceresini göster"""
        QMessageBox.about(
            self,
            "Hakkında",
            "Premium Video Oynatıcı\n\n"
            "Sürüm: 2.0\n\n"
            "Özellikler:\n"
            "• Donanım hızlandırmalı video oynatma\n"
            "• Zoom ve pan desteği\n"
            "• Altyazı desteği (SRT, ASS)\n"
            "• Oynatma listesi\n"
            "• Oynatma hızı kontrolü\n"
            "• Tam ekran modu\n"
            "• Kaldığınız yerden devam etme\n\n"
            "Geliştirilmiş Python ile PyQt6 kullanılarak yapılmıştır.")

    def show_shortcuts(self):
        """Kısayol penceresini göster"""
        shortcuts_text = """
        <h3>Klavye Kısayolları</h3>
        <table style="width:100%">
        <tr><td><b>Boşluk</b></td><td>Oynat/Duraklat</td></tr>
        <tr><td><b>Sol Ok</b></td><td>10 saniye geri sar</td></tr>
        <tr><td><b>Sağ Ok</b></td><td>30 saniye ileri sar</td></tr>
        <tr><td><b>Yukarı Ok</b></td><td>Sesi artır</td></tr>
        <tr><td><b>Aşağı Ok</b></td><td>Sesi azalt</td></tr>
        <tr><td><b>M</b></td><td>Sesi aç/kapa</td></tr>
        <tr><td><b>F / F11</b></td><td>Tam ekran</td></tr>
        <tr><td><b>Alt+R</b></td><td>Sağa döndür</td></tr>
        <tr><td><b>Alt+L</b></td><td>Sola döndür</td></tr>
        <tr><td><b>Ctrl+Sol</b></td><td>Önceki video</td></tr>
        <tr><td><b>Ctrl+Sağ</b></td><td>Sonraki video</td></tr>
        </table>
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("Klavye Kısayolları")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(shortcuts_text)
        msg.exec()

    def closeEvent(self, event):
        """Pencere kapatıldığında"""
        self.save_current_position()
        self.save_settings()
        event.accept()

    def keyPressEvent(self, event):
        """Klavye olaylarını işle"""
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Pencere boyutu değiştiğinde"""
        super().resizeEvent(event)
        if hasattr(self, 'video_item') and self.video_item.nativeSize().isValid():
            self.graphics_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)





if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("Premium Video Player")
    app.setOrganizationName("VideoPlayer")
    
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec())