"""API điều khiển Simulator qua HTTP (mặc định 127.0.0.1:8090) – phục vụ trang web /simulator.

Chỉ dùng thư viện chuẩn. Đây là công cụ DEV/DEMO: không có xác thực, nên mặc định chỉ lắng nghe
127.0.0.1 (đặt SIM_CONTROL_HOST=0.0.0.0 khi chạy trong Docker). CORS cho phép mọi origin.

  GET  /sim/carts                      trạng thái tất cả xe
  GET  /sim/catalog                    danh mục sản phẩm
  POST /sim/carts/{id}/scan            {"barcode": "...", "action": "ADD|REMOVE"}
  POST /sim/carts/{id}/battery         {"percent": 0..100}
  POST /sim/carts/{id}/weight_offset   {"grams": số}   (0 = bỏ vật lạ)
  POST /sim/carts/{id}/connection      {"online": true|false}
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from simulator import scenarios as sc

log = logging.getLogger("sim.control")


class ControlServer:
    def __init__(self, carts, host: str = "127.0.0.1", port: int = 8090, token: str | None = None):
        self.carts = {c.cart_id: c for c in carts}
        self.host, self.port = host, port
        self.token = token or os.getenv("SIM_CONTROL_TOKEN") or None
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ nghiệp vụ
    def catalog(self):
        c = next(iter(self.carts.values()))
        return [{"barcode": b, **{k: p[k] for k in ("name", "price", "unit_weight")}} for b, p in c.catalog.items()]

    def act(self, cart_id: str, action: str, body: dict):
        cart = self.carts.get(cart_id)
        if not cart:
            return 404, {"error": f"Không có xe {cart_id}"}
        try:
            if action == "scan":
                barcode = str(body.get("barcode", "")).strip()
                kind = body.get("action", "ADD")
                if not barcode or kind not in ("ADD", "REMOVE"):
                    return 400, {"error": "Cần barcode và action ADD|REMOVE"}
                result = cart.scan(barcode, kind)
                return 200, {"result": result, "cart": cart.snapshot()}
            if action == "battery":
                pct = float(body["percent"])
                if not 0 <= pct <= 100:
                    return 400, {"error": "percent phải trong 0..100"}
                sc.low_battery(cart, pct)
            elif action == "weight_offset":
                with cart.lock:
                    cart.weight_offset = float(body["grams"])
                cart.send_telemetry()
            elif action == "connection":
                online = bool(body["online"])
                if online and not cart.mqtt.connected:
                    sc.reconnect(cart)
                elif not online and cart.mqtt.connected:
                    sc.drop_connection(cart)
            elif action == "drain_queue":
                drained = cart.drain_offline_queue()
                return 200, {"drained": drained, "cart": cart.snapshot()}
            else:
                return 404, {"error": f"Không có hành động {action}"}
        except (KeyError, TypeError, ValueError) as e:
            return 400, {"error": f"Tham số không hợp lệ: {e}"}
        return 200, {"cart": cart.snapshot()}

    # ----------------------------------------------------------------- HTTP
    def _handler(self):
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # im lặng
                pass

            def _send(self, status, data):
                raw = json.dumps(data, ensure_ascii=False).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Sim-Token")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.end_headers()
                self.wfile.write(raw)

            def _check_auth(self) -> bool:
                if not srv.token:
                    return True
                auth = self.headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    auth = auth[7:].strip()
                sim_tok = self.headers.get("X-Sim-Token", "").strip()
                return (auth == srv.token) or (sim_tok == srv.token)

            def do_OPTIONS(self):
                self._send(204, {})

            def do_GET(self):
                if not self._check_auth():
                    return self._send(401, {"error": "Unauthorized: Cần SIM_CONTROL_TOKEN hợp lệ"})
                if self.path == "/sim/carts":
                    return self._send(200, [c.snapshot() for c in srv.carts.values()])
                if self.path == "/sim/catalog":
                    return self._send(200, srv.catalog())
                self._send(404, {"error": "Not found"})

            def do_POST(self):
                if not self._check_auth():
                    return self._send(401, {"error": "Unauthorized: Cần SIM_CONTROL_TOKEN hợp lệ"})
                m = re.fullmatch(r"/sim/carts/([\w-]+)/(\w+)", self.path)
                if not m:
                    return self._send(404, {"error": "Not found"})
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                    body = json.loads(self.rfile.read(n) or b"{}")
                    if not isinstance(body, dict):
                        raise ValueError
                except (ValueError, json.JSONDecodeError):
                    return self._send(400, {"error": "Body không phải JSON object"})
                self._send(*srv.act(m.group(1), m.group(2), body))

        return H

    def start(self) -> "ControlServer":
        self._httpd = ThreadingHTTPServer((self.host, self.port), self._handler())
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="sim-control", daemon=True)
        self._thread.start()
        log.info("Simulator control API: http://%s:%s/sim/carts", self.host, self.port)
        return self

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
