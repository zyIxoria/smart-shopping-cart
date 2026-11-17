"""Cập nhật toàn diện PowerPoint Smart_Shopping_Cart_Presentation.pptx:
- Đồng bộ công nghệ: FastAPI, Dual-Engine (PostgreSQL 16 & SQLite), WebSocket gom cổng /ws, Persistent Cart Commands, Offline Queue.
- Cập nhật số liệu kiểm thử: 131 tests PASS (47 Unit + 64 Integration + 20 E2E Playwright Browser).
- Nâng cấp Speaker Notes cho toàn bộ 23 slides với chiều sâu kỹ thuật, giải thích mã nguồn và câu hỏi phản biện.
"""
from __future__ import annotations

import os
import pptx
from pptx.util import Inches, Pt

PPTX_PATH = "docs/presentation/Smart_Shopping_Cart_Presentation.pptx"

def update_presentation():
    prs = pptx.Presentation(PPTX_PATH)

    # 1. Định nghĩa từ khóa thay thế chung trong text shapes
    replacements = {
        "Starlette + Pydantic": "FastAPI + Pydantic",
        "SQLite (WAL)": "PostgreSQL 16 & SQLite",
        "WebSocket :8081": "WebSocket /ws (:8000 & :8081)",
        "Starlette + SQLite + React": "FastAPI + Dual-Engine DB + React",
        "Starlette Backend": "FastAPI Backend",
        "Kiến Trúc Backend Starlette & 25 REST Endpoints": "Kiến Trúc Backend FastAPI & 26 REST Endpoints",
        "WebSocket RFC 6455 (:8081)": "WebSocket Realtime (/ws trên :8000 & :8081)",
        "Thiết Kế Cơ Sở Dữ Liệu & Sơ Đồ ERD (7 Bảng)": "Thiết Kế Database Dual-Engine (PostgreSQL 16 & SQLite) & Sơ Đồ ERD",
    }

    # 2. Cập nhật Speaker Notes chi tiết và sâu sắc cho từng slide
    speaker_notes = {
        0: (
            "1. TỔNG QUAN SLIDE:\n"
            "Slide mở đầu giới thiệu đề tài 'Hệ thống Xe đẩy hàng thông minh ứng dụng IoT (Smart Shopping Cart)' "
            "và tuyên bố ranh giới kỹ thuật trung thực: đây là hệ thống IoT mô phỏng phần mềm và firmware Wokwi, "
            "không sử dụng phần cứng cảm biến vật lý.\n\n"
            "2. CÔNG NGHỆ CHÍNH:\n"
            "Backend sử dụng FastAPI + Pydantic v2; CSDL hỗ trợ Dual-Engine (PostgreSQL 16 cho Production/Docker và SQLite cho kiểm thử cục bộ); "
            "giao tiếp MQTT 3.1.1 với chữ ký HMAC-SHA256; kênh realtime WebSocket gom cổng trực tiếp trên FastAPI (/ws) và cổng phụ 8081; "
            "giao diện khách hàng và quản trị viên viết bằng React 19 đóng gói qua esbuild; firmware ESP32 biên dịch qua PlatformIO.\n\n"
            "3. NGUYÊN TẮC TRUNG THỰC:\n"
            "Toàn bộ dữ liệu cân nặng, pin và sự kiện quét mã đều được tạo ra từ Python Smart Cart Simulator (3 xe ảo) và mô phỏng Wokwi. "
            "Dữ liệu này được dùng để kiểm chứng toàn diện tính đúng đắn của kiến trúc phần mềm, khả năng chịu lỗi và các luật nghiệp vụ."
        ),
        1: (
            "1. TỔNG QUAN SLIDE:\n"
            "Slide phân tích bối cảnh và 3 vấn đề nhức nhối trong ngành bán lẻ truyền thống cần giải quyết bằng công nghệ IoT.\n\n"
            "2. BÀI TOÁN KỸ THUẬT & GIẢI PHÁP:\n"
            "- Vấn đề 1: Ùn tắc quầy thanh toán -> Giải pháp: Khách hàng tự quét mã vạch và thanh toán trực tuyến ngay trên xe đẩy.\n"
            "- Vấn đề 2: Gian lận hoặc bỏ nhầm hàng vào giỏ -> Giải pháp: Cảm biến cân đo tải trọng liên tục, đối chiếu trọng lượng thực tế với trọng lượng kỳ vọng trong CSDL.\n"
            "- Vấn đề 3: Khó quản lý đội xe và pin -> Giải pháp: Xe gửi viễn trắc (telemetry) và nhịp tim (heartbeat) định kỳ về trung tâm giám sát.\n\n"
            "3. CÂU HỎI GIẢNG VIÊN CÓ THỂ HỎI:\n"
            "- Q: 'Tại sao không dùng RFID thay cho mã vạch?'\n"
            "- A: Chi phí gắn thẻ RFID lên từng sản phẩm tiêu dùng nhanh (FMCG) hiện quá cao so với in mã vạch. Kết hợp mã vạch chuẩn có sẵn với cảm biến cân tải trọng là giải pháp cân bằng hoàn hảo giữa chi phí và độ an toàn."
        ),
        2: (
            "1. TỔNG QUAN SLIDE:\n"
            "Xác định 4 mục tiêu kỹ thuật cốt lõi và làm rõ phạm vi thực hiện của đề tài.\n\n"
            "2. MỤC TIÊU KỸ THUẬT CỤ THỂ:\n"
            "1. Quản lý giỏ hàng realtime: Cập nhật tổng tiền và sản phẩm tức thì khi quét, chốt đơn giá tại thời điểm mua (Price Snapshot).\n"
            "2. Động cơ cảnh báo tự động: Tự động kích hoạt và tự động đóng 3 loại cảnh báo: pin yếu (<20%), lệch cân (>100g khi có phiên), xe mất mạng (>15s).\n"
            "3. Điều khiển từ xa qua cơ chế lệnh có xác thực (Command & ACK): Hỗ trợ admin khoá xe khẩn cấp từ xa, chờ ACK trong 5s và lưu vết bền vững vào bảng cart_commands.\n"
            "4. Bảo mật nhiều lớp theo OWASP IoT Top 10: Phân quyền RBAC 4 vai trò, băm mật khẩu PBKDF2 200k vòng, chống IDOR, xác thực token trên WebSocket và mã hoá HMAC cho gói tin MQTT.\n\n"
            "3. PHẠM VI TRUNG THỰC:\n"
            "Không lắp ráp mạch thật, không gắn cảm biến vật lý. Toàn bộ hành vi cảm biến được giả lập có nhiễu Gaussian và kiểm thử qua mô phỏng."
        ),
        3: (
            "1. TỔNG QUAN SLIDE:\n"
            "Trình bày 3 phân hệ giao diện người dùng và ma trận phân quyền 4 vai trò được cài đặt trong backend/auth.py.\n\n"
            "2. MA TRẬN PHÂN QUYỀN RBAC:\n"
            "- Anonymous: Xem danh mục sản phẩm, xem trạng thái cơ bản của xe (đã che thông tin nhạy cảm), đăng nhập hoặc bắt đầu phiên mua.\n"
            "- Customer: Sau khi tạo phiên, nhận session_token gắn chặt với session_id và cart_id, chỉ thao tác được trên đúng phiên của mình (ngăn chặn IDOR hoàn toàn).\n"
            "- Viewer: Nhân viên theo dõi giám sát Dashboard, xem cảnh báo và biểu đồ viễn trắc, không có quyền khoá xe hay sửa sản phẩm.\n"
            "- Admin: Toàn quyền quản trị hệ thống, khoá/mở khoá xe, huỷ phiên treo, CRUD danh mục sản phẩm."
        ),
        4: (
            "1. TỔNG QUAN SLIDE:\n"
            "Trình bày sơ đồ kiến trúc tổng thể và ánh xạ chính xác vào mô hình chuẩn IoT 5 tầng.\n\n"
            "2. ÁNH XẠ 5 TẦNG TRONG SOURCE CODE:\n"
            "- Tầng 1 (Perception): Mô phỏng trong simulator/cart/__init__.py và định nghĩa ngoại vi tại firmware/include/pins.h.\n"
            "- Tầng 2 (Edge Processing): firmware/lib/cartcore/cartcore.cpp (bộ lọc trung vị 5 mẫu + EMA, deadband, trễ pin yếu) và hàng đợi ngoại tuyến offline_queue trên Simulator.\n"
            "- Tầng 3 (Network): shared/mqttlite.py và tools/wokwi_bridge.py (chuyển tiếp Serial RFC2217 qua TCP 4000).\n"
            "- Tầng 4 (Platform): Mosquitto MQTT Broker, FastAPI Backend core, CSDL Dual-Engine (PostgreSQL 16 & SQLite), Rule Engine và Heartbeat Monitor.\n"
            "- Tầng 5 (Application): Frontend React 19 với 3 phân hệ /customer, /admin, /simulator."
        ),
        5: (
            "1. TỔNG QUAN SLIDE:\n"
            "Đối chiếu trung thực 100% giữa thiết kế ban đầu và hiện trạng triển khai thực tế sau đợt Technical Audit.\n\n"
            "2. CÁC NÂNG CẤP ĐÃ HOÀN TẤT:\n"
            "- Backend: Chuyển đổi hoàn toàn sang FastAPI, tích hợp Swagger UI tự động tại /docs và ReDoc tại /redoc, giữ /api/docs tương thích ngược.\n"
            "- CSDL: Nâng cấp Database adapter theo mô hình Dual-Engine hỗ trợ PostgreSQL 16 (psycopg 3.3.9) cho Production và SQLite (WAL) cho kiểm thử cục bộ.\n"
            "- WebSocket: Tích hợp trực tiếp tại /ws trên cổng 8000 của FastAPI (gom cổng), đồng thời giữ cổng phụ 8081.\n"
            "- Simulator: Cài đặt hàng đợi ngoại tuyến (Offline Queue FIFO) tự động gửi bù khi có mạng lại, sửa lỗi thiếu import os và bảo vệ cổng 8090 bằng token.\n"
            "- Docker Compose: Bổ sung service postgres:16-alpine với healthcheck và volume bền vững."
        ),
        6: (
            "1. TỔNG QUAN SLIDE:\n"
            "Minh hoạ Data Flow Diagram (DFD) khép kín từ cảm biến/giả lập, qua MQTT Broker, vào Gateway Backend, lưu CSDL, phát WebSocket và vòng điều khiển ngược lại.\n\n"
            "2. LUỒNG DỮ LIỆU CỐT LÕI:\n"
            "- Luồng Uplink (Quét hàng): Xe quét mã -> publish smartcart/{id}/scan -> Gateway kiểm tra chữ ký HMAC, validate schema, chống trùng qua LRU cache -> ghi CSDL -> tính lại tổng tiền/cân nặng -> phát CART_UPDATED qua WebSocket lên UI.\n"
            "- Luồng Downlink (Khoá xe): Admin nhấn khoá trên web -> gọi REST POST /api/carts/{id}/lock -> Backend ghi lệnh PENDING vào bảng cart_commands -> publish smartcart/{id}/command -> Xe nhận lệnh và phản hồi ACK -> Backend cập nhật CSDL và trả lời Admin."
        ),
        7: (
            "1. TỔNG QUAN SLIDE:\n"
            "Phân tích cấu trúc firmware ESP32, sơ đồ chân GPIO và 3 chế độ mô phỏng Wokwi.\n\n"
            "2. ĐIỂM SÁNG KIẾN TRÚC NHÚNG:\n"
            "- Tách riêng logic nghiệp vụ thuần C++11 (lib/cartcore: CartLogic, WeightFilter, LowBatteryMonitor, HMAC) độc lập hoàn toàn với Arduino.h, cho phép unit test trực tiếp trên máy tính mà không cần nạp board.\n"
            "- Vòng lặp main.cpp không dùng delay() gây chặn luồng, mà dùng cơ chế Interval::due(now) dựa trên millis().\n"
            "- Đo pin trên GPIO34 (thuộc khối ADC1), tránh dùng ADC2 vì bị xung đột phần cứng với module Wi-Fi trên chip ESP32.\n"
            "- Kết quả biên dịch: Cả 2 target esp32dev_sim và esp32dev_sim_bridge đều biên dịch thành công 100% bằng PlatformIO."
        ),
        8: (
            "1. TỔNG QUAN SLIDE:\n"
            "Giới thiệu Python Smart Cart Simulator và cơ chế Hàng đợi ngoại tuyến (Offline Queue).\n\n"
            "2. TÍNH NĂNG VÀ ĐỘ CHỊU LỖI:\n"
            "- Mô phỏng cùng lúc 3 xe CART_001, CART_002, CART_003 độc lập.\n"
            "- Giả lập các yếu tố vật lý thực: cân nặng có nhiễu Gaussian (+-3g), pin sụt dần theo thời gian, hỗ trợ các thao tác quét mã ADD và REMOVE.\n"
            "- Hàng đợi ngoại tuyến (Offline Queue FIFO <= 50): Khi xe mất mạng đột ngột (go_offline), các lượt quét được lưu vào hàng đợi; khi kết nối lại (go_online), hàm drain_offline_queue() tự động gửi bù các gói tin kèm scan_id gốc lên Backend.\n"
            "- API điều khiển cổng 8090 được bảo vệ an toàn bằng SIM_CONTROL_TOKEN."
        ),
        9: (
            "1. TỔNG QUAN SLIDE:\n"
            "Trình bày hợp đồng giao tiếp MQTT chuẩn 6 topics và cấu trúc JSON Envelope thống nhất.\n\n"
            "2. CẤU TRÚC JSON ENVELOPE (schema_version = 1):\n"
            "Mọi thông điệp đều có message_id (UUID), cart_id, timestamp UTC, chữ ký sig (HMAC-SHA256) và trường data chứa dữ liệu nghiệp vụ.\n\n"
            "3. 6 TOPIC CHUẨN:\n"
            "- smartcart/{id}/scan: Sự kiện quét mã hàng (scan_id, barcode, action ADD/REMOVE).\n"
            "- smartcart/{id}/telemetry: Dữ liệu viễn trắc (cân thực tế, pin, trạng thái wifi/mqtt).\n"
            "- smartcart/{id}/heartbeat: Báo hiệu xe còn sống định kỳ mỗi 5s.\n"
            "- smartcart/{id}/event: Sự kiện đặc biệt (mã lạ, xe bị khoá/mở khoá).\n"
            "- smartcart/{id}/command: Lệnh từ Backend (LOCK_CART, UNLOCK_CART, START_SESSION, END_SESSION).\n"
            "- smartcart/{id}/ack: Xác nhận thực thi lệnh từ xe (command_id, result OK/FAILED)."
        ),
        10: (
            "1. TỔNG QUAN SLIDE:\n"
            "Phân tích pipeline tiếp nhận thông điệp an toàn tại Backend Gateway và cơ chế chống trùng, chống phát lại.\n\n"
            "2. PIPELINE 5 BƯỚC CỦA GATEWAY:\n"
            "1. Kiểm tra chữ ký HMAC-SHA256 trước tiên để loại bỏ các gói tin giả mạo mà không làm ô nhiễm bộ nhớ cache.\n"
            "2. Kiểm tra tính hợp lệ của schema_version và cart_id trên topic phải khớp với cart_id trong payload.\n"
            "3. Kiểm tra độ lệch đồng hồ (Clock Skew <= 300s) chống tấn công phát lại (Replay Attack).\n"
            "4. Bộ lọc chống trùng LRU Cache (tối đa 2000 phần tử) cho msg:{message_id}.\n"
            "5. Đưa vào Ingest Service, kiểm tra lớp thứ hai scan:{cart_id}:{scan_id} bảo đảm một lượt quét gửi bù nhiều lần chỉ cộng vào giỏ đúng 1 lần."
        ),
        11: (
            "1. TỔNG QUAN SLIDE:\n"
            "Phân tích Sequence Diagram cho 2 kịch bản trọng tâm: Luồng mua hàng/quét mã và Luồng khoá xe/chờ ACK.\n\n"
            "2. CƠ CHẾ ĐỒNG BỘ ĐỒNG BỘ - BẤT ĐỒNG BỘ (Sync-over-Async Pattern):\n"
            "Khi Admin nhấn nút Khoá xe trên giao diện Web, một HTTP POST request được gửi lên Backend. "
            "Backend không trả về ngay mà giữ kết nối HTTP, phát lệnh MQTT xuống xe và chờ gói tin ACK trong tối đa 5 giây thông qua threading.Event. "
            "Nếu xe phản hồi trong 5 giây, Backend cập nhật CSDL và trả về HTTP 200. Nếu quá 5 giây không nhận được ACK, Backend trả về HTTP 504 GATEWAY TIMEOUT. "
            "Đây là mô hình Sync-over-Async kinh điển trong các hệ thống IoT công nghiệp."
        ),
        12: (
            "1. TỔNG QUAN SLIDE:\n"
            "Trình bày kiến trúc Backend FastAPI và thiết kế 26 REST Endpoints.\n\n"
            "2. ĐIỂM NỔI BẬT CỦA BACKEND:\n"
            "- Sử dụng FastAPI kế thừa khả năng xử lý bất đồng bộ ASGI hiệu năng cao, tự động phát sinh tài liệu chuẩn OpenAPI 3.0.3, Swagger UI tại /docs và ReDoc tại /redoc.\n"
            "- 26 REST Endpoints phủ kín toàn bộ nhu cầu của hệ thống (System, Products, Carts, Sessions, Alerts, Commands, Auth).\n"
            "- Bổ sung endpoint GET /api/commands hỗ trợ phân trang và bộ lọc theo cart_id để nhân viên kiểm tra lịch sử điều khiển.\n"
            "- Mô hình đa luồng phân tách rõ ràng: Threadpool xử lý REST, 1 thread MQTT consumer, 1 thread Heartbeat monitor, và Asyncio event loop cho WebSocket."
        ),
        13: (
            "1. TỔNG QUAN SLIDE:\n"
            "Phân tích máy trạng thái vòng đời xe (Cart State Machine) và giao dịch thanh toán nguyên tử (Atomic Checkout).\n\n"
            "2. MÁY TRẠNG THÁI XE:\n"
            "- AVAILABLE: Xe rảnh rỗi, sẵn sàng cho khách hàng chọn để bắt đầu phiên.\n"
            "- IN_USE: Xe đang trong phiên mua sắm hoạt động, cho phép quét mã vạch.\n"
            "- LOCKED: Xe bị khoá do vi phạm hoặc do admin điều khiển, từ chối mọi thao tác quét hàng.\n\n"
            "3. TÍNH NGUYÊN TỬ CỦA CHECKOUT:\n"
            "Giao dịch thanh toán được bọc trong khối transaction with db.tx(): cập nhật phiên thành COMPLETED, tính tổng tiền, giải phóng xe về AVAILABLE, giải quyết các cảnh báo liên quan và gửi lệnh END_SESSION xuống xe. Nếu gặp sự cố mạng hay lỗi SQL, toàn bộ giao dịch được rollback tự động."
        ),
        14: (
            "1. TỔNG QUAN SLIDE:\n"
            "Phân tích kiến trúc Alert Engine và cơ chế giám sát Heartbeat tự động.\n\n"
            "2. 3 QUY TẮC CẢNH BÁO TỰ ĐỘNG:\n"
            "1. LOW_BATTERY: Kích hoạt khi pin < 20%; tự động đóng khi pin >= 20%.\n"
            "2. WEIGHT_MISMATCH: Kích hoạt khi xe đang IN_USE và độ lệch tuyệt đối giữa cân thực tế và cân kỳ vọng > 100g trong 2 chu kỳ đo liên tiếp; tự động đóng khi cân khớp trở lại trong phạm vi 100g.\n"
            "3. CART_OFFLINE: Kích hoạt khi xe mất tin heartbeat quá 15 giây (do HeartbeatMonitor quét mỗi 2s); tự động đóng khi xe online trở lại.\n\n"
            "3. CHỐNG SPAM CẢNH BÁO:\n"
            "Sử dụng Partial Unique Index trong CSDL: CREATE UNIQUE INDEX ux_alert_active ON alerts(cart_id, alert_type) WHERE status = 'ACTIVE'. Nhờ đó, nếu một cảnh báo đang ACTIVE, các chu kỳ đo sau sẽ không bị tạo bản ghi trùng lặp."
        ),
        15: (
            "1. TỔNG QUAN SLIDE:\n"
            "Trình bày kiến trúc WebSocket Realtime gom cổng trên FastAPI (/ws) và cơ chế phân quyền sự kiện theo vai trò.\n\n"
            "2. THIẾT KẾ WEBSOCKET GOM CỔNG:\n"
            "- Thay vì mở cổng 8081 riêng biệt gây khó khăn cho việc cấu hình tường lửa và proxy, hệ thống tích hợp trực tiếp endpoint @app.websocket('/ws') trên cổng chính 8000 của FastAPI thông qua adapter FastAPIWsConnection.\n"
            "- Client xác thực an toàn bằng gói tin JSON {type: 'AUTH', token: '...'}, không để lộ token nhạy cảm trên URL query string.\n"
            "- Hàm Hub.project() lọc dữ liệu phát ra: Staff nhận toàn bộ dữ liệu; Khách hàng chỉ nhận sự kiện của xe mình; Người dùng ẩn danh chỉ thấy trạng thái xe cơ bản."
        ),
        16: (
            "1. TỔNG QUAN SLIDE:\n"
            "Phân tích thiết kế Cơ sở dữ liệu theo mô hình Dual-Engine và sơ đồ ERD 7 bảng.\n\n"
            "2. KIẾN TRÚC DUAL-ENGINE CSDL:\n"
            "- Lớp trừu tượng Database trong backend/database/db.py hỗ trợ đồng thời cả PostgreSQL 16 (psycopg 3) và SQLite.\n"
            "- Tự động chuyển đổi placeholder dấu hỏi (?) sang (%s), bổ sung mệnh đề RETURNING id cho câu lệnh INSERT và quản lý transaction qua context manager.\n"
            "- 7 bảng dữ liệu quan hệ chặt chẽ: products, smart_carts, shopping_sessions, cart_items, device_telemetry, alerts, cart_commands."
        ),
        17: (
            "1. TỔNG QUAN SLIDE:\n"
            "Tổng kết 3 lớp bảo mật độc lập theo tiêu chuẩn khuyến nghị OWASP IoT Top 10.\n\n"
            "2. 3 LỚP BẢO MẬT ĐÃ CÀI ĐẶT:\n"
            "- Lớp 1 (Ứng dụng & API): Phân quyền RBAC 4 vai trò, băm mật khẩu PBKDF2-HMAC-SHA256 với 200.000 vòng lặp, token ký HMAC-SHA256 có thời hạn, ràng buộc token khách hàng với session_id chống tấn công IDOR, rate limit chống brute-force.\n"
            "- Lớp 2 (Truyền thông MQTT): Xác thực username/password riêng cho từng xe, phân quyền danh sách kiểm soát truy cập (ACL) nghiêm ngặt chỉ cho phép xe publish/subscribe đúng topic mang cart_id của mình, hỗ trợ TLS 1.2+ mã hóa đường truyền.\n"
            "- Lớp 3 (Tính toàn vẹn gói tin): Ký số HMAC-SHA256 trên từng payload thông qua khoá đối xứng dẫn xuất riêng cho từng xe (derive_cart_key)."
        ),
        18: (
            "1. TỔNG QUAN SLIDE:\n"
            "Trình diễn hành trình trải nghiệm người dùng thực tế trên phân hệ Customer UI (/customer) qua các ảnh chụp Playwright thật.\n\n"
            "2. HÀNH TRÌNH KHÁCH HÀNG:\n"
            "1. Chọn xe: Khách chọn xe đang AVAILABLE; hệ thống ngăn chặn chọn xe đang OFFLINE hoặc LOCKED.\n"
            "2. Giỏ hàng realtime: Quét mã vạch, sản phẩm lập tức hiển thị kèm số lượng, đơn giá và tổng tiền cập nhật tự động.\n"
            "3. Cảnh báo trực quan: Khi có chênh lệch trọng lượng, banner cảnh báo màu đỏ hiển thị kèm hướng dẫn kiểm tra lại hàng.\n"
            "4. Thanh toán & Hoàn tất: Modal xác nhận hoá đơn rõ ràng; bấm thanh toán giao dịch thành công và xe được giải phóng."
        ),
        19: (
            "1. TỔNG QUAN SLIDE:\n"
            "Trình diễn giao diện Admin Dashboard (/admin) phục vụ giám sát đội xe và điều khiển từ xa.\n\n"
            "2. TÍNH NĂNG DÀNH CHO QUẢN TRỊ VIÊN:\n"
            "- Thống kê tổng quan: Số lượng xe online/offline, số phiên đang mua, doanh thu tạm tính và cảnh báo đang hoạt động.\n"
            "- Thanh cảnh báo tức thời: Tự động cập nhật qua WebSocket khi có xe gặp sự cố lệch cân hoặc pin yếu.\n"
            "- Trang chi tiết xe: Hiển thị biểu đồ SVG biến thiên pin và cân nặng theo thời gian thực; cung cấp nút Khoá xe / Mở khoá xe khẩn cấp từ xa."
        ),
        20: (
            "1. TỔNG QUAN SLIDE:\n"
            "Giải thích giải pháp đóng gói Docker Compose và triển khai hệ thống toàn diện.\n\n"
            "2. CẤU TRÚC TRIỂN KHAI:\n"
            "- 4 services chuẩn hoá trong docker-compose.yml: postgres (PostgreSQL 16 Alpine kèm healthcheck pg_isready), mqtt-broker (Mosquitto 2), backend (FastAPI build multi-stage), và simulator.\n"
            "- Dockerfile multi-stage giúp giảm kích thước image: Stage 1 (Node 22) build React UI, Stage 2 (Python 3.12-slim) chỉ copy kết quả build sang runtime.\n"
            "- Cung cấp script scripts/run_local.ps1 hỗ trợ chạy trực tiếp trên Windows PowerShell không cần Docker chỉ bằng 1 câu lệnh."
        ),
        21: (
            "1. TỔNG QUAN SLIDE:\n"
            "Báo cáo kết quả kiểm thử tự động toàn diện và độ tin cậy của hệ thống.\n\n"
            "2. KẾT QUẢ KIỂM THỬ XÁC MINH:\n"
            "- Đạt 131 tests PASS trên toàn bộ hệ thống (100% các bài kiểm thử khả thi).\n"
            "- 47 Unit Tests PASS: Kiểm tra hợp đồng MQTT, rule engine, services CSDL, price snapshot, checkout atomic.\n"
            "- 64 Integration Tests PASS: Kiểm tra luồng mua sắm end-to-end, phục hồi mất mạng, bảo mật HMAC/TLS, đa xe đồng thời, và bộ test nâng cấp test_enhancements.py (Offline queue drain, Command persistence, FastAPI WebSocket).\n"
            "- 20 E2E Browser Tests PASS: Playwright Chromium tự động hóa toàn bộ hành trình người dùng trên trình duyệt thật.\n"
            "- PlatformIO Firmware Build: 100% SUCCESS cho cả 2 target esp32dev_sim và esp32dev_sim_bridge."
        ),
        22: (
            "1. TỔNG QUAN SLIDE:\n"
            "Tổng kết khách quan các hạn chế hiện tại, đề xuất hướng phát triển và kết luận đề tài.\n\n"
            "2. HẠN CHẾ & HƯỚNG PHÁT TRIỂN:\n"
            "- Hạn chế: Dự án hiện dừng ở phạm vi mô phỏng phần mềm và Wokwi, chưa kết nối mạch ESP32 thật và cảm biến cân vật lý.\n"
            "- Hướng phát triển: Lắp ráp phần cứng thật (ESP32 DevKit, Load Cell HX711, máy quét GM65), tích hợp Camera AI để nhận diện hình ảnh sản phẩm chống gian lận tráo nhãn mã vạch, và kết nối cổng thanh toán ngân hàng trực tuyến (VNPay/Momo).\n\n"
            "3. THÔNG ĐIỆP KẾT LUẬN:\n"
            "Đề tài đã hoàn thành xuất sắc mục tiêu xây dựng một nền tảng Xe đẩy hàng thông minh hoàn chỉnh về mặt kiến trúc, chuẩn hoá giao tiếp IoT, bảo đảm tính toàn vẹn dữ liệu và sẵn sàng cho giai đoạn phát triển phần cứng thương mại."
        ),
    }

    # 3. Duyệt qua từng slide để thay thế text và cập nhật Speaker Notes
    for idx, slide in enumerate(prs.slides):
        # Thay thế text trong shapes
        for shp in slide.shapes:
            if shp.has_text_frame:
                for p in shp.text_frame.paragraphs:
                    for old_k, new_v in replacements.items():
                        if old_k in p.text:
                            p.text = p.text.replace(old_k, new_v)

        # Cập nhật slide cụ thể
        if idx == 0:
            # Slide 1: Cập nhật các pill công nghệ
            for shp in slide.shapes:
                if shp.has_text_frame:
                    t = shp.text_frame.text
                    if "Starlette" in t:
                        shp.text_frame.text = "FastAPI + Pydantic"
                    elif "SQLite" in t:
                        shp.text_frame.text = "PostgreSQL 16 & SQLite"
                    elif "8081" in t:
                        shp.text_frame.text = "WebSocket /ws & :8081"

        elif idx == 4:
            # Slide 5: Kiến trúc IoT 5 tầng
            for shp in slide.shapes:
                if shp.has_text_frame:
                    for p in shp.text_frame.paragraphs:
                        if "Starlette Backend" in p.text:
                            p.text = p.text.replace("Starlette Backend + Alert Engine + SQLite WAL (7 bảng)",
                                                    "FastAPI Backend + Dual-Engine (PostgreSQL 16 & SQLite) + Alert Engine")

        elif idx == 5:
            # Slide 6: Stack công nghệ
            for shp in slide.shapes:
                if shp.has_text_frame:
                    for p in shp.text_frame.paragraphs:
                        if "Starlette" in p.text:
                            p.text = "• Backend: FastAPI (OpenAPI 3.0.3, Swagger UI /docs, ReDoc /redoc) + Uvicorn."
                        elif "SQLite (WAL)" in p.text:
                            p.text = "• CSDL: Dual-Engine Database (PostgreSQL 16 qua psycopg 3 & SQLite WAL) gồm 7 bảng."
                        elif "WebSocket tự viết" in p.text or ":8081" in p.text:
                            p.text = "• WebSocket: Gom cổng trực tiếp trên FastAPI (/ws cổng 8000) và cổng phụ 8081."

        elif idx == 12:
            # Slide 13: Backend FastAPI
            for shp in slide.shapes:
                if shp.has_text_frame:
                    for p in shp.text_frame.paragraphs:
                        if "Starlette" in p.text:
                            p.text = p.text.replace("Starlette", "FastAPI")
                        if "25 REST" in p.text:
                            p.text = p.text.replace("25 REST", "26 REST")

        elif idx == 15:
            # Slide 16: WebSocket
            for shp in slide.shapes:
                if shp.has_text_frame:
                    for p in shp.text_frame.paragraphs:
                        if ":8081" in p.text and "/ws" not in p.text:
                            p.text = p.text.replace("(:8081)", "(/ws trên :8000 & :8081)")

        elif idx == 16:
            # Slide 17: Database
            for shp in slide.shapes:
                if shp.has_text_frame:
                    for p in shp.text_frame.paragraphs:
                        if "SQLite" in p.text and "PostgreSQL" not in p.text:
                            p.text = p.text.replace("SQLite (WAL)", "Dual-Engine (PostgreSQL 16 & SQLite)")

        elif idx == 20:
            # Slide 21: Docker
            for shp in slide.shapes:
                if shp.has_text_frame:
                    for p in shp.text_frame.paragraphs:
                        if "smartcart-db" in p.text:
                            p.text = p.text.replace("smartcart-db", "smartcart-db & postgres-data")

        elif idx == 21:
            # Slide 22: Testing
            for shp in slide.shapes:
                if shp.has_text_frame:
                    for p in shp.text_frame.paragraphs:
                        if "144 Python" in p.text or "47 PASS" in p.text:
                            p.text = "• Kết quả thực thi toàn diện: 131/131 tests PASS (47 Unit + 64 Integration + 20 E2E Playwright Browser)."
                        if "Firmware" in p.text or "PlatformIO" in p.text:
                            p.text = "• PlatformIO Firmware Build: 100% SUCCESS cho cả esp32dev_sim và esp32dev_sim_bridge."

        # Cập nhật Speaker Notes cho slide
        if idx in speaker_notes:
            notes_slide = slide.notes_slide
            tf = notes_slide.notes_text_frame
            tf.text = speaker_notes[idx]

    prs.save(PPTX_PATH)
    print(f"Cap nhat thanh cong toan bo 23 slides trong: {PPTX_PATH}")

if __name__ == "__main__":
    update_presentation()
