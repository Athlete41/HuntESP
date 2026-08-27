import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QPointF, QLineF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from core import math3d


class Point3D:
    """
    三维空间中的一个点（含可选大小和颜色）。

    属性：
        pos : np.ndarray，形状 (3,)，点的三维坐标
        size : float，点的大小（可选）
        color : QColor 或 str，点的颜色（可选）
    """
    def __init__(self, pos: np.ndarray | list | tuple, size: float = None, color: QColor | str = None):
        # 转换并验证 pos 必须为长度为 3 的向量
        if not isinstance(pos, np.ndarray):
            pos = np.array(pos)
        if pos.shape != (3,):
            raise ValueError(f"Point3D position must have exactly 3 elements, got {pos.shape}")
        self.pos = pos
        self.size = size
        self.color = color

class Lines3D:
    """
    三维空间中的一组点（按顺序两两成对构成线段）。

    输入点集应为形状 (N, 3) 的二维数组，每行一个三维点。
    存储时自动转换为齐次坐标并转置为 (4, N) 以便直接与 MVP 矩阵相乘。
    """
    def __init__(self, points: np.ndarray | list | tuple, color: QColor | str = None):
        # 转换并验证 points 必须为 (N, 3)
        if not isinstance(points, np.ndarray):
            points = np.array(points)
        if points.ndim != 2:
            raise ValueError("Lines3D points must be a 2D array")
        if points.shape[1] != 3:
            raise ValueError(f"Each point must have exactly 3 components, got {points.shape[1]}")
        # 转为齐次坐标 (N, 4) 并转置为 (4, N)
        hom = np.hstack((points, np.ones((points.shape[0], 1))))
        self.points = hom.T  # 形状 (4, N)
        self.color = color

class WireFrameBox2D3D:
    """
    三维空间中的二维线框矩形框（位置 + 宽高）。
    """
    def __init__(self, pos: np.ndarray | list | tuple, width: float = None, height: float = None, color=None):
        if not isinstance(pos, np.ndarray):
            pos = np.array(pos)
        if pos.shape != (3,):
            raise ValueError(f"WireFrameBox2D3D position must have exactly 3 elements, got {pos.shape}")
        self.pos = pos
        self.width = width
        self.height = height
        self.color = color

class WireFrameBox3D:
    """
    三维轴对齐包围盒，生成 12 条棱的端点，存储为 (4, 24) 数组。
    每列是一个齐次点 (x,y,z,1)，24 列按顺序：
    线1起点, 线1终点, 线2起点, 线2终点, ...
    可直接用于 MVP @ self.points。
    """
    def __init__(self, pos, ang, min, max, color=None):
        # 验证并存储四个三维向量
        for name, val in [("min", min), ("max", max), ("pos", pos), ("ang", ang)]:
            if not isinstance(val, np.ndarray):
                val = np.array(val)
            if val.shape != (3,):
                raise ValueError(f"{name} must have exactly 3 elements")
            setattr(self, name, val)

        self.color = color

        # 提取边界标量
        xmin, ymin, zmin = self.min
        xmax, ymax, zmax = self.max

        self.points = np.array([
            [xmin, xmax, xmin, xmax, xmin, xmax, xmin, xmax, xmin, xmin, xmax, xmax, xmin, xmin, xmax, xmax, xmin, xmin, xmax, xmax, xmin, xmin, xmax, xmax],
            [ymin, ymin, ymax, ymax, ymin, ymin, ymax, ymax, ymin, ymax, ymin, ymax, ymin, ymax, ymin, ymax, ymin, ymin, ymin, ymin, ymax, ymax, ymax, ymax],
            [zmin, zmin, zmin, zmin, zmax, zmax, zmax, zmax, zmin, zmin, zmin, zmin, zmax, zmax, zmax, zmax, zmin, zmax, zmin, zmax, zmin, zmax, zmin, zmax],
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        ])

class Text3D:
    """
    三维空间中的文字标签。

    属性：
        pos : 三维向量，文字位置
        text : str，显示的文字
        color : 颜色
    """
    def __init__(self, pos: np.ndarray | list | tuple, text: str, color=None):
        if not isinstance(pos, np.ndarray):
            pos = np.array(pos)
        if pos.shape != (3,):
            raise ValueError(f"Text3D position must have exactly 3 elements, got {pos.shape}")
        self.pos = pos
        self.text = text
        self.color = color


class Qt6Numpy3DCanvas(QWidget):
    """
    注意: 相机看向 X 正轴, 右手坐标系, Y 轴向左, Z 轴向上
    """

    CROSSHAIR_LENGTH = 10
    CROSSHAIR_COLOR = QColor(0, 255, 50)
    DEFAULT_COLOR = QColor(255, 50, 50)
    DEFAULT_SIZE = 10.0
    DEFAULT_FONT = QFont("Arial", 12)

    COLOR_X = QColor(255, 0, 0)
    COLOR_Y = QColor(0, 255, 0)
    COLOR_Z = QColor(0, 0, 255)
    AXIS_X = np.array([1.0, 0.0, 0.0])
    AXIS_Y = np.array([0.0, 1.0, 0.0])
    AXIS_Z = np.array([0.0, 0.0, 1.0])

    def __init__(self, parent=None):
        super().__init__(parent)

        # 默认外旋 roll, pitch, yaw, 使用度为单位
        self.angSeq = 'xyz' 
        self.angIsDeg = True
        self.antialiasing = True
        self.enableCrosshair = True
        self.enableDebugCoordinate = False
        self._useExternalMatrix = False


        self._camPos = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self._camAng = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self._fov = 90.0
        self._zNear = 0.1
        self._zFar = 1000.0
        self._viewMatrix = self._buildViewMatrix()
        self._projectionMatrix = self._buildProjectionMatrix()
        self._VPMatrix = self._projectionMatrix @ self._viewMatrix[1]


        self._point3DDict = {}
        self._lines3DDict = {}
        self._wireFrameBox2D3Dict = {}
        self._wireFrameBox3DDict = {}
        self._text3DDict = {}

    def setDebugCoordinate(self, enable: bool):
        self.enableDebugCoordinate = enable

    def setAngSeq(self, seq: str):
        self.angSeq = seq

    def setAngIsDeg(self, isDeg: bool):
        self.angIsDeg = isDeg

    def setCrosshair(self, enable):
        self.enableCrosshair = enable

    def getCrosshair(self):
        return self.enableCrosshair

    def setAntialiasing(self, antialiasing):
        self.antialiasing = antialiasing


    def setCamPosAng(self, pos, ang):
        self._useExternalMatrix = False
        self._camPos = np.array(pos, dtype=np.float32)
        self._camAng = np.array(ang, dtype=np.float32)

        self._viewMatrix = self._buildViewMatrix()
        self._projectionMatrix = self._buildProjectionMatrix()
        self._VPMatrix = self._projectionMatrix @ self._viewMatrix[1]

    def setScreen(self, fov=90.0, zNear=0.1, zFar=1000.0):
        self._useExternalMatrix = False
        self._fov = fov
        self._zNear = zNear
        self._zFar = zFar

        self._viewMatrix = self._buildViewMatrix()
        self._projectionMatrix = self._buildProjectionMatrix()
        self._VPMatrix = self._projectionMatrix @ self._viewMatrix[1]

    def setViewProjectionMatrix(self, view_matrix, projection_matrix):
        """外部接口：直接注入视图/投影矩阵（4x4），调用 setCamPosAng/setScreen 后切回内部管线。"""
        view = np.array(view_matrix, dtype=np.float32)
        proj = np.array(projection_matrix, dtype=np.float32)
        if view.shape != (4, 4) or proj.shape != (4, 4):
            raise ValueError("view_matrix and projection_matrix must be (4, 4)")
        self._viewMatrix = (np.eye(4, dtype=np.float32), view)
        self._projectionMatrix = proj
        self._VPMatrix = proj @ view
        self._useExternalMatrix = True

    def _buildProjectionMatrix(self):
        """
        创建透视投影矩阵, 相机看向 X 正轴, Y 轴向左, Z 轴向上, 右手坐标系

        参数:
            fovDeg: float 视野角度（度）
            aspect: float 宽高比
            near: float 近裁剪平面距离, 默认0.1
            far: float 远裁剪平面距离, 默认1000.0
        返回:
            (4,4) ndarray 透视投影矩阵
        [(f + n) / (f - n), 0.0                            , 0.0               , -(2.0 * f * n) / (f - n)]
        [0.0              , 1.0 / (tan(fov/2.0) * aspect)  , 0.0               , 0.0                    ]
        [0.0              , 0.0                            , 1.0 / tan(fov/2.0), 0.0                    ]
        [1.0              , 0.0                            , 0.0               , 0.0                    ]
        """
        aspect = self.width() / self.height()
        fov_rad = np.radians(self._fov) if self.angIsDeg else self._fov
        tan_half = np.tan(fov_rad / 2.0)
        f = self._zFar
        n = self._zNear

        P = np.zeros((4, 4), dtype=np.float32)
        P[0, 0] = (f + n) / (f - n)
        P[1, 1] = 1.0 / (tan_half * aspect)
        P[2, 2] = 1.0 / tan_half
        P[0, 3] = -(2.0 * f * n) / (f - n)
        P[3, 0] = 1.0

        return P

    def _buildViewMatrix(self):
        """
        创建视图矩阵, 相机看向 X 正轴, Y 轴向左, Z 轴向上, 右手坐标系

        参数:
            pos: (3,) ndarray 相机位置
            ang: (3,) ndarray 相机角度（度）
        返回:
            (4,4) ndarray 视图矩阵
        """

        V = math3d.makeTransformFromEuler(self._camPos, np.array([1.0, 1.0, 1.0]), self._camAng, self.angSeq, self.angIsDeg)
        return (V, math3d.getInverseFast(V))

    def transformPoint(self, MVP, pos):
        """
        将单个3D点转换为屏幕坐标 (QPointF)，若点超出裁剪面 或 depth = 0 则返回 None
        """

        pt_c = MVP @ np.append(pos, 1.0)
        depth = pt_c[3]
        if depth == 0:
            return None, None

        pt_c = pt_c / depth
        if abs(pt_c[0]) > 1:
            return None, None

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        dx, dy = pt_c[1], pt_c[2]

        return QPointF(cx - dx * w * 0.5, cy - dy * h * 0.5), depth

    def transformLinesDirect(self, MVP, points) -> list[QLineF]:
        """
        将多个点（成对构成线段）转换为屏幕坐标线段
        输入: points 形状 (4, N)
        返回: list[QLineF]，若点数奇数则最后一个点丢弃
        """

        pts_c = MVP @ points
        depths = pts_c[3, :]
        with np.errstate(divide='ignore', invalid='ignore'):
            pts_c = pts_c / depths
        
        # 提取归一化屏幕偏移量 (y_n, z_n)
        y_n = pts_c[1, :]
        z_n = pts_c[2, :]
        
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        screen_x = cx - y_n * w * 0.5
        screen_y = cy - z_n * h * 0.5
        
        # 生成 QPointF 列表
        points_screen = [QPointF(screen_x[i], screen_y[i]) for i in range(len(screen_x))]
        
        # 两两配对成线段（偶数个点）
        n = len(points_screen)
        lines = []
        for i in range(0, n - 1, 2):   # 步长为2，跳过最后一个若奇数
            lines.append(QLineF(points_screen[i], points_screen[i + 1]))
        
        return lines

    def transformLines(self, MVP, points) -> list[QLineF]:
        """
        将多个点（成对构成线段）转换为屏幕坐标线段
        输入: points 形状 (N, 3)
        返回: list[QLineF]，若点数奇数则最后一个点丢弃
        """
        return self.transformLinesDirect(MVP, np.hstack((points, np.ones((points.shape[0], 1)))).T)

    def addPoint3D(self, id, point):
        if not isinstance(point, Point3D):
            raise ValueError("point must be a Point3D instance")
        self._point3DDict[id] = point
    
    def addLines3D(self, id, lines):
        if not isinstance(lines, Lines3D):
            raise ValueError("lines must be a Lines3D instance")
        self._lines3DDict[id] = lines

    def addText3D(self, id, text):
        if not isinstance(text, Text3D):
            raise ValueError("text must be a Text3D instance")
        self._text3DDict[id] = text

    def addWireFrameBox2D3D(self, id, box):
        if not isinstance(box, WireFrameBox2D3D):
            raise ValueError("box must be a WireFrameBox2D3D instance")
        self._wireFrameBox2D3Dict[id] = box

    def addWireFrameBox3D(self, id, box):
        if not isinstance(box, WireFrameBox3D):
            raise ValueError("box must be a WireFrameBox3D instance")
        self._wireFrameBox3DDict[id] = box

    def _drawDebugCoordinate(self, painter):
        if not self.enableDebugCoordinate:
            return

        forward = math3d.getForward(self._viewMatrix[0])

        center = self._camPos + forward * 10.0
        points = np.array([
            center, center + 5.0 * self.AXIS_X,
            center, center + 5.0 * self.AXIS_Y,
            center, center + 5.0 * self.AXIS_Z,
        ])

        lineList = self.transformLines(self._VPMatrix, points)

        painter.setPen(QPen(self.COLOR_X, 2))
        painter.drawLine(lineList[0])
        painter.setPen(QPen(self.COLOR_Y, 2))
        painter.drawLine(lineList[1])
        painter.setPen(QPen(self.COLOR_Z, 2))
        painter.drawLine(lineList[2])



    def _drawPoint3D(self, painter, point: Point3D) -> bool:
        pos, color = point.pos, point.color

        p, depth = self.transformPoint(self._VPMatrix, pos)
        if p is not None:
            if isinstance(color, str):
                color = QColor(color)
            elif color is None:
                color = self.DEFAULT_COLOR

            painter.setPen(QPen(color, 2))

            size = point.size if point.size is not None else self.DEFAULT_SIZE
            sizeX = size / max(abs(depth), 0.001) * self._projectionMatrix[1, 1]  # 考虑FOV等因素
            sizeY = size / max(abs(depth), 0.001) * self._projectionMatrix[2, 2]
            painter.drawEllipse(p, sizeX, sizeY)

            return True
        else:
            return False

    def _drawLines3D(self, painter, lines: Lines3D):
        points, color = lines.points, lines.color

        
        lineList = self.transformLinesDirect(self._VPMatrix, points)
        if len(lineList) > 0:
            if isinstance(color, str):
                color = QColor(color)
            elif color is None:
                color = self.DEFAULT_COLOR
            painter.setPen(QPen(color, 2))

            for line in lineList:
                painter.drawLine(line)
            return True
        else:
            return False

    def _drawWireFrameBox2D3D(self, painter, box: WireFrameBox2D3D) -> bool:
        width, height, pos, color = box.width, box.height, box.pos, box.color

        p, depth = self.transformPoint(self._VPMatrix, pos)
        if p is not None:
            width = width if width is not None else self.DEFAULT_SIZE
            height = height if height is not None else self.DEFAULT_SIZE

            width = width / max(abs(depth), 0.001) * self._projectionMatrix[1, 1]
            height = height / max(abs(depth), 0.001) * self._projectionMatrix[2, 2]

            if isinstance(color, str):
                color = QColor(color)
            elif color is None:
                color = self.DEFAULT_COLOR

            painter.setPen(QPen(color, 2))
            painter.drawRect(QRectF(p.x(), p.y(), width, height))
            return True
        else:
            return False

    def _drawText3D(self, painter, text: Text3D) -> bool:
        pos, color = text.pos, text.color

        p, _ = self.transformPoint(self._VPMatrix, pos)
        if p is not None:
            if isinstance(color, str):
                color = QColor(color)
            elif color is None:
                color = self.DEFAULT_COLOR

            painter.setPen(QPen(color, 2))
            painter.setFont(self.DEFAULT_FONT)
            painter.drawText(p, text.text)
            return True
        else:
            return False

    def _drawWireFrameBox3D(self, painter, box: WireFrameBox3D) -> bool:
        points, pos, ang, color = box.points, box.pos, box.ang, box.color
        model = math3d.makeTransformFromEuler(pos, np.array([1.0, 1.0, 1.0]), ang, self.angSeq, self.angIsDeg)

        lineList = self.transformLinesDirect(self._VPMatrix @ model, points)
        if len(lineList) > 0:
            if isinstance(color, str):
                color = QColor(color)
            elif color is None:
                color = self.DEFAULT_COLOR

            painter.setPen(QPen(color, 2))
            for line in lineList: 
                painter.drawLine(line)
            return True
        else:
            return False

    def _drawCrosshair(self, painter):
        if not self.enableCrosshair:
            return

        cx, cy = self.width() / 2, self.height() / 2
        painter.setPen(QPen(self.CROSSHAIR_COLOR, 1))
        painter.drawLine(QPointF(cx - self.CROSSHAIR_LENGTH, cy), QPointF(cx + self.CROSSHAIR_LENGTH, cy))
        painter.drawLine(QPointF(cx, cy - self.CROSSHAIR_LENGTH), QPointF(cx, cy + self.CROSSHAIR_LENGTH))

    def paintEvent(self, event):
        painter = QPainter(self)

        if self.antialiasing:
            painter.setRenderHint(QPainter.Antialiasing)

        self._drawCrosshair(painter)

        if self._VPMatrix is None:
            return

        self._drawDebugCoordinate(painter)

        for id, point in self._point3DDict.items():
            self._drawPoint3D(painter, point)

        for id, lines in self._lines3DDict.items():
            self._drawLines3D(painter, lines)

        for id, text in self._text3DDict.items():
            self._drawText3D(painter, text)

        for id, box in self._wireFrameBox2D3Dict.items():
            self._drawWireFrameBox2D3D(painter, box)

        for id, box in self._wireFrameBox3DDict.items():
            self._drawWireFrameBox3D(painter, box)


        self._point3DDict.clear()
        self._lines3DDict.clear()
        self._text3DDict.clear()
        self._wireFrameBox2D3Dict.clear()
        self._wireFrameBox3DDict.clear()

        painter.end()

    def resizeEvent(self, event):
        if not self._useExternalMatrix:
            self._viewMatrix = self._buildViewMatrix()
            self._projectionMatrix = self._buildProjectionMatrix()
            self._VPMatrix = self._projectionMatrix @ self._viewMatrix[1]
        return super().resizeEvent(event)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer


    app = QApplication(sys.argv)
    window = Qt6Numpy3DCanvas()
    window.show()
    window.setCamPosAng([0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
    window.setScreen(90, 0.1, 1000.0)

    t = 0
    def timerTask():
        global t
        t += 0.1
        window.addPoint3D("point1", Point3D([5.0 + np.sin(t) * 5.0, 0.0, 0.0], color="red"))
        window.addPoint3D("point2", Point3D([5.0, np.cos(t) * 5.0, np.sin(t) * 5.0], color="blue"))
        window.addLines3D("lines1", Lines3D([[5.0, -5.0, -5.0], [5.0, -5.0, 5]], color="green"))
        window.addLines3D("lines2", Lines3D([[5.0, -5.0, 5.0], [5.0, 5.0, 5.0]], color="green"))
        window.addLines3D("lines3", Lines3D([[5.0, 5.0, 5.0], [5.0, 5.0, -5.0]], color="green"))
        window.addLines3D("lines4", Lines3D([[5.0, 5.0, -5.0], [5.0, -5.0, -5.0]], color="green"))

        window.addWireFrameBox2D3D("box1", WireFrameBox2D3D([5.0 + np.sin(t) * 5.0, 5.0, 5.0], 70.0, 70.0, color="red"))
        window.addText3D("text1", Text3D([5.0 + np.sin(t) * 5.0, 5.0, 5.0], "hello world", color="blue"))
        window.addWireFrameBox3D("box2", WireFrameBox3D([20.0, 0.0, 0.0], [10.0, 10.0, 0.0], [-5.0, -5.0, -5.0], [5.0, 5.0, 5.0], color="red"))


        window.update()

    timer = QTimer()
    timer.timeout.connect(timerTask)
    timer.start(30)

    sys.exit(app.exec())

