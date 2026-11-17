"""Nạp dữ liệu mẫu: sản phẩm + 3 xe (idempotent)."""
from __future__ import annotations

import json
from pathlib import Path

from shared.contract import iso

DATA = Path(__file__).resolve().parent.parent.parent / "data"


def seed(db) -> dict:
    products = json.loads((DATA / "products_seed.json").read_text(encoding="utf-8"))
    carts = json.loads((DATA / "carts_seed.json").read_text(encoding="utf-8"))
    now = iso()
    added_p = added_c = 0
    with db.tx():
        for p in products:
            if not db.one("SELECT id FROM products WHERE barcode=?", (p["barcode"],)):
                db.insert(
                    "INSERT INTO products(barcode,name,price,unit_weight,image,active) VALUES(?,?,?,?,?,?)",
                    (p["barcode"], p["name"], p["price"], p["unit_weight"], p.get("image", ""), 1 if p.get("active", True) else 0),
                )
                added_p += 1
        for c in carts:
            if not db.one("SELECT cart_id FROM smart_carts WHERE cart_id=?", (c["cart_id"],)):
                db.insert(
                    "INSERT INTO smart_carts(cart_id,name,created_at,updated_at) VALUES(?,?,?,?)",
                    (c["cart_id"], c["name"], now, now),
                )
                added_c += 1
    return {"products": added_p, "carts": added_c}


if __name__ == "__main__":
    from backend.config import Settings
    from backend.database.db import Database

    s = Settings()
    d = Database.from_settings(s)
    d.init_schema()
    print(seed(d))
