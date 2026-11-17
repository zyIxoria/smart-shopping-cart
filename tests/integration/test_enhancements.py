"""Kiểm thử tích hợp cho các tính năng nâng cấp:
1. Hàng đợi ngoại tuyến (Offline Queue) của Simulator và phục hồi dữ liệu khi kết nối lại.
2. Lưu trữ lệnh điều khiển xuống CSDL (Command Persistence, Timeout, Restart & History API).
3. WebSocket gom cổng trên FastAPI (/ws trên cổng HTTP): Auth, Ping/Pong, Reconnect & Event.
4. Ba xe hoạt động độc lập & hai xe mua hàng đồng thời không lẫn giỏ.
5. Bảo vệ Simulator Control API (:8090) bằng SIM_CONTROL_TOKEN.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request

import pytest
import uvicorn
import websockets

from backend.api.app import create_app
from simulator.control import ControlServer
from simulator import scenarios as sc
from tests.conftest import Api, free_port, wait_until


def test_offline_queue_drain_on_reconnect(stack):
    """Khi xe mất kết nối, các lượt quét được đưa vào hàng đợi; khi có mạng lại thì gửi tự động lên Backend."""
    cart_id = "CART_001"
    cart = stack.carts[cart_id]

    code, sess = stack.api.post("/api/sessions", {"cart_id": cart_id})
    assert code == 201
    sess_id = sess["id"]
    wait_until(lambda: cart.cart_status == "IN_USE", msg="xe nhận START_SESSION")

    cart.go_offline()
    wait_until(lambda: not cart.mqtt.connected, msg="xe đã ngắt MQTT")

    b1 = "8934673100019"  # Sữa tươi 1L
    b2 = "8934563138165"  # Mì Hảo Hảo tôm chua cay
    assert cart.scan(b1, "ADD") == "queued"
    assert cart.scan(b2, "ADD") == "queued"
    assert cart.offline_queue_len == 2

    _, s_before = stack.api.get(f"/api/sessions/{sess_id}")
    assert len(s_before["items"]) == 0

    cart.go_online()
    wait_until(lambda: cart.mqtt.connected, msg="xe kết nối lại MQTT")
    wait_until(lambda: cart.offline_queue_len == 0, timeout=10.0, interval=0.1, msg="hàng đợi ngoại tuyến xả sạch")
    wait_until(lambda: len(stack.api.get(f"/api/sessions/{sess_id}")[1]["items"]) == 2, timeout=8.0, msg="Backend ghi nhận đủ 2 món")

    _, s_after = stack.api.get(f"/api/sessions/{sess_id}")
    barcodes = [it["barcode"] for it in s_after["items"]]
    assert b1 in barcodes and b2 in barcodes
    assert s_after["total_amount"] > 0
    assert s_after["expected_weight"] > 0


def test_command_persistence_and_listing(auth_stack):
    """Lệnh gửi xuống xe được lưu vào bảng cart_commands, tra cứu được sau khi khởi tạo lại app và qua /api/commands."""
    cart_id = "CART_001"

    code, res = auth_stack.admin.post(f"/api/carts/{cart_id}/lock")
    assert code == 200
    cid = res["command_id"]
    assert res["status"] == "OK"

    code, cmd_list = auth_stack.admin.get(f"/api/commands?cart_id={cart_id}")
    assert code == 200
    matching = [c for c in cmd_list if c["command_id"] == cid]
    assert len(matching) == 1
    assert matching[0]["command_type"] == "LOCK_CART"
    assert matching[0]["status"] == "OK"

    # Mô phỏng Backend restart thực sự: tạo app instance thứ hai trỏ cùng db_path & token_secret
    import copy
    s2 = copy.copy(auth_stack.settings)
    s2.ws_port = s2.port
    s2.mqtt_enabled = False
    app2 = create_app(s2)
    from starlette.testclient import TestClient
    with TestClient(app2) as client:
        r = client.get(f"/api/commands/{cid}", headers={"Authorization": f"Bearer {auth_stack.admin.token}"})
        assert r.status_code == 200
        body = r.json()
        assert body["command_id"] == cid
        assert body["status"] == "OK"
        assert body["command_type"] == "LOCK_CART"


def test_command_timeout_persisted_when_no_ack(stack):
    """Khi xe chưa nhận lệnh và không phản hồi ACK trong timeout, lệnh chuyển TIMEOUT (HTTP 504) và lưu DB."""
    cart = stack.carts["CART_002"]
    # Ngắt socket MQTT của xe ngay lập tức trong khi Backend vẫn coi xe đang ONLINE (trước timeout 1.5s)
    cart.mqtt.stop(clean=False)
    code, body = stack.api.post("/api/carts/CART_002/lock")
    assert code == 504
    cid = body["command"]["command_id"]
    assert body["command"]["status"] == "TIMEOUT"

    code2, cmd = stack.api.get(f"/api/commands/{cid}")
    assert code2 == 200
    assert cmd["status"] == "TIMEOUT"


def test_fastapi_unified_websocket_ping_auth_events_and_reconnect(auth_stack):
    """WebSocket trên cổng FastAPI (/ws): handshake, PING/PONG, AUTH token, nhận ALERT_TRIGGERED và reconnect."""
    api_port = auth_stack.settings.port
    ws_url = f"ws://127.0.0.1:{api_port}/ws"

    async def run_ws():
        # Lần 1: Kết nối -> PING/PONG -> AUTH -> nhận ALERT_TRIGGERED
        async with websockets.connect(ws_url) as ws:
            msg1 = json.loads(await asyncio.wait_for(ws.recv(), 3.0))
            assert msg1["type"] == "CONNECTED"

            await ws.send(json.dumps({"type": "PING"}))
            pong = json.loads(await asyncio.wait_for(ws.recv(), 3.0))
            assert pong["type"] == "PONG"

            await ws.send(json.dumps({"type": "AUTH", "token": auth_stack.admin.token}))
            msg2 = json.loads(await asyncio.wait_for(ws.recv(), 3.0))
            assert msg2["type"] == "AUTHED" and msg2["role"] == "admin"

            # Gây pin thấp trên CART_003 để kiểm tra sự kiện đi qua unified /ws
            sc.low_battery(auth_stack.carts["CART_003"], 12)
            got_alert = False
            for _ in range(15):
                ev = json.loads(await asyncio.wait_for(ws.recv(), 4.0))
                if ev.get("type") == "ALERT_TRIGGERED" and ev.get("cart_id") == "CART_003":
                    got_alert = True
                    break
            assert got_alert

        # Lần 2: Reconnect lại /ws
        async with websockets.connect(ws_url) as ws2:
            msg_re = json.loads(await asyncio.wait_for(ws2.recv(), 3.0))
            assert msg_re["type"] == "CONNECTED"

    asyncio.run(run_ws())


def test_three_carts_independent_and_two_concurrent_shopping(stack):
    """Ba xe hoạt động độc lập, hai xe mua hàng đồng thời không lẫn giỏ hàng hay session."""
    c1, c2 = stack.carts["CART_001"], stack.carts["CART_002"]

    code1, s1 = stack.api.post("/api/sessions", {"cart_id": "CART_001"})
    code2, s2 = stack.api.post("/api/sessions", {"cart_id": "CART_002"})
    assert code1 == 201 and code2 == 201
    sid1, sid2 = s1["id"], s2["id"]
    wait_until(lambda: c1.cart_status == "IN_USE" and c2.cart_status == "IN_USE", msg="2 xe vào phiên")

    # Quét đồng thời 2 sản phẩm khác nhau trên 2 xe
    milk = "8934673100019"   # Sữa Vinamilk 1L
    cola = "8934588012341"   # Coca-Cola 330ml
    oreo = "8935001700011"   # Oreo 137g
    c1.scan(milk, "ADD")
    c2.scan(cola, "ADD")
    c2.scan(oreo, "ADD")

    wait_until(lambda: len(stack.api.get(f"/api/sessions/{sid1}")[1]["items"]) == 1, msg="CART_001 nhận 1 món")
    wait_until(lambda: len(stack.api.get(f"/api/sessions/{sid2}")[1]["items"]) == 2, msg="CART_002 nhận 2 món")

    _, view1 = stack.api.get(f"/api/sessions/{sid1}")
    _, view2 = stack.api.get(f"/api/sessions/{sid2}")
    _, view3 = stack.api.get("/api/carts/CART_003")

    assert [i["barcode"] for i in view1["items"]] == [milk]
    assert set(i["barcode"] for i in view2["items"]) == {cola, oreo}
    assert view3["cart_status"] == "AVAILABLE" and view3["session"] is None


def test_simulator_control_api_auth_protection(stack):
    """Khi cấu hình SIM_CONTROL_TOKEN, truy cập Control API (:8090) không có token phải trả 401."""
    srv = ControlServer(stack.carts.values(), "127.0.0.1", 0, token="secret-sim-token").start()
    try:
        anon = Api(f"http://127.0.0.1:{srv.port}")
        authed = Api(f"http://127.0.0.1:{srv.port}", token="secret-sim-token")
        wrong = Api(f"http://127.0.0.1:{srv.port}", token="wrong-token")

        assert anon.get("/sim/carts")[0] == 401
        assert anon.post("/sim/carts/CART_001/battery", {"percent": 15})[0] == 401
        assert wrong.get("/sim/carts")[0] == 401

        code, data = authed.get("/sim/carts")
        assert code == 200 and len(data) == 3

        code2, snap = authed.post("/sim/carts/CART_001/battery", {"percent": 42})
        assert code2 == 200 and snap["cart"]["battery_percent"] == 42.0
    finally:
        srv.stop()
