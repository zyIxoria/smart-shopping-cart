# Báo cáo Triển khai — Màn hình Mô phỏng Siêu thị 2D (Digital Twin)

## 1. Tổng quan
Màn hình **Mô phỏng Siêu thị 2D** (`/simulation`) được bổ sung vào ứng dụng React hiện có như một phần mở rộng trực quan (Digital Twin) của hệ thống **Smart Shopping Cart**, kết nối đồng bộ thời gian thực với:
- **Backend FastAPI & SQLite/PostgreSQL** (`/api/carts`, `/api/sessions`, `/api/alerts`, `/api/products`, `/ws`)
- **Python Smart Cart Simulator HTTP Control API** (`:8090`, `/sim/carts`, `/sim/catalog`, `/sim/carts/{id}/scan|battery|weight_offset|connection`)
- **MQTT Broker & WebSocket `/ws`** (`CART_UPDATED`, `ALERT_TRIGGERED`, `ALERT_RESOLVED`, `SCAN_REJECTED`, `COMMAND_ACK`, `CART_EVENT`, `CONNECTED`, `AUTHED`)

> **Phạm vi mô phỏng:** Tọa độ `(x, y)` và quỹ đạo di chuyển trong siêu thị 2D là vị trí mô phỏng Digital Twin trên Frontend (phục vụ quan sát hành vi và điều phối xe đẩy), không phải dữ liệu từ cảm biến định vị trong nhà vật lý. Mọi trạng thái pin, cân nặng, giỏ hàng, phiên mua sắm và cảnh báo đều đến từ Backend, Simulator và MQTT thật.

---

## 2. Kiến trúc & Files đã thêm / chỉnh sửa

| File | Vai trò |
| :--- | :--- |
| `frontend/src/simulation/floorPlan.js` | Định nghĩa bản đồ siêu thị SVG `1000×620`, 7 khu vực (`entrance`, `grocery`, `beverage`, `household`, `personal_care`, `checkout`, `exit`), 8 dãy kệ, 3 quầy thanh toán, đồ thị 18 điểm waypoint hành lang (`WAYPOINTS`, `EDGES`), vị trí đỗ không chồng lấn `initialSlotForIndex()` và thuật toán tìm đường `findPathWaypoints()` theo BFS tránh xuyên qua kệ hàng. |
| `frontend/src/simulation/SupermarketMap.jsx` | Component bản đồ SVG 2D tương tác: hỗ trợ zoom/pan chuột, hiển thị legend 5 trạng thái (`Online`, `Cảnh báo`, `Khoá`, `Offline`, `Vừa Checkout`), vẽ tuyến đường dự kiến (`polyline`), marker xe đẩy SVG tùy chỉnh `CartGlyph` với thông số `battery · weight · items`. |
| `frontend/src/simulation/SimulationPage.jsx` | Trang Cockpit `/simulation` gồm: thanh điều khiển chung (`Start`, `Pause`, `Reset Simulation`), KPI đội xe, danh sách đội xe bên trái, bản đồ 2D ở giữa với vòng lặp `requestAnimationFrame`, bảng thông số chi tiết xe + kịch bản IoT bên phải, và `Live Event Log` phía dưới. |
| `frontend/src/state/store.jsx` | Bổ sung `eventLog` và reducer `log_event` với hàm tóm tắt sự kiện WebSocket `summarizeEvent(ev)` (lọc giảm nhiễu các telemetry lặp giống hệt nhau). |
| `frontend/src/App.jsx` | Đăng ký route `/simulation` (bảo vệ qua `RequireStaff`), thêm card `Mô phỏng 2D` trên trang chủ `/`. |
| `frontend/src/admin/AdminLayout.jsx` | Thêm liên kết điều hướng `Mô phỏng 2D →` trên topbar quản trị. |
| `frontend/src/simulator/SimulatorPage.jsx` | Thêm liên kết điều hướng `Mô phỏng 2D →` trên topbar Simulator. |
| `frontend/src/styles.css` | Bổ sung layout responsive `.sim2d-*`, `.btn-ok`, và điều chỉnh `.landing-cards` hiển thị 4 card cân đối. |
| `frontend/dist/` | Bundle sản xuất được build lại bằng `node build.mjs` (`app.js`, `app.css`). |
| `tests/e2e/test_simulation_2d.py` | Bộ kiểm thử Playwright E2E trên Chromium kiểm chứng toàn bộ kịch bản 2D Digital Twin. |

---

## 3. Luồng tương tác & Dữ liệu

```
Người dùng thao tác trên /simulation
  ├── Click khu vực / Chọn "Di chuyển xe" ──► findPathWaypoints(BFS) ──► animation trên SVG
  ├── "Bắt đầu phiên" / "Checkout"       ──► REST Backend (/api/sessions...) ──► MQTT Command ──► Simulator
  ├── "Quét & Thêm" / "Bỏ 1 món" / "Mã lạ" ─► Simulator :8090 (/scan) ──► MQTT ──► Backend ──► WebSocket /ws
  └── "Pin 15%" / "Lệch cân" / "Ngắt mạng" ─► Simulator :8090 (/battery|/weight_offset|/connection)
                                                    │
                                                    ▼
                                         Backend Alert Engine & DB
                                                    │
                                                    ▼
                                WebSocket (/ws) ──► StoreProvider (carts, alerts, eventLog) ──► 2D Map & Inspector
```

---

## 4. Các tình huống đã hỗ trợ trực tiếp trên giao diện 2D
1. **Điều khiển chung:** `Start Simulation`, `Pause Simulation` (tạm dừng di chuyển SVG nhưng vẫn nhận WebSocket realtime), `Reset Simulation` (đưa toàn bộ xe về khu vực Lối vào, sạc 100%, cân chuẩn 0g, kết nối lại mạng và huỷ phiên còn mở nếu có).
2. **Di chuyển theo hành lang:** Click chọn xe trên bản đồ hoặc sidebar trái, sau đó click trực tiếp vào khu vực trên bản đồ hoặc chọn trong dropdown để xe di chuyển theo waypoint hành lang.
3. **Mua sắm & Thanh toán:** `Bắt đầu phiên`, chọn sản phẩm thực từ catalog, `Quét & Thêm` (tự mở phiên nếu chưa có và điều hướng xe tới khu vực kệ tương ứng), `Bỏ 1 món`, `Quét mã lạ` (`UNKNOWN_999999`), và `Checkout` (xe di chuyển tới Quầy thanh toán và chuyển màu xanh dương `Vừa Checkout`).
4. **Cảnh báo & Sự cố IoT:** `Pin 15%` / `Sạc 100%` + thanh trượt pin (`LOW_BATTERY`), `Lệch cân +250g` / `Cân chuẩn 0g` (`WEIGHT_MISMATCH`), `Ngắt mạng` / `Kết nối lại` (`OFFLINE`).
5. **Xử lý lỗi khi mất kết nối:** Khi Simulator (`:8090`) không chạy hoặc mất kết nối, UI hiển thị banner cảnh báo `Simulator chưa sẵn sàng`, vô hiệu hoá các nút phần cứng tương ứng và vẫn hiển thị trạng thái đội xe từ Backend.

---

## 5. Minh hoạ giao diện thực tế (Playwright Screenshots)
- `docs/2d-simulation/screenshots/01_sim2d_initial_map.png`: Toàn cảnh bản đồ siêu thị 2D, 3 xe tại Lối vào, thông tin chi tiết và bảng điều khiển.
- `docs/2d-simulation/screenshots/02_sim2d_shopping_in_progress.png`: Xe `CART_001` di chuyển tới khu vực `Đồ uống & Sữa`, quét 2 lon Coca Cola (`24.000 ₫`, `710 g`), Live Event Log cập nhật realtime.
- `docs/2d-simulation/screenshots/03_sim2d_alerts_active.png`: Cảnh báo `WEIGHT_MISMATCH` (`CART_001`) và `LOW_BATTERY` (`CART_002` pin 15% màu cam).
- `docs/2d-simulation/screenshots/04_sim2d_offline_state.png`: `CART_003` mất kết nối (`Offline`, cảnh báo `Mất kết nối`).
- `docs/2d-simulation/screenshots/05_sim2d_checkout_completed.png`: `CART_001` hoàn tất `Checkout` tại Quầy thanh toán (`Vừa Checkout`).
