"""Xử lý message MQTT đã được kiểm tra hợp lệ (scan/telemetry/heartbeat/event/ack)."""
from __future__ import annotations

import logging

from backend.services import alerts as alert_svc
from backend.services import carts as cart_svc
from backend.services import commands as cmd_svc
from backend.services import sessions as session_svc
from shared.contract import iso

log = logging.getLogger("ingest")


def _reconcile(ctx, cart_id: str) -> None:
    """Xe vừa online lại: gửi lại trạng thái đúng để xe đồng bộ với Backend (idempotent)."""
    cart = cart_svc.get_cart_row(ctx, cart_id)
    sess = cart_svc.active_session_row(ctx, cart_id)
    if cart["cart_status"] == "LOCKED":
        cmd_svc.send_command(ctx, cart_id, "LOCK_CART", {})
    elif sess:
        cmd_svc.send_command(ctx, cart_id, "START_SESSION", {"session_id": sess["id"]})
    else:
        cmd_svc.send_command(ctx, cart_id, "END_SESSION", {"session_id": None})


def handle(ctx, kind: str, cart_id: str, env: dict) -> None:
    if not ctx.db.one("SELECT 1 AS x FROM smart_carts WHERE cart_id=?", (cart_id,)):
        log.warning("Bỏ qua message từ xe chưa đăng ký: %s", cart_id)
        return
    data = env["data"]
    went_online = cart_svc.touch_online(ctx, cart_id)
    if kind == "heartbeat":
        pass
    elif kind == "telemetry":
        _telemetry(ctx, cart_id, env)
    elif kind == "scan":
        _scan(ctx, cart_id, data)
    elif kind == "event":
        ctx.hub.publish("CART_EVENT", {"cart_id": cart_id, "event": data})
    elif kind == "ack":
        cmd_svc.handle_ack(ctx, cart_id, data)
    if went_online and kind in ("heartbeat", "telemetry"):
        _reconcile(ctx, cart_id)
    cart_svc.broadcast_cart(ctx, cart_id)


def _telemetry(ctx, cart_id: str, env: dict) -> None:
    d = env["data"]
    with ctx.db.tx():
        cart_svc.update_cart(ctx, cart_id, battery_percent=float(d["battery_percent"]), current_weight=float(d["actual_weight"]))
        ctx.db.insert(
            "INSERT INTO device_telemetry(cart_id,battery_percent,actual_weight,cart_status,timestamp,created_at) VALUES(?,?,?,?,?,?)",
            (cart_id, d["battery_percent"], d["actual_weight"], d.get("cart_status"), env["timestamp"], iso()),
        )
        keep = ctx.settings.telemetry_keep
        ctx.db.execute(
            "DELETE FROM device_telemetry WHERE cart_id=? AND id <= (SELECT MAX(id) FROM device_telemetry WHERE cart_id=?) - ?",
            (cart_id, cart_id, keep),
        )
    cart = cart_svc.get_cart_row(ctx, cart_id)
    sess = cart_svc.active_session_row(ctx, cart_id)
    items = cart_svc.session_items(ctx, sess["id"]) if sess else None
    alert_svc.evaluate_telemetry(ctx, cart, items, sess is not None)


def _reject(ctx, cart_id: str, barcode: str, reason: str, message: str) -> None:
    ctx.hub.publish("SCAN_REJECTED", {"cart_id": cart_id, "barcode": barcode, "reason": reason, "message": message})


def _scan(ctx, cart_id: str, d: dict) -> None:
    barcode, action = d["barcode"], d.get("action", "ADD")
    scan_id = d.get("scan_id")
    if scan_id and ctx.dedupe.seen(f"scan:{cart_id}:{scan_id}"):
        ctx.stats["mqtt_duplicate"] += 1
        return
    cart = cart_svc.get_cart_row(ctx, cart_id)
    sess = cart_svc.active_session_row(ctx, cart_id)
    if cart["cart_status"] == "LOCKED":
        return _reject(ctx, cart_id, barcode, "CART_LOCKED", "Xe đang bị khoá")
    if cart["cart_status"] != "IN_USE" or not sess:
        return _reject(ctx, cart_id, barcode, "NO_ACTIVE_SESSION", "Xe chưa có phiên mua hàng")
    product = ctx.db.one("SELECT * FROM products WHERE barcode=? AND active=1", (barcode,))
    if not product:
        return _reject(ctx, cart_id, barcode, "UNKNOWN_BARCODE", f"Không có sản phẩm với mã vạch {barcode}")
    with ctx.db.tx():
        if action == "ADD":
            session_svc.apply_add(ctx, sess["id"], product, 1)
        elif not session_svc.apply_remove_one(ctx, sess["id"], product["id"]):
            return _reject(ctx, cart_id, barcode, "NOT_IN_CART", "Sản phẩm không có trong giỏ")
