# BÁO CÁO TỔNG HỢP BẰNG CHỨNG THỰC NGHIỆM
## Phục vụ: Chương 4 – Đánh giá thực nghiệm (Báo cáo đề tài Smart Shopping Cart)

> **Người tổng hợp:** Senior IoT QA Engineer  
> **Ngày lập:** 17/11/2026  
> **Nguyên tắc cốt lõi:** Chỉ ghi nhận bằng chứng kỹ thuật có thể kiểm chứng được (truy xuất từ file log, CSDL, lệnh chạy và ảnh chụp màn hình). Phân định rõ giữa thực tế chạy được và cấu hình lý thuyết.

---

## 1. TỔNG HỢP HIỆN TRẠNG KỸ THUẬT ĐÃ ĐỐI CHỨNG

| Thành phần hệ thống | Trạng thái thực tế | Bằng chứng kỹ thuật | Đánh giá |
|---|---|---|:---:|
| **Thiết bị biên (Edge)** | **Python Simulator** chạy giả lập 3 xe (`CART_001`, `CART_002`, `CART_003`), tự động phát heartbeat (5s) và telemetry (10s) qua MQTT. | `evidence/chapter_4/01_simulator/simulator_state_dump.json` | **VERIFIED** |
| **Firmware ESP32** | Mã nguồn C++ (`main.cpp`, `cartcore`) biên dịch thành công 100% bằng **PlatformIO Core 6.2.0** ra file `.bin`/`.elf`. Chưa có log chạy runtime live với Backend qua mạng. | `evidence/chapter_4/06_esp32_wokwi/platformio_build_evidence.json` | **CODE VERIFIED** |
| **Mô phỏng mạch Wokwi** | Sơ đồ [diagram.json](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/diagram.json) đấu nối 8 linh kiện ảo. Cầu nối [tools/wokwi_bridge.py](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/tools/wokwi_bridge.py) hỗ trợ RFC2217 TCP port 4000. Test bridge bị skip trên Windows do thiếu `g++`. | `tests/unit/test_wokwi_package.py` | **CODE VERIFIED** |
| **MQTT Broker** | Phiên demo local chạy bằng **`tools/dev_broker.py`** trên port 1883 (PID 22832). **Không chạy Eclipse Mosquitto** trên Windows. | Output `Get-NetTCPConnection -LocalPort 1883` | **VERIFIED** |
| **Bảo mật MQTT** | TLS 8883, ACL vai trò và chữ ký HMAC đã được kiểm thử đạt trong test cô lập `test_mqtt_security.py`. Ở phiên chạy demo thường, hệ thống chạy **Plaintext không mã hóa** để thuận tiện kết nối. | `tests/integration/test_mqtt_security.py` | **TEST VERIFIED** |
| **Cơ sở dữ liệu** | Runtime chạy hoàn toàn trên **SQLite (`data/smartcart.db`)** với 4.596 bản ghi telemetry, 31 lệnh, 7 phiên mua hàng. **PostgreSQL chưa chạy thực tế** do Docker daemon không hoạt động. | `evidence/chapter_4/04_database/sqlite_database_dump.json` | **VERIFIED** (SQLite)<br>**NOT VERIFIED** (Postgres) |
| **Backend & Realtime** | FastAPI + WebSocket `/ws` (port 8000), xử lý trơn tru cả 6 topic MQTT và đẩy sự kiện xuống web. | `evidence/chapter_4/03_backend/backend_state_dump.json` | **VERIFIED** |
| **Mô hình Siêu thị 3D** | Mô hình Three.js tương tác đồng bộ dữ liệu nghiệp vụ thời gian thực qua WebSocket. Tọa độ di chuyển là **waypoint mô phỏng**, không phải định vị cảm biến phần cứng. | `evidence/chapter_4/screenshots/supermarket_3d_cart_moving.png` | **VERIFIED** (IoT Data)<br>**SIMULATED** (Vị trí) |
| **Kiểm thử tự động** | Tổng cộng **158 tests**: **142 PASSED (100% test thực thi)**, **16 SKIPPED** (do thiếu `g++` trên Windows), **0 FAILED**. | `evidence/chapter_4/07_tests/test_breakdown_dump.json` | **VERIFIED** |

---

## 2. LUỒNG TRUYỀN THÔNG IOT THỰC TẾ ĐÃ XÁC MINH

Luồng truyền thông chạy thực nghiệm trong hệ thống:

```
[Python SmartCart Simulator] 
         │ (MQTT 3.1.1 JSON via port 1883)
         ▼
  [tools/dev_broker.py]
         │ (Subscribe smartcart/+/#)
         ▼
  [FastAPI Backend Listener]
         │ (Ingest & Alert Engine)
         ├──► [SQLite: data/smartcart.db] (Lưu telemetry, giỏ hàng, phiên, lệnh)
         │
         ▼ (WebSocket /ws on port 8000)
  [Customer UI & Admin Dashboard (React + Three.js 3D Digital Twin)]
```

### Bảng minh chứng xuyên suốt theo `cart_id = CART_001`

| Bước truyền thông | Thành phần | Topic / Endpoint | Dữ liệu kiểm chứng thực tế | File bằng chứng |
|:---:|---|---|---|---|
| **1. Heartbeat** | Simulator → Broker → Backend | `smartcart/CART_001/heartbeat` | `{"uptime_s": 2033, "cart_status": "AVAILABLE"}` | `02_mqtt/mqtt_topic_samples.json` |
| **2. Bắt đầu phiên** | Admin/Web → Backend → Cart | `POST /api/sessions` & `smartcart/CART_001/command` | Backend sinh `session_id = 7`, gửi lệnh `START_SESSION`, xe chuyển `IN_USE` | `04_database/sqlite_database_dump.json` |
| **3. Quét sản phẩm** | Simulator → Broker → Backend | `smartcart/CART_001/scan` | Quét mã `8934588012341` (Coca-Cola 330ml), giỏ hàng ghi nhận 12.000đ, 355g | `01_simulator/simulator_state_dump.json` |
| **4. Báo cáo đo lường** | Simulator → Broker → Backend | `smartcart/CART_001/telemetry` | `{"actual_weight": 355.0, "battery_percent": 80.5}` | `04_database/sqlite_database_dump.json` (ID: 4605) |
| **5. Cảnh báo lệch cân** | Simulator → Backend → Web | Telemetry `actual_weight = 655g` (+300g) | Backend so sánh `|655 - 355| = 300g > 100g`, kích hoạt `WEIGHT_MISMATCH` | `08_demo_scenarios/` (Step 7) |
| **6. Đóng phiên mua** | Web → Backend → Simulator | `POST /api/sessions/7/checkout` & `END_SESSION` | Phiên #7 chuyển `COMPLETED`, xe nhận `END_SESSION` quay về `AVAILABLE` | `04_database/sqlite_database_dump.json` |

---

## 3. DANH MỤC TỆP MINH CHỨNG TRONG THƯ MỤC NÀY

- [01_simulator/simulator_state_dump.json](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/evidence/chapter_4/01_simulator/simulator_state_dump.json): Dump dữ liệu JSON trực tiếp từ Control API cổng 8090 của 3 xe.
- [02_mqtt/mqtt_topic_samples.json](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/evidence/chapter_4/02_mqtt/mqtt_topic_samples.json): Cấu trúc envelope chuẩn hoá của 6 topic MQTT.
- [03_backend/backend_state_dump.json](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/evidence/chapter_4/03_backend/backend_state_dump.json): Endpoint `/api/health` và `/api/carts`.
- [04_database/sqlite_database_dump.json](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/evidence/chapter_4/04_database/sqlite_database_dump.json): Thống kê số dòng các bảng trong CSDL SQLite thực tế.
- [06_esp32_wokwi/platformio_build_evidence.json](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/evidence/chapter_4/06_esp32_wokwi/platformio_build_evidence.json): Kết quả biên dịch PlatformIO 3 môi trường firmware ESP32.
- [07_tests/test_breakdown_dump.json](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/evidence/chapter_4/07_tests/test_breakdown_dump.json): Bảng phân loại 158 bài test (142 pass, 16 skipped).
- [SCREENSHOT_CHECKLIST.md](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/evidence/chapter_4/SCREENSHOT_CHECKLIST.md): Danh mục hình ảnh đánh số phục vụ chèn vào Word.
- [DEMO_SCENARIO_EVIDENCE.md](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/evidence/chapter_4/DEMO_SCENARIO_EVIDENCE.md): Bằng chứng chi tiết 10 bước demo thực tế.
- [EVIDENCE_GAPS.md](file:///d:/Filehoc/IOT/smart-shopping-cart/smart-shopping-cart/evidence/chapter_4/EVIDENCE_GAPS.md): Các hạng mục mô phỏng hoặc chưa xác minh runtime.
