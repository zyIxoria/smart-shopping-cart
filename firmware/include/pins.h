// Sơ đồ chân ESP32 DevKit (30/38 chân). Đổi tại đây nếu đấu dây khác.
#pragma once

// Máy quét mã vạch UART (GM65/GM66/GM861): TX của module -> RX2 của ESP32.
#define PIN_SCANNER_RX   16          // UART2 RX  <- TX module
#define PIN_SCANNER_TX   17          // UART2 TX  -> RX module (không bắt buộc)
#define SCANNER_BAUD     9600        // mặc định GM65/GM66; GM861 cũng 9600

// Cân HX711 + load cell
#define PIN_HX711_DT     32
#define PIN_HX711_SCK    33

// OLED SSD1306 I2C 128x64
#define PIN_I2C_SDA      21
#define PIN_I2C_SCL      22

// Báo hiệu
#define PIN_BUZZER       25          // còi buzzer ACTIVE (HIGH = kêu)
#define PIN_LED_GREEN    26          // qua điện trở 220–330 Ω
#define PIN_LED_RED      27

// Nút bấm: nối chân với GND, dùng INPUT_PULLUP (nhấn = LOW)
#define PIN_BTN_MODE     13          // bấm: đổi chế độ quét ADD <-> REMOVE (cho đúng 1 lần quét)
#define PIN_BTN_TARE     14          // giữ 2 giây: về 0 cân (chỉ khi chưa có phiên mua)

// Đo pin qua cầu chia áp (ADC1 – KHÔNG dùng ADC2 vì xung đột Wi-Fi)
#define PIN_BATTERY_ADC  34
