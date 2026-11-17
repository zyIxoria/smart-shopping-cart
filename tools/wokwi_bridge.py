"""Cầu nối Serial <-> MQTT cho firmware ESP32 chạy trong Wokwi (cách 3).

    Wokwi (ESP32)  --Serial qua TCP/RFC2217-->  wokwi_bridge  --MQTT-->  broker  <-->  Backend

* Wokwi mở cổng Serial của mô phỏng ra TCP khi `wokwi.toml` có `rfc2217ServerPort = 4000`.
* Firmware build bằng env `esp32dev_sim_bridge` in mọi message ra Serial dưới dạng
      [local] smartcart/CART_DEMO/telemetry {"message_id":...}
  Cầu nối đọc các dòng đó, đặt lại `message_id` (mới), `timestamp` (giờ thật) và `cart_id` rồi publish lên MQTT
  (giờ trong mô phỏng không phải giờ thật và message_id của firmware cố định nên Backend sẽ loại nếu không sửa).
* Lệnh Backend gửi xuống (LOCK_CART, START_SESSION...) được cầu nối chuyển vào Serial dạng `cmd {json}`;
  ACK do firmware in ra lại được cầu nối đẩy về Backend.

Chạy:  python -m tools.wokwi_bridge --cart-id WK_BRIDGE
Cần Backend + broker đang chạy (vd. `python -m tools.dev_broker` và `python -m backend.main`), và xe phải được đăng ký
(mặc định cầu nối tự gọi POST /api/carts, tắt bằng --no-register).

Không dùng thư viện ngoài: giao thức RFC2217 chỉ dùng như socket thô (Telnet) – bỏ các chuỗi IAC khi nhận,
nhân đôi byte 0xFF khi gửi (theo hướng dẫn của Wokwi).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request

from shared import contract
from shared import security
from shared.mqttlite import MqttClient, options_from_env

log = logging.getLogger("wokwi_bridge")

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240
LOCAL_LINE = re.compile(r"^\[local\]\s+(\S+)\s+(\{.*\})\s*$")
FROM_FIRMWARE = ("scan", "event", "telemetry", "heartbeat", "ack")


# --------------------------------------------------------------------------- Telnet thô
class TelnetDecoder:
    """Bỏ chuỗi điều khiển Telnet (IAC ...) khỏi luồng byte, giữ lại dữ liệu; `IAC IAC` -> 0xFF."""

    def __init__(self) -> None:
        self._state = "data"      # data | iac | opt | sb | sb_iac
        self._carry = b""

    def feed(self, chunk: bytes) -> bytes:
        out = bytearray()
        for b in chunk:
            st = self._state
            if st == "data":
                if b == IAC:
                    self._state = "iac"
                else:
                    out.append(b)
            elif st == "iac":
                if b == IAC:
                    out.append(IAC)
                    self._state = "data"
                elif b in (DO, DONT, WILL, WONT):
                    self._state = "opt"
                elif b == SB:
                    self._state = "sb"
                else:                                   # lệnh 2 byte khác (NOP, GA...)
                    self._state = "data"
            elif st == "opt":
                self._state = "data"                    # byte tuỳ chọn: bỏ
            elif st == "sb":
                if b == IAC:
                    self._state = "sb_iac"
            elif st == "sb_iac":
                self._state = "data" if b == SE else "sb"
        return bytes(out)


def telnet_escape(data: bytes) -> bytes:
    return data.replace(b"\xff", b"\xff\xff")


# --------------------------------------------------------------------------- Logic cầu nối (không phụ thuộc socket)
class Bridge:
    """Chuyển đổi hai chiều. `send_serial(bytes)` và `mqtt.publish(topic, payload)` được tiêm vào để dễ kiểm thử."""

    def __init__(self, cart_id: str, firmware_cart_id: str, send_serial, mqtt, key: bytes | None = None,
                 max_skew_s: float = 300) -> None:
        self.key = key                  # khoá riêng của xe (DEVICE_MASTER_KEY): có => cầu nối ký lên và chỉ nhận lệnh đã ký
        self.max_skew_s = max_skew_s
        self.cart_id = cart_id
        self.firmware_cart_id = firmware_cart_id
        self.send_serial = send_serial
        self.mqtt = mqtt
        self.stats = {"up": 0, "down": 0, "ignored": 0, "rejected": 0}

    # firmware -> MQTT ------------------------------------------------------
    def on_serial_line(self, line: str) -> bool:
        m = LOCAL_LINE.match(line.strip())
        if not m:
            return False                                # dòng log thường
        topic, payload = m.group(1), m.group(2)
        kind = topic.rsplit("/", 1)[-1]
        if kind not in FROM_FIRMWARE:
            self.stats["ignored"] += 1
            return False
        try:
            env = json.loads(payload)
        except json.JSONDecodeError:
            log.warning("bỏ qua dòng JSON hỏng: %.80s", payload)
            self.stats["ignored"] += 1
            return False
        env["message_id"] = contract.new_id()
        env["timestamp"] = contract.iso()
        env["cart_id"] = self.cart_id
        payload_out = contract.encode_signed(env, self.key, kind) if self.key else contract.encode(env)
        ok = self.mqtt.publish(contract.topic(self.cart_id, kind), payload_out)
        if ok:
            self.stats["up"] += 1
            log.info("↑ %s %s", kind, _summary(kind, env.get("data", {})))
        return ok

    # MQTT -> firmware ------------------------------------------------------
    def on_mqtt_command(self, payload: bytes) -> bool:
        if self.key:    # cầu nối là ranh giới tin cậy: firmware trong Wokwi không có khoá, nên kiểm tra thay nó
            try:
                contract.verify_payload("command", self.key, payload)
                contract.check_freshness(json.loads(payload.decode("utf-8")), self.max_skew_s)
            except contract.ContractError as e:
                self.stats["rejected"] += 1
                log.warning("bỏ lệnh: %s", e)
                return False
        try:
            env = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False
        if not isinstance(env, dict) or env.get("cart_id") != self.cart_id:
            return False
        env["cart_id"] = self.firmware_cart_id           # firmware chỉ nhận lệnh đúng cart_id của nó
        line = "cmd " + json.dumps(env, ensure_ascii=False, separators=(",", ":")) + "\n"
        self.send_serial(telnet_escape(line.encode("utf-8")))
        self.stats["down"] += 1
        data = env.get("data", {})
        log.info("↓ %s id=%s", data.get("command_type"), data.get("command_id"))
        return True


def _summary(kind: str, data: dict) -> str:
    if kind == "scan":
        return f"{data.get('action')} {data.get('barcode')}"
    if kind == "telemetry":
        return f"cân={data.get('actual_weight')}g pin={data.get('battery_percent')}% {data.get('cart_status')}"
    if kind == "ack":
        return f"{data.get('command_id')} {data.get('result')}"
    if kind == "event":
        return str(data.get("event_type"))
    return ""


# --------------------------------------------------------------------------- Kết nối thật
class SerialLink:
    """Kết nối TCP tới cổng Serial Wokwi, tự nối lại, tách dòng và gọi `on_line`."""

    def __init__(self, host: str, port: int, on_line) -> None:
        self.host, self.port, self.on_line = host, port, on_line
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.connected = threading.Event()

    def send(self, data: bytes) -> bool:
        with self._lock:
            s = self._sock
        if s is None:
            return False
        try:
            s.sendall(data)
            return True
        except OSError:
            return False

    def start(self) -> None:
        threading.Thread(target=self._run, name="serial-link", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            s = self._sock
        if s:
            try:
                s.close()
            except OSError:
                pass

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                s = socket.create_connection((self.host, self.port), timeout=3)
            except OSError:
                if self._stop.wait(1.5):
                    return
                continue
            s.settimeout(1.0)
            with self._lock:
                self._sock = s
            self.connected.set()
            log.info("đã nối Serial Wokwi %s:%s", self.host, self.port)
            dec, buf = TelnetDecoder(), b""
            try:
                while not self._stop.is_set():
                    try:
                        chunk = s.recv(4096)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    buf += dec.feed(chunk)
                    while b"\n" in buf:
                        raw, buf = buf.split(b"\n", 1)
                        self.on_line(raw.decode("utf-8", "replace").rstrip("\r"))
                    if len(buf) > 8192:                  # không có xuống dòng: bỏ để khỏi phình bộ nhớ
                        buf = b""
            except OSError:
                pass
            finally:
                self.connected.clear()
                with self._lock:
                    self._sock = None
                try:
                    s.close()
                except OSError:
                    pass
            log.warning("mất kết nối Serial Wokwi – thử lại (cần đang chạy mô phỏng và có rfc2217ServerPort trong wokwi.toml)")


def admin_token(api: str, user: str, password: str) -> str | None:
    req = urllib.request.Request(f"{api.rstrip('/')}/api/auth/login", method="POST",
                                 data=json.dumps({"username": user, "password": password}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())["token"]
    except (OSError, ValueError, KeyError):
        return None


def register_cart(api: str, cart_id: str, token: str | None = None) -> str:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/carts", method="POST",
        data=json.dumps({"cart_id": cart_id, "name": "Xe Wokwi (cầu nối)"}).encode(),
        headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return f"đã đăng ký xe {cart_id} ({r.status})"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "Backend yêu cầu đăng nhập quản trị: đặt ADMIN_USERNAME/ADMIN_PASSWORD (hoặc đăng ký xe thủ công rồi dùng --no-register)"
        return f"xe {cart_id} đã có sẵn" if e.code == 409 else f"không đăng ký được xe (HTTP {e.code})"
    except OSError as e:
        return f"không gọi được Backend {api}: {e}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cart-id", default="WK_BRIDGE", help="mã xe hiển thị ở hệ thống (mặc định WK_BRIDGE)")
    ap.add_argument("--firmware-cart-id", default="CART_DEMO", help="CART_ID bên trong firmware (chế độ standalone: CART_DEMO)")
    ap.add_argument("--wokwi-host", default="localhost")
    ap.add_argument("--wokwi-port", type=int, default=int(os.getenv("WOKWI_SERIAL_PORT", "4000")))
    ap.add_argument("--mqtt-host", default=os.getenv("MQTT_HOST", "localhost"))
    ap.add_argument("--mqtt-port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    ap.add_argument("--api", default=os.getenv("API_URL", "http://localhost:8000"))
    ap.add_argument("--no-register", action="store_true", help="không tự đăng ký xe qua POST /api/carts")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    if not contract.CART_ID_RE.match(args.cart_id):
        raise SystemExit("--cart-id chỉ gồm [A-Za-z0-9_-], tối đa 32 ký tự")
    if not args.no_register:
        tok = None
        if os.getenv("ADMIN_PASSWORD"):
            tok = admin_token(args.api, os.getenv("ADMIN_USERNAME", "admin"), os.environ["ADMIN_PASSWORD"])
        print(register_cart(args.api, args.cart_id, tok))

    # Bảo mật (tuỳ chọn): MQTT_USERNAME/MQTT_PASSWORD/MQTT_TLS/MQTT_CA_FILE và DEVICE_MASTER_KEY lấy từ biến môi trường
    mqtt = MqttClient(f"wokwi-bridge-{args.cart_id}", args.mqtt_host, args.mqtt_port, keepalive=30, **options_from_env())
    master = os.getenv("DEVICE_MASTER_KEY", "")
    key = security.derive_cart_key(master, args.cart_id) if master else None
    link = SerialLink(args.wokwi_host, args.wokwi_port, on_line=lambda ln: bridge.on_serial_line(ln))
    bridge = Bridge(args.cart_id, args.firmware_cart_id, link.send, mqtt, key=key)
    mqtt.on_message = lambda topic, payload: bridge.on_mqtt_command(payload) if topic.endswith("/command") else None
    mqtt.subscribe(contract.topic(args.cart_id, "command"))
    mqtt.start()
    link.start()
    print(f"Cầu nối chạy: Wokwi {args.wokwi_host}:{args.wokwi_port} <-> MQTT {args.mqtt_host}:{args.mqtt_port} "
          f"(xe {args.cart_id}, topic gốc '{contract.TOPIC_ROOT}', ký HMAC={'BẬT' if key else 'tắt'}). Ctrl+C để dừng.")
    try:
        while True:
            time.sleep(10)
            log.info("thống kê: lên=%d xuống=%d bỏ qua=%d | serial=%s mqtt=%s", bridge.stats["up"], bridge.stats["down"],
                     bridge.stats["ignored"], "OK" if link.connected.is_set() else "--", "OK" if mqtt.connected else "--")
    except KeyboardInterrupt:
        pass
    finally:
        link.stop()
        mqtt.stop()


if __name__ == "__main__":
    main()
