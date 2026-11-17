"""Sinh toàn bộ bí mật cho chế độ bảo mật (chạy MỘT lần, kết quả nằm trong ./secrets – đã .gitignore).

    python -m tools.provision                       # 3 xe CART_001..3, chứng chỉ cho localhost/127.0.0.1
    python -m tools.provision --carts CART_001,CART_007 --host 192.168.1.20 --host broker.local
    python -m tools.provision --add-cart CART_004   # thêm xe mới vào bộ bí mật đã có

Kết quả (xem docs/SECURITY.md):
  secrets/secure.env               biến môi trường cho Backend/Simulator (khoá chủ, mật khẩu, TLS)
  secrets/mqtt_users.json          tài khoản MQTT đã băm cho tools/dev_broker.py
  secrets/mosquitto/               passwd + acl + lệnh tạo file passwd cho Mosquitto thật
  secrets/tls/ca.crt, server.*     CA riêng + chứng chỉ broker (cần openssl)
  secrets/firmware/<CART>/cart_secrets.h   dán vào firmware/include/ của từng xe

Khoá thiết bị = HMAC(khoá chủ, cart_id): firmware chỉ giữ khoá của chính nó, KHÔNG giữ khoá chủ.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from shared import security

ROOT = Path(__file__).resolve().parent.parent


def _write(path: Path, text: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _pw(n: int = 18) -> str:
    return secrets.token_urlsafe(n)


def generate_tls(tls_dir: Path, hosts: list[str], days: int = 825) -> None:
    """CA riêng + chứng chỉ server có SAN. Cần lệnh `openssl`."""
    if not shutil.which("openssl"):
        raise RuntimeError("không tìm thấy lệnh `openssl` – cài openssl hoặc dùng --no-tls")
    tls_dir.mkdir(parents=True, exist_ok=True)
    san = ["DNS:localhost", "IP:127.0.0.1"]
    for h in hosts:
        san.append(("IP:" if h.replace(".", "").isdigit() else "DNS:") + h)
    ext = tls_dir / "san.cnf"
    ext.write_text(
        "[v3]\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\nsubjectAltName=" + ",".join(dict.fromkeys(san)) + "\n", encoding="utf-8")

    def run(*a):
        subprocess.run(a, check=True, cwd=tls_dir, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.crt",
        "-days", str(days * 2), "-subj", "/CN=SmartCart Dev CA", "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    run("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", "server.key", "-out", "server.csr",
        "-subj", "/CN=smartcart-broker")
    run("openssl", "x509", "-req", "-in", "server.csr", "-CA", "ca.crt", "-CAkey", "ca.key", "-CAcreateserial",
        "-out", "server.crt", "-days", str(days), "-extfile", "san.cnf", "-extensions", "v3")
    for f in ("server.csr", "san.cnf", "ca.srl"):
        (tls_dir / f).unlink(missing_ok=True)
    for f in ("ca.key", "server.key"):
        os.chmod(tls_dir / f, 0o600)


def _firmware_header(cart_id: str, key: bytes, mqtt_pw: str, ca_pem: str | None) -> str:
    ca = ""
    if ca_pem:
        body = "\\n\"\n    \"".join(ca_pem.strip().splitlines())
        ca = f'\n#define MQTT_TLS 1\nstatic const char MQTT_CA_PEM[] =\n    "{body}\\n";\n'
    return (
        f"// Sinh bởi tools/provision.py – KHÔNG commit file này.\n#pragma once\n"
        f'#define SECRETS_CART_ID "{cart_id}"   // main.cpp kiểm tra CART_ID khớp để khỏi nạp nhầm khoá của xe khác\n'
        f'#ifndef CART_ID\n#define CART_ID "{cart_id}"\n#endif\n'
        f'#define MQTT_USER "{cart_id}"\n#define MQTT_PASS "{mqtt_pw}"\n'
        f'#define CART_KEY_HEX "{key.hex()}"   // HMAC-SHA256 ký message (khoá riêng của xe này)\n'
        f"{ca}"
    )


def add_cart(out: Path, cart_id: str, state: dict, ca_pem: str | None) -> None:
    from shared.contract import CART_ID_RE
    if not CART_ID_RE.match(cart_id):
        raise ValueError(f"cart_id không hợp lệ: {cart_id}")
    pw = state["cart_passwords"].get(cart_id) or _pw()
    state["cart_passwords"][cart_id] = pw
    key = security.derive_cart_key(state["master_key"], cart_id)
    _write(out / "firmware" / cart_id / "cart_secrets.h", _firmware_header(cart_id, key, pw, ca_pem))


def write_outputs(out: Path, state: dict) -> None:
    ca_path = out / "tls" / "ca.crt"
    ca_pem = ca_path.read_text() if ca_path.exists() else None
    users = {
        "backend": {"password_hash": security.hash_password(state["backend_password"]), "role": "backend"},
        "simulator": {"password_hash": security.hash_password(state["sim_password"]), "role": "sim"},
    }
    for cid, pw in state["cart_passwords"].items():
        users[cid] = {"password_hash": security.hash_password(pw), "role": "cart"}
        add_cart(out, cid, state, ca_pem)
    _write(out / "mqtt_users.json", json.dumps(users, indent=2))
    root = state.get("topic_root", "smartcart")
    acl = [f"# Sinh bởi tools/provision.py\nuser backend\ntopic read {root}/+/scan\ntopic read {root}/+/event\n"
           f"topic read {root}/+/telemetry\ntopic read {root}/+/heartbeat\ntopic read {root}/+/ack\n"
           f"topic write {root}/+/command\n",
           f"user simulator\ntopic write {root}/+/scan\ntopic write {root}/+/event\ntopic write {root}/+/telemetry\n"
           f"topic write {root}/+/heartbeat\ntopic write {root}/+/ack\ntopic read {root}/+/command\n",
           f"# xe thật: tên đăng nhập = cart_id, chỉ được động vào topic của chính nó\n"
           f"pattern write {root}/%u/scan\npattern write {root}/%u/event\npattern write {root}/%u/telemetry\n"
           f"pattern write {root}/%u/heartbeat\npattern write {root}/%u/ack\npattern read {root}/%u/command\n"]
    _write(out / "mosquitto" / "acl", "\n".join(acl), 0o644)
    cmds = ["#!/bin/sh", "# Tạo file passwd cho Mosquitto (cần mosquitto_passwd; hoặc: docker run --rm -v $PWD:/w eclipse-mosquitto:2 ...)",
            'cd "$(dirname "$0")"', "rm -f passwd", "touch passwd"]
    allpw = {"backend": state["backend_password"], "simulator": state["sim_password"], **state["cart_passwords"]}
    for u, p in allpw.items():
        cmds.append(f"mosquitto_passwd -b passwd '{u}' '{p}'")
    cmds.append("chmod 0700 passwd")
    _write(out / "mosquitto" / "make_passwd.sh", "\n".join(cmds) + "\n", 0o700)
    env = [
        "# Sinh bởi tools/provision.py – KHÔNG commit. Nạp bằng: set -a; . secrets/secure.env; set +a",
        f"DEVICE_MASTER_KEY={state['master_key']}",
        f"TOKEN_SECRET={state['token_secret']}",
        f"ADMIN_USERNAME={state['admin_username']}",
        f"ADMIN_PASSWORD={state['admin_password']}",
        "AUTH_ENABLED=1", "REQUIRE_SIGNATURE=1",
        f"MQTT_BACKEND_USER=backend\nMQTT_BACKEND_PASS={state['backend_password']}",
        f"MQTT_SIM_USER=simulator\nMQTT_SIM_PASS={state['sim_password']}",
    ]
    if ca_pem:
        env += ["MQTT_TLS=1", f"MQTT_CA_FILE={ca_path.resolve()}", "MQTT_PORT=8883"]
    _write(out / "secure.env", "\n".join(env) + "\n")
    _write(out / "state.json", json.dumps(state, indent=2))


def provision(out: Path, carts: list[str], hosts: list[str] | None = None, tls: bool = True, force: bool = False,
              topic_root: str | None = None) -> dict:
    out = Path(out)
    state_file = out / "state.json"
    if state_file.exists() and not force:
        state = json.loads(state_file.read_text())
        for c in carts:
            state["cart_passwords"].setdefault(c, _pw())
    else:
        if state_file.exists():
            shutil.rmtree(out)
        state = {
            "master_key": secrets.token_hex(32), "token_secret": secrets.token_hex(32),
            "admin_username": "admin", "admin_password": _pw(12),
            "backend_password": _pw(), "sim_password": _pw(),
            "cart_passwords": {c: _pw() for c in carts},
            "topic_root": topic_root or os.getenv("MQTT_TOPIC_ROOT", "smartcart"),
        }
    if tls and not (out / "tls" / "ca.crt").exists():
        generate_tls(out / "tls", hosts or [])
    write_outputs(out, state)
    return state


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "secrets"))
    ap.add_argument("--carts", default="CART_001,CART_002,CART_003", help="danh sách cart_id, cách nhau bằng dấu phẩy")
    ap.add_argument("--add-cart", action="append", default=[], help="thêm xe vào bộ bí mật đã có")
    ap.add_argument("--host", action="append", default=[], help="tên/IP broker đưa vào chứng chỉ (lặp lại được)")
    ap.add_argument("--no-tls", action="store_true", help="không sinh chứng chỉ")
    ap.add_argument("--force", action="store_true", help="XOÁ bộ bí mật cũ và sinh lại (mọi xe phải nạp lại firmware)")
    a = ap.parse_args(argv)
    carts = a.add_cart or [c.strip() for c in a.carts.split(",") if c.strip()]
    out = Path(a.out)
    try:
        st = provision(out, carts, a.host, tls=not a.no_tls, force=a.force)
    except (RuntimeError, ValueError) as e:
        print("Lỗi:", e, file=sys.stderr)
        return 1
    print(f"Đã sinh bí mật vào {out}/")
    print(f"  Đăng nhập quản trị: {st['admin_username']} / {st['admin_password']}   (đổi bằng ADMIN_PASSWORD trong secure.env)")
    print(f"  Xe: {', '.join(st['cart_passwords'])}  -> firmware: {out}/firmware/<CART>/cart_secrets.h")
    print("  Chạy hệ thống bảo mật:  bash scripts/run_secure.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
