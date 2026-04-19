import os
from functools import partial
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QScrollArea, QWidget,
    QLabel, QComboBox, QMessageBox, QMenu, QToolButton
)
from PyQt6.QtCore import Qt, QTimer, QUrl, QSize
from PyQt6.QtGui import QIcon, QPixmap, QAction, QKeySequence

from player_widgets import JumpSlider, ThumbnailWorker

class PlayerUIMixin:
    """VideoPlayer için UI bileşenlerini oluşturan Mixin (Drawer, Kontroller, Menü)"""

    def create_drawer_panel(self):
        """Alt kısımda şeffaf playlist / URL drawer ekranı oluştur."""
        self.drawer_panel = QFrame(self.graphics_view)
        self.drawer_panel.hide()
        self.drawer_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 23, 42, 0.85);
                border-top: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
            }
            QPushButton {
                background-color: rgba(255,255,255,0.05);
                color: white;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px;
                padding: 6px;
                text-align: center;
                font-size: 11px;
                font-family: 'Inter';
            }
            QPushButton:hover {
                background-color: rgba(255,255,255,0.15);
            }
            QLineEdit {
                background-color: rgba(0,0,0,0.3);
                color: white;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 6px;
                padding: 6px 12px;
                font-family: 'Inter';
            }
        """)
        
        main_lyt = QVBoxLayout(self.drawer_panel)
        
        # URL Alanı
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Veya uzaktan URL girin (örn: http://...)")
        
        url_btn = QPushButton("Oynat")
        url_btn.setFixedWidth(80)
        url_btn.clicked.connect(self.play_url)
        
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(url_btn)
        main_lyt.addLayout(url_layout)
        
        # Liste (Scroll Area)
        self.drawer_scroll = QScrollArea()
        self.drawer_scroll.setWidgetResizable(True)
        self.drawer_scroll.setStyleSheet("background: transparent; border: none;")
        self.drawer_scroll.setFixedHeight(120)
        
        self.drawer_container = QWidget()
        self.drawer_container.setStyleSheet("background: transparent;")
        
        self.drawer_flow_layout = QHBoxLayout(self.drawer_container)
        self.drawer_flow_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.drawer_flow_layout.setContentsMargins(0, 0, 0, 0)
        self.drawer_flow_layout.setSpacing(10)
        
        self.drawer_scroll.setWidget(self.drawer_container)
        main_lyt.addWidget(self.drawer_scroll)

    def toggle_drawer(self):
        if self.drawer_panel.isVisible():
            self.drawer_panel.hide()
        else:
            self.update_drawer_geometry()
            self.drawer_panel.show()

    def play_url(self):
        url_str = self.url_input.text().strip()
        if url_str:
            self.media_player.setSource(QUrl(url_str))
            self.play_button.setText("⏸")
            self.media_player.play()
            self.statusBar().showMessage(f"URL Yükleniyor: {url_str}")
            self.setWindowTitle("Premium Video Oynatıcı - URL")

    _DRAWER_BTN_STYLE_NORMAL = """
        QToolButton {
            background-color: rgba(255, 255, 255, 0.05);
            color: #cbd5e1;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 6px;
            text-align: center;
            font-size: 11px;
            font-family: 'Inter';
        }
        QToolButton:hover {
            background-color: rgba(255, 255, 255, 0.14);
            border-color: rgba(255, 255, 255, 0.28);
            color: #f8fafc;
        }
    """
    _DRAWER_BTN_STYLE_ACTIVE = """
        QToolButton {
            background-color: rgba(99, 102, 241, 0.35);
            color: #818cf8;
            border: 1px solid rgba(99, 102, 241, 0.65);
            border-radius: 8px;
            padding: 6px;
            text-align: center;
            font-size: 11px;
            font-family: 'Inter';
            font-weight: bold;
        }
        QToolButton:hover {
            background-color: rgba(99, 102, 241, 0.5);
        }
    """

    def update_drawer_playlist(self):
        if getattr(self, '_thumbnail_worker', None):
            self._thumbnail_worker.cancel()
            self._thumbnail_worker.deleteLater()
            self._thumbnail_worker = None

        self._drawer_buttons = []
        while self.drawer_flow_layout.count():
            item = self.drawer_flow_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        for i, video_path in enumerate(self.playlist):
            is_active = (i == self.current_playlist_index)
            btn = QToolButton()
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            name = os.path.basename(video_path)
            display_name = name if len(name) <= 22 else name[:19] + "..."
            btn.setText(f"🎬\n{display_name}")
            btn.setFixedWidth(150)
            btn.setFixedHeight(105)
            btn.setToolTip(name)
            btn.setStyleSheet(
                self._DRAWER_BTN_STYLE_ACTIVE if is_active
                else self._DRAWER_BTN_STYLE_NORMAL
            )

            def make_loader(checked=False, index=i):
                self.load_video_index(index)

            btn.clicked.connect(make_loader)
            self.drawer_flow_layout.addWidget(btn)
            self._drawer_buttons.append(btn)

        active_idx = self.current_playlist_index
        def _scroll_to_active():
            if 0 <= active_idx < len(self._drawer_buttons):
                try:
                    self.drawer_scroll.ensureWidgetVisible(self._drawer_buttons[active_idx])
                except Exception:
                    pass
        QTimer.singleShot(80, _scroll_to_active)

        self._thumbnail_worker = ThumbnailWorker(self.playlist, self)
        self._thumbnail_worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        self._thumbnail_worker.start()

    def _on_thumbnail_ready(self, index, data):
        if not hasattr(self, '_drawer_buttons') or index >= len(self._drawer_buttons):
            return
        
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            icon = QIcon(pixmap)
            btn = self._drawer_buttons[index]
            btn.setIcon(icon)
            btn.setIconSize(QSize(130, 70))
            new_text = btn.text().replace("🎬\n", "")
            btn.setText(new_text)

    def _refresh_drawer_highlight(self):
        if not hasattr(self, '_drawer_buttons'):
            return
        for i, btn in enumerate(self._drawer_buttons):
            try:
                is_active = (i == self.current_playlist_index)
                btn.setStyleSheet(
                    self._DRAWER_BTN_STYLE_ACTIVE if is_active
                    else self._DRAWER_BTN_STYLE_NORMAL
                )
            except Exception:
                pass

        active_idx = self.current_playlist_index
        def _scroll():
            if hasattr(self, '_drawer_buttons') and 0 <= active_idx < len(self._drawer_buttons):
                try:
                    self.drawer_scroll.ensureWidgetVisible(self._drawer_buttons[active_idx])
                except Exception:
                    pass
        QTimer.singleShot(50, _scroll)

    def load_video_index(self, index):
        if 0 <= index < len(self.playlist):
            self.current_playlist_index = index
            self.load_video(self.playlist[index])
            self._refresh_drawer_highlight()

    def update_drawer_geometry(self):
        if not hasattr(self, 'drawer_panel'):
            return
        w = min(900, self.graphics_view.width() - 40)
        h = 190
        x = (self.graphics_view.width() - w) // 2
        y = self.graphics_view.height() - h - 20
        self.drawer_panel.setGeometry(int(x), int(y), int(w), int(h))

    def create_controls_panel(self):
        controls_panel = QFrame()
        controls_panel.setStyleSheet("""
            QFrame { background-color: #0f172a; border-top: 1px solid rgba(255, 255, 255, 0.1); }
        """)
        
        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(15, 10, 15, 15)
        controls_layout.setSpacing(10)
        
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
        
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        
        self.open_button = QPushButton("📂 Aç")
        self.open_button.clicked.connect(self.open_file)
        self.open_button.setStyleSheet("""
            QPushButton { background-color: transparent; color: #f8fafc; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; padding: 8px 16px; font-family: 'Inter'; font-weight: 600; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.3); }
        """)
        buttons_layout.addWidget(self.open_button)
        
        self.drawer_toggle_btn = QPushButton("🎥 Önerilen")
        self.drawer_toggle_btn.clicked.connect(self.toggle_drawer)
        self.drawer_toggle_btn.setStyleSheet(self.open_button.styleSheet())
        buttons_layout.addWidget(self.drawer_toggle_btn)
        
        self.prev_button = QPushButton("⏮")
        self.prev_button.clicked.connect(self.previous_video)
        buttons_layout.addWidget(self.prev_button)
        
        self.rewind_button = QPushButton("⏪ 10s")
        self.rewind_button.clicked.connect(lambda: self.seek_relative(-10))
        buttons_layout.addWidget(self.rewind_button)
        
        self.play_button = QPushButton("▶")
        self.play_button.setFixedSize(40, 40)
        self.play_button.clicked.connect(self.play_video)
        self.play_button.setStyleSheet("""
            QPushButton { background-color: #6366f1; color: white; border: none; border-radius: 20px; font-size: 16px; }
            QPushButton:hover { background-color: #818cf8; }
        """)
        buttons_layout.addWidget(self.play_button)
        
        self.forward_button = QPushButton("30s ⏩")
        self.forward_button.clicked.connect(lambda: self.seek_relative(30))
        buttons_layout.addWidget(self.forward_button)
        
        self.next_button = QPushButton("⏭")
        self.next_button.clicked.connect(self.next_video)
        buttons_layout.addWidget(self.next_button)
        
        buttons_layout.addSpacing(10)
        
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
        
        self.audio_combo = QComboBox()
        self.audio_combo.setMinimumWidth(200)
        self.audio_combo.currentIndexChanged.connect(self.change_audio_device)
        buttons_layout.addWidget(self.audio_combo)
        
        self.subtitle_combo = QComboBox()
        self.subtitle_combo.setMinimumWidth(150)
        self.subtitle_combo.addItem("Altyazı Yok")
        self.subtitle_combo.currentIndexChanged.connect(self.change_subtitle)
        buttons_layout.addWidget(self.subtitle_combo)
        
        buttons_layout.addStretch()
        
        self.speed_label = QLabel("1.0x")
        self.speed_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.speed_label.mousePressEvent = self.show_speed_menu
        buttons_layout.addWidget(self.speed_label)
        
        buttons_layout.addSpacing(10)
        
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
        
        self.fullscreen_btn = QPushButton("⛶")
        self.fullscreen_btn.setFixedWidth(40)
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)
        self.fullscreen_btn.setToolTip("Tam ekran (F11)")
        buttons_layout.addWidget(self.fullscreen_btn)
        
        controls_layout.addLayout(buttons_layout)
        controls_panel.setLayout(controls_layout)
        
        return controls_panel

    def create_menu_bar(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar { background-color: #0f172a; color: #f8fafc; border-bottom: 1px solid rgba(255, 255, 255, 0.1); font-family: 'Inter'; font-size: 12px; }
            QMenuBar::item { padding: 6px 10px; border-radius: 4px; margin-left: 4px; }
            QMenuBar::item:selected { background-color: rgba(255, 255, 255, 0.1); }
            QMenu { background-color: #0f172a; color: #f8fafc; border: 1px solid rgba(255, 255, 255, 0.1); font-family: 'Inter'; font-size: 12px; padding: 4px; }
            QMenu::item { padding: 6px 20px 6px 20px; border-radius: 4px; }
            QMenu::item:selected { background-color: #6366f1; }
        """)
        
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
        
        help_menu = menubar.addMenu("❓ Yardım")
        
        about_action = QAction("ℹ️ Hakkında", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        shortcuts_action = QAction("⌨️ Kısayollar", self)
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)

    def create_shortcuts(self):
        shortcuts = {
            'Space': self.play_video,
            'Right': lambda: self.seek_relative(30),
            'Left': lambda: self.seek_relative(-10),
            'Up': lambda: self.volume_slider.setValue(min(100, self.volume_slider.value() + 5)),
            'Down': lambda: self.volume_slider.setValue(max(0, self.volume_slider.value() - 5)),
            'M': self.toggle_mute,
            'F': self.toggle_fullscreen,
            'R': self._resume_from_saved,
            'Ctrl+Left': self.previous_video,
            'Ctrl+Right': self.next_video,
            'Ctrl+Up': lambda: self.set_playback_speed(self.media_player.playbackRate() + 0.1),
            'Ctrl+Down': lambda: self.set_playback_speed(max(0.25, self.media_player.playbackRate() - 0.1)),
        }

        from PyQt6.QtGui import QShortcut
        for key, func in shortcuts.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(func)

    def _resume_from_saved(self):
        pos = getattr(self, '_pending_resume_position', 0)
        if pos > 0:
            self.media_player.setPosition(pos)
            self._pending_resume_position = 0
            mins, secs = pos // 60000, (pos % 60000) // 1000
            self.statusBar().showMessage(f"⏩ {mins}:{secs:02d} konumuna atlandı", 3000)
        else:
            self.statusBar().showMessage("Kaydedilmiş konum yok", 2000)
            
    def setup_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #020617; }
            QPushButton { background-color: transparent; color: #cbd5e1; border: 1px solid transparent; border-radius: 8px; padding: 6px 12px; font-size: 13px; font-family: 'Inter'; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); color: #f8fafc; border-color: rgba(255, 255, 255, 0.2); }
            QPushButton:pressed { background-color: rgba(255, 255, 255, 0.05); }
            QSlider::groove:horizontal { height: 6px; background: rgba(255, 255, 255, 0.15); border-radius: 3px; }
            QSlider::handle:horizontal { background: #6366f1; width: 16px; margin: -5px 0; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #818cf8; }
            QSlider::sub-page:horizontal { background: #6366f1; border-radius: 3px; }
            QComboBox { background-color: rgba(255, 255, 255, 0.05); color: #f8fafc; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 6px 12px; font-family: 'Inter'; font-size: 12px; }
            QComboBox::drop-down { border: none; }
            QComboBox::down-arrow { image: none; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 5px solid #cbd5e1; margin-right: 8px; }
            QLabel { color: #cbd5e1; font-family: 'Inter'; }
        """)

    def show_about(self):
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
