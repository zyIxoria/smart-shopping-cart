# Bảo mật hệ thống Smart Shopping Cart

Tài liệu này ánh xạ các biện pháp đã cài đặt tới **Chương 4 – An toàn và Bảo mật IoT** (4.2 các dạng tấn công, 4.3 OWASP IoT Top 10) và nói rõ cái gì **đã làm & đã test**, cái gì **chưa**.

Ba nhóm biện pháp, tắt/bật độc lập:

| Nhóm | Bảo vệ | Bật bằng |
|---|---|---|
| **Đăng nhập Admin/API** | Giao diện quản trị, REST, WebSocket | `AUTH_ENABLED=1` (**mặc định BẬT**) |
| **MQTT: đăng nhập + ACL + TLS** | Đường truyền xe ↔ Backend | broker chạy với `--users` và `--tls-*` (hoặc `mosquitto/secure/`), client đặt `MQTT_USERNAME/MQTT_PASSWORD/MQTT_TLS` |
| **Ký HMAC từng message** | Toàn vẹn + xác thực nguồn + chống phát lại | `DEVICE_MASTER_KEY` (Backend/Simulator) / `CART_KEY_HEX` (firmware) |

Chạy tất cả cùng lúc: `bash scripts/run_secure.sh` (lần đầu tự chạy `python -m tools.provision`). Chạy nhanh không bảo mật tầng MQTT: `scripts/run_local.sh` (vẫn có đăng nhập admin với mật khẩu ngẫu nhiên in ra màn hình).

## 1. Đối chiếu OWASP IoT Top 10 (slide 4.3)

| Mã | Rủi ro | Biện pháp trong dự án | Trạng thái |
|---|---|---|---|
| I1 | Giao diện quản trị không an toàn | Trang `/admin`, `/simulator` đòi đăng nhập; mọi route API mặc định **đóng** (`auth="admin"`), route công khai phải khai báo rõ; header `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Content-Security-Policy` (chỉ script cùng origin, cấm nhúng iframe), `Cache-Control: no-store` cho API; giới hạn body 64 KB; kiểm tra `Origin` của WebSocket | ✅ đã test |
| I2 | Xác thực/phân quyền yếu | PBKDF2-HMAC-SHA256 (200 000 vòng + salt); **không có mật khẩu mặc định** (không đặt `ADMIN_PASSWORD` ⇒ sinh ngẫu nhiên mỗi lần chạy); khoá đăng nhập tạm sau `LOGIN_MAX_ATTEMPTS` lần sai (theo cặp IP+user); thông báo lỗi không lộ user nào tồn tại, thời gian xử lý đều; token HMAC có hạn + thu hồi khi đăng xuất; 3 vai trò admin/viewer/khách; **khách chỉ thao tác trên đúng phiên của mình (chống IDOR)**; xe MQTT mỗi xe một tài khoản + ACL | ✅ đã test |
| I3 | Dịch vụ mạng không an toàn | Broker **không cho ẩn danh** khi bật `--users`; ACL chặn xe giả danh xe khác / tự ra lệnh; gói đầu tiên bắt buộc là CONNECT; giới hạn kích thước gói; WebSocket giới hạn 200 kết nối; API điều khiển Simulator mặc định chỉ `127.0.0.1` | ✅ đã test (broker Python); ⚠️ Mosquitto thật chưa chạy |
| I4 | Thiếu mã hoá/kiểm tra toàn vẹn tầng giao vận | **TLS 1.2+** cho MQTT (client kiểm chứng chứng chỉ bằng CA riêng ⇒ chống broker giả); **HMAC-SHA256** trên từng message ⇒ toàn vẹn + xác thực nguồn kể cả khi TLS bị tắt/sai cấu hình | ✅ đã test; ⚠️ HTTP/WebSocket của Backend **chưa có TLS** (xem §6) |
| I5 | Quyền riêng tư | Không lưu thông tin cá nhân khách; người chưa đăng nhập chỉ thấy trạng thái xe, **không** thấy số món/tiền/cân của phiên người khác (REST và WebSocket); `/api/health` công khai không lộ thống kê nội bộ | ✅ đã test |
| I6 | Giao diện Cloud không an toàn | API phía Backend áp dụng I1/I2; OpenAPI mô tả quyền của từng endpoint (`bearerAuth`) | ✅ |
| I7 | Giao diện Mobile không an toàn | Giao diện web responsive dùng chung API đã bảo vệ; token khách giữ trong `localStorage` (hết hạn sau `SESSION_TOKEN_TTL_S`), token admin chỉ trong `sessionStorage`, **không đặt token trong URL** | ✅ |
| I8 | Cấu hình bảo mật không đủ | Mọi thông số qua biến môi trường (`.env.example`); mặc định an toàn (auth bật, không mật khẩu mặc định); log cảnh báo khi cấu hình yếu (`TOKEN_SECRET` ngắn, chấp nhận message không ký, `TLS_INSECURE`) | ✅ |
| I9 | Phần mềm/firmware không an toàn | Lệnh xuống xe bị giới hạn 4 loại cố định + phải ký đúng khoá xe ⇒ kẻ chen vào broker không điều khiển được xe; firmware kiểm tra độ dài, cú pháp JSON, từ chối khoá trùng lặp. **Chưa có OTA/secure boot/ký firmware** | ⚠️ một phần |
| I10 | Thiếu bảo mật vật lý | Mỗi xe một khoá riêng (lộ một xe không lộ xe khác, không lộ khoá chủ). **Chưa** bật flash encryption / secure boot / khoá cổng debug của ESP32 | ⚠️ một phần |

## 2. Đối chiếu các dạng tấn công (slide 4.2)

| Tấn công | Cách hệ thống phòng |
|---|---|
| **Fake Control Server** (máy chủ điều khiển giả) | Xe kiểm chứng chứng chỉ TLS của broker bằng CA đã nạp sẵn; kể cả khi qua được, lệnh phải mang chữ ký HMAC đúng khoá của **xe đó** ⇒ broker/máy chủ giả không điều khiển được xe |
| **Attack on server open ports** | Broker bắt đăng nhập + ACL; REST mặc định đóng; WebSocket chỉ phát sự kiện đã lọc theo quyền, không nhận lệnh |
| **Steal Credential** | PBKDF2 + khoá tạm đăng nhập; token ngắn hạn thu hồi được; bí mật nằm ngoài git (`secrets/`, `cart_secrets.h` đã `.gitignore`); mật khẩu MQTT riêng từng xe |
| **Sniff data** | TLS cho MQTT; HMAC giữ nguyên toàn vẹn dù bị nghe lén |
| **Inject bad configuration or firmware** | Lệnh sai chữ ký/quá cũ/khác xe bị bỏ ở cả Backend→Xe và Xe→Backend; chưa chống được việc nạp firmware độc qua cổng USB (vật lý) |
| **Attack on device open ports** | Firmware không mở cổng lắng nghe nào (chỉ kết nối ra broker) |

## 3. Cơ chế chi tiết

### 3.1 Vai trò và quyền REST

| Vai trò | Lấy token từ | Được làm |
|---|---|---|
| anonymous | – | `GET /api/products*`, `GET /api/carts` (đã che phiên), `GET /api/carts/{id}`, `GET /api/health` (rút gọn), `POST /api/auth/login`, `GET /api/auth/config`, `POST /api/sessions` (giới hạn 20 lần/phút/IP) |
| customer | `POST /api/sessions` (trường `token`) | đọc/thêm/xoá/thanh toán/huỷ **đúng phiên của mình**, `GET /api/carts/{xe của mình}/session` |
| viewer | `POST /api/auth/login` (`VIEWER_USERNAME/PASSWORD`) | mọi thao tác **đọc** của admin (cảnh báo, telemetry, lệnh, phiên) |
| admin | `POST /api/auth/login` | tất cả: đăng ký xe, khoá/mở khoá, huỷ phiên bất kỳ, thêm/sửa/ẩn sản phẩm |

Gửi token: `Authorization: Bearer <token>`. 401 `UNAUTHENTICATED` (thiếu/sai/hết hạn/đã thu hồi), 403 `FORBIDDEN` (đúng người nhưng thiếu quyền), 429 `TOO_MANY_REQUESTS` (kèm `Retry-After`). Chính sách của từng route nằm cạnh khai báo trong `backend/api/routes.py`; chính sách không biết ⇒ từ chối.

### 3.2 WebSocket (`ws://host:8081/ws`)

Kết nối mới ở quyền **ẩn danh**. Muốn quyền cao hơn, client gửi tin đầu tiên `{"type":"AUTH","token":"..."}` (token **không** nằm trong URL ⇒ không vào log truy cập). Server trả `AUTHED` hoặc `AUTH_FAILED`.

| Sự kiện | staff | khách (xe của mình) | ẩn danh |
|---|---|---|---|
| `CART_UPDATED` | đầy đủ | đã che phiên | đã che phiên |
| `SCAN_REJECTED` | ✅ | ✅ (chỉ xe mình) | ❌ |
| `CART_EVENT`, `ALERT_*`, `COMMAND_ACK` | ✅ | ❌ | ❌ |

Token hết hạn giữa chừng ⇒ kết nối tự hạ xuống ẩn danh.

### 3.3 MQTT: tài khoản và ACL

Ba vai trò (file `secrets/mqtt_users.json`, mật khẩu băm PBKDF2; Mosquitto dùng `passwd` + `acl` cùng được sinh ra):

| Vai trò (tên đăng nhập) | Được publish | Được subscribe |
|---|---|---|
| `backend` | `ROOT/+/command` | `ROOT/+/{scan,event,telemetry,heartbeat,ack}` |
| `cart` (tên = `cart_id`) | `ROOT/<cart_id>/{scan,event,telemetry,heartbeat,ack}` | `ROOT/<cart_id>/command` |
| `sim` (Simulator, nhiều xe) | `ROOT/+/{scan,...,ack}` | `ROOT/+/command` |

Vi phạm ACL: publish bị bỏ lặng lẽ (giống Mosquitto) và ghi log; subscribe nhận mã từ chối `0x80`. Đăng nhập sai ⇒ CONNACK 4; client in lý do lên log (một lần mỗi loại lỗi).

### 3.4 Ký message (HMAC-SHA256)

```
sig = HMAC-SHA256(cart_key, message_id "\n" cart_id "\n" timestamp "\n" kind "\n" data_raw)    (hex thường, 64 ký tự)
cart_key = HMAC-SHA256(DEVICE_MASTER_KEY, "smartcart/device-key/v1\0" + cart_id)
```

- `kind` = tên topic (`scan`, `command`, …) ⇒ gói `scan` không phát lại thành `command` được.
- `data_raw` là **nguyên văn chuỗi JSON của `data`** nhận được – người nhận tách bằng bộ phân tích cấp gốc, **không** chuẩn hoá lại ⇒ Python và C++ không cần sinh JSON giống nhau từng byte. Khoá `data` trùng lặp ở cấp gốc bị từ chối (chống nhập nhằng bộ phân tích).
- Thứ tự trường: `message_id, cart_id, schema_version, timestamp, sig, data`.
- Phát lại: Backend kiểm chữ ký **trước** khi chạm bộ nhớ chống trùng/DB (gói giả không đầu độc được `message_id`), sau đó loại gói trùng `message_id` và gói lệch giờ > `MAX_CLOCK_SKEW_S`. Xe làm tương tự với lệnh (`command_id` đã xử lý ⇒ chỉ gửi lại ACK cũ; lệnh quá cũ bị bỏ).
- Chế độ chuyển đổi: `REQUIRE_SIGNATURE=0` cho phép gói **không ký** (xe cũ) nhưng gói **có ký sai vẫn bị loại**. Mặc định: có `DEVICE_MASTER_KEY` ⇒ bắt buộc ký.

## 4. Vận hành

```bash
python -m tools.provision [--carts CART_001,CART_007] [--host 192.168.1.20]   # sinh ./secrets (một lần)
bash scripts/run_secure.sh                                                      # broker TLS+ACL, Backend, Simulator ký HMAC
python -m tools.provision --add-cart CART_004                                   # thêm xe mới
```

Với xe ESP32 thật: sao chép `secrets/firmware/<CART>/cart_secrets.h` vào `firmware/include/` (xem [firmware/README.md](../firmware/README.md#bảo-mật-mqtt-tls--hmac)). Firmware tự từ chối chạy nếu `CART_ID` không khớp file bí mật.

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `AUTH_ENABLED` | bật đăng nhập API/WS | `1` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_PASSWORD_HASH` | tài khoản admin (có thể đưa hash PBKDF2 thay mật khẩu thô) | `admin` / ngẫu nhiên |
| `VIEWER_USERNAME` / `VIEWER_PASSWORD` | tài khoản chỉ xem (tuỳ chọn) | – |
| `TOKEN_SECRET` | khoá ký token (đặt cố định để token sống qua lần khởi động lại) | ngẫu nhiên mỗi lần chạy |
| `ADMIN_TOKEN_TTL_S` / `SESSION_TOKEN_TTL_S` | hạn token admin / khách | 8 giờ / 4 giờ |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCKOUT_S` | khoá đăng nhập tạm | 5 lần / 60 s |
| `MQTT_USERNAME` `MQTT_PASSWORD` `MQTT_TLS` `MQTT_CA_FILE` | client MQTT (Backend/Simulator/cầu nối) | – |
| `DEVICE_MASTER_KEY` / `REQUIRE_SIGNATURE` | ký message | – / bắt buộc nếu có khoá |

## 5. Đã kiểm thử

| Nội dung | Test |
|---|---|
| Băm mật khẩu, token (sửa payload/hết hạn/khoá khác), ma trận quyền, mật khẩu tự sinh | `tests/integration/test_auth.py` |
| Đăng nhập sai/khoá tạm/hồi phục, anonymous chỉ vào được endpoint công khai, viewer chỉ đọc, admin đủ quyền, **IDOR giữa hai khách**, đăng xuất thu hồi token, rate-limit tạo phiên, header an toàn + giới hạn body, OpenAPI có `security` | `test_auth.py` |
| WebSocket theo vai trò (ẩn danh/khách/admin), che chi tiết giỏ hàng, kiểm tra `Origin` | `test_auth.py` |
| Broker: bắt buộc đăng nhập, sai mật khẩu/user lạ, ACL (giả danh xe khác, tự ra lệnh, nghe lệnh xe khác), gói trước CONNECT bị đóng | `tests/integration/test_mqtt_security.py` |
| TLS: mã hoá thật, từ chối CA lạ, cổng TLS không nhận kết nối thuần | `test_mqtt_security.py` |
| End-to-end bảo mật (TLS + đăng nhập + ACL + HMAC): luồng quét/khoá đúng; gói không ký/ký sai khoá/sửa sau khi ký/sai topic bị loại; phát lại bị chặn; gói cũ bị loại; xe bỏ lệnh không ký/khoá xe khác/quá cũ; chế độ chuyển đổi | `test_mqtt_security.py` |
| SHA-256/HMAC trong firmware theo vector chuẩn (FIPS 180-4, RFC 4231), bộ tách JSON cấp gốc, độ mới của timestamp | `firmware/test` (38 test native) |
| **C++ ↔ Python**: HMAC giống hệt; Python xác minh gói firmware ký; firmware xác minh lệnh Backend ký và từ chối đúng 5 trường hợp giả | `tests/unit/test_firmware_protocol.py` |
| Giao diện: màn đăng nhập, sai mật khẩu, WebSocket xác thực, viewer không khoá được xe, khách không vào được phiên người khác | `tests/e2e/test_ui_auth.py` |
| Chạy thật `scripts/run_secure.sh` + thao tác bằng trình duyệt | thủ công (đã làm) |

## 6. Giới hạn đã biết (đọc trước khi dùng ngoài môi trường học tập)

1. **HTTP và WebSocket của Backend chưa có TLS.** Token Bearer đi qua mạng dạng rõ nếu không có TLS ở lớp trước. Khi triển khai thật: đặt Backend sau reverse proxy HTTPS (nginx/Caddy) và dùng `wss://`; đặt `CORS_ORIGINS` là origin cụ thể (mặc định `*`; vì dùng Bearer chứ không dùng cookie nên `*` không gây CSRF, nhưng vẫn nên siết).
2. Thu hồi token, khoá đăng nhập tạm và rate-limit nằm **trong bộ nhớ một tiến trình**: khởi động lại là quên; chạy nhiều tiến trình thì không chia sẻ. Địa chỉ client lấy từ kết nối trực tiếp (không đọc `X-Forwarded-For`), nên sau reverse proxy mọi người cùng một IP.
3. Bộ nhớ chống trùng `message_id` (2000 gói) mất khi Backend khởi động lại: trong cửa sổ `MAX_CLOCK_SKEW_S` kẻ nghe lén có thể phát lại một gói hợp lệ. TLS + ACL là lớp chặn chính; muốn chặt hơn, giảm `MAX_CLOCK_SKEW_S` hoặc lưu `message_id` vào DB.
4. Khoá HMAC đối xứng: ai lấy được `cart_secrets.h` của một xe giả được **xe đó** (không phải xe khác). Chưa có xoay khoá tự động (đổi `DEVICE_MASTER_KEY` + nạp lại mọi xe).
5. Chưa có secure boot / flash encryption / ký firmware / OTA (I9, I10); cổng USB debug của ESP32 còn mở.
6. API điều khiển Simulator (`:8090`) **không có xác thực**, chỉ an toàn vì mặc định bind `127.0.0.1`; trang `/simulator` vì thế chỉ có nghĩa khi dev local.
7. `tools/dev_broker.py` là broker dev: không giới hạn tốc độ, không lưu retained. Cấu hình **Mosquitto bảo mật** (`mosquitto/secure/`, `secrets/mosquitto/`) và profile `secure` của Docker Compose **chưa được chạy thử** (không có Mosquitto/Docker ở môi trường build).
8. TLS phía ESP32 (`WiFiClientSecure` + `MQTT_CA_PEM`) mới được **biên dịch thử với header giả lập**, chưa chạy trên board thật. ESP32 cần đồng hồ đúng (NTP) trước khi bắt tay TLS – firmware đã chờ NTP rồi mới kết nối.
9. Chưa quét lỗ hổng (SAST/DAST), chưa pentest, chưa có kiểm thử fuzz.
