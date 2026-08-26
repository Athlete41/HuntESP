import numpy as np
from scipy.spatial.transform import Rotation as R


def makeTransformFromEuler(translation: np.ndarray = None, scale: np.ndarray = None, euler: np.ndarray = None, seq: str = 'xyz', degrees: bool = True) -> np.ndarray:
    """
    从平移向量和欧拉角创建4x4变换矩阵。
    参数:
        translation: (3,) ndarray 平移向量
        scale: (3,) ndarray 缩放向量 (x, y, z)
        euler: (3,) ndarray 欧拉角 (顺序由seq指定)
        seq: str 旋转顺序，默认为'xyz'
        degrees: bool 角度单位是否为度，默认为True
    返回:
        (4,4) ndarray 齐次变换矩阵
    """
    mat = np.eye(4, dtype=np.float32)
    if translation is not None:
        assert translation.shape == (3,)
        mat[:3, 3] = translation
    if euler is not None:
        assert euler.shape == (3,)
        rot = R.from_euler(seq, euler, degrees=degrees)
        mat[:3, :3] = rot.as_matrix()
    if scale is not None:
        assert scale.shape == (3,)
        mat[:3, :3] = mat[:3, :3] @ np.diag(scale)
    return mat


def makeTransformFromQuaternion(translation: np.ndarray = None, scale: np.ndarray = None,
                                quaternion: np.ndarray = None) -> np.ndarray:
    """
    从平移向量和四元数创建4x4变换矩阵。
    参数:
        translation: (3,) ndarray 平移向量
        scale: (3,) ndarray 缩放向量 (x, y, z)
        quaternion: (4,) ndarray 四元数 (x, y, z, w)
    返回:
        (4,4) ndarray 齐次变换矩阵
    """
    mat = np.eye(4, dtype=np.float32)
    if translation is not None:
        assert translation.shape == (3,)
        mat[:3, 3] = translation
    if quaternion is not None:
        assert quaternion.shape == (4,)
        rot = R.from_quat(quaternion)
        mat[:3, :3] = rot.as_matrix()
    if scale is not None:
        assert scale.shape == (3,)
        mat[:3, :3] = mat[:3, :3] @ np.diag(scale)
    return mat


def makeTransformFromMatrix(matrix: np.ndarray) -> np.ndarray:
    """
    从给定的4x4矩阵复制生成变换矩阵。
    参数:
        matrix: (4,4) ndarray 源矩阵
    返回:
        (4,4) ndarray 拷贝后的变换矩阵
    """
    assert matrix.shape == (4, 4)
    return np.array(matrix, dtype=np.float32, copy=True)


def setTranslation(mat: np.ndarray, translation: np.ndarray) -> None:
    """
    就地设置变换矩阵的平移部分。
    参数:
        mat: (4,4) ndarray 变换矩阵
        translation: (3,) ndarray 新的平移向量
    """
    assert mat.shape == (4, 4) and translation.shape == (3,)
    mat[:3, 3] = translation


def setEuler(mat: np.ndarray, euler: np.ndarray, seq: str = 'xyz', degrees: bool = True) -> None:
    """
    就地设置变换矩阵的旋转部分（欧拉角）。
    参数:
        mat: (4,4) ndarray 变换矩阵
        euler: (3,) ndarray 欧拉角
        seq: str 旋转顺序，默认为'xyz'
        degrees: bool 角度单位是否为度，默认为True
    """
    assert mat.shape == (4, 4) and euler.shape == (3,)
    # 提取当前缩放
    scale = getScale(mat)
    rot = R.from_euler(seq, euler, degrees=degrees).as_matrix()
    mat[:3, :3] = rot @ np.diag(scale)


def setQuaternion(mat: np.ndarray, quaternion: np.ndarray) -> None:
    """
    就地设置变换矩阵的旋转部分（四元数）。
    参数:
        mat: (4,4) ndarray 变换矩阵
        quaternion: (4,) ndarray 四元数 (x, y, z, w)
    """
    assert mat.shape == (4, 4) and quaternion.shape == (4,)
    # 提取当前缩放
    scale = getScale(mat)
    rot = R.from_quat(quaternion).as_matrix()
    mat[:3, :3] = rot @ np.diag(scale)


def setMatrix(mat: np.ndarray, newMat: np.ndarray) -> None:
    """
    就地替换整个变换矩阵。
    参数:
        mat: (4,4) ndarray 原变换矩阵
        newMat: (4,4) ndarray 新矩阵
    """
    assert mat.shape == (4, 4) and newMat.shape == (4, 4)
    mat[:] = newMat

def setScale(mat: np.ndarray, scale: np.ndarray) -> None:
    """
    就地设置变换矩阵的缩放部分。
    参数:
        mat: (4,4) ndarray 变换矩阵
        scale: (3,) ndarray 新的缩放向量
    """
    assert mat.shape == (4, 4) and scale.shape == (3,)
    U, s, Vh = np.linalg.svd(mat[:3, :3], full_matrices=False)
    Rmat = U @ Vh
    if np.linalg.det(Rmat) < 0:
        Rmat = -Rmat
    mat[:3, :3] = Rmat @ np.diag(scale)

def getTranslation(mat: np.ndarray) -> np.ndarray:
    """
    获取变换矩阵的平移向量（拷贝）。
    参数:
        mat: (4,4) ndarray 变换矩阵
    返回:
        (3,) ndarray 平移向量
    """
    return mat[:3, 3].copy()


def getEuler(mat: np.ndarray, seq: str = 'xyz', degrees: bool = True) -> np.ndarray:
    """
    从变换矩阵提取欧拉角。
    参数:
        mat: (4,4) ndarray 变换矩阵
        seq: str 旋转顺序，默认为'xyz'
        degrees: bool 返回角度单位是否为度，默认为True
    返回:
        (3,) ndarray 欧拉角
    """
    rot = R.from_matrix(mat[:3, :3])
    return rot.as_euler(seq, degrees=degrees)


def getQuaternion(mat: np.ndarray) -> np.ndarray:
    """
    从变换矩阵提取四元数。
    参数:
        mat: (4,4) ndarray 变换矩阵
    返回:
        (4,) ndarray 四元数 (x, y, z, w)
    """
    rot = R.from_matrix(mat[:3, :3])
    return rot.as_quat()

def getScale(mat: np.ndarray) -> np.ndarray:
    """
    从变换矩阵提取缩放向量。
    参数:
        mat: (4,4) ndarray 变换矩阵
    返回:
        (3,) ndarray 缩放向量 (x, y, z)
    """
    assert mat.shape == (4, 4)
    _, s, _ = np.linalg.svd(mat[:3, :3], full_matrices=False)
    return s


def applyRotationByEuler(mat: np.ndarray, euler: np.ndarray, seq: str = 'xyz', degrees: bool = True) -> None:
    """
    在现有旋转基础上左乘一个欧拉角旋转（即局部坐标系旋转）。
    参数:
        mat: (4,4) ndarray 变换矩阵
        euler: (3,) ndarray 欧拉角
        seq: str 旋转顺序，默认为'xyz'
        degrees: bool 角度单位是否为度，默认为True
    """
    assert mat.shape == (4, 4) and euler.shape == (3,)
    delta = R.from_euler(seq, euler, degrees=degrees)
    rot = delta * R.from_matrix(mat[:3, :3])
    mat[:3, :3] = rot.as_matrix()


def applyRotationByQuaternion(mat: np.ndarray, quaternion: np.ndarray) -> None:
    """
    在现有旋转基础上左乘一个四元数旋转（即局部坐标系旋转）。
    参数:
        mat: (4,4) ndarray 变换矩阵
        quaternion: (4,) ndarray 四元数 (x, y, z, w)
    """
    assert mat.shape == (4, 4) and quaternion.shape == (4,)
    delta = R.from_quat(quaternion)
    rot = delta * R.from_matrix(mat[:3, :3])
    mat[:3, :3] = rot.as_matrix()


def invertInPlace(mat: np.ndarray) -> None:
    """
    就地求逆（通用分块求逆，支持旋转、缩放、切变，只要左上3x3可逆）。
    参数:
        mat: (4,4) ndarray 变换矩阵，将被原地修改为其逆矩阵
    """
    Rmat = mat[:3, :3]
    t = mat[:3, 3]
    R_inv = np.linalg.inv(Rmat)
    mat[:3, :3] = R_inv
    mat[:3, 3] = -R_inv @ t


def getInverse(mat: np.ndarray) -> np.ndarray | None:
    """
    返回逆矩阵（通用分块求逆），若奇异则返回None。
    参数:
        mat: (4,4) ndarray 变换矩阵
    返回:
        (4,4) ndarray 逆矩阵，或None（不可逆时）
    """
    try:
        Rmat = mat[:3, :3]
        t = mat[:3, 3]
        R_inv = np.linalg.inv(Rmat)
        inv = np.eye(4, dtype=np.float32)
        inv[:3, :3] = R_inv
        inv[:3, 3] = -R_inv @ t
        return inv
    except np.linalg.LinAlgError:
        return None


def invertInPlaceFast(mat: np.ndarray) -> None:
    """
    就地求逆（快速版，仅适用于旋转部分为正交矩阵的刚体变换）。
    利用正交矩阵逆等于转置，不支持缩放或切变。
    参数:
        mat: (4,4) ndarray 变换矩阵（仅纯旋转+平移）
    """
    Rmat = mat[:3, :3]
    t = mat[:3, 3]
    R_inv = Rmat.T
    mat[:3, :3] = R_inv
    mat[:3, 3] = -R_inv @ t


def getInverseFast(mat: np.ndarray) -> np.ndarray | None:
    """
    返回逆矩阵（快速版，仅适用于旋转部分为正交矩阵的刚体变换）。
    利用正交矩阵逆等于转置，不支持缩放或切变。
    参数:
        mat: (4,4) ndarray 变换矩阵（仅纯旋转+平移）
    返回:
        (4,4) ndarray 逆矩阵，若旋转部分无效则返回None
    """
    try:
        Rmat = mat[:3, :3]
        t = mat[:3, 3]
        R_inv = Rmat.T
        inv = np.eye(4, dtype=np.float32)
        inv[:3, :3] = R_inv
        inv[:3, 3] = -R_inv @ t
        return inv
    except AttributeError:
        return None

def getForward(mat: np.ndarray) -> np.ndarray:
    """
    从变换矩阵提取前向向量。
    参数:
        mat: (4,4) ndarray 变换矩阵
    返回:
        (3,) ndarray 前向向量
    """
    v = mat[:3, 0]
    norm = np.linalg.norm(v)
    if norm > 0:
        return v / norm
    return np.array([1., 0., 0.])

def getRight(mat: np.ndarray) -> np.ndarray:
    """
    从变换矩阵提取右向向量。
    参数:
        mat: (4,4) ndarray 变换矩阵
    返回:
        (3,) ndarray 右向向量
    """
    v = mat[:3, 1]
    norm = np.linalg.norm(v)
    if norm > 0:
        return -v / norm
    return np.array([0., -1., 0.])

def getUp(mat: np.ndarray) -> np.ndarray:
    """
    从变换矩阵提取上向向量。
    参数:
        mat: (4,4) ndarray 变换矩阵
    返回:
        (3,) ndarray 上向向量
    """
    v = mat[:3, 2]
    norm = np.linalg.norm(v)
    if norm > 0:
        return v / norm
    return np.array([0., 0., 1.])


def getForwardFromEuler(ang: np.ndarray, seq: str = 'xyz', degrees: bool = True) -> np.ndarray:
    """
    从欧拉角提取前向向量。
    参数:
        ang: (3,) ndarray 欧拉角
    返回:
        (3,) ndarray 前向向量
    """
    rot = R.from_euler(seq, ang, degrees=degrees).as_matrix()
    return rot[:, 0]


def getRightFromEuler(ang: np.ndarray, seq: str = 'xyz', degrees: bool = True) -> np.ndarray:
    """
    从欧拉角提取右向向量。
    参数:
        ang: (3,) ndarray 欧拉角
    返回:
        (3,) ndarray 右向向量
    """
    rot = R.from_euler(seq, ang, degrees=degrees).as_matrix()
    return -rot[:, 1]


def getUpFromEuler(ang: np.ndarray, seq: str = 'xyz', degrees: bool = True) -> np.ndarray:
    """
    从欧拉角提取上向向量。
    参数:
        ang: (3,) ndarray 欧拉角
    返回:
        (3,) ndarray 上向向量
    """
    rot = R.from_euler(seq, ang, degrees=degrees).as_matrix()
    return rot[:, 2]



if __name__ == '__main__':
    transform = makeTransformFromEuler(translation=np.array([10, 5, 7]), scale=np.array([2, 2, 2]), euler=np.array([30, 0, 0]))
    print(transform)
    print(getForward(transform), getRight(transform), getUp(transform))
    print(getForwardFromEuler(getEuler(transform)), getRightFromEuler(getEuler(transform)), getUpFromEuler(getEuler(transform)))
    print(getTranslation(transform), getScale(transform), getEuler(transform))

    print('===========')
    setTranslation(transform, np.array([20, 50, 70]))
    setScale(transform, np.array([1, 1, 1]))
    setEuler(transform, np.array([30, 0, 0]))
    print(transform)
    print(getForward(transform), getRight(transform), getUp(transform))
    print(getForwardFromEuler(getEuler(transform)), getRightFromEuler(getEuler(transform)), getUpFromEuler(getEuler(transform)))
    print(getTranslation(transform), getScale(transform), getEuler(transform))
