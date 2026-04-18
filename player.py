import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QFileDialog, QGraphicsScene
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtCore import Qt, QUrl, QRectF, QTimer, QSettings

from player_widgets import CustomGraphicsView
from player_settings import PlayerSettingsMixin
from player_ui import PlayerUIMixin

class VideoPlayer(PlayerUIMixin, PlayerSettingsMixin, QMainWindow):
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
        
        self.setAcceptDrops(True)
        
    def init_ui(self):
        """Kullanıcı arayüzünü oluştur"""
        # Merkez widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Menü çubuğu (Mixin'den)
        self.create_menu_bar()

        # Video + Ayarlar paneli (yatay splitter)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet("QSplitter::handle { background-color: rgba(255, 255, 255, 0.1); width: 1px; }")
        self.splitter.addWidget(self.graphics_view)

        # Gömülü ayarlar paneli (Mixin'den)
        self.settings_panel = self.create_settings_panel()
        self.settings_panel.setVisible(False)
        self.splitter.addWidget(self.settings_panel)
        self.splitter.setSizes([1200, 300])

        main_layout.addWidget(self.splitter, stretch=1)

        # Alt seçim çekmecesi oluştur (Mixin'den)
        self.create_drawer_panel()

        # Kontrol paneli (Mixin'den)
        controls_panel = self.create_controls_panel()
        main_layout.addWidget(controls_panel)

        # Durum çubuğu
        self.statusBar().showMessage("Hazır")
        self.statusBar().setStyleSheet("QStatusBar { background-color: #0f172a; color: #94a3b8; border-top: 1px solid rgba(255, 255, 255, 0.1); font-family: 'JetBrains Mono'; }")

        central_widget.setLayout(main_layout)

    def open_file(self):
        """Video dosyası aç — aynı klasördeki tüm videoları da yükle"""
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Video Seç",
            self.settings.value('last_path', ''),
            "Video Dosyaları (*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.ts *.m2ts *.ogv);;Tüm Dosyalar (*.*)"
        )

        if file_name:
            self.settings.setValue('last_path', os.path.dirname(file_name))
            # Aynı klasördeki tüm videoları bul
            self._load_folder_playlist(os.path.dirname(file_name), selected_file=file_name)
            
    def open_folder(self):
        """Klasördeki tüm videoları aç"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Video Klasörü Seç",
            self.settings.value('last_path', '')
        )

        if folder:
            self.settings.setValue('last_path', folder)
            self._load_folder_playlist(folder)

    def _load_folder_playlist(self, folder, selected_file=None):
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',
                            '.webm', '.m4v', '.ts', '.m2ts', '.ogv', '.3gp', '.wmv'}
        files = sorted(
            str(f) for f in Path(folder).iterdir()
            if f.is_file() and f.suffix.lower() in video_extensions
        )

        if not files:
            self.statusBar().showMessage("Klasörde video bulunamadı")
            return

        self.playlist = files

        if selected_file and selected_file in files:
            self.current_playlist_index = files.index(selected_file)
        else:
            self.current_playlist_index = 0

        self.load_video(self.playlist[self.current_playlist_index])
        self.update_drawer_playlist()

        self.update_drawer_geometry()
        self.drawer_panel.show()

        n = len(files)
        idx = self.current_playlist_index + 1
        self.statusBar().showMessage(
            f"{n} video yüklendi — {idx}/{n}: {os.path.basename(self.playlist[self.current_playlist_index])}"
        )
                
    def load_video(self, file_path):
        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(file_path))
        self.play_button.setText("⏸")
        self.media_player.play()
        self.set_volume(self.volume_slider.value())

        try:
            items = self.scene.items()
            if items:
                self.graphics_view.fitInView(items[0], Qt.AspectRatioMode.KeepAspectRatio)
            self.graphics_view.zoom_factor = 1.0
        except Exception:
            pass

        saved_position = self.settings.value(f'position_{file_path}', 0, type=int)
        self._pending_resume_position = 0
        if saved_position > 5000:
            self._pending_resume_position = saved_position
            mins = saved_position // 60000
            secs = (saved_position % 60000) // 1000
            self.statusBar().showMessage(
                f"▶ Oynatılıyor: {os.path.basename(file_path)}  |  "
                f"💡 {mins}:{secs:02d} konumundan devam etmek için [R] tuşuna basın"
            )
        else:
            self._pending_resume_position = 0
            self.setWindowTitle(f"Premium Video Oynatıcı - {os.path.basename(file_path)}")
            self.statusBar().showMessage(f"▶ Oynatılıyor: {os.path.basename(file_path)}")

        self.setWindowTitle(f"Premier — {os.path.basename(file_path)}")
        
    def play_video(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_button.setText("▶")
        else:
            self.media_player.play()
            self.play_button.setText("⏸")
            
    def previous_video(self):
        if self.playlist and self.current_playlist_index > 0:
            self.current_playlist_index -= 1
            self.load_video(self.playlist[self.current_playlist_index])
            self._refresh_drawer_highlight()

    def next_video(self):
        if self.playlist and self.current_playlist_index < len(self.playlist) - 1:
            self.current_playlist_index += 1
            self.load_video(self.playlist[self.current_playlist_index])
            self._refresh_drawer_highlight()
            
    def seek_relative(self, seconds):
        if self.media_player.duration() > 0:
            new_pos = self.media_player.position() + (seconds * 1000)
            new_pos = max(0, min(new_pos, self.media_player.duration()))
            self.media_player.setPosition(new_pos)
            
    def set_playback_speed(self, speed):
        self.media_player.setPlaybackRate(speed)
        self.speed_label.setText(f"{speed}x")
        self.statusBar().showMessage(f"Oynatma hızı: {speed}x", 2000)
        
    def set_volume(self, volume):
        self.volume_level = volume / 100.0
        self.audio_output.setVolume(self.volume_level)
        
        if volume == 0:
            self.volume_button.setText("🔇")
        elif volume < 30:
            self.volume_button.setText("🔈")
        elif volume < 70:
            self.volume_button.setText("🔉")
        else:
            self.volume_button.setText("🔊")
            
    def toggle_mute(self):
        self.audio_output.setMuted(not self.audio_output.isMuted())
        self.volume_button.setText("🔇" if self.audio_output.isMuted() else "🔊")
        
    def rotate_video(self, angle):
        self.rotation_angle = (self.rotation_angle + angle) % 360
        rect = self.video_item.boundingRect()
        self.video_item.setTransformOriginPoint(rect.width() / 2, rect.height() / 2)
        self.video_item.setRotation(self.rotation_angle)
        self.graphics_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)
        self.statusBar().showMessage(f"Döndürüldü: {self.rotation_angle}°", 2000)

    def toggle_fullscreen(self):
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
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Altyazı Seç",
            "",
            "Altyazı Dosyaları (*.srt *.ass *.ssa *.vtt);;Tüm Dosyalar (*.*)"
        )
        if file_name:
            self.subtitle_tracks.append(file_name)
            self.subtitle_combo.addItem(os.path.basename(file_name))
            self.statusBar().showMessage(f"Altyazı yüklendi: {os.path.basename(file_name)}")
            
    def change_subtitle(self, index):
        if index == 0:
            self.current_subtitle_index = -1
            self.statusBar().showMessage("Altyazı kapatıldı", 2000)
        elif index - 1 < len(self.subtitle_tracks):
            self.current_subtitle_index = index - 1
            self.statusBar().showMessage(f"Altyazı: {os.path.basename(self.subtitle_tracks[self.current_subtitle_index])}", 2000)
            
    def refresh_audio_devices_list(self):
        current_id = None
        if self.audio_combo.currentIndex() > 0:
            device = self.audio_combo.itemData(self.audio_combo.currentIndex())
            if device:
                current_id = device.id()
                
        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        
        self.audio_combo.addItem("💻 Sistem Varsayılanı", None)
        
        for device in QMediaDevices.audioOutputs():
            self.audio_combo.addItem(f"🔊 {device.description()}", device)
            if current_id and device.id() == current_id:
                self.audio_combo.setCurrentIndex(self.audio_combo.count() - 1)
                
        self.audio_combo.blockSignals(False)
        
    def change_audio_device(self, index):
        device = self.audio_combo.itemData(index)
        volume = self.volume_slider.value() / 100.0
        
        if index == 0 or not device:
            self.audio_output.setDevice(QMediaDevices.defaultAudioOutput())
        else:
            self.audio_output.setDevice(device)
            
        self.audio_output.setVolume(volume)
        self.statusBar().showMessage(f"Ses cihazı değiştirildi", 2000)
        
    def show_speed_menu(self, event):
        menu = self.speed_label.parent().contextMenu()
        if not menu:
            from PyQt6.QtWidgets import QMenu
            menu = QMenu()
            speeds = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
            from functools import partial
            for speed in speeds:
                action = menu.addAction(f"{speed}x")
                action.triggered.connect(partial(self.set_playback_speed, speed))
        menu.exec(self.speed_label.mapToGlobal(event.pos()))
        
    def save_current_position(self):
        if self.media_player.source().isLocalFile():
            file_path = self.media_player.source().toLocalFile()
            position = self.media_player.position()
            if position > 5000:
                self.settings.setValue(f'position_{file_path}', position)
                
    def load_settings(self):
        self.volume_level = self.settings.value('volume', 1.0, type=float)
        self.last_window_geometry = self.settings.value('geometry', None)
        if self.last_window_geometry:
            self.restoreGeometry(self.last_window_geometry)
            
    def save_settings(self):
        self.settings.setValue('volume', self.volume_level)
        self.settings.setValue('geometry', self.saveGeometry())
        
    def video_size_changed(self, size):
        if size.isValid():
            self.video_item.setSize(size)
            self.scene.setSceneRect(QRectF(0, 0, size.width(), size.height()))
            self.graphics_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)
            
    def position_changed(self, position):
        if not self.is_slider_pressed:
            self.position_slider.setValue(position)
        self.update_time_label(position, self.media_player.duration())
        
    def duration_changed(self, duration):
        self.position_slider.setRange(0, duration)
        
    def playback_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setText("⏸")
        else:
            self.play_button.setText("▶")
            
    def slider_pressed(self):
        self.is_slider_pressed = True
        
    def slider_released(self):
        self.is_slider_pressed = False
        self.media_player.setPosition(self.position_slider.value())
        
    def set_position(self, position):
        self.media_player.setPosition(position)
        
    def update_time_label(self, current_ms, total_ms):
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
        error_string = self.media_player.errorString()
        if error_string:
            self.statusBar().showMessage(f"Hata: {error_string}", 5000)
            print(f"Media Player Error: {error_string}")

    def closeEvent(self, event):
        self.save_current_position()
        self.save_settings()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.toggle_fullscreen()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'video_item') and self.video_item.nativeSize().isValid():
            from PyQt6.QtGui import QTransform
            self.graphics_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)
        if hasattr(self, 'update_drawer_geometry'):
            self.update_drawer_geometry()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return

        file_path = urls[0].toLocalFile()
        if not os.path.isfile(file_path):
            return

        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv',
                            '.webm', '.m4v', '.ts', '.m2ts', '.ogv', '.3gp'}
        if Path(file_path).suffix.lower() not in video_extensions:
            self.statusBar().showMessage("Desteklenmeyen dosya formatı!")
            return

        self.settings.setValue('last_path', os.path.dirname(file_path))
        self._load_folder_playlist(os.path.dirname(file_path), selected_file=file_path)