"""Fixture dùng chung: stack tích hợp trong tiến trình (broker + backend thật + simulator)."""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.request
import urllib.error

import pytest
import uvicorn

from backend.api.app import create_app
from backend.config import Settings
from simulator.cart import SmartCart
from simulator.config import SimConfig
from simulator.control import ControlServer
from tools.dev_broker import DevBroker

os.environ.setdefault("PBKDF2_ITERATIONS", "2000")     # băm mật khẩu nhanh hơn trong test (định dạng không đổi)
ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(fn, timeout=8.0, interval=0.05, msg="điều kiện không đạt"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = fn()
            if last:
                return last
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(interval)
    raise AssertionError(f"Hết thời gian chờ: {msg} (cuối cùng: {last!r})")


class Api:
    def __init__(self, base, token=None):
        self.base = base
        self.token = token

    def with_token(self, token):
        return Api(self.base, token)

    def call(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        h = {"Content-Type": "application/json", **(headers or {})}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raw = e.read()
            return e.code, json.loads(raw) if raw else None

    def get(self, path):
        return self.call("GET", path)

    def post(self, path, body=None):
        return self.call("POST", path, body or {})

    def delete(self, path):
        return self.call("DELETE", path)

    def put(self, path, body=None):
        return self.call("PUT", path, body or {})


class Stack:
    pass


def make_stack(tmp_path, **overrides):
    """Broker + Backend (uvicorn thật) + 3 xe giả lập, thời gian rút ngắn cho test. overrides -> thuộc tính Settings."""
    st = Stack()
    st.broker = DevBroker("127.0.0.1", 0).start_in_thread()
    s = Settings()
    s.auth_enabled = False          # test nghiệp vụ chạy không đăng nhập; test đăng nhập dùng fixture auth_stack
    for k, v in overrides.items():
        setattr(s, k, v)
    s.db_path = str(tmp_path / "t.db")
    s.mqtt_host, s.mqtt_port = "127.0.0.1", st.broker.port
    s.port, s.ws_port = free_port(), free_port()
    s.host = "127.0.0.1"
    s.heartbeat_timeout_s = 1.5
    s.monitor_interval_s = 0.25
    s.command_ack_timeout_s = 3
    s.frontend_dist = str(ROOT / "frontend" / "dist")
    st.settings = s
    st.app = create_app(s)
    st.ctx = st.app.state.ctx
    cfg = uvicorn.Config(st.app, host="127.0.0.1", port=s.port, log_level="error")
    st.server = uvicorn.Server(cfg)
    st.thread = threading.Thread(target=st.server.run, daemon=True)
    st.thread.start()
    st.api = Api(f"http://127.0.0.1:{s.port}")
    wait_until(lambda: st.api.get("/api/health")[0] == 200, msg="backend khởi động")
    wait_until(lambda: st.ctx.gateway.connected, msg="backend nối MQTT")

    sc = SimConfig()
    sc.mqtt_host, sc.mqtt_port = "127.0.0.1", st.broker.port
    sc.heartbeat_s, sc.telemetry_s, sc.noise_g = 0.4, 0.8, 0.0
    sc.battery_drain_per_min = 0.0
    catalog = sc.catalog()
    st.carts = {cid: SmartCart(cid, sc, catalog) for cid in sc.cart_ids()}
    st.catalog = catalog
    for c in st.carts.values():
        c.start()
    st.control = ControlServer(st.carts.values(), "127.0.0.1", 0).start()
    st.sim = Api(f"http://127.0.0.1:{st.control.port}")
    st.events = []
    st.ctx.hub.listeners.append(st.events.append)
    wait_until(lambda: all(c["connection_status"] == "ONLINE" for c in st.api.get("/api/carts")[1]), msg="3 xe ONLINE")
    return st


def close_stack(st):
    st.control.stop()
    for c in st.carts.values():
        c.stop()
    st.server.should_exit = True
    st.thread.join(timeout=5)
    st.broker.stop()


@pytest.fixture()
def stack(tmp_path):
    st = make_stack(tmp_path)
    yield st
    close_stack(st)


ADMIN_PW = "Correct-Horse-9"


@pytest.fixture()
def auth_stack(tmp_path):
    """Như `stack` nhưng bật đăng nhập: admin / viewer / token khách."""
    st = make_stack(tmp_path, auth_enabled=True, admin_password=ADMIN_PW, viewer_username="viewer",
                    viewer_password="View-Only-1", token_secret="test-secret-test-secret", login_max_attempts=3,
                    login_lockout_s=1.0)
    st.anon = st.api
    code, r = st.anon.post("/api/auth/login", {"username": "admin", "password": ADMIN_PW})
    assert code == 200, r
    st.admin = st.anon.with_token(r["token"])
    code, r = st.anon.post("/api/auth/login", {"username": "viewer", "password": "View-Only-1"})
    st.viewer = st.anon.with_token(r["token"])
    yield st
    close_stack(st)
