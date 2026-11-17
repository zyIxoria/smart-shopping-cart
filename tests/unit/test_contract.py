import json

import pytest

from shared import contract as c


def env(kind_data, **over):
    e = c.envelope("CART_001", kind_data)
    e.update(over)
    return c.encode(e)


def test_topics_roundtrip():
    assert c.topic("CART_001", "scan") == "smartcart/CART_001/scan"
    assert c.parse_topic("smartcart/CART_001/ack") == ("CART_001", "ack")
    for bad in ("smartcart/CART_001", "x/CART_001/scan", "smartcart/CART_001/foo", "smartcart/a b/scan", "smartcart/+/scan"):
        assert c.parse_topic(bad) is None


def test_valid_messages():
    out = c.decode_and_validate("scan", "CART_001", env({"barcode": "123"}))
    assert out["data"]["action"] == "ADD"      # mặc định ADD
    c.decode_and_validate("telemetry", "CART_001", env({"actual_weight": 10, "battery_percent": 50, "cart_status": "IN_USE"}))
    c.decode_and_validate("heartbeat", "CART_001", env({"uptime_s": 3}))
    c.decode_and_validate("event", "CART_001", env({"event_type": "X"}))
    c.decode_and_validate("ack", "CART_001", env({"command_id": "a", "result": "OK"}))
    c.decode_and_validate("command", "CART_001", env({"command_id": "a", "command_type": "LOCK_CART", "parameters": {}}))


@pytest.mark.parametrize("kind,data", [
    ("scan", {}), ("scan", {"barcode": ""}), ("scan", {"barcode": "1", "action": "DELETE"}),
    ("telemetry", {"actual_weight": -1, "battery_percent": 50}),
    ("telemetry", {"actual_weight": 1, "battery_percent": 101}),
    ("telemetry", {"actual_weight": "1", "battery_percent": 5}),
    ("telemetry", {"actual_weight": True, "battery_percent": 5}),
    ("telemetry", {"actual_weight": 1, "battery_percent": 5, "cart_status": "BROKEN"}),
    ("ack", {"command_id": "a", "result": "MAYBE"}),
    ("command", {"command_id": "a", "command_type": "SELF_DESTRUCT"}),
])
def test_invalid_data(kind, data):
    with pytest.raises(c.ContractError):
        c.decode_and_validate(kind, "CART_001", env(data))


def test_invalid_envelope():
    good = {"barcode": "1"}
    for over in ({"schema_version": 2}, {"message_id": ""}, {"cart_id": "CART_002"}, {"timestamp": "hôm qua"}, {"data": []}):
        with pytest.raises(c.ContractError):
            c.decode_and_validate("scan", "CART_001", env(good, **over))
    for raw in (b"not json", b"\xff\xfe", b"[]", b"123"):
        with pytest.raises(c.ContractError):
            c.decode_and_validate("scan", "CART_001", raw)


def test_timestamp_parse_variants():
    assert c.parse_ts("2026-11-07T10:30:00Z").tzinfo is not None
    assert c.parse_ts("2026-11-07T10:30:00+07:00").hour == 10
    assert c.parse_ts("2026-11-07T10:30:00").tzinfo is not None   # thiếu timezone -> coi là UTC
    assert c.iso().endswith("Z") and json.loads(c.encode(c.envelope("A", {"x": "ế"})))["data"]["x"] == "ế"


def test_topic_root_is_configurable_via_env():
    """MQTT_TOPIC_ROOT cho phép dùng broker công cộng mà không lẫn topic với người khác."""
    import os
    import subprocess
    import sys

    def run(root):
        env = dict(os.environ, PYTHONPATH=os.getcwd())
        if root is None:
            env.pop("MQTT_TOPIC_ROOT", None)
        else:
            env["MQTT_TOPIC_ROOT"] = root
        return subprocess.run(
            [sys.executable, "-c", "from shared import contract as c; print(c.topic('CART_9','scan'), c.parse_topic('abc/CART_9/scan'), c.parse_topic('smartcart/CART_9/scan'))"],
            env=env, capture_output=True, text=True)

    r = run(None)
    assert r.stdout.split()[0] == "smartcart/CART_9/scan"
    r = run("abc")
    assert r.stdout.split()[0] == "abc/CART_9/scan"
    assert "('CART_9', 'scan') None" in r.stdout      # topic gốc cũ bị bỏ qua khi đã đổi gốc
    assert run("bad root!").returncode != 0           # ký tự không hợp lệ bị từ chối
