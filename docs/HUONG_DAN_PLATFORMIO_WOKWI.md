# Hướng dẫn PlatformIO & Wokwi (firmware ESP32)

Hướng dẫn từng bước để **build firmware bằng PlatformIO**, **chạy mô phỏng trong Wokwi** khi chưa có linh kiện, và **nạp lên ESP32 thật**.
Chi tiết đấu dây, hiệu chuẩn cân, hành vi của xe: [firmware/README.md](../firmware/README.md). Hướng dẫn chạy phần web: [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md). **Nối thiết bị ảo với web để quản lý dữ liệu và thao tác: [HUONG_DAN_KET_NOI_XE_AO_VOI_WEB.md](HUONG_DAN_KET_NOI_XE_AO_VOI_WEB.md).**

> ⚠️ **Phần này chưa được kiểm chứng trên công cụ thật.** Môi trường phát triển không có PlatformIO, Wokwi, Internet hay ESP32. Đã kiểm tra: logic `lib/cartcore` (38 test); tên linh kiện/chân trong `diagram.json` đối chiếu với tài liệu Wokwi và khớp `pins.h`; cú pháp `src/main.cpp` và gói `wokwi-web/` với header Arduino **giả** (test `tests/unit/test_wokwi_package.py`); cầu nối Wokwi ↔ MQTT với "Wokwi giả". **Lần build/chạy đầu tiên của bạn là lần kiểm chứng đầu tiên** – nếu gặp lỗi biên dịch hoặc lỗi dây trong Wokwi, hãy gửi nguyên văn thông báo lỗi để sửa.

## 1. Cài đặt

| Cần | Cách |
|---|---|
| VS Code | https://code.visualstudio.com |
| PlatformIO | Extension **PlatformIO IDE** trong VS Code (hoặc `pip install platformio` để dùng lệnh `pio`). Lần build đầu sẽ tải toolchain ESP32 + thư viện nên **cần Internet** |
| Wokwi | Extension **Wokwi Simulator**. `F1` → **Wokwi: Request a new License** → đăng nhập tài khoản Wokwi miễn phí |
| Python ≥ 3.11 | Để chạy Backend/broker/cầu nối (`pip install -r requirements.txt` ở thư mục gốc dự án) |
| Driver USB (chỉ khi nạp board thật) | CP2102 hoặc CH340 tuỳ board |

Mở **thư mục `firmware/`** (không phải thư mục gốc dự án) trong VS Code, vì `platformio.ini` và `wokwi.toml` nằm ở đó.
Thư viện (PubSubClient, HX711, Adafruit SSD1306/GFX) PlatformIO tự tải theo `lib_deps`.

## 2. Chọn môi trường (env) build

Mỗi env là một "chế độ" của cùng một firmware:

| Env | Dùng khi | Wi-Fi/MQTT | Cần `cart_config.h` |
|---|---|---|---|
| `esp32dev_sim` | **Wokwi (VS Code), chạy độc lập** (không liên kết hệ thống web) | không | không |
| `esp32dev_sim_bridge` | **Wokwi + liên kết hệ thống** qua cầu nối Serial↔MQTT trên máy bạn (không cần Internet) | không (cầu nối lo) | không |
| `esp32dev_wokwi_online` | **Wokwi + liên kết hệ thống** qua broker MQTT công cộng | Wi-Fi ảo `Wokwi-GUEST` | không (dùng `wokwi_online.h`) |
| `esp32dev_standalone` | **Board thật**, thử linh kiện qua Serial, chưa cần mạng | không | không |
| `esp32dev` | **Board thật chạy cùng hệ thống** | Wi-Fi thật + MQTT | **có** |
| `native` | Unit test trên PC | – | – |

Chọn env: thanh trạng thái dưới cùng VS Code (biểu tượng PlatformIO) hoặc thêm `-e <env>` vào lệnh `pio`.

Build: nút **✓ (Build)** ở thanh dưới, hoặc:

```bash
cd firmware
pio run -e esp32dev_sim
```

Build thành công tạo `.pio/build/<env>/firmware.bin` và `firmware.elf` – chính là hai file `wokwi.toml` trỏ tới. **Wokwi không tự build**: sau mỗi lần sửa code hoặc đổi env phải build lại rồi khởi động lại mô phỏng.

## 3. Wokwi trên trình duyệt (wokwi.com) – không cần cài gì

Cách nhanh nhất để thấy firmware chạy: Wokwi **tự biên dịch trong trình duyệt**, không cần PlatformIO, VS Code hay license. Gói nằm ở:

| Thư mục | Dùng để |
|---|---|
| `firmware/wokwi-web/standalone/` | Chạy độc lập, gõ lệnh trong Serial Monitor (như cách 1 ở mục 4) |
| `firmware/wokwi-web/online/` | Liên kết hệ thống web qua broker MQTT công cộng (như cách 3 ở mục 6) |

Mỗi thư mục có: `sketch.ino` (cố ý để trống), `smartcart.cpp` (= `src/main.cpp` + cờ build), `cartcore.h/.cpp`, `cartsec.h/.cpp`, `pins.h`, `diagram.json`, `libraries.txt` (và `wokwi_online.h` ở bản online). Thư mục này **sinh tự động** từ `firmware/src` và `firmware/lib` bằng `python3 firmware/tools/make_wokwi_web.py`; đừng sửa tay.

Các bước (giao diện Wokwi có thể khác chút):
1. Vào https://wokwi.com → **New Project** → chọn **ESP32** (Arduino). Đăng nhập tài khoản miễn phí nếu muốn lưu dự án.
2. Thay nội dung 3 file có sẵn `sketch.ino`, `diagram.json`, `libraries.txt` bằng nội dung file cùng tên trong thư mục gói.
3. Thêm các file còn lại bằng nút mũi tên **▾** cạnh các tab (New file / Upload file(s)), **đặt đúng tên** rồi dán nội dung: `smartcart.cpp`, `cartcore.h`, `cartcore.cpp`, `cartsec.h`, `cartsec.cpp`, `pins.h` (bản online thêm `wokwi_online.h`).
4. Bấm **▶ Start the Simulation**. Lần đầu Wokwi tải thư viện và biên dịch nên chờ khoảng một phút.
5. Gõ lệnh vào ô nhập của Serial Monitor (danh sách lệnh ở mục 4).

Bản **online**: Backend phải dùng đúng cùng `MQTT_TOPIC_ROOT` và `CART_ID` với firmware. Script `scripts/run_online_demo.*` đọc các giá trị này từ `firmware/include/wokwi_online.h`. Nếu bạn đổi chúng (nên đổi, xem cảnh báo ở mục 6): sửa `firmware/include/wokwi_online.h`, chạy lại `make_wokwi_web.py`, rồi dán lại `wokwi_online.h` mới lên Wokwi.

Giới hạn của cách này:
- Không có chế độ cầu nối Serial↔MQTT (cần cổng RFC2217 của Wokwi cho VS Code). Muốn liên kết web mà không qua Internet, dùng cách 2 ở mục 5.
- **Chưa thử trên wokwi.com thật**: mình không truy cập được trang này từ môi trường phát triển. Hai điểm chưa chắc: Wokwi có biên dịch các file `.cpp` thêm vào cạnh `sketch.ino` không (theo hiểu biết của mình là có), và tên thư viện trong `libraries.txt` (`HX711 Arduino Library` – nếu báo không tìm thấy, thử đổi thành `HX711`). Nếu cách này không chạy, dùng PlatformIO (mục 2 và 4) và gửi lại nguyên văn thông báo lỗi.

## 4. Wokwi cách 1 – chạy độc lập (dễ nhất, nên thử trước)

1. Build env `esp32dev_sim` (mục 2). `wokwi.toml` mặc định đã trỏ env này.
2. `F1` → **Wokwi: Start Simulator**. Cửa sổ hiện mạch: ESP32, OLED, HX711 + load cell, còi, 2 LED, 2 nút.
3. Dùng panel **Serial Monitor/Terminal** của Wokwi để gõ lệnh (Enter để gửi). Mô phỏng không có máy quét mã vạch nên **quét bằng lệnh**:

| Lệnh | Tác dụng |
|---|---|
| `scan 8934588012341` | Như quét mã vạch: OLED hiện mã, còi kêu; message sẽ gửi lên Backend được in ra dạng `[local] smartcart/…/scan {...}` |
| `weight 750` / `weight auto` | Đặt số cân 750 g / quay lại đọc cảm biến |
| `battery 15` / `battery auto` | Đặt pin 15 % (LED đỏ nháy, OLED "PIN YEU!") / quay lại đo thật |
| `start`, `end`, `lock`, `unlock` | Giả lập lệnh từ Backend: xem OLED, LED, còi |
| `status`, `selftest`, `help` | Trạng thái / tự kiểm tra / danh sách lệnh |

> Còi trong Wokwi là loại piezo (chỉ phát tiếng khi nhận sóng vuông), còn firmware điều khiển còi **active** bằng mức cao/thấp, nên trong mô phỏng bạn có thể chỉ nghe tiếng tách hoặc không nghe gì. Hãy theo dõi OLED và LED.

Nút **MODE** (bấm ngắn = đổi THÊM ↔ BỎ HÀNG cho đúng một lần quét) và **TARE** (giữ chuột 2 giây = về 0 cân, chỉ khi chưa có phiên) bấm bằng chuột trên mạch.

Chế độ này **không nối với web**. Muốn thấy xe trên `/customer` và `/admin`, dùng cách 2 hoặc 3.

> Tên linh kiện/chân trong `diagram.json` đã đối chiếu với tài liệu Wokwi (OLED dùng `board-ssd1306`), nhưng file **chưa được mở thử trong Wokwi thật**. Nếu một dây báo sai tên chân, kéo lại dây trong giao diện Wokwi; không ảnh hưởng tới firmware.

## 5. Wokwi cách 2 – liên kết web qua cầu nối Serial↔MQTT (không cần Internet)

Dữ liệu ở lại trong máy bạn. Wokwi mở Serial của mạch ra TCP cổng 4000 (`rfc2217ServerPort` trong `wokwi.toml`); `tools/wokwi_bridge.py` đọc các dòng `[local] …` của firmware rồi đẩy lên MQTT, và chuyển lệnh của Backend ngược vào mạch.

```
Wokwi (esp32dev_sim_bridge) ⇄ TCP :4000 ⇄ tools/wokwi_bridge.py ⇄ MQTT broker (máy bạn) ⇄ Backend ⇄ /customer, /admin
```

Mở **4 terminal** tại thư mục gốc dự án. Đặt **cùng một** `ADMIN_PASSWORD` cho Backend và cầu nối (cầu nối cần nó để đăng ký xe):

```bash
# Linux/macOS/Git Bash                                  # Windows PowerShell:  $env:ADMIN_PASSWORD = "mat-khau-cua-ban"
export ADMIN_PASSWORD='mat-khau-cua-ban'
```

| # | Lệnh |
|---|---|
| 1 | `python -m tools.dev_broker` |
| 2 | `python -m backend.main` → mở http://localhost:8000 |
| 3 | Trong VS Code: sửa `firmware/wokwi.toml`, đổi **hai** dòng `esp32dev_sim` thành `esp32dev_sim_bridge`; chọn env `esp32dev_sim_bridge`; **Build ✓**; `F1` → **Wokwi: Start Simulator**. **Giữ tab mô phỏng đang hiển thị** (bị ẩn là mô phỏng tạm dừng) |
| 4 | `python -m tools.wokwi_bridge --cart-id WK_BRIDGE` (tự đăng ký xe `WK_BRIDGE`; thêm `--no-register` nếu đã đăng ký) |

Sau vài giây xe `WK_BRIDGE` chuyển **ONLINE** ở `/admin` (đăng nhập `admin` + mật khẩu đã đặt). Thử:
1. `/customer` → chọn `WK_BRIDGE` → bắt đầu phiên (OLED hiện "BAT DAU MUA HANG").
2. Trong Terminal Wokwi gõ `scan <mã vạch hợp lệ>` → giỏ hàng cập nhật. `weight 750` → số cân lên `/admin`.
3. `/admin` → chi tiết xe → **Khoá xe** → LED đỏ trong Wokwi sáng. Thanh toán trên web → OLED "CAM ON!".

Lưu ý:
- Giờ trong mô phỏng không phải giờ thật nên cầu nối **thay `message_id`, `timestamp`, `cart_id`** trước khi gửi; việc này là bình thường.
- Khi Backend nối lại, nó gửi lệnh đồng bộ (vd. `END_SESSION`) cho xe vừa ONLINE – bình thường.
- Cầu nối tự nối lại Serial. Báo "mất kết nối Serial Wokwi" → kiểm tra mô phỏng đang chạy và tab đang hiển thị.
- Tuỳ chọn: `--wokwi-port`, `--mqtt-host/--mqtt-port`, `--api` (Backend ở máy khác).
- Nếu cầu nối báo "Backend yêu cầu đăng nhập quản trị": bạn chưa đặt `ADMIN_PASSWORD` trong terminal chạy cầu nối (hoặc nó khác mật khẩu của Backend). Cách khác: đăng nhập `/admin` → **＋ Đăng ký xe** (mã `WK_BRIDGE`) rồi chạy cầu nối với `--no-register`.
- Chạy với **bản bảo mật** (`run_secure.sh`): nạp biến rồi chạy cầu nối bằng tài khoản `simulator`, cầu nối sẽ ký HMAC thay cho xe:
  ```bash
  set -a; . secrets/secure.env; set +a
  MQTT_USERNAME="$MQTT_SIM_USER" MQTT_PASSWORD="$MQTT_SIM_PASS" python -m tools.wokwi_bridge --cart-id WK_BRIDGE
  ```
  (Cách này mới được test bằng code, **chưa chạy trọn vẹn với Wokwi thật**.)

## 6. Wokwi cách 3 – liên kết web qua broker MQTT công cộng

Wokwi (gói miễn phí) có Internet qua Wi-Fi ảo `Wokwi-GUEST` nhưng không nối được vào máy bạn. Vì vậy firmware trong Wokwi và Backend trên máy bạn cùng nối vào **một broker MQTT công cộng** (mặc định `broker.hivemq.com`, cổng 1883, **không mật khẩu, không TLS**).

> ⚠️ Ai biết gốc topic + mã xe đều đọc/gửi được tin nhắn của xe bạn. **Đổi** `MQTT_TOPIC_ROOT` và `CART_ID` trong `firmware/include/wokwi_online.h` thành chuỗi ngẫu nhiên của riêng bạn (a–z, 0–9, `_`, `-`) và chỉ dùng dữ liệu demo.

1. **Backend** (từ thư mục gốc, **không** chạy `run_local.sh`/Simulator cùng lúc):
   - Windows: `powershell -ExecutionPolicy Bypass -File scripts\run_online_demo.ps1`
   - Linux/macOS: `scripts/run_online_demo.sh`

   Script đọc `wokwi_online.h`, nối Backend vào broker đúng gốc topic, in **mật khẩu admin** ra màn hình và tự đăng ký xe sau 5 giây. Mở http://localhost:8000.
2. **Firmware:** sửa `firmware/wokwi.toml`, đổi hai dòng `esp32dev_sim` thành `esp32dev_wokwi_online`; chọn env `esp32dev_wokwi_online`; **Build ✓**; **Wokwi: Start Simulator**.
3. Terminal Wokwi phải có `[wifi] da ket noi` rồi `[mqtt] da ket noi + subscribe`. Sau vài giây xe chuyển **ONLINE** ở `/admin`.
4. Thử như cách 2: `/customer` chọn xe → bắt đầu phiên → `scan …` / `weight 750` trong Terminal Wokwi.

Không lên ONLINE: xem Terminal có `[mqtt] that bai rc=…`; thử đổi `MQTT_HOST` sang `broker.emqx.io` rồi build lại; kiểm tra Backend đã chạy bằng script (đúng gốc topic).
(Hai script này đã được sửa để đăng ký xe kèm token quản trị; phần đăng ký đã test với Backend thật, bản PowerShell **chưa chạy thử** vì không có PowerShell.)

> Khi xong, **trả `wokwi.toml` về `esp32dev_sim`** để lần sau chạy cách 1 không bị nhầm env.

## 7. Nạp ESP32 thật

### 6.1 Thử linh kiện trước (không cần mạng)

```bash
cd firmware
pio run -e esp32dev_standalone -t upload
pio device monitor            # 115200 baud
```

Khi khởi động firmware chạy **self-test** (OLED, HX711, pin, LED, còi, byte nhận từ máy quét) và in kết quả. Trong Serial Monitor gõ `help`, `status`, `selftest`, `scan <mã>`, `start|end|lock|unlock`, `tare`, `cal 1000`. Hiệu chuẩn cân: xe trống → `tare` → đặt vật **1000 g** → gõ `cal 1000` (hệ số lưu vào bộ nhớ NVS, không cần sửa code).
Đấu dây theo bảng trong [firmware/README.md](../firmware/README.md#linh-kiện--đấu-dây); đổi chân ở `include/pins.h`.
Chạy bằng USB không có pin: đặt `BATTERY_ENABLED 0` để luôn báo 100 %.

### 6.2 Chạy cùng hệ thống

1. Máy chủ: `MQTT_BIND=0.0.0.0 scripts/run_local.sh` (cho ESP32 trong cùng LAN kết nối được), mở tường lửa cổng **1883**. Ghi lại mật khẩu admin script in ra.
2. Cấu hình firmware:
   ```bash
   cd firmware
   cp include/cart_config.example.h include/cart_config.h    # rồi sửa WIFI_SSID, WIFI_PASS, MQTT_HOST, CART_ID
   ```
   `MQTT_HOST` là **IP của máy chạy broker** (không dùng `localhost`). `cart_config.h` nằm trong `.gitignore` vì chứa mật khẩu Wi-Fi.
3. Đăng ký xe (Backend bỏ qua mã xe lạ). Cách dễ: đăng nhập `/admin` → **＋ Đăng ký xe** → nhập `CART_ID`. Hoặc bằng API (cần token admin):
   ```bash
   TOKEN=$(curl -s localhost:8000/api/auth/login -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"<mật khẩu>"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
   curl -X POST localhost:8000/api/carts -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"cart_id":"CART_004","name":"Xe thật số 4"}'
   ```
4. Nạp và xem log: `pio run -e esp32dev -t upload` rồi `pio device monitor`. Log phải có `wifi=OK mqtt=OK ntp=OK` và xe chuyển **ONLINE** ở `/admin`.

### 6.3 Chạy với bảo mật (TLS + HMAC)

```bash
python -m tools.provision --carts CART_001,CART_004 --host 192.168.1.20     # IP broker đưa vào chứng chỉ
cp secrets/firmware/CART_004/cart_secrets.h firmware/include/               # KHÔNG commit
# include/cart_config.h: CART_ID "CART_004", MQTT_HOST "192.168.1.20", MQTT_PORT 8883
pio run -e esp32dev -t upload
bash scripts/run_secure.sh                                                  # máy chủ
```

`SECRETS_CART_ID` phải trùng `CART_ID`. TLS cần đồng hồ đúng (firmware chờ NTP xong mới kết nối) và `MQTT_HOST` nằm trong SAN của chứng chỉ. Phần TLS trên ESP32 **chưa chạy trên board thật**. Xem [SECURITY.md](SECURITY.md).

## 8. Unit test logic (không cần board)

```bash
bash firmware/tools/run_native_tests.sh      # 38 test, g++ + ASan/UBSan, không cần PlatformIO
python -m pytest tests/unit/test_wokwi_package.py -q   # kiểm tra tĩnh sơ đồ Wokwi, platformio.ini, gói wokwi-web, cú pháp main.cpp
cd firmware && pio test -e native            # cùng bộ test với Unity của PlatformIO
```

## 9. Lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| wokwi.com: báo thiếu thư viện / `HX711.h: No such file` | Tên trong `libraries.txt` không khớp Library Manager: đổi `HX711 Arduino Library` thành `HX711` (hoặc ngược lại) |
| wokwi.com: `undefined reference to setup/loop` hoặc không thấy hàm trong `smartcart.cpp` | Chưa thêm đủ file `.cpp/.h` vào dự án (mục 3), hoặc Wokwi không biên dịch `.cpp` phụ: dùng PlatformIO |
| Sửa `src/` mà gói wokwi-web cũ | Chạy `python3 firmware/tools/make_wokwi_web.py` (test sẽ báo lệch nếu quên) |
| Wokwi: "firmware.bin not found" | Chưa build env tương ứng, hoặc `wokwi.toml` trỏ env khác env đã build |
| Sửa code mà Wokwi vẫn chạy bản cũ | Wokwi không tự build: Build lại rồi Stop/Start mô phỏng |
| Wokwi: yêu cầu license | `F1` → **Wokwi: Request a new License** |
| Wokwi: dây/chân báo lỗi | `diagram.json` chưa thử; kéo lại dây trong giao diện, không ảnh hưởng firmware |
| Biên dịch lỗi thiếu `cart_config.h` | Dùng env `esp32dev`: tạo file từ `cart_config.example.h`. Hoặc dùng env `*_sim*`/`*_standalone` không cần file này |
| Biên dịch lỗi `unknown name`/hàm thư viện | Báo lại nguyên văn lỗi (main.cpp chưa được biên dịch bằng toolchain thật) |
| Cầu nối báo "mất kết nối Serial Wokwi" | Mô phỏng chưa chạy, tab Wokwi bị ẩn, hoặc đang chạy env khác `esp32dev_sim_bridge` |
| Xe không lên ONLINE (Wokwi cách 3) | Xem `[mqtt] that bai rc=…`; đổi broker; script Backend phải đúng `wokwi_online.h` |
| Xe thật không lên ONLINE | `MQTT_HOST` sai/tường lửa chặn 1883/xe chưa đăng ký/`CART_ID` khác mã đã đăng ký; (bảo mật) `cart_secrets.h` của xe khác |
| Quét mà không có phản ứng | Xe chưa có phiên hoặc đang khoá (OLED báo lý do, còi 3 tiếng); mã vạch không hợp lệ (ký tự lạ/quá ngắn/dài) |
| Cảnh báo lệch cân liên tục (xe thật) | Chưa hiệu chuẩn: `tare` rồi `cal 1000` |
| `pio` không có lệnh | Cài PlatformIO CLI (`pip install platformio`) hoặc dùng nút Build trong VS Code |
