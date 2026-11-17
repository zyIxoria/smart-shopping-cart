from __future__ import annotations

from backend.services import alerts as alert_svc
from backend.services import carts as cart_svc
from backend.services import commands as cmd_svc
from backend.services.errors import bad_request, conflict, not_found
from shared.contract import iso


def get_session_row(ctx, session_id: int) -> dict:
    row = ctx.db.one("SELECT * FROM shopping_sessions WHERE id=?", (session_id,))
    if not row:
        raise not_found("phiên mua hàng", session_id)
    return row


def get_session(ctx, session_id: int) -> dict:
    return cart_svc.session_view(ctx, get_session_row(ctx, session_id))


def start_session(ctx, cart_id: str) -> dict:
    with ctx.db.tx():
        cart = cart_svc.get_cart_row(ctx, cart_id)
        if cart["connection_status"] != "ONLINE":
            raise conflict("CART_OFFLINE", f"Xe {cart_id} đang OFFLINE, không thể bắt đầu phiên")
        if cart["cart_status"] != "AVAILABLE":
            raise conflict("CART_NOT_AVAILABLE", f"Xe {cart_id} đang {cart['cart_status']}, chỉ xe AVAILABLE mới bắt đầu được phiên")
        sid = ctx.db.insert(
            "INSERT INTO shopping_sessions(cart_id,status,started_at) VALUES(?, 'ACTIVE', ?)", (cart_id, iso())
        )
        cart_svc.update_cart(ctx, cart_id, cart_status="IN_USE")
    cmd_svc.send_command(ctx, cart_id, "START_SESSION", {"session_id": sid})
    cart_svc.broadcast_cart(ctx, cart_id)
    return get_session(ctx, sid)


def _require_active(ctx, session_id: int) -> dict:
    s = get_session_row(ctx, session_id)
    if s["status"] != "ACTIVE":
        raise conflict("SESSION_NOT_ACTIVE", f"Phiên {session_id} đã kết thúc")
    return s


def add_item(ctx, session_id: int, product_id: int | None = None, barcode: str | None = None, quantity: int = 1) -> dict:
    if quantity < 1 or quantity > 99:
        raise bad_request("quantity phải từ 1 đến 99")
    with ctx.db.tx():
        s = _require_active(ctx, session_id)
        if product_id is not None:
            p = ctx.db.one("SELECT * FROM products WHERE id=? AND active=1", (product_id,))
        elif barcode:
            p = ctx.db.one("SELECT * FROM products WHERE barcode=? AND active=1", (barcode,))
        else:
            raise bad_request("Cần product_id hoặc barcode")
        if not p:
            raise not_found("sản phẩm", product_id or barcode)
        apply_add(ctx, s["id"], p, quantity)
    cart_svc.broadcast_cart(ctx, s["cart_id"])
    return get_session(ctx, session_id)


def apply_add(ctx, session_id: int, product: dict, quantity: int = 1) -> None:
    row = ctx.db.one("SELECT id FROM cart_items WHERE session_id=? AND product_id=?", (session_id, product["id"]))
    if row:
        ctx.db.execute("UPDATE cart_items SET quantity=quantity+? WHERE id=?", (quantity, row["id"]))
    else:
        ctx.db.insert(
            "INSERT INTO cart_items(session_id,product_id,quantity,unit_price) VALUES(?,?,?,?)",
            (session_id, product["id"], quantity, product["price"]),
        )


def apply_remove_one(ctx, session_id: int, product_id: int) -> bool:
    row = ctx.db.one("SELECT id,quantity FROM cart_items WHERE session_id=? AND product_id=?", (session_id, product_id))
    if not row:
        return False
    if row["quantity"] <= 1:
        ctx.db.execute("DELETE FROM cart_items WHERE id=?", (row["id"],))
    else:
        ctx.db.execute("UPDATE cart_items SET quantity=quantity-1 WHERE id=?", (row["id"],))
    return True


def remove_item(ctx, session_id: int, item_id: int) -> dict:
    with ctx.db.tx():
        s = _require_active(ctx, session_id)
        row = ctx.db.one("SELECT id FROM cart_items WHERE id=? AND session_id=?", (item_id, session_id))
        if not row:
            raise not_found("dòng hàng", item_id)
        ctx.db.execute("DELETE FROM cart_items WHERE id=?", (item_id,))
    cart_svc.broadcast_cart(ctx, s["cart_id"])
    return get_session(ctx, session_id)


def checkout(ctx, session_id: int) -> dict:
    with ctx.db.tx():
        s = _require_active(ctx, session_id)
        cart = cart_svc.get_cart_row(ctx, s["cart_id"])
        if cart["cart_status"] == "LOCKED":
            raise conflict("CART_LOCKED", f"Xe {cart['cart_id']} đang bị khoá, không thể thanh toán")
        items = cart_svc.session_items(ctx, session_id)
        if not items:
            raise conflict("EMPTY_SESSION", "Giỏ hàng trống, không thể thanh toán")
        total = sum(i["line_total"] for i in items)
        unresolved = alert_svc.active_types(ctx, s["cart_id"])
        note = ("Cảnh báo chưa xử lý khi thanh toán: " + ", ".join(unresolved)) if unresolved else ""
        ctx.db.execute(
            "UPDATE shopping_sessions SET status='COMPLETED', ended_at=?, total_amount=?, note=? WHERE id=?",
            (iso(), total, note, session_id),
        )
        cart_svc.update_cart(ctx, s["cart_id"], cart_status="AVAILABLE")
    # Điều kiện cân nặng không còn áp dụng khi phiên đã kết thúc
    alert_svc.resolve_alert(ctx, s["cart_id"], "WEIGHT_MISMATCH")
    cmd_svc.send_command(ctx, s["cart_id"], "END_SESSION", {"session_id": session_id})
    cart_svc.broadcast_cart(ctx, s["cart_id"])
    return get_session(ctx, session_id)


def cancel(ctx, session_id: int) -> dict:
    """Huỷ phiên (mở rộng): kết thúc với tổng 0, xoá dòng hàng, xe về AVAILABLE."""
    with ctx.db.tx():
        s = _require_active(ctx, session_id)
        ctx.db.execute("DELETE FROM cart_items WHERE session_id=?", (session_id,))
        ctx.db.execute(
            "UPDATE shopping_sessions SET status='COMPLETED', ended_at=?, total_amount=0, note='Phiên bị huỷ' WHERE id=?",
            (iso(), session_id),
        )
        cart = cart_svc.get_cart_row(ctx, s["cart_id"])
        if cart["cart_status"] != "LOCKED":
            cart_svc.update_cart(ctx, s["cart_id"], cart_status="AVAILABLE")
    alert_svc.resolve_alert(ctx, s["cart_id"], "WEIGHT_MISMATCH")
    cmd_svc.send_command(ctx, s["cart_id"], "END_SESSION", {"session_id": session_id})
    cart_svc.broadcast_cart(ctx, s["cart_id"])
    return get_session(ctx, session_id)
