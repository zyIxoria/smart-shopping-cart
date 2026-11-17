"""Kiểm tra chéo: message do firmware (cartcore C++) dựng phải qua được contract Python,
và lệnh do Backend dựng phải được firmware hiểu + ACK đúng contract.

Cần g++; nếu không có thì bỏ qua (firmware không bắt buộc để chạy hệ thống mô phỏng).
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from shared import contract, security

FW = Path(__file__).resolve().parents[2] / "firmware"
pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="cần g++ để biên dịch cartcore")


@pytest.fixture(scope="module")
def tool(tmp_path_factory):
    out = tmp_path_factory.mktemp("fw") / "protocol_tool"
    subprocess.run(
        ["g++", "-std=c++11", "-Wall", "-Wextra", f"-I{FW/'lib/cartcore'}",
         str(FW / "lib/cartcore/cartcore.cpp"), str(FW / "lib/cartcore/cartsec.cpp"), str(FW / "tools/protocol_tool.cpp"), "-o", str(out)],
        check=True, capture_output=True, text=True)
    return str(out)


def _build(tool):
    res = subprocess.run([tool, "build"], check=True, capture_output=True, text=True)
    return [line.split("\t", 1) for line in res.stdout.splitlines()]


def test_firmware_messages_pass_backend_validation(tool):
    msgs = _build(tool)
    assert {k for k, _ in msgs} == {"heartbeat", "telemetry", "scan", "event", "ack"}
    for kind, payload in msgs:
        env = contract.decode_and_validate(kind, "CART_004", payload.encode("utf-8"))
        assert env["schema_version"] == 1
        # timestamp ISO 8601 UTC phân tích được
        assert contract.parse_ts(env["timestamp"]).year == 2026


def test_firmware_message_content(tool):
    by_kind = {}
    for kind, payload in _build(tool):
        by_kind.setdefault(kind, []).append(json.loads(payload)["data"])
    assert by_kind["telemetry"][0]["actual_weight"] == 842.5
    assert by_kind["telemetry"][0]["cart_status"] == "IN_USE"
    assert by_kind["scan"][1] == {"scan_id": "5d3c1f7a-0000-4000-8000-000000000002", "barcode": "ABC-123", "action": "REMOVE"}
    assert by_kind["event"][0]["description"] == 'Xe đang bị khoá "test"'    # escape + UTF-8 đúng
    assert [a["result"] for a in by_kind["ack"]] == ["OK", "FAILED"]


def _commands(tool, lines, cart="CART_004"):
    res = subprocess.run([tool, "command", cart], input="\n".join(lines) + "\n",
                         check=True, capture_output=True, text=True)
    return [l.split("\t") for l in res.stdout.splitlines()]


def _cmd(ctype, cid, params=None, cart="CART_004"):
    env = contract.envelope(cart, {"command_id": cid, "command_type": ctype, "parameters": params or {}})
    return contract.encode(env).decode("utf-8")


def test_firmware_understands_backend_commands_and_acks_validly(tool):
    lines = [
        _cmd("START_SESSION", "c1", {"session_id": 12}),
        _cmd("LOCK_CART", "c2"),
        _cmd("UNLOCK_CART", "c3"),
        _cmd("END_SESSION", "c4", {"session_id": 12}),
        _cmd("START_SESSION", "c5", {"session_id": 12}),
        _cmd("START_SESSION", "c5", {"session_id": 12}),   # trùng command_id -> replay
    ]
    rows = _commands(tool, lines)
    assert [r[0] for r in rows] == ["START_SESSION", "LOCK_CART", "UNLOCK_CART", "END_SESSION", "START_SESSION", "START_SESSION"]
    assert [r[3] for r in rows] == ["IN_USE", "LOCKED", "IN_USE", "AVAILABLE", "IN_USE", "IN_USE"]
    assert rows[0][2] == "12"
    for r in rows:
        ack = contract.decode_and_validate("ack", "CART_004", r[4].encode("utf-8"))
        assert ack["data"]["command_id"] == r[1]
        assert ack["data"]["result"] == "OK"


def test_firmware_rejects_foreign_or_garbage_commands(tool):
    rows = _commands(tool, [_cmd("LOCK_CART", "x", cart="CART_001"), "not json", "{}"])
    assert rows == [["REJECT"]] * 3


def test_firmware_acks_failed_for_start_without_session_id(tool):
    rows = _commands(tool, [_cmd("START_SESSION", "bad")])
    ack = contract.decode_and_validate("ack", "CART_004", rows[0][4].encode("utf-8"))
    assert ack["data"]["result"] == "FAILED"


# ----------------------------------------------------------------------------- chữ ký HMAC: C++ <-> Python
KEY = security.derive_cart_key("master-for-tests", "CART_004")


def test_cpp_hmac_matches_python_hmac(tool):
    for msg in ("", "a", "x" * 63, "x" * 64, "x" * 65, "Tiếng Việt – ký tự đa byte", "\n".join(["a"] * 40)):
        got = subprocess.run([tool, "hmac", KEY.hex(), msg], check=True, capture_output=True, text=True).stdout.strip()
        import hashlib, hmac as _h
        assert got == _h.new(KEY, msg.encode(), hashlib.sha256).hexdigest(), msg


def test_python_verifies_firmware_signed_messages(tool):
    res = subprocess.run([tool, "build", KEY.hex()], check=True, capture_output=True, text=True)
    msgs = [l.split("\t", 1) for l in res.stdout.splitlines()]
    assert len(msgs) == 8
    for kind, payload in msgs:
        contract.verify_payload(kind, KEY, payload.encode("utf-8"))                    # chữ ký C++ đúng với Python
        env = contract.decode_and_validate(kind, "CART_004", payload.encode("utf-8"))
        assert len(env["sig"]) == 64
        with pytest.raises(contract.SignatureError):
            contract.verify_payload(kind, security.derive_cart_key("master-for-tests", "CART_005"), payload.encode("utf-8"))
        wrong_kind = "ack" if kind != "ack" else "scan"
        with pytest.raises(contract.SignatureError):
            contract.verify_payload(wrong_kind, KEY, payload.encode("utf-8"))


def _signed_cmd(ctype, cid, params=None, cart="CART_004", key=KEY, ts=None):
    env = contract.envelope(cart, {"command_id": cid, "command_type": ctype, "parameters": params or {}}, timestamp=ts)
    return (contract.encode_signed(env, key, "command") if key else contract.encode(env)).decode("utf-8")


def test_firmware_verifies_backend_signed_commands(tool):
    now = int(contract.utcnow().timestamp())
    lines = [
        _signed_cmd("START_SESSION", "s1", {"session_id": 5}),
        _signed_cmd("LOCK_CART", "s2", key=None),                                      # không ký
        _signed_cmd("LOCK_CART", "s3", key=b"k" * 32),                                 # ký sai khoá
        _signed_cmd("LOCK_CART", "s4", key=security.derive_cart_key("master-for-tests", "CART_001")),   # khoá của xe khác
        _signed_cmd("LOCK_CART", "s5", ts="2020-01-01T00:00:00Z"),                     # ký đúng nhưng cũ
        _signed_cmd("LOCK_CART", "s6"),
    ]
    tampered = _signed_cmd("UNLOCK_CART", "s7").replace('"UNLOCK_CART"', '"LOCK_CART"')
    res = subprocess.run([tool, "command", "CART_004", KEY.hex(), str(now)], input="\n".join(lines + [tampered]) + "\n",
                         check=True, capture_output=True, text=True)
    out = [l.split("\t") for l in res.stdout.splitlines()]
    assert out[0][0] == "START_SESSION" and out[0][3] == "IN_USE"
    assert [o[0] for o in out[1:5]] == ["REJECT_UNSIGNED", "REJECT_SIG", "REJECT_SIG", "REJECT_STALE"]
    assert out[5][0] == "LOCK_CART" and out[5][3] == "LOCKED"                          # lệnh hợp lệ vẫn chạy
    assert out[6] == ["REJECT_SIG"]                                                    # sửa data sau khi ký bị phát hiện
    # ACK do firmware ký cũng qua được Backend
    ack = contract.decode_and_validate("ack", "CART_004", out[5][4].encode("utf-8"))
    contract.verify_payload("ack", KEY, out[5][4].encode("utf-8"))
    assert ack["data"]["result"] == "OK"
