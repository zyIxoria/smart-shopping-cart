"""SmartCart giả lập: giỏ hàng vật lý + cảm biến + MQTT."""
from __future__ import annotations

import logging
import random
import threading
import time

from shared.contract import new_id
from shared import security
from simulator.mqtt import CartMqtt

log = logging.getLogger("sim.cart")


class SmartCart:
    def __init__(self, cart_id: str, cfg, catalog: list[dict]):
        self.cart_id, self.cfg = cart_id, cfg
        self.catalog = {p["barcode"]: p for p in catalog}
        self.lock = threading.RLock()
        # trạng thái xe
        self.session_id: int | None = None
        self.locked = False
        self.basket: dict[str, int] = {}       # barcode -> số lượng (đồ thật trong giỏ)
        self.weight_offset = 0.0               # g – mô phỏng đồ lạ / lấy bớt đồ
        self.battery = float(cfg.battery_start)
        self.log: list[str] = []
        self.sent = {"heartbeat": 0, "telemetry": 0, "scan": 0, "event": 0, "ack": 0}
        self._handled: dict[str, dict] = {}    # command_id -> ack data (idempotent)
        self._t0 = time.monotonic()
        self._stop = threading.Event()
        self._tick: threading.Thread | None = None
        self.offline_queue: list[dict] = []    # Hàng đợi lưu trữ các gói quét khi mất mạng
        self.max_offline_queue = getattr(cfg, "offline_queue_max_size", 50)
        key = security.derive_cart_key(cfg.device_master_key, cart_id) if cfg.device_master_key else None
        self.mqtt = CartMqtt(cart_id, cfg.mqtt_host, cfg.mqtt_port, self._on_command, self._on_connected,
                             key=key, max_skew_s=cfg.max_command_skew_s, mqtt_options=cfg.mqtt_options or None)

    # ------------------------------------------------------------ trạng thái
    @property
    def cart_status(self) -> str:
        if self.locked:
            return "LOCKED"
        return "IN_USE" if self.session_id is not None else "AVAILABLE"

    def true_weight(self) -> float:
        base = sum(self.catalog[b]["unit_weight"] * q for b, q in self.basket.items())
        return max(0.0, base + self.weight_offset)

    def measured_weight(self) -> float:
        w = self.true_weight()
        if self.cfg.noise_g > 0:
            w += random.gauss(0, self.cfg.noise_g)
        return round(max(0.0, w), 1)

    def _note(self, msg: str) -> None:
        self.log.append(msg)
        del self.log[:-50]
        log.info("[%s] %s", self.cart_id, msg)

    # --------------------------------------------------------------- vòng đời
    def start(self) -> None:
        self._stop.clear()
        self.mqtt.start()
        self._tick = threading.Thread(target=self._run, name=f"tick-{self.cart_id}", daemon=True)
        self._tick.start()

    def stop(self, clean: bool = True) -> None:
        self._stop.set()
        self.mqtt.stop(clean=clean)
        if self._tick:
            self._tick.join(timeout=2)

    def go_offline(self) -> None:
        """Mất mạng đột ngột (không gửi DISCONNECT)."""
        self.mqtt.stop(clean=False)
        self._note("MẤT KẾT NỐI (mô phỏng)")

    def go_online(self) -> None:
        self.mqtt.start()
        self._note("KẾT NỐI LẠI (mô phỏng)")

    def drain_offline_queue(self) -> int:
        """Gửi bù các gói tin quét trong offline queue theo thứ tự FIFO khi xe online lại."""
        with self.lock:
            if not self.mqtt.connected or not self.offline_queue:
                return 0
            items = list(self.offline_queue)
            self.offline_queue.clear()

        sent_count = 0
        for item in items:
            ok = self._pub("scan", item)
            if ok:
                sent_count += 1
                self._note(f"Gửi bù offline: {item['action']} {item['barcode']} ({item['scan_id'][:8]})")
                time.sleep(0.05)
            else:
                with self.lock:
                    self.offline_queue = items[sent_count:] + self.offline_queue
                break
        return sent_count

    def _on_connected(self) -> None:
        # Sau (re)connect: gửi ngay heartbeat để Backend biết xe online
        self.send_heartbeat()
        self.drain_offline_queue()
        self.send_telemetry()

    def _run(self) -> None:
        c = self.cfg
        now = time.monotonic()
        next_hb, next_tel = now, now + 0.2
        next_drain, drain_backoff = 0.0, 0.5
        last = now
        while not self._stop.wait(0.1):
            now = time.monotonic()
            with self.lock:   # pin tụt dần
                self.battery = max(0.0, self.battery - c.battery_drain_per_min * (now - last) / 60.0)
            last = now
            if self.mqtt.connected and self.offline_queue and now >= next_drain:
                self.drain_offline_queue()
                if self.offline_queue:
                    next_drain = now + drain_backoff
                    drain_backoff = min(8.0, drain_backoff * 2.0)
                else:
                    drain_backoff = 0.5
            if now >= next_hb:
                self.send_heartbeat()
                next_hb = now + c.heartbeat_s
            if now >= next_tel:
                self.send_telemetry()
                next_tel = now + c.telemetry_s

    # -------------------------------------------------------------- gửi tin
    def _pub(self, kind: str, data: dict) -> bool:
        ok = self.mqtt.publish(kind, data)
        if ok:
            self.sent[kind] += 1
        return ok

    def send_heartbeat(self) -> bool:
        return self._pub("heartbeat", {"uptime_s": int(time.monotonic() - self._t0), "cart_status": self.cart_status})

    def send_telemetry(self) -> bool:
        with self.lock:
            data = {
                "actual_weight": self.measured_weight(),
                "battery_percent": round(self.battery, 1),
                "cart_status": self.cart_status,
                "wifi_status": "CONNECTED" if self.mqtt.connected else "DISCONNECTED",
                "mqtt_status": "CONNECTED" if self.mqtt.connected else "DISCONNECTED",
            }
        return self._pub("telemetry", data)

    def send_event(self, event_type: str, description: str = "") -> bool:
        return self._pub("event", {"event_type": event_type, "description": description})

    # ------------------------------------------------------------------ quét
    def scan(self, barcode: str, action: str = "ADD") -> str:
        """Khách quét mã. Trả mô tả kết quả (cho CLI)."""
        with self.lock:
            if self.locked:
                self._note(f"Xe đang KHOÁ – bỏ qua quét {barcode}")
                return "locked"
            if self.session_id is None:
                self._note(f"Chưa có phiên – bỏ qua quét {barcode}")
                return "no_session"
            product = self.catalog.get(barcode)
            if action == "REMOVE":
                if self.basket.get(barcode, 0) <= 0:
                    return "not_in_basket"
                self.basket[barcode] -= 1
                if self.basket[barcode] == 0:
                    del self.basket[barcode]
            elif product:
                self.basket[barcode] = self.basket.get(barcode, 0) + 1   # đồ thật được bỏ vào giỏ
            scan_payload = {"scan_id": new_id(), "barcode": barcode, "action": action}
            if self.mqtt.connected:
                sent = self._pub("scan", scan_payload)
            else:
                sent = False

            if not sent:
                if len(self.offline_queue) < self.max_offline_queue:
                    self.offline_queue.append(scan_payload)
                    self._note(f"Quét {action} {barcode} (LƯU OFFLINE QUEUE #{len(self.offline_queue)})")
                else:
                    self._note(f"Quét {action} {barcode} (OFFLINE QUEUE ĐẦY, BỎ QUA)")
            else:
                self._note(f"Quét {action} {barcode}")

            if product is None:
                self.send_event("UNKNOWN_BARCODE", f"Mã vạch không có trong danh mục: {barcode}")
        self.send_telemetry()   # cập nhật cân ngay sau khi bỏ đồ
        return "sent" if sent else "queued"

    # --------------------------------------------------------------- command
    def _ack(self, command_id: str, result: str, message: str = "") -> None:
        data = {"command_id": command_id, "result": result, "message": message}
        self._handled[command_id] = data
        self._pub("ack", data)

    def _on_command(self, env: dict) -> None:
        d = env["data"]
        cid, ctype, params = d["command_id"], d["command_type"], d.get("parameters", {})
        with self.lock:
            if cid in self._handled:        # lệnh lặp -> trả lại ACK cũ, không thực thi lại
                self._pub("ack", self._handled[cid])
                return
            if ctype == "LOCK_CART":
                self.locked = True
                self._note("Nhận LOCK_CART -> LOCKED")
                self._ack(cid, "OK", "Đã khoá xe")
                self.send_event("CART_LOCKED", "Xe đã bị khoá")
            elif ctype == "UNLOCK_CART":
                self.locked = False
                self._note(f"Nhận UNLOCK_CART -> {self.cart_status}")
                self._ack(cid, "OK", "Đã mở khoá")
                self.send_event("CART_UNLOCKED", "Xe đã được mở khoá")
            elif ctype == "START_SESSION":
                sid = params.get("session_id")
                if self.session_id != sid:      # phiên mới: giỏ thật phải trống
                    self.basket.clear()
                    self.weight_offset = 0.0
                self.session_id = sid
                self._note(f"Nhận START_SESSION #{sid} -> {self.cart_status}")
                self._ack(cid, "OK", "Đã bắt đầu phiên")
            elif ctype == "END_SESSION":
                self.session_id = None
                self.basket.clear()
                self.weight_offset = 0.0
                self._note(f"Nhận END_SESSION -> {self.cart_status}")
                self._ack(cid, "OK", "Đã kết thúc phiên")
            else:
                self._ack(cid, "FAILED", f"Lệnh không hỗ trợ: {ctype}")
        self.send_telemetry()

    @property
    def offline_queue_len(self) -> int:
        with self.lock:
            return len(self.offline_queue)

    def snapshot(self) -> dict:
        """Trạng thái đầy đủ của xe (cho giao diện web điều khiển Simulator)."""
        with self.lock:
            return {
                "cart_id": self.cart_id,
                "connected": self.mqtt.connected,
                "cart_status": self.cart_status,
                "session_id": self.session_id,
                "battery_percent": round(self.battery, 1),
                "true_weight": round(self.true_weight(), 1),
                "weight_offset": self.weight_offset,
                "basket": [
                    {"barcode": b, "name": self.catalog[b]["name"], "quantity": q, "unit_weight": self.catalog[b]["unit_weight"]}
                    for b, q in self.basket.items()
                ],
                "sent": dict(self.sent),
                "offline_queue_len": len(self.offline_queue),
                "log": self.log[-12:],
                "heartbeat_s": self.cfg.heartbeat_s,
                "telemetry_s": self.cfg.telemetry_s,
            }

    # ------------------------------------------------------------- mô tả CLI
    def status_line(self) -> str:
        with self.lock:
            items = sum(self.basket.values())
            conn = "ONLINE " if self.mqtt.connected else "OFFLINE"
            return (f"{self.cart_id}  {conn}  {self.cart_status:<9}  pin {self.battery:5.1f}%  "
                    f"cân {self.true_weight():8.1f} g  giỏ {items} món  phiên {self.session_id}")
