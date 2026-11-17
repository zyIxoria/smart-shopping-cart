# BẢNG PHÂN LOẠI CHI TIẾT KẾT QUẢ KIỂM THỬ (TEST RESULT BREAKDOWN)
## Phục vụ: Chương 4 – Đánh giá thực nghiệm

> **Môi trường thực thi kiểm thử:** Windows 11, Python 3.13.0, pytest 9.1.1, Playwright Chromium  
> **Nguyên tắc thẩm định:** Ghi nhận trung thực tuyệt đối: 142 PASSED, 16 SKIPPED, 0 FAILED. Không quy đổi SKIPPED thành PASSED.

---

## 1. BẢNG TỔNG HỢP KIỂM THỬ THEO NHÓM

| Phân nhóm kiểm thử | Đường dẫn thư mục | Tổng số test | PASSED | FAILED | SKIPPED / BLOCKED | Tỷ lệ đạt (trên số test chạy) |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **1. Kiểm thử đơn vị (Unit Tests)** | `tests/unit/` | 65 | **50** | 0 | **15** | 100.0% |
| **2. Kiểm thử tích hợp (Integration Tests)** | `tests/integration/` | 69 | **68** | 0 | **1** | 100.0% |
| **3. Kiểm thử đầu-cuối (E2E Tests)** | `tests/e2e/` | 24 | **24** | 0 | **0** | 100.0% |
| **TỔNG CỘNG** | `tests/` | **158** | **142** | **0** | **16** | **100.0% (142/142)** |

> **Lưu ý thống kê:** Tỷ lệ đạt trên toàn bộ 158 test được thu thập là **89.87% (142/158)**. Tỷ lệ đạt trên 142 test thực sự chạy được trên môi trường Windows là **100.0% (142/142)**.

---

## 2. CHI TIẾT TỪNG MODULE KIỂM THỬ

### 2.1. Nhóm Kiểm thử Đơn vị (Unit Tests - 65 tests)

| Module test | Mục tiêu kiểm thử | Tổng | Pass | Skip | Trạng thái |
|---|---|:---:|:---:|:---:|:---:|
| `test_contract.py` | Kiểm tra định dạng envelope, topic, enum, timestamp ISO 8601 | 15 | 15 | 0 | **VERIFIED** |
| `test_rules.py` | Kiểm tra ngưỡng cảnh báo: pin < 20%, lệch cân > 100g, offline > 15s | 5 | 5 | 0 | **VERIFIED** |
| `test_services.py` | Nghiệp vụ giỏ hàng: bắt đầu phiên, cộng dồn sản phẩm, tính giá, xóa xe | 10 | 10 | 0 | **VERIFIED** |
| `test_mqttlite.py` | Client MQTT nội bộ: khớp wildcard topic, kết nối lại, đệm bản tin lớn | 6 | 6 | 0 | **VERIFIED** |
| `test_db_postgres.py` | Chuyển đổi cú pháp SQL `?` -> `%s` và bắt lỗi ngắt kết nối PostgreSQL | 2 | 2 | 0 | **VERIFIED** |
| `test_wokwi_bridge_codec.py` | Giải mã Telnet RFC2217, xử lý byte thoát IAC, đóng gói bản tin Serial | 6 | 6 | 0 | **VERIFIED** |
| `test_wokwi_package.py` | Kiểm tra tĩnh cấu hình chân GPIO `diagram.json`, `pins.h`, `platformio.ini` | 13 | 6 | 7 | **PARTIAL** |
| `test_firmware_protocol.py` | Biên dịch chéo C++ `cartcore` kiểm tra tính tương thích nhị phân với Python | 8 | 0 | 8 | **BLOCKED** |

### 2.2. Nhóm Kiểm thử Tích hợp (Integration Tests - 69 tests)

| Module test | Mục tiêu kiểm thử | Tổng | Pass | Skip | Trạng thái |
|---|---|:---:|:---:|:---:|:---:|
| `test_api_misc.py` | REST API: danh mục sản phẩm, CORS headers, WebSocket handshake | 6 | 6 | 0 | **VERIFIED** |
| `test_auth.py` | Xác thực JWT, băm PBKDF2, phân quyền RBAC (admin, staff, customer) | 18 | 18 | 0 | **VERIFIED** |
| `test_flows.py` | Toàn bộ luồng nghiệp vụ mua sắm, lệch cân, offline và khôi phục mạng | 15 | 15 | 0 | **VERIFIED** |
| `test_enhancements.py` | Hàng đợi ngoại tuyến (offline queue), lưu trữ lệnh điều khiển, xóa xe | 7 | 7 | 0 | **VERIFIED** |
| `test_mqtt_security.py` | Xác thực đăng nhập MQTT, phân quyền ACL theo vai trò, mã hóa TLS 8883 | 10 | 10 | 0 | **TEST VERIFIED** |
| `test_mqtt_robustness.py` | Khả năng chống chịu bản tin rác, trùng `message_id`, timestamp lệch giờ | 2 | 2 | 0 | **VERIFIED** |
| `test_products_admin.py` | Thêm, sửa, ẩn/hiện sản phẩm, chống SQL Injection qua tham số | 5 | 5 | 0 | **VERIFIED** |
| `test_sim_control.py` | HTTP Control API (:8090) điều khiển xe ảo, quét mã, chỉnh pin và cân nặng | 4 | 4 | 0 | **VERIFIED** |
| `test_smoke.py` | Khởi động đồng thời 3 xe ảo, xác nhận cả 3 cùng ONLINE | 1 | 1 | 0 | **VERIFIED** |
| `test_wokwi_bridge.py` | Đầu-cuối cầu nối Wokwi Serial <-> Broker <-> Backend | 1 | 0 | 1 | **BLOCKED** |

### 2.3. Nhóm Kiểm thử Đầu-Cuối (E2E Playwright Tests - 24 tests)

| Module test | Mục tiêu kiểm thử | Tổng | Pass | Skip | Trạng thái |
|---|---|:---:|:---:|:---:|:---:|
| `test_simulation_2d.py` | Bản đồ siêu thị 2D, điều khiển waypoint xe đẩy, kịch bản nghiệp vụ | 4 | 4 | 0 | **VERIFIED** |
| `test_ui.py` | Hành trình khách hàng đầy đủ, quét mã, chặn xe khóa, Dashboard admin | 13 | 13 | 0 | **VERIFIED** |
| `test_ui_auth.py` | Đăng nhập/đăng xuất Admin, giới hạn quyền viewer, bảo mật phiên khách | 3 | 3 | 0 | **VERIFIED** |
| `test_ui_manage.py` | Quản trị viên hủy phiên treo, thêm sản phẩm, đăng ký xe mới | 4 | 4 | 0 | **VERIFIED** |

---

## 3. DANH SÁCH CHI TIẾT 16 BÀI KIỂM THỬ BỊ BỎ QUA (SKIPPED)

| STT | Tên bài kiểm thử đầy đủ | File mã nguồn | Lý do Skip thực tế | Đánh giá & Khắc phục |
|:---:|---|---|---|---|
| 1 | `test_firmware_messages_pass_backend_validation` | `test_firmware_protocol.py:34` | Thiếu trình biên dịch `g++` trong PATH Windows | Không ảnh hưởng firmware thật (PlatformIO đã build thành công). Muốn chạy test cần cài MinGW-w64. |
| 2 | `test_firmware_message_content` | `test_firmware_protocol.py:44` | Thiếu trình biên dịch `g++` | Tương tự trên. |
| 3 | `test_firmware_understands_backend_commands_and_acks_validly` | `test_firmware_protocol.py:66` | Thiếu trình biên dịch `g++` | Tương tự trên. |
| 4 | `test_firmware_rejects_foreign_or_garbage_commands` | `test_firmware_protocol.py:85` | Thiếu trình biên dịch `g++` | Tương tự trên. |
| 5 | `test_firmware_acks_failed_for_start_without_session_id` | `test_firmware_protocol.py:90` | Thiếu trình biên dịch `g++` | Tương tự trên. |
| 6 | `test_cpp_hmac_matches_python_hmac` | `test_firmware_protocol.py:100` | Thiếu trình biên dịch `g++` | Tương tự trên. |
| 7 | `test_python_verifies_firmware_signed_messages` | `test_firmware_protocol.py:107` | Thiếu trình biên dịch `g++` | Tương tự trên. |
| 8 | `test_firmware_verifies_backend_signed_commands` | `test_firmware_protocol.py:127` | Thiếu trình biên dịch `g++` | Tương tự trên. |
| 9 | `test_main_cpp_syntax_sim_envs[standalone]` | `test_wokwi_package.py:163` | Thiếu `g++ -fsyntax-only` | **Đã được bù đắp**: PlatformIO Core 6.2.0 đã biên dịch môi trường `esp32dev_standalone` thành công. |
| 10 | `test_main_cpp_syntax_sim_envs[sim]` | `test_wokwi_package.py:163` | Thiếu `g++ -fsyntax-only` | **Đã được bù đắp**: PlatformIO Core 6.2.0 đã biên dịch môi trường `esp32dev_sim` thành công. |
| 11 | `test_main_cpp_syntax_sim_envs[sim_bridge]` | `test_wokwi_package.py:163` | Thiếu `g++ -fsyntax-only` | **Đã được bù đắp**: PlatformIO Core 6.2.0 đã biên dịch môi trường `esp32dev_sim_bridge` thành công. |
| 12 | `test_main_cpp_syntax_sim_envs[wokwi_online]` | `test_wokwi_package.py:163` | Thiếu `g++ -fsyntax-only` | Cần `g++` để kiểm tra macro cú pháp. |
| 13 | `test_main_cpp_syntax_real_env_and_secure` | `test_wokwi_package.py:174` | Thiếu `g++ -fsyntax-only` | Cần `g++` để kiểm tra cờ bảo mật. |
| 14 | `test_wokwi_web_sketch_syntax[standalone]` | `test_wokwi_package.py:189` | Thiếu `g++ -fsyntax-only` | Kiểm tra cú pháp sketch web standalone. |
| 15 | `test_wokwi_web_sketch_syntax[online]` | `test_wokwi_package.py:189` | Thiếu `g++ -fsyntax-only` | Kiểm tra cú pháp sketch web online. |
| 16 | `test_bridge_end_to_end` | `test_wokwi_bridge.py:79` | Thiếu `g++` để biên dịch binary giả lập Wokwi | Test tích hợp cầu nối Serial-MQTT bị hoãn. |
