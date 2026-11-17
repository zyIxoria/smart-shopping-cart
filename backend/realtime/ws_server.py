"""WebSocket server RFC 6455 viết tay bằng asyncio (chỉ phát sự kiện server -> client).

Lý do tự viết: môi trường build không có thư viện `websockets`/`wsproto`. Khi chuyển sang
FastAPI/Starlette + uvicorn[standard] có thể thay bằng `@app.websocket("/ws")` mà
giữ nguyên định dạng sự kiện (xem docs/api).
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import struct

from backend.auth import ROOT_PRINCIPAL
from shared.contract import iso

log = logging.getLogger("ws")
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def encode_frame(opcode: int, payload: bytes) -> bytes:
    head = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        head += bytes([n])
    elif n < 65536:
        head += bytes([126]) + struct.pack(">H", n)
    else:
        head += bytes([127]) + struct.pack(">Q", n)
    return head + payload


async def read_frame(reader: asyncio.StreamReader):
    b1, b2 = await reader.readexactly(2)
    opcode = b1 & 0x0F
    masked = b2 & 0x80
    n = b2 & 0x7F
    if n == 126:
        n = struct.unpack(">H", await reader.readexactly(2))[0]
    elif n == 127:
        n = struct.unpack(">Q", await reader.readexactly(8))[0]
    if n > 1_000_000:
        raise ConnectionError("frame quá lớn")
    mask = await reader.readexactly(4) if masked else b""
    data = await reader.readexactly(n) if n else b""
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data


class WsConnection:
    def __init__(self, writer: asyncio.StreamWriter, principal):
        self.writer = writer
        self.principal = principal        # đổi sau khi client gửi {"type":"AUTH","token":...}

    def send_text(self, text: str) -> None:
        try:
            self.writer.write(encode_frame(0x1, text.encode("utf-8")))
        except Exception:  # noqa: BLE001
            pass


class WsServer:
    MAX_CLIENTS = 200

    def __init__(self, hub, host: str = "0.0.0.0", port: int = 8081, auth=None, allowed_origins=None):
        self.hub, self.host, self.port = hub, host, port
        self.auth = auth                                     # backend.auth.AuthService | None (None = không kiểm tra)
        self.allowed_origins = [o for o in (allowed_origins or []) if o != "*"]
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> None:
        self.hub.loop = asyncio.get_running_loop()
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]
        log.info("WebSocket lắng nghe ws://%s:%s/ws", self.host, self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            for c in list(self.hub.clients):
                try:
                    c.writer.close()
                except Exception:  # noqa: BLE001
                    pass
            self.hub.clients.clear()
            try:
                await asyncio.wait_for(self._server.wait_closed(), 2)
            except asyncio.TimeoutError:
                pass

    def _on_text(self, conn: WsConnection, data: bytes) -> None:
        try:
            msg = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(msg, dict) or msg.get("type") != "AUTH":
            return
        tok = msg.get("token")
        p = self.auth.authenticate_token(tok if isinstance(tok, str) else None)
        if p.authenticated:
            conn.principal = p
            conn.send_text(json.dumps({"type": "AUTHED", "role": p.role, "timestamp": iso()}))
        else:
            conn.principal = self.auth.authenticate_token(None)
            conn.send_text(json.dumps({"type": "AUTH_FAILED", "timestamp": iso()}))

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        conn = WsConnection(writer, self.auth.authenticate_token(None) if self.auth else ROOT_PRINCIPAL)
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5)
            lines = head.decode("latin-1").split("\r\n")
            request_line = lines[0].split(" ")
            headers = {}
            for ln in lines[1:]:
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            path = request_line[1] if len(request_line) > 1 else "/"
            if headers.get("upgrade", "").lower() != "websocket" or "sec-websocket-key" not in headers:
                body = b"WebSocket endpoint: ws://host/ws"
                writer.write(b"HTTP/1.1 426 Upgrade Required\r\nContent-Length: %d\r\nConnection: close\r\n\r\n" % len(body) + body)
                await writer.drain()
                return
            origin = headers.get("origin")
            if self.allowed_origins and origin and origin not in self.allowed_origins:
                writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await writer.drain()
                return
            if len(self.hub.clients) >= self.MAX_CLIENTS:
                writer.write(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await writer.drain()
                return
            if path.split("?")[0] != "/ws":
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await writer.drain()
                return
            accept = base64.b64encode(hashlib.sha1((headers["sec-websocket-key"] + GUID).encode()).digest()).decode()
            writer.write(
                ("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                 f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode()
            )
            await writer.drain()
            self.hub.clients.add(conn)
            conn.send_text(json.dumps({"type": "CONNECTED", "timestamp": iso()}))
            await writer.drain()
            while True:
                opcode, data = await read_frame(reader)
                if opcode == 0x8:  # close
                    writer.write(encode_frame(0x8, data[:2]))
                    await writer.drain()
                    break
                if opcode == 0x9:  # ping
                    writer.write(encode_frame(0xA, data))
                if opcode == 0x1 and self.auth and len(data) <= 4096:
                    self._on_text(conn, data)           # chỉ hiểu tin AUTH; còn lại bỏ qua (kênh một chiều)
                await writer.drain()
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, ConnectionError, OSError):
            pass
        finally:
            self.hub.clients.discard(conn)
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass
