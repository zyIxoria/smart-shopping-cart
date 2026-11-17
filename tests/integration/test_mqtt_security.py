"""Bảo mật tầng MQTT: đăng nhập broker, ACL theo vai trò, TLS, ký HMAC end-to-end."""
from __future__ import annotations

import json
import shutil
import ssl
import threading
import time

import pytest
import uvicorn

from backend.api.app import create_app
from backend.config import Settings
from shared import contract, security
from shared.mqttlite import MqttClient, make_tls_context
from simulator.cart import SmartCart
from simulator.config import SimConfig
from tools import provision
from tools.dev_broker import Acl, DevBroker, covers, load_users

from tests.conftest import Api, free_port, wait_until

needs_openssl = pytest.mark.skipif(not shutil.which("openssl"), reason="cần openssl")


@pytest.fixture(scope="module")
def prov(tmp_path_factory):
    out = tmp_path_factory.mktemp("secrets")
    # PBKDF2 ít vòng cho nhanh – hash vẫn đúng định dạng
    import os
    os.environ["PBKDF2_ITERATIONS"] = "2000"
    st = provision.provision(out, ["CART_001", "CART_002", "CART_003"], tls=bool(shutil.which("openssl")))
    return out, st


def connect(host, port, user, pw, tls=None, wait=3.0):
    c = MqttClient(f"t-{user}-{time.time_ns()}", host, port, username=user, password=pw, tls=tls)
    c.start()
    ok = c.wait_connected(wait)
    return c, ok


# ------------------------------------------------------------------- khớp ACL (hàm thuần)
def test_covers_pattern():
    assert covers("smartcart/+/scan", "smartcart/+/scan")
    assert covers("smartcart/+/scan", "smartcart/CART_001/scan")
    assert not covers("smartcart/+/scan", "smartcart/#")
    assert not covers("smartcart/CART_001/command", "smartcart/+/command")      # xe không được nghe lệnh của xe khác
    assert not covers("smartcart/CART_001/command", "smartcart/CART_002/command")
    assert covers("smartcart/CART_001/command", "smartcart/CART_001/command")


def test_acl_roles():
    a = Acl("smartcart")
    assert a.can_subscribe("backend", "backend", "smartcart/+/telemetry")
    assert not a.can_subscribe("backend", "backend", "smartcart/+/command")
    assert a.can_publish("backend", "backend", "smartcart/CART_001/command")
    assert not a.can_publish("backend", "backend", "smartcart/CART_001/scan")
    assert a.can_publish("CART_001", "cart", "smartcart/CART_001/scan")
    assert not a.can_publish("CART_001", "cart", "smartcart/CART_002/scan")
    assert not a.can_publish("CART_001", "cart", "smartcart/CART_001/command")   # xe không tự ra lệnh cho mình
    assert a.can_subscribe("CART_001", "cart", "smartcart/CART_001/command")
    assert not a.can_subscribe("CART_001", "cart", "smartcart/#")
    assert a.can_publish("simulator", "sim", "smartcart/CART_003/ack")


# ------------------------------------------------------------------- đăng nhập + ACL trên broker thật
def test_broker_requires_login_and_enforces_acl(prov):
    out, _ = prov
    st = json.loads((out / "state.json").read_text())
    broker = DevBroker("127.0.0.1", 0, users=load_users(str(out / "mqtt_users.json"))).start_in_thread()
    clients = []
    try:
        # không đăng nhập / sai mật khẩu / user lạ -> bị từ chối
        c, ok = connect("127.0.0.1", broker.port, "", "", wait=1.5)
        clients.append(c)
        assert not ok and "từ chối" in (c.last_error or "")
        c, ok = connect("127.0.0.1", broker.port, "CART_001", "sai-mat-khau", wait=1.5)
        clients.append(c)
        assert not ok and "mã 4" in (c.last_error or "")
        c, ok = connect("127.0.0.1", broker.port, "ke-la-mat", "x", wait=1.5)
        clients.append(c)
        assert not ok
        assert broker.auth_failed >= 3

        # đúng mật khẩu
        backend, ok = connect("127.0.0.1", broker.port, "backend", st["backend_password"])
        clients.append(backend)
        assert ok
        cart, ok = connect("127.0.0.1", broker.port, "CART_001", st["cart_passwords"]["CART_001"])
        clients.append(cart)
        assert ok

        got = []
        backend.on_message = lambda t, p: got.append(t)
        backend.subscribe("smartcart/+/scan")
        cart2_got = []
        cart.on_message = lambda t, p: cart2_got.append(t)
        cart.subscribe("smartcart/CART_001/command")
        cart.subscribe("smartcart/CART_002/command")     # bị ACL chặn
        time.sleep(0.3)

        # xe 1 gửi vào topic của mình -> tới backend; gửi giả danh xe 2 -> bị chặn
        assert cart.publish("smartcart/CART_001/scan", b"{}")
        cart.publish("smartcart/CART_002/scan", b"{}")
        cart.publish("smartcart/CART_001/command", b"{}")     # xe tự ra lệnh -> chặn
        wait_until(lambda: got == ["smartcart/CART_001/scan"], msg="chỉ topic hợp lệ tới backend")
        time.sleep(0.3)
        assert got == ["smartcart/CART_001/scan"]
        assert broker.denied >= 3          # 1 subscribe + 2 publish

        # backend ra lệnh cho đúng xe 1; xe 2 không nghe được; backend không được publish uplink
        backend.publish("smartcart/CART_001/command", b"{}")
        backend.publish("smartcart/CART_001/scan", b"{}")
        wait_until(lambda: cart2_got == ["smartcart/CART_001/command"], msg="xe nhận lệnh của mình")
    finally:
        for c in clients:
            c.stop()
        broker.stop()


def test_packet_before_connect_is_dropped(prov):
    import socket
    out, _ = prov
    broker = DevBroker("127.0.0.1", 0, users=load_users(str(out / "mqtt_users.json"))).start_in_thread()
    try:
        s = socket.create_connection(("127.0.0.1", broker.port), timeout=2)
        s.sendall(b"\x30\x08\x00\x05a/b/cx")        # PUBLISH khi chưa CONNECT
        s.settimeout(2)
        assert s.recv(10) == b""                    # broker đóng kết nối
        s.close()
        assert broker.published == 0
    finally:
        broker.stop()


# ------------------------------------------------------------------- TLS
@needs_openssl
def test_tls_encrypts_and_verifies_certificate(prov):
    out, st = prov
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(out / "tls" / "server.crt", out / "tls" / "server.key")
    broker = DevBroker("127.0.0.1", 0, users=load_users(str(out / "mqtt_users.json")), ssl_context=ctx).start_in_thread()
    cs = []
    try:
        good = make_tls_context(str(out / "tls" / "ca.crt"))
        c, ok = connect("127.0.0.1", broker.port, "backend", st["backend_password"], tls=good)
        cs.append(c)
        assert ok, c.last_error
        assert c._sock.version() in ("TLSv1.2", "TLSv1.3")

        # CA lạ -> client từ chối chứng chỉ giả mạo broker (chống Fake Control Server)
        c, ok = connect("127.0.0.1", broker.port, "backend", st["backend_password"], tls=make_tls_context(None), wait=1.5)
        cs.append(c)
        assert not ok and "CERTIFICATE" in (c.last_error or "").upper()

        # kết nối thuần (không TLS) vào cổng TLS -> không dùng được
        c, ok = connect("127.0.0.1", broker.port, "backend", st["backend_password"], wait=1.5)
        cs.append(c)
        assert not ok
    finally:
        for c in cs:
            c.stop()
        broker.stop()


# ------------------------------------------------------------------- end-to-end: broker bảo mật + Backend + xe ký HMAC
@pytest.fixture()
def secure_stack(prov, tmp_path):
    out, pst = prov
    use_tls = (out / "tls" / "ca.crt").exists()
    ctx = None
    if use_tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(out / "tls" / "server.crt", out / "tls" / "server.key")
    st = type("S", (), {})()
    st.pst = pst
    st.broker = DevBroker("127.0.0.1", 0, users=load_users(str(out / "mqtt_users.json")), ssl_context=ctx).start_in_thread()
    s = Settings()
    s.auth_enabled = False
    s.db_path = str(tmp_path / "t.db")
    s.mqtt_host, s.mqtt_port = "127.0.0.1", st.broker.port
    s.mqtt_username, s.mqtt_password = "backend", pst["backend_password"]
    s.mqtt_tls, s.mqtt_ca_file = use_tls, str(out / "tls" / "ca.crt")
    s.device_master_key = pst["master_key"]
    s.require_signature = None            # mặc định: có khoá chủ => bắt buộc ký
    s.port, s.ws_port = free_port(), free_port()
    s.host = "127.0.0.1"
    s.heartbeat_timeout_s, s.monitor_interval_s, s.command_ack_timeout_s = 1.5, 0.25, 3
    st.settings = s
    st.app = create_app(s)
    st.ctx = st.app.state.ctx
    st.server = uvicorn.Server(uvicorn.Config(st.app, host="127.0.0.1", port=s.port, log_level="error"))
    st.thread = threading.Thread(target=st.server.run, daemon=True)
    st.thread.start()
    st.api = Api(f"http://127.0.0.1:{s.port}")
    wait_until(lambda: st.api.get("/api/health")[0] == 200, msg="backend")
    wait_until(lambda: st.ctx.gateway.connected, msg="backend nối broker bảo mật")

    sc = SimConfig()
    sc.mqtt_host, sc.mqtt_port = "127.0.0.1", st.broker.port
    sc.heartbeat_s, sc.telemetry_s, sc.noise_g, sc.battery_drain_per_min = 0.4, 0.8, 0.0, 0.0
    sc.device_master_key = pst["master_key"]
    sc.mqtt_options = {"username": "simulator", "password": pst["sim_password"]}
    if use_tls:
        sc.mqtt_options["tls"] = make_tls_context(str(out / "tls" / "ca.crt"))
    st.sc = sc
    st.carts = {cid: SmartCart(cid, sc, sc.catalog()) for cid in sc.cart_ids()}
    for c in st.carts.values():
        c.start()
    wait_until(lambda: all(c["connection_status"] == "ONLINE" for c in st.api.get("/api/carts")[1]), msg="xe ONLINE")
    st.use_tls, st.out = use_tls, out
    yield st
    for c in st.carts.values():
        c.stop()
    st.server.should_exit = True
    st.thread.join(timeout=5)
    st.broker.stop()


def test_secure_stack_full_flow(secure_stack):
    st = secure_stack
    api = st.api
    code, sess = api.post("/api/sessions", {"cart_id": "CART_001"})
    assert code == 201
    barcode = api.get("/api/products")[1][0]["barcode"]
    st.carts["CART_001"].scan(barcode)
    wait_until(lambda: api.get(f"/api/sessions/{sess['id']}")[1]["item_count"] == 1, msg="quét đã ký được nhận")
    # lệnh Backend -> xe cũng được ký và xe chấp nhận
    code, cmd = api.post("/api/carts/CART_002/lock")
    assert code == 200 and cmd["status"] == "OK"
    assert st.carts["CART_002"].mqtt.rejected == {"unsigned": 0, "bad_signature": 0, "stale": 0}
    assert st.ctx.stats["mqtt_bad_signature"] == 0 and st.ctx.stats["mqtt_unsigned"] == 0


def _attacker(st, user="CART_001", pw=None):
    """Kẻ có tài khoản MQTT hợp lệ của một xe (vd. đánh cắp mật khẩu) nhưng KHÔNG có khoá HMAC."""
    pw = pw or st.pst["cart_passwords"][user]
    tls = make_tls_context(str(st.out / "tls" / "ca.crt")) if st.use_tls else None
    c, ok = connect("127.0.0.1", st.broker.port, user, pw, tls=tls)
    assert ok, c.last_error
    return c


def test_forged_messages_are_rejected(secure_stack):
    st = secure_stack
    api = st.api
    api.post("/api/sessions", {"cart_id": "CART_001"})
    atk = _attacker(st)
    try:
        before = dict(st.ctx.stats)
        bc = api.get("/api/products")[1][0]["barcode"]
        # 1) không ký
        env = contract.envelope("CART_001", {"barcode": bc, "action": "ADD"})
        atk.publish(contract.topic("CART_001", "scan"), contract.encode(env))
        # 2) ký bằng khoá sai
        env = contract.envelope("CART_001", {"barcode": bc, "action": "ADD"})
        atk.publish(contract.topic("CART_001", "scan"), contract.encode_signed(env, b"k" * 32, "scan"))
        # 3) chữ ký đúng nhưng sửa data sau khi ký
        key = security.derive_cart_key(st.pst["master_key"], "CART_001")
        good = contract.encode_signed(contract.envelope("CART_001", {"barcode": bc, "action": "ADD"}), key, "scan")
        atk.publish(contract.topic("CART_001", "scan"), good.replace(b'"ADD"', b'"REMOVE"'))
        # 4) chữ ký đúng của topic khác (scan) nhưng phát vào topic heartbeat
        atk.publish(contract.topic("CART_001", "heartbeat"), good)
        wait_until(lambda: st.ctx.stats["mqtt_received"] >= before["mqtt_received"] + 4, msg="backend nhận 4 gói")
        time.sleep(0.2)
        assert st.ctx.stats["mqtt_unsigned"] == before["mqtt_unsigned"] + 1
        assert st.ctx.stats["mqtt_bad_signature"] == before["mqtt_bad_signature"] + 3
        s = api.get("/api/carts/CART_001/session")[1]
        assert s["item_count"] == 0
    finally:
        atk.stop()


def test_replay_of_valid_message_is_ignored_and_stale_is_dropped(secure_stack):
    st = secure_stack
    api = st.api
    _, sess = api.post("/api/sessions", {"cart_id": "CART_003"})
    key = security.derive_cart_key(st.pst["master_key"], "CART_003")
    bc = api.get("/api/products")[1][0]["barcode"]
    # kẻ nghe lén có tài khoản đúng cart (CART_003) bắt được 1 gói hợp lệ rồi phát lại
    atk = _attacker(st, "CART_003")
    try:
        good = contract.encode_signed(contract.envelope("CART_003", {"barcode": bc, "action": "ADD"}), key, "scan")
        atk.publish(contract.topic("CART_003", "scan"), good)
        wait_until(lambda: api.get(f"/api/sessions/{sess['id']}")[1]["item_count"] == 1, msg="gói đầu tiên")
        dup = st.ctx.stats["mqtt_duplicate"]
        for _ in range(3):
            atk.publish(contract.topic("CART_003", "scan"), good)
        wait_until(lambda: st.ctx.stats["mqtt_duplicate"] == dup + 3, msg="3 gói phát lại bị chặn")
        assert api.get(f"/api/sessions/{sess['id']}")[1]["item_count"] == 1
        # gói ký đúng nhưng quá cũ (phát lại sau hàng giờ)
        old = contract.envelope("CART_003", {"barcode": bc, "action": "ADD"}, timestamp="2020-01-01T00:00:00Z")
        stale = st.ctx.stats["mqtt_stale"]
        atk.publish(contract.topic("CART_003", "scan"), contract.encode_signed(old, key, "scan"))
        wait_until(lambda: st.ctx.stats["mqtt_stale"] == stale + 1, msg="gói cũ bị loại")
    finally:
        atk.stop()


def test_cart_ignores_unsigned_and_foreign_commands(secure_stack):
    """Kẻ có tài khoản `backend`... không có thật; giả định kẻ publish được vào command (broker cấu hình sai)."""
    st = secure_stack
    cart = st.carts["CART_002"]
    cmd = {"command_id": "evil-1", "command_type": "UNLOCK_CART", "parameters": {}}
    cart.mqtt._message(contract.topic("CART_002", "command"), contract.encode(contract.envelope("CART_002", cmd)))
    cart.mqtt._message(contract.topic("CART_002", "command"),
                       contract.encode_signed(contract.envelope("CART_002", cmd), b"z" * 32, "command"))
    # khoá đúng của xe KHÁC cũng không dùng được cho xe này
    other = security.derive_cart_key(st.pst["master_key"], "CART_001")
    cart.mqtt._message(contract.topic("CART_002", "command"),
                       contract.encode_signed(contract.envelope("CART_002", cmd), other, "command"))
    # lệnh ký đúng nhưng cũ
    key = security.derive_cart_key(st.pst["master_key"], "CART_002")
    old = contract.envelope("CART_002", {**cmd, "command_id": "evil-2"}, timestamp="2020-01-01T00:00:00Z")
    cart.mqtt._message(contract.topic("CART_002", "command"), contract.encode_signed(old, key, "command"))
    assert cart.mqtt.rejected == {"unsigned": 1, "bad_signature": 2, "stale": 1}
    assert "evil-1" not in cart._handled and "evil-2" not in cart._handled


def test_unsigned_allowed_only_in_migration_mode(secure_stack):
    st = secure_stack
    st.settings.require_signature = False       # chế độ chuyển đổi: xe cũ chưa ký vẫn chạy
    atk = _attacker(st, "CART_003")
    try:
        before = st.ctx.stats["mqtt_received"]
        atk.publish(contract.topic("CART_003", "heartbeat"),
                    contract.encode(contract.envelope("CART_003", {"uptime_s": 1})))
        wait_until(lambda: st.ctx.stats["mqtt_received"] > before, msg="nhận gói")
        assert st.ctx.stats["mqtt_unsigned"] == 0
        # nhưng gói CÓ chữ ký sai vẫn bị loại
        bad = contract.encode_signed(contract.envelope("CART_003", {"uptime_s": 1}), b"q" * 32, "heartbeat")
        atk.publish(contract.topic("CART_003", "heartbeat"), bad)
        wait_until(lambda: st.ctx.stats["mqtt_bad_signature"] == 1, msg="chữ ký sai vẫn bị loại")
    finally:
        atk.stop()
