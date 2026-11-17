"""MQTT broker tối giản chỉ dùng để DEV/TEST khi không có Mosquitto.

Production/demo dùng Mosquitto (docker-compose). Broker này chỉ cài đủ giao thức
MQTT 3.1.1 để Backend và Simulator nói chuyện được: CONNECT, SUBSCRIBE
(wildcard + và #), PUBLISH QoS 0/1 (forward QoS 0), PINGREQ, DISCONNECT.

Bảo mật (tuỳ chọn, giống cấu hình Mosquitto trong mosquitto/secure/):
  --users users.json     bật xác thực username/password + ACL theo vai trò (không có = cho ẩn danh như cũ)
  --tls-cert/--tls-key   bật TLS (chứng chỉ do `python -m tools.provision` sinh ra)

Chạy:  python -m tools.dev_broker --port 1883
       python -m tools.dev_broker --port 8883 --users secrets/mqtt_users.json --tls-cert secrets/tls/server.crt --tls-key secrets/tls/server.key
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import ssl
import struct
import threading

from shared import security
from shared.mqttlite import (CONNACK, CONNECT, DISCONNECT, PINGREQ, PINGRESP, PUBACK, PUBLISH, SUBACK, SUBSCRIBE,
                             UNSUBACK, UNSUBSCRIBE, build_publish, enc_len, packet, parse_connect, parse_publish)

log = logging.getLogger("dev_broker")

UPLINK = ("scan", "event", "telemetry", "heartbeat", "ack")   # xe -> Backend
DOWNLINK = ("command",)                                       # Backend -> xe


def covers(pattern: str, flt: str) -> bool:
    """Bộ lọc `flt` mà client xin subscribe có nằm trọn trong mẫu cho phép `pattern` không."""
    p, f = pattern.split("/"), flt.split("/")
    for i, part in enumerate(p):
        if part == "#":
            return True
        if i >= len(f):
            return False
        if f[i] == "#":
            return False
        if part == "+":
            continue            # '+' trong mẫu cho phép bất kỳ một cấp nào (kể cả '+')
        if part != f[i]:
            return False
    return len(p) == len(f)


class Acl:
    """ACL theo vai trò (xem docs/SECURITY.md):

    backend : subscribe  ROOT/+/{scan,event,telemetry,heartbeat,ack}   publish ROOT/+/command
    cart    : publish    ROOT/<tên đăng nhập>/{scan,...,ack}            subscribe ROOT/<tên đăng nhập>/command
    sim     : như cart nhưng cho mọi cart_id (Simulator chạy nhiều xe bằng một tài khoản)
    """

    def __init__(self, root: str):
        self.root = root

    def publish_patterns(self, user: str, role: str) -> list[str]:
        r = self.root
        if role == "backend":
            return [f"{r}/+/{k}" for k in DOWNLINK]
        who = "+" if role == "sim" else user
        return [f"{r}/{who}/{k}" for k in UPLINK]

    def subscribe_patterns(self, user: str, role: str) -> list[str]:
        r = self.root
        if role == "backend":
            return [f"{r}/+/{k}" for k in UPLINK]
        who = "+" if role == "sim" else user
        return [f"{r}/{who}/{k}" for k in DOWNLINK]

    def can_publish(self, user: str, role: str, topic: str) -> bool:
        return any(covers(p, topic) for p in self.publish_patterns(user, role))

    def can_subscribe(self, user: str, role: str, flt: str) -> bool:
        return any(covers(p, flt) for p in self.subscribe_patterns(user, role))


def load_users(path: str) -> dict:
    """users.json: {"<user>": {"password_hash": "pbkdf2_sha256$...", "role": "backend|cart|sim"}}"""
    with open(path, encoding="utf-8") as f:
        users = json.load(f)
    for name, u in users.items():
        if u.get("role") not in ("backend", "cart", "sim") or "password_hash" not in u:
            raise ValueError(f"user {name!r} thiếu role/password_hash hợp lệ")
    return users


def topic_matches(flt: str, topic: str) -> bool:
    f, t = flt.split("/"), topic.split("/")
    for i, part in enumerate(f):
        if part == "#":
            return True
        if i >= len(t):
            return False
        if part != "+" and part != t[i]:
            return False
    return len(f) == len(t)


class DevBroker:
    def __init__(self, host: str = "127.0.0.1", port: int = 1883, users: dict | None = None,
                 ssl_context: ssl.SSLContext | None = None, topic_root: str | None = None):
        self.host, self.port = host, port
        self.users = users                    # None = cho phép ẩn danh (chế độ DEV cũ)
        self.ssl_context = ssl_context
        if topic_root is None:
            from shared import contract
            topic_root = contract.TOPIC_ROOT
        self.acl = Acl(topic_root)
        self.denied = 0                       # số thao tác bị ACL chặn (dùng trong test/giám sát)
        self.auth_failed = 0
        self.sessions: set["_Session"] = set()
        self._server: asyncio.AbstractServer | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self.published = 0

    # --- asyncio --------------------------------------------------------
    async def _read_packet(self, reader: asyncio.StreamReader):
        first = await reader.readexactly(1)
        mult, length = 1, 0
        while True:
            b = (await reader.readexactly(1))[0]
            length += (b & 0x7F) * mult
            if not b & 0x80:
                break
            mult *= 128
        if length > 262144:
            raise ConnectionError("gói MQTT quá lớn")
        body = await reader.readexactly(length) if length else b""
        return first[0] >> 4, first[0] & 0x0F, body

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        sess = _Session(writer)
        try:
            while True:
                ptype, flags, body = await self._read_packet(reader)
                if ptype == CONNECT:
                    code = await asyncio.get_running_loop().run_in_executor(None, self._authenticate, sess, body)
                    writer.write(packet(CONNACK, 0, bytes([0, code])))
                    if code:
                        await writer.drain()
                        break
                    self.sessions.add(sess)
                elif not sess.authed:
                    break               # gói đầu tiên bắt buộc là CONNECT hợp lệ
                elif ptype == SUBSCRIBE:
                    pid = body[:2]
                    pos, granted = 2, b""
                    while pos < len(body):
                        tlen = struct.unpack(">H", body[pos:pos + 2])[0]
                        flt = body[pos + 2:pos + 2 + tlen].decode()
                        pos += 2 + tlen + 1
                        if self.users is None or self.acl.can_subscribe(sess.user, sess.role, flt):
                            sess.filters.add(flt)
                            granted += b"\x00"
                        else:
                            self.denied += 1
                            log.warning("ACL: %s không được subscribe %s", sess.user, flt)
                            granted += b"\x80"
                    writer.write(packet(SUBACK, 0, pid + granted))
                elif ptype == UNSUBSCRIBE:
                    pid = body[:2]
                    pos = 2
                    while pos < len(body):
                        tlen = struct.unpack(">H", body[pos:pos + 2])[0]
                        sess.filters.discard(body[pos + 2:pos + 2 + tlen].decode())
                        pos += 2 + tlen
                    writer.write(packet(UNSUBACK, 0, pid))
                elif ptype == PUBLISH:
                    topic, payload, qos, pid = parse_publish(flags, body)
                    if qos == 1 and pid is not None:
                        writer.write(packet(PUBACK, 0, struct.pack(">H", pid)))
                    if self.users is not None and not self.acl.can_publish(sess.user, sess.role, topic):
                        self.denied += 1        # giống Mosquitto: lặng lẽ bỏ message, ghi log
                        log.warning("ACL: %s không được publish %s", sess.user, topic)
                        await writer.drain()
                        continue
                    self.published += 1
                    out = build_publish(topic, payload)
                    for s in list(self.sessions):
                        if any(topic_matches(f, topic) for f in s.filters):
                            s.writer.write(out)
                elif ptype == PINGREQ:
                    writer.write(packet(PINGRESP, 0))
                elif ptype == DISCONNECT:
                    break
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            pass
        finally:
            self.sessions.discard(sess)
            try:
                writer.close()
            except OSError:
                pass

    def _authenticate(self, sess: "_Session", body: bytes) -> int:
        """Trả mã CONNACK: 0 ok, 2 client id/giao thức sai, 4 sai user/mật khẩu."""
        try:
            c = parse_connect(body)
        except ValueError as e:
            log.warning("CONNECT không hợp lệ: %s", e)
            return 2
        if self.users is None:
            sess.authed, sess.user, sess.role = True, c["username"] or "", "anonymous"
            return 0
        u = self.users.get(c["username"] or "")
        # luôn băm một lần dù user không tồn tại, để thời gian trả lời không lộ tài khoản nào có thật
        stored = u["password_hash"] if u else _DUMMY_HASH
        ok = security.verify_password(c["password"] or "", stored) and u is not None
        if not ok:
            self.auth_failed += 1
            log.warning("đăng nhập MQTT thất bại: user=%r", c["username"])
            return 4
        sess.authed, sess.user, sess.role = True, c["username"], u["role"]
        return 0

    async def serve(self):
        self._server = await asyncio.start_server(self._handle, self.host, self.port, ssl=self.ssl_context)
        log.info("dev broker lắng nghe %s:%s", self.host, self.port)
        async with self._server:
            await self._server.serve_forever()

    # --- chạy nền trong thread (dùng cho test) ---------------------------
    def start_in_thread(self) -> "DevBroker":
        ready = threading.Event()

        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def main():
                self._server = await asyncio.start_server(self._handle, self.host, self.port, ssl=self.ssl_context)
                if self.port == 0:
                    self.port = self._server.sockets[0].getsockname()[1]
                ready.set()
                async with self._server:
                    await self._server.serve_forever()

            try:
                self._loop.run_until_complete(main())
            except asyncio.CancelledError:
                pass
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=run, name="dev-broker", daemon=True)
        self._thread.start()
        ready.wait(5)
        return self

    def stop(self):
        loop, server = self._loop, self._server
        if loop and server:
            def shut():
                server.close()
                for s in list(self.sessions):
                    s.writer.close()
                for t in asyncio.all_tasks(loop):
                    t.cancel()
            loop.call_soon_threadsafe(shut)
        if self._thread:
            self._thread.join(timeout=3)


class _Session:
    def __init__(self, writer):
        self.writer = writer
        self.filters: set[str] = set()
        self.authed = False
        self.user = ""
        self.role = "anonymous"


_DUMMY_HASH = security.hash_password("dummy", iterations=1000)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--users", help="file users.json (bật xác thực + ACL)")
    ap.add_argument("--tls-cert")
    ap.add_argument("--tls-key")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ssl_ctx = None
    if args.tls_cert or args.tls_key:
        if not (args.tls_cert and args.tls_key):
            ap.error("--tls-cert và --tls-key phải đi cùng nhau")
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_ctx.load_cert_chain(args.tls_cert, args.tls_key)
    users = load_users(args.users) if args.users else None
    if users is None:
        log.warning("Không có --users: broker cho phép ẩn danh (chỉ dùng DEV, không dùng khi ra mạng)")
    try:
        asyncio.run(DevBroker(args.host, args.port, users=users, ssl_context=ssl_ctx).serve())
    except KeyboardInterrupt:
        pass
