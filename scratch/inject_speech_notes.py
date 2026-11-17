"""Chèn trực tiếp lời thoại thuyết trình tự nhiên (kịch bản đọc khi trình chiếu) vào phần đầu Speaker Notes
của toàn bộ 23 slides trong Smart_Shopping_Cart_Presentation.pptx, giữ nguyên phần ghi chú kỹ thuật & Q&A bên dưới.
"""
from __future__ import annotations

import pptx

PPTX_PATH = "docs/presentation/Smart_Shopping_Cart_Presentation.pptx"

SPEECH_SCRIPTS = {
    0: (
        "Kính thưa quý thầy cô trong hội đồng. Hôm nay nhóm/em xin phép trình bày đồ án Hệ Thống Xe Đẩy Hàng Thông Minh Ứng Dụng IoT — Smart Shopping Cart System.\n"
        "Trước khi đi vào chi tiết, em xin nêu rõ phạm vi trung thực của đề tài: đây là hệ thống IoT mô phỏng, sử dụng Python Smart Cart Simulator mô phỏng 3 xe đẩy hoạt động song song kết hợp với mã nguồn Firmware ESP32 và cấu hình mô phỏng Wokwi. Đề tài không lắp ráp phần cứng vật lý; toàn bộ dữ liệu cân nặng, pin và quét mã là dữ liệu mô phỏng nhằm kiểm chứng toàn diện kiến trúc phần mềm, giao thức truyền thông và độ tin cậy của hệ thống.\n"
        "Về công nghệ lõi, hệ thống sử dụng Backend FastAPI, cơ sở dữ liệu Dual-Engine (PostgreSQL 16 & SQLite), giao tiếp MQTT 3.1.1 kèm chữ ký HMAC, kênh realtime WebSocket và giao diện React 19."
    ),
    1: (
        "Đề tài xuất phát từ 3 bài toán thực tế rất phổ biến tại các siêu thị truyền thống:\n"
        "- Thứ nhất là ùn tắc tại quầy thu ngân: Vào giờ cao điểm, khách hàng phải xếp hàng dài chờ nhân viên quét lại từng món đồ, đồng thời bản thân khách không theo dõi được tổng số tiền đang mua theo thời gian thực.\n"
        "- Thứ hai là sai sót và thất thoát hàng hoá: Khách có thể quên hoặc cố ý bỏ sản phẩm vào giỏ mà không quét mã, trong khi xe đẩy thông thường không có cơ chế đối soát trọng lượng.\n"
        "- Thứ ba là khó giám sát đội xe đẩy: Bộ phận quản lý không nắm được xe nào đang rảnh, xe nào sắp hết pin để sạc kịp thời hoặc không thể khoá xe từ xa khi có bất thường.\n"
        "Từ đó, giải pháp Smart Shopping Cart IoT giải quyết bằng cách đưa xử lý thông minh xuống từng xe đẩy tại biên và đồng bộ dữ liệu thời gian thực về trung tâm."
    ),
    2: (
        "Để giải quyết 3 vấn đề trên, hệ thống hướng tới 4 mục tiêu kỹ thuật chính:\n"
        "1. Mô phỏng đồng thời 3 xe đẩy (CART_001 đến CART_003) và firmware ESP32 giao tiếp qua MQTT.\n"
        "2. Xây dựng 3 luật cảnh báo tự động theo thời gian thực: pin yếu dưới 20%, lệch cân vượt quá 100g khi có phiên mua hàng, và mất kết nối quá 15 giây.\n"
        "3. Đẩy cập nhật tức thời qua WebSocket trên cổng FastAPI.\n"
        "4. Áp dụng 3 lớp bảo mật từ tầng API, mạng MQTT đến toàn vẹn gói tin.\n"
        "Ở cột bên phải, em xin nhấn mạnh lại ranh giới trung thực: cảm biến cân có nhiễu Gaussian ±3g và tụt pin được mô phỏng bằng phần mềm; Firmware ESP32 đã được biên dịch thành công bằng PlatformIO cho Wokwi nhưng chưa đo kiểm trực tiếp trên bo mạch vật lý."
    ),
    3: (
        "Hệ thống được chia thành 3 phân hệ giao diện rõ ràng:\n"
        "- Customer UI (/customer): Dành cho khách hàng, không cần tạo tài khoản. Khách chỉ cần chọn một xe đang rảnh và online để bắt đầu phiên, nhận một session_token gắn chặt với phiên đó, theo dõi giỏ hàng và thanh toán.\n"
        "- Admin Dashboard (/admin): Dành cho nhân viên và quản trị viên đăng nhập bằng Bearer token để theo dõi đội xe, biểu đồ telemetry, xử lý cảnh báo và khoá/mở khoá xe từ xa.\n"
        "- Simulator UI (/simulator): Bảng điều khiển giả lập phần cứng thay thế cảm biến thật.\n"
        "Ở bảng bên dưới là ma trận phân quyền 4 vai trò (anonymous, customer, viewer, admin). Điểm quan trọng là token của khách hàng được ràng buộc chặt với session_id và cart_id để chống lỗ hổng IDOR — tức khách của xe 1 tuyệt đối không xem hay thao tác được vào phiên của xe 2."
    ),
    4: (
        "Slide này trình bày kiến trúc tổng thể hệ thống được ánh xạ vào mô hình IoT 5 tầng chuẩn:\n"
        "- Tầng 1 (Perception): Gồm cảm biến cân, đầu đọc mã vạch, đo pin — được mô phỏng bởi SmartCart Python và định nghĩa chân phần cứng trong firmware/include/pins.h.\n"
        "- Tầng 2 (Edge Processing): Thực hiện lọc nhiễu cân trung vị 5 mẫu kết hợp EMA, chuẩn hoá mã vạch ở tầng nhúng, và hàng đợi ngoại tuyến Offline Queue trên Simulator.\n"
        "- Tầng 3 (Network): Sử dụng giao thức MQTT 3.1.1 cùng cầu nối Serial TCP cho Wokwi.\n"
        "- Tầng 4 (Platform): Bao gồm MQTT Broker (Mosquitto / DevBroker), Backend FastAPI, CSDL Dual-Engine (PostgreSQL 16 & SQLite) và Alert Engine.\n"
        "- Tầng 5 (Application): Là ứng dụng web React 19 giao tiếp qua REST API và WebSocket /ws trên cổng 8000."
    ),
    5: (
        "Bảng này tổng hợp toàn bộ ngăn xếp công nghệ thực tế đang chạy trong source code sau đợt hoàn thiện:\n"
        "- Backend & API sử dụng FastAPI + Uvicorn + Pydantic, tự động sinh Swagger UI tại /docs và ReDoc tại /redoc.\n"
        "- Cơ sở dữ liệu triển khai theo kiến trúc Dual-Engine: hỗ trợ cả PostgreSQL 16 (qua driver psycopg 3) cho môi trường Docker/Production và SQLite (WAL mode) cho kiểm thử cục bộ siêu nhanh.\n"
        "- WebSocket đã được tích hợp trực tiếp vào FastAPI tại /ws cổng 8000 (song song giữ cổng phụ 8081).\n"
        "- Frontend dùng React 19 đóng gói tĩnh bằng esbuild.\n"
        "Điểm thiết kế nổi bật là toàn bộ tầng hạ tầng đều nằm sau interface trừu tượng, giúp chuyển đổi giữa SQLite và PostgreSQL 16 mà không phải sửa một dòng code nào ở tầng nghiệp vụ services/."
    ),
    6: (
        "Trên sơ đồ Data Flow này, luồng dữ liệu vận hành khép kín theo hai chiều:\n"
        "- Theo chiều Uplink (từ bước 1 đến bước 5): Khi xe quét mã hoặc gửi telemetry, gói tin được bọc trong JSON Envelope chuẩn kèm message_id và chữ ký HMAC, gửi qua MQTT Broker tới Gateway của Backend. Gateway thực hiện kiểm tra chữ ký, chống trùng lặp, rồi mới đưa vào lưu CSDL và chạy Alert Engine.\n"
        "- Từ bước 6 đến bước 7: Mọi thay đổi đều được WebSocket Hub phát tức thời tới giao diện Customer và Admin (có lọc theo quyền).\n"
        "- Theo chiều Downlink (bước 8): Khi Admin bấm khoá xe, lệnh đi qua REST API, được lưu vết vào bảng cart_commands, đẩy xuống MQTT và chờ thiết bị phản hồi ACK.\n"
        "Xuyên suốt luồng này, Backend đóng vai trò Single Source of Truth — thiết bị không được tự ý thay đổi trạng thái phiên hay giá tiền."
    ),
    7: (
        "Ở phần nhúng ESP32, nhóm áp dụng nguyên tắc tách lớp kiến trúc rõ ràng:\n"
        "- Toàn bộ logic nghiệp vụ thuần tuý như parser JSON, máy trạng thái CartLogic, bộ lọc cân WeightFilter (lọc trung vị 5 mẫu loại nhiễu xung kết hợp làm mượt EMA) và tính chữ ký HMAC-SHA256 được tách vào thư viện lib/cartcore viết bằng C++11 thuần, không phụ thuộc Arduino.h nên có thể chạy unit test ngay trên PC.\n"
        "- File src/main.cpp chỉ đóng vai trò kết nối phần cứng, sử dụng vòng lặp non-blocking dựa trên millis() để đọc máy quét UART2 (GPIO16/17), Load Cell HX711 (GPIO32/33), OLED SSD1306 (I2C) và đo pin qua GPIO34 (ADC1) — tránh dùng ADC2 vì bị xung đột phần cứng với Wi-Fi của ESP32.\n"
        "- Hệ thống cấu hình sẵn 3 chế độ mô phỏng Wokwi và đã biên dịch thành công 100% ra file nhị phân firmware.bin cho cả môi trường esp32dev_sim và esp32dev_sim_bridge."
    ),
    8: (
        "Để kiểm thử hệ thống nhiều xe đồng thời mà không phụ thuộc phần cứng thật, dự án xây dựng Python Smart Cart Simulator với giao diện điều khiển trực quan /simulator như ảnh chụp thực tế bên trái.\n"
        "Simulator có 3 điểm kỹ thuật đáng chú ý:\n"
        "1. Mô phỏng 3 xe độc lập, cân nặng có nhiễu Gaussian ±3g và pin tụt dần theo thời gian thực.\n"
        "2. Cài đặt Hàng đợi ngoại tuyến (Offline Queue FIFO tối đa 50 lượt quét): Khi xe bị ngắt mạng đột ngột (go_offline), các lượt quét vẫn được lưu lại kèm scan_id gốc. Ngay khi có mạng lại, hàm drain_offline_queue() tự động gửi bù lần lượt lên Backend để không mất giỏ hàng.\n"
        "3. API điều khiển mô phỏng cổng :8090 được bảo vệ bằng cơ chế xác thực Bearer token qua biến SIM_CONTROL_TOKEN."
    ),
    9: (
        "Giao tiếp giữa thiết bị và Backend tuân thủ chặt chẽ hợp đồng 6 MQTT topics dưới tiền tố smartcart/{cart_id}/:\n"
        "- 5 topic chiều lên (Uplink) gồm: scan (quét thêm/bớt sản phẩm), telemetry (cân nặng, pin), heartbeat (báo sống mỗi 5 giây), event (mã lạ, sự cố) và ack (xác nhận thực thi lệnh).\n"
        "- 1 topic chiều xuống (Downlink) là command để điều khiển xe.\n"
        "Mọi gói tin đều bọc trong một JSON Envelope chuẩn (schema_version = 1) có message_id dạng UUID, timestamp UTC và trường chữ ký sig.\n"
        "Lưu ý kỹ thuật: Client mqttlite.py dùng QoS 0 để giữ mã nguồn siêu nhẹ không phụ thuộc thư viện ngoài; nhưng độ tin cậy được bù đắp hoàn toàn ở tầng ứng dụng bằng Offline Queue, cơ chế Command + ACK chờ 5 giây, và HeartbeatMonitor."
    ),
    10: (
        "Khi một gói tin MQTT đi vào Backend tại gateway.py, nó phải vượt qua pipeline kiểm soát 5 bước tuần tự:\n"
        "- Bước 1: Parse topic và kiểm tra loại thông điệp hợp lệ.\n"
        "- Bước 2: Kiểm tra chữ ký HMAC-SHA256 trước tiên — bước này giúp chặn ngay gói tin giả mạo từ bên ngoài để tránh làm ô nhiễm bộ nhớ đệm chống trùng.\n"
        "- Bước 3: Kiểm tra schema JSON và đối chiếu cart_id trong payload phải khớp với cart_id trên topic.\n"
        "- Bước 4: Kiểm tra độ lệch thời gian (Clock Skew ≤ 300 giây) để chống tấn công phát lại (Replay Attack).\n"
        "- Bước 5: Kiểm tra bộ nhớ đệm LRU Dedupe 2000 phần tử cho message_id và scan_id — đảm bảo dù Offline Queue có gửi lại một lượt quét nhiều lần thì giỏ hàng vẫn chỉ cộng đúng 1 lần.\n"
        "Khi xe mất mạng nối lại, Backend tự đóng cảnh báo OFFLINE và gọi hàm _reconcile() để đồng bộ lại đúng trạng thái phiên từ CSDL."
    ),
    11: (
        "Sơ đồ trình tự này minh hoạ 2 kịch bản tương tác cốt lõi theo thời gian:\n"
        "- Phần A — Luồng mua hàng (Eventual Realtime): Khách hàng bấm bắt đầu phiên qua REST, Backend phát lệnh START_SESSION xuống xe. Khi khách quét mã, xe gửi MQTT scan, Backend lưu CSDL, tính cân nặng và phát ngay sự kiện CART_UPDATED qua WebSocket /ws để giao diện khách cập nhật tức thì mà không cần tải lại trang.\n"
        "- Phần B — Luồng khoá xe (Sync-over-Async): Khi Admin bấm khoá xe qua HTTP POST /lock, Backend ghi nhận lệnh trạng thái PENDING vào bảng cart_commands, phát MQTT LOCK_CART và giữ kết nối HTTP đợi bằng threading.Event tối đa 5 giây. Khi xe khoá xong và gửi MQTT ack, Backend cập nhật CSDL và trả ngay HTTP 200 OK cho Admin, hoặc trả 504 Timeout nếu xe không phản hồi."
    ),
    12: (
        "Chuyển sang tầng Backend, hệ thống sử dụng FastAPI chạy trên Uvicorn ASGI, tự động cung cấp tài liệu tương tác chuẩn OpenAPI 3.0.3 tại /docs và /redoc.\n"
        "Để xử lý đồng thời mà không xung đột dữ liệu, Backend phân tách rõ 4 đơn vị thực thi:\n"
        "1. Threadpool xử lý các request HTTP REST.\n"
        "2. 1 thread nền riêng cho MQTT Consumer xử lý tuần tự các gói tin đến — bảo đảm bản tin scan luôn được ghi trước khi telemetry tính cảnh báo lệch cân.\n"
        "3. 1 thread cho HeartbeatMonitor quét mỗi 2 giây.\n"
        "4. Event loop bất đồng bộ phục vụ WebSocket /ws.\n"
        "Ở bảng bên phải là 26 REST endpoints chia theo 7 nhóm nghiệp vụ, bao gồm cả endpoint GET /api/commands mới bổ sung để nhân viên tra cứu toàn bộ lịch sử lệnh điều khiển xe."
    ),
    13: (
        "Về nghiệp vụ cốt lõi, mỗi xe đẩy vận hành theo máy trạng thái 3 trạng thái: AVAILABLE (sẵn sàng) chuyển sang IN_USE khi có phiên mua sắm, và có thể bị chuyển sang LOCKED bởi Admin để chặn mọi thao tác quét và thanh toán.\n"
        "Nhóm cài đặt 3 quy tắc bảo toàn dữ liệu chặt chẽ:\n"
        "- Thứ nhất: Partial Unique Index ux_active_session_per_cart bảo đảm ở mức CSDL rằng một xe chỉ có duy nhất 1 phiên ACTIVE tại một thời điểm, chống race condition.\n"
        "- Thứ hai (Price Snapshot): Khi thêm sản phẩm vào giỏ, hệ thống chốt luôn đơn giá tại thời điểm đó vào cột unit_price của cart_items. Nếu Admin thay đổi giá trong danh mục sau đó, hoá đơn khách đang mua vẫn giữ nguyên giá lúc quét.\n"
        "- Thứ ba (Atomic Checkout): Toàn bộ bước chốt tiền, đóng phiên, trả xe về AVAILABLE và ghi chú cảnh báo còn tồn đọng được bọc trong một giao dịch db.tx() duy nhất — thành công toàn bộ hoặc rollback toàn bộ."
    ),
    14: (
        "Hệ thống giám sát bất thường (Alert Engine) tự động xử lý 3 loại cảnh báo:\n"
        "1. LOW_BATTERY: Kích hoạt ngay khi battery_percent < 20% và tự động chuyển sang RESOLVED khi pin được sạc lại >= 20%.\n"
        "2. WEIGHT_MISMATCH: Chỉ đánh giá khi xe đang IN_USE có phiên hoạt động và độ lệch tuyệt đối giữa cân thực tế với cân kỳ vọng lớn hơn 100g; tự đóng khi khách bỏ hàng dư ra hoặc hoàn tất checkout.\n"
        "3. CART_OFFLINE: Do HeartbeatMonitor kiểm tra định kỳ 2 giây một lần; nếu quá 15 giây không nhận được tín hiệu từ xe, hệ thống đánh dấu OFFLINE và mở cảnh báo.\n"
        "Để tránh spam hàng trăm bản ghi cảnh báo giống nhau mỗi khi xe gửi telemetry, CSDL dùng Partial Unique Index (cart_id, alert_type) WHERE status = 'ACTIVE' và phát sự kiện ALERT_TRIGGERED / ALERT_RESOLVED tức thì lên Dashboard."
    ),
    15: (
        "Kênh truyền tải realtime WebSocket đã được tích hợp trực tiếp vào FastAPI tại /ws trên cổng 8000 (gom chung cổng với REST API, rất thuận tiện khi cấu hình Docker hoặc Reverse Proxy), đồng thời vẫn giữ cổng 8081 cho tương thích ngược.\n"
        "Về bảo mật WebSocket: Client sau khi kết nối sẽ gửi gói tin AUTH chứa Bearer token trong payload thay vì đặt token lên URL (tránh bị lộ token trong log của máy chủ).\n"
        "Tại hàm hub.project(), hệ thống thực hiện lọc sự kiện theo từng vai trò như trong bảng: Nhân viên (Staff) nhận toàn bộ dữ liệu; Khách hàng chỉ nhận thông báo SCAN_REJECTED của đúng xe mình; còn người dùng ẩn danh chỉ thấy trạng thái xe đã che toàn bộ chi tiết giỏ hàng. Nếu mạng rớt WebSocket, Frontend tự kích hoạt cơ chế Fallback Polling 5 giây."
    ),
    16: (
        "Cơ sở dữ liệu gồm 7 bảng quan hệ chặt chẽ được thiết kế đồng bộ cho cả PostgreSQL 16 và SQLite thông qua lớp adapter Dual-Engine (backend/database/db.py):\n"
        "- Bảng trung tâm là smart_carts liên kết 1:N tới shopping_sessions, device_telemetry, alerts và bảng cart_commands vừa được bổ sung.\n"
        "- Bảng shopping_sessions liên kết 1:N tới cart_items với ràng buộc ON DELETE CASCADE và tham chiếu tới danh mục products.\n"
        "Adapter db.py tự động chuyển đổi placeholder ? sang %s và bổ sung RETURNING id khi chạy trên PostgreSQL 16 với driver psycopg 3. Nhờ bổ sung bảng cart_commands, toàn bộ lịch sử lệnh khoá/mở xe và trạng thái ACK được lưu trữ bền vững, không bị mất khi Backend khởi động lại."
    ),
    17: (
        "An toàn thông tin được thiết kế theo mô hình phòng thủ 3 lớp độc lập:\n"
        "- Lớp 1 — Ứng dụng & API: Băm mật khẩu bằng PBKDF2-HMAC-SHA256 (200.000 vòng) kèm salt ngẫu nhiên; token ký HMAC có thời hạn và ràng buộc chống IDOR; chống brute-force đăng nhập; chèn các HTTP Security Header như CSP, X-Frame-Options: DENY, no-store; và bảo vệ Simulator API bằng token.\n"
        "- Lớp 2 — Mạng & MQTT Broker: Mỗi xe có tài khoản riêng và danh sách ACL chỉ cho phép publish/subscribe đúng topic mang cart_id của mình; hỗ trợ mã hoá TLS 1.2+ trên cổng 8883.\n"
        "- Lớp 3 — Toàn vẹn gói tin: Từng payload được ký HMAC-SHA256 bằng khoá dẫn xuất riêng cho từng xe, kết hợp kiểm tra Clock Skew 300s và LRU Dedupe chống replay.\n"
        "Nhóm cũng ghi nhận minh bạch: trên môi trường dev cục bộ, HTTP/WS chưa bật TLS và cần bọc qua Reverse Proxy khi triển khai thực tế."
    ),
    18: (
        "Đây là 4 ảnh chụp màn hình thực tế thu được từ bộ kiểm thử trình duyệt tự động Playwright cho hành trình khách hàng:\n"
        "- Bước 1: Giao diện chọn xe trực quan; các xe đang IN_USE, LOCKED hoặc OFFLINE tự động bị vô hiệu hoá để tránh mở nhầm phiên.\n"
        "- Bước 2: Khi quét hàng, giao diện giỏ hàng cập nhật tức thì qua WebSocket với số lượng, đơn giá, thành tiền và cân nặng dự kiến.\n"
        "- Bước 3: Khi cân thực tế bị lệch quá 100g, banner cảnh báo lệch cân lập tức hiển thị ngay trên màn hình xe để khách kiểm tra lại.\n"
        "- Bước 4: Khách nhấn thanh toán, giao dịch hoàn tất qua db.tx(), hiển thị hoá đơn rõ ràng và giải phóng xe về trạng thái sẵn sàng."
    ),
    19: (
        "Còn đây là giao diện thực tế dành cho quản trị viên (Admin Dashboard):\n"
        "- Ở màn hình chính bên trái, quản trị viên theo dõi được ngay tổng số xe, số xe đang online, pin, cân nặng, thời điểm last_seen và bộ lọc trạng thái.\n"
        "- Khi có sự cố, thanh cảnh báo Realtime phía trên lập tức xuất hiện giúp điều hướng nhanh sang Trung tâm cảnh báo (ảnh trên bên phải) để lọc theo loại sự cố.\n"
        "- Khi bấm vào từng xe ở ảnh dưới bên phải, hệ thống vẽ trực tiếp biểu đồ SVG biến thiên pin và cân nặng theo lịch sử telemetry, kèm nút Khoá xe / Mở khoá xe khẩn cấp gửi lệnh xuống xe theo cơ chế ACK."
    ),
    20: (
        "Về triển khai, hệ thống cung cấp hai phương án gọn nhẹ:\n"
        "- Phương án 1 — Docker Compose: Gồm 4 service phối hợp đồng bộ là postgres (PostgreSQL 16 Alpine kèm volume postgres-data và healthcheck pg_isready), mqtt-broker (Mosquitto 2), backend (FastAPI build bằng Dockerfile multi-stage từ Node 22 sang Python 3.12-slim để tối ưu dung lượng image) và simulator.\n"
        "- Phương án 2 — Chạy trực tiếp trên Windows: Nhóm viết sẵn script scripts/run_local.ps1 giúp kiểm tra phụ thuộc, tự động giải phóng các cổng 8000/8081/8090 nếu bị chiếm dụng, khởi động tuần tự các tiến trình và tự dọn dẹp sạch sẽ khi nhấn Ctrl + C."
    ),
    21: (
        "Để chứng minh độ tin cậy của hệ thống, dự án thực hiện kiểm thử tự động đa tầng và đạt kết quả 131 / 131 bài test khả thi PASS (tỷ lệ đạt 100%, 0 Fail):\n"
        "- 47 Unit Tests PASS: Kiểm tra hợp đồng 6 topic MQTT, rule cảnh báo, tính nguyên tử checkout, price snapshot và cấu hình Wokwi (15 test C++ native được skip hợp lệ do máy Windows host không cài MinGW g++).\n"
        "- 64 Integration Tests PASS: Kiểm tra trọn vẹn luồng nghiệp vụ, đa xe CART_001..003 chạy đồng thời, phục hồi mất mạng với Offline Queue, lưu trữ lệnh cart_commands sống qua restart, bảo mật HMAC/ACL và chống replay.\n"
        "- 20 E2E Browser Tests PASS: Sử dụng Playwright điều khiển trình duyệt Chromium thật kiểm chứng giao diện Customer, Admin và Simulator.\n"
        "- Firmware Build: PlatformIO biên dịch thành công 100% cả 2 môi trường esp32dev_sim và esp32dev_sim_bridge."
    ),
    22: (
        "Tổng kết lại buổi trình bày:\n"
        "- Về kết quả đạt được: Hệ thống đã hoàn thiện đồng bộ cả kiến trúc Backend FastAPI, cơ sở dữ liệu Dual-Engine PostgreSQL 16 & SQLite, WebSocket gom cổng, MQTT bảo mật đa lớp, cơ chế chịu lỗi Offline Queue và đạt 131/131 bài kiểm thử tự động.\n"
        "- Về hạn chế trung thực: Đề tài hiện dừng ở mô phỏng phần mềm và firmware Wokwi, chưa tích hợp trực tiếp trên mạch ESP32 và cảm biến cân vật lý thật; giao thức HTTP/WS cục bộ cần bọc thêm TLS qua Reverse Proxy khi đưa ra môi trường thực tế.\n"
        "- Về hướng phát triển tiếp theo: Trong giai đoạn tới, hệ thống có thể lắp ráp hoàn chỉnh bộ phần cứng ESP32 + Load Cell HX711 + đầu đọc GM65 lên xe mẫu, tích hợp thêm Camera AI nhận diện hình ảnh món hàng để chống tráo nhãn mã vạch có cùng trọng lượng, và kết nối cổng thanh toán trực tuyến VNPay/MoMo.\n"
        "Bài thuyết trình của nhóm/em xin phép kết thúc tại đây. Em xin trân trọng cảm ơn quý thầy cô đã lắng nghe và rất mong nhận được câu hỏi, góp ý từ hội đồng."
    ),
}


def main():
    prs = pptx.Presentation(PPTX_PATH)
    for idx, slide in enumerate(prs.slides):
        ns = slide.notes_slide
        old_notes = ns.notes_text_frame.text.strip()
        # Tránh lặp nếu đã từng chèn
        marker = "=== LỜI THOẠI THUYẾT TRÌNH (ĐỌC TRỰC TIẾP) ==="
        if marker in old_notes:
            # Tách lấy phần ghi chú kỹ thuật cũ bên dưới
            tech_part = old_notes.split("=== GHI CHÚ KỸ THUẬT CHI TIẾT ===")[-1].strip()
        else:
            tech_part = old_notes

        speech = SPEECH_SCRIPTS.get(idx, "")
        combined = (
            f"{marker}\n\n"
            f"{speech}\n\n"
            f"=== GHI CHÚ KỸ THUẬT CHI TIẾT ===\n\n"
            f"{tech_part}"
        )
        ns.notes_text_frame.text = combined

    prs.save(PPTX_PATH)
    print(f"Da chen loi thoai thuyet trinh vao Speaker Notes cua ca {len(prs.slides)} slides trong {PPTX_PATH}")


if __name__ == "__main__":
    main()
