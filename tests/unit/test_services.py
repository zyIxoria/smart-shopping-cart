"""Service layer với SQLite tạm, không MQTT/HTTP."""
import pytest

from backend.config import Settings
from backend.database.db import Database
from backend.database.seed import seed
from backend.realtime.hub import Hub
from backend.services import alerts as alert_svc
from backend.services import carts as cart_svc
from backend.services import ingest
from backend.services import sessions as sess
from backend.services.context import AppContext, LruSet
from backend.services.errors import ApiError
from shared import contract


class FakeGateway:
    def __init__(self):
        self.sent = []
        self.connected = True

    def publish_command(self, cart_id, command_id, command_type, parameters):
        self.sent.append((cart_id, command_type, parameters))
        return True


@pytest.fixture()
def ctx():
    s = Settings()
    s.db_path = ":memory:"
    db = Database(":memory:")
    db.init_schema()
    seed(db)
    c = AppContext(s, db, Hub(), FakeGateway())
    c.events = []
    c.hub.listeners.append(c.events.append)
    return c


def env(cart, kind, data):
    return contract.envelope(cart, data)


def online(ctx, cart="CART_001"):
    ingest.handle(ctx, "heartbeat", cart, env(cart, "heartbeat", {"uptime_s": 1}))


def test_seed_is_idempotent(ctx):
    assert seed(ctx.db) == {"products": 0, "carts": 0}
    assert ctx.db.one("SELECT COUNT(*) n FROM products")["n"] >= 12
    assert ctx.db.one("SELECT COUNT(*) n FROM smart_carts")["n"] == 3


def test_start_session_requires_online_and_available(ctx):
    with pytest.raises(ApiError) as e:
        sess.start_session(ctx, "CART_001")
    assert e.value.code == "CART_OFFLINE"
    online(ctx)
    s = sess.start_session(ctx, "CART_001")
    assert s["status"] == "ACTIVE" and cart_svc.get_cart_row(ctx, "CART_001")["cart_status"] == "IN_USE"
    assert ("CART_001", "START_SESSION", {"session_id": s["id"]}) in ctx.gateway.sent
    with pytest.raises(ApiError) as e:
        sess.start_session(ctx, "CART_001")
    assert e.value.code == "CART_NOT_AVAILABLE"


def test_one_active_session_per_cart_db_constraint(ctx):
    import sqlite3
    online(ctx)
    sess.start_session(ctx, "CART_001")
    with pytest.raises(sqlite3.IntegrityError):
        ctx.db.insert("INSERT INTO shopping_sessions(cart_id,status,started_at) VALUES('CART_001','ACTIVE','x')")


def test_items_merge_quantity_and_total(ctx):
    online(ctx)
    s = sess.start_session(ctx, "CART_001")
    sess.add_item(ctx, s["id"], barcode="8934588012341")
    v = sess.add_item(ctx, s["id"], barcode="8934588012341", quantity=2)
    assert len(v["items"]) == 1 and v["items"][0]["quantity"] == 3 and v["total_amount"] == 36000


def test_price_snapshot_survives_price_change(ctx):
    online(ctx)
    s = sess.start_session(ctx, "CART_001")
    sess.add_item(ctx, s["id"], barcode="8934588012341")
    ctx.db.execute("UPDATE products SET price=99999 WHERE barcode='8934588012341'")
    assert sess.checkout(ctx, s["id"])["total_amount"] == 12000


def test_checkout_is_atomic_on_failure(ctx, monkeypatch):
    online(ctx)
    s = sess.start_session(ctx, "CART_001")
    sess.add_item(ctx, s["id"], barcode="8934588012341")

    def boom(*a, **k):
        raise RuntimeError("lỗi giữa chừng")

    monkeypatch.setattr(cart_svc, "update_cart", boom)
    with pytest.raises(RuntimeError):
        sess.checkout(ctx, s["id"])
    monkeypatch.undo()
    assert ctx.db.one("SELECT status FROM shopping_sessions WHERE id=?", (s["id"],))["status"] == "ACTIVE"   # rollback


def test_cancel_session(ctx):
    online(ctx)
    s = sess.start_session(ctx, "CART_001")
    sess.add_item(ctx, s["id"], barcode="8934588012341")
    v = sess.cancel(ctx, s["id"])
    assert v["status"] == "COMPLETED" and v["total_amount"] == 0 and v["items"] == []
    assert cart_svc.get_cart_row(ctx, "CART_001")["cart_status"] == "AVAILABLE"


def test_duplicate_alert_not_created(ctx):
    assert alert_svc.raise_alert(ctx, "CART_001", "LOW_BATTERY", "x")
    assert alert_svc.raise_alert(ctx, "CART_001", "LOW_BATTERY", "x") is None
    assert len(alert_svc.resolve_alert(ctx, "CART_001", "LOW_BATTERY")) == 1
    assert alert_svc.raise_alert(ctx, "CART_001", "LOW_BATTERY", "again")      # sau khi resolve được tạo lại
    assert len(alert_svc.list_alerts(ctx, cart_id="CART_001")) == 2


def test_lru_set():
    s = LruSet(2)
    assert not s.seen("a") and s.seen("a")
    s.seen("b"); s.seen("c")
    assert not s.seen("a")       # "a" đã bị loại khỏi LRU


def test_delete_cart(ctx):
    online(ctx)
    s = sess.start_session(ctx, "CART_001")
    with pytest.raises(ApiError):
        cart_svc.delete_cart(ctx, "CART_001")
    sess.cancel(ctx, s["id"])
    cart_svc.delete_cart(ctx, "CART_001")
    assert not ctx.db.one("SELECT cart_id FROM smart_carts WHERE cart_id='CART_001'")
    assert any(ev["type"] == "CART_DELETED" and ev["cart_id"] == "CART_001" for ev in ctx.events)

