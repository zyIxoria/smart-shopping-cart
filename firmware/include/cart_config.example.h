// Sao chép file này thành include/cart_config.h rồi sửa. cart_config.h đã nằm trong .gitignore (chứa mật khẩu Wi-Fi).
#pragma once

#define WIFI_SSID        "TEN_WIFI"
#define WIFI_PASS        "MAT_KHAU_WIFI"

// Địa chỉ IP của máy đang chạy MQTT broker (Mosquitto hoặc tools/dev_broker.py) trong CÙNG mạng LAN.
// KHÔNG dùng "localhost"/127.0.0.1: trên ESP32 đó là chính nó.
#define MQTT_HOST        "192.168.1.10"
#define MQTT_PORT        1883

// Mã xe – phải được đăng ký trước ở Backend (POST /api/carts hoặc cart có sẵn). Chỉ gồm [A-Za-z0-9_-], <= 32 ký tự.
#define CART_ID          "CART_004"

// --- Tuỳ chọn (có giá trị mặc định trong main.cpp) ---
// Số đếm HX711 trên mỗi gram. Hiệu chuẩn theo README (đặt vật nặng đã biết khối lượng). Có thể âm nếu đấu ngược dây.
#define HX711_COUNTS_PER_GRAM   420.0f
// Hệ số cầu chia áp đo pin: (R1+R2)/R2. 100k/100k -> 2.0
#define BATTERY_DIVIDER_RATIO   2.0f
// 0 = không có pin (cấp nguồn USB): luôn báo 100 %, tránh ADC để hở báo pin yếu giả.
#define BATTERY_ENABLED         1
#define OLED_I2C_ADDR           0x3C
