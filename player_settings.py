from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGroupBox, QSlider
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QTransform, QPainter
from PyQt6.QtWidgets import (
    QGraphicsBlurEffect, QGraphicsColorizeEffect,
    QGraphicsOpacityEffect, QGraphicsDropShadowEffect
)

from player_widgets import SharpenEffect, _NUMPY_AVAILABLE

class PlayerSettingsMixin:
    """VideoPlayer için sağ taraf ayarlar panelini oluşturan ve yöneten Mixin"""

    def create_settings_panel(self):
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
        content = QWidget() if hasattr(self, 'QWidget') else None # Düzeltme: QWidget importunu mixinleri birleştiren dosyadan veya buradan yapacağız. Aşağıda halledeceğiz.
        
        # QWidget import on demand since it's commonly used here
        from PyQt6.QtWidgets import QWidget
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

        # 1. Netlik / Bulanıklık
        self._sharpen_effect = None
        self.blur_effect = None

        def apply_sharpness(v):
            self.video_item.setGraphicsEffect(None)
            self._sharpen_effect = None
            self.blur_effect = None
            if v < 0:
                eff = SharpenEffect()
                eff.set_strength(-v)
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

        if not _NUMPY_AVAILABLE:
            warn = QLabel("⚠ numpy yüklü değil — netlik efekti devre dışı.\n  pip install numpy ile kurun.")
            warn.setStyleSheet("color: #f85149; font-size: 10px;")
            warn.setWordWrap(True)
            layout.addWidget(warn)

        self.blur_slider = self.sharp_slider

        # 2. Saydamlık (Opaklık)
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(1.0)
        def apply_opacity(v):
            self.video_item.setOpacity(v / 100.0)
        box, self.opacity_slider = make_slider_row("🫙 Saydamlık", 10, 100, 100, apply_opacity)
        layout.addWidget(box)

        # 3. Yakınlaştırma / Zoom
        def apply_zoom(v):
            factor = v / 100.0
            self.video_item.resetTransform()
            rect = self.video_item.boundingRect()
            self.video_item.setTransformOriginPoint(rect.width()/2, rect.height()/2)
            self.video_item.setScale(factor)
        box, self.zoom_slider = make_slider_row("🔎 Zoom", 50, 300, 100, apply_zoom)
        layout.addWidget(box)

        # 4. Döndürme
        def apply_rotation(v):
            rect = self.video_item.boundingRect()
            self.video_item.setTransformOriginPoint(rect.width()/2, rect.height()/2)
            self.video_item.setRotation(v)
            self.rotation_angle = v
        box, self.rotation_slider = make_slider_row("🔄 Döndürme (°)", -180, 180, 0, apply_rotation)
        layout.addWidget(box)

        # 5. Oynatma Hızı
        def apply_speed(v):
            speed = v / 100.0
            self.media_player.setPlaybackRate(speed)
            self.speed_label.setText(f"⚡{speed:.2f}x")
        box, self.speed_slider = make_slider_row("⚡ Oynatma Hızı (×100)", 25, 400, 100, apply_speed)
        layout.addWidget(box)

        # 6. Ses Seviyesi
        def apply_volume_panel(v):
            self.audio_output.setVolume(v / 100.0)
            self.volume_level = v / 100.0
        box, self.vol_slider_panel = make_slider_row("🔊 Ses Seviyesi", 0, 150, 100, apply_volume_panel)
        layout.addWidget(box)

        # Toggle butonları
        toggle_box = QGroupBox("🎨 Görsel Efektler")
        tl = QVBoxLayout(toggle_box)
        tl.setContentsMargins(8, 4, 8, 8)
        tl.setSpacing(6)

        # 7. Gri Ton
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

        # 8. Renk Tonu (Warm/Cool)
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

        # 9. Yatay / Dikey Ayna
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

        # 10. Renk Yoğunluğu (Colorize Strength)
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

        # 11. Gölge Efekti
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

        # Sıfırla butonu
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

    def show_video_settings(self):
        """Video ayarları panelini aç/kapat"""
        visible = not self.settings_panel.isVisible()
        self.settings_panel.setVisible(visible)
        if visible:
            self.splitter.setSizes([900, 280])
        self.statusBar().showMessage("Video ayarları " + ("açıldı" if visible else "kapatıldı"), 1500)
