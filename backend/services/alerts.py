from __future__ import annotations

from backend.alerts import rules
from shared.contract import iso


def active_types(ctx, cart_id: str) -> list[str]:
    rows = ctx.db.all("SELECT alert_type FROM alerts WHERE cart_id=? AND status='ACTIVE' ORDER BY id", (cart_id,))
    return [r["alert_type"] for r in rows]


def raise_alert(ctx, cart_id: str, alert_type: str, detail: str) -> dict | None:
    """Tạo cảnh báo ACTIVE nếu chưa có cảnh báo ACTIVE cùng loại. Trả None nếu đã tồn tại."""
    with ctx.db.tx():
        if ctx.db.one("SELECT id FROM alerts WHERE cart_id=? AND alert_type=? AND status='ACTIVE'", (cart_id, alert_type)):
            return None
        aid = ctx.db.insert(
            "INSERT INTO alerts(cart_id,alert_type,status,detail,created_at) VALUES(?,?, 'ACTIVE',?,?)",
            (cart_id, alert_type, detail, iso()),
        )
        alert = ctx.db.one("SELECT * FROM alerts WHERE id=?", (aid,))
    ctx.hub.publish("ALERT_TRIGGERED", {"cart_id": cart_id, "alert": alert})
    return alert


def resolve_alert(ctx, cart_id: str, alert_type: str) -> list[dict]:
    with ctx.db.tx():
        rows = ctx.db.all("SELECT * FROM alerts WHERE cart_id=? AND alert_type=? AND status='ACTIVE'", (cart_id, alert_type))
        now = iso()
        for r in rows:
            ctx.db.execute("UPDATE alerts SET status='RESOLVED', resolved_at=? WHERE id=?", (now, r["id"]))
        resolved = [ctx.db.one("SELECT * FROM alerts WHERE id=?", (r["id"],)) for r in rows]
    for a in resolved:
        ctx.hub.publish("ALERT_RESOLVED", {"cart_id": cart_id, "alert": a})
    return resolved


def list_alerts(ctx, status: str | None = None, cart_id: str | None = None, limit: int = 200) -> list[dict]:
    sql, params = "SELECT * FROM alerts WHERE 1=1", []
    if status:
        sql += " AND status=?"
        params.append(status)
    if cart_id:
        sql += " AND cart_id=?"
        params.append(cart_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return ctx.db.all(sql, tuple(params))


def evaluate_telemetry(ctx, cart: dict, session_items: list[dict] | None, has_session: bool) -> None:
    """Áp dụng quy tắc LOW_BATTERY và WEIGHT_MISMATCH sau mỗi telemetry hợp lệ."""
    s = ctx.settings
    cid = cart["cart_id"]
    # LOW_BATTERY
    if rules.is_low_battery(cart["battery_percent"], s.battery_low_percent):
        raise_alert(ctx, cid, "LOW_BATTERY", f"Pin còn {cart['battery_percent']:.0f}% (< {s.battery_low_percent:.0f}%)")
    else:
        resolve_alert(ctx, cid, "LOW_BATTERY")
    # WEIGHT_MISMATCH
    if rules.weight_applicable(cart["cart_status"], has_session):
        exp = rules.expected_weight(session_items or [])
        act = cart["current_weight"]
        if rules.is_weight_mismatch(act, exp, s.weight_tolerance_g):
            raise_alert(
                ctx, cid, "WEIGHT_MISMATCH",
                f"Cân thực tế {act:.0f} g, dự kiến {exp:.0f} g (lệch {rules.weight_diff(act, exp):.0f} g > {s.weight_tolerance_g:.0f} g)",
            )
        else:
            resolve_alert(ctx, cid, "WEIGHT_MISMATCH")
    else:
        resolve_alert(ctx, cid, "WEIGHT_MISMATCH")
