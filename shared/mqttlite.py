"""MQTT 3.1.1 client tối giản bằng thư viện chuẩn (không cần paho-mqtt).

Hỗ trợ: CONNECT (clean session, username/password), TLS (ssl.SSLContext), SUBSCRIBE (wildcard + # do broker xử lý),
PUBLISH QoS 0, nhận PUBLISH QoS 0/1 (tự gửi PUBACK), PINGREQ/PINGRESP,
tự động reconnect với backoff và tự subscribe lại sau khi kết nối lại.

Không hỗ trợ: QoS 1/2 khi publish, retained, will.
Giao diện cố tình giống paho (connect/subscribe/publish/on_message) để sau này
có thể thay bằng paho-mqtt chỉ trong một file này.
"""
from __future__ import annotations

import logging
import os
import socket
import ssl
import struct
import threading
import time
from typing import Callable

log = logging.getLogger("mqttlite")

CONNECT, CONNACK, PUBLISH, PUBACK = 1, 2, 3, 4
SUBSCRIBE, SUBACK, UNSUBSCRIBE, UNSUBACK = 8, 9, 10, 11
PINGREQ, PINGRESP, DISCONNECT = 12, 13, 14


# ---------------------------------------------------------------- packet utils
def enc_len(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n % 128
        n //= 128
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            return bytes(out)


def enc_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack(">H", len(b)) + b


def packet(ptype: int, flags: int, body: bytes = b"") -> bytes:
    return bytes([(ptype << 4) | flags]) + enc_len(len(body)) + body


def build_publish(topic: str, payload: bytes) -> bytes:
    return packet(PUBLISH, 0, enc_str(topic) + payload)


def parse_publish(flags: int, body: bytes):
    """-> (topic, payload, qos, packet_id|None)"""
    qos = (flags >> 1) & 0x3
    tlen = struct.unpack(">H", body[:2])[0]
    topic = body[2:2 + tlen].decode("utf-8")
    pos = 2 + tlen
    pid = None
    if qos:
        pid = struct.unpack(">H", body[pos:pos + 2])[0]
        pos += 2
    return topic, body[pos:], qos, pid


def recv_exact(sock: socket.socket, n: int, deadline_s: float = 10.0) -> bytes:
    buf = bytearray()
    end = time.monotonic() + deadline_s
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except socket.timeout:
            if time.monotonic() > end:
                raise
            continue
        if not chunk:
            raise ConnectionError("kết nối bị đóng")
        buf += chunk
    return bytes(buf)


def read_packet(sock: socket.socket):
    """Đọc 1 packet. Trả None nếu hết thời gian chờ byte đầu (không có dữ liệu)."""
    try:
        first = sock.recv(1)
    except socket.timeout:
        return None
    if not first:
        raise ConnectionError("kết nối bị đóng")
    mult, length = 1, 0
    while True:
        b = recv_exact(sock, 1)[0]
        length += (b & 0x7F) * mult
        if not b & 0x80:
            break
        mult *= 128
        if mult > 128 ** 3:
            raise ConnectionError("remaining length không hợp lệ")
    body = recv_exact(sock, length) if length else b""
    return first[0] >> 4, first[0] & 0x0F, body


CONNACK_TEXT = {
    1: "phiên bản giao thức không được hỗ trợ", 2: "client id bị từ chối", 3: "broker không sẵn sàng",
    4: "sai username/password", 5: "không được phép (not authorized)",
}


def build_connect(client_id: str, keepalive: int, username: str | None = None, password: str | None = None) -> bytes:
    flags = 0x02
    body = enc_str("MQTT") + bytes([4, 0]) + struct.pack(">H", keepalive) + enc_str(client_id)
    if username is not None:
        flags |= 0x80
        body += enc_str(username)
        if password is not None:
            flags |= 0x40
            body += enc_str(password)
    body = body[:7] + bytes([flags]) + body[8:]
    return packet(CONNECT, 0, body)


def parse_connect(body: bytes) -> dict:
    """-> {client_id, keepalive, username|None, password|None}; ném ValueError nếu sai cấu trúc."""
    def rd_str(pos):
        n = struct.unpack(">H", body[pos:pos + 2])[0]
        return body[pos + 2:pos + 2 + n].decode("utf-8"), pos + 2 + n

    try:
        proto, pos = rd_str(0)
        level, flags = body[pos], body[pos + 1]
        keepalive = struct.unpack(">H", body[pos + 2:pos + 4])[0]
        cid, pos = rd_str(pos + 4)
        if flags & 0x04:  # will
            _, pos = rd_str(pos)
            n = struct.unpack(">H", body[pos:pos + 2])[0]
            pos += 2 + n
        user = pwd = None
        if flags & 0x80:
            user, pos = rd_str(pos)
        if flags & 0x40:
            pwd, pos = rd_str(pos)
    except (struct.error, IndexError, UnicodeDecodeError) as e:
        raise ValueError(f"CONNECT hỏng: {e}") from e
    if proto != "MQTT" or level != 4:
        raise ValueError("chỉ hỗ trợ MQTT 3.1.1")
    return {"client_id": cid, "keepalive": keepalive, "username": user, "password": pwd}


def options_from_env(prefix: str = "MQTT") -> dict:
    """Đọc cấu hình bảo mật từ biến môi trường -> kwargs cho MqttClient.

    MQTT_USERNAME / MQTT_PASSWORD   : đăng nhập broker
    MQTT_TLS=1                      : bật TLS (cổng thường là 8883)
    MQTT_CA_FILE=<ca.pem>           : CA tin cậy (không đặt = dùng CA hệ thống)
    MQTT_TLS_INSECURE=1             : KHÔNG kiểm tra chứng chỉ (chỉ để thử, in cảnh báo)
    """
    opts: dict = {}
    user = os.getenv(f"{prefix}_USERNAME") or None
    if user:
        opts["username"] = user
        opts["password"] = os.getenv(f"{prefix}_PASSWORD", "")
    if os.getenv(f"{prefix}_TLS", "0") not in ("", "0", "false", "False"):
        opts["tls"] = make_tls_context(os.getenv(f"{prefix}_CA_FILE") or None,
                                       insecure=os.getenv(f"{prefix}_TLS_INSECURE", "0") == "1")
    return opts


def make_tls_context(ca_file: str | None = None, insecure: bool = False) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if insecure:
        log.warning("TLS_INSECURE: KHÔNG kiểm tra chứng chỉ broker – chỉ dùng để thử nghiệm")
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    elif ca_file:
        ctx.load_verify_locations(cafile=ca_file)
    else:
        ctx.load_default_certs()
    return ctx


# ---------------------------------------------------------------------- client
class MqttClient:
    def __init__(
        self,
        client_id: str,
        host: str = "localhost",
        port: int = 1883,
        keepalive: int = 30,
        reconnect_min: float = 0.5,
        reconnect_max: float = 8.0,
        username: str | None = None,
        password: str | None = None,
        tls: ssl.SSLContext | None = None,
    ):
        self.client_id = client_id
        self.username, self.password, self.tls = username, password, tls
        self.last_error: str | None = None   # lý do kết nối thất bại gần nhất (sai mật khẩu, TLS...)
        self.host, self.port, self.keepalive = host, port, keepalive
        self.reconnect_min, self.reconnect_max = reconnect_min, reconnect_max
        self.on_message: Callable[[str, bytes], None] | None = None
        self.on_connect: Callable[["MqttClient"], None] | None = None
        self.on_disconnect: Callable[["MqttClient"], None] | None = None
        self._topics: list[str] = []
        self._sock: socket.socket | None = None
        self._send_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._connected = threading.Event()
        self._pid = 0

    # --- public ---------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def subscribe(self, topic_filter: str) -> None:
        if topic_filter not in self._topics:
            self._topics.append(topic_filter)
        if self.connected:
            self._send_subscribe([topic_filter])

    def publish(self, topic: str, payload: bytes | str, qos: int = 0) -> bool:
        if qos != 0:
            raise ValueError("mqttlite chỉ hỗ trợ publish QoS 0")
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        if not self.connected:
            return False
        return self._send(build_publish(topic, payload))

    def start(self) -> None:
        """Bắt đầu (hoặc bắt đầu lại sau stop) vòng kết nối nền."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=f"mqtt-{self.client_id}", daemon=True)
        self._thread.start()

    def stop(self, clean: bool = True) -> None:
        """Dừng client. clean=False mô phỏng mất mạng đột ngột (không gửi DISCONNECT)."""
        self._stop.set()
        sock = self._sock
        if sock is not None:
            if clean and self.connected:
                self._send(packet(DISCONNECT, 0))
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass
        t = self._thread
        if t and t is not threading.current_thread():
            t.join(timeout=3)
        self._connected.clear()

    def wait_connected(self, timeout: float = 5.0) -> bool:
        return self._connected.wait(timeout)

    # --- internals ------------------------------------------------------
    def _next_pid(self) -> int:
        self._pid = (self._pid % 65535) + 1
        return self._pid

    def _send(self, data: bytes) -> bool:
        sock = self._sock
        if sock is None:
            return False
        try:
            with self._send_lock:
                sock.sendall(data)
            self._last_send = time.monotonic()
            return True
        except OSError as e:
            log.debug("%s gửi lỗi: %s", self.client_id, e)
            try:
                sock.close()
            except OSError:
                pass
            return False

    def _send_subscribe(self, topics: list[str]) -> None:
        body = struct.pack(">H", self._next_pid())
        for t in topics:
            body += enc_str(t) + b"\x00"
        self._send(packet(SUBSCRIBE, 0x02, body))

    def _run(self) -> None:
        backoff = self.reconnect_min
        while not self._stop.is_set():
            was_connected = False
            try:
                sock = socket.create_connection((self.host, self.port), timeout=5)
                if self.tls is not None:
                    sock = self.tls.wrap_socket(sock, server_hostname=self.host)
                sock.settimeout(1.0)
                self._sock = sock
                self._last_send = self._last_recv = time.monotonic()
                if not self._send(build_connect(self.client_id, self.keepalive, self.username, self.password)):
                    raise ConnectionError("không gửi được CONNECT")
                pkt = None
                t_end = time.monotonic() + 5
                while pkt is None and time.monotonic() < t_end:
                    pkt = read_packet(sock)
                if not pkt or pkt[0] != CONNACK or len(pkt[2]) < 2:
                    raise ConnectionError(f"CONNACK lỗi: {pkt}")
                if pkt[2][1] != 0:
                    code = pkt[2][1]
                    raise PermissionError(f"broker từ chối kết nối (mã {code}: {CONNACK_TEXT.get(code, '?')})")
                self.last_error = None
                self._connected.set()
                was_connected = True
                backoff = self.reconnect_min
                if self._topics:
                    self._send_subscribe(list(self._topics))
                log.info("%s đã kết nối %s:%s", self.client_id, self.host, self.port)
                if self.on_connect:
                    self._safe(self.on_connect, self)
                self._loop(sock)
            except Exception as e:  # noqa: BLE001 - vòng reconnect phải sống
                if not self._stop.is_set():
                    msg = str(e) or type(e).__name__
                    if msg != self.last_error and not was_connected:
                        # lỗi cấu hình (sai mật khẩu, chứng chỉ) cần thấy được, nhưng chỉ in khi nội dung thay đổi
                        log.warning("%s không kết nối được %s:%s – %s", self.client_id, self.host, self.port, msg)
                    self.last_error = msg
                    log.debug("%s mất kết nối/không kết nối được: %s", self.client_id, e)
            finally:
                self._connected.clear()
                try:
                    if self._sock:
                        self._sock.close()
                except OSError:
                    pass
                self._sock = None
                if was_connected and self.on_disconnect:
                    self._safe(self.on_disconnect, self)
            if self._stop.wait(backoff):
                break
            backoff = min(backoff * 2, self.reconnect_max)

    def _loop(self, sock: socket.socket) -> None:
        while not self._stop.is_set():
            pkt = read_packet(sock)
            now = time.monotonic()
            if pkt is None:
                if now - self._last_recv > self.keepalive * 1.5:
                    raise TimeoutError("broker không phản hồi")
                if now - self._last_send > self.keepalive * 0.6:
                    self._send(packet(PINGREQ, 0))
                continue
            self._last_recv = now
            ptype, flags, body = pkt
            if ptype == PUBLISH:
                topic, payload, qos, pid = parse_publish(flags, body)
                if qos == 1 and pid is not None:
                    self._send(packet(PUBACK, 0, struct.pack(">H", pid)))
                if self.on_message:
                    self._safe(self.on_message, topic, payload)

    @staticmethod
    def _safe(fn, *args) -> None:
        try:
            fn(*args)
        except Exception:  # noqa: BLE001
            log.exception("callback lỗi")
