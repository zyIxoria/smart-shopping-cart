"""Tiện ích bảo mật dùng chung (chỉ thư viện chuẩn): băm mật khẩu, token ký HMAC, khoá thiết bị, ký message.

Ánh xạ tới tài liệu môn học (Chương 4 – OWASP IoT Top 10): xem docs/SECURITY.md.

  * hash_password / verify_password : PBKDF2-HMAC-SHA256 + salt ngẫu nhiên   (I2 – xác thực)
  * make_token / verify_token        : token ngắn hạn ký HMAC, không lưu phía server (I1/I2)
  * derive_cart_key                  : khoá riêng cho từng xe sinh từ khoá chủ (I2/I8)
  * sign_message / verify_message    : HMAC-SHA256 trên message MQTT (toàn vẹn + xác thực nguồn, I4)
  * top_level_spans                  : tách chuỗi gốc của `data` để ký/kiểm tra đúng từng byte
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

PBKDF2_PREFIX = "pbkdf2_sha256"
DEVICE_KEY_LABEL = b"smartcart/device-key/v1\x00"


class SecurityError(ValueError):
    pass


# --------------------------------------------------------------------------- base64url
def b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# --------------------------------------------------------------------------- mật khẩu
def _iterations() -> int:
    try:
        return max(1000, int(os.getenv("PBKDF2_ITERATIONS", "200000")))
    except ValueError:
        return 200000


def hash_password(password: str, iterations: int | None = None) -> str:
    """-> 'pbkdf2_sha256$<iter>$<salt>$<hash>' (salt/hash base64url)."""
    it = iterations or _iterations()
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, it)
    return f"{PBKDF2_PREFIX}${it}${b64e(salt)}${b64e(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        prefix, it, salt, want = stored.split("$")
        if prefix != PBKDF2_PREFIX:
            return False
        got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b64d(salt), int(it))
        return hmac.compare_digest(got, b64d(want))
    except Exception:  # noqa: BLE001 - chuỗi băm hỏng => không hợp lệ
        return False


# --------------------------------------------------------------------------- token
def make_token(secret: bytes, claims: dict, ttl_s: float, now: float | None = None) -> str:
    now = time.time() if now is None else now
    body = {**claims, "iat": int(now), "exp": int(now + ttl_s)}
    payload = b64e(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = b64e(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(secret: bytes, token: str, now: float | None = None) -> dict | None:
    """Trả claims nếu token đúng chữ ký và còn hạn; ngược lại None."""
    try:
        payload, sig = token.split(".")
        want = hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(want, b64d(sig)):
            return None
        claims = json.loads(b64d(payload))
        if not isinstance(claims, dict):
            return None
        if (time.time() if now is None else now) >= float(claims.get("exp", 0)):
            return None
        return claims
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- khoá thiết bị
def derive_cart_key(master: str | bytes, cart_id: str) -> bytes:
    """Khoá HMAC 32 byte riêng cho từng xe. Thiết bị chỉ giữ khoá của mình, không giữ khoá chủ."""
    m = master.encode("utf-8") if isinstance(master, str) else master
    return hmac.new(m, DEVICE_KEY_LABEL + cart_id.encode("utf-8"), hashlib.sha256).digest()


# --------------------------------------------------------------------------- ký message
def mac_input(message_id: str, cart_id: str, timestamp: str, kind: str, data_raw: str) -> bytes:
    """Chuỗi được ký. `kind` (loại topic) nằm trong chữ ký để một message scan không thể bị phát lại như command."""
    return "\n".join((message_id, cart_id, timestamp, kind, data_raw)).encode("utf-8")


def sign_message(key: bytes, message_id: str, cart_id: str, timestamp: str, kind: str, data_raw: str) -> str:
    return hmac.new(key, mac_input(message_id, cart_id, timestamp, kind, data_raw), hashlib.sha256).hexdigest()


def verify_message(key: bytes, sig: object, message_id: str, cart_id: str, timestamp: str, kind: str, data_raw: str) -> bool:
    if not isinstance(sig, str) or len(sig) != 64:
        return False
    want = sign_message(key, message_id, cart_id, timestamp, kind, data_raw)
    return hmac.compare_digest(want, sig.lower())


# --------------------------------------------------------------------------- tách JSON mức gốc
def _skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


def _skip_string(s: str, i: int) -> int:
    """s[i] == '"' -> vị trí ngay sau dấu nháy đóng."""
    i += 1
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return i + 1
        i += 1
    raise SecurityError("chuỗi JSON không đóng")


def _skip_value(s: str, i: int) -> int:
    if i >= len(s):
        raise SecurityError("thiếu giá trị JSON")
    c = s[i]
    if c == '"':
        return _skip_string(s, i)
    if c in "{[":
        depth = 0
        while i < len(s):
            c = s[i]
            if c == '"':
                i = _skip_string(s, i)
                continue
            if c in "{[":
                depth += 1
            elif c in "}]":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        raise SecurityError("JSON không cân bằng")
    while i < len(s) and s[i] not in ",}] \t\r\n":
        i += 1
    return i


def top_level_spans(text: str) -> dict[str, str]:
    """Với object JSON `{"a":..., "data":{...}}` trả về {khoá: chuỗi giá trị gốc} (đúng từng ký tự).

    Từ chối khoá trùng lặp ở mức gốc: kẻ tấn công không thể giấu hai `data` khác nhau.
    """
    i = _skip_ws(text, 0)
    if i >= len(text) or text[i] != "{":
        raise SecurityError("payload không phải JSON object")
    i += 1
    out: dict[str, str] = {}
    while True:
        i = _skip_ws(text, i)
        if i < len(text) and text[i] == "}":
            return out
        if i >= len(text) or text[i] != '"':
            raise SecurityError("khoá JSON không hợp lệ")
        j = _skip_string(text, i)
        key = json.loads(text[i:j])
        i = _skip_ws(text, j)
        if i >= len(text) or text[i] != ":":
            raise SecurityError("thiếu dấu ':'")
        i = _skip_ws(text, i + 1)
        j = _skip_value(text, i)
        if key in out:
            raise SecurityError(f"khoá trùng lặp: {key}")
        out[key] = text[i:j]
        i = _skip_ws(text, j)
        if i < len(text) and text[i] == ",":
            i += 1
