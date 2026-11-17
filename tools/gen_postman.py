"""Sinh Postman collection + environment từ registry route (luôn khớp API thật).

    python -m tools.gen_postman
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from backend.api import routes as _r  # noqa: F401
from backend.api.registry import ROUTES

OUT = Path(__file__).resolve().parent.parent / "postman"
EXAMPLES = {
    "id": "1", "item_id": "1", "cart_id": "{{cart_id}}", "barcode": "8934588012341", "command_id": "{{command_id}}",
}
BODIES = {
    "SessionCreate": {"cart_id": "{{cart_id}}"},
    "CartCreate": {"cart_id": "CART_004", "name": "Xe phần cứng ESP32"},
    "ProductCreate": {"barcode": "8934588099999", "name": "Bánh quy bơ 100g", "price": 18000, "unit_weight": 100},
    "ProductUpdate": {"price": 20000, "active": True},
    "ItemAdd": {"barcode": "8934588012341", "quantity": 1},
    "LoginRequest": {"username": "{{admin_user}}", "password": "{{admin_password}}"},
}
TESTS = {
    "health": "pm.test('200', () => pm.response.to.have.status(200));",
    "create_session": ("pm.test('201', () => pm.response.to.have.status(201));\n"
                       "pm.collectionVariables.set('session_id', pm.response.json().id);\n"
                       "if (pm.response.json().token) pm.collectionVariables.set('customer_token', pm.response.json().token);"),
    "login": ("pm.test('200', () => pm.response.to.have.status(200));\n"
              "pm.collectionVariables.set('admin_token', pm.response.json().token);"),
}


def build():
    folders: dict[str, list] = {}
    for r in ROUTES:
        path = re.sub(r"\{(\w+):\w+\}", r"{\1}", r.path)
        segs = [re.sub(r"\{(\w+)\}", lambda m: "{{" + ("session_id" if m.group(1) == "id" and "sessions" in path else m.group(1)) + "}}", s)
                for s in path.strip("/").split("/")]
        raw = "{{base_url}}/" + "/".join(segs)
        headers = [{"key": "Content-Type", "value": "application/json"}] if r.body else []
        auth = {"type": "noauth"}
        if r.auth in ("session", "session_read"):
            auth = {"type": "bearer", "bearer": [{"key": "token", "value": "{{customer_token}}", "type": "string"}]}
        elif r.auth != "public":
            auth = {"type": "bearer", "bearer": [{"key": "token", "value": "{{admin_token}}", "type": "string"}]}
        item = {
            "name": f"{r.method} {path} – {r.summary}",
            "request": {
                "auth": auth,
                "method": r.method,
                "header": headers,
                "url": {"raw": raw, "host": ["{{base_url}}"], "path": segs,
                        "query": [{"key": n, "value": "", "disabled": True, "description": d} for n, _t, d in r.query]},
            },
        }
        if r.body:
            item["request"]["body"] = {"mode": "raw", "raw": json.dumps(BODIES[r.body.__name__], ensure_ascii=False, indent=2),
                                       "options": {"raw": {"language": "json"}}}
        if r.fn.__name__ in TESTS:
            item["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": TESTS[r.fn.__name__].split("\n")}}]
        folders.setdefault(r.tag, []).append(item)
    coll = {
        "info": {"name": "Smart Shopping Cart API", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                 "description": "Sinh tự động bằng tools/gen_postman.py. Khi bật đăng nhập: chạy 'POST /api/auth/login' (lưu admin_token) "
                                    "rồi 'POST /api/sessions' (lưu session_id + customer_token) trước các request khác."},
        "item": [{"name": tag, "item": items} for tag, items in folders.items()],
        "variable": [{"key": "session_id", "value": "1"}, {"key": "cart_id", "value": "CART_001"},
                     {"key": "command_id", "value": ""}, {"key": "item_id", "value": "1"},
                     {"key": "id", "value": "1"}, {"key": "barcode", "value": "8934588012341"},
                     {"key": "admin_token", "value": ""}, {"key": "customer_token", "value": ""}],
    }
    env = {"name": "Smart Cart – local", "values": [{"key": "base_url", "value": "http://localhost:8000", "enabled": True},
                                        {"key": "admin_user", "value": "admin", "enabled": True},
                                        {"key": "admin_password", "value": "", "type": "secret", "enabled": True}],
           "_postman_variable_scope": "environment"}
    return coll, env


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    c, e = build()
    (OUT / "SmartCart.postman_collection.json").write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "SmartCart.postman_environment.json").write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Đã ghi", OUT)
