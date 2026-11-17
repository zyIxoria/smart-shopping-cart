# Kiến trúc

```
 ┌───────────────┐   MQTT   ┌────────────┐   MQTT   ┌─────────────────────────────┐
 │ Simulator     │─────────▶│  Mosquitto │─────────▶│ Backend (Starlette)         │
 │ 3 xe giả lập  │◀─────────│  (broker)  │◀─────────│  MQTT consumer/publisher    │
 │ (hoặc ESP32)  │ command  └────────────┘  command │  Rule engine (3 cảnh báo)   │
 └───────────────┘                                  │  Heartbeat monitor          │
                                                    │  REST /api  ·  WS :8081     │
                                                    └──────┬───────────────┬──────┘
                                                           │ SQL           │ HTTP + WebSocket
                                                      ┌────▼────┐   ┌──────▼──────────────────┐
                                                      │ SQLite  │   │ React: Customer + Admin │
                                                      └─────────┘   └─────────────────────────┘
```

## Thành phần

| Thư mục | Vai trò |
|---|---|
| `shared/` | `contract.py` (topic, enum, envelope, validate) + `mqttlite.py` (MQTT client) – dùng chung Backend/Simulator |
| `backend/` | `api/` (routes, openapi, app) · `services/` (carts, sessions, alerts, commands, ingest) · `alerts/rules.py` (hàm thuần) · `mqtt/` (gateway, monitor) · `realtime/` (hub, ws_server) · `database/` |
| `simulator/` | `cart/` (SmartCart) · `mqtt/` · `scenarios/` · `cli/` · `control.py` (API HTTP :8090 cho trang `/simulator`) · `main.py` |
| `frontend/` | `src/customer`, `src/admin`, `src/common`, `src/api` (client + mock + socket), `src/state` |
| `tools/` | `dev_broker.py` (broker thử nghiệm có user/ACL/TLS), `provision.py` (sinh bí mật), `gen_postman.py` |
| `backend/auth.py`, `shared/security.py` | Đăng nhập, token, vai trò, khoá đăng nhập; PBKDF2, HMAC ký message, dẫn xuất khoá từng xe |

## Luồng chính

**Mua hàng.** Khách chọn xe `AVAILABLE`+`ONLINE` → `POST /sessions` → Backend lưu phiên, xe → `IN_USE`, gửi `START_SESSION` → xe quét `scan` → Backend tra sản phẩm, cập nhật `cart_items` → `CART_UPDATED` qua WebSocket → UI cập nhật tức thì → `checkout` (giao dịch) → xe → `AVAILABLE`, gửi `END_SESSION`.

**Cảnh báo.** Mỗi `telemetry` hợp lệ lưu vào DB rồi chạy rule engine: pin < 20 % → `LOW_BATTERY`; trong phiên, \|cân thực tế − dự kiến\| > 100 g → `WEIGHT_MISMATCH`; điều kiện hết → tự đóng. Thread `HeartbeatMonitor` (2 s/lần) đặt xe `OFFLINE` khi > 15 s không có tin và tạo cảnh báo `OFFLINE`. Cảnh báo ACTIVE cùng loại không bao giờ trùng (unique index + kiểm tra trong giao dịch).

**Khoá xe.** Admin → `POST /carts/{id}/lock` → Backend gửi `LOCK_CART` (QoS 0) và **chờ ACK** → chỉ khi ACK `OK` mới đặt `LOCKED` (xe offline → 409; không ACK → 504).

**Mất/nối lại kết nối.** Xe tự reconnect + subscribe lại; Backend phát hiện `OFFLINE → ONLINE`, đóng cảnh báo và gửi lại trạng thái đúng để xe đồng bộ (idempotent).

## Đa luồng

Endpoint đồng bộ chạy trong threadpool của Starlette; consumer MQTT chạy thread riêng (xử lý tuần tự nên scan luôn đến trước telemetry gửi sau nó); monitor thread riêng; WebSocket chạy trên event loop của app. `Hub.publish` an toàn đa luồng (`call_soon_threadsafe`). Một connection SQLite + `RLock` tuần tự hoá truy cập DB.

## Lựa chọn thiết kế cần biết

- **Backend là nguồn sự thật** về `cart_status`; telemetry của xe chỉ để ghi lịch sử.
- Quét khi xe `LOCKED`/không có phiên/mã lạ bị **từ chối kèm sự kiện `SCAN_REJECTED`** thay vì im lặng.
- `WEIGHT_MISMATCH` chỉ xét khi xe đang `IN_USE` có phiên – tránh báo động giả khi xe rảnh.
- **Lớp bảo mật** (xem [SECURITY.md](SECURITY.md)): mọi request REST qua `AuthService` (`auth=` khai báo ngay cạnh route, mặc định đóng); WebSocket lọc sự kiện theo quyền (`hub.project`); MQTT đi qua broker có user/ACL/TLS và mỗi message mang `sig` HMAC, Backend kiểm chữ ký **trước** khi giải mã/chống trùng/ghi DB, lệnh xuống xe cũng được Backend ký.
- CORS mặc định `*` (xác thực bằng Bearer token, không dùng cookie) – nên siết trước khi triển khai thật. HTTP/WS của Backend chưa có TLS.
