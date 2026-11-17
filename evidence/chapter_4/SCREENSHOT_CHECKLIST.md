# DANH MỤC ẢNH CHỤP THỰC NGHIỆM CHO CHƯƠNG 4 (SCREENSHOT CHECKLIST)
## Báo cáo đề tài: Hệ thống Xe Đẩy Hàng Thông Minh Ứng Dụng IoT

> **Thư mục lưu trữ ảnh gốc:** `evidence/chapter_4/screenshots/`  
> **Nguyên tắc:** Toàn bộ ảnh được chụp từ hệ thống chạy thực tế bằng công cụ Playwright Chromium hoặc giao diện thực tế. Không sử dụng ảnh mockup hoặc hình minh họa vẽ tay làm bằng chứng thực nghiệm.

---

### BẢNG TRA CỨU HÌNH ẢNH CHƯƠNG 4

| Mã hình | Tên hình ảnh | Nội dung cần chứng minh | Tên file ảnh tương ứng | Trạng thái | Chú thích đề xuất đưa vào Word |
|:---:|---|---|---|:---:|---|
| **Hình 4.1** | Giao diện đăng nhập quản trị hệ thống | Cơ chế xác thực người dùng dựa trên JWT Token và phân quyền (RBAC) | `login.png` | **VERIFIED** | *Hình 4.1: Màn hình đăng nhập quản trị viên với cơ chế bảo mật xác thực phiên làm việc.* |
| **Hình 4.2** | Tổng quan Dashboard quản trị thời gian thực | Giám sát trạng thái 3 xe đẩy, thống kê Online/Offline, cảnh báo và bản đồ siêu thị | `08_admin_tong_quan.png` | **VERIFIED** | *Hình 4.2: Bảng điều khiển trung tâm hiển thị chỉ số hạm đội xe và trạng thái hệ thống theo thời gian thực.* |
| **Hình 4.3** | Mô hình Siêu thị 3D Interactive Digital Twin | Không gian siêu thị 3D isometric dựng bằng Three.js hiển thị vị trí các xe tại bãi xe | `supermarket_3d_overview.png` | **VERIFIED** | *Hình 4.3: Không gian siêu thị 3D Digital Twin với các dãy kệ hàng, quầy thu ngân và khu vực xe đẩy.* |
| **Hình 4.4** | Xe đẩy di chuyển trong siêu thị 3D | Hoạt ảnh xe di chuyển mượt mà theo các điểm nút (waypoint) giữa các lối đi | `supermarket_3d_cart_moving.png` | **VERIFIED** | *Hình 4.4: Mô hình xe đẩy di chuyển trên lối đi siêu thị 3D không xuyên qua kệ hàng và hiển thị hào quang nhận diện.* |
| **Hình 4.5** | Góc nhìn trực giao từ trên xuống (Top-down) | Khả năng quan sát toàn diện sơ đồ mặt bằng siêu thị 3D từ góc nhìn 90 độ | `supermarket_3d_topdown.png` | **VERIFIED** | *Hình 4.5: Góc quan sát từ trên cao (Top-down view) hỗ trợ quản lý sơ đồ phân bổ vị trí các xe.* |
| **Hình 4.6** | Màn hình khách hàng lựa chọn xe đẩy | Khách hàng chọn xe khả dụng (`AVAILABLE` & `ONLINE`), chặn chọn xe bị khóa hoặc offline | `01_customer_chon_xe.png` | **VERIFIED** | *Hình 4.6: Màn hình khách hàng bắt đầu phiên mua sắm bằng cách chọn xe đẩy sẵn sàng.* |
| **Hình 4.7** | Màn hình giỏ hàng và quét sản phẩm | Cập nhật tự động số lượng, đơn giá, tổng tiền VND và tải trọng khi quét mã vạch | `02_customer_gio_hang.png` | **VERIFIED** | *Hình 4.7: Giao diện giỏ hàng của khách hàng cập nhật tức thì danh sách sản phẩm và tổng tiền thanh toán.* |
| **Hình 4.8** | Cảnh báo sai lệch trọng lượng trên màn hình khách | Phát hiện bất thường khi trọng lượng thực tế không khớp với tổng trọng lượng lý thuyết | `03_customer_canh_bao_lech_can.png` | **VERIFIED** | *Hình 4.8: Cảnh báo lệch cân (Weight Mismatch) hiển thị trên màn hình khách hàng và tạm dừng thanh toán.* |
| **Hình 4.9** | Cảnh báo lệch cân trên Dashboard quản trị | Nhân viên quản lý nhận cảnh báo đỏ tức thì qua WebSocket kèm mã xe và chi tiết lỗi | `09_admin_canh_bao.png` | **VERIFIED** | *Hình 4.9: Cảnh báo thời gian thực gửi về Dashboard trung tâm khi có hành vi gian lận hoặc sai sót hàng hóa.* |
| **Hình 4.10** | Lệnh khóa xe từ xa qua MQTT | Quản trị viên kích hoạt khóa xe (`LOCK_CART`), xe phản hồi ACK và bị vô hiệu hóa quét mã | `07_customer_xe_bi_khoa.png` | **VERIFIED** | *Hình 4.10: Trạng thái xe đẩy bị khóa từ xa từ trung tâm điều hành khi phát hiện sự cố an ninh.* |
| **Hình 4.11** | Xác nhận thanh toán và mã QR | Khách hàng thực hiện thanh toán tự phục vụ với mã QR hóa đơn | `04_customer_xac_nhan_thanh_toan.png` | **VERIFIED** | *Hình 4.11: Bước đối soát cuối cùng và hiển thị mã QR thanh toán trước khi đóng phiên mua sắm.* |
| **Hình 4.12** | Hoàn tất phiên mua sắm | Phiên mua chuyển sang `COMPLETED`, xe đẩy nhận lệnh `END_SESSION` tự động về trạng thái sẵn sàng | `05_customer_hoan_tat.png` | **VERIFIED** | *Hình 4.12: Thông báo hoàn tất mua hàng, hệ thống giải phóng xe đẩy về trạng thái sẵn sàng đón khách mới.* |
| **Hình 4.13** | Trang quản trị chi tiết thiết bị và biểu đồ | Đồ thị telemetry theo dõi dung lượng pin và trọng lượng lịch sử của xe đẩy | `11_admin_chi_tiet_xe.png` | **VERIFIED** | *Hình 4.13: Trang thông tin chi tiết xe đẩy với đồ thị lịch sử pin, cảm biến cân nặng và nhật ký lệnh điều khiển.* |
| **Hình 4.14** | Trình giả lập cảm biến phần cứng (Hardware Simulator) | Bảng điều khiển mô phỏng quét mã, thay đổi cân nặng, xả pin và ngắt kết nối mạng | `13_simulator_phan_cung.png` | **VERIFIED** | *Hình 4.14: Giao diện Python Hardware Simulator hỗ trợ thử nghiệm các tình huống cảm biến và mạng.* |
| **Hình 4.15** | Phát hiện mất kết nối mạng (Offline Watchdog) | Backend phát hiện xe mất heartbeat quá 15 giây, tự động kích hoạt cảnh báo OFFLINE | `14_simulator_mat_mang.png` | **VERIFIED** | *Hình 4.15: Hệ thống tự động phát hiện thiết bị mất kết nối và hiển thị trạng thái ngoại tuyến.* |

---

### CÁC HÌNH ẢNH CẦN CHỤP THỦ CÔNG THÊM (NẾU NHÓM MUỐN BỔ SUNG)

1. **Ảnh mở mạch trên phần mềm mô phỏng Wokwi:**
   - *Cách chụp:* Mở VS Code có cài Wokwi extension hoặc truy cập `https://wokwi.com`, nạp file `diagram.json` và chụp màn hình cửa sổ mô phỏng có vi điều khiển ESP32, màn hình OLED SSD1306 sáng đèn và cảm biến HX711.
   - *Mục đích:* Đưa vào Chương 2 hoặc Chương 4 để minh chứng sơ đồ mạch ảo hoạt động trực quan.
2. **Ảnh chụp mã nguồn PlatformIO biên dịch thành công:**
   - *Cách chụp:* Chụp màn hình terminal chạy lệnh `pio run -d firmware -e esp32dev_sim` xuất dòng chữ xanh `[SUCCESS] Took 4.05 seconds`.
