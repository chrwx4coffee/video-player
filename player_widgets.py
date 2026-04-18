import subprocess
from PyQt6.QtWidgets import QGraphicsEffect, QSlider, QGraphicsView
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QImage, QTransform, QWheelEvent, QMouseEvent, QPainter

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


class ThumbnailWorker(QThread):
    thumbnail_ready = pyqtSignal(int, bytes)

    def __init__(self, playlist, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        for i, video_path in enumerate(self.playlist):
            if self._is_cancelled:
                break
            try:
                cmd = [
                    "ffmpeg", "-y", "-ss", "00:00:02", "-i", video_path,
                    "-vframes", "1", "-q:v", "2", "-vf", "scale=160:-1",
                    "-f", "image2pipe", "-vcodec", "mjpeg", "-"
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                stdout_data, _ = proc.communicate()
                if stdout_data and not self._is_cancelled:
                    self.thumbnail_ready.emit(i, stdout_data)
            except Exception as e:
                print(f"Thumbnail error for {video_path}: {e}")
