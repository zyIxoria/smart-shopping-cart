from datetime import datetime, timedelta, timezone

from backend.alerts import rules as r


def test_expected_weight():
    items = [{"quantity": 2, "unit_weight": 355}, {"quantity": 1, "unit_weight": 137}]
    assert r.expected_weight(items) == 847 and r.expected_weight([]) == 0


def test_low_battery_threshold_is_strict():
    assert r.is_low_battery(19.9) and not r.is_low_battery(20) and not r.is_low_battery(None)
    assert r.is_low_battery(25, threshold=30)


def test_weight_mismatch_threshold_is_strict():
    assert not r.is_weight_mismatch(1100, 1000)       # đúng 100 g -> chưa lệch
    assert r.is_weight_mismatch(1100.1, 1000)
    assert r.is_weight_mismatch(850, 1000)            # lệch âm cũng tính


def test_offline_threshold():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert not r.is_offline(now - timedelta(seconds=15), now)
    assert r.is_offline(now - timedelta(seconds=15.1), now)
    assert r.is_offline(None, now)


def test_weight_applicable():
    assert r.weight_applicable("IN_USE", True)
    assert not r.weight_applicable("IN_USE", False)
    assert not r.weight_applicable("AVAILABLE", True) and not r.weight_applicable("LOCKED", True)
