"""E2E giao diện khi BẬT đăng nhập (AUTH_ENABLED=1): màn đăng nhập, vai trò viewer/admin, khách chỉ thấy phiên của mình."""
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

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


def new_page(browser, base):
    ctx = browser.new_context(viewport={"width": 1100, "height": 760}, locale="vi-VN")
    pg = ctx.new_page()
    pg.set_default_timeout(8000)
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.base = base
    return pg


def login(pg, user, pw):
    pg.fill("[data-testid=login-username]", user)
    pg.fill("[data-testid=login-password]", pw)
    pg.click("[data-testid=login-submit]")


def test_admin_requires_login_then_works_and_logout(browser, auth_stack):
    pg = new_page(browser, auth_stack.anon.base)
    pg.goto(pg.base + "/admin")
    expect(pg.locator("[data-testid=login-form]")).to_be_visible()
    SHOTS.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(SHOTS / "login.png"))
    login(pg, "admin", "sai-mat-khau")
    expect(pg.locator("[data-testid=login-error]")).to_have_text("Sai tên đăng nhập hoặc mật khẩu")
    pg.fill("[data-testid=login-password]", ADMIN_PW)
    pg.click("[data-testid=login-submit]")
    expect(pg.locator("[data-testid=user-chip]")).to_contain_text("Quản trị")
    expect(pg.locator("text=Tổng số xe")).to_be_visible()
    expect(pg.locator("[data-testid=nav-alerts]")).to_be_visible()
    # WebSocket đã xác thực: khoá xe từ trang chi tiết và thấy cập nhật realtime
    pg.goto(pg.base + "/admin/carts/CART_001")
    pg.click("[data-testid=lock-toggle]")
    pg.get_by_test_id("lock-confirm").click()
    expect(pg.get_by_test_id("cart-status")).to_have_text("Đã khoá", timeout=6000)       # sự kiện realtime tới trình duyệt đã xác thực
    assert auth_stack.admin.get("/api/carts/CART_001")[1]["cart_status"] == "LOCKED"
    pg.click("[data-testid=logout]")
    expect(pg.locator("[data-testid=login-form]")).to_be_visible()
    # tải lại trang vẫn phải đăng nhập (token đã bị thu hồi + xoá)
    pg.reload()
    expect(pg.locator("[data-testid=login-form]")).to_be_visible()
    assert not pg.errors, pg.errors


def test_viewer_cannot_lock(browser, auth_stack):
    pg = new_page(browser, auth_stack.anon.base)
    pg.goto(pg.base + "/admin/carts/CART_002")
    login(pg, "viewer", "View-Only-1")
    expect(pg.locator("[data-testid=user-chip]")).to_contain_text("Chỉ xem")
    expect(pg.locator("[data-testid=lock-toggle]")).to_be_disabled()
    pg.screenshot(path=str(SHOTS / "viewer.png"))


def test_customer_sees_only_own_session(browser, auth_stack):
    base = auth_stack.anon.base
    mine = new_page(browser, base)
    mine.goto(base + "/customer")
    mine.click("[data-testid=choose-CART_003]")
    mine.wait_for_url("**/customer/cart/*")
    sid = mine.url.rsplit("/", 1)[1]
    expect(mine.get_by_role("heading", name="Giỏ hàng")).to_be_visible()
    # tải lại: token nằm trong localStorage nên vẫn là phiên của mình
    mine.reload()
    expect(mine.get_by_role("heading", name="Giỏ hàng")).to_be_visible()

    other = new_page(browser, base)
    other.goto(base + "/customer")
    other.wait_for_selector("[data-testid=cart-select-grid]")
    wait_until(lambda: other.locator("[data-testid=cart-card-CART_003]").inner_text().count("IN_USE") or "Đang sử dụng" in other.locator("[data-testid=cart-card-CART_003]").inner_text(), msg="xe 3 đang dùng")
    expect(other.locator("[data-testid=choose-CART_003]")).to_be_disabled()
    expect(other.locator("[data-testid=cart-card-CART_003]")).to_contain_text("Xe đang được sử dụng")
    assert "Giỏ hiện tại" not in other.locator("[data-testid=cart-card-CART_003]").inner_text()   # không lộ số món/tiền
    other.goto(base + f"/customer/cart/{sid}")
    expect(other.locator("text=Không có quyền xem phiên này")).to_be_visible()
    other.screenshot(path=str(SHOTS / "stranger_blocked.png"))
