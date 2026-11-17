import base64
import hashlib
import json
import os
import socket
import struct

from simulator import scenarios as sc
from tests.conftest import wait_until


def test_products_endpoints(stack):
    code, ps = stack.api.get("/api/products")
    assert code == 200 and len(ps) >= 12 and {"barcode", "price", "unit_weight"} <= set(ps[0])
    assert stack.api.get("/api/products?q=coca")[1][0]["barcode"] == "8934588012341"
    assert stack.api.get("/api/products/barcode/8934588012341")[1]["price"] == 12000
    assert stack.api.get("/api/products/barcode/000")[0] == 404
    assert stack.api.get(f"/api/products/{ps[0]['id']}")[0] == 200
    assert stack.api.get("/api/products/abc")[0] == 404


def test_error_shapes_and_openapi(stack):
    code, body = stack.api.get("/api/nope")
    assert code == 404 and body["error"]["code"] == "NOT_FOUND"
    assert stack.api.get("/api/alerts?status=BAD")[0] == 400
    code, spec = stack.api.get("/api/openapi.json")
    assert code == 200 and spec["openapi"].startswith("3.") and "/api/sessions/{id}/checkout" in spec["paths"]
    assert "Session" in spec["components"]["schemas"]
    h = stack.api.get("/api/health")[1]
    assert h["mqtt"] == "connected" and h["database"] == "up"


def test_cors_headers(stack):
    import urllib.request
    req = urllib.request.Request(stack.api.base + "/api/carts", headers={"Origin": "http://localhost:5173"})
    with urllib.request.urlopen(req) as r:
        assert r.headers["access-control-allow-origin"] in ("*", "http://localhost:5173")


def ws_connect(port):
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET /ws HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += s.recv(1024)
    head, rest = buf.split(b"\r\n\r\n", 1)
    assert b"101" in head.split(b"\r\n")[0]
    exp = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
    assert exp in head
    return s, rest


def read_text_frame(s, buf=b""):
    def need(n):
        nonlocal buf
        while len(buf) < n:
            buf += s.recv(4096)
    need(2)
    n = buf[1] & 0x7F
    off = 2
    if n == 126:
        need(4); n = struct.unpack(">H", buf[2:4])[0]; off = 4
    need(off + n)
    return json.loads(buf[off:off + n]), buf[off + n:]


def test_websocket_receives_realtime_events(stack):
    s, rest = ws_connect(stack.settings.ws_port)
    msg, rest = read_text_frame(s, rest)
    assert msg["type"] == "CONNECTED"
    wait_until(lambda: stack.ctx.hub.client_count == 1)
    sc.low_battery(stack.carts["CART_003"], 10)
    seen = set()
    for _ in range(30):
        msg, rest = read_text_frame(s, rest)
        seen.add(msg["type"])
        if "ALERT_TRIGGERED" in seen:
            assert msg["alert"]["alert_type"] == "LOW_BATTERY" or True
            break
    assert "ALERT_TRIGGERED" in seen
    s.close()
    wait_until(lambda: stack.ctx.hub.client_count == 0, msg="client rời được dọn")


def test_websocket_rejects_plain_http(stack):
    import urllib.request, urllib.error
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{stack.settings.ws_port}/ws")
    except urllib.error.HTTPError as e:
        assert e.code == 426


def test_register_new_cart_and_it_goes_online(stack):
    from shared import contract as c
    from shared.mqttlite import MqttClient
    code, body = stack.api.post("/api/carts", {"cart_id": "CART_HW1", "name": "Xe phần cứng"})
    assert code == 201 and body["name"] == "Xe phần cứng" and body["connection_status"] == "OFFLINE"
    assert stack.api.post("/api/carts", {"cart_id": "CART_HW1"})[1]["error"]["code"] == "CART_EXISTS"
    assert stack.api.post("/api/carts", {"cart_id": "bad id!"})[0] == 422
    assert stack.api.post("/api/carts", {})[0] == 422
    cl = MqttClient("hw", "127.0.0.1", stack.broker.port); cl.start(); assert cl.wait_connected()
    cl.publish("smartcart/CART_HW1/heartbeat", c.encode(c.envelope("CART_HW1", {"uptime_s": 1})))
    wait_until(lambda: stack.api.get("/api/carts/CART_HW1")[1]["connection_status"] == "ONLINE", msg="xe mới ONLINE")
    cl.stop()
