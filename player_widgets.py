import subprocess
import threading
import time

from PyQt6.QtWidgets import (
    QGraphicsEffect, QSlider, QGraphicsView, QScrollArea,
    QFrame, QLabel, QVBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import (
    QImage, QTransform, QWheelEvent, QMouseEvent, QPainter,
    QPixmap, QGuiApplication
)

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False


class SharpenEffect(QGraphicsEffect):
    """Unsharp mask ile gerçek netlik artırma efekti (numpy tabanlı)."""
    def __init__(self, strength=0):
        super().__init__()
        self._strength = strength  # 1–10

    def set_strength(self, v):
        self._strength = max(0, v)
        self.update()

    def draw(self, painter):
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
    """Tıklanan yere atlayan ve üzerinde fare gezdirildiğinde önizleme sinyali yayan slider"""
    hover_moved = pyqtSignal(int, int, int)  # ms, global_x, global_y
    hover_left = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.width() > 0:
                val = self.minimum() + ((self.maximum() - self.minimum()) * event.position().x()) / self.width()
                self.setValue(int(val))
                self.sliderMoved.emit(self.value())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.width() > 0 and self.maximum() > self.minimum():
            x = max(0, min(int(event.position().x()), self.width()))
            ratio = x / self.width()
            val = int(self.minimum() + ratio * (self.maximum() - self.minimum()))
            g_pos = event.globalPosition().toPoint()
            self.hover_moved.emit(val, g_pos.x(), g_pos.y())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hover_left.emit()
        super().leaveEvent(event)


class VideoPreviewTooltipWidget(QFrame):
    """YouTube tarzı kayan küçük video kare önizleme penceresi"""
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.setStyleSheet("""
            QFrame#PreviewCard {
                background-color: rgba(15, 23, 42, 0.95);
                border: 1.5px solid rgba(99, 102, 241, 0.6);
                border-radius: 10px;
            }
            QLabel {
                color: #f8fafc;
                font-family: 'Inter';
            }
        """)
        self.setObjectName("PreviewCard")
        self.setFixedSize(184, 134)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(172, 97)
        self.thumbnail_label.setStyleSheet("background-color: #020617; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1);")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setScaledContents(True)

        self.time_label = QLabel("00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #818cf8;")

        layout.addWidget(self.thumbnail_label)
        layout.addWidget(self.time_label)

    def set_preview(self, pixmap: QPixmap, time_str: str, global_x: int, global_y: int):
        if pixmap and not pixmap.isNull():
            self.thumbnail_label.setPixmap(pixmap)
        else:
            self.thumbnail_label.clear()
            self.thumbnail_label.setText("🎬 Yükleniyor...")
            
        self.time_label.setText(time_str)

        # Pozisyonu farenin tam üstüne yerleştir, ekran sınırlarına dikkat et
        screen = QGuiApplication.screenAt(QGuiApplication.primaryScreen().geometry().topLeft())
        screen_geo = screen.availableGeometry() if screen else None

        target_x = int(global_x - (self.width() / 2))
        target_y = int(global_y - self.height() - 14)

        if screen_geo:
            target_x = max(screen_geo.left() + 5, min(target_x, screen_geo.right() - self.width() - 5))
            target_y = max(screen_geo.top() + 5, min(target_y, screen_geo.bottom() - self.height() - 5))

        self.move(target_x, target_y)
        if not self.isVisible():
            self.show()


class VideoPreviewWorker(QThread):
    """FFmpeg kullanarak arkaplanda hızlı video kareleri çıkaran iş parçacığı"""
    frame_ready = pyqtSignal(str, int, bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True
        self._lock = threading.Lock()
        self._pending_request = None  # (file_path, sec_int)
        self._cache = {}  # (file_path, sec_int) -> bytes
        self._cond = threading.Condition(self._lock)
        self._proc = None

    def request_frame(self, file_path: str, sec_int: int):
        key = (file_path, sec_int)
        if key in self._cache:
            self.frame_ready.emit(file_path, sec_int, self._cache[key])
            return True

        with self._cond:
            self._pending_request = (file_path, sec_int)
            self._cond.notify_all()
        return False

    def get_cached_frame(self, file_path: str, sec_int: int):
        return self._cache.get((file_path, sec_int))

    def stop(self):
        self._is_running = False
        with self._cond:
            self._cond.notify_all()
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self.wait(500)

    def run(self):
        while self._is_running:
            req = None
            with self._cond:
                while self._is_running and self._pending_request is None:
                    self._cond.wait(0.2)
                if not self._is_running:
                    break
                req = self._pending_request
                self._pending_request = None

            if not req:
                continue

            file_path, sec_int = req
            key = (file_path, sec_int)
            if key in self._cache:
                self.frame_ready.emit(file_path, sec_int, self._cache[key])
                continue

            try:
                # Hızlı arama için -ss dosya adından önce verilir
                mins = sec_int // 60
                secs = sec_int % 60
                hours = mins // 60
                mins = mins % 60
                time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

                cmd = [
                    "ffmpeg", "-y", "-ss", time_str, "-noaccurate_seek",
                    "-i", file_path,
                    "-vframes", "1", "-q:v", "3",
                    "-vf", "scale=180:-1",
                    "-f", "image2pipe", "-vcodec", "mjpeg", "-"
                ]
                self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                stdout_data, _ = self._proc.communicate()
                self._proc = None

                if stdout_data and self._is_running:
                    # Basit LRU koruması
                    if len(self._cache) > 400:
                        # İlk 100 kaydı temizle
                        keys = list(self._cache.keys())[:100]
                        for k in keys:
                            self._cache.pop(k, None)
                    self._cache[key] = stdout_data
                    self.frame_ready.emit(file_path, sec_int, stdout_data)
            except Exception:
                pass


class HorizontalScrollArea(QScrollArea):
    """Fare tekerleği ile yatay kaydırma sağlayan modern ScrollArea"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.angleDelta().x()
        if delta != 0:
            h_bar = self.horizontalScrollBar()
            # Aşağı tekerlek sağa kaydırır, yukarı sola
            h_bar.setValue(h_bar.value() - delta)
            event.accept()
        else:
            super().wheelEvent(event)


class CustomGraphicsView(QGraphicsView):
    """Zoom ve pan desteği olan, içerikleri her zaman merkezde tutan graphics view"""
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setOptimizationFlags(QGraphicsView.OptimizationFlag.DontSavePainterState)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.zoom_factor = 1.0
        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
        
    def wheelEvent(self, event: QWheelEvent):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / 1.15
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
            self.zoom_factor *= zoom_in_factor
            event.accept()
        elif event.angleDelta().y() < 0:
            if self.zoom_factor > 0.1:
                self.scale(zoom_out_factor, zoom_out_factor)
                self.zoom_factor *= zoom_out_factor
                event.accept()
        else:
            super().wheelEvent(event)

    def zoom_in(self):
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.scale(1.2, 1.2)
        self.zoom_factor *= 1.2
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def zoom_out(self):
        if self.zoom_factor > 0.1:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
            self.scale(1 / 1.2, 1 / 1.2)
            self.zoom_factor /= 1.2
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def reset_zoom(self):
        self.setTransform(QTransform())
        self.zoom_factor = 1.0
        target = None
        for item in self.scene().items():
            if item.isVisible():
                target = item
                break
        if target:
            bounds = target.mapToScene(target.boundingRect()).boundingRect()
            if bounds.isValid() and bounds.width() > 0 and bounds.height() > 0:
                self.scene().setSceneRect(bounds)
                self.fitInView(bounds, Qt.AspectRatioMode.KeepAspectRatio)
                self.centerOn(target)


class ThumbnailWorker(QThread):
    thumbnail_ready = pyqtSignal(int, bytes)

    def __init__(self, playlist, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self._is_cancelled = False
        self._proc = None

    def cancel(self):
        self._is_cancelled = True
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def run(self):
        for i, media_path in enumerate(self.playlist):
            if self._is_cancelled:
                break
            try:
                ext = media_path.lower()
                image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.webp', '.gif', '.tiff', '.svg', '.jfif', '.avif')
                if ext.endswith(image_extensions):
                    # Resim dosyaları için hızlı yerel okuma
                    with open(media_path, "rb") as f:
                        img_bytes = f.read()
                    if img_bytes and not self._is_cancelled:
                        self.thumbnail_ready.emit(i, img_bytes)
                else:
                    cmd = [
                        "ffmpeg", "-y", "-ss", "00:00:02", "-i", media_path,
                        "-vframes", "1", "-q:v", "2", "-vf", "scale=160:-1",
                        "-f", "image2pipe", "-vcodec", "mjpeg", "-"
                    ]
                    self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    stdout_data, _ = self._proc.communicate()
                    if stdout_data and not self._is_cancelled:
                        self.thumbnail_ready.emit(i, stdout_data)
            except Exception as e:
                if not self._is_cancelled:
                    print(f"Thumbnail error for {media_path}: {e}")
            finally:
                self._proc = None
