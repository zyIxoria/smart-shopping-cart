"""Phần thuần của cầu nối Wokwi: giải mã Telnet, escape, ánh xạ message hai chiều."""
import json

from shared import contract
from tools.wokwi_bridge import Bridge, TelnetDecoder, telnet_escape


def test_telnet_decoder_strips_negotiation_and_unescapes():
    d = TelnetDecoder()
    raw = b"\xff\xfd\x2c" + b"abc" + b"\xff\xfa\x2c\x01\xff\xf0" + b"\xff\xff" + b"d\n"
    assert d.feed(raw) == b"abc\xffd\n"
    # chuỗi IAC bị cắt giữa các lần recv vẫn đúng
    d2 = TelnetDecoder()
    assert d2.feed(b"x\xff") + d2.feed(b"\xfb") + d2.feed(b"\x2cy") == b"xy"


def test_telnet_escape_roundtrip():
    data = "cmd {\"a\":\"é\"}\n".encode() + b"\xff"
    assert TelnetDecoder().feed(telnet_escape(data)) == data


class FakeMqtt:
    def __init__(self):
        self.sent = []

    def publish(self, topic, payload):
        self.sent.append((topic, json.loads(payload)))
        return True


def _bridge():
    sent_serial = []
    m = FakeMqtt()
    return Bridge("WK_X", "CART_DEMO", sent_serial.append, m), m, sent_serial


def test_firmware_line_is_rewritten_and_published():
    b, m, _ = _bridge()
    line = ('[local] smartcart/CART_DEMO/scan {"message_id":"0000","cart_id":"CART_DEMO","schema_version":1,'
            '"timestamp":"1970-01-01T00:00:00Z","data":{"scan_id":"s1","barcode":"8934588012341","action":"ADD"}}\r')
    assert b.on_serial_line(line)
    topic, env = m.sent[0]
    assert topic == contract.topic("WK_X", "scan")
    assert env["cart_id"] == "WK_X" and env["message_id"] != "0000" and env["timestamp"].startswith("20")
    assert env["data"]["barcode"] == "8934588012341"
    # hai lần liên tiếp phải có message_id khác nhau (Backend loại message trùng id)
    b.on_serial_line(line)
    assert m.sent[0][1]["message_id"] != m.sent[1][1]["message_id"]
    contract.decode_and_validate("scan", "WK_X", contract.encode(env))


def test_ignores_normal_logs_and_unknown_topics():
    b, m, _ = _bridge()
    assert not b.on_serial_line("[scan] ADD 8934588012341")
    assert not b.on_serial_line("[local] smartcart/CART_DEMO/command {}")
    assert not b.on_serial_line("[local] smartcart/CART_DEMO/scan {broken")
    assert m.sent == []


def test_backend_command_forwarded_with_firmware_cart_id():
    b, _, serial = _bridge()
    env = contract.envelope("WK_X", {"command_id": "c1", "command_type": "LOCK_CART", "parameters": {}})
    assert b.on_mqtt_command(contract.encode(env))
    line = TelnetDecoder().feed(serial[0]).decode()
    assert line.startswith("cmd {") and line.endswith("\n")
    sent = json.loads(line[4:])
    assert sent["cart_id"] == "CART_DEMO" and sent["data"]["command_id"] == "c1"
    assert not b.on_mqtt_command(contract.encode(contract.envelope("OTHER", {"command_id": "x"})))
    assert not b.on_mqtt_command(b"not json")


def test_bridge_with_key_signs_uplink_and_requires_signed_commands():
    from shared import security
    key = security.derive_cart_key("master", "WK_X")
    serial, m = [], FakeMqtt()
    b = Bridge("WK_X", "CART_DEMO", serial.append, m, key=key)
    line = ('[local] smartcart/CART_DEMO/scan {"message_id":"0000","cart_id":"CART_DEMO","schema_version":1,'
            '"timestamp":"1970-01-01T00:00:00Z","data":{"scan_id":"s1","barcode":"8934588012341","action":"ADD"}}\r')
    assert b.on_serial_line(line)
    # message_id/timestamp/cart_id bị viết lại rồi MỚI ký -> chữ ký phải đúng với giá trị cuối cùng
    sent = json.dumps(m.sent[0][1], ensure_ascii=False, separators=(",", ":"))
    assert m.sent[0][1]["sig"] and len(m.sent[0][1]["sig"]) == 64
    contract.verify_payload("scan", key, sent.encode())

    cmd = {"command_id": "c1", "command_type": "LOCK_CART", "parameters": {}}
    assert not b.on_mqtt_command(contract.encode(contract.envelope("WK_X", cmd)))                     # không ký
    assert not b.on_mqtt_command(contract.encode_signed(contract.envelope("WK_X", cmd), b"z" * 32, "command"))
    old = contract.envelope("WK_X", cmd, timestamp="2020-01-01T00:00:00Z")
    assert not b.on_mqtt_command(contract.encode_signed(old, key, "command"))                          # cũ
    assert serial == [] and b.stats["rejected"] == 3
    assert b.on_mqtt_command(contract.encode_signed(contract.envelope("WK_X", cmd), key, "command"))
    assert len(serial) == 1
