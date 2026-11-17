# Hướng dẫn sử dụng Smart Shopping Cart

Mới nhận file zip? Đọc [BAT_DAU_NHANH.md](BAT_DAU_NHANH.md) trước.

Dành cho người **chạy thử, demo và vận hành** hệ thống. Cần hiểu kiến trúc: xem [ARCHITECTURE.md](ARCHITECTURE.md). Cần chi tiết bảo mật: [SECURITY.md](SECURITY.md).

> Hệ thống mặc định chạy **mô phỏng** (Simulator Python thay cho xe thật). Phần ESP32 thật chưa được thử trên board – xem [firmware/README.md](../firmware/README.md).

## 1. Chuẩn bị

| Cần | Ghi chú |
|---|---|
| Python ≥ 3.11 | `pip install -r requirements.txt` (starlette, uvicorn, pydantic) |
| Trình duyệt | Giao diện đã build sẵn ở `frontend/dist`, không cần Node |
| `openssl` | Chỉ khi chạy chế độ bảo mật (sinh chứng chỉ TLS) |

Chạy các lệnh dưới đây từ **thư mục gốc dự án** (`smart-shopping-cart/`). Dùng Git Bash/WSL trên Windows để chạy file `.sh`, hoặc chạy từng phần như mục 2.3.

## 2. Khởi động hệ thống

### 2.1 Chạy nhanh (khuyên dùng khi demo)

```bash
scripts/run_local.sh
```

Lệnh này bật cùng lúc: broker MQTT thử nghiệm (cổng 1883), Backend + giao diện (8000, WebSocket 8081) và Simulator 3 xe.
Màn hình in ra địa chỉ và **tài khoản quản trị**:

```
Giao diện: http://localhost:8000   Swagger: /api/docs   (Ctrl+C để dừng)
Quản trị: đăng nhập admin / <mật khẩu ngẫu nhiên>   (khách hàng không cần đăng nhập)
```

Mật khẩu admin **đổi mỗi lần chạy**. Muốn cố định: `ADMIN_PASSWORD='mat-khau-cua-ban' scripts/run_local.sh`.
Dừng bằng `Ctrl+C`.

### 2.2 Chạy bản bảo mật đầy đủ (đăng nhập + MQTT TLS/ACL + ký HMAC)

```bash
bash scripts/run_secure.sh
```

Lần đầu script tự sinh thư mục `secrets/` (khoá, mật khẩu, chứng chỉ) và in mật khẩu admin. Các lần sau dùng lại bộ bí mật đó nên mật khẩu **giữ nguyên**.
**Không commit/gửi thư mục `secrets/`.** Xoá `secrets/` rồi chạy lại là sinh bộ mới (xe thật phải nạp lại firmware).

### 2.3 Chạy từng phần (3 terminal)

```bash
python -m tools.dev_broker      # terminal 1: broker MQTT
python -m backend.main          # terminal 2: API + giao diện + WebSocket
python -m simulator.main        # terminal 3: 3 xe + dòng lệnh tương tác (thêm --auto để tự quét hàng)
```

Khi chạy kiểu này, nếu không đặt `ADMIN_PASSWORD` thì mật khẩu admin tạm được **in trong log của Backend** (terminal 2), dòng `ADMIN_PASSWORD chưa đặt – mật khẩu tạm thời…`.

### 2.4 Các địa chỉ

| Địa chỉ | Dùng để | Cần đăng nhập |
|---|---|---|
| http://localhost:8000/ | Trang chủ, chọn vai trò | không |
| http://localhost:8000/customer | Giao diện khách hàng | không |
| http://localhost:8000/admin | Quản trị | **admin / viewer** |
| http://localhost:8000/simulator | Điều khiển xe giả lập như phần cứng | **admin / viewer** |
| http://localhost:8000/api/docs | Swagger (cần Internet để tải giao diện Swagger) | – |
| `localhost:8090` | API điều khiển Simulator (chỉ máy cục bộ) | không – đừng mở ra mạng |

## 3. Khách hàng: mua hàng

1. Mở `/customer` → chọn một xe **Sẵn sàng** (trạng thái AVAILABLE + trực tuyến). Xe đang dùng, bị khoá hoặc mất mạng sẽ không chọn được.
2. Trang giỏ hàng mở ra. Thêm sản phẩm bằng một trong hai cách:
   - **Quét bằng xe** (máy quét trên xe thật, hoặc Simulator – xem mục 5): giỏ hàng cập nhật ngay, không cần tải lại trang.
   - **Nhập tay**: gõ hoặc chọn mã vạch trong ô *Nhập hoặc chọn mã vạch*.
3. Bấm **Xoá** ở từng dòng để bỏ món khỏi giỏ.
4. Bấm **Thanh toán** → xem lại → **Xác nhận thanh toán** → màn hình *Shopping Completed / Thank you!*, xe tự về trạng thái sẵn sàng.
5. Muốn bỏ giữa chừng: **Huỷ phiên mua hàng** (toàn bộ giỏ bị xoá).

Lưu ý:
- Banner **xe bị khoá** hiện khi nhân viên khoá xe: không quét/thanh toán được cho đến khi mở khoá.
- Cảnh báo **lệch cân** hiện khi cân thực tế khác cân dự kiến của giỏ quá 100 g (vd. bỏ thêm món chưa quét).
- **Mỗi phiên gắn với trình duyệt đã bắt đầu nó** (token lưu trong trình duyệt). Nếu đóng trình duyệt/đổi máy, bạn không vào lại được phiên đó và xe hiện *“đang được sử dụng”* – nhờ nhân viên **huỷ phiên** (nút trên trang quản trị, xem mục 4.1). Người khác cũng không xem được giỏ của bạn.

Mã vạch mẫu (15 sản phẩm trong `data/products_seed.json`), ví dụ:

| Mã vạch | Sản phẩm | Giá |
|---|---|---|
| 8934588012341 | Coca Cola lon 330ml | 12.000 |
| 8934588012358 | Pepsi lon 330ml | 11.000 |
| 8935001700011 | Oreo vị vani 137g | 15.000 |
| 8934563138165 | Mì Hảo Hảo tôm chua cay 75g | 4.500 |
| 8934673100019 | Sữa tươi Vinamilk 1L | 32.000 |
| 8935024140015 | Nước suối Aquafina 500ml | 6.000 |

## 4. Quản trị

Mở `/admin`, nhập tài khoản. Có hai loại:

| Tài khoản | Quyền |
|---|---|
| **admin** | Xem + khoá/mở khoá xe, đăng ký xe, huỷ phiên, quản lý sản phẩm |
| **viewer** (nếu cấu hình `VIEWER_USERNAME/PASSWORD`) | Chỉ xem. Không có nút sửa/đăng ký/huỷ, nút khoá bị vô hiệu |

Sai mật khẩu 5 lần liên tiếp → bị khoá đăng nhập 60 giây. Phiên đăng nhập hết hạn sau 8 giờ. Thoát bằng nút **Đăng xuất** ở thanh trên.

Các trang:
- **Tổng quan** (`/admin`): bộ đếm số xe theo trạng thái, danh sách xe (pin, cân, trực tuyến/ngoại tuyến), thanh cảnh báo đang mở. Cập nhật thời gian thực.
- **Cảnh báo** (`/admin/alerts`): lọc theo loại/trạng thái.
  - `LOW_BATTERY`: pin < 20 %. `WEIGHT_MISMATCH`: lệch cân > 100 g trong phiên mua. `OFFLINE`: > 15 s không có tin từ xe.
  - Cảnh báo tự đóng khi điều kiện hết.
- **Sản phẩm** (`/admin/products`): bảng danh mục, tìm theo tên/mã vạch, **＋ Thêm sản phẩm**, **Sửa**, **Ẩn/Hiện** (không xoá hẳn để giữ lịch sử giỏ hàng). Mã vạch 4–64 ký tự chữ/số/dấu `-`. Khối lượng dùng tính *cân dự kiến* của giỏ (lệch > 100 g sinh cảnh báo). Sản phẩm thêm xong khách quét/nhập được ngay.
- **＋ Đăng ký xe** (nút ở trang Tổng quan): nhập mã xe (trùng `CART_ID` trong firmware hoặc xe ảo Wokwi). Xe hiện *Offline* cho tới khi gửi tin nhắn đầu tiên.
- **Chi tiết xe** (`/admin/carts/<mã xe>`): biểu đồ pin/cân, phiên hiện tại, **Khoá xe / Mở khoá xe**, **Huỷ phiên này**.
  - Khoá chỉ có hiệu lực khi xe **xác nhận (ACK)**. Xe ngoại tuyến → báo lỗi; xe không phản hồi sau ~5 s → báo hết thời gian.

### 4.1 Huỷ phiên đang treo của khách

Cách dễ nhất: `/admin` → bấm vào xe → **Huỷ phiên này** → xác nhận (giỏ của khách bị xoá, xe về *Sẵn sàng*). Chỉ tài khoản **admin** thấy nút này.

Cách khác bằng API (lấy `$TOKEN` như mục 6):

```bash
curl -H "Authorization: Bearer $TOKEN" localhost:8000/api/carts/CART_001/session     # xem "id"
curl -X POST -H "Authorization: Bearer $TOKEN" localhost:8000/api/sessions/<id>/cancel
```

## 5. Giả lập phần cứng

### 5.1 Trang `/simulator` (dễ nhất)

Mỗi xe hiện như một thiết bị: màn hình, đèn kết nối MQTT, máy quét, cân, pin, nút ngắt mạng, nhật ký. Thao tác ở đây đi qua MQTT như xe thật, và thấy ngay ở `/customer` và `/admin`. Cột *Hệ thống thấy* cho biết Backend đang ghi nhận gì về xe.

Kịch bản demo nhanh (3 phút):
1. `/customer` chọn CART_001.
2. `/simulator`: quét vài sản phẩm → giỏ khách cập nhật.
3. Thêm **vật lạ** (cộng gram) → cảnh báo lệch cân ở trang khách và `/admin`.
4. Đặt **pin yếu** → cảnh báo `LOW_BATTERY`; **ngắt mạng** > 15 s → `OFFLINE`, bật lại → xe quay lại và **giữ nguyên giỏ**.
5. `/admin` → chi tiết xe → **Khoá xe** → khách thấy banner khoá. **Mở khoá**.
6. Khách **Thanh toán** → xe về sẵn sàng.

Trang này cần Simulator đang chạy; nếu tắt Simulator, trang báo lỗi.

### 5.2 Dòng lệnh Simulator

Khi chạy `python -m simulator.main` (không `--no-cli`), gõ trong terminal đó:

| Lệnh | Tác dụng |
|---|---|
| `carts` | Trạng thái các xe |
| `catalog` | Danh sách sản phẩm (số thứ tự, mã vạch, tên, gram) |
| `scan <xe> <mã vạch\|số thứ tự> [remove]` | Quét thêm (hoặc bỏ) sản phẩm |
| `unknown <xe>` | Quét mã không tồn tại → bị từ chối |
| `weight <xe> <±gram>` / `fix-weight <xe>` | Gây / sửa lệch cân |
| `low-battery <xe> [%]` / `recharge <xe>` | Pin yếu (mặc định 15 %) / sạc đầy |
| `offline <xe> [giây]` / `online <xe>` | Mất / nối lại mạng |
| `log <xe>` | Nhật ký xe |
| `quit` | Thoát |

`<xe>` là mã như `CART_001` (xem `carts`). Script `run_local.sh` chạy Simulator ở nền (`--no-cli`) nên không có dòng lệnh – dùng trang `/simulator` hoặc chạy từng phần.

## 6. Đăng ký thêm xe

Backend chỉ nhận xe đã đăng ký (mã lạ bị bỏ qua). Đăng ký bằng admin trong Swagger hoặc `curl` (cần token, xem mục 8):

```bash
TOKEN=$(curl -s localhost:8000/api/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<mật khẩu>"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -X POST localhost:8000/api/carts -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"cart_id":"CART_004","name":"Xe thật số 4"}'
```

Với chế độ bảo mật, thêm bí mật cho xe mới: `python -m tools.provision --add-cart CART_004`.

## 7. Dùng xe ESP32 thật (khi có linh kiện)

Tóm tắt, chi tiết ở [firmware/README.md](../firmware/README.md):
1. Máy chủ cho mạng LAN kết nối: `MQTT_BIND=0.0.0.0 scripts/run_local.sh` (mở tường lửa cổng 1883).
2. `cp firmware/include/cart_config.example.h firmware/include/cart_config.h` rồi sửa `WIFI_SSID`, `WIFI_PASS`, `MQTT_HOST` (**IP máy chủ**, không dùng `localhost`), `CART_ID`.
3. Đăng ký xe (mục 6), rồi `pio run -e esp32dev -t upload` và `pio device monitor`.
4. Chưa có linh kiện: mô phỏng bằng Wokwi, 3 cách trong firmware/README.md (độc lập, qua broker công cộng, qua cầu nối serial).

Phần firmware **chưa được build bằng PlatformIO thật hay chạy trên board**; hãy báo lỗi biên dịch nếu gặp.

## 8. Gọi API trực tiếp (Postman / curl)

- Thư mục `postman/` có sẵn collection + environment. Chạy request **Login** trước, token tự lưu vào biến `admin_token`.
- Mọi request quản trị gửi header `Authorization: Bearer <token>`.
- Danh mục sản phẩm, danh sách xe (đã che thông tin phiên) và bắt đầu phiên là công khai. Chi tiết quyền: [SECURITY.md §3.1](SECURITY.md#31-vai-trò-và-quyền-rest), danh sách endpoint: [api/API.md](api/API.md).

## 9. Cấu hình hay dùng

Mọi cấu hình là biến môi trường, đặt trước lệnh chạy (xem đầy đủ trong [.env.example](../.env.example)).

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `ADMIN_PASSWORD` | Mật khẩu admin | ngẫu nhiên mỗi lần |
| `VIEWER_USERNAME` / `VIEWER_PASSWORD` | Tạo tài khoản chỉ xem | không có |
| `API_PORT` | Cổng giao diện + REST | 8000 |
| `MQTT_BIND` | Địa chỉ broker nghe (`0.0.0.0` cho LAN) | 127.0.0.1 |
| `BATTERY_LOW_PERCENT` / `WEIGHT_TOLERANCE_G` / `HEARTBEAT_TIMEOUT_S` | Ngưỡng cảnh báo | 20 / 100 / 15 |
| `SIM_CARTS` | Số xe giả lập | 3 |
| `TOKEN_SECRET` | Giữ phiên đăng nhập qua lần khởi động lại | ngẫu nhiên mỗi lần |

Dữ liệu lưu ở `data/smartcart.db` (SQLite). Xoá file này (khi đã tắt hệ thống) để về dữ liệu mẫu ban đầu.

## 10. Xử lý sự cố

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| Quên mật khẩu admin | Chạy lại với `ADMIN_PASSWORD=...`; chế độ bảo mật: xem `secrets/secure.env` |
| `429` / “khoá đăng nhập” | Sai quá 5 lần; chờ 60 s |
| Đang đăng nhập bỗng bị đưa về màn đăng nhập | Token hết hạn (8 giờ), hoặc Backend khởi động lại mà không đặt `TOKEN_SECRET` → đăng nhập lại |
| Không có xe nào chọn được | Simulator chưa chạy, hoặc xe đang dùng/bị khoá. Kiểm tra `/admin` hoặc `/simulator` |
| Xe hiện “đang được sử dụng” nhưng không phải bạn | Phiên cũ còn treo: admin vào chi tiết xe bấm **Huỷ phiên này** (mục 4.1) |
| Quét mà giỏ không đổi | Xe đang khoá, chưa có phiên (khách chưa chọn xe), hoặc mã vạch không có trong danh mục (xem sự kiện bị từ chối) |
| Trang `/simulator` báo lỗi | Simulator chưa chạy hoặc cổng 8090 bị chiếm |
| Backend báo không kết nối MQTT | Broker chưa chạy / sai `MQTT_HOST`/`MQTT_PORT` (hoặc sai tài khoản/TLS ở chế độ bảo mật – log nói rõ lý do) |
| Chế độ bảo mật: xe/Simulator bị bỏ qua | Sai khoá ký hoặc lệch giờ > 300 s; xem bộ đếm `stats.mqtt_bad_signature` / `stats.mqtt_unsigned` trong `GET /api/health` (gửi kèm token admin/viewer) |
| ESP32 không lên ONLINE | `MQTT_HOST` sai/tường lửa; xe chưa đăng ký; `CART_ID` khác với đã đăng ký; (bảo mật) `cart_secrets.h` của xe khác |
| Cổng 8000/8081/1883 đã bị dùng | Đổi `API_PORT`, `WS_PORT`, `MQTT_PORT` hoặc tắt chương trình đang chiếm |

## 11. Chạy kiểm thử

```bash
pip install -r requirements-dev.txt && python -m playwright install chromium
python -m pytest tests -q                     # 144 test, vài phút
bash firmware/tools/run_native_tests.sh       # 38 test firmware (cần g++)
```

Chi tiết: [TESTING.md](TESTING.md).
