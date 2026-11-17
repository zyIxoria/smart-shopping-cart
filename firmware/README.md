# Firmware Smart Cart (ESP32 + PlatformIO)

> Hướng dẫn thao tác gọn từng bước (build, Wokwi 3 cách, nạp board thật, lỗi thường gặp): [docs/HUONG_DAN_PLATFORMIO_WOKWI.md](../docs/HUONG_DAN_PLATFORMIO_WOKWI.md).

Firmware thật cho xe đẩy: **quét mã vạch**, **báo cân/pin/trạng thái**, **nhận lệnh khoá/mở khoá/bắt đầu/kết thúc phiên** và hiển thị trạng thái.
Xe nói chuyện với Backend qua MQTT đúng [MQTT contract](../docs/mqtt/MQTT_CONTRACT.md), nên xuất hiện ngay ở giao diện `/customer` và `/admin`
như xe giả lập. **Thanh toán vẫn thực hiện trên màn hình web của khách** (xe chỉ báo kết quả: khi Backend gửi `END_SESSION`, OLED hiện "CAM ON!" và còi kêu).

> ⚠️ **Trạng thái kiểm chứng** – xem cuối file. Phần logic (`lib/cartcore`) đã được test; phần nối phần cứng `src/main.cpp`
> **chưa được biên dịch bằng PlatformIO thật và chưa chạy trên board** (môi trường phát triển không có PlatformIO/mạng/ESP32).
> Hãy coi lần build đầu tiên là bước kiểm tra, có thể cần chỉnh nhỏ.

## Linh kiện & đấu dây

| Linh kiện | Chân module | Chân ESP32 DevKit | Ghi chú |
|---|---|---|---|
| Máy quét UART GM65/GM66/GM861 | TX / RX / VCC / GND | **GPIO16 (RX2)** / GPIO17 (TX2) / 5V / GND | TX module → RX ESP32. Bật chế độ UART 9600 8N1, kết thúc bằng CR (mặc định). Module 5 V có TX mức 3,3 V thì nối thẳng được; nếu TX ra 5 V phải qua chia áp |
| HX711 + load cell | DT / SCK / VCC / GND | GPIO32 / GPIO33 / 3V3 / GND | Cấp 3V3 để mức logic an toàn cho ESP32 |
| OLED SSD1306 128×64 I2C | SDA / SCL / VCC / GND | GPIO21 / GPIO22 / 3V3 / GND | Địa chỉ 0x3C (đổi `OLED_I2C_ADDR`) |
| Còi buzzer **active** | + / − | GPIO25 / GND | Còi passive cần đổi code sang `tone()` |
| LED xanh / đỏ | anode | GPIO26 / GPIO27 (qua điện trở 220–330 Ω) | Cathode nối GND |
| Nút MODE | một chân | GPIO13, chân kia nối GND | Bấm ngắn: đổi **THÊM ↔ BỎ HÀNG** cho đúng 1 lần quét |
| Nút TARE | một chân | GPIO14, chân kia nối GND | **Giữ 2 giây**: về 0 cân (chỉ khi chưa có phiên) |
| Đo pin | Pin+ —R1— **GPIO34** —R2— GND | GPIO34 (ADC1) | R1 = R2 = 100 kΩ → `BATTERY_DIVIDER_RATIO 2.0`. Pin LiPo 1S (3,3–4,2 V) |

Đổi chân tại [`include/pins.h`](include/pins.h). Không dùng chân ADC2 để đo pin (xung đột Wi-Fi).
Nếu chạy bằng USB không có pin, đặt `#define BATTERY_ENABLED 0` để luôn báo 100 %.

## Bước 0 – Mô phỏng khi chưa có linh kiện (Wokwi)

Dự án có sẵn `diagram.json` (ESP32 + OLED + HX711 + còi + 2 LED + 2 nút; OLED dùng linh kiện `board-ssd1306` vì `wokwi-ssd1306` đã bị Wokwi ngừng hỗ trợ) và `wokwi.toml`, nên chạy được trong VS Code mà không cần board.

1. Cài extension **Wokwi Simulator** trong VS Code. Nhấn `F1` → **Wokwi: Request a new License** (đăng nhập tài khoản Wokwi miễn phí, bấm xác nhận).
2. Build firmware mô phỏng (Wokwi không tự build): ở thanh dưới chọn env `esp32dev_sim` rồi bấm **Build ✓**, hoặc `pio run -e esp32dev_sim`.
3. Mở thư mục `firmware` trong VS Code, nhấn `F1` → **Wokwi: Start Simulator**. Cửa sổ mô phỏng hiện OLED, LED, còi và nút; log và ô gõ lệnh nằm ở panel Serial của Wokwi.
4. Mô phỏng không có máy quét mã vạch và Wi-Fi tới máy bạn, nên: quét bằng lệnh `scan <mã>`; cân bằng lệnh `weight <gram>`; pin bằng `battery <phần trăm>` (các env mô phỏng tắt đo pin thật nên không có biến trở); nút MODE/TARE bấm bằng chuột (giữ chuột 2 giây cho TARE).

| Lệnh giả lập | Tác dụng |
|---|---|
| `scan 8934588012341` | Như vừa quét mã vạch: OLED hiện mã, còi kêu, dòng `[local] .../scan {...}` hiện trong log |
| `weight 750` / `weight auto` | Đặt số cân là 750 g / quay lại đọc cảm biến |
| `battery 15` / `battery auto` | Đặt pin 15 % (LED đỏ nháy + "PIN YEU!") / quay lại đo thật |
| `lock`, `unlock`, `start`, `end` | Giả lập lệnh của Backend: kiểm tra OLED, LED, còi |

> Lưu ý: tên linh kiện/chân trong `diagram.json` đã được **đối chiếu với tài liệu Wokwi** và có test tĩnh (`tests/unit/test_wokwi_package.py`), nhưng file **chưa được mở thử trong Wokwi thật**. Nếu một dây báo sai tên chân thì kéo lại dây trong giao diện Wokwi; không ảnh hưởng tới firmware.
> Wokwi gói miễn phí không cho ESP32 nối tới MQTT broker trên máy bạn, nên chế độ mô phỏng là độc lập (không liên kết hệ thống).

> **Không muốn cài gì?** Thư mục [`wokwi-web/`](wokwi-web/) là gói để dán lên https://wokwi.com (Wokwi tự biên dịch trong trình duyệt, không cần PlatformIO). Xem [HUONG_DAN_PLATFORMIO_WOKWI.md](../docs/HUONG_DAN_PLATFORMIO_WOKWI.md) mục 3. Sinh lại bằng `python3 tools/make_wokwi_web.py` sau khi sửa `src/` hoặc `lib/`.

## Bước 0b – Mô phỏng Wokwi LIÊN KẾT với hệ thống web (qua broker MQTT công cộng)

Wokwi (gói miễn phí) không nối được vào máy của bạn, nhưng có Internet qua Wi-Fi ảo `Wokwi-GUEST`. Vì vậy firmware trong Wokwi và Backend trên máy bạn cùng nối vào **một broker MQTT công cộng** (`broker.hivemq.com`).
Xe mô phỏng khi đó hiện ở `/customer`, `/admin` và nhận lệnh khoá/mở khoá từ Backend.

> ⚠️ Broker công cộng **không có mật khẩu**. Để tin nhắn của bạn không lẫn với người khác, dự án dùng một **gốc topic riêng** (`MQTT_TOPIC_ROOT`) và **mã xe riêng**, đặt trong [`include/wokwi_online.h`](include/wokwi_online.h) (đã sinh sẵn giá trị ngẫu nhiên – bạn nên đổi thành chuỗi của riêng mình).
> Ai biết gốc topic + mã xe đều đọc/gửi được tin nhắn của xe; chỉ dùng dữ liệu demo, không dùng trong sản xuất.

1. **Phía Backend** (từ thư mục gốc dự án, KHÔNG chạy `run_local.sh`/Simulator cùng lúc):
   - Windows PowerShell: `powershell -ExecutionPolicy Bypass -File scripts\run_online_demo.ps1`
   - Linux/macOS: `scripts/run_online_demo.sh`

   Script đọc `wokwi_online.h`, nối Backend vào broker với đúng gốc topic và tự đăng ký xe sau 5 giây. Mở http://localhost:8000.
2. **Phía firmware:** mở `firmware/wokwi.toml`, đổi hai dòng `esp32dev_sim` thành `esp32dev_wokwi_online`; chọn env `esp32dev_wokwi_online` ở thanh dưới của VS Code, bấm **Build ✓**, rồi **F1 → Wokwi: Start Simulator**.
3. Trong Wokwi Terminal sẽ thấy `[wifi] da ket noi`, `[mqtt] da ket noi + subscribe`. Sau vài giây xe có mã trong `wokwi_online.h` chuyển **ONLINE** ở `/admin`.
4. Thử: ở `/customer` chọn xe đó → bắt đầu phiên → trong Wokwi Terminal gõ `scan 8934588012341` (xem mã vạch hợp lệ ở `/customer`) → giỏ hàng cập nhật; `weight 750` → số cân lên `/admin`; ở `/admin` bấm Khoá xe → LED đỏ trong Wokwi sáng.

Nếu không thấy ONLINE: kiểm tra Terminal Wokwi có dòng `[mqtt] that bai rc=...` không; thử đổi `MQTT_HOST` sang `broker.emqx.io` (ở cả `wokwi_online.h`; script Backend tự đọc lại) rồi build lại.

## Bước 0c – Mô phỏng Wokwi liên kết hệ thống bằng CẦU NỐI Serial ↔ MQTT (không cần Internet)

Cách này giữ dữ liệu **trong máy bạn**: Wokwi mở cổng Serial của mạch ra TCP (`rfc2217ServerPort = 4000` đã có sẵn trong `wokwi.toml`), script `tools/wokwi_bridge.py` đọc các dòng `[local] ...` do firmware in ra rồi gửi lên MQTT broker trên máy bạn, và chuyển lệnh khoá/mở khoá/bắt đầu/kết thúc phiên của Backend ngược vào firmware.

```
Wokwi (firmware esp32dev_sim_bridge) ⇄ Serial/TCP:4000 ⇄ tools/wokwi_bridge.py ⇄ MQTT broker (máy bạn) ⇄ Backend ⇄ /customer, /admin
```

Mở **4 cửa sổ terminal** tại thư mục gốc dự án (Windows PowerShell hoặc bất kỳ):

1. Broker: `python -m tools.dev_broker`
2. Backend + giao diện: `python -m backend.main` (mở http://localhost:8000)
3. Wokwi: trong `firmware/wokwi.toml` đổi hai dòng `esp32dev_sim` thành `esp32dev_sim_bridge`; chọn env `esp32dev_sim_bridge`, **Build ✓**, rồi **F1 → Wokwi: Start Simulator** và **để tab mô phỏng đang hiển thị** (nếu ẩn, mô phỏng tạm dừng và Serial không chạy).
4. Cầu nối: `python -m tools.wokwi_bridge --cart-id WK_BRIDGE` (tự đăng ký xe `WK_BRIDGE` ở Backend; thêm `--no-register` nếu đã đăng ký).

Sau vài giây xe `WK_BRIDGE` chuyển **ONLINE** ở `/admin`. Thử: ở `/customer` chọn `WK_BRIDGE` → bắt đầu phiên (cầu nối chuyển `START_SESSION` vào firmware; OLED báo "BAT DAU MUA HANG"), rồi trong Wokwi Terminal gõ `scan <mã vạch hợp lệ>` → giỏ hàng cập nhật; `weight 750` → số cân lên `/admin`; ở `/admin` Khoá xe → LED đỏ sáng. Kết thúc phiên/thanh toán trên web → OLED "CAM ON!".

Lưu ý:
- Giờ trong mô phỏng không phải giờ thật, nên cầu nối **thay `message_id`, `timestamp`, `cart_id`** trước khi gửi lên MQTT (nếu không Backend sẽ loại message).
- Khi Backend nối lại, nó gửi lệnh đồng bộ trạng thái (vd. `END_SESSION`) cho xe vừa ONLINE – đó là hành vi bình thường.
- Cầu nối nối lại Serial tự động. Nếu log báo "mất kết nối Serial Wokwi", kiểm tra mô phỏng đang chạy và tab Wokwi đang hiển thị.
- Đổi cổng: `--wokwi-port`; đổi broker: `--mqtt-host/--mqtt-port` hoặc biến `MQTT_HOST/MQTT_PORT`; Backend ở máy khác: `--api`.
- Cầu nối này **đã được kiểm thử** với "Wokwi giả" (cùng logic firmware) và Backend thật, nhưng **chưa thử với Wokwi thật**.

## Bước 1 – Thử phần cứng độc lập (chưa cần liên kết hệ thống)

Env `esp32dev_standalone` **không dùng Wi-Fi, MQTT hay `cart_config.h`**. Xe tự bắt đầu một phiên mua hàng nội bộ; quét mã, cân, OLED, còi, LED và nút đều hoạt động,
còn các message lẽ ra gửi lên Backend được **in ra Serial** (`[local] smartcart/CART_DEMO/scan {...}`) để bạn xem đúng nội dung sẽ gửi.

```bash
cd firmware
pio run -e esp32dev_standalone -t upload
pio device monitor            # 115200 baud
```

Lúc khởi động firmware chạy **self-test** (OLED, HX711, pin, LED, còi, số byte nhận từ máy quét) và in kết quả. Có thể gõ lệnh trong Serial Monitor (kết thúc bằng Enter):

| Lệnh | Tác dụng |
|---|---|
| `help`, `status` | Xem lệnh / trạng thái (cân, pin, hệ số hiệu chuẩn, số byte máy quét) |
| `selftest` | Chạy lại tự kiểm tra |
| `scan 8934588012341` | Giả lập một lần quét (kiểm tra luồng khi chưa có máy quét) |
| `start`, `end`, `lock`, `unlock` | Giả lập lệnh từ Backend (kiểm tra OLED/LED/còi và ACK) |
| `tare` | Về 0 cân (chỉ khi chưa có phiên) |
| `cal 1000` | Hiệu chuẩn cân: xe trống → `tare` → đặt vật 1000 g lên cân → gõ lệnh; hệ số được **lưu vào bộ nhớ NVS**, không cần sửa code |

Các lệnh console cũng dùng được ở env `esp32dev` (chạy cùng hệ thống) để gỡ lỗi.

## Bước 2 – Chạy cùng hệ thống (Wi-Fi + MQTT)

```bash
cd firmware
cp include/cart_config.example.h include/cart_config.h      # rồi sửa: WIFI_SSID, WIFI_PASS, MQTT_HOST, CART_ID
pio run -e esp32dev -t upload                      # biên dịch + nạp
pio device monitor                                 # xem log (115200)
```

`MQTT_HOST` là **IP của máy chạy broker** trong cùng mạng LAN (không dùng `localhost`).

### Phía máy chủ

```bash
# 1) Cho broker (và Backend) nhận kết nối từ mạng LAN, không chỉ localhost
MQTT_BIND=0.0.0.0 scripts/run_local.sh            # hoặc dùng Mosquitto trong docker-compose
# 2) Đăng ký xe mới (Backend bỏ qua cart_id lạ)
curl -X POST http://localhost:8000/api/carts -H 'Content-Type: application/json' \
     -d '{"cart_id":"CART_004","name":"Xe thật số 4"}'
```

Mở tường lửa cho cổng 1883 trên máy chủ. Cấu hình trên **không có xác thực** – chỉ dùng trong mạng LAN tin cậy; để bật đăng nhập + TLS + ký HMAC xem mục dưới.

### Bảo mật MQTT (TLS + HMAC)

```bash
python -m tools.provision --carts CART_001,CART_004 --host 192.168.1.20   # IP/tên broker đưa vào chứng chỉ (SAN)
cp secrets/firmware/CART_004/cart_secrets.h firmware/include/              # file KHÔNG được commit (.gitignore)
# trong include/cart_config.h: CART_ID "CART_004", MQTT_HOST "192.168.1.20", MQTT_PORT 8883
pio run -e esp32dev -t upload
# máy chủ:  bash scripts/run_secure.sh
```

- `cart_secrets.h` chứa tài khoản MQTT của riêng xe, **khoá HMAC riêng của xe** (không phải khoá chủ) và chứng chỉ CA. Có file này firmware tự dùng đăng nhập + ký mọi gói gửi lên + kiểm chữ ký và độ mới (≤ 300 s) của lệnh nhận về; lệnh không ký/sai khoá/quá cũ bị bỏ và đếm ở dòng trạng thái `rejected`.
- `SECRETS_CART_ID` phải trùng `CART_ID`, nếu không firmware báo lỗi và không kết nối (tránh nạp nhầm khoá của xe khác).
- TLS cần **đồng hồ đúng** (kiểm tra hạn chứng chỉ): firmware đã chờ NTP xong mới kết nối. `MQTT_HOST` phải nằm trong SAN của chứng chỉ (`--host`).
- ⚠️ Phần TLS trên ESP32 mới biên dịch thử với header giả lập; **chưa chạy trên board thật**. Logic ký/kiểm (SHA-256/HMAC theo vector RFC 4231, bộ tách JSON) đã được test native và kiểm tra chéo với Python.

## Cách xe hoạt động

| Tình huống | Hành vi |
|---|---|
| Bật nguồn | OLED "Khoi dong", cân tự **về 0 (xe phải trống)**, nối Wi-Fi → đồng bộ giờ NTP → nối MQTT → gửi ngay heartbeat + telemetry |
| Heartbeat / telemetry | mỗi 5 s / 10 s; gửi ngay sau mỗi lệnh; sau lần quét thì chờ **3 s** để khách bỏ hàng vào xe rồi mới báo cân (tránh cảnh báo lệch cân giả) |
| Quét hàng | Mã hợp lệ → publish `scan` (ADD, hoặc REMOVE nếu vừa bấm MODE), còi 1 tiếng ngắn, OLED hiện mã |
| Quét khi **chưa có phiên / xe bị khoá / mất mạng** | Từ chối ngay tại xe: còi 3 tiếng, OLED nêu lý do (khoá/chưa phiên → gửi thêm event `SCAN_REJECTED`) |
| Mã lạ (ký tự không hợp lệ, quá ngắn/dài) | Bỏ qua + còi lỗi |
| `START_SESSION` | Lưu `session_id`, còi 1 tiếng. Lệnh lặp cùng phiên không làm gì thêm |
| `LOCK_CART` / `UNLOCK_CART` | LED đỏ sáng + còi dài / còi kép; gửi ACK + event `CART_LOCKED` / `CART_UNLOCKED` |
| `END_SESSION` (sau khi khách thanh toán trên web) | OLED "CAM ON!" 4 s + còi 3 nhịp |
| Lệnh trùng `command_id` | Không thực hiện lại, **vẫn gửi lại ACK** |
| Mất Wi-Fi/MQTT | LED xanh nhấp nháy; tự nối lại (backoff 0,5→8 s), subscribe lại, gửi heartbeat ngay; Backend đồng bộ lại trạng thái xe |
| Pin < 20 % | LED đỏ nhấp nháy + "PIN YEU!" (trễ: tắt khi ≥ 25 %); Backend sinh cảnh báo `LOW_BATTERY` từ telemetry |
| Hàng thực tế lệch > 100 g so với giỏ | Backend sinh `WEIGHT_MISMATCH` từ telemetry (xe chỉ báo cân đã lọc) |

LED: xanh sáng = sẵn sàng; xanh nhấp nháy = đang kết nối; đỏ sáng = xe bị khoá.

## Hiệu chuẩn cân HX711

1. Bật nguồn khi xe **trống** (hoặc giữ nút TARE 2 s khi chưa có phiên).
2. Đặt vật đã biết khối lượng (vd. 1000 g), đọc `[scale] ...` trong log hoặc OLED.
3. Cách nhanh: để xe trống, gõ `tare`, đặt vật lên cân rồi gõ `cal 1000` (số gram thật) – hệ số tự tính và lưu vào NVS. Số âm là bình thường nếu đấu ngược dây.
   Cách thủ công: sửa `HX711_COUNTS_PER_GRAM` = (thô khi có vật − thô khi trống) / khối lượng thật.
4. Kiểm tra bằng 2–3 vật khác nhau.

## Kiểm thử

```bash
tools/run_native_tests.sh                     # 38 unit test logic (g++ + ASan/UBSan, không cần PlatformIO)
pio test -e native                            # cùng bộ test, dùng Unity thật của PlatformIO
python3 -m pytest tests/unit/test_firmware_protocol.py   # (ở thư mục gốc) message firmware ⇄ contract Python
```

## Cấu trúc

```
firmware/
├─ platformio.ini          env esp32dev, esp32dev_standalone, esp32dev_sim, native (mỗi env khai báo đầy đủ cờ)
├─ diagram.json, wokwi.toml  mô phỏng Wokwi (không cần linh kiện)
├─ wokwi-web/              gói dán lên wokwi.com (SINH TỰ ĐỘNG bởi tools/make_wokwi_web.py – không sửa tay)
├─ include/pins.h, cart_config.example.h, wokwi_online.h   (+ cart_secrets.h do tools/provision sinh, không commit)
│  (env mô phỏng: esp32dev_sim | esp32dev_sim_bridge (cách 3) | esp32dev_wokwi_online (cách 2))
├─ src/main.cpp            keo dán phần cứng/mạng (không chặn, không delay trong loop)
├─ lib/cartcore/           logic thuần C++ (JSON, ACK/idempotent, trạng thái xe, lọc cân, pin, nút, reconnect)
├─ test/test_cartcore/     unit test (Unity)
└─ tools/                  run_native_tests.sh, protocol_tool.cpp (kiểm tra chéo), unity_shim (chỉ để chạy test khi không có PlatformIO)
```

## Đã kiểm chứng và chưa kiểm chứng

| | Trạng thái |
|---|---|
| `lib/cartcore` (38 unit test, gồm SHA-256/HMAC theo vector chuẩn và kiểm chữ ký; g++ `-Wall -Wextra`, ASan/UBSan) | ✅ đã chạy |
| Message firmware dựng ra qua `shared.contract.decode_and_validate` của Backend; lệnh do Backend dựng được firmware phân tích + ACK đúng | ✅ đã chạy (`test_firmware_protocol.py`) |
| Đăng ký xe qua `POST /api/carts` và xe mới lên ONLINE | ✅ đã chạy (Python) |
| `src/main.cpp` biên dịch bằng toolchain ESP32/PlatformIO thật | ❌ **chưa** (chỉ kiểm tra cú pháp, cả hai chế độ `STANDALONE_MODE=0/1`, với header giả lập Arduino; tên hàm thư viện thật như `PubSubClient::setSocketTimeout`, `analogReadMilliVolts` chưa được trình biên dịch thật xác nhận) |
| Ký/kiểm HMAC giữa firmware (C++) và Backend (Python), cả hai chiều | ✅ đã chạy (`test_firmware_protocol.py`) |
| `WiFiClientSecure` + TLS với Mosquitto trên ESP32 | ❌ **chưa** (chỉ kiểm tra cú pháp với header giả lập) |
| Chạy trên ESP32, máy quét GM65, HX711, OLED, buzzer, đo pin thật | ❌ **chưa** |
| Wi-Fi + NTP + Mosquitto thật | ❌ **chưa** |
| Giá trị hiệu chuẩn cân, đường cong pin | ❌ giá trị mặc định mang tính tham khảo, cần hiệu chuẩn |
