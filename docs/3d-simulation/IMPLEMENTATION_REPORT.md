# BÁO CÁO NÂNG CẤP: SIÊU THỊ 3D INTERACTIVE DIGITAL TWIN

## 1. Tổng quan & Mục tiêu

Tính năng mô phỏng siêu thị đã được nâng cấp toàn diện từ mô hình 2D phẳng thành **Mô hình Siêu thị 3D Interactive Digital Twin** hiện đại, trực quan, hỗ trợ trình diễn thời gian thực trước hội đồng và giảng viên.

Hệ thống cho phép:
- Quan sát không gian siêu thị 3D nhìn từ góc camera **Isometric** hoặc **Top-Down**.
- Theo dõi các xe đẩy thông minh 3D di chuyển mượt mà giữa các hành lang mà không đâm xuyên kệ hàng.
- Click chuột trực tiếp vào xe trên không gian 3D (Raycasting) hoặc chọn xe từ thanh HUD để xem trạng thái chi tiết.
- Đồng bộ dữ liệu IoT 2 chiều theo thời gian thực (Cart ID, Online/Offline, Pin, Trọng lượng thực/dự kiến, Giỏ hàng, Tổng tiền, Cảnh báo) từ Python Simulator & Backend qua MQTT và WebSocket.
- Chuyển đổi linh hoạt giữa chế độ **[ 🎮 3D Digital Twin ]** và **[ 🗺️ 2D Mặt bằng ]**.

---

## 2. Công nghệ sử dụng

- **Three.js r187**: Thư viện dựng hình 3D WebGL chính, tích hợp trực tiếp vào bundle ứng dụng bằng esbuild (không phụ thuộc CDN bên ngoài, chạy 100% offline).
- **OrbitControls**: Điều khiển camera mượt mà với damping (xoay, kéo pan, cuộn thu phóng, giới hạn góc không bị chìm xuống sàn).
- **Procedural Low-Poly 3D Modeling**: Dựng hình học không gian siêu thị, 8 dãy kệ hàng gondola, sản phẩm sắc màu, quầy thu ngân và xe đẩy thông minh bằng các khối hình học cơ bản (Box, Cylinder, Ring, Plane) kết hợp vật liệu chuẩn PBR (`MeshStandardMaterial`), giúp giảm tối đa dung lượng và duy trì tốc độ 60 FPS ổn định trên mọi laptop.
- **HTML5 Dynamic CanvasTexture**: Tạo nhãn nổi 3D (Floating Badges), biển phân vùng tiếng Việt có dấu với độ sắc nét cao.

---

## 3. Kiến trúc Không gian Siêu thị 3D

Bản đồ siêu thị 3D được chuẩn hoá tỷ lệ từ hệ tọa độ chuẩn (1000x620) sang không gian 3D (100x62 units) lấy tâm `(0, 0, 0)` làm gốc:

1. **Mặt sàn & Viền không gian**:
   - Mặt sàn gạch bóng màu sẫm (`#0f172a`) với lưới gạch định vị (`GridHelper`).
   - Tường bảo vệ kính mica thấp (`height = 1.8 units`) bao quanh 4 phía theo phong cách Isometric Cutaway (không che khuất tầm nhìn).
2. **7 Phân vùng siêu thị (Zones)**:
   - **Lối vào & Bãi xe (Entrance / Cart Bay)**: Đệm sàn xanh ngọc `#059669`.
   - **Thực phẩm khô (Grocery)**: Đệm sàn xanh lá `#10b981`.
   - **Đồ uống & Sữa (Beverage)**: Đệm sàn xanh dương `#3b82f6`.
   - **Hàng gia dụng (Household)**: Đệm sàn màu cam/hổ phách `#f59e0b`.
   - **Chăm sóc cá nhân (Personal Care)**: Đệm sàn màu tím `#8b5cf6`.
   - **Quầy thanh toán (Checkout Counters)**: Đệm sàn màu xanh cyan `#06b6d4`.
   - **Lối ra (Exit Gate)**: Đệm sàn màu xám `#64748b`.
3. **8 Dãy kệ hàng Gondola (Shelves)**:
   - Kệ A1, A2 (Thực phẩm khô), Kệ B1, B2 (Đồ uống & Sữa), Kệ C1, C2 (Gia dụng), Kệ D1, D2 (Chăm sóc cá nhân).
   - Mỗi kệ có vách kim loại trung tâm, 2 trụ hồi và 3 tầng đợt đỗ hàng.
   - Trên mỗi tầng kệ xếp các hàng hộp ngũ cốc, bánh kẹo, chai nước giải khát, can nước giặt, chai dầu gội low-poly nhiều màu sắc.
4. **3 Quầy thu ngân (Counters)**:
   - Bàn thu ngân, băng chuyền cao su đen, màn hình hiển thị POS phát sáng.

---

## 4. Mô hình Xe đẩy thông minh 3D (Smart Cart 3D)

Mỗi xe đẩy trong siêu thị 3D được cấu thành từ:
- **Khung gầm kim loại mạ chrome**: 4 bánh xe cao su xoay linh hoạt.
- **Giỏ chứa hàng kim loại (Wire Basket)**: Giỏ mắt lưới hiện đại, bên trong chứa các khối sản phẩm 3D khi có hàng trong giỏ.
- **Tay đẩy & Màn hình IoT Console**: Màn hình LCD phát sáng xanh gắn trên tay cầm thể hiện trạng thái thông minh.
- **Vòng hào quang trạng thái (Status Aura Ring)**: Vòng tròn phát sáng dưới gầm xe:
  - Xanh lá: Online / Đang mua.
  - Vàng/Cam: Cảnh báo (Lệch cân, Pin yếu).
  - Đỏ: Xe bị khoá từ xa.
  - Xám: Xe mất mạng / Offline.
  - Xanh dương: Vừa hoàn tất Checkout.
- **Cột sáng Highlight**: Cột ánh sáng hình nón xanh phát sáng khi xe được chọn.
- **Nhãn nổi 3D (Floating Badge)**: Bảng thông tin nổi trên nóc xe hiển thị Cart ID, mức pin thực tế và trạng thái hoạt động.

---

## 5. Camera & Tương tác 3D

- **Preset Camera**:
  - `Isometric`: Góc nhìn chéo 40° từ trên cao quan sát toàn bộ không gian.
  - `Nhìn từ trên (Top-Down)`: Góc nhìn vuông góc 90° từ đỉnh.
  - `Bám theo xe (Follow Cart)`: Camera tự động xoay và bám theo tọa độ xe đang được chọn khi xe di chuyển.
  - `Đặt lại (Reset)`: Đưa camera về góc nhìn chuẩn ban đầu.
- **Tương tác trực tiếp**:
  - Click vào xe đẩy 3D -> Chọn xe và cập nhật Cockpit Inspector bên phải.
  - Click vào mặt sàn phân vùng hoặc nút điểm đến 3D -> Xe tự động tìm đường qua mạng lưới hành lang và chạy tới đích.

---

## 6. Kết quả Kiểm thử (E2E Test Results)

Hệ thống đã chạy kiểm thử tự động toàn diện qua Playwright:

| Bộ kiểm thử | Số lượng bài test | Kết quả | Ghi chú |
|---|---|---|---|
| `test_simulation_2d.py` | 4 tests | **PASS (100%)** | Kiểm thử tương tác bản đồ, chuyển động, kịch bản IoT, offline |
| `test_ui.py` | 13 tests | **PASS (100%)** | Khách hàng quét hàng, quản trị, cảnh báo, simulator |
| `test_ui_auth.py` | 3 tests | **PASS (100%)** | Xác thực đăng nhập phân quyền Admin / Viewer |
| `test_ui_manage.py` | 4 tests | **PASS (100%)** | Đăng ký xe mới, huỷ phiên treo, quản lý sản phẩm |
| **Tổng cộng** | **24 tests** | **PASS (24/24)** | **Toàn bộ hệ thống ổn định 100%** |
