# REST API & WebSocket

Prefix `/api`. Swagger UI: `GET /api/docs` (cần Internet để tải giao diện Swagger từ CDN), đặc tả: `GET /api/openapi.json`
(sinh tự động từ danh sách route + pydantic nên luôn khớp code). Postman: `postman/` (sinh bằng `python -m tools.gen_postman`).

## Xác thực

Khi `AUTH_ENABLED=1` (mặc định) hầu hết endpoint cần `Authorization: Bearer <token>`. Quyền từng endpoint nằm trong OpenAPI (`security`) và bảng ở [SECURITY.md §3.1](../SECURITY.md#31-vai-trò-và-quyền-rest).

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/auth/config` | `{auth_required}` – giao diện dùng để biết có cần màn đăng nhập không |
| POST | `/api/auth/login` `{username, password}` | → `{token, token_type, expires_in, role, username}`; 401 `INVALID_CREDENTIALS`; 429 khi bị khoá tạm |
| GET | `/api/auth/me` | vai trò hiện tại |
| POST | `/api/auth/logout` | thu hồi token đang dùng |

`POST /api/sessions` trả thêm `token` + `token_expires_in`: token **của khách** chỉ dùng được cho phiên đó.
WebSocket: gửi `{"type":"AUTH","token":"…"}` sau khi mở kết nối (xem SECURITY.md §3.2).

## Lỗi

Mọi lỗi trả JSON `{ "error": { "code": "...", "message": "..." } }`.

| HTTP | Khi nào | Ví dụ `code` |
|---|---|---|
| 400 | tham số sai | `BAD_REQUEST`, `INVALID_JSON` |
| 401 | thiếu/sai/hết hạn token | `UNAUTHENTICATED`, `INVALID_CREDENTIALS` |
| 403 | đủ đăng nhập nhưng thiếu quyền | `FORBIDDEN` |
| 413 | body > 64 KB | `PAYLOAD_TOO_LARGE` |
| 429 | quá nhiều yêu cầu / đang bị khoá đăng nhập | `TOO_MANY_REQUESTS` (header `Retry-After`) |
| 404 | không thấy tài nguyên | `NOT_FOUND` |
| 409 | sai trạng thái nghiệp vụ | `CART_OFFLINE`, `CART_NOT_AVAILABLE`, `CART_LOCKED`, `SESSION_NOT_ACTIVE`, `EMPTY_SESSION`, `ALREADY_LOCKED`, `NOT_LOCKED` |
| 422 | body không hợp lệ | `VALIDATION_ERROR` |
| 504 | xe không ACK lệnh | `COMMAND_TIMEOUT` (kèm trường `command`) |

## Endpoint

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/health` | DB, MQTT, số client WS, `ws_port`, bộ đếm message lỗi (người chưa đăng nhập chỉ thấy `status`, `time`, `ws_port`) |
| GET | `/api/products?q=&all=1` | Danh sách / tìm sản phẩm đang bán. `all=1` gồm cả sản phẩm đã ẩn (chỉ staff; với người khác bị bỏ qua) |
| POST | `/api/products` | **Admin.** Thêm sản phẩm `{barcode (4–64 ký tự [0-9A-Za-z-]), name, price (≥0, VND), unit_weight (>0, gram), image?}` → 201; 409 `BARCODE_EXISTS`; 422 |
| PUT | `/api/products/{id}` | **Admin.** Sửa một phần `{barcode?, name?, price?, unit_weight?, image?, active?}`; `active=false` để ẩn (không xoá hẳn, giữ lịch sử giỏ hàng) |
| GET | `/api/products/{id}` · `/api/products/barcode/{barcode}` | Chi tiết |
| GET | `/api/carts` | Tất cả xe + cảnh báo đang bật + tóm tắt phiên |
| POST | `/api/carts` `{cart_id, name?}` | Đăng ký xe mới (vd. xe phần cứng). 201; 409 `CART_EXISTS`; `cart_id` theo `^[A-Za-z0-9_-]{1,32}$`. Backend **bỏ qua** message từ xe chưa đăng ký |
| GET | `/api/carts/{cart_id}` | Một xe |
| GET | `/api/carts/{cart_id}/telemetry?limit=` | Lịch sử (cũ → mới), mặc định 100, tối đa 1000 |
| GET | `/api/carts/{cart_id}/session` | Phiên ACTIVE của xe (404 nếu không có) |
| POST | `/api/carts/{cart_id}/lock` · `/unlock` | Gửi `LOCK_CART`/`UNLOCK_CART`, **chờ ACK** (≤ 5 s). 200 nếu OK |
| POST | `/api/sessions` `{cart_id}` | Bắt đầu phiên → 201. Yêu cầu xe `AVAILABLE` và `ONLINE` |
| GET | `/api/sessions/{id}` | Giỏ hàng, tổng tiền, cân dự kiến/thực tế |
| POST | `/api/sessions/{id}/items` `{barcode\|product_id, quantity}` | Thêm thủ công → 201 |
| DELETE | `/api/sessions/{id}/items/{item_id}` | Xoá một dòng hàng |
| POST | `/api/sessions/{id}/checkout` | Thanh toán (giao dịch nguyên tử) → phiên `COMPLETED`, xe `AVAILABLE`, gửi `END_SESSION` |
| POST | `/api/sessions/{id}/cancel` | Huỷ phiên *(mở rộng)* |
| GET | `/api/alerts?status=&cart_id=` | Cảnh báo, mới nhất trước |
| GET | `/api/commands/{command_id}` | Trạng thái lệnh (`PENDING/OK/FAILED/TIMEOUT`); lưu trong bộ nhớ, mất khi restart |

Quy tắc đáng chú ý: không `checkout` khi giỏ trống hoặc xe `LOCKED`; `checkout` ghi cảnh báo chưa xử lý vào `note` của phiên rồi đóng cảnh báo `WEIGHT_MISMATCH`;
giá trong `cart_items.unit_price` là **ảnh chụp giá lúc thêm** nên đổi giá sau đó không ảnh hưởng hoá đơn.

## WebSocket (`ws://HOST:8081/ws`, một chiều server → client)

Cổng thực tế lấy từ `GET /api/health → ws_port`. Mỗi message là JSON `{ "type", "timestamp", ... }`:

| `type` | Trường thêm | Khi nào |
|---|---|---|
| `CONNECTED` | — | vừa kết nối (client nên nạp lại dữ liệu qua REST) |
| `CART_UPDATED` | `cart_id`, `cart` | bất kỳ thay đổi trạng thái/telemetry/giỏ của xe |
| `ALERT_TRIGGERED` | `cart_id`, `alert` | cảnh báo mới |
| `ALERT_RESOLVED` | `cart_id`, `alert` | cảnh báo được đóng |
| `COMMAND_ACK` | `cart_id`, `command` | xe phản hồi lệnh |
| `SCAN_REJECTED` | `cart_id`, `barcode`, `reason`, `message` | quét bị từ chối |
| `CART_EVENT` | `cart_id`, `event` | event xe gửi lên |

Frontend tự reconnect (backoff ≤ 8 s), nạp lại REST khi nối lại và poll 5 s khi WS không mở.

## Chuyển sang FastAPI

Handler nằm trong `backend/api/routes.py` (đồng bộ, nhận `request` + `body` pydantic), service không phụ thuộc framework.
Chuyển sang FastAPI chủ yếu là: khai báo lại route bằng `@router.get/post`, thay `registry` bằng `response_model`, và thay `ws_server.py` bằng `@app.websocket("/ws")` (giữ nguyên định dạng sự kiện).
