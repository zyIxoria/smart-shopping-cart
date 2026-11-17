# Báo cáo Kiểm thử — Màn hình Mô phỏng Siêu thị 2D & Toàn hệ thống

## 1. Phạm vi & Môi trường thực thi
- **Hệ điều hành:** Windows (`win32`, Python `3.13.0`, `pytest 9.1.1`)
- **Frontend Build:** `esbuild` (`node build.mjs` trong `frontend/`), output tại `frontend/dist/assets/app.js` (`331.5kb`) và `app.css` (`19.7kb`)
- **Trình duyệt E2E:** Playwright Chromium (thực thi trên Backend FastAPI + MQTT DevBroker + 3 xe Simulator + ControlServer HTTP `:8090` + WebSocket `/ws`)

---

## 2. Kết quả kiểm thử sau lần chỉnh sửa cuối

### A. Build Frontend (`cd frontend && node build.mjs`)
- **Trạng thái:** `PASS` (thoát mã `0`, thời gian `44ms`).

### B. Playwright E2E — Mô phỏng Siêu thị 2D (`tests/e2e/test_simulation_2d.py`)
Chạy riêng cùng `tests/e2e/test_ui.py` (`python -m pytest tests/e2e/test_simulation_2d.py tests/e2e/test_ui.py -v`) và trong full suite (`python -m pytest tests -v`):

| Test Case | Kịch bản kiểm chứng | Trạng thái |
| :--- | :--- | :--- |
| `test_simulation_navigation_and_initial_map` | Link từ `/` (`go-simulation`), `/admin` (`nav-simulation`), truy cập `/simulation`, kết nối WebSocket `Realtime`, trạng thái `RUNNING`, hiển thị đủ `CART_001..003` ở sidebar & SVG, không tràn ngang ở `1440×900`. | `PASS` |
| `test_simulation_select_move_and_pause_resume_reset` | Click chọn `CART_002` trực tiếp trên SVG, điều hướng tới `beverage` qua dropdown, kiểm tra `Pause Simulation` giữ nguyên vị trí khi click zone trên bản đồ, `Start Simulation` tiếp tục di chuyển tới `household`, `Reset Simulation` đưa xe về `Lối vào & Bãi xe`. | `PASS` |
| `test_simulation_full_business_and_iot_scenarios` | Chọn `CART_001` → `Bắt đầu phiên` → `Quét & Thêm` x2 Coca Cola (`24.000 ₫`, `2 món`, tự di chuyển tới `Đồ uống & Sữa`) → `Bỏ 1 món` (`12.000 ₫`) → `Quét mã lạ` (ghi nhận `SCAN_REJECTED` ở Live Event Log) → `Lệch cân +250g` (`WEIGHT_MISMATCH`) & `Pin 15%` trên `CART_002` (`LOW_BATTERY`) → khôi phục pin/cân → `Ngắt mạng` & `Kết nối lại` trên `CART_003` (`OFFLINE`/`ONLINE`) → `Checkout` trên `CART_001` (`Vừa Checkout`, di chuyển tới `Quầy thanh toán`). | `PASS` |
| `test_simulation_handles_simulator_offline_gracefully` | Truy cập `/simulation?sim=http://127.0.0.1:1`: hiển thị banner `Simulator chưa sẵn sàng`, giữ hiển thị xe từ Backend và disable các nút phần cứng tương ứng. | `PASS` |

### C. Kiểm thử toàn hệ thống (`python -m pytest tests -v`)
- **Kết quả tổng:** **`140 passed, 16 skipped, 0 failed`** trong `316.41s`.
- Trong đó toàn bộ 13 bài test E2E giao diện cũ (`tests/e2e/test_ui.py`), phân quyền (`test_ui_auth.py`), quản trị (`test_ui_manage.py`), tích hợp API/MQTT/WebSocket (`tests/integration/*`) và unit test nghiệp vụ Backend/Simulator/MQTT/Wokwi (`tests/unit/*` trừ C++ native) đều **PASS**.
- **16 test `SKIPPED`** thuộc nhóm biên dịch/chạy firmware C++ / Wokwi CLI chưa cài trình biên dịch native trên môi trường Windows hiện tại:
  - `tests/integration/test_wokwi_bridge.py::test_bridge_end_to_end` (1 test)
  - `tests/unit/test_firmware_protocol.py` (8 tests)
  - `tests/unit/test_wokwi_package.py` C++ syntax checks (`test_main_cpp_syntax_sim_envs[standalone|sim|sim_bridge|wokwi_online]`, `test_main_cpp_syntax_real_env_and_secure`, `test_wokwi_web_sketch_syntax[standalone|online]`) (7 tests)

---

## 3. Kiểm tra bằng mắt (Visual Verification qua ảnh chụp Playwright)
Đã mở kiểm tra trực tiếp các ảnh chụp trong `docs/2d-simulation/screenshots/`:
- `01_sim2d_initial_map.png`: 3 xe đứng tách biệt gọn gàng tại khu vực `Lối vào & Bãi xe`, không chồng nhãn; dropdown hiển thị đúng giá & khối lượng (`Coca Cola lon 330ml (12.000 ₫ · 355g)`).
- `02_sim2d_shopping_in_progress.png`: `CART_001` hiển thị tại `Đồ uống & Sữa` với `100% · 710g · 2 món`, `Live Event Log` cập nhật `CART_UPDATED` theo thời gian thực.
- `03_sim2d_alerts_active.png`: `CART_002` đổi màu cam cảnh báo pin `15%`, log ghi nhận `ALERT_TRIGGERED` cho `LOW_BATTERY` và `WEIGHT_MISMATCH`.
- `04_sim2d_offline_state.png`: `CART_003` đổi màu xám `Offline` và hiển thị chip `Mất kết nối`.
- `05_sim2d_checkout_completed.png`: `CART_001` đổi màu xanh dương `Vừa Checkout` tại `Quầy thanh toán`.
