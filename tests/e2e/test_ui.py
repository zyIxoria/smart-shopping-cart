"""E2E bằng Playwright (Chromium) trên UI thật: Backend + MQTT broker + Simulator đều chạy thật.

Ảnh chụp lưu ở docs/screenshots/ (dùng làm tài liệu & để rà soát giao diện bằng mắt).
"""
import os
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from simulator import scenarios as sc
from tests.conftest import wait_until

SHOTS = Path(__file__).resolve().parent.parent.parent / "docs" / "screenshots"
COLA, OREO = "8934588012341", "8935001700011"

pytestmark = pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "index.html").exists(),
    reason="chưa build frontend (cd frontend && npm run build)",
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser, stack):
    ctx = browser.new_context(viewport={"width": 1280, "height": 860}, locale="vi-VN", device_scale_factor=1)
    pg = ctx.new_page()
    pg.set_default_timeout(8000)
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.base = stack.api.base
    SHOTS.mkdir(parents=True, exist_ok=True)
    yield pg
    ctx.close()


def shot(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def test_customer_full_journey(page, stack):
    page.goto(page.base + "/customer")
    expect(page.get_by_role("heading", name="Chọn xe đẩy của bạn")).to_be_visible()
    expect(page.get_by_test_id("ws-status")).to_contain_text("Realtime")
    expect(page.get_by_test_id("cart-card-CART_001")).to_contain_text("Sẵn sàng")
    shot(page, "01_customer_chon_xe")

    page.get_by_test_id("choose-CART_001").click()
    expect(page.get_by_test_id("cart-id")).to_have_text("CART_001")
    expect(page.get_by_text("Giỏ hàng đang trống")).to_be_visible()
    wait_until(lambda: stack.carts["CART_001"].cart_status == "IN_USE")

    # Simulator quét -> giỏ hàng tự cập nhật qua WebSocket (không reload trang)
    stack.carts["CART_001"].scan(COLA)
    stack.carts["CART_001"].scan(COLA)
    stack.carts["CART_001"].scan(OREO)
    expect(page.get_by_test_id("item-row")).to_have_count(2)
    expect(page.get_by_test_id("total")).to_have_text("39.000 ₫")
    expect(page.get_by_test_id("item-count")).to_have_text("3 sản phẩm")
    expect(page.get_by_test_id("actual-weight")).to_have_text("847 g", timeout=6000)
    expect(page.get_by_test_id("expected-weight")).to_have_text("847 g")
    shot(page, "02_customer_gio_hang")

    # Mã lạ -> toast từ chối
    stack.carts["CART_001"].scan("0000000000000")
    expect(page.get_by_test_id("toast").first).to_contain_text("Không có sản phẩm")

    # Lệch cân -> widget hiển thị cảnh báo
    sc.weight_mismatch(stack.carts["CART_001"], 300)
    expect(page.get_by_test_id("alert-chip-WEIGHT_MISMATCH")).to_be_visible(timeout=6000)
    shot(page, "03_customer_canh_bao_lech_can")
    sc.fix_weight(stack.carts["CART_001"])
    expect(page.get_by_test_id("alert-chip-WEIGHT_MISMATCH")).to_have_count(0, timeout=6000)

    # Thanh toán
    page.get_by_test_id("checkout-btn").click()
    expect(page.get_by_test_id("confirm-total")).to_have_text("39.000 ₫")
    shot(page, "04_customer_xac_nhan_thanh_toan")
    page.get_by_test_id("confirm-checkout").click()
    expect(page.get_by_test_id("completed")).to_contain_text("Shopping Completed")
    expect(page.get_by_test_id("completed")).to_contain_text("Thank you!")
    expect(page.get_by_test_id("receipt-total")).to_have_text("39.000 ₫")
    shot(page, "05_customer_hoan_tat")
    page.get_by_test_id("done-close").click()
    expect(page.get_by_test_id("cart-card-CART_001")).to_contain_text("Sẵn sàng")
    assert not page.errors, page.errors


def test_customer_manual_add_remove_and_cancel(page, stack):
    page.goto(page.base + "/customer")
    page.get_by_test_id("choose-CART_002").click()
    page.get_by_text("Thêm sản phẩm thủ công").click()
    page.get_by_test_id("manual-barcode").fill(COLA)
    page.get_by_test_id("manual-add").click()
    expect(page.get_by_test_id("item-row")).to_have_count(1)
    page.get_by_role("button", name="Xoá Coca Cola lon 330ml").click()
    expect(page.get_by_test_id("item-row")).to_have_count(0)
    expect(page.get_by_test_id("checkout-btn")).to_be_disabled()
    page.once("dialog", lambda d: d.accept())
    page.get_by_test_id("cancel-btn").click()
    expect(page.get_by_test_id("cart-card-CART_002")).to_contain_text("Sẵn sàng")


def test_customer_cannot_pick_offline_or_locked_cart(page, stack):
    sc.drop_connection(stack.carts["CART_003"])
    stack.api.post("/api/carts/CART_002/lock")
    page.goto(page.base + "/customer")
    expect(page.get_by_test_id("choose-CART_003")).to_be_disabled(timeout=8000)
    expect(page.get_by_test_id("cart-card-CART_003")).to_contain_text("mất kết nối")
    expect(page.get_by_test_id("choose-CART_002")).to_be_disabled()
    expect(page.get_by_test_id("cart-card-CART_002")).to_contain_text("bị khoá")
    expect(page.get_by_test_id("choose-CART_001")).to_be_enabled()
    shot(page, "06_customer_xe_khong_kha_dung")


def test_locked_cart_shows_banner_and_blocks_checkout(page, stack):
    page.goto(page.base + "/customer")
    page.get_by_test_id("choose-CART_001").click()
    page.get_by_text("Thêm sản phẩm thủ công").click()
    page.get_by_test_id("manual-barcode").fill(OREO)
    page.get_by_test_id("manual-add").click()
    expect(page.get_by_test_id("item-row")).to_have_count(1)
    assert stack.api.post("/api/carts/CART_001/lock")[0] == 200
    expect(page.get_by_test_id("locked-banner")).to_be_visible(timeout=6000)
    expect(page.get_by_test_id("checkout-btn")).to_be_disabled()
    shot(page, "07_customer_xe_bi_khoa")
    stack.api.post("/api/carts/CART_001/unlock")
    expect(page.get_by_test_id("locked-banner")).to_have_count(0, timeout=6000)
    expect(page.get_by_test_id("checkout-btn")).to_be_enabled()


def test_admin_dashboard_realtime_alerts(page, stack):
    page.goto(page.base + "/admin")
    expect(page.get_by_test_id("stat-total")).to_have_text("3")
    expect(page.get_by_test_id("stat-online")).to_have_text("3")
    expect(page.get_by_test_id("stat-alerts")).to_have_text("0")
    shot(page, "08_admin_tong_quan")

    sc.low_battery(stack.carts["CART_002"], 12)
    expect(page.get_by_test_id("stat-alerts")).to_have_text("1", timeout=6000)
    expect(page.get_by_test_id("alert-bar")).to_contain_text("CART_002")
    expect(page.get_by_test_id("admin-cart-CART_002").get_by_test_id("alert-chip-LOW_BATTERY")).to_be_visible()
    expect(page.get_by_test_id("nav-alert-count")).to_have_text("1")

    sc.drop_connection(stack.carts["CART_003"])
    expect(page.get_by_test_id("stat-offline")).to_have_text("1", timeout=8000)
    expect(page.get_by_test_id("stat-alerts")).to_have_text("2")
    shot(page, "09_admin_canh_bao")

    page.get_by_test_id("filter-OFFLINE").click()
    expect(page.get_by_test_id("admin-cart-CART_003")).to_be_visible()
    expect(page.get_by_test_id("admin-cart-CART_001")).to_have_count(0)
    page.get_by_test_id("filter-ALL").click()

    sc.reconnect(stack.carts["CART_003"])
    sc.recharge(stack.carts["CART_002"])
    expect(page.get_by_test_id("stat-alerts")).to_have_text("0", timeout=8000)
    assert not page.errors, page.errors


def test_admin_alerts_page_filters(page, stack):
    sc.low_battery(stack.carts["CART_001"], 5)
    wait_until(lambda: stack.api.get("/api/alerts?status=ACTIVE")[1])
    page.goto(page.base + "/admin/alerts")
    expect(page.get_by_test_id("alert-row")).to_have_count(1)
    expect(page.get_by_test_id("alert-row")).to_contain_text("Pin yếu")
    page.get_by_test_id("filter-type").select_option("OFFLINE")
    expect(page.get_by_test_id("alert-row")).to_have_count(0)
    page.get_by_test_id("filter-type").select_option("ALL")
    sc.recharge(stack.carts["CART_001"])
    expect(page.get_by_test_id("alert-row")).to_have_count(0, timeout=6000)
    page.get_by_test_id("filter-status").select_option("RESOLVED")
    expect(page.get_by_test_id("alert-row")).to_have_count(1)
    shot(page, "10_admin_trang_canh_bao")


def test_admin_cart_detail_lock_unlock_and_charts(page, stack):
    page.goto(page.base + "/admin/carts/CART_001")
    expect(page.get_by_test_id("detail-title")).to_contain_text("CART_001")
    expect(page.get_by_test_id("chart-battery")).to_be_visible()
    wait_until(lambda: len(stack.api.get("/api/carts/CART_001/telemetry")[1]) >= 3)
    expect(page.get_by_test_id("chart-battery").locator("svg path").first).to_be_visible(timeout=8000)
    page.get_by_test_id("lock-toggle").click()
    page.get_by_test_id("lock-confirm").click()
    expect(page.get_by_test_id("cart-status")).to_have_text("Đã khoá", timeout=6000)
    assert stack.carts["CART_001"].cart_status == "LOCKED"
    shot(page, "11_admin_chi_tiet_xe")
    page.get_by_test_id("lock-toggle").click()
    page.get_by_test_id("lock-confirm").click()
    expect(page.get_by_test_id("cart-status")).to_have_text("Sẵn sàng", timeout=6000)
    assert stack.carts["CART_001"].cart_status == "AVAILABLE"


def test_admin_lock_disabled_when_offline(page, stack):
    sc.drop_connection(stack.carts["CART_003"])
    wait_until(lambda: stack.api.get("/api/carts/CART_003")[1]["connection_status"] == "OFFLINE", timeout=6)
    page.goto(page.base + "/admin/carts/CART_003")
    expect(page.get_by_test_id("lock-toggle")).to_be_disabled()


def test_unknown_routes_and_landing(page, stack):
    page.goto(page.base + "/")
    expect(page.get_by_test_id("go-customer")).to_be_visible()
    page.goto(page.base + "/khong-ton-tai")
    expect(page.get_by_role("heading", name="Không tìm thấy trang")).to_be_visible()
    page.goto(page.base + "/admin/carts/NOPE")
    expect(page.get_by_text("Không tìm thấy xe NOPE")).to_be_visible()
    page.goto(page.base + "/customer/cart/99999")
    expect(page.get_by_text("Không tìm thấy phiên mua hàng", exact=True)).to_be_visible()


def test_mobile_layout_has_no_horizontal_scroll(browser, stack):
    ctx = browser.new_context(viewport={"width": 390, "height": 800}, device_scale_factor=2, is_mobile=True)
    pg = ctx.new_page()
    for path in ("/customer", "/admin", "/admin/alerts"):
        pg.goto(stack.api.base + path)
        pg.wait_for_selector("[data-testid=ws-status]")
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), path
    pg.goto(stack.api.base + "/customer")
    pg.get_by_test_id("choose-CART_001").click()
    pg.wait_for_selector("[data-testid=status-widget]")
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    pg.screenshot(path=str(SHOTS / "12_mobile_gio_hang.png"))
    ctx.close()


def test_mock_mode_runs_without_backend_data(browser, stack):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.goto(stack.api.base + "/admin?mock=1")
    expect(pg.get_by_test_id("ws-status")).to_contain_text("mock")
    expect(pg.get_by_test_id("stat-total")).to_have_text("3")
    expect(pg.get_by_test_id("stat-alerts")).to_have_text("1")     # CART_003 pin 17% trong dữ liệu mock
    pg.goto(stack.api.base + "/customer?mock=0")
    ctx.close()


# ---------------------------------------------------------------- trang Simulator phần cứng
def sim_url(stack):
    return f"{stack.api.base}/simulator?sim=http://127.0.0.1:{stack.control.port}"


def test_simulator_page_drives_whole_system(page, stack):
    """Thao tác trên trang /simulator -> MQTT -> Backend -> UI khách & admin (mở ở 2 tab) cập nhật."""
    page.goto(sim_url(stack))
    expect(page.get_by_test_id("device-grid")).to_be_visible()
    expect(page.get_by_test_id("led-CART_001")).to_have_class("led led-on")
    expect(page.get_by_test_id("backend-view-CART_001")).to_contain_text("Online")
    expect(page.get_by_test_id("lcd-CART_001")).to_contain_text("MQTT       : CONNECTED")
    shot(page, "13_simulator_phan_cung")

    admin = page.context.new_page()
    admin.goto(page.base + "/admin")
    cust = page.context.new_page()
    cust.goto(page.base + "/customer")
    cust.get_by_test_id("choose-CART_001").click()
    expect(cust.get_by_test_id("cart-id")).to_have_text("CART_001")

    # Quét 2 lon Coca trên "phần cứng" -> giỏ hàng khách cập nhật
    expect(page.get_by_test_id("lcd-CART_001")).to_contain_text("TRANG THAI : IN_USE", timeout=6000)
    page.get_by_test_id("product-CART_001").select_option(COLA)
    page.get_by_test_id("scan-add-CART_001").click()
    expect(page.get_by_test_id("note-CART_001")).to_contain_text("Đã gửi")
    page.get_by_test_id("scan-add-CART_001").click()
    expect(cust.get_by_test_id("item-qty")).to_have_text("2")
    expect(cust.get_by_test_id("total")).to_have_text("24.000 ₫")
    expect(page.get_by_test_id("basket-CART_001")).to_contain_text("× 2")
    expect(page.get_by_test_id("lcd-CART_001")).to_contain_text("CAN        : 710 g")

    # Mã lạ -> báo từ chối cho khách
    page.get_by_test_id("scan-unknown-CART_001").click()
    expect(cust.get_by_test_id("toast").first).to_contain_text("Không có sản phẩm")

    # Vật lạ -> cảnh báo lệch cân ở khách & admin; bỏ vật lạ -> hết
    page.get_by_test_id("weight-add-CART_001").click()
    expect(cust.get_by_test_id("alert-chip-WEIGHT_MISMATCH")).to_be_visible(timeout=6000)
    expect(admin.get_by_test_id("stat-alerts")).to_have_text("1", timeout=6000)
    page.get_by_test_id("weight-fix-CART_001").click()
    expect(cust.get_by_test_id("alert-chip-WEIGHT_MISMATCH")).to_have_count(0, timeout=6000)

    # Pin yếu / sạc đầy
    page.get_by_test_id("battery-low-CART_002").click()
    expect(admin.get_by_test_id("admin-cart-CART_002").get_by_test_id("alert-chip-LOW_BATTERY")).to_be_visible(timeout=6000)
    page.get_by_test_id("battery-full-CART_002").click()
    expect(admin.get_by_test_id("stat-alerts")).to_have_text("0", timeout=6000)

    # Ngắt mạng -> LED đỏ, hệ thống thấy OFFLINE; kết nối lại -> phục hồi
    page.get_by_test_id("conn-CART_003").click()
    expect(page.get_by_test_id("led-CART_003")).to_have_class("led led-off")
    expect(page.get_by_test_id("backend-view-CART_003")).to_contain_text("Offline", timeout=8000)
    expect(admin.get_by_test_id("stat-offline")).to_have_text("1", timeout=8000)
    shot(page, "14_simulator_mat_mang")
    page.get_by_test_id("conn-CART_003").click()
    expect(page.get_by_test_id("backend-view-CART_003")).to_contain_text("Online", timeout=8000)

    # Thanh toán trên UI khách
    cust.get_by_test_id("checkout-btn").click()
    cust.get_by_test_id("confirm-checkout").click()
    expect(cust.get_by_test_id("completed")).to_contain_text("Shopping Completed")
    expect(page.get_by_test_id("lcd-CART_001")).to_contain_text("TRANG THAI : AVAILABLE", timeout=6000)
    assert not page.errors, page.errors


def test_simulator_page_shows_error_when_simulator_down(page, stack):
    page.goto(f"{stack.api.base}/simulator?sim=http://127.0.0.1:1")
    expect(page.get_by_test_id("sim-error")).to_contain_text("python -m simulator.main")
    expect(page.get_by_test_id("device-grid")).to_have_count(0)
