"""Các kịch bản demo/kiểm thử. Mỗi hàm tác động lên một SmartCart."""
from __future__ import annotations

import random
import threading
import time


def low_battery(cart, percent: float = 15.0) -> None:
    """Pin tụt xuống dưới ngưỡng 20% -> Backend sinh cảnh báo LOW_BATTERY."""
    with cart.lock:
        cart.battery = percent
    cart.send_telemetry()


def recharge(cart, percent: float = 100.0) -> None:
    with cart.lock:
        cart.battery = percent
    cart.send_telemetry()


def weight_mismatch(cart, extra_g: float = 250.0) -> None:
    """Có vật lạ bỏ vào giỏ (không quét) -> cân nặng lệch > 100 g -> WEIGHT_MISMATCH."""
    with cart.lock:
        cart.weight_offset += extra_g
    cart.send_telemetry()


def fix_weight(cart) -> None:
    with cart.lock:
        cart.weight_offset = 0.0
    cart.send_telemetry()


def unknown_barcode(cart, barcode: str = "0000000000000") -> str:
    """Quét mã không có trong CSDL -> Backend từ chối (SCAN_REJECTED), không thêm hàng."""
    return cart.scan(barcode)


def drop_connection(cart, seconds: float | None = None) -> threading.Timer | None:
    """Mất kết nối; nếu có `seconds` thì tự kết nối lại sau đó."""
    cart.go_offline()
    if seconds:
        t = threading.Timer(seconds, cart.go_online)
        t.daemon = True
        t.start()
        return t
    return None


def reconnect(cart) -> None:
    cart.go_online()


class AutoShopper(threading.Thread):
    """Tự động quét hàng ngẫu nhiên cho các xe đang IN_USE (để demo không cần gõ tay)."""

    def __init__(self, carts, min_s: float = 3, max_s: float = 8, seed: int | None = None):
        super().__init__(name="auto-shopper", daemon=True)
        self.carts, self.min_s, self.max_s = carts, min_s, max_s
        self.rng = random.Random(seed)
        self._stop_evt = threading.Event()

    def run(self):
        while not self._stop_evt.wait(self.rng.uniform(self.min_s, self.max_s)):
            active = [c for c in self.carts if c.cart_status == "IN_USE" and c.mqtt.connected]
            if not active:
                continue
            cart = self.rng.choice(active)
            if cart.basket and self.rng.random() < 0.2:
                cart.scan(self.rng.choice(list(cart.basket)), "REMOVE")
            else:
                cart.scan(self.rng.choice(list(cart.catalog)), "ADD")

    def stop(self):
        self._stop_evt.set()
