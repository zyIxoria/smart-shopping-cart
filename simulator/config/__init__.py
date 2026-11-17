"""Cấu hình Simulator (env). Có thể ghi đè bằng tham số dòng lệnh."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _f(n, d):
    return float(os.getenv(n, d))


@dataclass
class SimConfig:
    mqtt_host: str = field(default_factory=lambda: os.getenv("MQTT_HOST", "localhost"))
    mqtt_port: int = field(default_factory=lambda: int(os.getenv("MQTT_PORT", 1883)))
    cart_count: int = field(default_factory=lambda: int(os.getenv("SIM_CARTS", 3)))
    heartbeat_s: float = field(default_factory=lambda: _f("SIM_HEARTBEAT_S", 5))
    telemetry_s: float = field(default_factory=lambda: _f("SIM_TELEMETRY_S", 10))
    battery_start: float = field(default_factory=lambda: _f("SIM_BATTERY_START", 100))
    battery_drain_per_min: float = field(default_factory=lambda: _f("SIM_BATTERY_DRAIN_PER_MIN", 0.2))
    noise_g: float = field(default_factory=lambda: _f("SIM_NOISE_G", 3))
    # bảo mật (xem docs/SECURITY.md): khoá chủ -> khoá riêng từng xe; đăng nhập/TLS lấy từ MQTT_USERNAME, MQTT_TLS...
    device_master_key: str = field(default_factory=lambda: os.getenv("DEVICE_MASTER_KEY", ""))
    mqtt_options: dict = field(default_factory=dict)   # kwargs MqttClient; rỗng = đọc từ biến môi trường
    max_command_skew_s: float = field(default_factory=lambda: _f("MAX_CLOCK_SKEW_S", 300))
    catalog_path: str = field(default_factory=lambda: os.getenv("SIM_CATALOG", str(ROOT / "data" / "products_seed.json")))

    def cart_ids(self) -> list[str]:
        return [f"CART_{i:03d}" for i in range(1, self.cart_count + 1)]

    def catalog(self) -> list[dict]:
        return json.loads(Path(self.catalog_path).read_text(encoding="utf-8"))
