# KẾ HOẠCH TRIỂN KHAI MÀN HÌNH MÔ PHỎNG SIÊU THỊ 2D TƯƠNG TÁC (2D SUPERMARKET DIGITAL TWIN)

## 1. Kết quả khảo sát kiến trúc & mã nguồn hiện tại

### 1.1. Công nghệ & Tổ chức mã nguồn
- **Frontend:** React 19 (`react`, `react-dom`), đóng gói qua `esbuild` (`frontend/build.mjs`), CSS thuần với biến thiết kế trong `frontend/src/styles.css`. Routing tối giản qua `frontend/src/router.jsx` và `frontend/src/App.jsx`. Quản lý trạng thái toàn cục bằng React Context + `useReducer` trong `frontend/src/state/store.jsx`.
- **Backend:** **FastAPI** (`backend/api/app.py`, `APIRouter`, Swagger UI `/docs`, ReDoc `/redoc`), WebSocket tích hợp trực tiếp tại `/ws` trên cổng `8000` (qua `Hub.publish()` + `Hub.project()`), xử lý nghiệp vụ tại `backend/services/*` (`carts.py`, `sessions.py`, `alerts.py`, `commands.py`, `ingest.py`).
- **Database:** Dual-Engine (`backend/database/db.py`) hỗ trợ PostgreSQL 16 (`schema_postgres.sql`) và SQLite WAL (`schema.sql`) với 7 bảng: `products`, `smart_carts`, `shopping_sessions`, `cart_items`, `device_telemetry`, `alerts`, `cart_commands`.
- **MQTT & Gateway:** 6 topics chuẩn `smartcart/{cart_id}/{scan|event|telemetry|heartbeat|command|ack}` trong `shared/contract.py`; tiêu thụ bởi `backend/mqtt/gateway.py` (HMAC, Clock Skew 300s, LRU Dedupe 2000) và `HeartbeatMonitor` (quét 2s/lần, timeout 15s).
- **Python Smart Cart Simulator:** `simulator/cart/__init__.py` (`SmartCart`) chạy mặc định 3 xe (`CART_001`, `CART_002`, `CART_003`), có cân nặng nhiễu Gauss ±3g, tụt pin 0.2%/phút, Offline Queue FIFO ≤ 50, và máy chủ điều khiển HTTP `ControlServer` (`:8090` trong `simulator/control.py`) hỗ trợ Bearer token `SIM_CONTROL_TOKEN`.

### 1.2. Dữ liệu hiện có & Dữ liệu còn thiếu

| Nhóm dữ liệu | Hiện có trong hệ thống | Nguồn cung cấp thực tế | Thiếu / Cần bổ sung ở tầng mô phỏng |
|---|---|---|---|
| **Danh sách xe & Trạng thái** | `cart_id`, `name`, `cart_status`, `connection_status`, `battery_percent`, `current_weight`, `last_seen`, `active_alerts`, `session` | `GET /api/carts` + WebSocket `CART_UPDATED` + `simApi.carts()` (`:8090`) | Chưa có toạ độ `(x, y)` trên bản đồ 2D siêu thị |
| **Giỏ hàng & Phiên mua** | `items[]`, `item_count`, `total_amount`, `expected_weight`, `actual_weight`, `status` | `GET /api/sessions/{id}` / `GET /api/carts/{id}/session` | Cần tải chi tiết phiên của xe đang chọn khi có `session.id` |
| **Danh mục sản phẩm** | `barcode`, `name`, `price`, `unit_weight` | `simApi.catalog()` / `GET /api/products` | — |
| **Sự kiện & Cảnh báo** | `ALERT_TRIGGERED`, `ALERT_RESOLVED`, `CART_UPDATED`, `SCAN_REJECTED`, `COMMAND_ACK`, `CART_EVENT`, `sim.log` | WebSocket `/ws` + `simApi.carts()[i].log` | Cần lưu danh sách `eventLog` gần nhất trong `StoreProvider` |
| **Vị trí & Tuyến đường 2D** | Chưa có (đề tài không gắn cảm biến định vị vật lý) | Cần thiết kế tầng **Virtual Spatial Twin** tách biệt hoàn toàn khỏi telemetry cảm biến | Graph lối đi siêu thị, thuật toán BFS tránh xuyên kệ hàng, chuyển động mượt `requestAnimationFrame` |

---

## 2. Thiết kế giao diện & Trải nghiệm (`Supermarket Simulation`)

### 2.1. Bố cục tổng thể (Digital Twin Cockpit)
Trang mới được gắn tại đường dẫn **`/simulation`** (`Supermarket Simulation`), thiết kế theo phong cách **Modern Smart Retail / IoT Digital Twin** với tông màu kỹ thuật sắc nét:
1. **Header Bar:** Tên màn hình (`Supermarket Simulation · Digital Twin`), trạng thái WebSocket realtime (`WsIndicator`), trạng thái mô phỏng (`RUNNING` / `PAUSED`), nút điều khiển chung (**Start**, **Pause**, **Reset**) và liên kết nhanh sang `/admin`, `/customer`, `/simulator`.
2. **Sidebar Trái (Fleet List):** Danh sách toàn bộ xe từ Backend/Simulator hiển thị trạng thái kết nối, trạng thái hoạt động, pin, cân nặng, số món và vị trí khu vực hiện tại trên bản đồ. Click chọn xe tức thì không reload trang.
3. **Khu vực Trung tâm (Bản đồ Siêu thị 2D SVG Tương tác):**
   - Bản đồ nhìn từ trên xuống (`1000 × 620` SVG viewBox) gồm:
     * **Entrance / Cart Bay** (Khu đỗ xe đẩy & Lối vào)
     * **4 Khu kệ hàng có nhãn phân loại & tỷ lệ chuẩn:** `Grocery` (Thực phẩm khô), `Beverage` (Đồ uống & Sữa), `Household` (Gia dụng), `Personal Care` (Chăm sóc cá nhân)
     * **Checkout Counters 1–3** (Quầy thanh toán) và **Exit Gate** (Lối ra)
   - Hỗ trợ **Zoom (`+` / `-` / `Reset`)** và **Pan (kéo chuột)** trên bản đồ.
   - **Tuyến đường & Chuyển động:** Đồ thị lối đi (`waypoints`) nằm hoàn toàn trên hành lang, tuyệt đối **không đi xuyên qua kệ hàng**. Khi điều hướng xe đến khu vực mới, BFS tìm đường ngắn nhất, vẽ đường dẫn nét đứt và di chuyển xe mượt mà qua `requestAnimationFrame`.
   - **Biểu tượng & Màu sắc trạng thái xe (SVG vector, không dùng emoji):**
     * **Online bình thường (`AVAILABLE` / `IN_USE`):** Xanh lá (`#059669`)
     * **Cảnh báo (`LOW_BATTERY`, `WEIGHT_MISMATCH`, hoặc có `offline_queue > 0`):** Vàng/Cam (`#d97706`) kèm vòng xung cảnh báo
     * **Offline / Khoá (`OFFLINE` / `LOCKED`):** Đỏ/Xám (`#dc2626` / `#64748b`)
     * **Vừa Checkout hoàn tất (`COMPLETED`):** Xanh dương (`#0284c7`)
4. **Sidebar Phải (Chi tiết xe & Simulation Controls):**
   - **Thông tin xe đang chọn:** Cart ID, Connection Status, Cart Status, Battery %, Current Weight vs Expected Weight, Items count, Session ID, Total Amount, Last Heartbeat, Active Alerts và danh sách sản phẩm thực tế trong giỏ.
   - **Bảng điều khiển theo từng xe & Kịch bản IoT (gọi API/Simulator thật):**
     * **Di chuyển xe (`Move Cart`):** Chọn khu vực đích (`Entrance`, `Grocery`, `Beverage`, `Household`, `Personal Care`, `Checkout`) hoặc click trực tiếp vào khu vực trên bản đồ để xe di chuyển tới khu vực đó.
     * **Tình huống thiết bị:** Thanh trượt & nút nhanh `Change Battery Level` (`15% Pin yếu` / `100% Đầy`), `Simulate Weight Change` (`+250g lệch cân` / `0g cân chuẩn`), `Trigger Offline` / `Trigger Reconnect`.
     * **Kịch bản nghiệp vụ:** `Start Session` (nếu chưa có phiên), `Scan Product / Add Item`, `Remove Item`, `Scan Unknown Barcode`, `Checkout`.
5. **Thanh dưới (Live Event Log):** Hiển thị luồng sự kiện thật từ WebSocket `/ws` và kết quả thao tác Simulator kèm thời gian, mã xe và loại sự kiện.

---

## 3. Kế hoạch kết nối dữ liệu & Phạm vi thay đổi

### 3.1. Nguyên tắc phân tách ranh giới dữ liệu
- **Vị trí `(x, y)` và lộ trình trên bản đồ 2D:** Là dữ liệu mô phỏng không gian ở tầng hiển thị Digital Twin trên Frontend (lưu trạng thái vị trí/tuyến đường từng `cart_id`, được gắn nhãn rõ ràng là *Vị trí mô phỏng 2D*), hoàn toàn **không** giả mạo thành dữ liệu cảm biến định vị vật lý.
- **Trạng thái IoT, giỏ hàng, pin, cân, cảnh báo:** 100% lấy từ luồng thật **Simulator (`:8090`) → MQTT → Backend FastAPI (`:8000`) → Database → WebSocket (`/ws`) → Frontend**. Không giả lập thành công trên UI khi Backend hoặc Simulator bị lỗi/ngắt kết nối.

### 3.2. Danh sách file dự kiến tạo / chỉnh sửa
1. **[Tạo mới]** `docs/2d-simulation/IMPLEMENTATION_PLAN.md` (tài liệu này).
2. **[Chỉnh sửa]** `frontend/src/state/store.jsx`: Lưu `eventLog` các sự kiện WebSocket nhận được để màn hình mô phỏng hiển thị log realtime.
3. **[Tạo mới]** `frontend/src/simulation/floorPlan.js`: Định nghĩa toạ độ khu vực siêu thị 2D, kích thước kệ hàng, mạng lưới điểm nút hành lang (`waypoints`) và thuật toán tìm đường ngắn nhất BFS (tránh va chạm kệ).
4. **[Tạo mới]** `frontend/src/simulation/SupermarketMap.jsx`: Thành phần SVG bản đồ siêu thị 2D tương tác, hỗ trợ zoom/pan, click chọn khu vực đích, hiển thị tuyến đường và biểu tượng xe đẩy SVG cập nhật trạng thái realtime.
5. **[Tạo mới]** `frontend/src/simulation/SimulationPage.jsx`: Trang `Supermarket Simulation` hoàn chỉnh gồm Header, Fleet Sidebar, Bản đồ 2D, Panel Chi tiết xe + Simulation Controls và Live Event Log.
6. **[Chỉnh sửa]** `frontend/src/App.jsx`, `frontend/src/admin/AdminLayout.jsx`, `frontend/src/simulator/SimulatorPage.jsx`, `frontend/src/styles.css`: Gắn route `/simulation`, nút điều hướng rõ ràng từ Landing / Admin / Simulator và CSS layout cho Digital Twin.
7. **[Tạo mới]** `tests/e2e/test_simulation_2d.py`: Bộ kiểm thử E2E bằng Playwright Chromium kiểm chứng toàn bộ 10 hạng mục mục tiêu (truy cập, chọn xe, di chuyển trên bản đồ, scan/add/remove, weight mismatch alert, low battery alert, offline/reconnect, checkout, start/pause/reset, mất kết nối).
8. **[Tạo mới]** `docs/2d-simulation/IMPLEMENTATION_REPORT.md` và `docs/2d-simulation/TEST_REPORT.md` kèm ảnh chụp màn hình Playwright thực tế.

### 3.3. Rủi ro tương thích & Cách phòng tránh
- **Rủi ro 1:** Simulator (`:8090`) chưa chạy trong khi Backend (`:8000`) đang chạy → **Giải pháp:** Hiển thị banner cảnh báo rõ ràng, vẫn hiển thị danh sách xe và telemetry thực từ Backend, vô hiệu hoá các nút thao tác phần cứng Simulator thay vì giả lập kết quả.
- **Rủi ro 2:** Quét sản phẩm khi xe đang ở trạng thái `AVAILABLE` (chưa mở phiên) → **Giải pháp:** Backend sẽ từ chối với `NO_ACTIVE_SESSION`; cung cấp nút rõ ràng `Mở phiên` (gọi `POST /api/sessions`) và tuỳ chọn tự động mở phiên trước khi `Add Item` nếu người dùng nhấn kịch bản mua nhanh (nhưng luôn gọi `POST /api/sessions` thật và chờ xe nhận `START_SESSION`).
- **Rủi ro 3:** Không phá vỡ bất kỳ test cũ nào (`136 passed`) → **Giải pháp:** Không đổi contract API, không đổi `data-testid` của các trang cũ, chạy lại toàn bộ `pytest tests` sau khi hoàn thành.
