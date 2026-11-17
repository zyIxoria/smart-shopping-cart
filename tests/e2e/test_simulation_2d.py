"""E2E tests (Playwright Chromium) cho màn hình Mô phỏng Siêu thị 2D (/simulation).

Chạy trên stack thật: Backend FastAPI + MQTT DevBroker + Simulator + ControlServer + WebSocket.
Ảnh chụp giao diện thực tế lưu tại docs/2d-simulation/screenshots/.
"""
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.conftest import wait_until

SHOTS = Path(__file__).resolve().parent.parent.parent / "docs" / "2d-simulation" / "screenshots"
COLA = "8934588012341"

pytestmark = pytest.mark.skipif(
    not (Path(__file__).resolve().parent.parent.parent / "frontend" / "dist" / "index.html").exists(),
    reason="chưa build frontend (cd frontend && node build.mjs)",
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser, stack):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="vi-VN", device_scale_factor=1)
    pg = ctx.new_page()
    pg.set_default_timeout(9000)
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.base = stack.api.base
    SHOTS.mkdir(parents=True, exist_ok=True)
    yield pg
    ctx.close()


def sim2d_url(stack, sim_override=None):
    sim_base = sim_override or f"http://127.0.0.1:{stack.control.port}"
    return f"{stack.api.base}/simulation?sim={sim_base}"


def shot(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def test_simulation_navigation_and_initial_map(page, stack):
    """Truy cập từ Landing & Admin topbar -> hiển thị đủ 3 xe trên bản đồ 2D và fleet sidebar."""
    page.goto(page.base + "/")
    expect(page.get_by_test_id("go-simulation")).to_be_visible()

    page.goto(page.base + "/admin")
    expect(page.get_by_test_id("nav-simulation")).to_be_visible()

    page.goto(sim2d_url(stack))
    expect(page.get_by_test_id("ws-status")).to_contain_text("Realtime", timeout=6000)
    expect(page.get_by_test_id("sim-run-state")).to_contain_text("RUNNING")

    for cid in ("CART_001", "CART_002", "CART_003"):
        expect(page.get_by_test_id(f"fleet-item-{cid}")).to_be_visible()
        expect(page.get_by_test_id(f"map-cart-{cid}")).to_be_visible()

    # Không tràn ngang trên desktop 1440px
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    shot(page, "01_sim2d_initial_map")
    assert not page.errors, page.errors


def test_simulation_select_move_and_pause_resume_reset(page, stack):
    """Chọn xe trên SVG, di chuyển theo waypoint hành lang, Pause/Start và Reset hoạt động đúng."""
    page.goto(sim2d_url(stack))
    expect(page.get_by_test_id("map-cart-CART_002")).to_be_visible()

    # Click chọn CART_002 trực tiếp trên bản đồ SVG
    page.get_by_test_id("map-cart-CART_002").click()
    expect(page.get_by_test_id("inspector-cart-id")).to_have_text("CART_002")

    # Di chuyển CART_002 tới khu vực Đồ uống & Sữa
    page.get_by_test_id("select-target-zone").select_option("beverage")
    page.get_by_test_id("btn-move-cart").click()
    expect(page.get_by_test_id("inspector-panel")).to_contain_text("Đồ uống & Sữa", timeout=7000)

    # Pause -> ra lệnh di chuyển tới Gia dụng -> kiểm tra trạng thái PAUSED giữ nguyên vị trí
    page.get_by_test_id("btn-sim-pause").click()
    expect(page.get_by_test_id("sim-run-state")).to_contain_text("PAUSED")
    page.get_by_test_id("map-zone-household").click()
    page.wait_for_timeout(400)
    expect(page.get_by_test_id("inspector-panel")).to_contain_text("Đồ uống & Sữa")

    # Start -> tiếp tục di chuyển tới Gia dụng
    page.get_by_test_id("btn-sim-start").click()
    expect(page.get_by_test_id("sim-run-state")).to_contain_text("RUNNING")
    expect(page.get_by_test_id("inspector-panel")).to_contain_text("Gia dụng", timeout=7000)

    # Reset -> đưa xe về Lối vào & Bãi xe
    page.get_by_test_id("btn-sim-reset").click()
    expect(page.get_by_test_id("inspector-panel")).to_contain_text("Lối vào & Bãi xe", timeout=6000)
    assert not page.errors, page.errors


def test_simulation_full_business_and_iot_scenarios(page, stack):
    """Luồng IoT đầy đủ qua 2D UI: Start Session -> Scan Add/Remove -> Unknown Barcode -> Alerts -> Offline/Reconnect -> Checkout."""
    page.goto(sim2d_url(stack))
    expect(page.get_by_test_id("ws-status")).to_contain_text("Realtime", timeout=6000)
    page.get_by_test_id("fleet-item-CART_001").click()
    expect(page.get_by_test_id("inspector-cart-id")).to_have_text("CART_001")

    # 1. Start Session + Scan Add x2 + Scan Remove x1
    page.get_by_test_id("btn-start-session").click()
    expect(page.get_by_test_id("inspector-session")).not_to_contain_text("Chưa mở phiên", timeout=6000)
    wait_until(lambda: stack.carts["CART_001"].session_id is not None)

    page.get_by_test_id("select-product").select_option(COLA)
    page.get_by_test_id("btn-scan-add").click()
    expect(page.get_by_test_id("inspector-total")).to_have_text("12.000 ₫", timeout=6000)
    page.get_by_test_id("btn-scan-add").click()
    expect(page.get_by_test_id("inspector-total")).to_have_text("24.000 ₫", timeout=6000)
    expect(page.get_by_test_id("inspector-items")).to_contain_text("× 2")
    expect(page.get_by_test_id("map-cart-CART_001")).to_contain_text("2 món")
    expect(page.get_by_test_id("inspector-panel")).to_contain_text("Đồ uống & Sữa", timeout=7000)
    shot(page, "02_sim2d_shopping_in_progress")

    # Bỏ bớt 1 lon -> còn 12.000 đ
    page.get_by_test_id("btn-scan-remove").click()
    expect(page.get_by_test_id("inspector-total")).to_have_text("12.000 ₫", timeout=6000)

    # 2. Quét mã lạ -> toast & Live Event Log ghi nhận SCAN_REJECTED
    page.get_by_test_id("btn-scan-unknown").click()
    expect(page.get_by_test_id("live-event-log")).to_contain_text("SCAN_REJECTED", timeout=6000)

    # 3. Kích hoạt Lệch cân +250g trên CART_001 & Pin yếu 15% trên CART_002
    page.get_by_test_id("btn-weight-mismatch").click()
    expect(page.get_by_test_id("alert-badge-WEIGHT_MISMATCH")).to_be_visible(timeout=6000)

    page.get_by_test_id("fleet-item-CART_002").click()
    page.get_by_test_id("btn-low-battery").click()
    expect(page.get_by_test_id("alert-badge-LOW_BATTERY")).to_be_visible(timeout=6000)
    shot(page, "03_sim2d_alerts_active")

    # Khắc phục cả 2 cảnh báo
    page.get_by_test_id("btn-full-battery").click()
    expect(page.get_by_test_id("alert-badge-LOW_BATTERY")).to_have_count(0, timeout=6000)
    page.get_by_test_id("fleet-item-CART_001").click()
    page.get_by_test_id("btn-weight-reset").click()
    expect(page.get_by_test_id("alert-badge-WEIGHT_MISMATCH")).to_have_count(0, timeout=6000)

    # 4. Ngắt mạng & Kết nối lại trên CART_003
    page.get_by_test_id("fleet-item-CART_003").click()
    page.get_by_test_id("btn-trigger-offline").click()
    expect(page.get_by_test_id("inspector-panel")).to_contain_text("Offline", timeout=8000)
    shot(page, "04_sim2d_offline_state")
    page.get_by_test_id("btn-trigger-reconnect").click()
    expect(page.get_by_test_id("inspector-panel")).to_contain_text("Online", timeout=8000)

    # 5. Checkout CART_001 -> chuyển trạng thái Vừa Checkout & di chuyển tới Quầy thanh toán
    page.get_by_test_id("fleet-item-CART_001").click()
    page.get_by_test_id("btn-checkout").click()
    expect(page.get_by_test_id("inspector-session")).to_contain_text("Chưa mở phiên", timeout=6000)
    expect(page.get_by_test_id("fleet-item-CART_001")).to_contain_text("Vừa Checkout")
    expect(page.get_by_test_id("inspector-panel")).to_contain_text("Quầy thanh toán", timeout=7000)
    expect(page.get_by_test_id("live-event-log")).to_contain_text("CART_UPDATED")
    shot(page, "05_sim2d_checkout_completed")
    assert not page.errors, page.errors


def test_simulation_handles_simulator_offline_gracefully(page, stack):
    """Khi Simulator (:8090) không khả dụng, trang vẫn hiển thị xe từ Backend và hiện cảnh báo rõ ràng."""
    page.goto(sim2d_url(stack, sim_override="http://127.0.0.1:1"))
    expect(page.get_by_test_id("sim-error-banner")).to_be_visible(timeout=6000)
    expect(page.get_by_test_id("map-cart-CART_001")).to_be_visible()
    expect(page.get_by_test_id("btn-scan-add")).to_be_disabled()
