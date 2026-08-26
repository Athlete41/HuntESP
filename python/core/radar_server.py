"""GUI 内嵌 Web Radar 服务：托管静态页面，广播 WebSocket 快照。"""

import base64
import hashlib
import json
import os
import struct
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def text_frame(payload):
    length = len(payload)
    header = bytearray([0x81])
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header += struct.pack(">H", length)
    else:
        header.append(127)
        header += struct.pack(">Q", length)
    return bytes(header) + payload


def build_snapshot(snap, map_id, seq):
    entities = []
    for ent in snap.get("players", []) + snap.get("bosses", []):
        pos = ent.get("position")
        entities.append(
            {
                "id": hex(ent.get("addr", 0)),
                "type": ent.get("type", "Other"),
                "position": (
                    {"x": pos[0], "y": pos[1], "z": pos[2]} if pos else None
                ),
            }
        )
    return {
        "v": 1,
        "type": "snapshot",
        "seq": seq,
        "capturedAtMs": int(time.time() * 1000),
        "map": {"id": map_id},
        "entities": entities,
    }


class ClientRegistry:
    def __init__(self):
        self._clients = set()
        self._lock = threading.Lock()
        self._latest = None

    def set_latest(self, snapshot):
        with self._lock:
            self._latest = snapshot

    def get_latest(self):
        with self._lock:
            return self._latest

    def has_clients(self):
        with self._lock:
            return bool(self._clients)

    def add(self, sock):
        with self._lock:
            self._clients.add(sock)

    def remove(self, sock):
        with self._lock:
            self._clients.discard(sock)

    def broadcast(self, payload):
        dead = []
        with self._lock:
            clients = list(self._clients)
        for sock in clients:
            try:
                sock.sendall(payload)
            except OSError:
                dead.append(sock)
        for sock in dead:
            self.remove(sock)


class RadarHandler(SimpleHTTPRequestHandler):
    registry = None
    static_root = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.static_root, **kwargs)

    def log_message(self, fmt, *args):
        print("[radar]", fmt % args)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/v1/stream":
            self._open_stream()
            return
        super().do_GET()

    def _open_stream(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400, "missing Sec-WebSocket-Key")
            return
        accept = base64.b64encode(
            hashlib.sha1((key + WS_GUID).encode()).digest()
        ).decode()
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        self.registry.add(self.connection)
        hello = text_frame(
            json.dumps(
                {"v": 1, "type": "hello", "serverTimeMs": int(time.time() * 1000)}
            ).encode("utf-8")
        )
        try:
            self.connection.sendall(hello)
        except OSError:
            pass
        latest = self.registry.get_latest()
        if latest is not None:
            try:
                self.connection.sendall(
                    text_frame(json.dumps(latest, ensure_ascii=False).encode("utf-8"))
                )
            except OSError:
                pass
        try:
            while True:
                chunk = self.rfile.read(2)
                if not chunk:
                    break
        except (ConnectionError, OSError, ValueError):
            pass
        finally:
            self.registry.remove(self.connection)
            try:
                self.connection.close()
            except OSError:
                pass


class RadarServer:
    def __init__(self, static_root, host="127.0.0.1", port=8080, broadcast_hz=5.0):
        self.static_root = static_root
        self.host = host
        self.port = port
        self.broadcast_hz = broadcast_hz
        self.registry = ClientRegistry()
        self._server = None
        self._thread = None
        self._broadcast_thread = None
        self._stop_event = threading.Event()
        self._last_sent_seq = None

    def start(self):
        RadarHandler.registry = self.registry
        RadarHandler.static_root = self.static_root
        self._server = ThreadingHTTPServer((self.host, self.port), RadarHandler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()
        self._broadcast_thread = threading.Thread(
            target=self._broadcast_loop, daemon=True
        )
        self._broadcast_thread.start()

    def publish(self, snapshot):
        self.registry.set_latest(snapshot)

    def has_clients(self):
        return self.registry.has_clients()

    def stop(self):
        self._stop_event.set()
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def _broadcast_loop(self):
        interval = 1.0 / max(1.0, self.broadcast_hz)
        while not self._stop_event.wait(interval):
            latest = self.registry.get_latest()
            if latest is None or not self.registry.has_clients():
                continue
            seq = latest.get("seq")
            if seq == self._last_sent_seq:
                continue
            payload = text_frame(
                json.dumps(latest, ensure_ascii=False).encode("utf-8")
            )
            self.registry.broadcast(payload)
            self._last_sent_seq = seq
