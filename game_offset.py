"""Hunt: Showdown 最小偏移表。"""

PROCESS_NAME = "HuntGame.exe"
GAMEHUNT_DLL = "GameHunt.dll"

# 根指针
SGE = "[GameHunt.dll + 0x2827328]"

ENTITY_SYSTEM = f"[{SGE} + 0xC0]"
P_SYSTEM = f"[{SGE} + 0x90]"

OBJECT_COUNT = f"{ENTITY_SYSTEM} + 0x40092"
ENTITY_LIST = f"{ENTITY_SYSTEM} + 0x40098"

CAMERA_BASE = f"{P_SYSTEM} + 0x8F8"
CAMERA_POS = f"{CAMERA_BASE} + 0x2F0"
VIEW_MATRIX = f"{CAMERA_BASE} + 0x230"
PROJECTION_MATRIX = f"{CAMERA_BASE} + 0x270"

ENTITY_TEMPLATES = {
    "class_name": f"[[{{entity}} + 0x18] + 0x10]",
    "name": f"[{{entity}} + 0x10]",
    "position": f"{{entity}} + 0x134",
}

NAME_SIZE = 100
