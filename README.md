# Smart Shopping Cart – Hệ thống giỏ hàng thông minh IoT

Hệ thống mô phỏng đầy đủ: **3 xe đẩy giả lập → MQTT → Backend (REST + realtime + luật cảnh báo) → CSDL → Giao diện Khách hàng & Quản trị**.
Xây theo `Noi_dung_IOT_chinh_sua.docx` / `Phan_cong_IOT_chinh_sua.xlsx` (xem **[docs/DEVIATIONS.md](docs/DEVIATIONS.md)** cho các điểm khác stack dự kiến và phần chưa kiểm chứng).

```
Simulator (3 xe) ⇄ MQTT broker ⇄ Backend ⇄ SQLite
                                     ├── REST  /api        ┐
                                     └── WebSocket :8081   ┴─▶ React: /customer  ·  /admin
```

## Chạy nhanh (không cần Docker)

Yêu cầu: Python ≥ 3.11 (`pip install -r requirements.txt`). Frontend đã build sẵn ở `frontend/dist`.

```bash
scripts/run_local.sh          # dev broker :1883 + Backend :8000 (WS :8081) + Simulator 3 xe
# mở http://localhost:8000   (khách dùng không cần đăng nhập; trang /admin cần mật khẩu – in ra màn hình khi chạy)
```

Bản **bảo mật đầy đủ** (đăng nhập, MQTT user/ACL/TLS, ký HMAC từng message):

```bash
bash scripts/run_secure.sh    # lần đầu tự chạy `python -m tools.provision` để sinh ./secrets (mật khẩu admin in ra màn hình)
```

Chi tiết, đối chiếu OWASP IoT Top 10 và **các giới hạn còn lại**: [docs/SECURITY.md](docs/SECURITY.md).

Hoặc chạy từng phần (3 terminal):

```bash
python -m tools.dev_broker            # broker thử nghiệm (có Mosquitto thì dùng nó)
python -m backend.main                # API + giao diện + WebSocket
python -m simulator.main              # 3 xe + CLI tương tác + API điều khiển :8090 (thêm --auto để tự quét hàng)
```

## Phần cứng thật (ESP32 + PlatformIO)

Thư mục [`firmware/`](firmware/README.md) chứa firmware ESP32 (quét mã vạch UART, cân HX711, OLED, còi/LED, nút, đo pin) kết nối cùng hệ thống qua MQTT.
Thanh toán vẫn ở màn hình web; xe chỉ quét, báo cân/pin/trạng thái và hiển thị. Xem đấu dây, cấu hình, hiệu chuẩn và **phạm vi đã/chưa kiểm chứng** trong [`firmware/README.md`](firmware/README.md).
Mô phỏng Wokwi nối hệ thống qua broker công cộng: xem [`firmware/README.md`](firmware/README.md) (Bước 0b) và `scripts/run_online_demo.ps1|.sh`.
Mô phỏng Wokwi nối hệ thống không cần Internet: cầu nối `python -m tools.wokwi_bridge` (Bước 0c).
Chạy broker cho mạng LAN: `MQTT_BIND=0.0.0.0 scripts/run_local.sh`; đăng ký xe thật: `POST /api/carts`.

## Simulator phần cứng (giao diện web)

Mở **http://localhost:8000/simulator** (hoặc thẻ "Simulator phần cứng" ở trang chủ). Mỗi xe giả lập hiển thị như một thiết bị:
màn hình LCD, đèn LED kết nối MQTT, máy quét mã vạch, cảm biến cân, pin, nút ngắt mạng, bộ đếm gói tin và nhật ký.
Mọi thao tác đi qua MQTT giống phần cứng thật và thấy ngay ở `/customer` và `/admin`; cột "Hệ thống thấy" cho biết Backend đang ghi nhận gì về xe đó.

Trang này gọi API điều khiển của tiến trình Simulator (cổng 8090, chỉ lắng nghe `127.0.0.1`, không có xác thực – chỉ dùng DEV).
Nếu thấy "Không kết nối được tới Simulator" nghĩa là tiến trình `python -m simulator.main` chưa chạy.
Đổi địa chỉ: `?sim=http://host:port` trên URL hoặc `VITE_SIM_URL` khi build; tắt API điều khiển: `--control-port 0`.

Build lại frontend (cần Node ≥ 20): `cd frontend && npm install && npm run build`.
Không có Backend? `http://localhost:8000/admin?mock=1` chạy giao diện bằng dữ liệu giả (`?mock=0` để tắt).

## Docker Compose (chưa chạy thử trong môi trường build – xem DEVIATIONS)

```bash
cp .env.example .env
docker compose --profile sim up --build     # Mosquitto + Backend(+UI) + Simulator
docker compose exec simulator python -m simulator.main   # CLI điều khiển xe (xe do tiến trình nền đã chạy)
```

## Kịch bản demo (3 phút)

Mở 3 tab: `/customer`, `/admin`, `/simulator`. (Mỗi bước làm được bằng trang `/simulator` **hoặc** bằng lệnh CLI tương ứng.)

1. **Khách:** tab `/customer` → chọn `CART_001` → *Bắt đầu mua sắm*.
2. **Quét hàng:** tab `/simulator`, thẻ CART_001: chọn *Coca Cola* → *Quét · bỏ vào giỏ* hai lần, rồi Oreo một lần (CLI: `scan 1 1`, `scan 1 1`, `scan 1 3`) → giỏ hàng khách tự cập nhật (39.000 ₫).
3. **Cảnh báo lệch cân:** *+250 g vật lạ* (CLI: `weight 1 250`) → khách hiện "Lệch cân" (> 100 g); *Bỏ vật lạ* (`fix-weight 1`) → tự hết.
4. **Cảnh báo pin:** thẻ CART_002 → *Pin yếu 15%* (`low-battery 2 12`) → `/admin` hiện "Pin yếu" tức thì; *Sạc đầy* (`recharge 2`) → hết.
5. **Mất kết nối:** thẻ CART_003 → *Ngắt kết nối* (`offline 3`) → sau ~15 s xe thành Offline + cảnh báo; *Kết nối lại* (`online 3`) → tự phục hồi.
6. **Quản trị:** `/admin/carts/CART_001` → *Khoá xe* → xe ACK → trạng thái *Đã khoá*; màn khách hiện banner khoá.
7. **Thanh toán:** *Thanh toán → Xác nhận* → "Shopping Completed – Thank you!".

Lệnh CLI: `carts`, `catalog`, `scan <xe> <STT|mã vạch> [remove]`, `unknown <xe>`, `low-battery <xe> [%]`, `recharge <xe>`, `weight <xe> <±g>`, `fix-weight <xe>`, `offline <xe> [giây]`, `online <xe>`, `log <xe>`, `quit`.

## Cổng & cấu hình

| Dịch vụ | Cổng |
|---|---|
| Giao diện + REST | 8000 (`/api/docs` = Swagger; `/simulator` = Simulator phần cứng) |
| API điều khiển Simulator | 8090 (chỉ localhost) |
| WebSocket | 8081 (`/ws`) |
| MQTT | 1883 (WebSocket 9001 nếu dùng Mosquitto) · **8883 = MQTT qua TLS** (`run_secure.sh`) |

Toàn bộ cấu hình qua biến môi trường – xem **[.env.example](.env.example)** (ngưỡng cảnh báo: pin < 20 %, lệch cân > 100 g, offline > 15 s).

## Kiểm thử

```bash
pip install -r requirements-dev.txt && python -m playwright install chromium
python -m pytest tests -q        # unit + tích hợp (MQTT thật) + E2E trình duyệt
```

Chi tiết và kết quả: **[docs/TESTING.md](docs/TESTING.md)**. Ảnh giao diện do E2E chụp: `docs/screenshots/`.

## Tài liệu

| | |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Kiến trúc, luồng nghiệp vụ, đa luồng |
| [docs/BAT_DAU_NHANH.md](docs/BAT_DAU_NHANH.md) | **Bắt đầu nhanh từ file zip**: giải nén, mở đúng thư mục, cài đặt, chạy web / Wokwi / PlatformIO |
| [docs/HUONG_DAN_SU_DUNG.md](docs/HUONG_DAN_SU_DUNG.md) | **Hướng dẫn sử dụng**: chạy, khách hàng, quản trị, Simulator, ESP32, xử lý sự cố |
| [docs/HUONG_DAN_PLATFORMIO_WOKWI.md](docs/HUONG_DAN_PLATFORMIO_WOKWI.md) | **Hướng dẫn PlatformIO & Wokwi**: build, mô phỏng 3 cách, nạp ESP32 thật |
| [docs/SECURITY.md](docs/SECURITY.md) | Mô hình đe doạ, OWASP IoT Top 10, vai trò/quyền, MQTT ACL+TLS, chữ ký HMAC, giới hạn |
| [docs/mqtt/MQTT_CONTRACT.md](docs/mqtt/MQTT_CONTRACT.md) | 6 topic, envelope, payload, hành vi reconnect |
| [docs/api/API.md](docs/api/API.md) | REST, mã lỗi, sự kiện WebSocket |
| [docs/database/DATABASE.md](docs/database/DATABASE.md) | 6 bảng, ràng buộc, chuyển sang PostgreSQL |
| [docs/DEVIATIONS.md](docs/DEVIATIONS.md) | Khác biệt stack, mở rộng, phần chưa kiểm chứng |
| `postman/` | Collection + environment (sinh bằng `python -m tools.gen_postman`) |

## Cấu trúc

```
shared/      contract.py · mqttlite.py          backend/    api · services · alerts · mqtt · realtime · database
simulator/   cart · mqtt · scenarios · cli · control   frontend/   src/{customer,admin,simulator,common,api,state}
tools/       dev_broker · provision · gen_postman           tests/      unit · integration · e2e
data/        products_seed.json · carts_seed.json    mosquitto/config/   docker-compose.yml   scripts/
```
