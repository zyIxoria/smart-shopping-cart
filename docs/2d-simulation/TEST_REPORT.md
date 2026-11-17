# Báo cáo Kiểm thử — Bản đồ Siêu thị 2D tích hợp Web Quản trị (`/admin`)

## 1. Phạm vi & Môi trường thực thi
- **Hệ điều hành:** Windows (`win32`, Python `3.13.0`, `pytest 9.1.1`)
- **Frontend Build:** `esbuild` (`node build.mjs` trong `frontend/`), output tại `frontend/dist/assets/app.js` (`330.2kb`) và `app.css` (`19.5kb`)
- **Trình duyệt E2E:** Playwright Chromium (thực thi trên Backend FastAPI + MQTT DevBroker + 3 xe Simulator + ControlServer HTTP `:8090` + WebSocket `/ws`)

---

## 2. Kết quả kiểm thử sau lần chỉnh sửa hợp nhất vào `/admin`

### A. Build Frontend (`cd frontend && node build.mjs`)
- **Trạng thái:** `PASS` (thoát mã `0`, thời gian `35ms`).

### B. Playwright E2E toàn giao diện (`python -m pytest tests/e2e -v`)
- **Kết quả:** **`24 passed, 0 failed`** trong `82.00s` (gồm 4 test Bản đồ 2D tích hợp + 13 test `test_ui.py` + 3 test `test_ui_auth.py` + 4 test `test_ui_manage.py`).

| Test Case (`tests/e2e/test_simulation_2d.py`) | Kịch bản kiểm chứng trên `/admin` | Trạng thái |
| :--- | :--- | :--- |
| `test_simulation_navigation_and_initial_map` | Trang `/` không còn tách card riêng (`go-simulation` = 0); `/admin` hiển thị đồng thời `stats`, `simulation-section`, `admin-cart-grid`, WebSocket `Realtime`, trạng thái `RUNNING`, đủ `CART_001..003` trên sidebar & SVG, không tràn ngang ở `1440×900`. | `PASS` |
| `test_simulation_select_move_and_pause_resume_reset` | Click chọn `CART_002` trực tiếp trên SVG, di chuyển tới `beverage`, kiểm tra `Pause Simulation` giữ nguyên vị trí, `Start Simulation` tiếp tục di chuyển tới `household`, `Reset Simulation` đưa xe về `Lối vào & Bãi xe`. | `PASS` |
| `test_simulation_full_business_and_iot_scenarios` | Chọn `CART_001` → `Bắt đầu phiên` → `Quét & Thêm` x2 Coca Cola (`24.000 ₫`, `2 món`, di chuyển tới `Đồ uống & Sữa`) → `Bỏ 1 món` (`12.000 ₫`) → `Quét mã lạ` (ghi nhận `SCAN_REJECTED`) → `Lệch cân +250g` (`WEIGHT_MISMATCH`) & `Pin 15%` trên `CART_002` (`LOW_BATTERY`) → khôi phục → `Ngắt mạng` / `Kết nối lại` trên `CART_003` → `Checkout` trên `CART_001` (`Vừa Checkout`, di chuyển tới `Quầy thanh toán`). | `PASS` |
| `test_simulation_handles_simulator_offline_gracefully` | Truy cập `/admin?sim=http://127.0.0.1:1`: hiển thị banner `Simulator chưa sẵn sàng`, giữ hiển thị xe từ Backend và vô hiệu các nút điều khiển phần cứng. | `PASS` |

### C. Unit & Integration toàn hệ thống (`python -m pytest tests/unit tests/integration -v`)
- **Kết quả:** **`116 passed, 16 skipped, 0 failed`** trong `229.93s`.
- Cộng gộp sau chỉnh sửa cuối: **`140 passed, 16 skipped, 0 failed`** (`24` E2E + `116` Unit/Integration).
- **16 test `SKIPPED`** thuộc nhóm biên dịch/chạy firmware C++ và Wokwi CLI chưa cài trình biên dịch native trên Windows (`tests/integration/test_wokwi_bridge.py::test_bridge_end_to_end`, `tests/unit/test_firmware_protocol.py` [8 tests], `tests/unit/test_wokwi_package.py` C++ syntax checks [7 tests]).

---

## 3. Kiểm tra bằng mắt (Visual Verification)
Đã mở kiểm tra trực tiếp ảnh chụp sau khi gộp vào `/admin` tại `docs/2d-simulation/screenshots/01_sim2d_initial_map.png`:
- Giao diện `/admin` hiển thị thống nhất: Topbar quản trị → `Tổng quan hệ thống` + KPI → thanh cảnh báo → **Bản đồ Siêu thị 2D** (Đội xe · SVG Floor Plan · Inspector + Điều khiển IoT) → Live Event Log & bộ lọc danh sách xe bên dưới; 3 xe `CART_001..003` đứng tách biệt rõ ràng tại Lối vào, không chồng nhãn hay tràn khung hình.
