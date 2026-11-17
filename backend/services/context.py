"""AppContext: các thành phần dùng chung (DB, hub, MQTT, cấu hình, bộ nhớ lệnh)."""
from __future__ import annotations

import threading
from collections import OrderedDict


class LruSet:
    """Tập message_id đã xử lý (chống xử lý lặp)."""

    def __init__(self, size: int):
        self.size = size
        self._d: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()

    def seen(self, key: str) -> bool:
        """Trả True nếu đã thấy; nếu chưa thì ghi nhận và trả False."""
        with self._lock:
            if key in self._d:
                self._d.move_to_end(key)
                return True
            self._d[key] = None
            if len(self._d) > self.size:
                self._d.popitem(last=False)
            return False


class AppContext:
    def __init__(self, settings, db, hub, gateway=None):
        self.settings = settings
        self.db = db
        self.hub = hub
        self.gateway = gateway           # backend.mqtt.gateway.Gateway | None
        from backend.auth import AuthService
        self.auth = AuthService(settings)
        self.dedupe = LruSet(settings.dedupe_size)
        self.commands: dict[str, dict] = {}
        self._cmd_events: dict[str, threading.Event] = {}
        self.cmd_lock = threading.Lock()
        self.stats = {"mqtt_received": 0, "mqtt_invalid": 0, "mqtt_duplicate": 0, "mqtt_stale": 0,
                      "mqtt_unsigned": 0, "mqtt_bad_signature": 0}
