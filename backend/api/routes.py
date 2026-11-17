"""Các REST endpoint (prefix /api). Handler đồng bộ, chạy trong threadpool."""
from __future__ import annotations

import time

from backend.api.registry import route
from backend.auth import RateLimitError
from backend.schemas import models as m
from backend.services import alerts as alert_svc
from backend.services import carts as cart_svc
from backend.services import commands as cmd_svc
from backend.services import sessions as session_svc
from backend.services.errors import ApiError, bad_request, conflict, not_found
from shared.contract import iso

START = time.time()


def ctx_of(request):
    return request.app.state.ctx


def principal_of(request):
    return request.state.principal


def client_ip(request) -> str:
    return request.client.host if request.client else "?"


def _limited(e: RateLimitError) -> ApiError:
    err = ApiError(429, "TOO_MANY_REQUESTS", f"Quá nhiều yêu cầu, thử lại sau {e.retry_after}s")
    err.headers = {"Retry-After": str(e.retry_after)}
    return err


def _product(row: dict) -> dict:
    return {**row, "active": bool(row["active"])}


# ----------------------------------------------------------------- system
@route("GET", "/api/health", "Kiểm tra sức khoẻ hệ thống (chi tiết chỉ dành cho staff)", "System", auth="public")
def health(request, body):
    ctx = ctx_of(request)
    gw = ctx.gateway
    try:
        ctx.db.one("SELECT 1 AS ok")
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    if not principal_of(request).is_staff:      # người lạ chỉ biết "còn sống không" + cổng WS (không lộ thống kê nội bộ)
        return {"status": "ok" if db_ok else "degraded", "time": iso(), "ws_port": request.app.state.ws.port}
    return {
        "status": "ok" if db_ok else "degraded",
        "time": iso(),
        "uptime_s": round(time.time() - START, 1),
        "database": "up" if db_ok else "down",
        "mqtt": "connected" if (gw and gw.connected) else "disconnected",
        "websocket_clients": ctx.hub.client_count,
        "ws_port": request.app.state.ws.port,
        "stats": ctx.stats,
    }


# --------------------------------------------------------------- products
@route("GET", "/api/products", "Danh sách sản phẩm", "Products", response=[m.Product], auth="public",
       query=[("q", "string", "Tìm theo tên hoặc mã vạch"),
              ("all", "string", "1 = gồm cả sản phẩm đã ẩn (chỉ có tác dụng với admin/viewer)")])
def list_products(request, body):
    q = request.query_params.get("q", "").strip()
    show_hidden = request.query_params.get("all") == "1" and principal_of(request).is_staff
    db = ctx_of(request).db
    sql, params = "SELECT * FROM products WHERE " + ("1=1" if show_hidden else "active=1"), []
    if q:
        op = "ILIKE" if db.is_postgres else "LIKE"
        sql += f" AND (name {op} ? OR barcode {op} ?)"
        params += [f"%{q}%", f"%{q}%"]
    return [_product(r) for r in db.all(sql + " ORDER BY name", tuple(params))]


@route("POST", "/api/products", "Thêm sản phẩm (admin)", "Products", body=m.ProductCreate, response=m.Product, status=201,
       errors=(409, 422), auth="admin")
def create_product(request, body):
    db = ctx_of(request).db
    if not body.name.strip():
        raise ApiError(422, "VALIDATION_ERROR", "name: không được để trống")
    with db.tx():
        if db.one("SELECT 1 AS x FROM products WHERE barcode=?", (body.barcode,)):
            raise conflict("BARCODE_EXISTS", f"Mã vạch {body.barcode} đã có")
        pid = db.insert("INSERT INTO products(barcode,name,price,unit_weight,image,active) VALUES(?,?,?,?,?,1)",
                        (body.barcode, body.name.strip(), body.price, body.unit_weight, body.image))
    return 201, _product(db.one("SELECT * FROM products WHERE id=?", (pid,)))


@route("PUT", "/api/products/{id:int}", "Sửa / ẩn / hiện sản phẩm (admin)", "Products", body=m.ProductUpdate, response=m.Product,
       errors=(404, 409, 422), auth="admin")
def update_product(request, body):
    db = ctx_of(request).db
    pid = request.path_params["id"]
    changes = body.model_dump(exclude_none=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise ApiError(422, "VALIDATION_ERROR", "name: không được để trống")
    if "active" in changes:
        changes["active"] = 1 if changes["active"] else 0
    with db.tx():
        if not db.one("SELECT 1 AS x FROM products WHERE id=?", (pid,)):
            raise not_found("sản phẩm", pid)
        if "barcode" in changes and db.one("SELECT 1 AS x FROM products WHERE barcode=? AND id<>?", (changes["barcode"], pid)):
            raise conflict("BARCODE_EXISTS", f"Mã vạch {changes['barcode']} đã có")
        if changes:
            cols = ",".join(f"{k}=?" for k in changes)        # tên cột lấy từ khoá của model (cố định), giá trị luôn là tham số
            db.execute(f"UPDATE products SET {cols} WHERE id=?", (*changes.values(), pid))
    return _product(db.one("SELECT * FROM products WHERE id=?", (pid,)))


@route("GET", "/api/products/barcode/{barcode}", "Tra cứu sản phẩm theo mã vạch", "Products", response=m.Product, errors=(404,), auth="public")
def product_by_barcode(request, body):
    code = request.path_params["barcode"]
    row = ctx_of(request).db.one("SELECT * FROM products WHERE barcode=? AND active=1", (code,))
    if not row:
        raise not_found("sản phẩm", code)
    return _product(row)


@route("GET", "/api/products/{id:int}", "Chi tiết sản phẩm", "Products", response=m.Product, errors=(404,), auth="public")
def product_by_id(request, body):
    pid = request.path_params["id"]
    row = ctx_of(request).db.one("SELECT * FROM products WHERE id=? AND active=1", (pid,))
    if not row:
        raise not_found("sản phẩm", pid)
    return _product(row)


# ------------------------------------------------------------------ carts
@route("GET", "/api/carts", "Danh sách xe kèm trạng thái", "Carts", response=[m.Cart], auth="public")
def list_carts(request, body):
    carts = cart_svc.list_carts(ctx_of(request))
    return carts if principal_of(request).is_staff else [cart_svc.public_cart(c) for c in carts]


@route("POST", "/api/carts", "Đăng ký xe mới (vd. xe phần cứng ESP32)", "Carts", body=m.CartCreate, response=m.Cart, status=201, errors=(409, 422), auth="admin")
def create_cart(request, body):
    ctx = ctx_of(request)
    if ctx.db.one("SELECT 1 AS x FROM smart_carts WHERE cart_id=?", (body.cart_id,)):
        raise conflict("CART_EXISTS", f"Xe {body.cart_id} đã tồn tại")
    now = iso()
    ctx.db.insert("INSERT INTO smart_carts(cart_id,name,created_at,updated_at) VALUES(?,?,?,?)",
                  (body.cart_id, body.name or body.cart_id, now, now))
    cart_svc.broadcast_cart(ctx, body.cart_id)
    return 201, cart_svc.cart_view(ctx, body.cart_id)


@route("GET", "/api/carts/{cart_id}", "Chi tiết một xe", "Carts", response=m.Cart, errors=(404,), auth="public")
def get_cart(request, body):
    cart = cart_svc.cart_view(ctx_of(request), request.path_params["cart_id"])
    return cart if principal_of(request).is_staff else cart_svc.public_cart(cart)


@route("GET", "/api/carts/{cart_id}/telemetry", "Lịch sử telemetry của xe", "Carts", errors=(404,), auth="staff",
       query=[("limit", "integer", "Số bản ghi mới nhất (mặc định 100, tối đa 1000)")])
def cart_telemetry(request, body):
    try:
        limit = max(1, min(1000, int(request.query_params.get("limit", 100))))
    except ValueError:
        raise bad_request("limit phải là số nguyên")
    return cart_svc.list_telemetry(ctx_of(request), request.path_params["cart_id"], limit)


@route("GET", "/api/carts/{cart_id}/session", "Phiên mua hàng đang ACTIVE của xe", "Carts", response=m.Session, errors=(404,), auth="cart_session")
def cart_active_session(request, body):
    ctx = ctx_of(request)
    cid = request.path_params["cart_id"]
    cart_svc.get_cart_row(ctx, cid)
    s = cart_svc.active_session_row(ctx, cid)
    if not s:
        raise not_found("phiên ACTIVE của xe", cid)
    return cart_svc.session_view(ctx, s)


@route("POST", "/api/carts/{cart_id}/lock", "Khoá xe (gửi LOCK_CART, chờ ACK)", "Carts", response=m.Command, errors=(404, 409, 504), auth="admin")
def lock_cart(request, body):
    status, rec = cmd_svc.lock_or_unlock(ctx_of(request), request.path_params["cart_id"], True)
    return status, rec if status == 200 else {"error": {"code": f"COMMAND_{rec['status']}", "message": rec["message"]}, "command": rec}


@route("POST", "/api/carts/{cart_id}/unlock", "Mở khoá xe (gửi UNLOCK_CART, chờ ACK)", "Carts", response=m.Command, errors=(404, 409, 504), auth="admin")
def unlock_cart(request, body):
    status, rec = cmd_svc.lock_or_unlock(ctx_of(request), request.path_params["cart_id"], False)
    return status, rec if status == 200 else {"error": {"code": f"COMMAND_{rec['status']}", "message": rec["message"]}, "command": rec}


# --------------------------------------------------------------- sessions
@route("POST", "/api/sessions", "Bắt đầu phiên mua hàng", "Sessions", body=m.SessionCreate, response=m.SessionStarted, status=201, errors=(404, 409, 429), auth="public")
def create_session(request, body):
    ctx = ctx_of(request)
    try:    # chống một IP chiếm hết xe bằng cách tạo phiên liên tục
        ctx.auth.rate_limit("session", client_ip(request), 20, 60)
    except RateLimitError as e:
        raise _limited(e)
    sess = session_svc.start_session(ctx, body.cart_id)
    if ctx.auth.enabled:
        sess["token"], sess["token_expires_in"] = ctx.auth.issue_session_token(sess["id"], sess["cart_id"])
    return 201, sess


@route("GET", "/api/sessions/{id:int}", "Chi tiết phiên (giỏ hàng, tổng tiền, cân nặng)", "Sessions", response=m.Session, errors=(404,), auth="session_read")
def get_session(request, body):
    return session_svc.get_session(ctx_of(request), request.path_params["id"])


@route("POST", "/api/sessions/{id:int}/items", "Thêm sản phẩm vào giỏ (nhập tay)", "Sessions", body=m.ItemAdd, response=m.Session, status=201, errors=(404, 409), auth="session")
def add_item(request, body):
    return 201, session_svc.add_item(ctx_of(request), request.path_params["id"], body.product_id, body.barcode, body.quantity)


@route("DELETE", "/api/sessions/{id:int}/items/{item_id:int}", "Xoá một dòng hàng khỏi giỏ", "Sessions", response=m.Session, errors=(404, 409), auth="session")
def delete_item(request, body):
    return session_svc.remove_item(ctx_of(request), request.path_params["id"], request.path_params["item_id"])


@route("POST", "/api/sessions/{id:int}/checkout", "Thanh toán & kết thúc phiên", "Sessions", response=m.Session, errors=(404, 409), auth="session")
def checkout(request, body):
    return session_svc.checkout(ctx_of(request), request.path_params["id"])


@route("POST", "/api/sessions/{id:int}/cancel", "Huỷ phiên (mở rộng)", "Sessions", response=m.Session, errors=(404, 409), auth="session")
def cancel(request, body):
    return session_svc.cancel(ctx_of(request), request.path_params["id"])


# ----------------------------------------------------------------- alerts
@route("GET", "/api/alerts", "Danh sách cảnh báo", "Alerts", response=[m.Alert], auth="staff",
       query=[("status", "string", "ACTIVE | RESOLVED"), ("cart_id", "string", "Lọc theo xe")])
def list_alerts(request, body):
    status = request.query_params.get("status")
    if status and status not in ("ACTIVE", "RESOLVED"):
        raise bad_request("status phải là ACTIVE hoặc RESOLVED")
    return alert_svc.list_alerts(ctx_of(request), status, request.query_params.get("cart_id"))


@route("GET", "/api/commands", "Danh sách các lệnh đã gửi xuống xe", "Commands", response=[m.Command], auth="staff",
       query=[("cart_id", "string", "Lọc theo xe"), ("limit", "int", "Số lượng tối đa (mặc định 50)")])
def list_commands(request, body):
    cart_id = request.query_params.get("cart_id")
    try:
        limit = int(request.query_params.get("limit", 50))
    except ValueError:
        limit = 50
    return cmd_svc.list_commands(ctx_of(request), cart_id=cart_id, limit=limit)


@route("GET", "/api/commands/{command_id}", "Trạng thái một lệnh đã gửi xuống xe", "Commands", response=m.Command, errors=(404,), auth="staff")
def get_command(request, body):
    return cmd_svc.get_command(ctx_of(request), request.path_params["command_id"])


# ------------------------------------------------------------------- auth
@route("GET", "/api/auth/config", "Máy chủ có yêu cầu đăng nhập không", "Auth", response=m.AuthConfig, auth="public")
def auth_config(request, body):
    return {"auth_required": ctx_of(request).auth.enabled}


@route("POST", "/api/auth/login", "Đăng nhập quản trị -> token Bearer", "Auth", body=m.LoginRequest, response=m.LoginResponse,
       errors=(401, 422, 429), auth="public")
def login(request, body):
    auth = ctx_of(request).auth
    if not auth.enabled:
        raise bad_request("Máy chủ chạy AUTH_ENABLED=0, không cần đăng nhập", "AUTH_DISABLED")
    try:
        token, p, ttl = auth.login(body.username, body.password, client_ip(request))
    except RateLimitError as e:
        raise _limited(e)
    except PermissionError as e:
        raise ApiError(401, "INVALID_CREDENTIALS", str(e))
    return {"token": token, "token_type": "Bearer", "expires_in": ttl, "role": p.role, "username": p.name}


@route("GET", "/api/auth/me", "Thông tin người đang đăng nhập", "Auth", response=m.Me, errors=(401,), auth="authenticated")
def me(request, body):
    p = principal_of(request)
    return {"role": p.role, "username": p.name, "session_id": p.session_id, "cart_id": p.cart_id}


@route("POST", "/api/auth/logout", "Đăng xuất (thu hồi token hiện tại)", "Auth", errors=(401,), auth="authenticated")
def logout(request, body):
    ctx_of(request).auth.revoke(principal_of(request))
    return {"ok": True}
