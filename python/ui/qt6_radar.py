import sys
import math
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen, QFont

class RadarEntity:
    """
    雷达实体，表示一个可显示在雷达上的目标。
    """

    def __init__(self, name, pos=None, yaw=None, color=None):
        """
        初始化雷达实体。

        :param name: 实体名称（字符串）
        :param pos: 位置，应包含至少 2 个元素（x, y[, z]），世界坐标
        :param yaw: 朝向角（度），相对于世界坐标系，float 类型
        :param color: QColor 对象或可转换为 QColor 的颜色值，None 时使用默认颜色
        :raises ValueError: 当 pos 长度小于 2 或 yaw 不是数字时抛出
        """
        if pos is not None:
            if len(pos) < 2:
                raise ValueError("pos must be a sequence of length at least 2 (x, y)")
        if yaw is not None and not isinstance(yaw, (int, float)):
            raise ValueError("yaw must be a number")

        self.name = name
        self.color = color
        self.pos = pos
        self.yaw = yaw


class Qt6RadarCanvas(QWidget):
    """
    雷达画布，用于显示中心点、网格、雷达范围及实体。
    """

    pointSize = 5
    dirLength = 15
    HGrid = 10
    VGrid = 10

    GRID_COLOR = QColor(120, 120, 120)
    CAM_COLOR = QColor(0, 255, 0)
    ENTITY_COLOR = QColor(255, 50, 50)
    RAR_RANGE_COLOR = QColor(0, 150, 255, 60)   # 半透明

    def __init__(self, parent=None):
        """
        初始化雷达画布。

        :param parent: 父窗口部件
        """
        super().__init__(parent)
        self.centerPos = (0, 0)
        self.centerYaw = 0
        self.entities = {}
        self.radar_radius = 1000
        self.radar_mode = "Dynamicness"  # "Dynamicness" 或 "Fixedness"
        self.enableGrid = False
        self.enableBorder = True

    def setEnableBorder(self, enableBorder):
        """设置是否绘制雷达边界圆。"""
        self.enableBorder = enableBorder

    def setEnableGrid(self, enableGrid):
        """设置是否绘制网格线。"""
        self.enableGrid = enableGrid


    def setRadarRadius(self, radius):
        """设置雷达探测半径（世界单位）。"""
        
        self.radar_radius = max(radius, 1)

    def setCenterPos(self, pos):
        """
        设置雷达中心点位置（世界坐标）。

        :param pos: 至少包含 (x, y) 的序列
        :raises ValueError: 若 pos 长度不足 2
        """
        if len(pos) < 2:
            raise ValueError("pos must have at least 2 elements (x, y)")
        self.centerPos = pos

    def setCenterYaw(self, yaw):
        """
        设置雷达中心点的朝向角（度，世界坐标系）。

        :param yaw: 浮点数角度
        :raises ValueError: 若 yaw 不是数字
        """
        if yaw is not None and not isinstance(yaw, (int, float)):
            raise ValueError("Yaw must be a number")
        self.centerYaw = yaw

    def setCenterPosYaw(self, pos, yaw):
        """
        同时设置雷达中心位置和朝向。

        :param pos: 至少包含 (x, y) 的序列
        :param yaw: 浮点数角度
        :raises ValueError: 若 pos 长度不足 2 或 yaw 不是数字
        """
        if len(pos) < 2:
            raise ValueError("pos must have at least 2 elements (x, y)")
        if yaw is not None and not isinstance(yaw, (int, float)):
            raise ValueError("Yaw must be a number")
        self.centerPos = pos
        self.centerYaw = yaw

    def addEntity(self, idx, entity):
        """
        添加绘制实体。

        :param entity: RadarEntity 实例
        :raises ValueError: 若 entity 不是 RadarEntity 类型
        """
        if not isinstance(entity, RadarEntity):
            raise ValueError("Entity must be a RadarEntity instance")
        self.entities[idx] = entity


    def drawCenterPoint(self, painter):
        """
        绘制中心点及其方向指示线。

        :param painter: QPainter 实例
        """
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2

        painter.setBrush(QColor(0, 255, 0))
        painter.setPen(QPen(self.CAM_COLOR, 2))
        painter.drawEllipse(cx - self.pointSize / 2, cy - self.pointSize / 2,
                            self.pointSize, self.pointSize)

        if self.radar_mode == "Fixedness":
            if self.centerYaw is not None:
                yaw = self.centerYaw
                length = self.dirLength
                dx = math.cos(math.radians(yaw)) * length
                dy = -math.sin(math.radians(yaw)) * length
                painter.setPen(QPen(self.CAM_COLOR, 2))
                painter.drawLine(cx, cy, cx + dx, cy + dy)
        else:  # Dynamicness
            length = self.dirLength
            painter.setPen(QPen(self.CAM_COLOR, 2))
            painter.drawLine(cx, cy, cx, cy - length)

    def drawEntity(self, painter, entity):
        """
        绘制单个实体（点 + 名称 + 朝向线）。

        :param painter: QPainter 实例
        :param entity: RadarEntity 实例
        """
        if not self.centerPos or not entity.pos:
            return

        center_pos = self.centerPos
        ent_pos = entity.pos
        ent_ang_yaw = entity.yaw
        ent_name = entity.name
        ent_color = entity.color if entity.color is not None else self.ENTITY_COLOR

        dx = ent_pos[0] - center_pos[0]
        dy = ent_pos[1] - center_pos[1]

        if self.radar_mode == "Dynamicness":
            if self.centerYaw is not None:
                ang = math.atan2(dy, dx) - math.radians(self.centerYaw) + math.pi / 2
                dist = math.hypot(dx, dy)
                dx = math.cos(ang) * dist
                dy = math.sin(ang) * dist

                if ent_ang_yaw is not None:
                    ent_ang_yaw = ent_ang_yaw - self.centerYaw + 90

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        scale = min(w, h) / 2 / self.radar_radius

        sx = cx + dx * scale
        sy = cy - dy * scale

        if abs(sx - cx) > w / 2 or abs(sy - cy) > h / 2:
            return

        painter.setBrush(ent_color)
        painter.setPen(QPen(ent_color, 2))
        painter.drawEllipse(sx - self.pointSize / 2, sy - self.pointSize / 2,
                            self.pointSize, self.pointSize)

        if ent_name:
            painter.drawText(sx - 10, sy - 10, ent_name)

        if ent_ang_yaw is not None:
            length = self.dirLength
            dx = math.cos(math.radians(ent_ang_yaw)) * length
            dy = -math.sin(math.radians(ent_ang_yaw)) * length
            painter.setPen(QPen(ent_color, 2))
            painter.drawLine(sx, sy, sx + dx, sy + dy)

    def drawBorder(self, painter):
        """
        绘制雷达边界圆。

        :param painter: QPainter 实例
        """
        if not self.enableBorder:
            return

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        scale = min(w, h) / 2 / self.radar_radius

        painter.setPen(QPen(self.RAR_RANGE_COLOR, 2))
        painter.drawEllipse(cx - self.radar_radius * scale, cy - self.radar_radius * scale,
                            self.radar_radius * scale * 2, self.radar_radius * scale * 2)


    def drawGrid(self, painter):
        """
        绘制网格线及刻度标签。
        垂直网格线（x 方向）的标签显示在底部，水平网格线（y 方向）的标签显示在右侧。
        """
        if not self.enableGrid:
            return
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        scale = min(w, h) / 2 / self.radar_radius
        radius_px = self.radar_radius * scale

        # 计算步长（世界坐标单位）
        h_step = self.radar_radius / (self.HGrid // 2) if self.HGrid > 1 else self.radar_radius
        v_step = self.radar_radius / (self.VGrid // 2) if self.VGrid > 1 else self.radar_radius

        painter.setPen(QPen(self.GRID_COLOR, 1, Qt.PenStyle.DashLine))
        font = QFont("Arial", 8)
        painter.setFont(font)

        # 垂直网格线（x 固定）
        half_h = self.HGrid // 2
        for i in range(-half_h, half_h + 1):
            x = cx + i * h_step * scale
            painter.drawLine(x, cy - radius_px, x, cy + radius_px)
            # 在底部显示刻度（仅当网格线在圆内）
            if abs(i * h_step) <= self.radar_radius:
                label = f"{i * h_step:.0f}"
                painter.drawText(x - 10, cy + radius_px + 15, label)

        # 水平网格线（y 固定）
        half_v = self.VGrid // 2
        for i in range(-half_v, half_v + 1):
            y = cy + i * v_step * scale
            painter.drawLine(cx - radius_px, y, cx + radius_px, y)
            if abs(i * v_step) <= self.radar_radius:
                # y 轴向下为正，显示的世界坐标值为 -i * v_step
                label = f"{-i * v_step:.0f}"
                painter.drawText(cx + radius_px + 5, y + 3, label)

        # 中心原点标注
        painter.setPen(QPen(self.GRID_COLOR, 2))
        painter.drawText(cx + 5, cy - 5, "0")

    def paintEvent(self, event):
        """
        重绘事件，依次绘制网格、范围、中心点、持久实体和临时实体。

        :param event: QPaintEvent
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.drawBorder(painter)
        self.drawGrid(painter)
        self.drawCenterPoint(painter)

        for entity in self.entities.values():
            self.drawEntity(painter, entity)

        self.entities.clear()

        painter.end()
        super().paintEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Qt6RadarCanvas()
    window.show()
    window.setCenterPos((0, 0, 0))
    window.setCenterYaw(0)
    window.addEntity("1", RadarEntity(name="entity1", pos=(100, 100, 100), yaw=50))

    sys.exit(app.exec())