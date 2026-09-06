"""Hunt DMA GUI：后台线程读坐标，UI 只画点。"""

import math
import sys
import ctypes

from PySide6.QtCore import QTimer, Qt, QRect
from PySide6.QtGui import QColor
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
        self.geo = QRect(window_posx, window_posy, window_width, window_height)

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

        self.key_timer = QTimer(self)
        self.key_timer.timeout.connect(self._handle_keys)
        self.key_timer.start(50)

        self.fps = fps
        self.full_camera_ms = camera_ms
        self.full_update_ms = update_ms
        self.low_power = False
        self._last_g_key = False
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
        g_pressed = keyboard.is_pressed("g")
        if g_pressed and not self._last_g_key:
            if self.low_power:
                self._enter_full_power()
            else:
                self._enter_low_power()
        self._last_g_key = g_pressed

        open_pressed = keyboard.is_pressed("num plus")
        close_pressed = keyboard.is_pressed("num -")
        if open_pressed and not self._last_open_key:
            self.reader.request_full_scan()
        if close_pressed and not self._last_close_key:
            self.close()
        self._last_open_key = open_pressed
        self._last_close_key = close_pressed

    def on_snapshot(self, snap):
        if self.low_power:
            return
        self.snapshot = snap

    def closeEvent(self, event):
        self.key_timer.stop()
        self.reader.stop()
        super().closeEvent(event)

    def render_frame(self):
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

    def _enter_low_power(self):
        self.low_power = True
        overlay_timer = getattr(self, "overlay_timer", None)
        if overlay_timer is not None:
            overlay_timer.stop()
        self.render_timer.stop()
        self.reader.emit_snapshots = False
        self.reader.camera_ms = 10**9
        self.reader.update_ms = 10**9
        self.setWindowFlags(Qt.Widget)
        self.hide()
        try:
            hwnd = int(self.winId())
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            ex_style &= ~(
                win32con.WS_EX_TRANSPARENT
                | win32con.WS_EX_LAYERED
                | win32con.WS_EX_NOACTIVATE
            )
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_NOTOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE
                | win32con.SWP_NOSIZE
                | win32con.SWP_NOACTIVATE,
            )
        except Exception as exc:
            print("[low-power] style cleanup failed:", exc)
        print("[mode] low power")

    def _enter_full_power(self):
        self.low_power = False
        self.setup_overlay()
        self.render_timer.start(int(1000.0 / self.fps))
        self.reader.emit_snapshots = True
        self.reader.camera_ms = self.full_camera_ms
        self.reader.update_ms = self.full_update_ms
        self.show()
        self.raise_()
        self.setGeometry(self.geo)
        print("[mode] full power")



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
