import sys
import os
import subprocess
from PyQt6.QtWidgets import QApplication

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

def main():
    # Import inside to ensure env vars are set before Qt loads
    from player import VideoPlayer
    
    app = QApplication(sys.argv)
    app.setApplicationName("Premium Video Player")
    app.setOrganizationName("VideoPlayer")
    
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
