# MQTT Contract – Smart Shopping Cart

Contract duy nhất giữa **Simulator/ESP32 ↔ Broker ↔ Backend**. Mã tham chiếu: `shared/contract.py`
(dùng chung cho Backend và Simulator; ESP32 cần cài đặt lại đúng theo tài liệu này).

## 1. Topic

| Topic | Hướng | Mục đích | Tần suất |
|---|---|---|---|
| `smartcart/{cart_id}/scan` | Xe → Backend | Quét mã vạch (thêm/bớt hàng) | khi có sự kiện |
| `smartcart/{cart_id}/event` | Xe → Backend | Sự kiện rời rạc (mã lạ, khoá/mở khoá…) | khi có sự kiện |
| `smartcart/{cart_id}/telemetry` | Xe → Backend | Pin, cân nặng, trạng thái | 10 s (+ ngay sau mỗi lần quét/lệnh) |
| `smartcart/{cart_id}/heartbeat` | Xe → Backend | Báo còn sống | 5 s (+ ngay khi kết nối lại) |
| `smartcart/{cart_id}/command` | Backend → Xe | Lệnh điều khiển | khi cần |
| `smartcart/{cart_id}/ack` | Xe → Backend | Phản hồi lệnh | sau mỗi lệnh |

> **Gốc topic tuỳ chọn:** `smartcart` là mặc định. Khi dùng broker công cộng (vd. mô phỏng Wokwi), đặt biến môi trường `MQTT_TOPIC_ROOT` (Backend, Simulator) và `MQTT_TOPIC_ROOT` trong firmware (`firmware/include/wokwi_online.h`) cùng một giá trị riêng, ví dụ `smartcart-abc123` → topic thành `smartcart-abc123/{cart_id}/scan`. Phần envelope/payload không đổi. Đồng thời đặt `MQTT_CLIENT_ID` duy nhất cho Backend.

`cart_id` khớp `^[A-Za-z0-9_-]{1,32}$` (ví dụ `CART_001`). **QoS 0** cho mọi topic.
Backend subscribe `smartcart/+/{scan|event|telemetry|heartbeat|ack}`; mỗi xe subscribe `smartcart/{cart_id}/command`.

## 2. Envelope (mọi message)

```json
{
  "message_id": "6f1c2a9e-0f4e-4a43-9b6f-1d6f2a7c8e10",
  "cart_id": "CART_001",
  "schema_version": 1,
  "timestamp": "2026-11-07T10:30:00Z",
  "data": { }
}
```

- `message_id`: chuỗi duy nhất (UUID) → Backend loại message trùng (LRU 2000 id).
- `cart_id`: **phải khớp** `cart_id` trong topic, nếu không message bị loại.
- `schema_version`: hiện là `1`; khác 1 bị loại.
- `timestamp`: ISO 8601 UTC. Lệch giờ Backend > 300 s (`MAX_CLOCK_SKEW_S`) bị loại (đặt 0 để tắt).
  ESP32 không có NTP cần đồng bộ giờ trước khi gửi.
- `data`: object, tuỳ topic.

## 3. Payload `data`

### scan
```json
{ "scan_id": "uuid", "barcode": "8934588012341", "action": "ADD" }
```
`action`: `ADD` (mặc định nếu thiếu) | `REMOVE`. `scan_id` (tuỳ chọn) dùng chống quét lặp: cùng `scan_id` chỉ tính một lần.
Backend từ chối (phát `SCAN_REJECTED` tới UI, không đổi giỏ) khi: xe `LOCKED`, xe chưa có phiên ACTIVE, mã vạch không có trong CSDL, `REMOVE` món không có trong giỏ.

### telemetry
```json
{ "actual_weight": 847.0, "battery_percent": 82.5, "cart_status": "IN_USE",
  "wifi_status": "CONNECTED", "mqtt_status": "CONNECTED" }
```
- `actual_weight`: **gram**, số, 0…1 000 000. `battery_percent`: 0…100.
- `cart_status` (tuỳ chọn): `AVAILABLE|IN_USE|LOCKED`, chỉ để ghi lịch sử – **Backend là nguồn sự thật** về trạng thái xe.
- `wifi_status`, `mqtt_status`: thông tin phụ.

### heartbeat
```json
{ "uptime_s": 1234, "cart_status": "AVAILABLE" }
```

### event
```json
{ "event_type": "UNKNOWN_BARCODE", "description": "Mã vạch không có trong danh mục: 000" }
```
Hiện Simulator gửi: `UNKNOWN_BARCODE`, `CART_LOCKED`, `CART_UNLOCKED`. Backend chuyển tiếp tới UI (`CART_EVENT`).

### command (Backend → Xe)
```json
{ "command_id": "uuid", "command_type": "LOCK_CART", "parameters": {} }
```
| `command_type` | Ý nghĩa | `parameters` |
|---|---|---|
| `LOCK_CART` | Khoá xe: bỏ qua mọi lần quét | — |
| `UNLOCK_CART` | Mở khoá | — |
| `START_SESSION` *(mở rộng)* | Bắt đầu phiên | `{ "session_id": int }` |
| `END_SESSION` *(mở rộng)* | Kết thúc phiên, xe về trạng thái rảnh | `{ "session_id": int\|null }` |

`START_SESSION`/`END_SESSION` không có trong đề cương gốc; thêm để xe biết khi nào được nhận quét và khi nào giỏ vật lý được coi là trống.
Xe phải **idempotent**: cùng `session_id` đang chạy → không xoá giỏ; cùng `command_id` nhận lại → gửi lại ACK cũ, không thực thi lại.

### ack (Xe → Backend)
```json
{ "command_id": "uuid", "result": "OK", "message": "Đã khoá xe" }
```
`result`: `OK` | `FAILED`. Backend chỉ đổi trạng thái `LOCKED` **sau khi nhận ACK `OK`**. Không có ACK trong 5 s → API trả `504 COMMAND_TIMEOUT`.

## 4. Quy ước giá trị

| Trường | Giá trị |
|---|---|
| `cart_status` | `AVAILABLE` · `IN_USE` · `LOCKED` |
| `connection_status` (Backend suy ra) | `ONLINE` · `OFFLINE` |
| Cảnh báo | `LOW_BATTERY` (pin < 20 %) · `WEIGHT_MISMATCH` (\|thực tế − dự kiến\| > 100 g) · `OFFLINE` (> 15 s không có tin) |
| Đơn vị | cân nặng **gram**; tiền **VND** (số nguyên) |

`dự kiến = Σ quantity × unit_weight` của phiên đang ACTIVE. Cân chỉ được đối chiếu khi xe `IN_USE` có phiên ACTIVE.
### Chữ ký `sig` (tuỳ chọn, bật bằng `DEVICE_MASTER_KEY`)

Khi bật ký, envelope có thêm trường `sig` **ngay trước `data`**:

```json
{"message_id":"…","cart_id":"CART_001","schema_version":1,"timestamp":"2026-11-07T10:30:00Z","sig":"<64 hex>","data":{…}}
```

`sig = HMAC-SHA256(cart_key, message_id "\n" cart_id "\n" timestamp "\n" kind "\n" data_raw)` với `kind` là tên topic và `data_raw` là nguyên văn chuỗi JSON của `data`.
Áp dụng cho **cả hai chiều** (xe → Backend và `command` Backend → xe). Chi tiết, khoá riêng từng xe và chế độ chuyển đổi: [docs/SECURITY.md](../SECURITY.md#34-ký-message-hmac-sha256).
Backend loại gói thiếu/sai chữ ký (đếm ở `stats.mqtt_unsigned` / `stats.mqtt_bad_signature`).

Backend coi bất kỳ message hợp lệ nào (heartbeat, telemetry, scan…) là bằng chứng xe còn sống.

## 5. Hành vi khi kết nối lại

1. Client tự reconnect (backoff 0,5 → 8 s) và **subscribe lại** `command`.
2. Ngay sau khi nối lại, xe gửi **heartbeat + telemetry** mới.
3. Backend thấy xe chuyển `OFFLINE → ONLINE` → đóng cảnh báo `OFFLINE` và **gửi lại trạng thái đúng** (`LOCK_CART` / `START_SESSION` / `END_SESSION`) để xe đồng bộ.
4. Message QoS 0 gửi trong lúc offline **bị mất** (xe ghi nhận cục bộ nhưng Backend không biết) – giới hạn đã biết của QoS 0.

## 6. Xử lý message lỗi (Backend)

Message không phải JSON, sai envelope/`data`, lệch `cart_id`, quá cũ, hoặc trùng `message_id` được **ghi log + đếm** (`/api/health → stats`) và bỏ qua – không bao giờ làm dừng consumer. Message từ `cart_id` chưa đăng ký bị bỏ qua.
