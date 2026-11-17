# Smart Shopping Cart – Hệ thống Xe đẩy hàng Thông minh IoT

Hệ thống IoT mô phỏng trọn vẹn luồng **Thiết bị xe đẩy (`CART_001..003` / ESP32 Wokwi) ⇄ MQTT Broker ⇄ Backend (FastAPI + Alert Engine + WebSocket) ⇄ Database (SQLite / PostgreSQL) ⇄ Giao diện Web (Khách hàng, Quản trị tích hợp Bản đồ 2D & Simulator phần cứng)**.

> **Phạm vi triển khai:** Project chạy theo mô hình IoT mô phỏng (Python Simulator và firmware ESP32 trên Wokwi/PlatformIO), không yêu cầu phần cứng vật lý. Trên Bản đồ Siêu thị 2D tích hợp trong `/admin`, tọa độ `(x, y)` là vị trí mô phỏng Digital Twin trên Frontend; dữ liệu pin, cân nặng, giỏ hàng và cảnh báo được truyền qua MQTT/Backend/WebSocket.

```
Python Simulator (3 xe, :8090) ─┐
                                 ├──▶ MQTT Broker (:1883 / TLS :8883)
ESP32 Firmware (Wokwi / thật)   ─┘            │
                                              ▼
                               Backend FastAPI (:8000) ⇄ SQLite / PostgreSQL
                                 ├── REST API    (/api/*, Swagger /docs)
                                 └── WebSocket   (ws://localhost:8000/ws)
                                              │
                                              ▼
                       React UI: /customer · /admin (gồm Bản đồ 2D) · /simulator
```

---

## 1. Các màn hình chính sau khi khởi chạy

| Đường dẫn | Màn hình | Yêu cầu đăng nhập |
| :--- | :--- | :--- |
| `http://localhost:8000/` | Trang chủ chọn giao diện | Không |
| `http://localhost:8000/customer` | Giao diện Khách hàng (chọn xe, quét/xem giỏ, thanh toán) | Không |
| `http://localhost:8000/admin` | **Quản trị & Bản đồ Siêu thị 2D (Digital Twin)** — KPI tổng quan, bản đồ SVG di chuyển hành lang, kịch bản IoT, Live Event Log, danh sách xe, cảnh báo, khoá/mở xe | Có (in sẵn ở terminal khi chạy) |
| `http://localhost:8000/simulator` | Simulator phần cứng (LCD, LED MQTT, cân, pin, ngắt mạng) | Có (cùng tài khoản Admin) |
| `http://localhost:8000/docs` | Tài liệu REST API tương tác (Swagger UI · ReDoc tại `/redoc`) | Xem được schema |

> Lưu ý bảo mật: Nếu chưa cấu hình `ADMIN_PASSWORD`, Backend và các script khởi chạy sẽ **tự sinh mật khẩu ngẫu nhiên cho `admin`** và in ra ngay trên terminal lúc khởi động. Để dùng mật khẩu cố định khi dev cục bộ, đặt biến `ADMIN_PASSWORD`, hoặc tắt xác thực tạm thời bằng `AUTH_ENABLED=0` (chỉ dùng nội bộ DEV).

---

## 2. Yêu cầu môi trường & Cài đặt ban đầu

- **Python ≥ 3.11** (bắt buộc để chạy Backend, MQTT dev broker và Simulator)
- **Node.js ≥ 20** *(chỉ cần nếu bạn sửa code React và muốn build lại `frontend/dist`; bản build sẵn đã có trong repo)*
- **Docker & Docker Compose** *(chỉ cần nếu chạy bằng container)*

Cài đặt thư viện Python tại thư mục gốc của project (`smart-shopping-cart/`):

```bash
pip install -r requirements.txt
```

*(Nên tạo virtualenv nếu muốn tách môi trường: `python -m venv .venv` rồi kích hoạt trước khi chạy `pip install`.)*

---

## 3. Hướng dẫn chạy Project

### Cách 1: Chạy nhanh bằng 1 lệnh (Khuyên dùng cho máy cá nhân, không cần Docker)

Script tự khởi động **3 tiến trình**: MQTT dev broker (`:1883`) + Backend FastAPI/WebSocket (`:8000`) + Simulator 3 xe (`:8090`), tự động dùng SQLite (`./data/smartcart.db`) nếu bạn chưa cấu hình PostgreSQL.

**Trên Windows (PowerShell):**

```powershell
.\scripts\run_local.ps1
```

- Script tự động nạp `.env` (nếu có), kiểm tra/giải phóng các cổng `1883, 8000, 8081, 8090` nếu bị kẹt tiến trình cũ, chờ `/api/health` sẵn sàng và in ra đầy đủ URL + tài khoản đăng nhập Admin.
- Nhấn `Ctrl + C` để dừng toàn bộ dịch vụ.

**Trên Linux / macOS / Git Bash:**

```bash
bash scripts/run_local.sh
```

**Chế độ bảo mật đầy đủ trên Linux / macOS** *(MQTT username/ACL + TLS 8883 + ký HMAC từng message; cần Mosquitto & OpenSSL)*:

```bash
bash scripts/run_secure.sh
```
*(Lần đầu tự chạy `python -m tools.provision` để sinh cấu hình & chứng chỉ trong `./secrets/`.)*

---

### Cách 2: Chạy thủ công từng tiến trình (3 terminal riêng)

Dùng cách này khi bạn muốn xem log tách biệt hoặc dùng **CLI tương tác** trực tiếp của Simulator. Mở 3 terminal tại thư mục gốc dự án:

**Terminal 1 — MQTT Broker thử nghiệm** *(bỏ qua nếu máy bạn đã chạy Mosquitto ở cổng `1883`)*:

```bash
python -m tools.dev_broker --host 127.0.0.1 --port 1883
```

**Terminal 2 — Backend FastAPI + WebSocket + Web UI:**

*Windows PowerShell:*
```powershell
$env:DB_BACKEND="sqlite"
$env:ADMIN_PASSWORD="admin123"   # tùy chọn; bỏ trống để tự sinh ngẫu nhiên
python -m backend.main
```

*Linux / macOS:*
```bash
DB_BACKEND=sqlite ADMIN_PASSWORD=admin123 python -m backend.main
```

**Terminal 3 — Python Simulator (3 xe `CART_001..003` + HTTP Control API `:8090`):**

```bash
python -m simulator.main
```

Các tuỳ chọn thường dùng cho Simulator:
- `python -m simulator.main --no-cli` : chạy nền không mở dấu nhắc CLI (phù hợp khi điều khiển trực tiếp trong `/admin` hoặc `/simulator`).
- `python -m simulator.main --auto` : tự động sinh kịch bản quét hàng định kỳ.
- Lệnh trong CLI tương tác: `carts`, `catalog`, `scan <xe> <STT|barcode> [remove]`, `unknown <xe>`, `low-battery <xe> [%]`, `recharge <xe>`, `weight <xe> <±g>`, `fix-weight <xe>`, `offline <xe> [giây]`, `online <xe>`, `log <xe>`, `quit`.

---

### Cách 3: Chạy bằng Docker Compose (PostgreSQL 16 + Mosquitto + Backend + Simulator)

```bash
cp .env.example .env
docker compose --profile sim up --build
```

Sau khi container chạy lên:
- Giao diện Web & API: `http://localhost:8000`
- Simulator Control API: `http://localhost:8090/sim/carts`
- PostgreSQL 16: `localhost:5432` · Mosquitto MQTT: `localhost:1883` (WS `9001`)
- Mở CLI điều khiển Simulator trong container (khi cần gõ lệnh tay):

```bash
docker compose exec simulator python -m simulator.main
```

Dừng container: `docker compose --profile sim down` (thêm `-v` nếu muốn xoá volume database).

> **Lưu ý khi dùng file `.env` ngoài Docker:** File `.env.example` đặt mặc định `DB_BACKEND=postgres`. Nếu bạn copy `.env.example` thành `.env` rồi chạy cục bộ không có PostgreSQL, hãy đổi dòng đó thành `DB_BACKEND=sqlite`.

---

## 4. Build hoặc chạy chế độ phát triển Frontend (React 19 + esbuild)

Backend mặc định phục vụ file tĩnh đã build sẵn tại `frontend/dist/`. Khi chỉnh sửa mã nguồn trong `frontend/src/`, build lại bằng:

```bash
cd frontend
npm install        # chỉ cần chạy lần đầu
npm run build      # tạo dist/assets/app.js và dist/assets/app.css
```

- Chạy dev watch server (tự rebuild khi sửa file): `npm run dev`
- Xem nhanh UI không cần chạy Backend/Simulator (dữ liệu giả lập trong trình duyệt): truy cập `http://localhost:8000/admin?mock=1` (`?mock=0` để tắt).

---

## 5. Mô phỏng phần cứng ESP32 (PlatformIO & Wokwi)

Mã nguồn firmware ESP32 nằm trong `firmware/`:
- Tài liệu chi tiết: [`firmware/README.md`](firmware/README.md) và [`docs/HUONG_DAN_PLATFORMIO_WOKWI.md`](docs/HUONG_DAN_PLATFORMIO_WOKWI.md).
- Mô phỏng Wokwi nối vào hệ thống qua broker công cộng: xem `scripts/run_online_demo.ps1` (Windows) hoặc `scripts/run_online_demo.sh` (Linux/macOS).
- Mô phỏng Wokwi cục bộ không cần Internet qua cầu nối Serial/TCP: `python -m tools.wokwi_bridge`.
- Chạy broker cho ESP32 thật trong cùng mạng LAN: đặt `MQTT_BIND=0.0.0.0` trước khi chạy broker và đăng ký mã xe mới qua `POST /api/carts`.

---

## 6. Kịch bản trải nghiệm nhanh (Demo)

Sau khi chạy hệ thống (ví dụ bằng `.\scripts\run_local.ps1`), đăng nhập Admin và mở **`http://localhost:8000/admin`** (có thể mở song song `/customer` ở tab khác):

1. **Quan sát đội xe trên bản đồ 2D:** Thấy 3 xe `CART_001`, `CART_002`, `CART_003` tại khu vực *Lối vào & Bãi xe*, kèm `Live Event Log` nhận sự kiện realtime qua WebSocket.
2. **Mở phiên & Quét hàng:** Chọn `CART_001` → bấm **Bắt đầu phiên** → chọn *Coca Cola lon 330ml* → bấm **Quét & Thêm** 2 lần. Xe tự động di chuyển dọc hành lang tới khu *Đồ uống & Sữa*, giỏ hàng tăng lên `24.000 ₫` (`2 món`, `710 g`) và đồng bộ ngay sang tab `/customer`.
3. **Thử các tình huống bất thường IoT:**
   - Bấm **Quét mã lạ** → hệ thống báo từ chối (`SCAN_REJECTED`).
   - Bấm **Lệch cân +250g** → mở cảnh báo `WEIGHT_MISMATCH`; bấm **Cân chuẩn 0g** → tự động đóng cảnh báo.
   - Chọn `CART_002` → bấm **Pin 15%** → icon xe chuyển màu cam cảnh báo `LOW_BATTERY`; bấm **Sạc 100%** để phục hồi.
   - Chọn `CART_003` → bấm **Ngắt mạng** → sau timeout heartbeat (~15s) xe chuyển xám `Offline` và phát cảnh báo `OFFLINE`; bấm **Kết nối lại** để phục hồi.
4. **Thanh toán:** Chọn `CART_001` → bấm **Checkout** → phiên kết thúc, xe di chuyển tới *Quầy thanh toán* và chuyển trạng thái xanh dương `Vừa Checkout`.

---

## 7. Bảng cổng & cấu hình biến môi trường

Toàn bộ cấu hình qua biến môi trường xem tại **[`.env.example`](.env.example)**.

| Dịch vụ / Giao thức | Cổng mặc định | Ghi chú |
| :--- | :---: | :--- |
| Backend REST API + React UI + WebSocket (`/ws`) | `8000` | Swagger `/docs` & `/api/docs`; `WS_PORT` mặc định `8000` (Docker map thêm `8081`) |
| Simulator HTTP Control API | `8090` | Chỉ lắng nghe `127.0.0.1` ở local (`0.0.0.0` trong Docker); đặt `--control-port 0` để tắt |
| MQTT Broker | `1883` | `8883` cho MQTT TLS (`run_secure.sh`); `9001` MQTT-over-WS (Mosquitto Docker) |
| PostgreSQL 16 | `5432` | Dùng khi `DB_BACKEND=postgres` |

Ngưỡng cảnh báo mặc định: Pin yếu `< 20%` (`BATTERY_LOW_PERCENT`), lệch cân `> 100g` (`WEIGHT_TOLERANCE_G`), mất kết nối `> 15s` (`HEARTBEAT_TIMEOUT_S`).

---

## 8. Kiểm thử tự động (Unit · Integration · Playwright E2E)

Cài đặt công cụ kiểm thử (lần đầu):

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
```

Chạy kiểm thử:

```bash
# Toàn bộ unit + integration + E2E trình duyệt
python -m pytest tests -v

# Chạy riêng bộ E2E cho màn hình Mô phỏng Siêu thị 2D
python -m pytest tests/e2e/test_simulation_2d.py -v

# Chạy toàn bộ E2E giao diện
python -m pytest tests/e2e -v
```

*(Lưu ý: các bài test biên dịch/chạy firmware C++ trong `test_wokwi_package.py`, `test_firmware_protocol.py` và `test_wokwi_bridge.py` sẽ tự `SKIPPED` nếu máy chưa cài trình biên dịch `g++` / Wokwi CLI.)*

---

## 9. Tài liệu kỹ thuật & Cấu trúc thư mục

| Tài liệu | Nội dung |
| :--- | :--- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Kiến trúc tổng thể, luồng nghiệp vụ, đa luồng |
| [docs/BAT_DAU_NHANH.md](docs/BAT_DAU_NHANH.md) | Hướng dẫn bắt đầu nhanh từ mã nguồn / file zip |
| [docs/HUONG_DAN_SU_DUNG.md](docs/HUONG_DAN_SU_DUNG.md) | Hướng dẫn sử dụng Khách hàng, Quản trị, Simulator, ESP32 |
| [docs/HUONG_DAN_PLATFORMIO_WOKWI.md](docs/HUONG_DAN_PLATFORMIO_WOKWI.md) | Build & mô phỏng PlatformIO / Wokwi |
| [docs/2d-simulation/IMPLEMENTATION_REPORT.md](docs/2d-simulation/IMPLEMENTATION_REPORT.md) | Thiết kế & tích hợp Bản đồ Siêu thị 2D trong `/admin` |
| [docs/2d-simulation/TEST_REPORT.md](docs/2d-simulation/TEST_REPORT.md) | Báo cáo kiểm thử E2E màn hình 2D & toàn hệ thống |
| [docs/SECURITY.md](docs/SECURITY.md) | Bảo mật, phân quyền, MQTT ACL + TLS, chữ ký HMAC |
| [docs/mqtt/MQTT_CONTRACT.md](docs/mqtt/MQTT_CONTRACT.md) | Giao thức MQTT (6 topic, envelope, payload, reconnect) |
| [docs/api/API.md](docs/api/API.md) | REST API, mã lỗi và sự kiện WebSocket |
| [docs/database/DATABASE.md](docs/database/DATABASE.md) | Thiết kế CSDL 6 bảng & cấu hình PostgreSQL |
| [docs/DEVIATIONS.md](docs/DEVIATIONS.md) | Sai khác so với thiết kế ban đầu & giới hạn |

```text
backend/     FastAPI, REST API, WebSocket (/ws), Alert Engine, MQTT consumer, ORM/DB
simulator/   Python Simulator 3 xe (CLI, scenarios, HTTP Control API :8090)
frontend/    React 19 + esbuild: customer/, admin/, simulation/ (2D Digital Twin), simulator/, dist/
firmware/    Mã nguồn ESP32 (PlatformIO + cấu hình Wokwi)
shared/      MQTT contract, lightweight MQTT client, bảo mật/HMAC
tools/       dev_broker, provision (TLS/ACL/HMAC), wokwi_bridge, gen_postman
tests/       unit/, integration/, e2e/ (Playwright Chromium)
scripts/     run_local.ps1|.sh, run_secure.sh, run_online_demo.ps1|.sh
data/        products_seed.json, carts_seed.json, smartcart.db (SQLite khi chạy local)
docs/        Tài liệu kiến trúc, sử dụng, bảo mật, báo cáo & ảnh chụp kiểm thử
```
