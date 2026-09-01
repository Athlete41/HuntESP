"""Hunt DMA GUI：后台线程读坐标，UI 只画点。"""

import math
import sys
import ctypes

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import game_offset as off
from core.game_camera import apply_game_camera, yaw_from_view
from core.reader_thread import ReaderThread
from hunt_reader import BOSS_TYPES
from ui.qt6_canvas3d import Point3D, Qt6Numpy3DCanvas, Text3D
from ui.qt6_radar import Qt6RadarCanvas, RadarEntity

import win32gui
import win32con
import keyboard

def ent_color(etype):
    if etype == "LocalPlayer":
        return QColor(0, 255, 0)
    if etype == "FriendlyPlayer":
        return QColor(0, 150, 255)
    if etype == "DeadPlayer":
        return QColor(130, 130, 130)
    if etype in BOSS_TYPES:
        return QColor(255, 165, 0)
    return QColor(255, 50, 50)


class HuntESPWindow(QWidget):
    def __init__(
        self,
        camera_ms=30,
        update_ms=50,
        scan_ms=60000,
        scan_batch_ms=0,
        batch_size=5000,
        max_entities=99999,
        fps=30.0,
        crosshair=True,
        show_distance=True,
        radar_range=250.0,
        radar_visible=True,
        window_posx=1920 * 0.5 - 1366 * 0.5,
        window_posy=1080 * 0.5 - 768 * 0.5,
        window_width=1366,
        window_height=768,
    ):
        super().__init__()
        self.setup_overlay()

        self.radar_range = radar_range
        self.show_distance = show_distance
        self.setGeometry(window_posx, window_posy, window_width, window_height)

        layout = QVBoxLayout(self)
        self.canvas3D = Qt6Numpy3DCanvas(self)
        self.canvas3D.setScreen(90.0, 0.1, 10000.0)
        self.canvas3D.setCrosshair(crosshair)
        layout.addWidget(self.canvas3D)

        self.radar = Qt6RadarCanvas(self)
        self.radar.setRadarRadius(self.radar_range)
        self.radar.setVisible(radar_visible)
        self.radar.setGeometry(0, 0, 260, 260)

        self.snapshot = {
            "camera": {"pos": [0.0, 0.0, 0.0], "view": [0.0] * 16, "proj": [0.0] * 16},
            "players": [],
            "bosses": [],
        }
        self.reader = ReaderThread(
            off.PROCESS_NAME,
            camera_ms=camera_ms,
            update_ms=update_ms,
            scan_ms=scan_ms,
            scan_batch_ms=scan_batch_ms,
            batch_size=batch_size,
            max_entities=max_entities,
        )
        self.reader.snapshot.connect(self.on_snapshot)
        self.reader.status.connect(lambda msg: print("[reader]", msg))
        self.reader.start()

        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self.render_frame)
        self.render_timer.start(int(1000.0 / fps))

        self._last_open_key = False
        self._last_close_key = False

    def setup_overlay(self):
        # 1. 设置窗口属性：无边框、置顶、Tool（不抢焦点）
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowDoesNotAcceptFocus
        )

        # 2. 启用真正的透明背景（关键！）
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # 3. 取消颜色键设置（不再需要）
        # 不需要 setStyleSheet，不需要 SetLayeredWindowAttributes

        hwnd = int(self.winId())
        # 4. 依然需要鼠标穿透（WS_EX_TRANSPARENT）
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        ex_style |= win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)

        # 5. 置顶
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)

        self.overlay_timer = QTimer(self)
        self.overlay_timer.timeout.connect(self._keep_overlay_top)
        self.overlay_timer.start(250)

    def _keep_overlay_top(self):
        hwnd = int(self.winId())
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        required = (
            win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_LAYERED
            | win32con.WS_EX_NOACTIVATE
        )
        if ex_style & required != required:
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style | required)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE
            | win32con.SWP_NOSIZE
            | win32con.SWP_NOACTIVATE
            | win32con.SWP_SHOWWINDOW,
        )

    def _handle_keys(self):
        open_pressed = keyboard.is_pressed("num plus")
        close_pressed = keyboard.is_pressed("num -")
        if open_pressed and not self._last_open_key:
            self.request_full_scan()
        if close_pressed and not self._last_close_key:
            self.close()
        self._last_open_key = open_pressed
        self._last_close_key = close_pressed

    def on_snapshot(self, snap):
        self.snapshot = snap

    def closeEvent(self, event):
        self.reader.stop()
        super().closeEvent(event)

    def render_frame(self):
        self._handle_keys()
        cam = self.snapshot["camera"]
        if cam["view"] and any(cam["view"]):
            apply_game_camera(self.canvas3D, cam["pos"], cam["view"], cam["proj"], z_near=0.1, z_far=10000.0)
            self.radar.setCenterPos(cam["pos"])
            self.radar.setCenterYaw(yaw_from_view(cam["view"]))
        cam_pos = cam["pos"]

        for ent in self.snapshot["players"]:
            pos = ent.get("position")
            if not pos:
                continue
            head_pos = list.copy(pos)
            head_pos[2] += 1.7
            
            distance = math.dist(cam_pos, head_pos)
            if distance < 1:
                continue

            color = ent_color(ent["type"])
            self.radar.addEntity(str(ent["addr"]), RadarEntity("", head_pos, color=color))
            self.canvas3D.addPoint3D(str(ent["addr"]), Point3D(head_pos, 50, color=color))
            if self.show_distance:
                self.canvas3D.addText3D(
                    f"text-{ent['addr']}",
                    Text3D(head_pos, f"{distance:.0f}m", color=color),
                )

        for ent in self.snapshot["bosses"]:
            pos = ent.get("position")
            if not pos:
                continue
            color = ent_color(ent["type"])
            self.radar.addEntity(str(ent["addr"]), RadarEntity("", pos, color=color))
            self.canvas3D.addPoint3D(str(ent["addr"]), Point3D(pos, 50, color=color))
            if self.show_distance:
                distance = math.dist(cam_pos, pos)
                self.canvas3D.addText3D(
                    f"text-{ent['addr']}",
                    Text3D(pos, f"{distance:.0f}m", color=color),
                )

        self.radar.update()
        self.canvas3D.update()

    def request_full_scan(self):
        self.reader.request_full_scan()

    def set_camera_hz(self, hz):
        self.reader.camera_ms = max(10, int(1000 / max(0.1, float(hz))))

    def set_update_hz(self, hz):
        self.reader.update_ms = max(100, int(1000 / max(0.1, float(hz))))

    def set_radar_range(self, radius):
        self.radar_range = float(radius)
        self.radar.setRadarRadius(self.radar_range)

    def set_radar_visible(self, show):
        self.radar.setVisible(bool(show))

    def set_crosshair(self, show):
        self.canvas3D.setCrosshair(bool(show))

    def set_show_distance(self, show):
        self.show_distance = bool(show)

    def set_window_geometry(self, posx, posy, width, height):
        self.setGeometry(int(posx), int(posy), int(width), int(height))

    def center_window(self):
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

    def camera_text(self):
        pos = self.snapshot["camera"]["pos"]
        return f"{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}"


if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass



    app = QApplication(sys.argv)
    window = HuntESPWindow()
    window.show()
    sys.exit(app.exec())
