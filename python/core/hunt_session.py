"""Hunt 会话：分批扫描实体，另外独立刷坐标和相机。"""

import math

from hunt_reader import BOSS_TYPES, PLAYER_TYPES


class HuntSession:
    def __init__(self, reader, max_entities=1024):
        self.reader = reader
        self.max_entities = max_entities
        self.camera = {"pos": [0.0, 0.0, 0.0], "view": [0.0] * 16, "proj": [0.0] * 16}
        self.players = []
        self.bosses = []
        self._player_index = {}
        self._boss_index = {}
        self.pending_addrs = []
        self._scan_offset = 0
        self._seen_addrs = set()
        self.scan_done = True

    def begin_scan(self):
        r = self.reader
        r.refresh_world(self.max_entities)
        self._copy_camera()
        self.pending_addrs = r.read_entity_addrs(self.max_entities)
        self._scan_offset = 0
        self._seen_addrs = set()
        self.scan_done = False

    def scan_next_batch(self, batch_size=500):
        if self.scan_done:
            return False
        r = self.reader
        start = self._scan_offset
        end = min(start + max(1, batch_size), len(self.pending_addrs))
        for addr in self.pending_addrs[start:end]:
            etype = r.classify(r.read_class_name(addr))
            ent = {"addr": addr, "type": etype, "position": list(r.read_position(addr))}
            self._seen_addrs.add(addr)
            if etype in PLAYER_TYPES:
                self._upsert(ent, self.players, self._player_index, self.bosses, self._boss_index)
            elif etype in BOSS_TYPES:
                self._upsert(ent, self.bosses, self._boss_index, self.players, self._player_index)
        self._scan_offset = end
        if self._scan_offset >= len(self.pending_addrs):
            self._prune_disappeared()
            self._sort()
            self.scan_done = True
        return True

    def scan(self):
        self.begin_scan()
        while self.scan_next_batch(self.max_entities):
            pass

    def update_positions(self):
        for ent in self.players + self.bosses:
            ent["position"] = list(self.reader.read_position(ent["addr"]))
        self._sort()

    def update_camera(self):
        self.reader.update_camera()
        self._copy_camera()

    @property
    def scan_processed(self):
        return self._scan_offset

    @property
    def scan_remaining(self):
        return len(self.pending_addrs) - self._scan_offset

    def _copy_camera(self):
        r = self.reader
        self.camera = {
            "pos": list(r.camera_pos),
            "view": list(r.view_matrix),
            "proj": list(r.proj_matrix),
        }

    def _upsert(self, ent, target_list, target_index, other_list, other_index):
        other = other_index.pop(ent["addr"], None)
        if other is not None:
            other_list.remove(other)
        existing = target_index.get(ent["addr"])
        if existing is not None:
            existing["type"] = ent["type"]
            existing["position"] = ent["position"]
        else:
            target_index[ent["addr"]] = ent
            target_list.append(ent)

    def _prune_disappeared(self):
        for target_list, index in (
            (self.players, self._player_index),
            (self.bosses, self._boss_index),
        ):
            for addr in list(index):
                if addr not in self._seen_addrs:
                    index.pop(addr)
            target_list[:] = [ent for ent in target_list if ent["addr"] in self._seen_addrs]

    def _sort(self):
        cam = self.camera["pos"]
        self.players.sort(key=lambda e: math.dist(cam, e["position"]))
        self.bosses.sort(key=lambda e: math.dist(cam, e["position"]))
