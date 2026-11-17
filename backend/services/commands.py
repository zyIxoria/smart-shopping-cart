"""Gửi lệnh xuống xe qua MQTT, theo dõi ACK và lưu lịch sử vào CSDL."""
from __future__ import annotations

import json
import logging
import threading

from backend.services import alerts as alert_svc  # noqa: F401  (giữ import cho mở rộng)
from backend.services.errors import ApiError, conflict
from shared.contract import iso, new_id

log = logging.getLogger("commands")


def send_command(ctx, cart_id: str, command_type: str, parameters: dict | None = None) -> dict:
    cid = new_id()
    now = iso()
    params = parameters or {}
    rec = {
        "command_id": cid, "cart_id": cart_id, "command_type": command_type,
        "parameters": params, "status": "PENDING", "message": "",
        "created_at": now, "acked_at": None,
    }
    ev = threading.Event()
    with ctx.cmd_lock:
        ctx.commands[cid] = rec
        ev_map = ctx._cmd_events
        ev_map[cid] = ev
        if len(ctx.commands) > 500:  # giới hạn bộ nhớ
            for k in list(ctx.commands)[:100]:
                ctx.commands.pop(k, None)
                ev_map.pop(k, None)

    sent = ctx.gateway.publish_command(cart_id, cid, command_type, rec["parameters"]) if ctx.gateway else False
    if not sent:
        rec["status"] = "FAILED"
        rec["message"] = "Không gửi được lệnh (MQTT chưa kết nối)"
        ev.set()

    # Lưu trạng thái command vào CSDL (PostgreSQL / SQLite)
    try:
        ctx.db.insert(
            "INSERT INTO cart_commands(command_id,cart_id,command_type,parameters,status,message,created_at,sent_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (cid, cart_id, command_type, json.dumps(params, ensure_ascii=False),
             rec["status"], rec["message"], now, now if sent else None),
        )
    except Exception as e:
        log.warning("Không thể lưu command vào DB: %s", e)

    return rec


def wait_ack(ctx, command_id: str, timeout: float) -> dict:
    ev = ctx._cmd_events.get(command_id)
    rec = ctx.commands[command_id]
    if ev and not ev.wait(timeout) and rec["status"] == "PENDING":
        rec["status"] = "TIMEOUT"
        rec["message"] = f"Không nhận ACK trong {timeout:g}s"
        try:
            ctx.db.execute(
                "UPDATE cart_commands SET status='TIMEOUT', message=? WHERE command_id=?",
                (rec["message"], command_id),
            )
        except Exception as e:
            log.warning("Lỗi cập nhật command timeout: %s", e)
    return rec


def get_command(ctx, command_id: str) -> dict:
    # 1. Tra cứu trong RAM cache
    rec = ctx.commands.get(command_id)
    if rec:
        return rec

    # 2. Tra cứu trong CSDL (sống qua lần khởi động lại Backend)
    try:
        row = ctx.db.one("SELECT * FROM cart_commands WHERE command_id=?", (command_id,))
        if row:
            raw_params = row.get("parameters", "{}")
            params = json.loads(raw_params) if isinstance(raw_params, str) else (raw_params or {})
            rec = {
                "command_id": row["command_id"],
                "cart_id": row["cart_id"],
                "command_type": row["command_type"],
                "parameters": params,
                "status": row["status"],
                "message": row.get("message", ""),
                "created_at": str(row["created_at"]),
                "acked_at": str(row["acked_at"]) if row.get("acked_at") else None,
            }
            with ctx.cmd_lock:
                ctx.commands[command_id] = rec
            return rec
    except Exception as e:
        log.warning("Lỗi tra cứu command từ DB: %s", e)

    raise ApiError(404, "NOT_FOUND", f"Không tìm thấy lệnh: {command_id}")


def list_commands(ctx, cart_id: str | None = None, limit: int = 50) -> list[dict]:
    """Danh sách lịch sử lệnh từ CSDL."""
    try:
        sql = "SELECT * FROM cart_commands"
        params = []
        if cart_id:
            sql += " WHERE cart_id=?"
            params.append(cart_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = ctx.db.all(sql, tuple(params))
        res = []
        for r in rows:
            raw_p = r.get("parameters", "{}")
            p_dict = json.loads(raw_p) if isinstance(raw_p, str) else (raw_p or {})
            res.append({
                "command_id": r["command_id"],
                "cart_id": r["cart_id"],
                "command_type": r["command_type"],
                "parameters": p_dict,
                "status": r["status"],
                "message": r.get("message", ""),
                "created_at": str(r["created_at"]),
                "acked_at": str(r["acked_at"]) if r.get("acked_at") else None,
            })
        return res
    except Exception as e:
        log.warning("Lỗi list_commands từ DB: %s", e)
        return []


def handle_ack(ctx, cart_id: str, data: dict) -> None:
    from backend.services import carts as cart_svc

    cid = data["command_id"]
    rec = ctx.commands.get(cid)
    if not rec:
        try:
            rec = get_command(ctx, cid)
        except ApiError:
            return

    if rec["cart_id"] != cart_id or rec["status"] != "PENDING":
        return

    rec["status"] = data["result"]
    rec["message"] = data.get("message", "")
    rec["acked_at"] = iso()

    # Cập nhật CSDL
    try:
        ctx.db.execute(
            "UPDATE cart_commands SET status=?, message=?, acked_at=? WHERE command_id=?",
            (rec["status"], rec["message"], rec["acked_at"], cid),
        )
    except Exception as e:
        log.warning("Lỗi cập nhật ACK vào DB: %s", e)

    if data["result"] == "OK":
        ctype = rec["command_type"]
        if ctype == "LOCK_CART":
            cart_svc.update_cart(ctx, cart_id, cart_status="LOCKED")
        elif ctype == "UNLOCK_CART":
            has = cart_svc.active_session_row(ctx, cart_id) is not None
            cart_svc.update_cart(ctx, cart_id, cart_status="IN_USE" if has else "AVAILABLE")

    ev = ctx._cmd_events.get(cid)
    if ev:
        ev.set()

    ctx.hub.publish("COMMAND_ACK", {"cart_id": cart_id, "command": rec})
    cart_svc.broadcast_cart(ctx, cart_id)


def lock_or_unlock(ctx, cart_id: str, lock: bool) -> tuple[int, dict]:
    """Gửi LOCK/UNLOCK và chờ ACK. Trả (http_status, command)."""
    from backend.services import carts as cart_svc

    cart = cart_svc.get_cart_row(ctx, cart_id)
    if cart["connection_status"] != "ONLINE":
        raise conflict("CART_OFFLINE", f"Xe {cart_id} đang OFFLINE, không thể gửi lệnh")
    if lock and cart["cart_status"] == "LOCKED":
        raise conflict("ALREADY_LOCKED", f"Xe {cart_id} đã bị khoá")
    if not lock and cart["cart_status"] != "LOCKED":
        raise conflict("NOT_LOCKED", f"Xe {cart_id} không ở trạng thái LOCKED")
    rec = send_command(ctx, cart_id, "LOCK_CART" if lock else "UNLOCK_CART", {})
    rec = wait_ack(ctx, rec["command_id"], ctx.settings.command_ack_timeout_s)
    status = {"OK": 200, "FAILED": 409, "TIMEOUT": 504, "PENDING": 504}[rec["status"]]
    return status, rec
