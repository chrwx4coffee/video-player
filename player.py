import os
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QFileDialog, QGraphicsScene, QApplication
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices, QMediaMetaData
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
        self.loop_mode = 0  # 0: Kapalı, 1: Tek Oynatım Tekrarı, 2: Liste Tekrarı
        
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
        self.media_player.tracksChanged.connect(self.update_tracks)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status_change)
        
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
        
    def go_to_parent_directory(self):
        if not self.playlist or self.current_playlist_index < 0:
            last_path = self.settings.value('last_path', '')
            if last_path and os.path.exists(last_path):
                current_dir = last_path
            else:
                current_dir = os.path.expanduser('~')
        else:
            current_dir = os.path.dirname(self.playlist[self.current_playlist_index])
        
        parent_dir = os.path.dirname(current_dir)
        if parent_dir and os.path.exists(parent_dir) and parent_dir != current_dir:
            self._load_folder_playlist(parent_dir)

    def go_to_subdirectory(self, index):
        if index <= 0:
            return
        path = self.sub_dir_combo.itemData(index)
        if path and os.path.exists(path):
            self._load_folder_playlist(path)

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
        self.load_bookmarks(file_path)
        
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
        data = self.subtitle_combo.itemData(index)
        sub_tracks_count = len(self.media_player.subtitleTracks())
        if data == -1 or data is None:
            self.media_player.setActiveSubtitleTrack(-1)
            self.current_subtitle_index = -1
            self.statusBar().showMessage("Altyazı kapatıldı", 2000)
        elif isinstance(data, int) and data < sub_tracks_count:
            self.media_player.setActiveSubtitleTrack(data)
            self.current_subtitle_index = data
            self.statusBar().showMessage(f"İç Altyazı {data+1} etkinleştirildi", 2000)
        else:
            # External track
            ext_idx = data - sub_tracks_count
            if ext_idx < len(self.subtitle_tracks):
                self.current_subtitle_index = data
                self.statusBar().showMessage(f"Dış altyazı seçildi: {os.path.basename(self.subtitle_tracks[ext_idx])}", 2000)
            
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
        if not hasattr(self, '_speed_menu'):
            from PyQt6.QtWidgets import QMenu
            from functools import partial
            self._speed_menu = QMenu(self)
            speeds = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
            for speed in speeds:
                action = self._speed_menu.addAction(f"{speed}x")
                action.triggered.connect(partial(self.set_playback_speed, speed))
        self._speed_menu.exec(self.speed_label.mapToGlobal(event.pos()))
        
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

    def toggle_loop_mode(self):
        self.loop_mode = (self.loop_mode + 1) % 3
        if self.loop_mode == 0:
            self.loop_button.setText("🔁")
            self.loop_button.setToolTip("Oynatma Listesi Tekrarı: Kapalı")
            self.loop_button.setStyleSheet("""
                QPushButton { background-color: transparent; color: #cbd5e1; border: 1px solid transparent; border-radius: 8px; padding: 6px; font-size: 14px; }
                QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }
            """)
            self.statusBar().showMessage("Tekrar Modu: Kapalı (Otomatik Sonraki)", 2000)
        elif self.loop_mode == 1:
            self.loop_button.setText("🔂")
            self.loop_button.setToolTip("Tekrar Modu: Tek Video Tekrar")
            self.loop_button.setStyleSheet("""
                QPushButton { background-color: rgba(99, 102, 241, 0.35); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.65); border-radius: 8px; padding: 6px; font-size: 14px; }
            """)
            self.statusBar().showMessage("Tekrar Modu: Tek Video Tekrar", 2000)
        else:
            self.loop_button.setText("🔁")
            self.loop_button.setToolTip("Tekrar Modu: Oynatma Listesi Tekrar")
            self.loop_button.setStyleSheet("""
                QPushButton { background-color: rgba(99, 102, 241, 0.35); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.65); border-radius: 8px; padding: 6px; font-size: 14px; }
            """)
            self.statusBar().showMessage("Tekrar Modu: Tüm Oynatma Listesini Tekrarla", 2000)

    def handle_media_status_change(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.loop_mode == 1:  # Loop One
                self.media_player.setPosition(0)
                self.media_player.play()
            elif self.loop_mode == 2:  # Loop Playlist
                if self.playlist:
                    self.current_playlist_index = (self.current_playlist_index + 1) % len(self.playlist)
                    self.load_video(self.playlist[self.current_playlist_index])
                    self._refresh_drawer_highlight()
            else:  # Loop Off (Default: Auto advance but stop at end)
                if self.playlist and self.current_playlist_index < len(self.playlist) - 1:
                    self.next_video()
                else:
                    self.play_button.setText("▶")

    def update_tracks(self):
        # Update Audio Tracks
        self.audio_track_combo.blockSignals(True)
        self.audio_track_combo.clear()
        audio_tracks = self.media_player.audioTracks()
        if not audio_tracks:
            self.audio_track_combo.addItem("Ses İzi Yok", -1)
            self.audio_track_combo.setEnabled(False)
        else:
            self.audio_track_combo.setEnabled(True)
            active_audio = self.media_player.activeAudioTrack()
            for i, track in enumerate(audio_tracks):
                lang = track.stringValue(QMediaMetaData.Key.Language)
                title = track.stringValue(QMediaMetaData.Key.Title)
                label = f"Ses {i+1}"
                if title:
                    label += f" - {title}"
                if lang:
                    label += f" ({lang})"
                self.audio_track_combo.addItem(label, i)
                if i == active_audio:
                    self.audio_track_combo.setCurrentIndex(i)
        self.audio_track_combo.blockSignals(False)

        # Update Subtitle Tracks
        self.subtitle_combo.blockSignals(True)
        self.subtitle_combo.clear()
        self.subtitle_combo.addItem("Altyazı Yok", -1)
        sub_tracks = self.media_player.subtitleTracks()
        active_sub = self.media_player.activeSubtitleTrack()
        
        for i, track in enumerate(sub_tracks):
            lang = track.stringValue(QMediaMetaData.Key.Language)
            title = track.stringValue(QMediaMetaData.Key.Title)
            label = f"İç Altyazı {i+1}"
            if title:
                label += f" - {title}"
            if lang:
                label += f" ({lang})"
            self.subtitle_combo.addItem(label, i)
            if i == active_sub:
                self.subtitle_combo.setCurrentIndex(self.subtitle_combo.count() - 1)
                
        for i, sub_path in enumerate(self.subtitle_tracks):
            label = f"Dış Altyazı: {os.path.basename(sub_path)}"
            self.subtitle_combo.addItem(label, len(sub_tracks) + i)
            if len(sub_tracks) + i == self.current_subtitle_index:
                self.subtitle_combo.setCurrentIndex(self.subtitle_combo.count() - 1)
                
        self.subtitle_combo.blockSignals(False)

    def change_audio_track(self, index):
        track_idx = self.audio_track_combo.itemData(index)
        if track_idx is not None and track_idx >= -1:
            self.media_player.setActiveAudioTrack(track_idx)
            if track_idx == -1:
                self.statusBar().showMessage("Varsayılan ses izi seçildi", 2000)
            else:
                self.statusBar().showMessage(f"Ses izi değiştirildi: {self.audio_track_combo.currentText()}", 2000)

    def take_screenshot(self):
        if not self.media_player.source().isValid():
            self.statusBar().showMessage("Ekran görüntüsü alınacak yüklü video yok!", 2000)
            return

        drawer_was_visible = False
        if hasattr(self, 'drawer_panel') and self.drawer_panel.isVisible():
            drawer_was_visible = True
            self.drawer_panel.hide()
            QApplication.processEvents()

        try:
            pixmap = self.graphics_view.viewport().grab()
            
            from pathlib import Path
            pictures_dir = Path.home() / "Resimler"
            if not pictures_dir.exists():
                pictures_dir = Path.home() / "Pictures"
            if not pictures_dir.exists():
                video_url = self.media_player.source().toLocalFile()
                if video_url and os.path.exists(video_url):
                    pictures_dir = Path(os.path.dirname(video_url))
                else:
                    pictures_dir = Path.home()
            
            video_name = "video"
            video_file = self.media_player.source().toLocalFile()
            if video_file:
                video_name = Path(video_file).stem
            
            pos_ms = self.media_player.position()
            pos_sec = pos_ms // 1000
            mins = pos_sec // 60
            secs = pos_sec % 60
            
            filename = f"Screenshot_{video_name}_{mins:02d}m{secs:02d}s.png"
            filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
            save_path = pictures_dir / filename
            
            pictures_dir.mkdir(parents=True, exist_ok=True)
            
            if pixmap.save(str(save_path), "PNG"):
                self.statusBar().showMessage(f"📸 Ekran görüntüsü kaydedildi: {save_path.name}", 4000)
                self.show_screenshot_notification(save_path)
            else:
                self.statusBar().showMessage("Ekran görüntüsü kaydedilemedi!", 3000)
        finally:
            if drawer_was_visible:
                self.drawer_panel.show()

    def show_screenshot_notification(self, file_path):
        notification = QLabel(self.graphics_view)
        notification.setText(f"📸 Ekran Görüntüsü Kaydedildi\n{file_path.name}")
        notification.setStyleSheet("""
            QLabel {
                background-color: rgba(99, 102, 241, 0.9);
                color: white;
                border-radius: 8px;
                padding: 10px 15px;
                font-family: 'Inter';
                font-size: 12px;
                font-weight: bold;
            }
        """)
        notification.setAlignment(Qt.AlignmentFlag.AlignCenter)
        notification.adjustSize()
        
        margin = 20
        x = self.graphics_view.width() - notification.width() - margin
        y = margin
        notification.move(int(x), int(y))
        notification.show()
        
        from PyQt6.QtCore import QPropertyAnimation
        from PyQt6.QtWidgets import QGraphicsOpacityEffect
        
        opacity_effect = QGraphicsOpacityEffect(notification)
        notification.setGraphicsEffect(opacity_effect)
        
        anim = QPropertyAnimation(opacity_effect, b"opacity")
        anim.setDuration(2500)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setKeyValueAt(0.7, 1.0)
        
        notification._anim = anim
        anim.finished.connect(notification.deleteLater)
        anim.start()

    def load_bookmarks(self, file_path):
        self.bookmark_list.clear()
        if not file_path:
            return
        
        bookmarks = self.settings.value(f'bookmarks_{file_path}', [])
        for item in bookmarks:
            try:
                if isinstance(item, list) and len(item) == 2:
                    pos, label = item[0], item[1]
                elif isinstance(item, tuple) and len(item) == 2:
                    pos, label = item[0], item[1]
                else:
                    continue
                self.add_bookmark_item_to_widget(pos, label)
            except Exception as e:
                print(f"Error loading bookmark: {e}")

    def add_bookmark_item_to_widget(self, pos, label):
        pos_sec = pos // 1000
        mins = pos_sec // 60
        secs = pos_sec % 60
        time_str = f"{mins:02d}:{secs:02d}"
        
        from PyQt6.QtWidgets import QListWidgetItem
        item = QListWidgetItem(f"📌 {time_str} - {label}")
        item.setData(Qt.ItemDataRole.UserRole, pos)
        self.bookmark_list.addItem(item)

    def add_bookmark(self):
        file_path = self.media_player.source().toLocalFile()
        if not file_path:
            self.statusBar().showMessage("Zaman imi eklemek için video oynatılıyor olmalı!", 2000)
            return
            
        pos = self.media_player.position()
        label = self.bookmark_input.text().strip()
        if not label:
            label = f"Zaman İmi {self.bookmark_list.count() + 1}"
            
        self.add_bookmark_item_to_widget(pos, label)
        self.bookmark_input.clear()
        
        self.save_bookmarks(file_path)
        self.statusBar().showMessage("Zaman imi başarıyla eklendi", 2000)

    def save_bookmarks(self, file_path):
        bookmarks = []
        for index in range(self.bookmark_list.count()):
            item = self.bookmark_list.item(index)
            pos = item.data(Qt.ItemDataRole.UserRole)
            text = item.text()
            label = text.split(" - ", 1)[1] if " - " in text else text
            bookmarks.append((pos, label))
        self.settings.setValue(f'bookmarks_{file_path}', bookmarks)

    def jump_to_bookmark(self, item):
        pos = item.data(Qt.ItemDataRole.UserRole)
        if pos is not None:
            self.media_player.setPosition(pos)
            self.statusBar().showMessage(f"Zaman imine gidildi: {item.text()}", 2000)

    def remove_bookmark(self):
        selected = self.bookmark_list.currentItem()
        if selected:
            self.bookmark_list.takeItem(self.bookmark_list.row(selected))
            file_path = self.media_player.source().toLocalFile()
            if file_path:
                self.save_bookmarks(file_path)
            self.statusBar().showMessage("Zaman imi silindi", 2000)