"""Backend phải sống sót với message rác/trùng/cũ."""
import time

from shared import contract as c
from shared.mqttlite import MqttClient
from tests.conftest import wait_until


def raw_client(stack):
    cl = MqttClient("raw", "127.0.0.1", stack.broker.port)
    cl.start()
    assert cl.wait_connected()
    return cl


def test_garbage_duplicate_stale_and_foreign(stack):
    cl = raw_client(stack)
    ctx = stack.ctx
    base = dict(ctx.stats)
    cl.publish("smartcart/CART_001/telemetry", b"not json")
    cl.publish("smartcart/CART_001/telemetry", c.encode(c.envelope("CART_001", {"actual_weight": -5, "battery_percent": 50})))
    cl.publish("smartcart/CART_001/telemetry", c.encode(c.envelope("CART_002", {"actual_weight": 5, "battery_percent": 50})))  # cart_id lệch topic
    wait_until(lambda: ctx.stats["mqtt_invalid"] >= base["mqtt_invalid"] + 3, msg="3 message sai bị loại")
    # trùng message_id
    msg = c.encode(c.envelope("CART_001", {"actual_weight": 7, "battery_percent": 55}, message_id="dup-1"))
    cl.publish("smartcart/CART_001/telemetry", msg)
    cl.publish("smartcart/CART_001/telemetry", msg)
    wait_until(lambda: ctx.stats["mqtt_duplicate"] >= base["mqtt_duplicate"] + 1, msg="message trùng")
    # timestamp quá cũ
    old = c.encode(c.envelope("CART_001", {"actual_weight": 1, "battery_percent": 1}, timestamp="2020-01-01T00:00:00Z"))
    cl.publish("smartcart/CART_001/telemetry", old)
    wait_until(lambda: ctx.stats["mqtt_stale"] >= base["mqtt_stale"] + 1, msg="message cũ")
    # xe lạ không đăng ký bị bỏ qua, backend vẫn sống
    cl.publish("smartcart/GHOST/heartbeat", c.encode(c.envelope("GHOST", {"uptime_s": 1})))
    time.sleep(0.5)
    assert stack.api.get("/api/health")[1]["status"] == "ok"
    assert not [x for x in stack.api.get("/api/carts")[1] if x["cart_id"] == "GHOST"]
    assert stack.api.get("/api/alerts?status=ACTIVE")[1] == []        # telemetry rác không kích hoạt cảnh báo pin 1%
    cl.stop()


def test_duplicate_scan_id_counted_once(stack):
    sid = stack.api.post("/api/sessions", {"cart_id": "CART_001"})[1]["id"]
    wait_until(lambda: stack.carts["CART_001"].cart_status == "IN_USE")
    cl = raw_client(stack)
    for _ in range(2):   # cùng scan_id, khác message_id
        cl.publish("smartcart/CART_001/scan", c.encode(c.envelope("CART_001", {"scan_id": "S1", "barcode": "8934588012341"})))
    wait_until(lambda: stack.api.get(f"/api/sessions/{sid}")[1]["item_count"] >= 1)
    time.sleep(0.5)
    assert stack.api.get(f"/api/sessions/{sid}")[1]["item_count"] == 1
    cl.stop()
