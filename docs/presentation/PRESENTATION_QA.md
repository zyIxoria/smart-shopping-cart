# Bộ Câu Hỏi & Trả Lời Bảo Vệ Đồ Án (45 Câu Hỏi Kỹ Thuật)

Tài liệu gồm **45 câu hỏi vấn đáp** chia đều theo **10 nhóm chủ đề**, trả lời chính xác theo source code thực tế của project Smart Shopping Cart sau đợt hoàn thiện Technical Audit, phân biệt rõ tính năng **đã triển khai**, **đang mô phỏng** và **hướng phát triển phần cứng**.

---

## Nhóm 1 — Tổng Quan Đề Tài (4 câu)

**Câu 1: Đề tài Smart Shopping Cart giải quyết bài toán thực tế nào, và phạm vi hiện tại của nhóm dừng ở đâu?**
- **Trả lời:** Giải quyết 3 vấn đề tại siêu thị: (1) ùn tắc thanh toán thủ công tại quầy, (2) sai sót/gian lận bỏ hàng không quét nhờ đối chiếu cân nặng thực tế với cân dự kiến, và (3) khó giám sát tình trạng pin/kết nối đội xe theo thời gian thực.
- **Phạm vi trung thực:** Đây là **hệ thống IoT mô phỏng** gồm Python Simulator 3 xe (`simulator/`), firmware ESP32 + cấu hình Wokwi (`firmware/`), Backend FastAPI + Dual-Engine Database (PostgreSQL 16 & SQLite), và giao diện React. Nhóm **không** lắp ráp phần cứng vật lý và không trình bày dữ liệu mô phỏng như dữ liệu cảm biến đo từ phần cứng thật.

**Câu 2: Hệ thống phục vụ những đối tượng nào và cách phân quyền ra sao?**
- **Trả lời:** Hệ thống có 4 vai trò trong `backend/auth.py`:
  1. `anonymous`: Xem sản phẩm (`GET /api/products`), danh sách xe đã che chi tiết giỏ hàng (`public_cart`), đăng nhập hoặc tạo phiên mới (`POST /api/sessions`).
  2. `customer`: Nhận `session_token` khi bắt đầu phiên, chỉ được xem/thêm/xoá/thanh toán/huỷ **đúng phiên của mình** (chống IDOR).
  3. `viewer`: Nhân viên chỉ xem dashboard, cảnh báo, telemetry, không được khoá xe hoặc sửa sản phẩm.
  4. `admin`: Toàn quyền đăng ký xe (`POST /api/carts`), khoá/mở khoá xe, huỷ phiên treo, CRUD sản phẩm.

**Câu 3: Tại sao thanh toán lại đặt trên Customer Web chứ không làm trực tiếp trên ESP32?**
- **Trả lời:** Để tối ưu chi phí và trải nghiệm: ESP32 chỉ cần màn hình OLED SSD1306 nhỏ (128×64) hiển thị trạng thái, cân nặng, pin và thông báo `"CAM ON!"` khi nhận `END_SESSION`. Giao dịch thanh toán cần danh sách chi tiết giỏ hàng, xác nhận hoá đơn và xử lý lỗi mạng nên đặt trên Customer Web (`/customer/cart/:sid`) giao tiếp REST trực tiếp với Backend.

**Câu 4: Điểm cải tiến và mở rộng nào của project sau Technical Audit?**
- **Trả lời:**
  1. Chuyển đổi Backend sang **FastAPI**, tự động sinh tài liệu Swagger UI tại `/docs` và ReDoc tại `/redoc`.
  2. Bổ sung hỗ trợ **PostgreSQL 16** với kiến trúc **Dual-Engine** (`db.py`), sẵn sàng cho Production container.
  3. Tích hợp **WebSocket trực tiếp trên cổng FastAPI 8000** (`/ws`), gom cổng tiện lợi cho triển khai.
  4. Cài đặt **Offline Queue** trên thiết bị Simulator, tự động gửi bù khi có mạng lại.
  5. Lưu trữ lịch sử lệnh điều khiển vào CSDL bền vững (`cart_commands`) và cung cấp API `GET /api/commands`.
  6. Bảo vệ API điều khiển mô phỏng bằng token `SIM_CONTROL_TOKEN`.

---

## Nhóm 2 — Kiến Trúc IoT (4 câu)

**Câu 5: Hãy trình bày kiến trúc tổng thể của hệ thống và lý do kết hợp 3 giao thức MQTT, REST và WebSocket.**
- **Trả lời:**
  - **MQTT (`:1883`):** Dùng cho thiết bị ↔ Backend vì nhẹ, hỗ trợ Pub/Sub tách rời thiết bị khỏi server ứng dụng, gửi lệnh điều khiển 2 chiều tức thì.
  - **REST (`/api/*` trên `:8000`):** Dùng cho các thao tác CRUD có cấu trúc, xác thực Bearer token, trạng thái HTTP rõ ràng (200/201/401/403/409/422/504) từ Frontend.
  - **WebSocket (`/ws` trên `:8000`):** Dùng để Backend đẩy sự kiện realtime (`CART_UPDATED`, `ALERT_TRIGGERED`, `COMMAND_ACK`, `SCAN_REJECTED`) lên UI mà không phải polling HTTP liên tục.

**Câu 6: "Backend là nguồn sự thật (Single Source of Truth)" có ý nghĩa kỹ thuật gì trong code?**
- **Trả lời:** Xe có thể gửi trường `cart_status` trong `telemetry`, nhưng trong `backend/services/ingest.py`, Backend **chỉ** cập nhật `battery_percent` và `current_weight` vào bảng `smart_carts`, còn `cart_status` trong telemetry chỉ lưu vào `device_telemetry` để ghi lịch sử. Trạng thái thật `AVAILABLE` / `IN_USE` / `LOCKED` chỉ do Backend quyết định qua các giao dịch session và ACK lệnh. Khi xe mất mạng nối lại, Backend ép xe đồng bộ lại theo trạng thái trong CSDL bằng `_reconcile()`.

**Câu 7: Mô hình xử lý đồng thời (concurrency) trong Backend hoạt động như thế nào để tránh xung đột dữ liệu?**
- **Trả lời:**
  - HTTP endpoint chạy trong threadpool của Starlette/FastAPI.
  - MQTT consumer (`MqttClient`) chạy trên 1 thread nền, xử lý tuần tự từng message → đảm bảo `scan` đến trước `telemetry` luôn được ghi DB trước khi Rule Engine tính cân dự kiến.
  - `HeartbeatMonitor` chạy trên thread riêng mỗi `2s`.
  - Truy cập CSDL qua transaction `with db.tx():` bảo đảm tính nguyên tử.
  - Đẩy sự kiện từ các worker thread lên WebSocket event loop qua `loop.call_soon_threadsafe()`.

**Câu 8: Trong mô hình 5 tầng IoT, tầng Edge Processing của project nằm ở đâu và làm những việc gì?**
- **Trả lời:** Nằm tại `firmware/lib/cartcore/` (trên ESP32) và `simulator/cart/__init__.py` (trên Simulator). Nó thực hiện: lọc nhiễu cân nặng (`WeightFilter`: trung vị 5 mẫu + EMA), chuẩn hoá mã vạch (`normalize_barcode`), trễ pin yếu (`LowBatteryMonitor` hysteresis `<20%` bật / `>=25%` tắt), từ chối quét ngay tại xe khi `LOCKED` hoặc chưa có phiên (`can_scan()`), và đệm hàng đợi ngoại tuyến (`offline_queue` trên Simulator).

---

## Nhóm 3 — ESP32 và Wokwi (5 câu)

**Câu 9: Vì sao nhóm tách `firmware/lib/cartcore/` ra khỏi `firmware/src/main.cpp`?**
- **Trả lời:** `src/main.cpp` phụ thuộc các thư viện phần cứng Arduino/ESP32 (`WiFi.h`, `HX711.h`, `Adafruit_SSD1306.h`), rất khó unit test nhanh. Tách toàn bộ logic nghiệp vụ thuần (JSON parser/builder, lọc cân, state machine, HMAC-SHA256) vào `lib/cartcore` bằng C++11 thuần giúp biên dịch & chạy unit test trực tiếp trên PC và kiểm tra chéo với Python (`test_firmware_protocol.py`).

**Câu 10: Firmware xử lý đọc cân HX711 và tránh cảnh báo lệch cân giả sau khi quét như thế nào?**
- **Trả lời:** Hai cơ chế:
  1. **Lọc nhiễu (`WeightFilter` trong `cartcore.cpp`):** Lấy trung vị của cửa sổ 5 mẫu để loại nhiễu xung, sau đó áp dụng EMA (`alpha = 0.4`) và deadband `< 1g` về `0g`.
  2. **Chờ ổn định sau quét (`SETTLE_AFTER_SCAN_MS = 3000ms` trong `main.cpp`):** Sau khi quét mã vạch, firmware đặt độ trễ 3 giây cho khách kịp đặt món hàng vào giỏ rồi mới gửi `telemetry`, tránh kích hoạt `WEIGHT_MISMATCH` giả.

**Câu 11: Vì sao pin lại đo trên `GPIO34` (ADC1) mà không dùng chân ADC2?**
- **Trả lời:** Trên ESP32, bộ ADC2 được chia sẻ phần cứng với module Wi-Fi; khi bật `WiFi.begin()`, các chân ADC2 không đọc được ổn định (`pins.h:26`). Do đó firmware bắt buộc dùng `GPIO34` (ADC1) kết hợp cầu chia áp `100kΩ / 100kΩ` (`BATTERY_DIVIDER_RATIO = 2.0`) và đường cong nội suy LiPo 1S (`3300mV=0% .. 4200mV=100%`).

**Câu 12: Giải thích 3 chế độ mô phỏng Wokwi trong `firmware/platformio.ini` và cơ chế hoạt động của `tools/wokwi_bridge.py`.**
- **Trả lời:**
  1. `esp32dev_sim` / `esp32dev_standalone`: Chạy độc lập trong Wokwi không nối mạng, tự tạo phiên nội bộ #1, in message `[local] ...` ra Serial.
  2. `esp32dev_wokwi_online`: Nối Wi-Fi ảo `Wokwi-GUEST` tới broker công cộng (`broker.hivemq.com:1883`) dùng `MQTT_TOPIC_ROOT` riêng.
  3. `esp32dev_sim_bridge`: Wokwi mở Serial ra cổng TCP `4000` (`rfc2217ServerPort = 4000`). `wokwi_bridge.py` giải mã Telnet, thay `message_id` UUID và `timestamp` UTC thực, ký HMAC nếu có key, rồi đẩy lên broker local; chiều ngược lại chuyển lệnh thành `cmd {json}\n`.

**Câu 13: Phần ESP32 & Wokwi hiện tại đã kiểm chứng tới đâu?**
- **Trả lời trung thực:**
  - **Đã kiểm chứng:** Biên dịch thành công 100% cả 2 target `esp32dev_sim` (41.96s) và `esp32dev_sim_bridge` (62.54s) bằng PlatformIO. Khớp chân phần cứng giữa `diagram.json` và `include/pins.h`.
  - **Giới hạn:** Chưa chạy thử nghiệm trên bo mạch ESP32 thật và cảm biến vật lý; hệ thống kiểm thử chính dựa trên Python Smart Cart Simulator và mô phỏng Wokwi.

---

## Nhóm 4 — MQTT (5 câu)

**Câu 14: Hệ thống dùng những MQTT topic nào và cấu trúc JSON Envelope có ý nghĩa gì?**
- **Trả lời:** Gồm 6 topic dạng `smartcart/{cart_id}/{kind}`:
  - Uplink (Xe → Backend): `scan`, `event`, `telemetry`, `heartbeat`, `ack`.
  - Downlink (Backend → Xe): `command`.
  Mọi payload bọc trong Envelope chuẩn (`message_id`, `cart_id`, `schema_version=1`, `timestamp` UTC, tuỳ chọn `sig`, `data`). Mục đích: tách metadata định tuyến/bảo mật/chống trùng ra khỏi dữ liệu nghiệp vụ (`data`), giúp `Gateway` kiểm tra thống nhất trước khi đưa vào từng handler.

**Câu 15: Tại sao `shared/mqttlite.py` sử dụng QoS 0 và hệ thống bù đắp độ tin cậy như thế nào?**
- **Trả lời:** `mqttlite.py` sử dụng QoS 0 để tối ưu hiệu năng và không phụ thuộc thư viện bên ngoài. Độ tin cậy được bù đắp bằng:
  1. **Offline Queue:** Simulator lưu các lượt quét vào hàng đợi khi mất mạng và tự động gửi bù khi kết nối lại.
  2. **Command & ACK:** Backend gửi lệnh kèm `command_id` và chờ ACK trong 5 giây, có lưu trữ trạng thái vào bảng `cart_commands`.
  3. **Deduplication:** Backend lưu `scan_id` để chống xử lý trùng khi gửi bù.

**Câu 16: Hệ thống có dùng Retained Message hay Last Will and Testament (LWT) không?**
- **Trả lời:** **Không dùng tầng MQTT.** Thay cho LWT, Backend dùng `HeartbeatMonitor` kiểm tra `last_seen > 15s` mỗi `2s` để chuyển xe sang `OFFLINE`. Thay cho Retained, khi xe nối lại mạng, Backend gọi `_reconcile()` để gửi lại lệnh trạng thái chuẩn (`LOCK_CART` / `START_SESSION` / `END_SESSION`).

**Câu 17: Cơ chế chống xử lý trùng (Deduplication) và chống phát lại (Anti-replay) hoạt động ở những bước nào?**
- **Trả lời:** Trong `Gateway.on_message()`:
  1. Kiểm tra chữ ký HMAC-SHA256 (`verify_payload`) trước để loại bỏ gói tin giả mạo.
  2. Kiểm tra `schema_version` và `cart_id` phải khớp nhau.
  3. Kiểm tra Clock Skew (`<=300s`): loại gói có timestamp lệch quá 5 phút so với server.
  4. Kiểm tra LRU cache `msg:{message_id}` (tối đa 2000 phần tử).
  5. Tại `ingest._scan()`: kiểm tra thêm `scan:{cart_id}:{scan_id}` chống trùng sự kiện quét hàng.

**Câu 18: Khi xe mất mạng đột ngột rồi có mạng lại, quá trình đồng bộ diễn ra như thế nào?**
- **Trả lời:**
  1. Xe gửi lại `heartbeat` ngay khi kết nối thành công.
  2. Xe tự động kích hoạt `drain_offline_queue()`, gửi bù các lượt quét đã lưu theo thứ tự FIFO.
  3. Backend nhận tin, phát hiện xe chuyển từ `OFFLINE → ONLINE`, kích hoạt `_reconcile()` để ép xe đồng bộ lại trạng thái phiên từ CSDL.

---

## Nhóm 5 — Backend và API (5 câu)

**Câu 19: Backend của hệ thống được xây dựng bằng công nghệ gì và cung cấp những gì?**
- **Trả lời:** Xây dựng bằng **FastAPI** (`backend/api/app.py`), phục vụ 26 REST endpoints, tự động sinh tài liệu OpenAPI 3.0.3, Swagger UI tại `/docs` và ReDoc tại `/redoc`, đồng thời tích hợp WebSocket server `/ws` trên cùng cổng 8000.

**Câu 20: Kể tên các nhóm route chính trong 26 REST endpoints.**
- **Trả lời:**
  1. **System:** `GET /api/health`
  2. **Products:** CRUD sản phẩm, ẩn/hiện sản phẩm, tìm kiếm theo barcode.
  3. **Carts:** Danh sách xe, chi tiết xe, lịch sử telemetry, khoá xe (`/lock`), mở khoá (`/unlock`).
  4. **Sessions:** Tạo phiên, chi tiết phiên, thêm/xóa món nhập tay, thanh toán (`/checkout`), huỷ phiên.
  5. **Alerts:** Danh sách cảnh báo (`/alerts`) lọc theo trạng thái và mã xe.
  6. **Commands:** Lịch sử lệnh (`/commands`), chi tiết lệnh (`/commands/{id}`).
  7. **Auth:** Kiểm tra cấu hình auth, đăng nhập, thông tin tài khoản hiện tại, đăng xuất.

**Câu 21: Price Snapshot là gì và được hiện thực như thế nào trong giỏ hàng?**
- **Trả lời:** Price Snapshot là cơ chế chốt giá sản phẩm tại thời điểm khách hàng đưa vào giỏ. Trong bảng `cart_items`, ngoài `product_id`, hệ thống lưu trực tiếp `unit_price` lấy từ bảng `products` lúc quét. Khi admin cập nhật giá mới trong danh mục, các phiên mua hàng đang diễn ra vẫn giữ nguyên giá cũ đã chốt.

**Câu 22: Giao dịch Checkout được bảo đảm tính nguyên tử (Atomic) như thế nào?**
- **Trả lời:** Toàn bộ quá trình Checkout được bọc trong khối transaction `with db.tx():`. Nếu có bất kỳ lỗi nào xảy ra (ví dụ: xe đã bị khoá, mất kết nối CSDL), toàn bộ câu lệnh SQL sẽ được rollback, trạng thái phiên không bị chuyển dở dang sang COMPLETED.

**Câu 23: Làm thế nào Backend gửi lệnh khoá xe xuống thiết bị và xác nhận thành công?**
- **Trả lời:** Khi Admin gọi `POST /api/carts/{id}/lock`:
  1. Backend ghi lệnh vào bảng `cart_commands` với trạng thái `PENDING`.
  2. Gửi MQTT `smartcart/{id}/command` với `LOCK_CART`.
  3. Chờ đợi gói tin ACK từ xe tối đa 5 giây thông qua `threading.Event`.
  4. Khi xe phản hồi ACK với kết quả `OK`, Backend cập nhật `cart_commands` thành `OK`, cập nhật trạng thái xe thành `LOCKED` và trả về HTTP 200. Nếu hết thời gian chờ, trả về HTTP 504 TIMEOUT.

---

## Nhóm 6 — Database (4 câu)

**Câu 24: Dự án sử dụng hệ quản trị cơ sở dữ liệu nào?**
- **Trả lời:** Dự án sử dụng kiến trúc **Dual-Engine Database** (`backend/database/db.py`):
  - **PostgreSQL 16:** Sử dụng thư viện `psycopg` 3.3.9 cho môi trường Docker và Production.
  - **SQLite (WAL mode):** Sử dụng cho môi trường kiểm thử tự động cục bộ nhằm tăng tốc độ chạy test.

**Câu 25: Nêu tên và chức năng của 7 bảng trong CSDL.**
- **Trả lời:**
  1. `products`: Danh mục sản phẩm, mã vạch, giá, cân nặng chuẩn.
  2. `smart_carts`: Trạng thái xe, trạng thái kết nối, pin, trọng lượng hiện tại.
  3. `shopping_sessions`: Phiên mua sắm, trạng thái phiên, tổng tiền, trọng lượng kỳ vọng.
  4. `cart_items`: Các mặt hàng trong phiên mua sắm, số lượng, đơn giá chốt.
  5. `device_telemetry`: Lịch sử viễn trắc cân nặng và pin.
  6. `alerts`: Các cảnh báo bất thường và thời điểm giải quyết.
  7. `cart_commands`: Lịch sử các lệnh điều khiển gửi xuống xe và trạng thái ACK.

**Câu 26: Ràng buộc "mỗi xe chỉ có 1 phiên mua sắm ACTIVE" được đảm bảo như thế nào?**
- **Trả lời:** Trong schema CSDL (cả SQLite lẫn PostgreSQL 16), hệ thống tạo một **Partial Unique Index**:
  `CREATE UNIQUE INDEX ux_active_session_per_cart ON shopping_sessions(cart_id) WHERE status = 'ACTIVE';`
  Ràng buộc này ngăn chặn ở mức CSDL việc tạo 2 phiên ACTIVE trên cùng 1 xe, ngay cả khi có 2 request gửi đồng thời.

**Câu 27: Tại sao cần bảng `cart_commands` thay vì chỉ lưu lệnh trong bộ nhớ RAM?**
- **Trả lời:** Lưu trong RAM sẽ làm mất toàn bộ lịch sử lệnh và trạng thái ACK khi Backend khởi động lại hoặc gặp sự cố crash. Bảng `cart_commands` giúp lưu trữ bền vững, phục vụ tra cứu lịch sử kiểm toán (audit trail) và hỗ trợ khôi phục trạng thái sau sự cố.

---

## Nhóm 7 — Frontend và WebSocket (4 câu)

**Câu 28: Giao diện người dùng được xây dựng bằng công nghệ gì?**
- **Trả lời:** Xây dựng bằng **React 19**, biên dịch đóng gói bằng **esbuild** (`frontend/build.mjs`), giao diện viết bằng CSS thuần tối ưu hóa không phụ thuộc thư viện CSS nặng.

**Câu 29: Kênh WebSocket hoạt động như thế nào và được bảo mật ra sao?**
- **Trả lời:** Tích hợp trực tiếp tại endpoint `/ws` trên cổng 8000 của FastAPI. Sau khi bắt tay kết nối, client gửi gói tin `{"type": "AUTH", "token": "..."}` để xác thực. Backend phân quyền sự kiện:
  - Khách hàng chỉ nhận sự kiện giỏ hàng của chính xe mình.
  - Quản trị viên (Staff) nhận toàn bộ sự kiện hệ thống.
  - Người dùng ẩn danh chỉ nhận trạng thái xe cơ bản (đã che thông tin nhạy cảm).

**Câu 30: Frontend xử lý ra sao nếu kết nối WebSocket bị gián đoạn?**
- **Trả lời:** Frontend cài đặt cơ chế **Fallback Polling** chu kỳ 5 giây trong `frontend/src/state/store.jsx`. Nếu WebSocket bị ngắt, giao diện tự động gửi HTTP GET định kỳ để cập nhật giỏ hàng và cảnh báo mà không làm gián đoạn trải nghiệm người dùng.

**Câu 31: Trang điều khiển mô phỏng (`/simulator`) có chức năng gì?**
- **Trả lời:** Cho phép giảng viên và người đánh giá tương tác trực quan với 3 xe ảo: quét thêm/bớt sản phẩm, kéo thanh trượt pin, tăng giảm độ lệch cân nặng để giả lập bỏ quên đồ, và ngắt/phục hồi mạng xe để kiểm tra khả năng phục hồi của hệ thống.

---

## Nhóm 8 — Docker và Triển Khai (4 câu)

**Câu 32: Docker Compose của dự án bao gồm những service nào?**
- **Trả lời:** Gồm 4 services:
  1. `postgres`: Image `postgres:16-alpine`, lưu trữ dữ liệu bền vững qua volume `postgres-data`.
  2. `mqtt-broker`: Image `eclipse-mosquitto:2`, làm nhiệm vụ định tuyến MQTT.
  3. `backend`: Image build từ `backend/Dockerfile` multi-stage, chạy FastAPI trên cổng 8000.
  4. `simulator`: Image build từ `simulator/Dockerfile`, mô phỏng 3 xe trên cổng 8090.

**Câu 33: Multi-stage build trong `backend/Dockerfile` mang lại lợi ích gì?**
- **Trả lời:**
  - Stage 1 (Node 22): Biên dịch mã nguồn React frontend thành các tệp tĩnh trong `frontend/dist/`.
  - Stage 2 (Python 3.12-slim): Chỉ copy thư mục `frontend/dist/` sang và cài đặt runtime Python, loại bỏ hoàn toàn Node.js và `node_modules` khỏi image cuối cùng, giúp giảm kích thước image và tăng tính bảo mật.

**Câu 34: Healthcheck trong Docker Compose được cấu hình như thế nào?**
- **Trả lời:**
  - `postgres` sử dụng `pg_isready -U postgres -d smartcart`.
  - Service `backend` có điều kiện `depends_on: { postgres: { condition: service_healthy } }`, bảo đảm Backend chỉ khởi động khi PostgreSQL đã sẵn sàng nhận kết nối.

**Câu 35: Script `scripts/run_local.ps1` giải quyết vấn đề gì trên Windows?**
- **Trả lời:** Tự động hóa toàn bộ quy trình khởi chạy cục bộ trên môi trường Windows native: kiểm tra phụ thuộc Python, dọn dẹp các tiến trình cũ đang chiếm dụng cổng 8000, 8081, 8090, khởi động tuần tự Broker -> Backend -> Simulator và xử lý tắt tiến trình sạch sẽ khi bấm `Ctrl + C`.

---

## Nhóm 9 — Kiểm Thử và Độ Tin Cậy (5 câu)

**Câu 36: Tổng số bài kiểm thử của dự án là bao nhiêu và kết quả ra sao?**
- **Trả lời:** Tổng cộng **131 bài kiểm thử tự động đã thực thi và ĐẠT 100% (131 PASS)**:
  - 47 bài Unit Tests (`tests/unit`).
  - 64 bài Integration Tests (`tests/integration`).
  - 20 bài E2E Browser Tests bằng Playwright (`tests/e2e`).
  - 16 bài kiểm thử bị bỏ qua (15 bài C++ host do thiếu compiler MinGW g++ trên máy Windows và 1 bài telnet bridge mock).

**Câu 37: Kiểm thử E2E bằng Playwright kiểm chứng những chức năng gì?**
- **Trả lời:** Khởi động trình duyệt Chromium thật và tự động hóa thao tác:
  - Khách hàng chọn xe, quét sản phẩm, tăng giảm số lượng, thanh toán hoàn tất.
  - Ngăn chặn chọn xe đã bị khóa hoặc đang offline.
  - Admin đăng nhập, xem danh sách xe, xem cảnh báo realtime, khóa xe và mở khóa xe.
  - Quản lý sản phẩm (thêm, sửa, ẩn, hiện).

**Câu 38: Nhóm đã kiểm tra kịch bản nhiều xe hoạt động đồng thời (Multi-cart) như thế nào?**
- **Trả lời:** Chạy đồng thời 3 xe `CART_001`, `CART_002`, `CART_003` với 3 phiên mua sắm song song. Mỗi xe gửi sự kiện quét và viễn trắc cùng lúc. Kết quả kiểm thử xác nhận giỏ hàng của từng xe hoàn toàn độc lập, không bị lẫn lộn dữ liệu và không xảy ra xung đột CSDL.

**Câu 39: Kịch bản kiểm thử Offline Queue được thực hiện như thế nào?**
- **Trả lời:** Khởi tạo phiên mua sắm -> Ngắt mạng xe (`cart.go_offline()`) -> Quét 2 sản phẩm khi xe đang offline (sản phẩm được đưa vào hàng đợi `offline_queue`) -> Kiểm tra Backend chưa nhận được món nào -> Phục hồi kết nối mạng (`cart.go_online()`) -> Xe tự động xả hàng đợi -> Kiểm tra Backend nhận đủ cả 2 món với tổng tiền và trọng lượng chính xác.

**Câu 40: Nhóm đã xác minh biên dịch Firmware ESP32 như thế nào?**
- **Trả lời:** Sử dụng công cụ PlatformIO CLI để biên dịch trực tiếp trên mã nguồn C++:
  - `pio run -d firmware -e esp32dev_sim`: Biên dịch thành công 100% (41.96 giây).
  - `pio run -d firmware -e esp32dev_sim_bridge`: Biên dịch thành công 100% (62.54 giây).
  - Kết quả sinh ra file nhị phân `firmware.bin` sẵn sàng nạp cho chip ESP32.

---

## Nhóm 10 — Hạn Chế và Hướng Phát Triển (5 câu)

**Câu 41: Những hạn chế kỹ thuật lớn nhất của dự án hiện tại là gì?**
- **Trả lời:**
  1. Chưa triển khai trên phần cứng ESP32 và cảm biến vật lý thực tế; dữ liệu vẫn là dữ liệu mô phỏng.
  2. Giao thức HTTP/WS trên môi trường cục bộ chưa cấu hình chứng chỉ SSL/TLS (mới có TLS cho MQTT).
  3. Cơ chế quét mã vạch vẫn dựa vào quét barcode 1D/2D, chưa có camera AI nhận diện trực quan sản phẩm.

**Câu 42: Nếu muốn triển khai hệ thống trên xe đẩy vật lý thật trong siêu thị, cần bổ sung những gì?**
- **Trả lời:**
  1. Lắp ráp phần cứng: Board ESP32 DevKit, cảm biến tải trọng Load Cell kèm mạch khuếch đại HX711 gắn dưới đáy giỏ, đầu đọc mã vạch GM65/GM66 giao tiếp UART, màn hình OLED SSD1306 và pin sạc Li-ion kèm mạch sạc an toàn.
  2. Hiệu chuẩn cảm biến cân (Calibration) với các quả cân chuẩn để loại bỏ sai số cơ khí.
  3. Cấu hình mạng Wi-Fi công nghiệp phủ sóng toàn bộ siêu thị và nạp chứng chỉ TLS vào bộ nhớ flash của ESP32.

**Câu 43: Làm thế nào để giải quyết trường hợp khách hàng gian lận tráo đổi nhãn mã vạch của sản phẩm đắt tiền sang sản phẩm rẻ tiền?**
- **Trả lời:** Hệ thống hiện tại đối chiếu mã vạch với **trọng lượng tiêu chuẩn** trong CSDL. Nếu dán nhãn mì gói (75g) lên hộp sữa (1030g), cảm biến cân sẽ phát hiện chênh lệch 955g > 100g (ngưỡng dung sai) và kích hoạt ngay cảnh báo `WEIGHT_MISMATCH`. Để chống gian lận hoàn toàn đối với 2 sản phẩm cùng trọng lượng, hướng phát triển tiếp theo là tích hợp camera AI nhận diện hình ảnh món hàng khi bỏ vào giỏ.

**Câu 44: Hệ thống có khả năng mở rộng (Scalability) phục vụ hàng trăm xe cùng lúc không?**
- **Trả lời:** Kiến trúc hiện tại rất dễ mở rộng:
  - MQTT Broker (Mosquitto) có thể chịu tải hàng chục nghìn kết nối đồng thời.
  - Backend FastAPI hỗ trợ bất đồng bộ và có thể triển khai nhiều instance phía sau Load Balancer (Nginx/HAProxy).
  - Cơ sở dữ liệu PostgreSQL 16 hỗ trợ connection pooling và replica để xử lý khối lượng giao dịch lớn.

**Câu 45: Bài học kinh nghiệm quan trọng nhất mà nhóm rút ra qua đồ án này là gì?**
- **Trả lời:** Tầm quan trọng của việc **phân tách rõ ràng giữa tầng logic nghiệp vụ và tầng phần cứng nhúng** (như việc tách `lib/cartcore` C++ thuần để kiểm thử trên PC), thiết kế hợp đồng giao tiếp (Contract) chặt chẽ giữa các thành phần trước khi viết code, và xây dựng bộ kiểm thử tự động đa tầng giúp phát hiện và ngăn chặn lỗi hồi quy trong quá trình phát triển hệ thống IoT.
