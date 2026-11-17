"""API điều khiển Simulator (phục vụ trang /simulator) tác động thật lên hệ thống."""
import urllib.request

from tests.conftest import wait_until

COLA = "8934588012341"


def test_snapshot_catalog_and_cors(stack):
    code, carts = stack.sim.get("/sim/carts")
    assert code == 200 and [c["cart_id"] for c in carts] == ["CART_001", "CART_002", "CART_003"]
    assert {"connected", "battery_percent", "true_weight", "basket", "log", "sent"} <= set(carts[0])
    code, cat = stack.sim.get("/sim/catalog")
    assert code == 200 and len(cat) >= 12 and cat[0]["barcode"] and cat[0]["unit_weight"] > 0
    req = urllib.request.Request(stack.sim.base + "/sim/carts", headers={"Origin": "http://localhost:8000"})
    with urllib.request.urlopen(req) as r:
        assert r.headers["access-control-allow-origin"] == "*"


def test_scan_via_control_reaches_backend(stack):
    sid = stack.api.post("/api/sessions", {"cart_id": "CART_001"})[1]["id"]
    wait_until(lambda: stack.carts["CART_001"].cart_status == "IN_USE")
    code, body = stack.sim.post("/sim/carts/CART_001/scan", {"barcode": COLA, "action": "ADD"})
    assert code == 200 and body["result"] == "sent" and body["cart"]["basket"][0]["quantity"] == 1
    wait_until(lambda: stack.api.get(f"/api/sessions/{sid}")[1]["item_count"] == 1)
    stack.sim.post("/sim/carts/CART_001/scan", {"barcode": COLA, "action": "REMOVE"})
    wait_until(lambda: stack.api.get(f"/api/sessions/{sid}")[1]["item_count"] == 0)


def test_battery_weight_and_connection_controls(stack):
    assert stack.sim.post("/sim/carts/CART_002/battery", {"percent": 10})[0] == 200
    wait_until(lambda: [a for a in stack.api.get("/api/alerts?status=ACTIVE")[1] if a["alert_type"] == "LOW_BATTERY"])
    stack.sim.post("/sim/carts/CART_002/battery", {"percent": 90})
    wait_until(lambda: not stack.api.get("/api/alerts?status=ACTIVE")[1])
    code, body = stack.sim.post("/sim/carts/CART_003/connection", {"online": False})
    assert code == 200 and body["cart"]["connected"] is False
    wait_until(lambda: stack.api.get("/api/carts/CART_003")[1]["connection_status"] == "OFFLINE", timeout=6)
    assert stack.sim.post("/sim/carts/CART_003/connection", {"online": True})[0] == 200
    wait_until(lambda: stack.api.get("/api/carts/CART_003")[1]["connection_status"] == "ONLINE")
    code, body = stack.sim.post("/sim/carts/CART_001/weight_offset", {"grams": 250})
    assert body["cart"]["true_weight"] == 250


def test_control_validation(stack):
    assert stack.sim.post("/sim/carts/NOPE/scan", {"barcode": COLA})[0] == 404
    assert stack.sim.post("/sim/carts/CART_001/scan", {})[0] == 400
    assert stack.sim.post("/sim/carts/CART_001/scan", {"barcode": "1", "action": "X"})[0] == 400
    assert stack.sim.post("/sim/carts/CART_001/battery", {"percent": 101})[0] == 400
    assert stack.sim.post("/sim/carts/CART_001/battery", {"percent": "abc"})[0] == 400
    assert stack.sim.post("/sim/carts/CART_001/battery", {})[0] == 400
    assert stack.sim.post("/sim/carts/CART_001/bogus", {})[0] == 404
    assert stack.sim.get("/sim/nothing")[0] == 404
