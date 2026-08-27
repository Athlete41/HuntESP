"""后台读取线程：分批扫描实体，坐标和相机按各自间隔刷新。"""

import time

from PySide6.QtCore import QThread, Signal

from core.hunt_session import HuntSession
from core.memory_engine import MemoryEngine
from hunt_reader import HuntReader
import json


class ReaderThread(QThread):
    snapshot = Signal(object)
    status = Signal(str)

    def __init__(
        self,
        process_name,
        camera_ms=100,
        update_ms=1000,
        scan_ms=10000,
        scan_batch_ms=10000,
        batch_size=500,
        max_entities=99999,
        parent=None,
    ):
        super().__init__(parent)
        self.process_name = process_name
        self.camera_ms = camera_ms
        self.update_ms = update_ms
        self.scan_ms = scan_ms
        self.scan_batch_ms = scan_batch_ms
        self.batch_size = batch_size
        self.max_entities = max_entities
        self._running = True
        self.force_full_scan = False

    def request_full_scan(self):
        self.force_full_scan = True

    def stop(self):
        self._running = False
        self.wait(5000)

    def run(self):
        engine = MemoryEngine(process_name=self.process_name)
        session = HuntSession(HuntReader(engine, use_cache=True), max_entities=self.max_entities)
        attached = False
        last_camera = 0.0
        last_update = 0.0
        last_scan = 0.0
        last_batch = 0.0
        scanning = False
        first_scan = True
        try:
            while self._running:
                if not attached:
                    try:
                        engine.attach()
                        attached = True
                        self.status.emit(f"attached {self.process_name}")
                    except Exception as exc:
                        self.status.emit(f"attach retry: {exc}")
                        time.sleep(1.0)
                        continue

                now = time.monotonic()
                scan_interval = self.scan_ms / 1000.0
                update_interval = self.update_ms / 1000.0
                camera_interval = self.camera_ms / 1000.0
                scan_batch_interval = self.scan_batch_ms / 1000.0
                try:
                    force_full = self.force_full_scan
                    if force_full and scanning:
                        scanning = False
                        last_batch = now

                    if not scanning and (force_full or now - last_scan >= scan_interval):
                        self.force_full_scan = False
                        if first_scan or force_full:
                            first_scan = False
                            if force_full:
                                self.status.emit("[scan] start: full scan (forced)")
                            else:
                                self.status.emit("[scan] start: initial full scan")
                            session.scan()
                            last_scan = now
                            last_update = now
                            last_camera = now
                            self.status.emit(
                                f"[scan] done: players={len(session.players)} "
                                f"bosses={len(session.bosses)}"
                            )
                            # self.status.emit(json.dumps(session.players, ensure_ascii=False, indent=4))
                        else:
                            session.begin_scan()
                            scanning = True
                            last_batch = now
                            self.status.emit(
                                f"[scan] start: dumped {session.scan_remaining} entity addresses"
                            )
                            if self._process_batch(session):
                                scanning = False
                                last_scan = now
                                last_update = now
                                last_camera = now
                                self.status.emit(
                                    f"[scan] done: players={len(session.players)} "
                                    f"bosses={len(session.bosses)}"
                                )
                                # self.status.emit(json.dumps(session.players, ensure_ascii=False, indent=4))
                            else:
                                last_batch = now

                    if scanning and now - last_batch >= scan_batch_interval:
                        if self._process_batch(session):
                            scanning = False
                            last_scan = now
                            last_update = now
                            last_camera = now
                            self.status.emit(
                                f"[scan] done: players={len(session.players)} "
                                f"bosses={len(session.bosses)}"
                            )
                            # self.status.emit(json.dumps(session.players, ensure_ascii=False, indent=4))
                        else:
                            last_batch = now
                    elif not scanning and now - last_update >= update_interval:
                        session.update_positions()
                        last_update = now

                    if now - last_camera >= camera_interval:
                        session.update_camera()
                        last_camera = now
                except Exception as exc:
                    self.status.emit(f"read error: {exc}")
                    scanning = False
                    last_scan = now
                    time.sleep(0.1)

                self.snapshot.emit(self._snapshot(session))
                time.sleep(0.02)
        finally:
            engine.close()

    @staticmethod
    def _snapshot(session):
        return {
            "camera": session.camera,
            "players": [dict(e) for e in session.players],
            "bosses": [dict(e) for e in session.bosses],
        }

    def _process_batch(self, session):
        start = time.monotonic()
        session.scan_next_batch(self.batch_size)
        elapsed = (time.monotonic() - start) * 1000.0
        self.status.emit(
            f"[scan] batch {elapsed:.0f}ms: "
            f"{session.scan_processed}/{session.scan_processed + session.scan_remaining}"
        )
        return session.scan_done
