"""Hunt DMA GUI：后台线程读坐标，UI 只画点。"""

import math
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import game_offset as off
from core.game_camera import apply_game_camera, yaw_from_view
from core.reader_thread import ReaderThread
from hunt_reader import BOSS_TYPES
from ui.qt6_canvas3d import Point3D, Qt6Numpy3DCanvas, Text3D
from ui.qt6_radar import Qt6RadarCanvas, RadarEntity

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
        camera_ms=100,
        update_ms=1000,
        scan_ms=10000,
        scan_batch_ms=10000,
        batch_size=5000,
        max_entities=99999,
        fps=30.0,
        crosshair=True,
        show_distance=True,
        radar_range=250.0,
        radar_visible=True,
        window_posx=100,
        window_posy=100,
        window_width=800,
        window_height=600,
    ):
        super().__init__()
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

    def on_snapshot(self, snap):
        self.snapshot = snap

    def closeEvent(self, event):
        self.reader.stop()
        super().closeEvent(event)

    def render_frame(self):
        cam = self.snapshot["camera"]
        if cam["view"] and any(cam["view"]):
            apply_game_camera(self.canvas3D, cam["pos"], cam["view"], cam["proj"], z_near=0.1, z_far=10000.0)
            self.radar.setCenterPos(cam["pos"])
            self.radar.setCenterYaw(yaw_from_view(cam["view"]))
        cam_pos = cam["pos"]

        for i in range(1, len(self.snapshot["players"])):
            ent = self.snapshot["players"][i]
            pos = ent.get("position")
            if not pos:
                continue
            head_pos = list.copy(pos)
            head_pos[2] += 1.7
            color = ent_color(ent["type"])
            self.radar.addEntity(str(ent["addr"]), RadarEntity("", head_pos, color=color))
            self.canvas3D.addPoint3D(str(ent["addr"]), Point3D(head_pos, 50, color=color))
            if self.show_distance:
                distance = math.dist(cam_pos, head_pos)
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
    app = QApplication(sys.argv)
    window = HuntESPWindow()
    window.show()
    sys.exit(app.exec())
