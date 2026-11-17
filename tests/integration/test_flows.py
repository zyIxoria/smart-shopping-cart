"""Luồng end-to-end qua MQTT thật: Simulator <-> Broker <-> Backend <-> REST."""
import time

from simulator import scenarios as sc
from tests.conftest import wait_until

COLA, OREO = "8934588012341", "8935001700011"


def start(stack, cart_id="CART_001"):
    code, s = stack.api.post("/api/sessions", {"cart_id": cart_id})
    assert code == 201, s
    wait_until(lambda: stack.carts[cart_id].cart_status == "IN_USE", msg="xe nhận START_SESSION")
    return s["id"]


def session(stack, sid):
    return stack.api.get(f"/api/sessions/{sid}")[1]


def alerts(stack, **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    return stack.api.get("/api/alerts" + ("?" + qs if qs else ""))[1]


def test_scan_flow_and_checkout(stack):
    sid = start(stack)
    assert stack.api.get("/api/carts/CART_001")[1]["cart_status"] == "IN_USE"
    stack.carts["CART_001"].scan(COLA)
    stack.carts["CART_001"].scan(COLA)
    stack.carts["CART_001"].scan(OREO)
    s = wait_until(lambda: (lambda x: x if x["item_count"] == 3 else None)(session(stack, sid)), msg="3 món vào giỏ")
    assert s["total_amount"] == 2 * 12000 + 15000
    assert abs(s["expected_weight"] - (2 * 355 + 137)) < 1e-6
    # cân thực tế khớp, không có cảnh báo
    wait_until(lambda: abs(session(stack, sid)["actual_weight"] - s["expected_weight"]) < 1, msg="cân khớp")
    assert alerts(stack, status="ACTIVE") == []
    # REMOVE giảm 1
    stack.carts["CART_001"].scan(COLA, "REMOVE")
    wait_until(lambda: session(stack, sid)["item_count"] == 2, msg="remove")
    code, done = stack.api.post(f"/api/sessions/{sid}/checkout")
    assert code == 200 and done["status"] == "COMPLETED" and done["total_amount"] == 12000 + 15000
    assert stack.api.get("/api/carts/CART_001")[1]["cart_status"] == "AVAILABLE"
    wait_until(lambda: stack.carts["CART_001"].cart_status == "AVAILABLE", msg="xe nhận END_SESSION")
    assert stack.carts["CART_001"].true_weight() == 0
    # không checkout lại / không thêm hàng vào phiên đã đóng
    assert stack.api.post(f"/api/sessions/{sid}/checkout")[0] == 409
    assert stack.api.post(f"/api/sessions/{sid}/items", {"barcode": COLA})[0] == 409


def test_session_preconditions(stack):
    start(stack)
    code, body = stack.api.post("/api/sessions", {"cart_id": "CART_001"})
    assert code == 409 and body["error"]["code"] == "CART_NOT_AVAILABLE"
    assert stack.api.post("/api/sessions", {"cart_id": "NOPE"})[0] == 404
    assert stack.api.post("/api/sessions", {})[0] == 422
    sid = start(stack, "CART_002")
    assert stack.api.post(f"/api/sessions/{sid}/checkout")[1]["error"]["code"] == "EMPTY_SESSION"


def test_manual_items_api(stack):
    sid = start(stack)
    code, s = stack.api.post(f"/api/sessions/{sid}/items", {"barcode": COLA, "quantity": 2})
    assert code == 201 and s["item_count"] == 2
    item_id = s["items"][0]["id"]
    assert stack.api.post(f"/api/sessions/{sid}/items", {"product_id": 99999})[0] == 404
    assert stack.api.post(f"/api/sessions/{sid}/items", {"barcode": COLA, "quantity": 0})[0] == 422
    code, s = stack.api.delete(f"/api/sessions/{sid}/items/{item_id}")
    assert code == 200 and s["item_count"] == 0


def test_unknown_barcode_rejected(stack):
    sid = start(stack)
    stack.carts["CART_001"].scan("0000000000000")
    wait_until(lambda: any(e["type"] == "SCAN_REJECTED" and e["reason"] == "UNKNOWN_BARCODE" for e in stack.events), msg="SCAN_REJECTED")
    assert session(stack, sid)["item_count"] == 0


def test_low_battery_alert_raise_and_resolve(stack):
    sc.low_battery(stack.carts["CART_002"], 15)
    wait_until(lambda: [a for a in alerts(stack, status="ACTIVE") if a["alert_type"] == "LOW_BATTERY"], msg="LOW_BATTERY")
    sc.low_battery(stack.carts["CART_002"], 15)       # telemetry thứ hai không tạo bản ghi trùng
    time.sleep(1.2)
    assert len([a for a in alerts(stack, status="ACTIVE") if a["alert_type"] == "LOW_BATTERY"]) == 1
    sc.recharge(stack.carts["CART_002"])
    wait_until(lambda: not alerts(stack, status="ACTIVE"), msg="LOW_BATTERY resolved")
    assert alerts(stack, status="RESOLVED")[0]["resolved_at"]


def test_battery_threshold_boundary(stack):
    sc.low_battery(stack.carts["CART_003"], 20)       # đúng 20% -> chưa cảnh báo (ngưỡng < 20)
    time.sleep(1.2)
    assert alerts(stack, status="ACTIVE") == []


def test_weight_mismatch_only_during_session(stack):
    # Không có phiên: lệch cân không sinh cảnh báo
    sc.weight_mismatch(stack.carts["CART_001"], 500)
    time.sleep(1.2)
    assert alerts(stack, status="ACTIVE") == []
    sc.fix_weight(stack.carts["CART_001"])
    sid = start(stack)
    stack.carts["CART_001"].scan(COLA)
    wait_until(lambda: session(stack, sid)["item_count"] == 1)
    sc.weight_mismatch(stack.carts["CART_001"], 250)
    a = wait_until(lambda: [x for x in alerts(stack, status="ACTIVE") if x["alert_type"] == "WEIGHT_MISMATCH"], msg="WEIGHT_MISMATCH")
    assert a[0]["cart_id"] == "CART_001"
    assert "lệch" in a[0]["detail"]
    sc.fix_weight(stack.carts["CART_001"])
    wait_until(lambda: not alerts(stack, status="ACTIVE"), msg="WEIGHT_MISMATCH resolved")


def test_weight_within_tolerance_no_alert(stack):
    sid = start(stack)
    stack.carts["CART_001"].scan(COLA)
    wait_until(lambda: session(stack, sid)["item_count"] == 1)
    sc.weight_mismatch(stack.carts["CART_001"], 90)      # lệch 90 g <= 100 g
    time.sleep(1.2)
    assert alerts(stack, status="ACTIVE") == []


def test_checkout_records_unresolved_alert_in_note(stack):
    sid = start(stack)
    stack.carts["CART_001"].scan(COLA)
    wait_until(lambda: session(stack, sid)["item_count"] == 1)
    sc.weight_mismatch(stack.carts["CART_001"], 300)
    wait_until(lambda: alerts(stack, status="ACTIVE"))
    done = stack.api.post(f"/api/sessions/{sid}/checkout")[1]
    assert "WEIGHT_MISMATCH" in done["note"]
    assert alerts(stack, status="ACTIVE") == []        # phiên đã đóng -> điều kiện không còn áp dụng


def test_offline_detection_and_recovery(stack):
    cart = stack.carts["CART_003"]
    sc.drop_connection(cart)
    wait_until(lambda: stack.api.get("/api/carts/CART_003")[1]["connection_status"] == "OFFLINE", timeout=6, msg="OFFLINE")
    act = wait_until(lambda: [a for a in alerts(stack, status="ACTIVE") if a["alert_type"] == "OFFLINE"], msg="OFFLINE alert")
    assert act[0]["cart_id"] == "CART_003"
    # không cho bắt đầu phiên / gửi lệnh khi OFFLINE
    assert stack.api.post("/api/sessions", {"cart_id": "CART_003"})[1]["error"]["code"] == "CART_OFFLINE"
    assert stack.api.post("/api/carts/CART_003/lock")[1]["error"]["code"] == "CART_OFFLINE"
    sc.reconnect(cart)
    wait_until(lambda: stack.api.get("/api/carts/CART_003")[1]["connection_status"] == "ONLINE", msg="ONLINE lại")
    wait_until(lambda: not [a for a in alerts(stack, status="ACTIVE") if a["alert_type"] == "OFFLINE"], msg="OFFLINE resolved")


def test_reconnect_keeps_session_and_basket(stack):
    sid = start(stack)
    cart = stack.carts["CART_001"]
    cart.scan(COLA)
    wait_until(lambda: session(stack, sid)["item_count"] == 1)
    sc.drop_connection(cart)
    wait_until(lambda: stack.api.get("/api/carts/CART_001")[1]["connection_status"] == "OFFLINE", timeout=6)
    sc.reconnect(cart)
    wait_until(lambda: stack.api.get("/api/carts/CART_001")[1]["connection_status"] == "ONLINE")
    time.sleep(1.0)
    assert cart.cart_status == "IN_USE" and cart.basket == {COLA: 1}   # reconcile idempotent, không xoá giỏ
    assert session(stack, sid)["item_count"] == 1


def test_lock_unlock_with_ack(stack):
    cart = stack.carts["CART_002"]
    code, cmd = stack.api.post("/api/carts/CART_002/lock")
    assert code == 200 and cmd["status"] == "OK" and cmd["command_type"] == "LOCK_CART"
    assert stack.api.get("/api/carts/CART_002")[1]["cart_status"] == "LOCKED" and cart.cart_status == "LOCKED"
    assert stack.api.post("/api/carts/CART_002/lock")[1]["error"]["code"] == "ALREADY_LOCKED"
    assert stack.api.post("/api/sessions", {"cart_id": "CART_002"})[1]["error"]["code"] == "CART_NOT_AVAILABLE"
    assert stack.api.get(f"/api/commands/{cmd['command_id']}")[1]["status"] == "OK"
    code, cmd = stack.api.post("/api/carts/CART_002/unlock")
    assert code == 200 and stack.api.get("/api/carts/CART_002")[1]["cart_status"] == "AVAILABLE"
    assert stack.api.post("/api/carts/CART_002/unlock")[1]["error"]["code"] == "NOT_LOCKED"


def test_locked_cart_ignores_scans_and_blocks_checkout(stack):
    sid = start(stack)
    stack.carts["CART_001"].scan(COLA)
    wait_until(lambda: session(stack, sid)["item_count"] == 1)
    assert stack.api.post("/api/carts/CART_001/lock")[0] == 200
    assert stack.carts["CART_001"].scan(OREO) == "locked"
    assert stack.api.post(f"/api/sessions/{sid}/checkout")[1]["error"]["code"] == "CART_LOCKED"
    assert stack.api.post("/api/carts/CART_001/unlock")[0] == 200
    assert stack.api.get("/api/carts/CART_001")[1]["cart_status"] == "IN_USE"   # còn phiên -> IN_USE


def test_scan_without_session_rejected(stack):
    cart = stack.carts["CART_003"]
    cart.session_id = 999          # xe tưởng đang có phiên nhưng Backend không biết
    cart.scan(COLA)
    wait_until(lambda: any(e["type"] == "SCAN_REJECTED" and e["reason"] == "NO_ACTIVE_SESSION" for e in stack.events))
    cart.session_id = None


def test_telemetry_history_and_realtime_events(stack):
    wait_until(lambda: len(stack.api.get("/api/carts/CART_001/telemetry?limit=5")[1]) >= 3, msg="telemetry")
    row = stack.api.get("/api/carts/CART_001/telemetry?limit=5")[1][-1]
    assert {"battery_percent", "actual_weight", "timestamp"} <= set(row)
    assert any(e["type"] == "CART_UPDATED" for e in stack.events)
    assert stack.api.get("/api/carts/NOPE/telemetry")[0] == 404
