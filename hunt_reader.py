"""Hunt: Showdown 极简读取器：只要坐标和分类。"""

import argparse
import json
import struct
import sys

import game_offset as off
from core.memory_engine import MemoryEngine

MIN_VALID_ADDR = 0x2000000
MAX_VALID_ADDR = 0x7FFFFFFFFFFF

PLAYER_TYPES = {"LocalPlayer", "EnemyPlayer", "FriendlyPlayer", "DeadPlayer"}
BOSS_TYPES = {"Assassin", "Butcher", "Spider", "Scrapbeak", "Rotjaw", "Hellborn"}


def is_valid_ptr(address):
    return MIN_VALID_ADDR < address < MAX_VALID_ADDR


class HuntReader:
    def __init__(self, engine, use_cache=True):
        self.engine = engine
        self.use_cache = use_cache
        self.camera_pos = (0.0, 0.0, 0.0)
        self.view_matrix = [0.0] * 16
        self.proj_matrix = [0.0] * 16
        self.object_count = 0
        self.entity_list_addr = 0

    def resolve(self, expr):
        return self.engine.resolve_expression(expr, is64bit=True, use_cache=self.use_cache)

    def update_camera(self):
        self.camera_pos = self._read_vec3(self.resolve(off.CAMERA_POS))
        self.view_matrix = self._read_matrix(self.resolve(off.VIEW_MATRIX))
        self.proj_matrix = self._read_matrix(self.resolve(off.PROJECTION_MATRIX))

    def refresh_world(self, max_entities=1024):
        self.object_count = self.engine.readUInt16(self.resolve(off.OBJECT_COUNT)) + 1
        self.entity_list_addr = self.resolve(off.ENTITY_LIST)
        self.update_camera()

    def read_entity_addrs(self, max_entities=1024):
        count = min(self.object_count, max_entities)
        if count <= 0 or not is_valid_ptr(self.entity_list_addr):
            return []
        data, _ = self.engine.read(self.entity_list_addr, count * 8)
        return [struct.unpack_from("<Q", data, i * 8)[0] for i in range(count)]

    def read_class_name(self, addr):
        ptr = self.resolve(off.ENTITY_TEMPLATES["class_name"].format(entity=hex(addr)))
        if not is_valid_ptr(ptr):
            return ""
        return self.engine.readString(ptr, off.NAME_SIZE, "utf-8")

    def read_entity_name(self, addr):
        ptr = self.resolve(off.ENTITY_TEMPLATES["name"].format(entity=hex(addr)))
        if not is_valid_ptr(ptr):
            return ""
        return self.engine.readString(ptr, off.NAME_SIZE, "utf-8")

    def read_position(self, addr):
        return self._read_vec3(self.resolve(off.ENTITY_TEMPLATES["position"].format(entity=hex(addr))))

    @staticmethod
    def classify(class_name):
        cls = class_name or ""
        if "Hunter_Loot" in cls:
            return "DeadPlayer"
        if "HunterBasic" in cls:
            return "EnemyPlayer"
        if "target_assassin" in cls:
            return "Assassin"
        if "target_butcher" in cls:
            return "Butcher"
        if "target_spider" in cls:
            return "Spider"
        if "target_scrapbeak" in cls:
            return "Scrapbeak"
        if "target_rotjaw" in cls:
            return "Rotjaw"
        if "immolator_elite" in cls:
            return "Hellborn"
        return "Other"

    def scan_snapshot(self, max_entities=1024):
        self.refresh_world(max_entities)
        players, bosses, others = [], [], []
        for addr in self.read_entity_addrs(max_entities):
            etype = self.classify(self.read_class_name(addr))
            name = self.read_entity_name(addr)
            ent = {
                "addr": addr,
                "type": etype,
                "name": name,
                "position": list(self.read_position(addr)),
            }
            if etype in PLAYER_TYPES:
                players.append(ent)
            elif etype in BOSS_TYPES:
                bosses.append(ent)
            else:
                others.append(ent)
        return {
            "camera": {
                "pos": list(self.camera_pos),
                "view": self.view_matrix,
                "proj": self.proj_matrix,
            },
            "object_count": self.object_count,
            "players": players,
            "bosses": bosses,
            "others": others,
        }

    def _read_vec3(self, address):
        if not is_valid_ptr(address):
            return (0.0, 0.0, 0.0)
        data, _ = self.engine.read(address, 12)
        return struct.unpack_from("<3f", data)

    def _read_matrix(self, address):
        if not is_valid_ptr(address):
            return [0.0] * 16
        data, _ = self.engine.read(address, 64)
        return list(struct.unpack_from("<16f", data))


def selftest():
    class FakeEngine(MemoryEngine):
        def __init__(self):
            super().__init__()
            self.pid = 1234
            self._handle = object()

        def getBaseAddressWithCache(self, module_name):
            self.modules[module_name] = 0x7FF000000000
            return self.modules[module_name]

        def readPointer64WithCache(self, address):
            value = address + 0x1000
            self._pointer_cache[address] = value
            return value

    engine = FakeEngine()
    reader = HuntReader(engine)
    sge = reader.resolve(off.SGE)
    if sge != 0x7FF002828328:
        print(f"[-] SGE 解析异常: {sge:#x}")
        return 1
    for expr in (off.ENTITY_SYSTEM, off.P_SYSTEM, off.ENTITY_LIST, off.CAMERA_POS, off.VIEW_MATRIX, off.PROJECTION_MATRIX):
        reader.resolve(expr)
    for key, template in off.ENTITY_TEMPLATES.items():
        reader.resolve(template.format(entity="0x7FF0000200000"))
    print("[+] 偏移表达式解析测试通过")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Hunt: Showdown 坐标读取器")
    parser.add_argument("--process", default=off.PROCESS_NAME)
    parser.add_argument("--max-entities", type=int, default=99999)
    parser.add_argument("--output", default="entities.json")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()

    engine = MemoryEngine(process_name=args.process)
    reader = HuntReader(engine)
    try:
        engine.attach()
    except Exception as exc:
        print(f"[-] 附加失败: {exc}")
        return 1
    try:
        data = reader.scan_snapshot(args.max_entities)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[+] 已保存 {len(data['players'])} 玩家 / {len(data['bosses'])} Boss 到 {args.output}")
    finally:
        engine.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
