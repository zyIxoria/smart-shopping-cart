"""Đầu-cuối: "Wokwi giả" (TCP + Telnet, dùng đúng logic firmware qua cartcore) <-> cầu nối <-> broker <-> Backend thật."""
import json
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path

import pytest

from shared import contract
from shared.mqttlite import MqttClient
from tests.conftest import wait_until
from tools.wokwi_bridge import Bridge, SerialLink, TelnetDecoder, register_cart

FW = Path(__file__).resolve().parents[2] / "firmware"
pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="cần g++ để biên dịch cartcore")


@pytest.fixture(scope="module")
def ptool(tmp_path_factory):
    out = tmp_path_factory.mktemp("wk") / "protocol_tool"
    subprocess.run(["g++", "-std=c++11", f"-I{FW/'lib/cartcore'}", str(FW / "lib/cartcore/cartcore.cpp"), str(FW / "lib/cartcore/cartsec.cpp"),
                    str(FW / "tools/protocol_tool.cpp"), "-o", str(out)], check=True, capture_output=True)
    return str(out)


class FakeWokwi:
    """Giả lập cổng RFC2217 của Wokwi: gửi heartbeat/telemetry như firmware, thực hiện lệnh `cmd {json}` bằng cartcore."""

    def __init__(self, ptool):
        self.ptool = ptool
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.port = self.srv.getsockname()[1]
        self.stop = threading.Event()
        self.cmds = []
        build = subprocess.run([ptool, "build"], capture_output=True, text=True, check=True).stdout.splitlines()
        self.lines = {}
        for ln in build:
            kind, payload = ln.split("\t", 1)
            self.lines.setdefault(kind, payload)
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        conn, _ = self.srv.accept()
        conn.settimeout(0.2)
        conn.sendall(b"\xff\xfd\x2c\xff\xfb\x2c")                      # đàm phán Telnet mà bridge phải bỏ qua
        dec, buf, last = TelnetDecoder(), b"", 0.0
        while not self.stop.is_set():
            if time.time() - last > 0.4:
                for kind in ("heartbeat", "telemetry"):
                    conn.sendall(f"[local] smartcart/CART_DEMO/{kind} {self.lines[kind]}\r\n".encode())
                last = time.time()
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                return
            buf += dec.feed(chunk)
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode().strip()
                if line.startswith("cmd {"):
                    self.cmds.append(json.loads(line[4:]))
                    out = subprocess.run([self.ptool, "command", "CART_DEMO"], input=line[4:] + "\n",
                                         capture_output=True, text=True).stdout.strip().split("\t")
                    conn.sendall(f"[local] smartcart/CART_DEMO/ack {out[4]}\r\n".encode())

    def close(self):
        self.stop.set()
        self.srv.close()


def test_bridge_end_to_end(stack, ptool):
    cart = "WK_BR1"
    assert "đã đăng ký" in register_cart(stack.api.base, cart)
    fake = FakeWokwi(ptool)
    mqtt = MqttClient("bridge-test", "127.0.0.1", stack.broker.port)
    link = SerialLink("127.0.0.1", fake.port, on_line=lambda ln: bridge.on_serial_line(ln))
    bridge = Bridge(cart, "CART_DEMO", link.send, mqtt)
    mqtt.on_message = lambda t, p: bridge.on_mqtt_command(p) if t.endswith("/command") else None
    mqtt.subscribe(contract.topic(cart, "command"))
    mqtt.start()
    link.start()
    try:
        wait_until(lambda: stack.api.get(f"/api/carts/{cart}")[1]["connection_status"] == "ONLINE", msg="xe qua cầu nối ONLINE")
        info = stack.api.get(f"/api/carts/{cart}")[1]
        assert info["battery_percent"] == 76.0   # từ telemetry do firmware dựng
        code, cmd = stack.api.post(f"/api/carts/{cart}/lock")
        assert code == 200 and cmd["status"] == "OK", (code, cmd)
        assert any(c["data"]["command_type"] == "LOCK_CART" and c["cart_id"] == "CART_DEMO" for c in fake.cmds)
        wait_until(lambda: stack.api.get(f"/api/carts/{cart}")[1]["cart_status"] == "LOCKED", msg="xe LOCKED")
        assert bridge.stats["up"] > 0 and bridge.stats["down"] > 0
    finally:
        link.stop()
        mqtt.stop()
        fake.close()
