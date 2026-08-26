"""入口：ESP 窗口 + 设置窗口 + 内嵌 Web Radar。"""

import ctypes
import json
import os
import sys

import keyboard
import win32gui
import win32con

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.radar_server import RadarServer, build_snapshot
from hunt_esp_window import HuntESPWindow


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

CONFIG_DEFAULTS = {
    "camera_hz": 10.0,
    "update_hz": 1.0,
    "radar_range": 250.0,
    "radar_visible": True,
    "crosshair": True,
    "show_distance": True
}


def load_config(path=CONFIG_PATH):
    config = dict(CONFIG_DEFAULTS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    except (OSError, ValueError):
        pass
    return config


def save_config(path, config):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        print("[config] save failed:", exc)


class SettingsWindow(QWidget):
    closed = Signal()

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.setWindowTitle("Settings")
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        read_group = QGroupBox("读取")
        read_form = QFormLayout(read_group)
        self.camera_hz_input = QLineEdit()
        self.camera_hz_input.setValidator(QDoubleValidator(0.1, 1000.0, 2, self))
        self.update_hz_input = QLineEdit()
        self.update_hz_input.setValidator(QDoubleValidator(0.1, 1000.0, 2, self))
        full_scan_button = QPushButton("强制全量扫描")
        read_form.addRow("相机更新频率 HZ", self.camera_hz_input)
        read_form.addRow("实体更新频率 HZ", self.update_hz_input)
        read_form.addRow(full_scan_button)
        layout.addWidget(read_group)

        radar_group = QGroupBox("雷达")
        radar_form = QFormLayout(radar_group)
        self.radar_check = QCheckBox("显示雷达")
        self.radar_range_input = QLineEdit()
        self.radar_range_input.setValidator(QDoubleValidator(1.0, 100000.0, 1, self))
        radar_form.addRow(self.radar_check)
        radar_form.addRow("雷达范围", self.radar_range_input)
        layout.addWidget(radar_group)

        canvas_group = QGroupBox("3D 画布")
        canvas_form = QFormLayout(canvas_group)
        self.crosshair_check = QCheckBox("显示准星")
        self.distance_check = QCheckBox("显示距离")
        self.camera_pos_label = QLabel("-")
        canvas_form.addRow(self.crosshair_check)
        canvas_form.addRow(self.distance_check)
        canvas_form.addRow("相机坐标", self.camera_pos_label)
        layout.addWidget(canvas_group)

        window_group = QGroupBox("窗口")
        window_form = QFormLayout(window_group)
        center_button = QPushButton("移到中心")
        self.posx_input = QLineEdit()
        self.posy_input = QLineEdit()
        self.width_input = QLineEdit()
        self.height_input = QLineEdit()
        for line in (self.posx_input, self.posy_input, self.width_input, self.height_input):
            line.setValidator(QIntValidator(-100000, 100000, self))
        window_form.addRow(center_button)
        window_form.addRow("窗口位置 X", self.posx_input)
        window_form.addRow("窗口位置 Y", self.posy_input)
        window_form.addRow("窗口宽度", self.width_input)
        window_form.addRow("窗口高度", self.height_input)
        layout.addWidget(window_group)

        self.camera_hz_input.editingFinished.connect(self._apply_camera_hz)
        self.update_hz_input.editingFinished.connect(self._apply_update_hz)
        full_scan_button.clicked.connect(self.main.request_full_scan)
        self.radar_check.toggled.connect(self.main.set_radar_visible)
        self.radar_range_input.editingFinished.connect(self._apply_radar_range)
        self.crosshair_check.toggled.connect(self.main.set_crosshair)
        self.distance_check.toggled.connect(self.main.set_show_distance)
        center_button.clicked.connect(self._center_window)
        self.posx_input.editingFinished.connect(self._apply_window_geometry)
        self.posy_input.editingFinished.connect(self._apply_window_geometry)
        self.width_input.editingFinished.connect(self._apply_window_geometry)
        self.height_input.editingFinished.connect(self._apply_window_geometry)

        self._camera_timer = QTimer(self)
        self._camera_timer.timeout.connect(self._refresh_camera_label)
        self._camera_timer.start(200)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def refresh_values(self):
        self.camera_hz_input.setText(f"{1000 / self.main.reader.camera_ms:.2f}")
        self.update_hz_input.setText(f"{1000 / self.main.reader.update_ms:.2f}")
        self.radar_range_input.setText(f"{self.main.radar_range:.1f}")
        self.radar_check.setChecked(self.main.radar.isVisible())
        self.crosshair_check.setChecked(self.main.canvas3D.getCrosshair())
        self.distance_check.setChecked(self.main.show_distance)
        self.posx_input.setText(str(self.main.x()))
        self.posy_input.setText(str(self.main.y()))
        self.width_input.setText(str(self.main.width()))
        self.height_input.setText(str(self.main.height()))
        self._refresh_camera_label()

    def _refresh_camera_label(self):
        self.camera_pos_label.setText(self.main.camera_text())

    def _apply_camera_hz(self):
        try:
            self.main.set_camera_hz(float(self.camera_hz_input.text()))
        except ValueError:
            pass

    def _apply_update_hz(self):
        try:
            self.main.set_update_hz(float(self.update_hz_input.text()))
        except ValueError:
            pass

    def _apply_radar_range(self):
        try:
            self.main.set_radar_range(float(self.radar_range_input.text()))
        except ValueError:
            pass

    def _apply_window_geometry(self):
        try:
            self.main.set_window_geometry(
                int(self.posx_input.text()),
                int(self.posy_input.text()),
                int(self.width_input.text()),
                int(self.height_input.text()),
            )
        except ValueError:
            pass

    def _center_window(self):
        self.main.center_window()
        self.posx_input.setText(str(self.main.x()))
        self.posy_input.setText(str(self.main.y()))


class MainWindow(HuntESPWindow):
    def __init__(
        self,
        host="127.0.0.1",
        port=8080,
        map_id="",
        static_root=None,
        broadcast_hz=5.0,
        config_path=CONFIG_PATH,
        **kwargs,
    ):
        config = load_config(config_path)
        self.config_path = config_path
        window_kwargs = {
            "camera_ms": round(1000 / max(0.1, config.get("camera_hz", 10))),
            "update_ms": round(1000 / max(0.1, config.get("update_hz", 1))),
            "radar_range": config.get("radar_range", 250.0),
            "radar_visible": config.get("radar_visible", True),
            "crosshair": config.get("crosshair", True),
            "show_distance": config.get("show_distance", True),
            "window_posx": config.get("window_posx", 0),
            "window_posy": config.get("window_posy", 0),
            "window_width": config.get("window_width", SCREEN_WIDTH),
            "window_height": config.get("window_height", SCREEN_HEIGHT),
        }
        window_kwargs.update(kwargs)
        super().__init__(**window_kwargs)
        self.setup_overlay()

        self.map_id = map_id
        self._snapshot_seq = 0
        self._last_open_key = False
        self._last_close_key = False

        # Web Radar 暂时关闭
        # if static_root is None:
        #     static_root = os.path.abspath(
        #         os.path.join(os.path.dirname(__file__), "..", "web-radar", "dist")
        #     )
        # self.server = RadarServer(
        #     static_root, host=host, port=port, broadcast_hz=broadcast_hz
        # )
        # if not os.path.isdir(static_root):
        #     print(f"[radar] static root not found: {static_root}")
        #     print("[radar] run: cd web-radar && npm ci && npm run build")
        # self.server.start()
        # print(f"[radar] http://{host}:{port}/")

        self.settings_window = SettingsWindow(self)
        self.settings_window.closed.connect(self._save_config)

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


    def on_snapshot(self, snap):
        super().on_snapshot(snap)
        # Web Radar 暂时关闭
        # if not self.server.has_clients():
        #     return
        # self._snapshot_seq += 1
        # self.server.publish(build_snapshot(snap, self.map_id, self._snapshot_seq))

    def render_frame(self):
        self._handle_keys()
        super().render_frame()

    def _handle_keys(self):
        open_pressed = keyboard.is_pressed("num plus")
        close_pressed = keyboard.is_pressed("num -")
        if open_pressed and not self._last_open_key:
            self._open_settings()
        if close_pressed and not self._last_close_key:
            self.close()
        self._last_open_key = open_pressed
        self._last_close_key = close_pressed

    def _open_settings(self):
        self.settings_window.refresh_values()
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

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

    def closeEvent(self, event):
        self.overlay_timer.stop()
        self._save_config()
        self.settings_window.close()
        # Web Radar 暂时关闭
        # self.server.stop()
        super().closeEvent(event)

    def _save_config(self):
        save_config(
            self.config_path,
            {
                "camera_hz": 1000 / self.reader.camera_ms,
                "update_hz": 1000 / self.reader.update_ms,
                "radar_range": self.radar_range,
                "radar_visible": self.radar.isVisible(),
                "crosshair": self.canvas3D.getCrosshair(),
                "show_distance": self.show_distance,
                "window_posx": self.x(),
                "window_posy": self.y(),
                "window_width": self.width(),
                "window_height": self.height(),
            },
        )


if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    app = QApplication(sys.argv)

    screen = QGuiApplication.primaryScreen()
    screen_size = screen.size()
    SCREEN_WIDTH = screen_size.width()
    SCREEN_HEIGHT = screen_size.height()

    print(f"SCREEN_WIDTH: {SCREEN_WIDTH}, SCREEN_HEIGHT: {SCREEN_HEIGHT}")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
