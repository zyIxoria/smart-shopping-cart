// Cấu hình cho env esp32dev_wokwi_online: firmware chạy TRONG Wokwi, nối Internet qua Wi-Fi ảo "Wokwi-GUEST"
// tới MQTT broker CÔNG CỘNG. Backend trên máy bạn nối cùng broker + cùng MQTT_TOPIC_ROOT.
//
// QUAN TRỌNG: broker công cộng KHÔNG có mật khẩu. Hai giá trị dưới đây là "bí mật" duy nhất giữ cho tin nhắn của bạn
// không lẫn với người khác – hãy ĐỔI thành chuỗi ngẫu nhiên của riêng bạn (a–z, 0–9, '_' '-') và dùng ĐÚNG cùng giá trị
// ở Backend (MQTT_TOPIC_ROOT, và mã xe khi đăng ký). Chỉ dùng cho dữ liệu demo.
#pragma once

#define WIFI_SSID        "Wokwi-GUEST"
#define WIFI_PASS        ""
#define MQTT_HOST        "broker.hivemq.com"      // hoặc broker.emqx.io / test.mosquitto.org (cổng 1883, không TLS)
#define MQTT_PORT        1883
#define MQTT_TOPIC_ROOT  "smartcart-msgozlq5o6"
#define CART_ID          "CART_001"
