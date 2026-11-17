from __future__ import annotations

from backend.alerts import rules
from backend.services import alerts as alert_svc
from backend.services.errors import not_found
from shared.contract import iso


def get_cart_row(ctx, cart_id: str) -> dict:
    row = ctx.db.one("SELECT * FROM smart_carts WHERE cart_id=?", (cart_id,))
    if not row:
        raise not_found("xe", cart_id)
    return row


def active_session_row(ctx, cart_id: str) -> dict | None:
    return ctx.db.one("SELECT * FROM shopping_sessions WHERE cart_id=? AND status='ACTIVE'", (cart_id,))


def session_items(ctx, session_id: int) -> list[dict]:
    return ctx.db.all(
        """SELECT ci.id, ci.product_id, p.barcode, p.name, p.image, ci.quantity, ci.unit_price,
                  p.unit_weight, ci.quantity*ci.unit_price AS line_total
           FROM cart_items ci JOIN products p ON p.id=ci.product_id
           WHERE ci.session_id=? ORDER BY ci.id""",
        (session_id,),
    )


def session_view(ctx, session: dict) -> dict:
    items = session_items(ctx, session["id"])
    total = sum(i["line_total"] for i in items) if session["status"] == "ACTIVE" else session["total_amount"]
    cart = get_cart_row(ctx, session["cart_id"])
    return {
        **session,
        "items": items,
        "item_count": sum(i["quantity"] for i in items),
        "total_amount": total,
        "expected_weight": rules.expected_weight(items),
        "actual_weight": cart["current_weight"],
        "cart_status": cart["cart_status"],
        "connection_status": cart["connection_status"],
        "battery_percent": cart["battery_percent"],
        "active_alerts": alert_svc.active_types(ctx, session["cart_id"]),
    }


def cart_view(ctx, cart_id: str) -> dict:
    cart = get_cart_row(ctx, cart_id)
    sess = active_session_row(ctx, cart_id)
    summary = None
    if sess:
        v = session_view(ctx, sess)
        summary = {
            "id": sess["id"], "started_at": sess["started_at"], "item_count": v["item_count"],
            "total_amount": v["total_amount"], "expected_weight": v["expected_weight"],
        }
    return {**cart, "active_alerts": alert_svc.active_types(ctx, cart_id), "session": summary}


def list_carts(ctx) -> list[dict]:
    return [cart_view(ctx, r["cart_id"]) for r in ctx.db.all("SELECT cart_id FROM smart_carts ORDER BY cart_id")]


def broadcast_cart(ctx, cart_id: str) -> None:
    ctx.hub.publish("CART_UPDATED", {"cart_id": cart_id, "cart": cart_view(ctx, cart_id)})


def update_cart(ctx, cart_id: str, **fields) -> None:
    fields["updated_at"] = iso()
    cols = ", ".join(f"{k}=?" for k in fields)
    ctx.db.execute(f"UPDATE smart_carts SET {cols} WHERE cart_id=?", (*fields.values(), cart_id))


def touch_online(ctx, cart_id: str) -> bool:
    """Ghi nhận cart còn sống. Trả True nếu vừa chuyển OFFLINE -> ONLINE."""
    row = ctx.db.one("SELECT connection_status FROM smart_carts WHERE cart_id=?", (cart_id,))
    if not row:
        return False
    was_offline = row["connection_status"] != "ONLINE"
    update_cart(ctx, cart_id, connection_status="ONLINE", last_seen=iso())
    if was_offline:
        alert_svc.resolve_alert(ctx, cart_id, "OFFLINE")
    return was_offline


def list_telemetry(ctx, cart_id: str, limit: int = 100) -> list[dict]:
    get_cart_row(ctx, cart_id)
    rows = ctx.db.all(
        "SELECT id,cart_id,battery_percent,actual_weight,cart_status,timestamp FROM device_telemetry "
        "WHERE cart_id=? ORDER BY id DESC LIMIT ?", (cart_id, limit),
    )
    return list(reversed(rows))


def public_cart(cart: dict) -> dict:
    """Bản dành cho người chưa đăng nhập: ẩn số món/tiền/cân của phiên (quyền riêng tư – I5)."""
    out = dict(cart)
    if out.get("session"):
        out["session"] = {"id": out["session"]["id"], "started_at": out["session"]["started_at"]}
    return out


def delete_cart(ctx, cart_id: str) -> None:
    get_cart_row(ctx, cart_id)
    sess = active_session_row(ctx, cart_id)
    if sess:
        from backend.services.errors import bad_request
        raise bad_request("Không thể xóa xe đang trong phiên mua hàng hoạt động")
    with ctx.db.tx():
        session_ids = [r["id"] for r in ctx.db.all("SELECT id FROM shopping_sessions WHERE cart_id=?", (cart_id,))]
        for sid in session_ids:
            ctx.db.execute("DELETE FROM cart_items WHERE session_id=?", (sid,))
        ctx.db.execute("DELETE FROM shopping_sessions WHERE cart_id=?", (cart_id,))
        ctx.db.execute("DELETE FROM alerts WHERE cart_id=?", (cart_id,))
        ctx.db.execute("DELETE FROM device_telemetry WHERE cart_id=?", (cart_id,))
        ctx.db.execute("DELETE FROM cart_commands WHERE cart_id=?", (cart_id,))
        ctx.db.execute("DELETE FROM smart_carts WHERE cart_id=?", (cart_id,))
    ctx.hub.publish("CART_DELETED", {"cart_id": cart_id})

