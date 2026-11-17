"""Hub phát sự kiện realtime tới các WebSocket client (thread-safe)."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Callable

from backend.auth import ANONYMOUS
from shared.contract import iso

log = logging.getLogger("hub")


def project(event: dict, p):
    """Quyết định client với quyền `p` thấy gì: ("full"|"public", event) hoặc None (không được thấy).

    staff: mọi thứ · khách: SCAN_REJECTED của xe mình + trạng thái xe đã che · ẩn danh: chỉ trạng thái xe đã che.
    """
    if p.exp and time.time() >= p.exp:
        p = ANONYMOUS               # token hết hạn giữa chừng => hạ xuống ẩn danh
    if p.is_staff:
        return "full", event
    t = event.get("type")
    if t == "CART_UPDATED":
        from backend.services.carts import public_cart
        return "public", {**event, "cart": public_cart(event["cart"])}
    if t == "SCAN_REJECTED" and p.role == "customer" and p.cart_id == event.get("cart_id"):
        return "full", event
    if t in ("CONNECTED", "AUTHED", "AUTH_FAILED"):
        return "full", event
    return None


class Hub:
    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: set = set()       # các WsConnection (xem ws_server)
        self.listeners: list[Callable[[dict], None]] = []  # callback đồng bộ (test / nội bộ)
        self._lock = threading.Lock()

    def publish(self, type_: str, payload: dict) -> dict:
        event = {"type": type_, "timestamp": iso(), **payload}
        for fn in list(self.listeners):
            try:
                fn(event)
            except Exception:  # noqa: BLE001
                log.exception("listener lỗi")
        loop = self.loop
        if loop is not None and self.clients:
            try:
                loop.call_soon_threadsafe(self._broadcast, event)
            except RuntimeError:  # loop đã đóng
                pass
        return event

    def _broadcast(self, event: dict) -> None:
        cache: dict[str, str] = {}
        for c in list(self.clients):
            view = project(event, c.principal)
            if view is None:
                continue
            variant, ev = view
            if variant not in cache:
                cache[variant] = json.dumps(ev, ensure_ascii=False)
            c.send_text(cache[variant])

    @property
    def client_count(self) -> int:
        return len(self.clients)
