# Báo cáo Triển khai — Bản đồ Siêu thị 2D (Digital Twin) tích hợp vào Web Quản trị

## 1. Tổng quan
Chức năng **Bản đồ Siêu thị 2D (Supermarket Digital Twin)** được tích hợp trực tiếp vào màn hình **Quản trị (`/admin`)** thay vì tách thành trang riêng biệt, giúp người vận hành vừa xem KPI/cảnh báo tổng quan, vừa quan sát trực quan vị trí mô phỏng các xe đẩy và kích hoạt các kịch bản IoT trên cùng một giao diện web.

Kết nối thời gian thực giữ nguyên kiến trúc gốc:
- **Backend FastAPI & SQLite/PostgreSQL:** `/api/carts`, `/api/sessions`, `/api/alerts`, `/api/products`, `/ws`, cùng proxy cùng origin `/api/sim/status` và `/api/sim/carts/{cart_id}/{action}` giúp `/admin` giao tiếp ổn định với Simulator `:8090` mà không phát sinh lỗi CORS hoặc lỗi mạng trên trình duyệt khi Simulator tắt.
- **Python Smart Cart Simulator (`:8090`):** hỗ trợ cả proxy qua Backend lẫn ghi đè trực tiếp `?sim=http://...`.
- **WebSocket `/ws`:** cập nhật tức thì `CART_UPDATED`, `ALERT_TRIGGERED`, `ALERT_RESOLVED`, `SCAN_REJECTED`, `COMMAND_ACK`, `CART_EVENT`.

> **Phạm vi mô phỏng:** Tọa độ `(x, y)` và quỹ đạo di chuyển trong siêu thị 2D là vị trí mô phỏng Digital Twin trên Frontend, không phải dữ liệu từ cảm biến định vị vật lý.

---

## 2. Kiến trúc & Files đã thêm / chỉnh sửa

| File | Vai trò |
| :--- | :--- |
| `frontend/src/simulation/floorPlan.js` | Định nghĩa mặt bằng siêu thị SVG `1000×620` (7 khu vực, 8 dãy kệ, 3 quầy thanh toán, 18 điểm waypoint hành lang), vị trí đỗ không chồng nhãn `initialSlotForIndex()` và thuật toán tìm đường BFS `findPathWaypoints()`. |
| `frontend/src/simulation/SupermarketMap.jsx` | Component bản đồ SVG 2D tương tác (zoom/pan, legend 5 trạng thái, polyline tuyến đường, marker xe đẩy SVG tùy chỉnh `CartGlyph`). |
| `frontend/src/simulation/SupermarketSimulation.jsx` | Component Digital Twin nhúng trực tiếp trong `/admin`: thanh điều khiển `Start`/`Pause`/`Reset Simulation`, danh sách đội xe bên trái, bản đồ SVG với vòng lặp `requestAnimationFrame` ở giữa, Inspector + Điều khiển kịch bản IoT bên phải, và `Live Event Log` phía dưới. |
| `frontend/src/admin/Dashboard.jsx` | Nhúng `<SupermarketSimulation />` ngay dưới `alert-bar` trong trang `/admin`. |
| `frontend/src/state/store.jsx` | Bổ sung `eventLog` và reducer `log_event` ghi nhận sự kiện WebSocket theo thời gian thực. |
| `frontend/src/api/sim.js` | Hỗ trợ đồng thời proxy cùng origin `/api/sim/*` (`embeddedState()`) khi dùng trên `/admin` và URL trực tiếp khi có tham số `?sim=`. |
| `backend/schemas/models.py`, `backend/api/routes.py` | Bổ sung `SimAction`, `GET /api/sim/status` (`auth="staff"`) và `POST /api/sim/carts/{cart_id}/{action}` (`auth="admin"` với whitelist action). |
| `frontend/src/styles.css` | Style `.sim2d-embedded`, `.sim2d-cockpit` responsive gọn trong `.container.wide` (hỗ trợ cả desktop 1440px và mobile 390px không tràn ngang). |
| `frontend/dist/` | Bundle sản xuất build qua `node build.mjs`. |
| `tests/e2e/test_simulation_2d.py` | Bộ kiểm thử Playwright E2E kiểm chứng toàn bộ kịch bản 2D Digital Twin ngay trên `/admin`. |

---

## 3. Ảnh chụp giao diện thực tế (Playwright)
- `docs/2d-simulation/screenshots/01_sim2d_initial_map.png`: Toàn cảnh `/admin` tích hợp KPI + Bản đồ 2D + Inspector + Điều khiển IoT.
- `docs/2d-simulation/screenshots/02_sim2d_shopping_in_progress.png`: `CART_001` di chuyển tới `Đồ uống & Sữa`, quét 2 lon Coca Cola (`24.000 ₫`, `710 g`), Live Event Log cập nhật realtime.
- `docs/2d-simulation/screenshots/03_sim2d_alerts_active.png`: Cảnh báo `WEIGHT_MISMATCH` (`CART_001`) và `LOW_BATTERY` (`CART_002` pin 15%).
- `docs/2d-simulation/screenshots/04_sim2d_offline_state.png`: `CART_003` mất kết nối (`Offline`, cảnh báo `Mất kết nối`).
- `docs/2d-simulation/screenshots/05_sim2d_checkout_completed.png`: `CART_001` hoàn tất `Checkout` tại Quầy thanh toán (`Vừa Checkout`).
