# Bắt đầu nhanh: mở file và sử dụng

Dành cho người **vừa tải file `smart-shopping-cart.zip` về** và chưa biết bắt đầu từ đâu. Làm lần lượt từ trên xuống; mỗi phần có dấu hiệu "thành công" để bạn biết mình đang đúng.
Hướng dẫn đầy đủ hơn: [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md) (web, quản trị, Simulator) và [HUONG_DAN_PLATFORMIO_WOKWI.md](HUONG_DAN_PLATFORMIO_WOKWI.md) (firmware ESP32, Wokwi).

## 0. Chọn đường đi

| Bạn muốn | Làm phần | Cần cài |
|---|---|---|
| Chỉ **xem hệ thống chạy** (web khách hàng + quản trị, xe giả lập) | **2** | Python, trình duyệt |
| Xem **firmware ESP32 chạy ảo** nhanh nhất, không cài gì | **3** | chỉ trình duyệt (wokwi.com) |
| Build firmware bằng **PlatformIO** rồi chạy trong Wokwi | **4** | VS Code + 2 extension |
| **Đọc tài liệu** | **5** | VS Code hoặc bất kỳ trình soạn thảo |

Bạn có thể làm cả bốn; các phần độc lập nhau (trừ khi muốn firmware nói chuyện với web: xem 3.3 và 4.3).

## 1. Giải nén và làm quen thư mục

1. **Giải nén** `smart-shopping-cart.zip` (Windows: chuột phải → *Extract All…*; macOS: bấm đúp). Bạn được thư mục `smart-shopping-cart`.
   Nên đặt ở đường dẫn **ngắn, không dấu, không khoảng trắng** (vd. `C:\dev\smart-shopping-cart`) để tránh lỗi công cụ.
2. Thư mục có gì:

| Mục | Là gì | Bạn mở khi nào |
|---|---|---|
| `README.md` | Giới thiệu tổng quan | Đọc đầu tiên |
| `docs/` | Tài liệu (`.md`), ảnh giao diện trong `docs/screenshots/` | Phần 5 |
| `backend/`, `shared/`, `simulator/`, `tools/`, `scripts/` | Mã Python: máy chủ, xe giả lập, công cụ, script chạy | Khi chạy hệ thống |
| `frontend/` | Giao diện web (đã build sẵn ở `frontend/dist`) | Không cần mở |
| `firmware/` | Mã ESP32 (PlatformIO) + cấu hình Wokwi + gói `wokwi-web/` | Phần 3, 4 |
| `tests/` | Kiểm thử tự động | Chỉ khi muốn chạy test |
| `postman/` | Bộ gọi API cho Postman | Tuỳ chọn |

## 2. Chạy hệ thống web (xe giả lập bằng Python)

### 2.1 Cài đặt (một lần)

- **Python 3.11 trở lên**: https://www.python.org/downloads/ . Trên Windows, khi cài **tick "Add python.exe to PATH"**.
- Kiểm tra: mở terminal, gõ `python --version` (Windows có thể phải gõ `py --version`; nếu vậy hãy thay `python` bằng `py` ở mọi lệnh bên dưới).
- **VS Code** (khuyên dùng để mở dự án và có sẵn terminal): https://code.visualstudio.com

### 2.2 Mở dự án trong VS Code

1. Mở VS Code → **File → Open Folder…** → chọn thư mục **`smart-shopping-cart`** (thư mục ngoài cùng, chứa `README.md`).
2. Nếu VS Code hỏi *"Do you trust the authors?"* → **Yes, I trust the authors**.
3. Mở terminal: **Terminal → New Terminal** (hoặc `` Ctrl+` ``). Terminal đã đứng sẵn trong thư mục dự án.

### 2.3 Cài thư viện (một lần)

```
pip install -r requirements.txt
```

Thành công: kết thúc không báo lỗi đỏ (cài `starlette`, `uvicorn`, `pydantic`).

### 2.4 Chạy

**macOS / Linux / Windows có Git Bash hoặc WSL** – một lệnh:

```bash
scripts/run_local.sh
```

**Windows PowerShell (không có bash)** – mở **3 terminal** (nút `+` ở panel terminal), mỗi terminal đứng ở thư mục dự án:

```powershell
# Terminal 1: broker MQTT
python -m tools.dev_broker

# Terminal 2: Backend + giao diện   (đặt mật khẩu admin do bạn chọn, ít nhất 8 ký tự)
$env:ADMIN_PASSWORD = "MatKhau-Cua-Ban-1"
python -m backend.main

# Terminal 3: 3 xe giả lập
python -m simulator.main
```

Thứ tự: broker → Backend → Simulator. Terminal 3 còn cho bạn gõ lệnh điều khiển xe (`carts`, `scan CART_001 1`, …).

Thành công: có dòng địa chỉ `http://localhost:8000`, và (với `run_local.sh`) dòng `Quản trị: đăng nhập admin / <mật khẩu>`. **Chép mật khẩu này ra**: nó đổi mỗi lần chạy nếu bạn không tự đặt `ADMIN_PASSWORD`.

### 2.5 Dùng

Mở trình duyệt:

| Địa chỉ | Làm gì |
|---|---|
| http://localhost:8000/customer | Khách: chọn xe → quét → thanh toán |
| http://localhost:8000/admin | Quản trị: đăng nhập `admin` + mật khẩu; xem xe, cảnh báo, khoá/mở khoá, **＋ Đăng ký xe**, huỷ phiên, **Sản phẩm** (thêm/sửa/ẩn) |
| http://localhost:8000/simulator | Bảng điều khiển xe giả lập: quét hàng, cân, pin, ngắt mạng (cũng cần đăng nhập admin) |

Thử nhanh (2 phút): mở `/customer` ở một tab, chọn **Xe đẩy 1** → mở `/simulator` ở tab khác, quét vài sản phẩm → quay lại tab khách thấy giỏ hàng tự cập nhật → bấm **Thanh toán**. Mở `/admin` xem xe và cảnh báo (thử thêm "vật lạ" ở `/simulator` để thấy cảnh báo lệch cân).

**Dừng**: bấm `Ctrl+C` trong mỗi terminal. Chạy lại bằng đúng các lệnh ở 2.4.

Gặp lỗi? Xem bảng cuối mục 6 hoặc mục "Xử lý sự cố" trong [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md).

## 3. Firmware ảo trên wokwi.com (không cài gì)

Wokwi tự biên dịch trong trình duyệt. Dùng gói đã chuẩn bị trong `firmware/wokwi-web/`.

### 3.1 Tạo dự án

1. Vào https://wokwi.com → **New Project** → chọn **ESP32** (Arduino).
2. Dự án mới có sẵn 3 file: `sketch.ino`, `diagram.json`, `libraries.txt`. Với **mỗi** file, mở file cùng tên trong `firmware/wokwi-web/standalone/` bằng VS Code (hoặc Notepad), **Ctrl+A, Ctrl+C**, rồi dán đè (**Ctrl+A, Ctrl+V**) vào file đó trên Wokwi.
3. Thêm các file còn lại: nút mũi tên **▾** cạnh các tab → **New file** (hoặc *Upload file(s)*), đặt **đúng tên** rồi dán nội dung:
   `smartcart.cpp`, `cartcore.h`, `cartcore.cpp`, `cartsec.h`, `cartsec.cpp`, `pins.h`.

### 3.2 Chạy

1. Bấm nút xanh **▶ Start the Simulation**. Lần đầu chờ ~1 phút (tải thư viện, biên dịch).
2. Thấy mạch: ESP32, màn OLED, cân HX711, còi, 2 LED, 2 nút. Màn OLED hiện trạng thái.
3. Ô **Serial Monitor** bên dưới là nơi gõ lệnh (Enter để gửi):

| Gõ | Tác dụng |
|---|---|
| `help` | Danh sách lệnh |
| `scan 8934588012341` | Giả lập quét mã vạch (Coca Cola) |
| `weight 750` | Đặt số cân 750 g (`weight auto` để trả lại) |
| `battery 15` | Giả lập pin 15 % (LED đỏ nháy, OLED báo pin yếu) |
| `start`, `lock`, `unlock`, `end` | Giả lập lệnh từ Backend |

Thành công: sau `scan …` (bản độc lập tự bắt đầu một phiên mua nội bộ nên không cần `start`), OLED hiện mã vừa quét và dòng `[local] …/scan {...}` hiện trong Serial Monitor.

### 3.3 Muốn firmware này hiện trên web ở phần 2

Dùng gói `firmware/wokwi-web/online/` thay cho `standalone/` (thêm file `wokwi_online.h`), rồi chạy Backend bằng script **thay cho** bước 2.4:
- Windows: `powershell -ExecutionPolicy Bypass -File scripts\run_online_demo.ps1`
- macOS/Linux/Git Bash: `scripts/run_online_demo.sh`

Script in mật khẩu admin; sau vài giây xe Wokwi xuất hiện **ONLINE** ở http://localhost:8000/admin. **Hướng dẫn từng bước đầy đủ (kèm cách quản lý dữ liệu, thao tác trên web): [HUONG_DAN_KET_NOI_XE_AO_VOI_WEB.md](HUONG_DAN_KET_NOI_XE_AO_VOI_WEB.md).** Chi tiết và cảnh báo về broker công cộng: [HUONG_DAN_PLATFORMIO_WOKWI.md](HUONG_DAN_PLATFORMIO_WOKWI.md) mục 3 và 6.

> Cách này chưa được thử trên wokwi.com thật. Nếu báo lỗi biên dịch hay thiếu thư viện, chép nguyên văn thông báo gửi lại để sửa.

## 4. Firmware bằng PlatformIO + Wokwi trong VS Code

### 4.1 Cài đặt (một lần)

Trong VS Code, tab **Extensions** (`Ctrl+Shift+X`) cài:
1. **PlatformIO IDE** (lần đầu mở sẽ tải công cụ, mất vài phút, cần Internet).
2. **Wokwi Simulator**. Sau đó `F1` → **Wokwi: Request a new License** → đăng nhập tài khoản Wokwi miễn phí → xác nhận.

Khởi động lại VS Code nếu được yêu cầu.

### 4.2 Mở đúng thư mục

**File → Open Folder…** → chọn thư mục **`smart-shopping-cart/firmware`** (không phải thư mục ngoài). Lý do: `platformio.ini` và `wokwi.toml` nằm ở đó; mở sai thư mục thì PlatformIO không nhận dự án.
Chờ PlatformIO ở thanh dưới cùng hiện biểu tượng ngôi nhà/dấu tick (đang tải thư viện lần đầu).

### 4.3 Build và chạy mô phỏng

1. Thanh dưới cùng của VS Code: bấm tên env (vd. `Default (esp32dev)`) → chọn **`esp32dev_sim`**.
2. Bấm dấu **✓ (Build)**. Thành công: terminal cuối ghi `SUCCESS`, và có file `.pio/build/esp32dev_sim/firmware.bin`.
3. `F1` → **Wokwi: Start Simulator**. Mạch hiện ra, dùng Serial Monitor của Wokwi như ở 3.2.

Sau mỗi lần sửa code: **Build lại** rồi bấm Stop/Start mô phỏng (Wokwi không tự build).
Liên kết với web (hai cách, cần sửa `wokwi.toml`): xem [HUONG_DAN_PLATFORMIO_WOKWI.md](HUONG_DAN_PLATFORMIO_WOKWI.md) mục 5 (cầu nối, không cần Internet) và 6 (broker công cộng).

## 5. Đọc tài liệu

- Trong VS Code: mở file `.md` rồi nhấn **`Ctrl+Shift+V`** để xem bản đã định dạng (hoặc `Ctrl+K V` để xem song song).
- Thứ tự gợi ý: `README.md` → `docs/BAT_DAU_NHANH.md` (file này) → `docs/HUONG_DAN_SU_DUNG.md` → `docs/ARCHITECTURE.md`. Về bảo mật: `docs/SECURITY.md`. Về phần chưa kiểm chứng: `docs/DEVIATIONS.md`.
- Ảnh giao diện mẫu: thư mục `docs/screenshots/` (mở bằng trình xem ảnh).

## 6. Sự cố hay gặp khi mới bắt đầu

| Hiện tượng | Cách xử lý |
|---|---|
| `python` / `pip` không nhận ra | Chưa cài Python hoặc chưa tick "Add to PATH". Cài lại, mở terminal **mới**. Thử `py` thay `python` |
| `ModuleNotFoundError: starlette` | Chưa chạy `pip install -r requirements.txt` ở thư mục dự án |
| `ModuleNotFoundError: backend` hoặc `shared` | Terminal đang đứng sai thư mục: phải ở thư mục `smart-shopping-cart` (nơi có `README.md`) |
| `run_local.sh` không chạy trên Windows | Cần Git Bash hoặc WSL; hoặc dùng 3 lệnh PowerShell ở 2.4 |
| `Address already in use` / cổng bị chiếm | Đã có bản chạy trước: đóng các terminal cũ (`Ctrl+C`) hoặc đổi cổng `API_PORT`/`MQTT_PORT` |
| Trang `/admin` đòi đăng nhập | Bình thường. Dùng `admin` + mật khẩu in ra (hoặc `ADMIN_PASSWORD` bạn đặt). Sai 5 lần sẽ bị khoá 60 giây |
| `/customer` không có xe nào chọn được | Chưa chạy Simulator (Terminal 3) |
| PlatformIO không hiện nút Build | Đang mở sai thư mục: phải mở `firmware/` (mục 4.2) |
| Wokwi báo `firmware.bin not found` | Chưa Build env `esp32dev_sim`, hoặc `wokwi.toml` trỏ env khác |
| Wokwi báo cần license | `F1` → **Wokwi: Request a new License** |
| Build PlatformIO báo lỗi | Chép **nguyên văn** thông báo lỗi và gửi lại: firmware chưa từng được build bằng PlatformIO thật |
