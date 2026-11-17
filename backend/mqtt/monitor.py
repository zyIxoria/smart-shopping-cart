"""Giám sát heartbeat: cart > HEARTBEAT_TIMEOUT_S không có tin -> OFFLINE + cảnh báo."""
from __future__ import annotations

import logging
import threading

from backend.alerts import rules
from backend.services import alerts as alert_svc
from backend.services import carts as cart_svc
from shared import contract

log = logging.getLogger("monitor")


def check_once(ctx) -> list[str]:
    """Quét một lần; trả danh sách cart_id vừa chuyển OFFLINE."""
    now = contract.utcnow()
    went = []
    for c in ctx.db.all("SELECT cart_id,last_seen FROM smart_carts WHERE connection_status='ONLINE'"):
        last = contract.parse_ts(c["last_seen"]) if c["last_seen"] else None
        if rules.is_offline(last, now, ctx.settings.heartbeat_timeout_s):
            cart_svc.update_cart(ctx, c["cart_id"], connection_status="OFFLINE")
            alert_svc.raise_alert(
                ctx, c["cart_id"], "OFFLINE",
                f"Mất kết nối: không nhận heartbeat quá {ctx.settings.heartbeat_timeout_s:g}s",
            )
            cart_svc.broadcast_cart(ctx, c["cart_id"])
            went.append(c["cart_id"])
    return went


class HeartbeatMonitor(threading.Thread):
    def __init__(self, ctx):
        super().__init__(name="heartbeat-monitor", daemon=True)
        self.ctx = ctx
        self._stop_evt = threading.Event()

    def run(self) -> None:
        while not self._stop_evt.wait(self.ctx.settings.monitor_interval_s):
            try:
                check_once(self.ctx)
            except Exception:  # noqa: BLE001
                log.exception("monitor lỗi")

    def stop(self) -> None:
        self._stop_evt.set()
