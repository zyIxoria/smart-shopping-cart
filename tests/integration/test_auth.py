"""Đăng nhập, phân quyền REST và phạm vi sự kiện WebSocket (I1/I2/I5 trong docs/SECURITY.md)."""
from __future__ import annotations

import base64
import json
import os
import socket
import struct
import time

import pytest

from backend.auth import AuthService, allowed, Principal, ANONYMOUS
from backend.config import Settings
from shared import security
from tests.conftest import ADMIN_PW, wait_until


# ---------------------------------------------------------------- đơn vị: băm mật khẩu + token
def test_password_hash_roundtrip():
    h = security.hash_password("mật-khẩu-đúng", iterations=2000)
    assert h.startswith("pbkdf2_sha256$2000$")
    assert security.verify_password("mật-khẩu-đúng", h)
    assert not security.verify_password("mật-khẩu-sai", h)
    assert not security.verify_password("x", "rác")
    assert security.hash_password("a", 1000) != security.hash_password("a", 1000)      # salt ngẫu nhiên


def test_token_tamper_and_expiry():
    sec = b"s" * 32
    t = security.make_token(sec, {"role": "admin", "sub": "a"}, 60)
    assert security.verify_token(sec, t)["role"] == "admin"
    assert security.verify_token(b"x" * 32, t) is None                                   # khoá khác
    head, sig = t.split(".")
    forged = security.b64e(json.dumps({"role": "admin", "sub": "a", "exp": 9e9}).encode()) + "." + sig
    assert security.verify_token(sec, forged) is None                                    # sửa payload
    assert security.verify_token(sec, t, now=time.time() + 61) is None                   # hết hạn
    assert security.verify_token(sec, "a.b.c") is None and security.verify_token(sec, "") is None


def test_policy_matrix():
    admin, viewer = Principal("admin", "a"), Principal("viewer", "v")
    cust = Principal("customer", "c", session_id=7, cart_id="CART_001")
    assert allowed("public", ANONYMOUS, {})
    assert not allowed("staff", ANONYMOUS, {}) and allowed("staff", viewer, {}) and not allowed("staff", cust, {})
    assert allowed("admin", admin, {}) and not allowed("admin", viewer, {})
    assert allowed("session", cust, {"id": 7}) and not allowed("session", cust, {"id": 8})
    assert allowed("session", admin, {"id": 8}) and not allowed("session", viewer, {"id": 8})
    assert allowed("session_read", viewer, {"id": 8}) and not allowed("session_read", ANONYMOUS, {"id": 7})
    assert allowed("cart_session", cust, {"cart_id": "CART_001"}) and not allowed("cart_session", cust, {"cart_id": "CART_002"})
    assert not allowed("không-tồn-tại", admin, {})        # fail closed


def test_generated_admin_password_when_unset():
    s = Settings()
    s.auth_enabled, s.admin_password, s.admin_password_hash = True, "", ""
    a = AuthService(s)
    assert a.generated_admin_password and len(a.generated_admin_password) >= 12
    tok, p, _ = a.login("admin", a.generated_admin_password, "1.1.1.1")
    assert p.role == "admin" and a.authenticate_token(tok).role == "admin"


# ---------------------------------------------------------------- REST
def test_login_and_me(auth_stack):
    st = auth_stack
    assert st.anon.get("/api/auth/config") == (200, {"auth_required": True})
    code, r = st.anon.post("/api/auth/login", {"username": "admin", "password": "sai"})
    assert code == 401 and r["error"]["code"] == "INVALID_CREDENTIALS"
    code, r = st.anon.post("/api/auth/login", {"username": "khong-co", "password": "x"})
    assert code == 401 and r["error"]["message"] == "Sai tên đăng nhập hoặc mật khẩu"     # không lộ user nào tồn tại
    assert st.admin.get("/api/auth/me")[1]["role"] == "admin"
    assert st.viewer.get("/api/auth/me")[1]["role"] == "viewer"
    assert st.anon.get("/api/auth/me")[0] == 401


def test_login_lockout_then_recovers(auth_stack):
    st = auth_stack
    for _ in range(3):
        assert st.anon.post("/api/auth/login", {"username": "admin", "password": "sai"})[0] == 401
    code, r = st.anon.post("/api/auth/login", {"username": "admin", "password": ADMIN_PW})
    assert code == 429 and r["error"]["code"] == "TOO_MANY_REQUESTS"        # đúng mật khẩu vẫn bị khoá khi đang khoá
    time.sleep(1.2)
    assert st.anon.post("/api/auth/login", {"username": "admin", "password": ADMIN_PW})[0] == 200


def test_anonymous_can_only_use_public_endpoints(auth_stack):
    a = auth_stack.anon
    assert a.get("/api/products")[0] == 200
    assert a.get("/api/carts")[0] == 200
    assert a.get("/api/carts/CART_001")[0] == 200
    h = a.get("/api/health")[1]
    assert set(h) == {"status", "time", "ws_port"}                        # không lộ thống kê/số client
    for method, path in [("GET", "/api/alerts"), ("GET", "/api/carts/CART_001/telemetry"), ("GET", "/api/carts/CART_001/session"),
                         ("POST", "/api/carts/CART_001/lock"), ("POST", "/api/carts/CART_001/unlock"),
                         ("POST", "/api/carts"), ("GET", "/api/commands/x"), ("GET", "/api/sessions/1"),
                         ("POST", "/api/sessions/1/checkout"), ("POST", "/api/sessions/1/items"), ("DELETE", "/api/sessions/1/items/1"),
                         ("POST", "/api/sessions/1/cancel")]:
        code, r = a.call(method, path, {} if method != "GET" else None)
        assert code == 401, (method, path, code)
        assert r["error"]["code"] == "UNAUTHENTICATED"


def test_bad_or_expired_token_is_401(auth_stack):
    st = auth_stack
    assert st.anon.with_token("rác").get("/api/alerts")[0] == 401
    forged = security.make_token(b"khoa-khac-khoa-khac-khoa-khac-!", {"role": "admin", "sub": "admin", "jti": "x"}, 60)
    assert st.anon.with_token(forged).get("/api/alerts")[0] == 401
    expired = security.make_token(st.ctx.auth.secret, {"role": "admin", "sub": "admin", "jti": "x"}, -5)
    assert st.anon.with_token(expired).get("/api/alerts")[0] == 401
    ghost = security.make_token(st.ctx.auth.secret, {"role": "admin", "sub": "da-bi-xoa", "jti": "y"}, 60)
    assert st.anon.with_token(ghost).get("/api/alerts")[0] == 401


def test_viewer_is_read_only(auth_stack):
    v = auth_stack.viewer
    assert v.get("/api/alerts")[0] == 200
    assert v.get("/api/carts/CART_001/telemetry")[0] == 200
    assert v.get("/api/health")[1]["stats"] is not None
    for method, path in [("POST", "/api/carts/CART_001/lock"), ("POST", "/api/carts"), ("POST", "/api/sessions/1/cancel")]:
        code, r = v.call(method, path, {"cart_id": "CART_099"} if path == "/api/carts" else {})
        assert code == 403 and r["error"]["code"] == "FORBIDDEN", (path, code)


def test_admin_can_do_everything(auth_stack):
    ad = auth_stack.admin
    assert ad.get("/api/alerts")[0] == 200
    assert ad.post("/api/carts", {"cart_id": "CART_099"})[0] == 201
    code, cmd = ad.post("/api/carts/CART_002/lock")
    assert code == 200 and cmd["status"] == "OK"
    assert ad.post("/api/carts/CART_002/unlock")[0] == 200


def test_customer_token_is_bound_to_own_session(auth_stack):
    st = auth_stack
    code, s1 = st.anon.post("/api/sessions", {"cart_id": "CART_001"})
    assert code == 201 and s1["token"] and s1["token_expires_in"] > 0
    code, s2 = st.anon.post("/api/sessions", {"cart_id": "CART_002"})
    c1, c2 = st.anon.with_token(s1["token"]), st.anon.with_token(s2["token"])
    barcode = st.anon.get("/api/products")[1][0]["barcode"]

    assert c1.get(f"/api/sessions/{s1['id']}")[0] == 200
    assert c1.post(f"/api/sessions/{s1['id']}/items", {"barcode": barcode, "quantity": 1})[0] == 201
    # IDOR: khách 1 không đọc/sửa/thanh toán phiên của khách 2
    assert c1.get(f"/api/sessions/{s2['id']}")[0] == 403
    assert c1.post(f"/api/sessions/{s2['id']}/items", {"barcode": barcode, "quantity": 1})[0] == 403
    assert c1.post(f"/api/sessions/{s2['id']}/checkout")[0] == 403
    assert c1.post(f"/api/sessions/{s2['id']}/cancel")[0] == 403
    assert c1.get("/api/carts/CART_002/session")[0] == 403
    assert c1.get("/api/carts/CART_001/session")[0] == 200
    # khách không có quyền quản trị
    assert c1.post("/api/carts/CART_001/lock")[0] == 403
    assert c1.get("/api/alerts")[0] == 403
    assert c1.get("/api/carts/CART_001/telemetry")[0] == 403
    # token của khách không "leo thang" thành admin
    assert c1.get("/api/auth/me")[1]["role"] == "customer"
    # quyền xem giỏ của khách 2 không bị rò qua danh sách xe
    carts = {c["cart_id"]: c for c in st.anon.get("/api/carts")[1]}
    assert set(carts["CART_002"]["session"]) == {"id", "started_at"}
    assert "total_amount" in st.admin.get("/api/carts")[1][1]["session"]
    # admin vẫn xử lý được phiên bất kỳ; thanh toán xong khách vẫn xem được hoá đơn của mình
    assert st.admin.get(f"/api/sessions/{s2['id']}")[0] == 200
    assert c2.post(f"/api/sessions/{s2['id']}/cancel")[0] == 200


def test_logout_revokes_token(auth_stack):
    st = auth_stack
    code, r = st.anon.post("/api/auth/login", {"username": "admin", "password": ADMIN_PW})
    t = st.anon.with_token(r["token"])
    assert t.get("/api/alerts")[0] == 200
    assert t.post("/api/auth/logout")[0] == 200
    assert t.get("/api/alerts")[0] == 401
    assert st.admin.get("/api/alerts")[0] == 200            # token khác của cùng người dùng không bị ảnh hưởng


def test_session_creation_is_rate_limited(auth_stack):
    st = auth_stack
    codes = [st.anon.post("/api/sessions", {"cart_id": "CART_NOPE"})[0] for _ in range(22)]
    assert codes.count(429) >= 2 and codes[0] == 404


def test_security_headers_and_body_limit(auth_stack):
    import urllib.request
    base = auth_stack.anon.base
    with urllib.request.urlopen(base + "/api/products") as r:
        h = r.headers
        assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY"
        assert h["Cache-Control"] == "no-store"
    with urllib.request.urlopen(base + "/") as r:
        assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    big = {"username": "a" * 70000, "password": "x"}
    assert auth_stack.anon.post("/api/auth/login", big)[0] == 413


def test_openapi_documents_security(auth_stack):
    spec = auth_stack.anon.get("/api/openapi.json")[1]
    assert "bearerAuth" in spec["components"]["securitySchemes"]
    assert "security" in spec["paths"]["/api/alerts"]["get"]
    assert "security" not in spec["paths"]["/api/products"]["get"]


# ---------------------------------------------------------------- WebSocket
class Ws:
    def __init__(self, port, origin=None):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=3)
        key = base64.b64encode(os.urandom(16)).decode()
        extra = f"Origin: {origin}\r\n" if origin else ""
        self.s.sendall((f"GET /ws HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n{extra}\r\n").encode())
        self.head = b""
        while b"\r\n\r\n" not in self.head:
            chunk = self.s.recv(1)
            if not chunk:
                break
            self.head += chunk
        self.buf = b""

    def send(self, obj):
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.s.sendall(bytes([0x81, 0x80 | len(data)]) + mask + masked if len(data) < 126
                       else bytes([0x81, 0x80 | 126]) + struct.pack(">H", len(data)) + mask + masked)

    def events(self, wait=0.6):
        out = []
        end = time.time() + wait            # hạn tổng: nguồn sự kiện (heartbeat/telemetry) không bao giờ ngừng
        try:
            while True:
                left = end - time.time()
                if left <= 0:
                    break
                self.s.settimeout(left)
                chunk = self.s.recv(65536)
                if not chunk:
                    break
                self.buf += chunk
        except (socket.timeout, TimeoutError):
            pass
        b = self.buf
        while len(b) >= 2:
            n = b[1] & 0x7F
            off = 2
            if n == 126:
                n, off = struct.unpack(">H", b[2:4])[0], 4
            if len(b) < off + n:
                break
            out.append(json.loads(b[off:off + n]))
            b = b[off + n:]
        self.buf = b
        return out

    def close(self):
        self.s.close()


def test_websocket_scopes(auth_stack):
    st = auth_stack
    port = st.settings.ws_port
    _, s1 = st.anon.post("/api/sessions", {"cart_id": "CART_001"})
    anon, adm, cust = Ws(port), Ws(port), Ws(port)
    try:
        adm.send({"type": "AUTH", "token": st.admin.token})
        cust.send({"type": "AUTH", "token": s1["token"]})
        for w in (anon, adm, cust):
            w.events(0.3)
        bad = Ws(port)
        bad.send({"type": "AUTH", "token": "rác"})
        assert "AUTH_FAILED" in [e["type"] for e in bad.events(0.5)]
        bad.close()

        # sinh sự kiện: cập nhật xe, cảnh báo pin thấp (staff-only), quét sai (xe 1)
        st.sim.post("/sim/carts/CART_001/battery", {"percent": 5})
        st.sim.post("/sim/carts/CART_001/scan", {"barcode": "0000000000000", "action": "ADD"})
        wait_until(lambda: any(a["alert_type"] == "LOW_BATTERY" for a in st.admin.get("/api/alerts")[1]), msg="cảnh báo")
        ta = {e["type"] for e in anon.events()}
        tc = [e for e in cust.events()]
        tadm = {e["type"] for e in adm.events()}
        assert "ALERT_TRIGGERED" in tadm and "CART_UPDATED" in tadm
        assert ta <= {"CART_UPDATED"}, ta                              # ẩn danh: chỉ trạng thái xe đã che
        types_c = {e["type"] for e in tc}
        assert "ALERT_TRIGGERED" not in types_c and "COMMAND_ACK" not in types_c
        assert "SCAN_REJECTED" in types_c                              # khách thấy lỗi quét của XE MÌNH
    finally:
        for w in (anon, adm, cust):
            w.close()


def test_websocket_anonymous_sees_no_basket_details(auth_stack):
    st = auth_stack
    _, s1 = st.anon.post("/api/sessions", {"cart_id": "CART_003"})
    anon, adm = Ws(st.settings.ws_port), Ws(st.settings.ws_port)
    try:
        adm.send({"type": "AUTH", "token": st.admin.token})
        anon.events(0.3), adm.events(0.3)
        st.anon.with_token(s1["token"]).post(f"/api/sessions/{s1['id']}/items",
                                              {"barcode": st.anon.get("/api/products")[1][0]["barcode"], "quantity": 2})
        ev_a = [e for e in anon.events(1.0) if e["type"] == "CART_UPDATED" and e["cart_id"] == "CART_003"]
        ev_s = [e for e in adm.events(0.5) if e["type"] == "CART_UPDATED" and e["cart_id"] == "CART_003"]
        assert ev_a and ev_s
        assert set(ev_a[-1]["cart"]["session"]) == {"id", "started_at"}
        assert ev_s[-1]["cart"]["session"]["item_count"] == 2
    finally:
        anon.close()
        adm.close()


def test_websocket_origin_check(tmp_path):
    from tests.conftest import make_stack, close_stack
    st = make_stack(tmp_path, cors_origins=["http://app.example"])
    try:
        ok = Ws(st.settings.ws_port, origin="http://app.example")
        assert b"101" in ok.head
        ok.close()
        evil = Ws(st.settings.ws_port, origin="http://evil.example")
        assert b"403" in evil.head
        evil.close()
    finally:
        close_stack(st)
