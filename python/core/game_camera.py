"""canvas3D 相机接口：把游戏的相机矩阵转换成 canvas3D 支持的参数。

canvas3D 不直接支持设置投影/视图矩阵，这里提供两个接口：
  apply_game_camera(..., mode="decompose")  拆成 pos + 欧拉角 + fov，走内部管线
  apply_game_camera(..., mode="direct")     直接注入 4x4 视图/投影矩阵
"""

import math
import warnings

import numpy as np
from scipy.spatial.transform import Rotation


def fov_from_projection(projection, fallback=90.0) -> float:
    """从游戏投影矩阵提取垂直 FOV（度）。"""
    if projection is None or len(projection) < 16:
        return fallback
    scale = abs(projection[5])
    if scale < 1e-9:
        return fallback
    return math.degrees(2.0 * math.atan(1.0 / scale))


def yaw_from_view(view, degrees=True):
    """从视图矩阵解算雷达用的世界朝向 yaw（度）。

    forward 取 view matrix 的第三行（world -> camera 的 Z 轴），
    即相机在世界 X/Y 平面上的朝向。雷达旋转基准是 bearing + 180 度。
    """
    if view is None or len(view) < 16 or not any(view):
        return 0.0
    fx, fy = view[2], view[6]
    yaw = math.atan2(fy, fx) + math.pi
    if degrees:
        return math.degrees(yaw) % 360.0
    return yaw % (2.0 * math.pi)


def decompose_game_camera(camera_pos, view, projection, seq="xyz"):
    """把游戏相机矩阵拆成 canvas3D 的 (pos, [roll, pitch, yaw], fov)。

    view 是 16 个 float，布局与 C++ WorldToScreen 一致（world -> camera）。
    先取 camera -> world 旋转，再换成 canvas3D 的相机基：
    forward=+X, right=-Y, up=+Z。
    """
    pos = list(camera_pos) if camera_pos is not None else [0.0, 0.0, 0.0]
    if view is None or len(view) < 16 or not any(view):
        return pos, [0.0, 0.0, 0.0], fov_from_projection(projection)

    r_wc = np.array(
        [
            [view[0], view[4], view[8]],
            [view[1], view[5], view[9]],
            [view[2], view[6], view[10]],
        ],
        dtype=np.float32,
    )
    r_cw = r_wc.T
    forward = r_cw[:, 2]
    right = r_cw[:, 0]
    up = r_cw[:, 1]

    basis = np.column_stack([forward, -right, up])
    norms = np.linalg.norm(basis, axis=0)
    if np.any(norms < 1e-6):
        return pos, [0.0, 0.0, 0.0], fov_from_projection(projection)
    basis = basis / norms
    if np.linalg.det(basis) < 0:
        # 基不是右手系时翻转 forward，保证 Rotation 能正常分解
        basis[:, 0] = -basis[:, 0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        euler = Rotation.from_matrix(basis).as_euler(seq, degrees=True)
    return pos, list(euler), fov_from_projection(projection)


def apply_game_camera(
    canvas,
    camera_pos,
    view,
    projection,
    z_near=0.1,
    z_far=10000.0,
    mode="decompose",
):
    """把游戏相机数据应用到 canvas3D。mode 见模块注释。"""
    if view is None or len(view) < 16 or not any(view):
        return
    if mode == "direct":
        canvas.setViewProjectionMatrix(
            np.array(view, dtype=np.float32).reshape(4, 4),
            np.array(projection, dtype=np.float32).reshape(4, 4),
        )
        return
    pos, ang, fov = decompose_game_camera(camera_pos, view, projection)
    canvas.setCamPosAng(pos, ang)
    canvas.setScreen(fov, z_near, z_far)
