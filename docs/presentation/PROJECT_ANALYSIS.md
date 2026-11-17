# Phân Tích Toàn Diện Source Code Project Smart Shopping Cart

Tài liệu này tổng hợp kết quả đọc, kiểm chứng trực tiếp và hoàn thiện toàn bộ source code, tệp cấu hình, cơ sở dữ liệu, firmware, frontend, tài liệu và bộ kiểm thử trong workspace `D:\Filehoc\IOT\smart-shopping-cart\smart-shopping-cart`.

> **Nguyên tắc phân tích:** Mọi nhận định về công nghệ, luồng dữ liệu và trạng thái hoàn thiện đều dựa trực tiếp trên mã nguồn hiện tại sau đợt Technical Audit và hoàn thiện Master Prompt; phản ánh trung thực ranh giới giữa phần mềm/mô phỏng và phần cứng thực tế.

---

## 1. Bảng Phân Tích Thành Phần & Trạng Thái Thực Tế

Phân loại trạng thái chuẩn:
- **Đã triển khai và kiểm chứng**: Đã có mã nguồn hoàn chỉnh, tích hợp vào luồng chạy chính và đã vượt qua toàn bộ các bài kiểm thử thực tế.
- **Đã triển khai nhưng chưa kiểm chứng đầy đủ**: Đã có mã nguồn/cấu hình nhưng phụ thuộc vào môi trường đặc thù bên ngoài (ví dụ: board ESP32 vật lý thật hoặc kết nối internet trực tiếp).
- **Đang triển khai một phần**: Đã có một phần mã nguồn nhưng chưa hoàn thiện hoặc chưa nối vào luồng chính.
- **Chưa triển khai**: Chỉ mới ở mức ý tưởng/thiết kế trên tài liệu.

| Thành phần | Công nghệ thực tế trong code | Vai trò | Cách hoạt động trong project | Trạng thái thực tế |
|---|---|---|---|---|
| **Backend Web & REST API** | **FastAPI** (`>=0.115`), **Uvicorn** (`>=0.30`), **Pydantic** (`>=2.6`) | Tiếp nhận REST `/api/*`, xác thực RBAC, phục vụ Swagger `/docs`, ReDoc `/redoc`, phục vụ SPA tĩnh `frontend/dist` | `backend/api/app.py` khởi tạo ứng dụng `FastAPI`; `routes.py` đăng ký 26 endpoints qua decorator `@route` (`registry.py`). Handler đồng bộ chạy trong `run_in_threadpool`. `SecurityHeadersMiddleware` chèn CSP, `X-Frame-Options: DENY`, `no-store`. | **Đã triển khai và kiểm chứng** *(26 REST endpoints, Swagger UI `/docs`, ReDoc `/redoc`, tương thích `/api/docs`)* |
| **Xác thực & Phân quyền (Auth)** | `PBKDF2-HMAC-SHA256` (200k vòng), token ký `HMAC-SHA256` (`shared/security.py`, `backend/auth.py`) | Bảo vệ REST & WebSocket cho 4 vai trò: `anonymous`, `customer`, `viewer`, `admin` | `AuthService` băm mật khẩu + salt, sinh token có hạn (`8h` admin / `4h` khách), chống brute-force (`5` lần sai khoá `60s`), cấp token gắn `sid`/`cart_id` chống IDOR. Danh sách thu hồi `_revoked` lưu trong bộ nhớ. | **Đã triển khai và kiểm chứng** *(đạt 100% tests bảo mật)* |
| **Cơ sở dữ liệu (Dual-Engine: PostgreSQL 16 & SQLite)** | **PostgreSQL 16** (`psycopg 3.3.9`) & **SQLite** (WAL mode), `Database` adapter (`backend/database/db.py`) | Lưu trữ danh mục sản phẩm, xe, phiên mua, giỏ hàng, telemetry, cảnh báo, lịch sử lệnh | Hỗ trợ 2 chế độ cấu hình qua `DB_BACKEND`: PostgreSQL cho Production/Docker và SQLite cho kiểm thử/máy cục bộ. Tự động chuyển đổi `?` sang `%s`, `RETURNING id`, giao dịch nguyên tử `db.tx()` thông qua transaction context. Schema gồm **7 bảng**. | **Đã triển khai và kiểm chứng** *(Cả 2 schema `schema.sql` và `schema_postgres.sql` đều đồng bộ 7 bảng)* |
| **Lịch sử Lệnh (Cart Commands)** | Bảng CSDL `cart_commands` + RAM cache + `threading.Event` (`backend/services/commands.py`) | Gửi lệnh `LOCK_CART` / `UNLOCK_CART` / `START_SESSION` / `END_SESSION` và chờ ACK | `send_command()` ghi nhận vào CSDL với trạng thái `PENDING`, chờ ACK tối đa `5s`. Khi nhận ACK từ xe, cập nhật trạng thái `OK`/`FAILED`/`TIMEOUT`. `get_command()` tự động fallback tra cứu CSDL nếu cache rỗng (sống qua restart Backend). Cung cấp `GET /api/commands`. | **Đã triển khai và kiểm chứng** *(đã có test kiểm chứng tồn tại qua restart)* |
| **Alert Engine & Monitor** | Hàm thuần Python (`backend/alerts/rules.py`), `alerts.py`, `HeartbeatMonitor` (`backend/mqtt/monitor.py`) | Phát hiện & tự động đóng 3 loại cảnh báo: `LOW_BATTERY`, `WEIGHT_MISMATCH`, `OFFLINE` | `evaluate_telemetry()` chạy sau mỗi `telemetry` hợp lệ (`pin < 20%`, `\|thực - dự kiến\| > 100g` khi `IN_USE`). Thread `HeartbeatMonitor` quét mỗi `2s`, đánh dấu `OFFLINE` nếu `last_seen > 15s`. Chống spam cảnh báo bằng partial unique index `ux_alert_active`. | **Đã triển khai và kiểm chứng** |
| **Realtime WebSocket (Gom cổng & Đa kênh)** | Native FastAPI WebSocket (`@app.websocket("/ws")`) trên cổng **8000** và máy chủ phụ trên cổng **8081** | Đẩy sự kiện realtime một chiều từ server xuống Customer UI & Admin Dashboard | Tích hợp WebSocket trực tiếp trên cổng HTTP chính 8000 (`/ws`) thông qua adapter `FastAPIWsConnection` gắn vào `Hub`. Client xác thực bằng tin nhắn `{"type":"AUTH","token":...}`. `hub.project()` lọc sự kiện theo vai trò (khách chỉ thấy giỏ hàng của mình, ẩn danh chỉ thấy trạng thái xe). | **Đã triển khai và kiểm chứng** *(kết nối thành công trên cổng 8000 và 8081)* |
| **MQTT Client & Gateway** | `shared/mqttlite.py` (MQTT 3.1.1 stdlib), `backend/mqtt/gateway.py` | Giao tiếp 2 chiều giữa xe và Backend qua 6 topic `smartcart/{cart_id}/{kind}` | Consumer thread xử lý tuần tự: Parse topic → Verify HMAC (`sig`) → Decode & Validate → Check Clock Skew (`<=300s`) → LRU Dedupe (`2000` `message_id` + `scan_id`) → Ingest & Reconcile (`_reconcile()` khi `OFFLINE → ONLINE`). | **Đã triển khai và kiểm chứng** |
| **MQTT Broker (Dev vs Mosquitto)** | Dev: `tools/dev_broker.py` (asyncio Python); Docker: `eclipse-mosquitto:2` (`mosquitto/`) | Định tuyến pub/sub MQTT giữa xe và Backend | Mọi kịch bản local & pytest dùng `DevBroker` (hỗ trợ `--users` PBKDF2 + ACL + TLS). File `mosquitto/config/mosquitto.conf` (1883/9001) và `mosquitto/secure/mosquitto.conf` (8883 TLS + passwd + ACL) đã cấu hình trong `docker-compose.yml`. | **DevBroker: Đã kiểm chứng**<br>**Mosquitto: Cấu hình chuẩn trong Docker** |
| **Python Smart Cart Simulator** | Python stdlib (`simulator/cart/`, `scenarios/`, `cli/`, `control.py`) | Mô phỏng 3 xe `CART_001..003` đầy đủ hành vi vật lý & mạng | Mô phỏng cân (nhiễu Gauss `±3g`), sụt pin, quét ADD/REMOVE, mất mạng, tự reconnect. Tích hợp **Offline Queue** (FIFO max 50) tự động xả qua `drain_offline_queue()` khi có mạng lại. API điều khiển `:8090` được bảo vệ bằng `SIM_CONTROL_TOKEN`. | **Đã triển khai và kiểm chứng** *(Offline Queue & Token Auth đã có test xác nhận PASS)* |
| **ESP32 Firmware & Wokwi** | C++/Arduino (`firmware/`), PlatformIO (`platformio.ini`), `diagram.json`, `tools/wokwi_bridge.py` | Firmware cho phần cứng ESP32 thật và mô phỏng Wokwi (3 chế độ) | Tách logic thuần C++11 (`lib/cartcore`: JSON, `CartLogic`, `WeightFilter` median-5 + EMA, `LowBatteryMonitor`, `cartsec` SHA-256/HMAC) khỏi `src/main.cpp`. Biên dịch thành công 100% cả 2 target `esp32dev_sim` và `esp32dev_sim_bridge` trên PlatformIO. | **Đã triển khai và kiểm chứng biên dịch** *(Firmware build 100% SUCCESS; mô phỏng trên Wokwi/phần cứng thật là bước tiếp theo)* |
| **Frontend (Customer, Admin, Simulator UI)** | **React 19** (`react`, `react-dom`), **esbuild** + CSS thuần | Giao diện mua hàng (`/customer`), giám sát quản trị (`/admin`), điều khiển giả lập (`/simulator`) | `frontend/build.mjs` đóng gói vào `frontend/dist/`. Quản lý state qua React Context + `useReducer` (`store.jsx`), nhận WebSocket + fallback polling 5s, vẽ biểu đồ SVG (`charts.jsx`). Đã vượt qua 20/20 bài kiểm thử trình duyệt thực tế Playwright. | **Đã triển khai và kiểm chứng** *(20/20 E2E tests PASSED)* |
| **Docker & Triển khai** | `docker-compose.yml`, `backend/Dockerfile`, `simulator/Dockerfile`, `.env.example` | Đóng gói và chạy đồng bộ PostgreSQL 16 + Mosquitto + Backend FastAPI + Simulator | `backend/Dockerfile` multi-stage build (Node 22 build UI → Python 3.12 runtime). `docker-compose.yml` gồm 4 services: `postgres:16-alpine`, `mqtt-broker` (Mosquitto), `backend` (FastAPI), `simulator` với volume `postgres-data` và healthcheck. | **Đã triển khai và kiểm chứng cấu hình** |
| **Kiểm thử tự động (Tests)** | `pytest`, Playwright Chromium, PlatformIO Unity (`tests/unit`, `tests/integration`, `tests/e2e`) | Đảm bảo độ tin cậy nghiệp vụ, bảo mật, giao thức, phục hồi mạng và UI | Đạt **131 tests PASS** (47 Unit + 64 Integration + 20 Playwright E2E Browser tests), 16 skipped (15 test C++ host cần MinGW g++ trên Windows và 1 test telnet bridge mock). | **Đã kiểm chứng toàn diện** *(131/131 tests khả thi PASSED 100%)* |

---

## 2. Các Chỉ Số Kỹ Thuật Chính Xác Từ Source Code

- **REST Endpoints:** **26 endpoints** được định nghĩa trong `backend/api/routes.py`:
  - **System (1):** `GET /api/health` (kiểm tra database, mqtt, ws_port, uptime, stats).
  - **Products (5):** `GET /api/products`, `POST /api/products`, `PUT /api/products/{id:int}`, `GET /api/products/barcode/{barcode}`, `GET /api/products/{id:int}`.
  - **Carts (7):** `GET /api/carts`, `POST /api/carts`, `GET /api/carts/{cart_id}`, `GET /api/carts/{cart_id}/telemetry`, `GET /api/carts/{cart_id}/session`, `POST /api/carts/{cart_id}/lock`, `POST /api/carts/{cart_id}/unlock`.
  - **Sessions (6):** `POST /api/sessions`, `GET /api/sessions/{id:int}`, `POST /api/sessions/{id:int}/items`, `DELETE /api/sessions/{id:int}/items/{item_id:int}`, `POST /api/sessions/{id:int}/checkout`, `POST /api/sessions/{id:int}/cancel`.
  - **Alerts (1):** `GET /api/alerts`.
  - **Commands (2):** `GET /api/commands` (danh sách lịch sử lệnh có bộ lọc xe), `GET /api/commands/{command_id}` (chi tiết trạng thái một lệnh).
  - **Auth (4):** `GET /api/auth/config`, `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`.
- **Tài liệu API tương tác:**
  - Swagger UI: `http://localhost:8000/docs` và `http://localhost:8000/api/docs`.
  - ReDoc: `http://localhost:8000/redoc`.
  - OpenAPI 3.0.3 Schema: `http://localhost:8000/openapi.json` và `http://localhost:8000/api/openapi.json`.
- **MQTT Topics:** 6 loại topic dạng `smartcart/{cart_id}/{kind}`:
  - Uplink: `scan`, `event`, `telemetry`, `heartbeat`, `ack`.
  - Downlink: `command`.
- **Cơ sở dữ liệu (7 bảng đồng bộ):**
  1. `products`: Quản lý danh mục hàng hóa, barcode, giá, trọng lượng đơn vị.
  2. `smart_carts`: Quản lý danh sách xe, trạng thái kết nối (ONLINE/OFFLINE), trạng thái xe (AVAILABLE/IN_USE/LOCKED), pin, cân nặng hiện tại.
  3. `shopping_sessions`: Quản lý phiên mua sắm, thời gian bắt đầu/kết thúc, tổng tiền, trọng lượng kỳ vọng, trạng thái (ACTIVE/COMPLETED/CANCELLED).
  4. `cart_items`: Các dòng hàng trong giỏ, số lượng, đơn giá chốt tại thời điểm mua (price snapshot).
  5. `device_telemetry`: Lịch sử dữ liệu viễn trắc (cân nặng, pin, wifi, mqtt) phục vụ phân tích biểu đồ.
  6. `alerts`: Cảnh báo bất thường (LOW_BATTERY, WEIGHT_MISMATCH, CART_OFFLINE), trạng thái (ACTIVE/RESOLVED), chống trùng bằng partial unique index.
  7. `cart_commands`: Lịch sử các lệnh điều khiển gửi xuống xe và kết quả ACK (PENDING, OK, FAILED, TIMEOUT).
- **Ngưỡng giám sát & Cảnh báo mặc định (`backend/config.py`):**
  - `BATTERY_LOW_PERCENT = 20` (%)
  - `WEIGHT_TOLERANCE_G = 100` (gram)
  - `HEARTBEAT_TIMEOUT_S = 15` (giây)
  - `MONITOR_INTERVAL_S = 2` (giây)
  - `MAX_CLOCK_SKEW_S = 300` (giây)
  - `COMMAND_ACK_TIMEOUT_S = 5` (giây)
  - `DEDUPE_SIZE = 2000` (message IDs)
- **Dữ liệu hạt giống (`data/`):** 15 sản phẩm (`products_seed.json`), 3 xe mẫu (`CART_001`, `CART_002`, `CART_003` trong `carts_seed.json`).
- **Phạm vi mô phỏng:** Dữ liệu cảm biến cân và quét barcode được sinh ra từ `SmartCart` simulator và firmware Wokwi, không gắn cảm biến vật lý.
