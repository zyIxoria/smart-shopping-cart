"""Quy tắc cảnh báo – hàm thuần (không I/O) để test độc lập.

Ngưỡng (mặc định, cấu hình qua env):
  LOW_BATTERY      battery_percent < 20 %
  WEIGHT_MISMATCH  |actual_weight - expected_weight| > 100 g
                   (expected = Σ quantity × unit_weight; chỉ xét khi xe IN_USE và có phiên ACTIVE)
  OFFLINE          > 15 s không nhận heartbeat/telemetry
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping


def expected_weight(items: Iterable[Mapping]) -> float:
    return float(sum(i["quantity"] * i["unit_weight"] for i in items))


def is_low_battery(battery_percent: float | None, threshold: float = 20) -> bool:
    return battery_percent is not None and battery_percent < threshold


def weight_diff(actual: float, expected: float) -> float:
    return abs(actual - expected)


def is_weight_mismatch(actual: float, expected: float, tolerance: float = 100) -> bool:
    return weight_diff(actual, expected) > tolerance


def is_offline(last_seen: datetime | None, now: datetime, timeout_s: float = 15) -> bool:
    if last_seen is None:
        return True
    return (now - last_seen).total_seconds() > timeout_s


def weight_applicable(cart_status: str, has_active_session: bool) -> bool:
    """Chỉ đối chiếu cân nặng khi khách đang mua (IN_USE + phiên ACTIVE)."""
    return cart_status == "IN_USE" and has_active_session
