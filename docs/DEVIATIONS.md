# Khác biệt so với tài liệu thiết kế & giới hạn đã biết

Tài liệu `Noi_dung_IOT_chinh_sua.docx` chọn: FastAPI · PostgreSQL · React + Vite + Tailwind · paho-mqtt · Mosquitto · Docker Compose.
Môi trường build hệ thống này **không có Internet cho pip/npm, không có Docker daemon, không có Mosquitto**, nên một số thành phần được thay bằng
phương án tương đương **chạy kiểm thử được ngay**. Mọi thứ nằm sau một ranh giới rõ ràng nên có thể quay lại stack gốc.

| Dự kiến | Thực tế | Lý do | Quay lại stack gốc |
|---|---|---|---|
| FastAPI | **Starlette + uvicorn + pydantic** (FastAPI chính là Starlette + pydantic) | Chưa cài FastAPI | Route trong `backend/api/routes.py` → `APIRouter`; xem `docs/api/API.md` |
| PostgreSQL | **SQLite** (6 bảng, schema đúng thiết kế) | Chưa có driver/DB server | `docs/database/DATABASE.md` – viết lại `Database` + chỉnh `schema.sql` |
| paho-mqtt | **`shared/mqttlite.py`** (MQTT 3.1.1, stdlib) | Chưa cài paho | Thay trong đúng 1 file; giao diện `subscribe/publish/on_message` giống paho |
| Mosquitto | Cấu hình + compose **có**, nhưng test dùng **`tools/dev_broker.py`** | Không có binary | Chạy `docker compose up` |
| WebSocket của FastAPI | **`backend/realtime/ws_server.py`** (RFC 6455 viết tay, cổng 8081) | Không có thư viện websockets/wsproto | `@app.websocket("/ws")`, giữ nguyên định dạng sự kiện |
| Vite + Tailwind + Zustand + MSW | **esbuild + CSS thuần + context/reducer + mock API tự viết** (`?mock=1`) | Không cài được | Biến env vẫn đặt tên `VITE_*`; chuyển Vite chỉ cần thêm `vite.config` |
| Swagger do FastAPI sinh | `/api/openapi.json` **sinh từ registry** + trang `/api/docs` nạp Swagger UI từ CDN | — | — |

## Mở rộng ngoài đề cương (có chủ đích)

- Lệnh `START_SESSION` / `END_SESSION` (ngoài `LOCK_CART`/`UNLOCK_CART`) để xe đồng bộ vòng đời phiên và reset giỏ vật lý.
- `POST /api/sessions/{id}/cancel`, `GET /api/carts/{id}/session`, `GET /api/commands/{id}`, sự kiện WebSocket `SCAN_REJECTED`/`CART_EVENT`.
- Backend gửi lại trạng thái đúng khi xe `OFFLINE → ONLINE` (reconcile).
- `POST /api/carts` (đăng ký xe mới, kể cả xe thật) và biến `MQTT_BIND` cho `scripts/run_local.sh` để ESP32 nối broker qua LAN.
- Firmware ESP32/PlatformIO (`firmware/`): quét + báo cân/pin + nhận lệnh; **thanh toán chỉ trên web** (theo yêu cầu).
- Lớp bảo mật (ngoài đề cương, theo Chương 4 của môn học): đăng nhập + vai trò admin/viewer/khách, MQTT user/ACL/TLS, ký HMAC từng message, `tools/provision.py`, `scripts/run_secure.sh`.
- Trang web `/simulator` (giao diện điều khiển phần cứng giả lập) + API điều khiển `simulator/control.py` (cổng 8090, không xác thực, mặc định chỉ localhost).

## Chưa kiểm chứng / chưa làm

| Hạng mục | Trạng thái |
|---|---|
| Chạy với **Mosquitto thật** | ❌ Chưa chạy. `mqttlite` tuân MQTT 3.1.1 (CONNECT clean-session, QoS 0, PINGREQ) nên kỳ vọng tương thích, nhưng **chưa được kiểm chứng** |
| `docker compose up`, các Dockerfile | ❌ Chưa build/chạy (không có Docker). Viết theo đúng cấu trúc thư mục nhưng có thể cần chỉnh nhỏ |
| PostgreSQL | ❌ Chưa triển khai (chỉ có hướng dẫn chuyển) |
| Swagger UI (`/api/docs`) | ⚠️ Trang trả 200, `openapi.json` hợp lệ; giao diện Swagger tải từ CDN nên chưa xem được trong môi trường không Internet |
| Đăng nhập Admin/API, phân quyền | ✅ Đã làm & có test (`test_auth.py`, `test_ui_auth.py`) – xem `docs/SECURITY.md`. Token thu hồi/khoá đăng nhập chỉ nằm **trong bộ nhớ một tiến trình** |
| MQTT đăng nhập + ACL + TLS, ký HMAC | ✅ Đã làm & có test với **`tools/dev_broker.py`** (`test_mqtt_security.py`) và kiểm tra chéo C++↔Python. ❌ **Chưa chạy với Mosquitto thật**: `mosquitto/secure/mosquitto.conf`, `secrets/mosquitto/{acl,make_passwd.sh}` và profile `secure` của Docker Compose chưa được thử |
| TLS trên ESP32 thật | ❌ `WiFiClientSecure` + `MQTT_CA_PEM` mới chỉ được biên dịch thử với header giả lập; chưa chạy trên board |
| TLS cho HTTP/WebSocket của Backend | ❌ Chưa có (token Bearer đi dạng rõ nếu không đặt reverse proxy HTTPS). CORS mặc định vẫn `*` |
| Bảo mật vật lý/firmware (secure boot, flash encryption, OTA ký) | ❌ Chưa làm |
| API điều khiển Simulator `:8090` | ⚠️ Không xác thực; chỉ an toàn nhờ bind `127.0.0.1` |
| `X-Forwarded-For`, token mất khi restart (không đặt `TOKEN_SECRET`), chống phát lại sau restart | ⚠️ Giới hạn đã biết – xem `docs/SECURITY.md` §6 |
| Firmware ESP32 (`firmware/`) | ⚠️ Đã viết; logic (`cartcore`) có test + kiểm tra chéo với contract. **Chưa biên dịch bằng PlatformIO thật, chưa chạy trên board/linh kiện thật** (xem `firmware/README.md`) |
| Hiệu năng/tải | ❌ Chưa đo. Một connection SQLite + RLock phù hợp quy mô demo (vài chục xe) |
| Mất message QoS 0 khi offline | ⚠️ Giới hạn đã biết: scan gửi lúc offline bị mất (xem `docs/mqtt/MQTT_CONTRACT.md` §5) |
| Lịch sử lệnh | ⚠️ Lưu trong bộ nhớ, mất khi restart Backend |
