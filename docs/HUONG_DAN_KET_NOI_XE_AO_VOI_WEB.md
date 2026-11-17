# Kết nối thiết bị ảo (Wokwi) với web để quản lý dữ liệu và thao tác

Mục tiêu: **xe đẩy ảo chạy trong Wokwi** gửi/nhận dữ liệu thật với hệ thống web của dự án, để bạn:
- **Khách hàng** (`/customer`): chọn xe, bắt đầu phiên, xem giỏ cập nhật khi xe "quét" hàng, thanh toán, huỷ phiên.
- **Quản trị** (`/admin`): đăng ký xe, xem trạng thái/pin/cân/cảnh báo theo thời gian thực, **khoá/mở khoá xe từ xa**, huỷ phiên đang treo, **thêm/sửa/ẩn sản phẩm**.

Tài liệu liên quan: [BAT_DAU_NHANH.md](BAT_DAU_NHANH.md), [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md), [HUONG_DAN_PLATFORMIO_WOKWI.md](HUONG_DAN_PLATFORMIO_WOKWI.md).

> ⚠️ **Phần "Wokwi thật ↔ web" chưa được chạy thử trên wokwi.com / VS Code Wokwi thật** (môi trường phát triển không có). Đã test tự động: toàn bộ phía web (đăng ký xe, quản lý sản phẩm, huỷ phiên, khoá/mở khoá, cảnh báo) với một "xe" gửi tin MQTT đúng định dạng của firmware; cầu nối Wokwi↔MQTT với Wokwi giả; logic firmware (`cartcore`). Lần chạy đầu của bạn là lần kiểm chứng đầu tiên – nếu lỗi, chép nguyên văn thông báo gửi lại.

## 1. Mô hình hoạt động (đọc 1 phút)

```
  Wokwi (xe ảo, ESP32)                      máy của bạn
  ┌──────────────────┐   MQTT    ┌─────────┐   ┌───────────────────────┐
  │ firmware SmartCart├─────────►│ broker  │◄─►│ Backend (:8000) + web │
  └──────────────────┘           └─────────┘   │ /customer  /admin     │
                                               └───────────────────────┘
```

- **Trang web chạy trên máy bạn** (`http://localhost:8000`), không có địa chỉ công khai. Chỉ bạn mở được.
- Wokwi không "thấy" được `localhost` của bạn, nên có **hai đường nối**:

| | Đường A – broker công cộng | Đường B – cầu nối Serial↔MQTT |
|---|---|---|
| Chạy Wokwi ở đâu | **wokwi.com (trình duyệt)** hoặc VS Code | chỉ **VS Code + extension Wokwi** |
| Cần PlatformIO | Không (wokwi.com) / Có (VS Code) | Có |
| Cần Internet | Có | Chỉ để cài công cụ |
| Bảo mật | Broker công cộng **không mật khẩu** – chỉ dùng dữ liệu demo | Broker chạy trên máy bạn, có thể bật TLS/HMAC |
| Độ khó | Dễ nhất | Nhiều bước hơn |

**Khuyên dùng đường A** (wokwi.com) để thấy kết quả sớm nhất.

## 2. Đường A – wokwi.com + broker công cộng

### Bước A1. Đặt mã xe riêng của bạn (khuyên làm)

Broker công cộng ai cũng đọc được. Mở `firmware/wokwi-web/online/wokwi_online.h` và đổi `MQTT_TOPIC_ROOT` và `CART_ID` thành chuỗi ngẫu nhiên của bạn (chữ thường, số, `_`, `-`). Gói đã được tạo sẵn với giá trị ngẫu nhiên, nên nếu bạn không đổi thì vẫn chạy, chỉ kém bí mật hơn.
Nếu đổi, **sửa luôn** `firmware/include/wokwi_online.h` thành **cùng giá trị** (script ở bước A2 đọc file này), hoặc chạy lại `python3 firmware/tools/make_wokwi_web.py` để sinh lại gói từ file đó.

### Bước A2. Chạy Backend trên máy bạn (nối vào broker công cộng)

Từ thư mục gốc dự án (không chạy `run_local.sh` hay Simulator cùng lúc):
- Windows: `powershell -ExecutionPolicy Bypass -File scripts\run_online_demo.ps1`
- macOS / Linux / Git Bash: `scripts/run_online_demo.sh`

Script in **mật khẩu admin** (chép lại) và địa chỉ http://localhost:8000. Để tự đặt mật khẩu: đặt biến `ADMIN_PASSWORD` trước khi chạy.
Script cũng **tự đăng ký xe** `CART_ID` sau 5 giây. Nếu không thấy xe, đăng ký bằng web ở bước A5.

### Bước A3. Tạo dự án Wokwi

1. Vào https://wokwi.com → **New Project** → **ESP32**.
2. Làm theo mục 3 của [HUONG_DAN_PLATFORMIO_WOKWI.md](HUONG_DAN_PLATFORMIO_WOKWI.md): dán `sketch.ino`, `diagram.json`, `libraries.txt` và thêm `smartcart.cpp`, `cartcore.h/.cpp`, `cartsec.h/.cpp`, `pins.h`, **`wokwi_online.h`** từ thư mục `firmware/wokwi-web/online/` (đúng tên file).
3. Bấm **▶ Start the Simulation**.

### Bước A4. Kiểm tra xe đã nối

Trong Terminal (Serial) của Wokwi phải thấy lần lượt `[wifi] da ket noi` rồi `[mqtt] da ket noi + subscribe`. Sau vài giây vào http://localhost:8000/admin (đăng nhập `admin` + mật khẩu ở A2): xe của bạn hiện **Online**, có % pin.

Không lên Online → xem mục 5 (bảng sự cố).

### Bước A5. Đăng ký xe trên web (nếu chưa tự có)

Backend **bỏ qua xe lạ**, nên xe phải được đăng ký, mã **trùng đúng `CART_ID`** trong firmware.
`/admin` → **＋ Đăng ký xe** → nhập mã xe (chữ, số, `_`, `-`) và tên → **Lưu**. Xe mới hiện *Offline* cho tới khi nhận được tin đầu tiên từ Wokwi (thường vài giây).

## 3. Đường B – VS Code + cầu nối (không cần broker công cộng)

Làm theo mục 5 của [HUONG_DAN_PLATFORMIO_WOKWI.md](HUONG_DAN_PLATFORMIO_WOKWI.md) (4 terminal: broker, Backend, cầu nối, Wokwi với env `esp32dev_sim_bridge`). Xe là `WK_BRIDGE` (cầu nối tự đăng ký; hoặc đăng ký bằng web rồi chạy cầu nối với `--no-register`). Các bước thao tác ở mục 4 dưới đây giống hệt.

## 4. Thao tác trên web với xe ảo (kịch bản thử đầy đủ)

Mở 2 tab: **Quản trị** `http://localhost:8000/admin` và **Khách** `http://localhost:8000/customer`.

### 4.1 Một phiên mua hàng

1. **Khách:** `/customer` → chọn xe ảo → **Bắt đầu**. Trên Wokwi, màn hình OLED chuyển sang trạng thái đang mua.
2. **Wokwi:** trong Terminal gõ `scan <mã vạch>` (vd. một mã trong bảng mã mẫu ở [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md), hoặc mã bạn vừa thêm ở 4.3). Giỏ của khách trên web tự cập nhật; OLED hiện mã vừa quét.
   - Mã không có trong danh mục → bị từ chối (xem sự kiện ở `/admin`).
3. **Cân:** gõ `weight 750` → khi lệch so với cân dự kiến > 100 g, `/admin` hiện cảnh báo **WEIGHT_MISMATCH** và trang khách báo lệch cân.
4. **Khách:** bấm **Thanh toán** (hoặc **Huỷ phiên**) → xe về *Sẵn sàng*.

### 4.2 Quản trị từ xa

- **Khoá xe:** `/admin` → bấm xe → **Khoá xe**. Xe ảo nhận lệnh, gửi *ACK*; trang khách hiện banner khoá, `scan` không thêm hàng. **Mở khoá xe** để dùng lại. Xe Offline thì báo lỗi, xe không phản hồi sau ~5 s báo hết thời gian.
- **Huỷ phiên treo:** khách đóng trình duyệt giữa chừng khiến xe báo "đang được sử dụng" → `/admin` → xe → **Huỷ phiên này** → xác nhận.
- **Cảnh báo tự động:** pin < 20 % (`LOW_BATTERY`), lệch cân (`WEIGHT_MISMATCH`), dừng Wokwi quá 15 s (`OFFLINE`; chạy lại thì xe tự quay về và giữ giỏ).

### 4.3 Quản lý dữ liệu sản phẩm

`/admin` → **Sản phẩm**:
- **＋ Thêm sản phẩm:** mã vạch (4–64 ký tự chữ/số/`-`, không trùng), tên, giá (VND ≥ 0), khối lượng (gram > 0). Lưu xong, **`scan <mã vạch>` trong Wokwi dùng được ngay**.
- **Sửa:** đổi tên/giá/khối lượng/mã vạch.
- **Ẩn / Hiện:** ẩn sản phẩm khỏi khách (không xoá để giữ lịch sử); tích "Hiện cả đã ẩn" để xem lại. Quét mã đã ẩn → bị từ chối.
- Khối lượng ảnh hưởng *cân dự kiến* của giỏ → thêm sản phẩm với khối lượng thực tế để so sánh cân đúng.
- Chỉ **admin** sửa được; tài khoản **viewer** chỉ xem.

Cùng thao tác có thể gọi bằng API (Swagger: http://localhost:8000/docs; Postman: thư mục `postman/`): `POST /api/products`, `PUT /api/products/{id}`, `POST /api/carts`, `POST /api/sessions/{id}/cancel`. Xem [api/API.md](api/API.md).

## 5. Sự cố hay gặp

| Hiện tượng | Cách xử lý |
|---|---|
| Wokwi báo lỗi biên dịch / thiếu thư viện | Kiểm tra đã thêm đủ file đúng tên và `libraries.txt`; chép nguyên văn lỗi gửi lại |
| Terminal Wokwi dừng ở `[wifi]…` | Phải dùng Wi-Fi ảo `Wokwi-GUEST` (đã đặt trong `wokwi_online.h`); thử Start lại |
| `[mqtt] that bai rc=…` | Broker công cộng bận/chặn: đổi `MQTT_HOST` sang `broker.emqx.io` (cả hai nơi: gói Wokwi và `firmware/include/wokwi_online.h`) rồi chạy lại script A2 |
| Xe không hiện hoặc luôn Offline | (1) xe chưa đăng ký / sai mã so với `CART_ID`; (2) Backend không chạy bằng script A2 (sai broker hoặc sai `MQTT_TOPIC_ROOT`); (3) Wokwi chưa Start |
| `/admin` đòi đăng nhập | `admin` + mật khẩu in ra ở bước A2 (đổi mỗi lần chạy nếu không đặt `ADMIN_PASSWORD`) |
| Không thấy nút **＋ Đăng ký xe** / **Sản phẩm** sửa được | Bạn đang đăng nhập tài khoản viewer – dùng `admin` |
| `scan` không thêm vào giỏ | Khách chưa bắt đầu phiên cho xe này, xe đang khoá, hoặc mã vạch chưa có/đã ẩn |
| Khoá xe báo lỗi | Xe đang Offline hoặc không phản hồi (xem mục 4.2) |
| Muốn mở web từ máy khác/điện thoại | Backend lắng nghe mọi địa chỉ (`API_HOST=0.0.0.0`) nên máy cùng mạng LAN vào được bằng `http://<IP máy bạn>:8000` (nhớ mở tường lửa). **Không** có địa chỉ công khai; hosting công khai cần máy chủ riêng và HTTPS |

## 6. Giới hạn cần biết

- Web chạy trên máy bạn; tắt máy/Backend là mất truy cập. Không có địa chỉ công khai kèm theo.
- Đường A dùng broker công cộng **không mã hoá, không mật khẩu**: chỉ dữ liệu demo. Để có TLS + HMAC, dùng chế độ bảo mật với broker riêng ([SECURITY.md](SECURITY.md)); chế độ đó chưa dùng được trực tiếp từ wokwi.com.
- Wokwi gói miễn phí giới hạn thời gian mô phỏng mỗi phiên; Start lại khi dừng.
