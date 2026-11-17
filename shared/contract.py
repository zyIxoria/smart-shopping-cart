"""MQTT contract dùng chung cho Backend, Simulator (và ESP32 sau này).

Tài liệu: docs/mqtt/MQTT_CONTRACT.md
Mọi message đều là JSON UTF-8 với "envelope" thống nhất:

    {
      "message_id": "uuid",
      "cart_id": "CART_001",
      "schema_version": 1,
      "timestamp": "2026-11-07T10:30:00Z",
      "data": { ... }          # tuỳ topic
    }
"""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone

from shared import security

SCHEMA_VERSION = 1
# Gốc topic. Mặc định "smartcart". Khi dùng MQTT broker CÔNG CỘNG (vd. chạy mô phỏng Wokwi) hãy đặt
# MQTT_TOPIC_ROOT=smartcart-<chuỗi-ngẫu-nhiên> ở Backend/Simulator và firmware để không lẫn với người khác.
TOPIC_ROOT = os.getenv("MQTT_TOPIC_ROOT", "smartcart").strip() or "smartcart"
if not re.fullmatch(r"[A-Za-z0-9_-]{1,48}", TOPIC_ROOT):
    raise ValueError("MQTT_TOPIC_ROOT chỉ gồm [A-Za-z0-9_-], tối đa 48 ký tự")
KINDS = ("scan", "event", "telemetry", "heartbeat", "command", "ack")

# --- enum dùng chung (xem "Quy ước chung" trong tài liệu) -------------------
CART_STATUS = ("AVAILABLE", "IN_USE", "LOCKED")
CONNECTION_STATUS = ("ONLINE", "OFFLINE")
SESSION_STATUS = ("ACTIVE", "COMPLETED")
ALERT_TYPES = ("LOW_BATTERY", "WEIGHT_MISMATCH", "OFFLINE")
ALERT_STATUS = ("ACTIVE", "RESOLVED")
# LOCK_CART là lệnh bắt buộc theo đề cương; 3 lệnh còn lại là mở rộng để
# đồng bộ vòng đời phiên mua hàng giữa Backend và xe (xem docs/mqtt).
COMMANDS = ("LOCK_CART", "UNLOCK_CART", "START_SESSION", "END_SESSION")
SCAN_ACTIONS = ("ADD", "REMOVE")

CART_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


class ContractError(ValueError):
    """Message không đúng contract (sẽ bị bỏ qua và ghi log)."""


class SignatureError(ContractError):
    """Thiếu chữ ký (missing=True) hoặc chữ ký sai (missing=False)."""

    def __init__(self, msg: str, missing: bool = False):
        super().__init__(msg)
        self.missing = missing


# --- topic ------------------------------------------------------------------
def topic(cart_id: str, kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"kind không hợp lệ: {kind}")
    return f"{TOPIC_ROOT}/{cart_id}/{kind}"


def parse_topic(t: str):
    """'smartcart/CART_001/scan' -> ('CART_001', 'scan'); sai định dạng -> None."""
    parts = t.split("/")
    if len(parts) != 3 or parts[0] != TOPIC_ROOT:
        return None
    if parts[2] not in KINDS or not CART_ID_RE.match(parts[1]):
        return None
    return parts[1], parts[2]


# --- thời gian & id ---------------------------------------------------------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    dt = dt or utcnow()
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s: str) -> datetime:
    if not isinstance(s, str):
        raise ContractError("timestamp phải là chuỗi ISO 8601")
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise ContractError(f"timestamp không hợp lệ: {s!r}") from e
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def new_id() -> str:
    return str(uuid.uuid4())


# --- build / encode ---------------------------------------------------------
def envelope(cart_id: str, data: dict, message_id: str | None = None, timestamp: str | None = None) -> dict:
    return {
        "message_id": message_id or new_id(),
        "cart_id": cart_id,
        "schema_version": SCHEMA_VERSION,
        "timestamp": timestamp or iso(),
        "data": data,
    }


def encode(env: dict) -> bytes:
    return json.dumps(env, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _compact(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def encode_signed(env: dict, key: bytes, kind: str) -> bytes:
    """Như encode() nhưng thêm trường `sig` = HMAC-SHA256 (hex) ngay trước `data`.

    Thứ tự cố định: message_id, cart_id, schema_version, timestamp, sig, data.
    Người nhận ký/kiểm tra trên đúng chuỗi `data` nhận được (không "chuẩn hoá" lại) nên
    firmware C++ và Python không cần sinh JSON giống hệt nhau từng byte.
    """
    data_raw = _compact(env["data"])
    sig = security.sign_message(key, env["message_id"], env["cart_id"], env["timestamp"], kind, data_raw)
    head = {k: env[k] for k in ("message_id", "cart_id", "schema_version", "timestamp")}
    head["sig"] = sig
    return (_compact(head)[:-1] + ',"data":' + data_raw + "}").encode("utf-8")


def verify_payload(kind: str, key: bytes, payload: bytes) -> None:
    """Kiểm tra chữ ký của payload thô. Ném SignatureError nếu thiếu/sai; ContractError nếu hỏng cấu trúc."""
    try:
        text = payload.decode("utf-8")
        env = json.loads(text)
        spans = security.top_level_spans(text)
    except (UnicodeDecodeError, json.JSONDecodeError, security.SecurityError) as e:
        raise ContractError(f"payload không phải JSON hợp lệ: {e}") from e
    if not isinstance(env, dict):
        raise ContractError("payload phải là JSON object")
    sig = env.get("sig")
    if sig is None:
        raise SignatureError("thiếu chữ ký (sig)", missing=True)
    raw = spans.get("data")
    mid, cid, ts = env.get("message_id"), env.get("cart_id"), env.get("timestamp")
    if raw is None or not all(isinstance(x, str) for x in (mid, cid, ts)):
        raise SignatureError("envelope thiếu trường để kiểm tra chữ ký")
    try:
        same = json.loads(raw) == env.get("data")
    except json.JSONDecodeError:
        same = False
    if not same:
        raise SignatureError("data không nhất quán")
    if not security.verify_message(key, sig, mid, cid, ts, kind, raw):
        raise SignatureError("chữ ký không hợp lệ")


def check_freshness(env: dict, max_skew_s: float) -> None:
    """Loại message cũ/lệch giờ (chống phát lại). max_skew_s <= 0 = tắt."""
    if max_skew_s > 0:
        delta = abs((utcnow() - parse_ts(env["timestamp"])).total_seconds())
        if delta > max_skew_s:
            raise ContractError(f"timestamp lệch {delta:.0f}s (> {max_skew_s:.0f}s)")


# --- decode + validate ------------------------------------------------------
def _num(data: dict, key: str, lo: float, hi: float, required: bool = True):
    if key not in data:
        if required:
            raise ContractError(f"thiếu trường data.{key}")
        return None
    v = data[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ContractError(f"data.{key} phải là số")
    if not (lo <= v <= hi):
        raise ContractError(f"data.{key}={v} ngoài khoảng [{lo}, {hi}]")
    return v


def _str(data: dict, key: str, required: bool = True, max_len: int = 128):
    if key not in data:
        if required:
            raise ContractError(f"thiếu trường data.{key}")
        return None
    v = data[key]
    if not isinstance(v, str) or not v.strip() or len(v) > max_len:
        raise ContractError(f"data.{key} phải là chuỗi không rỗng (<= {max_len} ký tự)")
    return v


def validate_data(kind: str, data: dict) -> dict:
    """Kiểm tra phần `data` theo từng topic; trả về dict đã chuẩn hoá."""
    if kind == "scan":
        _str(data, "barcode", max_len=64)
        action = data.get("action", "ADD")
        if action not in SCAN_ACTIONS:
            raise ContractError(f"data.action phải thuộc {SCAN_ACTIONS}")
        data = {**data, "action": action}
    elif kind == "telemetry":
        _num(data, "actual_weight", 0, 1_000_000)
        _num(data, "battery_percent", 0, 100)
        cs = data.get("cart_status")
        if cs is not None and cs not in CART_STATUS:
            raise ContractError(f"data.cart_status phải thuộc {CART_STATUS}")
    elif kind == "heartbeat":
        _num(data, "uptime_s", 0, 10**9, required=False)
    elif kind == "event":
        _str(data, "event_type", max_len=64)
    elif kind == "ack":
        _str(data, "command_id", max_len=64)
        if data.get("result") not in ("OK", "FAILED"):
            raise ContractError("data.result phải là OK hoặc FAILED")
    elif kind == "command":
        _str(data, "command_id", max_len=64)
        if data.get("command_type") not in COMMANDS:
            raise ContractError(f"data.command_type phải thuộc {COMMANDS}")
        if not isinstance(data.get("parameters", {}), dict):
            raise ContractError("data.parameters phải là object")
    return data


def decode_and_validate(kind: str, topic_cart_id: str, payload: bytes) -> dict:
    """Parse JSON + kiểm tra envelope, cart_id khớp topic, timestamp, data."""
    try:
        env = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ContractError(f"payload không phải JSON hợp lệ: {e}") from e
    if not isinstance(env, dict):
        raise ContractError("payload phải là JSON object")
    if env.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"schema_version phải là {SCHEMA_VERSION}")
    mid = env.get("message_id")
    if not isinstance(mid, str) or not mid.strip() or len(mid) > 64:
        raise ContractError("message_id phải là chuỗi không rỗng")
    if env.get("cart_id") != topic_cart_id:
        raise ContractError(f"cart_id trong payload ({env.get('cart_id')!r}) khác topic ({topic_cart_id!r})")
    parse_ts(env.get("timestamp"))
    data = env.get("data")
    if not isinstance(data, dict):
        raise ContractError("data phải là JSON object")
    env["data"] = validate_data(kind, data)
    return env
