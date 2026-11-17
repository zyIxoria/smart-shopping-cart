# BẰNG CHỨNG KỊCH BẢN THỰC NGHIỆM 10 BƯỚC (DEMO SCENARIO EVIDENCE)
## Báo cáo đề tài: Hệ thống Xe Đẩy Hàng Thông Minh Ứng Dụng IoT

> **Phương thức thực nghiệm:** Chạy trực tiếp trên ngăn xếp dịch vụ thật (Local Stack): `tools/dev_broker.py` (Port 1883), `backend.main` (Port 8000), `simulator.main` (Port 8090).  
> **Xe thực nghiệm:** `CART_001`  
> **Thời điểm xác minh:** 17/11/2026 20:09:30 (GMT+7)

---

### BẢNG ĐỐI CHIẾU 10 BƯỚC KỊCH BẢN DEMO THỰC TẾ

| Bước | Thao tác thực hiện | Kết quả mong đợi | Kết quả thực tế quan sát được | Bằng chứng kỹ thuật kiểm chứng |
|:---:|---|---|---|---|
| **1** | Khởi động hệ thống & kiểm tra sức khỏe | Backend và Broker phản hồi sẵn sàng | HTTP 200: `{"status": "ok", "ws_port": 8000}` | `GET http://127.0.0.1:8000/api/health` |
| **2** | Đăng nhập tài khoản Quản trị | Cấp phát JWT token với quyền `admin` | Đăng nhập thành công, nhận Bearer token hợp lệ | `POST /api/auth/login` -> HTTP 200, role: `admin` |
| **3** | Kiểm tra danh sách xe trong hạm đội | Hiển thị đúng 3 xe đẩy hoạt động | Đủ 3 xe: `CART_001`, `CART_002`, `CART_003` ở trạng thái `ONLINE` | `GET /api/carts` -> Trả về 3 xe, 0 cảnh báo rác |
| **4** | Bắt đầu phiên mua sắm cho `CART_001` | Tạo bản ghi phiên mua hàng, gửi lệnh `START_SESSION` | Sinh `session_id = 7`, xe `CART_001` chuyển sang trạng thái `IN_USE` | `POST /api/sessions` -> HTTP 201; CSDL ghi nhận Session #7 |
| **5** | Quét mã vạch sản phẩm Coca-Cola | Trình giả lập gửi bản tin `scan` qua MQTT topic | Gửi lệnh quét mã `8934588012341`, API phản hồi `result: "sent"` | `POST http://127.0.0.1:8090/sim/carts/CART_001/scan` |
| **6** | Cập nhật giỏ hàng và đối soát trọng lượng | Backend ghi nhận sản phẩm và cập nhật tổng tiền | Giỏ hàng có **1 món**, tổng tiền: **12.000 đ**, trọng lượng dự kiến: **355.0 g** | `GET /api/sessions/7` -> Danh sách 1 item, khớp CSDL SQLite |
| **7** | Kích hoạt tình huống lệch cân (+300g) | Trình giả lập tăng offset tải trọng thêm 300g (thực tế 655g vs dự kiến 355g) | Sau 1.5 giây, hệ thống kích hoạt cảnh báo `WEIGHT_MISMATCH` | `POST /sim/carts/CART_001/weight_offset` (`grams: 300`); `GET /api/alerts?status=ACTIVE` trả về 1 cảnh báo |
| **8** | Khắc phục tình huống lệch cân | Bỏ vật lạ ra khỏi giỏ, trọng lượng thực tế trở về 355g | Cảnh báo tự động chuyển sang `RESOLVED`, danh sách cảnh báo rỗng | `POST /sim/carts/CART_001/weight_offset` (`grams: 0`); `GET /api/alerts?status=ACTIVE` -> `[]` |
| **9** | Thực hiện thanh toán (Checkout) | Đóng phiên mua hàng, ghi nhận tổng thanh toán | Phiên mua #7 chuyển `status: "COMPLETED"`, tổng thu: **12.000 đ** | `POST /api/sessions/7/checkout` -> HTTP 200 |
| **10** | Đưa xe trở về trạng thái sẵn sàng | Xe nhận lệnh `END_SESSION`, giỏ hàng làm sạch, về bãi xe | `CART_001` có `cart_status: "AVAILABLE"`, `session: null`, sẵn sàng cho phiên mới | `GET /api/carts/CART_001` -> Trạng thái sẵn sàng đón khách |

---

### BẰNG CHỨNG XUYÊN SUỐT CỦA PHIÊN #7 TRONG CƠ SỞ DỮ LIỆU SQLITE

1. **Bản ghi trong bảng `shopping_sessions`:**
   ```json
   {
     "id": 7,
     "cart_id": "CART_001",
     "status": "COMPLETED",
     "started_at": "2026-11-17T13:09:28Z",
     "ended_at": "2026-11-17T13:09:32Z",
     "total_amount": 12000,
     "note": ""
   }
   ```
2. **Bản ghi trong bảng `cart_items`:**
   Sản phẩm ID 1 (`Coca-Cola 330ml`), đơn giá 12.000 đ, số lượng 1, trọng lượng đơn vị 355g.
3. **Bản ghi trong bảng `alerts`:**
   Cảnh báo `WEIGHT_MISMATCH` được ghi nhận với trạng thái `RESOLVED` sau khi trọng lượng cân trở về mức cho phép.
