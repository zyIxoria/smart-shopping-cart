# Kiểm thử

```bash
python -m pytest tests -q           # tất cả (vài phút; chạy nền nếu công cụ có giới hạn thời gian)
python -m pytest tests/unit -q      # chỉ unit (< 1 s)
```

Số test: **144** (62 unit · 62 tích hợp · 20 E2E) + **38** test native của firmware (`firmware/tools/run_native_tests.sh`). Kết quả lần chạy cuối ghi ở cuối trang.

## Các tầng

| Tầng | Số test | Phạm vi |
|---|---|---|
| `tests/unit` | 62 | Quy tắc cảnh báo (đúng ngưỡng biên: pin 20 %, lệch 100 g, offline 15 s) · contract MQTT (topic, envelope, từng payload hợp lệ/không hợp lệ) · `mqttlite` ↔ dev broker (wildcard, payload > 64 KB, **tự reconnect + subscribe lại**, stop không sạch rồi start lại) · service với SQLite tạm (seed idempotent, ràng buộc 1 phiên ACTIVE/xe, gộp số lượng, ảnh chụp giá, **rollback checkout**, huỷ phiên, không trùng cảnh báo, LRU dedupe) |
| `tests/integration` | 62 | Backend thật (uvicorn) + broker + 3 Simulator thật, thời gian rút ngắn (heartbeat 0,4 s, OFFLINE sau 1,5 s): luồng quét → giỏ → thanh toán, REMOVE, tiền điều kiện phiên, nhập tay, mã lạ, 3 loại cảnh báo (tạo/không trùng/tự đóng/biên), lệch cân chỉ xét trong phiên, ghi cảnh báo vào `note`, OFFLINE & phục hồi, **reconnect giữ phiên và giỏ**, khoá/mở khoá qua ACK, xe khoá bỏ qua quét + chặn thanh toán, message rác/trùng/quá cũ/xe lạ/`scan_id` trùng, mọi dạng lỗi API, OpenAPI, CORS, **WebSocket handshake + sự kiện realtime**, **API điều khiển Simulator** (quét/pin/cân/ngắt mạng tác động thật lên hệ thống, kiểm tra tham số, CORS), **quản lý sản phẩm** (`test_products_admin.py`: chỉ admin ghi được, thêm/sửa/ẩn/hiện, kiểm tra dữ liệu & 404/409/422, chuỗi kiểu SQL injection chỉ là dữ liệu, sản phẩm mới quét được rồi bị ẩn thì bị từ chối) |
| `tests/e2e` | 20 | Playwright (Chromium) trên UI thật: hành trình khách hàng đầy đủ (chọn xe → quét bằng Simulator → cập nhật không reload → mã lạ → lệch cân → thanh toán → "Shopping Completed / Thank you!"), thêm/xoá tay & huỷ phiên, xe offline/khoá không chọn được, banner khoá, dashboard realtime (bộ đếm, thanh cảnh báo, lọc), trang cảnh báo + bộ lọc, chi tiết xe (biểu đồ, khoá/mở khoá), nút khoá bị vô hiệu khi offline, route lạ, **không tràn ngang trên mobile 390 px**, chế độ mock, **trang `/simulator` điều khiển cả hệ thống** (quét → giỏ khách; vật lạ/pin/ngắt mạng → cảnh báo ở khách & admin; thanh toán → xe về AVAILABLE; báo lỗi khi Simulator tắt), không có lỗi JS console, **quản lý trên UI** (`test_ui_manage.py`: đăng ký xe ảo bằng form + xe "Wokwi giả" gửi MQTT → card Online/pin 77 %, viewer không thấy nút quản lý, admin huỷ phiên treo, thêm/sửa/ẩn sản phẩm) |

## Ma trận yêu cầu → test

| Yêu cầu | Test chính |
|---|---|
| ≥ 3 xe, heartbeat 5 s / telemetry 10 s, kết nối lại | `test_smoke`, `test_reconnect_keeps_session_and_basket`, `test_auto_reconnect_and_resubscribe` |
| Quét mã → giỏ hàng, tổng tiền, thanh toán | `test_scan_flow_and_checkout`, `test_customer_full_journey` |
| Cảnh báo pin < 20 % / lệch cân > 100 g / offline > 15 s | `test_low_battery_*`, `test_battery_threshold_boundary`, `test_weight_*`, `test_offline_detection_and_recovery`, `tests/unit/test_rules.py` |
| Khoá/mở khoá bằng lệnh + ACK | `test_lock_unlock_with_ack`, `test_admin_cart_detail_lock_unlock_and_charts` |
| Chống message trùng / sai / cũ | `test_garbage_duplicate_stale_and_foreign`, `test_duplicate_scan_id_counted_once` |
| Realtime (WebSocket) | `test_websocket_receives_realtime_events`, `test_admin_dashboard_realtime_alerts` |
| Customer UI + Admin UI + mock | toàn bộ `tests/e2e` |
| Đăng nhập, vai trò, khoá đăng nhập, chống IDOR, thu hồi token, rate-limit, header an toàn | `tests/integration/test_auth.py` |
| MQTT user/ACL/TLS; ký HMAC (giả mạo, sửa, phát lại, gói cũ, lệnh giả); chế độ chuyển đổi | `tests/integration/test_mqtt_security.py` |
| HMAC firmware (C++) ↔ Backend (Python) hai chiều, vector SHA-256/HMAC chuẩn | `tests/unit/test_firmware_protocol.py`, `firmware/test` |
| Màn đăng nhập, viewer chỉ xem, người lạ không vào được phiên người khác | `tests/e2e/test_ui_auth.py` (ảnh: `docs/screenshots/login.png`, `viewer.png`, `stranger_blocked.png`) |

| Sơ đồ Wokwi (tên chân theo tài liệu, khớp `pins.h`), `platformio.ini`/`wokwi.toml` nhất quán, gói `wokwi-web/` đồng bộ nguồn, cú pháp `main.cpp` ở mọi chế độ (kể cả TLS) | `tests/unit/test_wokwi_package.py` (**tĩnh**: header Arduino giả, không thay cho build PlatformIO thật) |

Các test bảo mật dùng `PBKDF2_ITERATIONS=2000` (chỉ trong test, cho nhanh); mặc định chạy thật là 200 000 vòng.

## Chưa được kiểm thử

Mosquitto thật (kể cả `mosquitto/secure/` và profile `secure`), TLS trên ESP32 thật, TLS cho HTTP/WebSocket của Backend, Docker Compose, PostgreSQL, build PlatformIO + chạy firmware trên ESP32/linh kiện thật (chỉ `firmware/lib/cartcore` được test; `src/main.cpp` mới kiểm tra cú pháp với header giả lập), tải/hiệu năng, trình duyệt khác Chromium, trang Swagger UI (CDN) – xem [DEVIATIONS.md](DEVIATIONS.md).
Test dùng khoảng thời gian rút ngắn nên không xác nhận được giá trị mặc định 5 s/10 s/15 s trong thời gian thực dài (chỉ được chạy thủ công ngắn bằng `scripts/run_local.sh`).

## Kết quả lần chạy cuối

- `python -m pytest tests -q` → **144 passed** (100 s) trên môi trường build (Python, Chromium/Playwright, broker `tools/dev_broker.py`).
- `firmware/tools/run_native_tests.sh` → **38 tests, 0 failures** (g++ + ASan/UBSan).
- Chạy tay `scripts/run_secure.sh` + trình duyệt: đăng nhập sai/đúng, dashboard realtime, đăng xuất, khách quét qua MQTT TLS có ký HMAC, người lạ bị chặn.
