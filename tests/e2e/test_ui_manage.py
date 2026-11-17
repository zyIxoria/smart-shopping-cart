"""E2E: quản trị trên web – đăng ký xe (xe ảo/ESP32), huỷ phiên treo, quản lý sản phẩm. Bật đăng nhập (AUTH_ENABLED=1)."""
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from shared import contract
from shared.mqttlite import MqttClient
from tests.conftest import ADMIN_PW, wait_until

SHOTS = Path(__file__).resolve().parent.parent.parent / "docs" / "screenshots"
pytestmark = pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "index.html").exists(),
    reason="chưa build frontend",
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def admin_page(browser, st, path="/admin", user="admin", pw=ADMIN_PW):
    ctx = browser.new_context(viewport={"width": 1100, "height": 800}, locale="vi-VN")
    pg = ctx.new_page()
    pg.set_default_timeout(8000)
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.base = st.anon.base
    pg.goto(pg.base + path)
    pg.fill("[data-testid=login-username]", user)
    pg.fill("[data-testid=login-password]", pw)
    pg.click("[data-testid=login-submit]")
    expect(pg.locator("[data-testid=user-chip]")).to_be_visible()
    return pg


def test_register_virtual_cart_then_it_goes_online(browser, auth_stack):
    """Luồng xe ảo (Wokwi/ESP32): đăng ký mã xe trên web -> xe gửi heartbeat qua MQTT -> web thấy ONLINE."""
    st = auth_stack
    pg = admin_page(browser, st)
    pg.click("[data-testid=add-cart]")
    save = pg.get_by_test_id("cf-save")
    expect(save).to_be_disabled()
    pg.fill("[data-testid=cf-id]", "mã sai!")                       # ký tự không hợp lệ
    expect(save).to_be_disabled()
    pg.fill("[data-testid=cf-id]", "CART_001")                      # trùng xe có sẵn
    pg.click("[data-testid=cf-save]")
    expect(pg.get_by_test_id("cf-error")).to_contain_text("đã tồn tại")
    pg.fill("[data-testid=cf-id]", "WK_virtual")
    pg.fill("[data-testid=cf-name]", "Xe ảo Wokwi")
    SHOTS.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(SHOTS / "admin_dang_ky_xe.png"))
    pg.click("[data-testid=cf-save]")
    card = pg.get_by_test_id("admin-cart-WK_virtual")
    expect(card).to_be_visible()
    expect(card).to_contain_text("Offline")                          # chưa nhận tin nhắn nào
    assert st.admin.get("/api/carts/WK_virtual")[1]["connection_status"] == "OFFLINE"

    # "thiết bị ảo" gửi heartbeat + telemetry như firmware
    dev = MqttClient("virtual-dev", "127.0.0.1", st.broker.port)
    dev.start()
    try:
        wait_until(lambda: dev.connected, msg="thiết bị nối broker")
        def beat():
            dev.publish(contract.topic("WK_virtual", "heartbeat"), contract.encode(contract.envelope("WK_virtual", {"uptime_s": 5})))
            dev.publish(contract.topic("WK_virtual", "telemetry"), contract.encode(contract.envelope(
                "WK_virtual", {"actual_weight": 0, "battery_percent": 77, "cart_status": "AVAILABLE", "wifi_status": "CONNECTED", "mqtt_status": "CONNECTED"})))
        deadline = time.time() + 8
        while time.time() < deadline:
            beat()
            if st.admin.get("/api/carts/WK_virtual")[1]["connection_status"] == "ONLINE":
                break
            time.sleep(0.3)
        expect(card).to_contain_text("Online", timeout=6000)         # cập nhật realtime, không tải lại trang
        expect(card).to_contain_text("77%")
    finally:
        dev.stop()
    assert not pg.errors, pg.errors


def test_viewer_has_no_manage_buttons(browser, auth_stack):
    pg = admin_page(browser, auth_stack, user="viewer", pw="View-Only-1")
    expect(pg.get_by_test_id("add-cart")).to_have_count(0)
    pg.click("[data-testid=nav-products]")
    expect(pg.get_by_test_id("products-table")).to_be_visible()
    expect(pg.get_by_test_id("add-product")).to_have_count(0)
    expect(pg.locator("[data-testid^=edit-]")).to_have_count(0)


def test_admin_cancels_stuck_session(browser, auth_stack):
    st = auth_stack
    pg = admin_page(browser, st, "/admin/carts/CART_002")
    expect(pg.get_by_test_id("cancel-session")).to_have_count(0)    # chưa có phiên
    code, sess = st.anon.post("/api/sessions", {"cart_id": "CART_002"})
    assert code == 201
    st.anon.with_token(sess["token"]).post(f"/api/sessions/{sess['id']}/items", {"barcode": "8934588012341"})
    pg.reload()
    expect(pg.get_by_test_id("detail-session")).to_contain_text(f"#{sess['id']}")
    pg.click("[data-testid=cancel-session]")
    pg.click("[data-testid=cancel-session-confirm]")
    expect(pg.get_by_test_id("detail-session")).to_contain_text("Không có phiên đang diễn ra", timeout=6000)
    assert st.admin.get(f"/api/sessions/{sess['id']}")[1]["status"] != "ACTIVE"
    wait_until(lambda: st.admin.get("/api/carts/CART_002")[1]["cart_status"] == "AVAILABLE", msg="xe về sẵn sàng")


def test_product_management_flow(browser, auth_stack):
    st = auth_stack
    pg = admin_page(browser, st, "/admin/products")
    expect(pg.get_by_test_id("products-table")).to_contain_text("Coca Cola")
    pg.fill("[data-testid=product-search]", "coca")
    expect(pg.locator("[data-testid^=product-row-]")).to_have_count(1)
    pg.fill("[data-testid=product-search]", "")
    # thêm
    pg.click("[data-testid=add-product]")
    expect(pg.get_by_test_id("pf-save")).to_be_disabled()
    pg.fill("[data-testid=pf-barcode]", "8934588099999")
    pg.fill("[data-testid=pf-name]", "Bánh quy bơ 100g")
    pg.fill("[data-testid=pf-price]", "18000")
    pg.fill("[data-testid=pf-weight]", "100")
    pg.screenshot(path=str(SHOTS / "admin_them_san_pham.png"))
    pg.click("[data-testid=pf-save]")
    row = pg.get_by_test_id("product-row-8934588099999")
    expect(row).to_contain_text("Bánh quy bơ 100g")
    expect(row).to_contain_text("Đang bán")
    assert st.anon.get("/api/products/barcode/8934588099999")[1]["price"] == 18000     # khách thấy ngay
    # trùng mã vạch -> báo lỗi trong biểu mẫu
    pg.click("[data-testid=add-product]")
    pg.fill("[data-testid=pf-barcode]", "8934588099999")
    pg.fill("[data-testid=pf-name]", "Trùng")
    pg.fill("[data-testid=pf-price]", "1")
    pg.fill("[data-testid=pf-weight]", "1")
    pg.click("[data-testid=pf-save]")
    expect(pg.get_by_test_id("pf-error")).to_contain_text("đã có")
    pg.keyboard.press("Escape")
    # sửa giá
    pg.click("[data-testid=edit-8934588099999]")
    pg.fill("[data-testid=pf-price]", "20000")
    pg.click("[data-testid=pf-save]")
    expect(row).to_contain_text("20.000")
    assert st.anon.get("/api/products/barcode/8934588099999")[1]["price"] == 20000
    # ẩn -> khách không còn thấy; hiện lại
    pg.click("[data-testid=toggle-8934588099999]")
    expect(row).to_have_count(0)                                    # mặc định không hiện sản phẩm đã ẩn
    assert st.anon.get("/api/products/barcode/8934588099999")[0] == 404
    pg.check("[data-testid=show-hidden]")
    expect(row).to_contain_text("Đã ẩn")
    pg.click("[data-testid=toggle-8934588099999]")
    expect(row).to_contain_text("Đang bán")
    assert st.anon.get("/api/products/barcode/8934588099999")[0] == 200
    assert not pg.errors, pg.errors
