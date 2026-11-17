// Smart Cart – firmware ESP32 (Arduino). Nói chuyện với Backend qua MQTT theo docs/mqtt/MQTT_CONTRACT.md.
//
//  Phần cứng: máy quét UART (GM65/66/861), cân HX711, OLED SSD1306, còi + 2 LED, 2 nút, đo pin qua ADC.
//  Thanh toán KHÔNG làm trên phần cứng: xe chỉ quét/báo cân/pin/trạng thái, khách thanh toán trên màn hình web.
//
//  Toàn bộ logic quyết định nằm trong lib/cartcore (đã có unit test chạy trên PC). File này chỉ là "keo dán"
//  vào phần cứng và mạng; vòng lặp KHÔNG chặn (không delay) trừ lúc khởi động.
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>
#include <HX711.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <esp_system.h>
#include <time.h>

#include "cartcore.h"
#include "cartsec.h"
#include "pins.h"
// STANDALONE_MODE=1 (env esp32dev_standalone): chạy độc lập, KHÔNG dùng Wi-Fi/MQTT – để thử phần cứng trước khi liên kết hệ thống.
#ifndef STANDALONE_MODE
#define STANDALONE_MODE 0
#endif
// WOKWI_ONLINE=1 (env esp32dev_wokwi_online): chạy trong Wokwi, nối broker MQTT công cộng (xem include/wokwi_online.h).
#ifndef WOKWI_ONLINE
#define WOKWI_ONLINE 0
#endif
// SERIAL_BRIDGE=1 (env esp32dev_sim_bridge, luôn đi kèm STANDALONE_MODE=1): xe KHÔNG tự bắt đầu phiên, in mọi message dạng
// "[local] <topic> <json>" (kể cả heartbeat) và nhận lệnh Backend qua console "cmd <json>". Dùng với tools/wokwi_bridge.py
// (cầu nối Serial <-> MQTT) để firmware trong Wokwi liên kết hệ thống mà không cần Internet/broker công cộng.
#ifndef SERIAL_BRIDGE
#define SERIAL_BRIDGE 0
#endif
// Lưu ý: tên "cart_config.h" (không phải "config.h") vì framework ESP32 có sẵn nhiều file config.h khác và trình biên dịch sẽ nhặt nhầm.
#if STANDALONE_MODE
#define CART_ID "CART_DEMO"
#define WIFI_SSID ""
#define WIFI_PASS ""
#define MQTT_HOST "127.0.0.1"
#elif WOKWI_ONLINE
#include "wokwi_online.h"
#elif __has_include("cart_config.h")
#include "cart_config.h"
#else
#error "Thiếu include/cart_config.h – sao chép include/cart_config.example.h thành include/cart_config.h rồi điền Wi-Fi/MQTT (xem firmware/README.md), hoặc build env esp32dev_standalone / esp32dev_sim"
#endif

// Bí mật sinh bởi `python -m tools.provision` (MQTT_USER/MQTT_PASS, CART_KEY_HEX, MQTT_TLS + MQTT_CA_PEM). Không có file = chạy không bảo mật.
#if !STANDALONE_MODE && !WOKWI_ONLINE && __has_include("cart_secrets.h")
#include "cart_secrets.h"
#endif
#ifdef MQTT_TLS
#include <WiFiClientSecure.h>
#endif

#ifndef HX711_COUNTS_PER_GRAM
#define HX711_COUNTS_PER_GRAM 420.0f
#endif
#ifndef BATTERY_DIVIDER_RATIO
#define BATTERY_DIVIDER_RATIO 2.0f
#endif
#ifndef BATTERY_ENABLED
#define BATTERY_ENABLED 1
#endif
#ifndef OLED_I2C_ADDR
#define OLED_I2C_ADDR 0x3C
#endif
#ifndef MQTT_PORT
#ifdef MQTT_TLS
#define MQTT_PORT 8883
#else
#define MQTT_PORT 1883
#endif
#endif
#ifndef MAX_CLOCK_SKEW_S
#define MAX_CLOCK_SKEW_S 300                 // lệnh cũ hơn mức này bị bỏ (chống phát lại); khớp MAX_CLOCK_SKEW_S của Backend
#endif
#ifndef MQTT_TOPIC_ROOT
#define MQTT_TOPIC_ROOT "smartcart"      // phải trùng MQTT_TOPIC_ROOT của Backend
#endif

using namespace cartcore;

// ------------------------------------------------------------------ Hằng số (khớp contract)
static const uint32_t HEARTBEAT_MS = 5000;
static const uint32_t TELEMETRY_MS = 10000;
static const uint32_t SETTLE_AFTER_SCAN_MS = 3000;   // chờ khách bỏ hàng vào xe rồi mới báo cân (tránh WEIGHT_MISMATCH giả)
static const uint32_t WEIGHT_SAMPLE_MS = 100;        // HX711 ~10 SPS
static const uint32_t BATTERY_SAMPLE_MS = 1000;
static const uint32_t DISPLAY_MS = 250;
static const uint32_t WIFI_RETRY_MS = 15000;
static const uint32_t SPLASH_MS = 4000;              // màn hình "Cam on" sau khi kết thúc phiên
static const uint32_t FLASH_MS = 3000;               // thời gian giữ dòng thông báo ngắn

// ------------------------------------------------------------------ Đối tượng toàn cục
#ifdef MQTT_TLS
static WiFiClientSecure wifi_client;                  // TLS: kiểm tra chứng chỉ broker bằng MQTT_CA_PEM (chống broker giả)
#else
static WiFiClient wifi_client;
#endif
static PubSubClient mqtt(wifi_client);

// --- ký HMAC (khoá riêng của xe này, KHÔNG phải khoá chủ)
static uint8_t cart_key[32];
static bool have_key = false;
static bool key_error = false;                        // CART_KEY_HEX có nhưng sai định dạng -> không gửi gì (fail closed)
static uint32_t rejected_cmds = 0;                    // lệnh bị bỏ vì thiếu/sai chữ ký hoặc quá cũ
static HX711 scale;
static Adafruit_SSD1306 oled(128, 64, &Wire, -1);
static bool oled_ok = false;

static CartLogic logic;
static ScanMode scan_mode;
static LineAssembler line_asm(80);
static WeightFilter weight_filter(0.4f);
static LowBatteryMonitor low_batt;
static Button btn_mode, btn_tare;
static Backoff mqtt_backoff(500, 8000);

static Interval iv_heartbeat(HEARTBEAT_MS), iv_telemetry(TELEMETRY_MS), iv_weight(WEIGHT_SAMPLE_MS),
    iv_battery(BATTERY_SAMPLE_MS), iv_display(DISPLAY_MS);

static char topic_cmd[112], topic_scan[112], topic_event[112], topic_tele[112], topic_hb[112], topic_ack[112];

static Preferences prefs;
static float counts_per_gram = HX711_COUNTS_PER_GRAM;   // ghi đè bằng giá trị hiệu chuẩn lưu trong NVS (lệnh "cal")
static long tare_raw = 0;
static uint32_t scanner_bytes = 0;                       // đếm byte nhận từ máy quét (chẩn đoán đấu dây)
static int local_items = 0;                              // chỉ dùng ở chế độ độc lập
static int console_seq = 0;
static float sim_weight = -1;                            // >= 0: ghi đè số cân (giả lập, lệnh "weight")
static int sim_battery = -1;                             // >= 0: ghi đè % pin (giả lập, lệnh "battery")
static float weight_g = 0;
static int battery_pct = 100;
static bool low_battery = false;

static bool ntp_started = false;
static uint32_t wifi_last_try = 0;
static uint32_t mqtt_next_try = 0;
static bool was_connected = false;

static bool tele_pending = false;                    // có lịch gửi telemetry sau khi quét
static uint32_t tele_at = 0;

static char flash_line[24] = "";                     // dòng thông báo ngắn trên OLED
static uint32_t flash_until = 0;
static uint32_t splash_until = 0;                    // màn hình cảm ơn

// ------------------------------------------------------------------ Còi (không chặn)
// Mảng xen kẽ: kêu, nghỉ, kêu, ... (ms), kết thúc bằng 0.
static const uint16_t PAT_OK[] = {70, 0};
static const uint16_t PAT_ERROR[] = {120, 80, 120, 80, 120, 0};
static const uint16_t PAT_LOCK[] = {450, 0};
static const uint16_t PAT_UNLOCK[] = {70, 60, 70, 0};
static const uint16_t PAT_THANKS[] = {80, 60, 80, 60, 220, 0};
static const uint16_t PAT_MODE[] = {40, 0};
static const uint16_t* pat = nullptr;
static int pat_idx = 0;
static uint32_t pat_next = 0;

// Chỉ số 0 = kêu, 1 = nghỉ, 2 = kêu, ...; gặp phần tử 0 là kết thúc.
static void beep(const uint16_t* p) {
  pat = p;
  digitalWrite(PIN_BUZZER, HIGH);
  pat_next = millis() + p[0];
  pat_idx = 1;
}

static void buzzer_update(uint32_t now) {
  if (!pat || (int32_t)(now - pat_next) < 0) return;
  uint16_t d = pat[pat_idx];
  if (d == 0) {                                       // hết mẫu
    digitalWrite(PIN_BUZZER, LOW);
    pat = nullptr;
    return;
  }
  digitalWrite(PIN_BUZZER, (pat_idx % 2 == 0) ? HIGH : LOW);
  pat_next = now + d;
  pat_idx++;
}

// ------------------------------------------------------------------ Tiện ích
__attribute__((unused)) static bool wifi_ok() { return WiFi.status() == WL_CONNECTED; }
__attribute__((unused)) static bool time_ok() { return time_valid((long long)time(nullptr)); }
// Chỉ coi là "sẵn sàng gửi" khi có Wi-Fi + MQTT + đồng hồ NTP (timestamp lệch > 300 s sẽ bị Backend loại).
#if STANDALONE_MODE
static bool net_ready() { return true; }              // không cần mạng: luôn "sẵn sàng" để thử phần cứng
#else
static bool net_ready() { return wifi_ok() && mqtt.connected() && time_ok(); }
#endif

static void flash(const char* text) {
  strncpy(flash_line, text, sizeof flash_line - 1);
  flash_line[sizeof flash_line - 1] = 0;
  flash_until = millis() + FLASH_MS;
}

static bool make_meta(char* id, char* ts, Meta* m) {
#if STANDALONE_MODE
  strcpy(id, "00000000-0000-4000-8000-000000000000");
  strcpy(ts, "1970-01-01T00:00:00Z");
  m->message_id = id;
  m->cart_id = CART_ID;
  m->timestamp = ts;
  m->key = nullptr;
  return true;
#endif
  if (!time_ok()) return false;
  uint8_t r[16];
  esp_fill_random(r, sizeof r);
  uuid4(r, id);
  iso8601_utc((long long)time(nullptr), ts);
  m->message_id = id;
  m->cart_id = CART_ID;
  m->timestamp = ts;
  m->key = have_key ? cart_key : nullptr;          // có khoá => build_* tự thêm "sig"
  return !key_error;
}

static bool publish_json(const char* topic, const char* payload, int len) {
  if (len <= 0) return false;
#if STANDALONE_MODE
  Serial.printf("[local] %s %s\n", topic, payload);   // in ra thay vì gửi: xem được đúng message sẽ gửi khi liên kết
  return true;
#endif
  if (!mqtt.connected()) return false;
  return mqtt.publish(topic, (const uint8_t*)payload, (unsigned int)len, false);
}

static char msg_buf[640];

__attribute__((unused)) static bool send_heartbeat() {
  char id[37], ts[21];
  Meta m;
  if (!make_meta(id, ts, &m)) return false;
  int n = build_heartbeat(msg_buf, sizeof msg_buf, m, millis() / 1000, status_name(logic.status()));
  return publish_json(topic_hb, msg_buf, n);
}

static bool send_telemetry() {
  char id[37], ts[21];
  Meta m;
  if (!make_meta(id, ts, &m)) return false;
  int n = build_telemetry(msg_buf, sizeof msg_buf, m, weight_g, battery_pct, status_name(logic.status()),
                          wifi_ok() || SERIAL_BRIDGE, mqtt.connected() || SERIAL_BRIDGE);
  return publish_json(topic_tele, msg_buf, n);
}

static bool send_event(const char* type, const char* desc) {
  char id[37], ts[21];
  Meta m;
  if (!make_meta(id, ts, &m)) return false;
  int n = build_event(msg_buf, sizeof msg_buf, m, type, desc);
  return publish_json(topic_event, msg_buf, n);
}

static bool send_ack(const char* command_id, bool ok, const char* message) {
  char id[37], ts[21];
  Meta m;
  if (!make_meta(id, ts, &m)) return false;
  int n = build_ack(msg_buf, sizeof msg_buf, m, command_id, ok ? "OK" : "FAILED", message);
  return publish_json(topic_ack, msg_buf, n);
}

// ------------------------------------------------------------------ Lệnh (từ Backend qua MQTT hoặc từ console Serial)
static void apply_command(const Command& c) {
  AckInfo a = logic.handle(c);
  Serial.printf("[cmd] %s id=%s -> %s%s\n", c.type, c.command_id, a.ok ? "OK" : "FAILED", a.replay ? " (lap lai)" : "");
  send_ack(c.command_id, a.ok, a.message);           // luôn ACK, kể cả lệnh lặp (ACK trước đó có thể bị mất)

  switch (a.effect) {
    case EFFECT_LOCKED:
      beep(PAT_LOCK);
      flash("XE BI KHOA");
      send_event("CART_LOCKED", "Xe đã bị khoá theo lệnh Backend");
      break;
    case EFFECT_UNLOCKED:
      beep(PAT_UNLOCK);
      flash("DA MO KHOA");
      send_event("CART_UNLOCKED", "Xe đã được mở khoá");
      break;
    case EFFECT_SESSION_STARTED:
      beep(PAT_OK);
      flash("BAT DAU MUA HANG");
      scan_mode = ScanMode();
      local_items = 0;
      break;
    case EFFECT_SESSION_ENDED:
      beep(PAT_THANKS);
      splash_until = millis() + SPLASH_MS;
      scan_mode = ScanMode();
      break;
    case EFFECT_NONE:
      break;
  }
  iv_telemetry.fire_next();                           // báo trạng thái mới ngay
  iv_heartbeat.fire_next();
}

// Phân tích + thực hiện một payload lệnh JSON (từ MQTT hoặc từ console "cmd <json>" của cầu nối Serial).
static void handle_command_payload(const char* json) {
  Command c;
  if (!parse_command(json, CART_ID, &c)) {
    Serial.println("[cmd] payload khong hop le, bo qua");
    return;
  }
  apply_command(c);
}

__attribute__((unused)) static void on_mqtt_message(char* topic, uint8_t* payload, unsigned int length) {
  if (strcmp(topic, topic_cmd) != 0) return;
  static char buf[512];
  if (length == 0 || length >= sizeof buf) {
    Serial.printf("[cmd] bo qua payload %u byte\n", length);
    return;
  }
  memcpy(buf, payload, length);                      // sao chép trước: publish bên dưới dùng lại buffer của PubSubClient
  buf[length] = 0;
  if (have_key) {                                    // chỉ nghe lệnh do Backend (người giữ khoá chủ) ký
    VerifyResult v = verify_signed_payload(buf, "command", cart_key);
    char ts[32];
    const char* why = v == VERIFY_MISSING ? "khong ky" : v != VERIFY_OK ? "sai chu ky" : nullptr;
    if (!why && time_ok() && (!json_get_string(buf, "timestamp", ts, sizeof ts) || !timestamp_fresh(ts, (long long)time(nullptr), MAX_CLOCK_SKEW_S)))
      why = "qua cu";
    if (why) {
      rejected_cmds++;
      Serial.printf("[sec] bo lenh (%s), tong %u\n", why, (unsigned)rejected_cmds);
      return;
    }
  }
  handle_command_payload(buf);
}

// ------------------------------------------------------------------ Mạng
__attribute__((unused)) static void ensure_wifi(uint32_t now) {
  if (wifi_ok()) {
    if (!ntp_started) {
      configTime(0, 0, "pool.ntp.org", "time.google.com", "time.cloudflare.com");
      ntp_started = true;
      Serial.printf("[wifi] da ket noi, IP=%s\n", WiFi.localIP().toString().c_str());
    }
    return;
  }
  if (now - wifi_last_try >= WIFI_RETRY_MS || wifi_last_try == 0) {
    wifi_last_try = now ? now : 1;
    Serial.println("[wifi] dang ket noi...");
    WiFi.disconnect();
    WiFi.begin(WIFI_SSID, WIFI_PASS);
  }
}

__attribute__((unused)) static void ensure_mqtt(uint32_t now) {
  if (mqtt.connected()) {
    if (!was_connected) {
      was_connected = true;
      mqtt_backoff.reset();
    }
    return;
  }
  if (was_connected) {
    was_connected = false;
    Serial.println("[mqtt] mat ket noi");
  }
  if (!wifi_ok() || !time_ok()) return;               // cần Wi-Fi và đồng hồ trước
  if ((int32_t)(now - mqtt_next_try) < 0) return;

  char client_id[48];
  snprintf(client_id, sizeof client_id, "cart-%s-%04x", CART_ID, (unsigned)(esp_random() & 0xFFFF));
  Serial.printf("[mqtt] ket noi %s:%d ...\n", MQTT_HOST, MQTT_PORT);
#ifdef MQTT_USER
  bool connected_ok = mqtt.connect(client_id, MQTT_USER, MQTT_PASS);
#else
  bool connected_ok = mqtt.connect(client_id);
#endif
  if (connected_ok) {
    mqtt.subscribe(topic_cmd);                        // subscribe lại sau MỖI lần kết nối (clean session)
    Serial.println("[mqtt] da ket noi + subscribe");
    was_connected = true;
    mqtt_backoff.reset();
    iv_heartbeat.fire_next();                         // gửi heartbeat/telemetry ngay để Backend thấy xe ONLINE
    iv_telemetry.fire_next();
    flash("DA KET NOI");
  } else {
    uint32_t wait = mqtt_backoff.next();
    mqtt_next_try = now + wait;
    int rc = mqtt.state();
    Serial.printf("[mqtt] that bai rc=%d%s, thu lai sau %u ms\n", rc,
                  rc == 4 ? " (sai MQTT_USER/MQTT_PASS)" : rc == 5 ? " (khong du quyen – kiem tra ACL)" :
                  rc == -2 ? " (khong noi duoc / loi TLS: kiem tra CA, gio he thong, dia chi trong chung chi)" : "",
                  (unsigned)wait);
  }
}

// ------------------------------------------------------------------ Máy quét mã vạch
static void handle_barcode_line(const char* raw, size_t len) {
  char code[70];
  if (!normalize_barcode(raw, len, code, sizeof code)) {
    Serial.printf("[scan] ma khong hop le (%u byte)\n", (unsigned)len);
    beep(PAT_ERROR);
    flash("MA KHONG HOP LE");
    return;
  }
  CartLogic::ScanDecision d = logic.can_scan(net_ready());
  if (d != CartLogic::SCAN_OK) {
    beep(PAT_ERROR);
    switch (d) {
      case CartLogic::SCAN_LOCKED:
        flash("XE BI KHOA");
        send_event("SCAN_REJECTED", "Quét bị từ chối: xe đang bị khoá");
        break;
      case CartLogic::SCAN_NO_SESSION:
        flash("CHUA CO PHIEN");
        send_event("SCAN_REJECTED", "Quét bị từ chối: chưa có phiên mua hàng");
        break;
      default:
        flash("MAT KET NOI");                        // không gửi được -> báo khách quét lại
        break;
    }
    Serial.printf("[scan] tu choi %s (%d)\n", code, (int)d);
    return;
  }

  char id[37], ts[21], scan_id[37];
  Meta m;
  if (!make_meta(id, ts, &m)) return;
  uint8_t r[16];
  esp_fill_random(r, sizeof r);
  uuid4(r, scan_id);
  const char* action = scan_mode.action();
  int n = build_scan(msg_buf, sizeof msg_buf, m, scan_id, code, action);
  if (publish_json(topic_scan, msg_buf, n)) {
    Serial.printf("[scan] %s %s\n", action, code);
    beep(PAT_OK);
    char line[24];
    snprintf(line, sizeof line, "%s %.15s", scan_mode.is_remove() ? "BO" : "+", code);
    flash(line);
    local_items += scan_mode.is_remove() ? (local_items > 0 ? -1 : 0) : 1;
    scan_mode.after_scan();
    tele_pending = true;                              // báo cân sau khi khách bỏ/lấy hàng
    tele_at = millis() + SETTLE_AFTER_SCAN_MS;
  } else {
    beep(PAT_ERROR);
    flash("GUI LOI, QUET LAI");
  }
}

static void scanner_poll(uint32_t now) {
  while (Serial2.available() > 0) {
    int b = Serial2.read();
    if (b < 0) break;
    scanner_bytes++;
    if (line_asm.feed((uint8_t)b, now)) {
      char line[100];
      size_t n = line_asm.take(line, sizeof line);
      handle_barcode_line(line, n);
    }
  }
  if (line_asm.poll_timeout(now)) {                   // module không gửi CR/LF -> chốt dòng khi im lặng
    char line[100];
    size_t n = line_asm.take(line, sizeof line);
    handle_barcode_line(line, n);
  }
}

// ------------------------------------------------------------------ Cân & pin
static void tare_now() {
  if (!scale.is_ready()) {
    delay(200);
  }
  tare_raw = scale.read_average(10);
  weight_filter.reset();
  weight_g = 0;
  Serial.printf("[scale] tare raw=%ld\n", tare_raw);
}

static void weight_poll() {
  if (sim_weight >= 0) { weight_g = sim_weight; return; }   // giả lập: bỏ qua cảm biến
  if (!scale.is_ready()) return;
  long raw = scale.read();
  weight_g = weight_filter.update(raw_to_grams(raw, tare_raw, counts_per_gram));
  if (sim_weight >= 0) weight_g = sim_weight;
}

static void battery_poll() {
#if BATTERY_ENABLED
  uint32_t sum = 0;
  for (int i = 0; i < 16; i++) sum += analogReadMilliVolts(PIN_BATTERY_ADC);
  float pin_mv = sum / 16.0f;
  battery_pct = battery_percent(battery_mv_from_pin(pin_mv, BATTERY_DIVIDER_RATIO));
#else
  battery_pct = 100;
#endif
  if (sim_battery >= 0) battery_pct = sim_battery;
  low_battery = low_batt.update(battery_pct);
}

// ------------------------------------------------------------------ Nút bấm
static void buttons_poll(uint32_t now) {
  if (btn_mode.update(digitalRead(PIN_BTN_MODE) == LOW, now) == Button::SHORT_PRESS) {
    scan_mode.toggle();
    beep(PAT_MODE);
    flash(scan_mode.is_remove() ? "CHE DO: BO HANG" : "CHE DO: THEM");
  }
  if (btn_tare.update(digitalRead(PIN_BTN_TARE) == LOW, now) == Button::LONG_PRESS) {
    if (logic.has_session()) {                        // đang mua hàng: không cho zero cân (tránh gian lận/lệch)
      beep(PAT_ERROR);
      flash("DANG CO PHIEN");
    } else {
      tare_now();
      beep(PAT_OK);
      flash("DA VE 0 CAN");
    }
  }
}

// ------------------------------------------------------------------ LED & màn hình
static void leds_update(uint32_t now) {
  bool blink_fast = (now / 250) % 2;
  bool blink_slow = (now / 500) % 2;
  bool green = false, red = false;
  if (logic.status() == LOCKED) {
    red = true;
  } else if (!net_ready()) {
    green = blink_fast;                               // đang kết nối
  } else {
    green = true;
    if (low_battery) red = blink_slow;
  }
  digitalWrite(PIN_LED_GREEN, green);
  digitalWrite(PIN_LED_RED, red);
}

static void display_update(uint32_t now) {
  if (!oled_ok) return;
  oled.clearDisplay();
  oled.setTextColor(SSD1306_WHITE);

  if ((int32_t)(splash_until - now) > 0) {            // sau END_SESSION
    oled.setTextSize(2);
    oled.setCursor(8, 10);
    oled.print("CAM ON!");
    oled.setTextSize(1);
    oled.setCursor(8, 40);
    oled.print("Hen gap lai");
    oled.display();
    return;
  }

  oled.setTextSize(1);
  oled.setCursor(0, 0);
  oled.printf("%s  %s", CART_ID, status_name(logic.status()));
  oled.setCursor(0, 11);
#if STANDALONE_MODE
  oled.printf("DOC LAP  hang:%d", local_items);
#else
  oled.printf("WiFi:%s MQTT:%s", wifi_ok() ? "OK" : "--", mqtt.connected() ? "OK" : "--");
#endif
  oled.setCursor(0, 22);
  oled.printf("Can: %.0f g", weight_g);
  oled.setCursor(0, 33);
  oled.printf("Pin: %d%%%s", battery_pct, low_battery ? " PIN YEU!" : "");
  oled.setCursor(0, 44);
  if (logic.has_session()) oled.printf("Phien #%ld  [%s]", logic.session_id(), scan_mode.is_remove() ? "BO" : "THEM");
  else oled.print("Chua co phien");
  oled.setCursor(0, 55);
  if ((int32_t)(flash_until - now) > 0) oled.print(flash_line);
  else if (!time_ok() && wifi_ok()) oled.print("Dang dong bo gio...");
  else if (logic.status() == LOCKED) oled.print("XE BI KHOA");
  else oled.print("San sang quet");
  oled.display();
}

// ------------------------------------------------------------------ Tự kiểm tra & console Serial
static void self_test() {
  Serial.println("\n=== SELF TEST ===");
  Wire.beginTransmission(OLED_I2C_ADDR);
  Serial.printf("OLED  @0x%02X : %s\n", OLED_I2C_ADDR, Wire.endTransmission() == 0 ? "OK" : "KHONG THAY (kiem tra SDA/SCL/dia chi)");
  uint32_t t0 = millis();
  while (!scale.is_ready() && millis() - t0 < 1000) delay(10);
  if (scale.is_ready()) Serial.printf("HX711        : OK (raw=%ld, tare=%ld, weight=%.1f g)\n", scale.read(), tare_raw, weight_g);
  else Serial.println("HX711        : KHONG PHAN HOI (kiem tra DT/SCK/nguon)");
#if BATTERY_ENABLED
  float mv = analogReadMilliVolts(PIN_BATTERY_ADC) * BATTERY_DIVIDER_RATIO;
  Serial.printf("Pin          : %.0f mV tren pin => %d %% (neu dung USB khong pin: dat BATTERY_ENABLED 0)\n", mv, battery_percent(mv));
#else
  Serial.println("Pin          : tat (BATTERY_ENABLED 0)");
#endif
  Serial.printf("May quet UART: da nhan %u byte (quet thu 1 ma vach de kiem tra)\n", (unsigned)scanner_bytes);
  Serial.println("LED/coi      : nhin va nghe LED xanh, LED do, coi...");
  digitalWrite(PIN_LED_GREEN, HIGH); delay(200); digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_RED, HIGH); delay(200); digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_BUZZER, HIGH); delay(80); digitalWrite(PIN_BUZZER, LOW);
  Serial.println("Nut          : bam MODE / giu TARE de thu (xem log)");
  Serial.println("=================");
}

static void print_help() {
  Serial.println("Lenh console: help | status | tare | cal <gram> | selftest | scan <ma> | start | end | lock | unlock");
  Serial.println("Gia lap (khi chua co linh kien): weight <gram|auto> | battery <phan_tram|auto>");
  Serial.println("  cal 1000 : tare luc xe TRONG, dat vat 1000 g len can, roi go lenh de luu he so (luu vao NVS)");
}

static void print_status() {
  Serial.printf("cart=%s trang_thai=%s phien=%ld can=%.1f g pin=%d%% he_so=%.3f scanner_bytes=%u\n", CART_ID,
                status_name(logic.status()), logic.has_session() ? logic.session_id() : -1L, weight_g, battery_pct,
                counts_per_gram, (unsigned)scanner_bytes);
#if STANDALONE_MODE
  Serial.printf("che do doc lap, so mon: %d\n", local_items);
#else
  Serial.printf("bao mat: ky HMAC=%s dang nhap MQTT=%s TLS=%s lenh bi bo=%u\n", have_key ? "BAT" : "tat",
#ifdef MQTT_USER
                "co",
#else
                "khong",
#endif
#ifdef MQTT_TLS
                "BAT",
#else
                "tat",
#endif
                (unsigned)rejected_cmds);
  Serial.printf("wifi=%s mqtt=%s ntp=%s\n", wifi_ok() ? "OK" : "--", mqtt.connected() ? "OK" : "--", time_ok() ? "OK" : "--");
#endif
}

static void console_command(const ConsoleCmd& c) {
  Command cmd;
  memset(&cmd, 0, sizeof cmd);
  snprintf(cmd.command_id, sizeof cmd.command_id, "console-%d", ++console_seq);
  switch (c.type) {
    case ConsoleCmd::HELP: print_help(); break;
    case ConsoleCmd::STATUS: print_status(); break;
    case ConsoleCmd::SELFTEST: self_test(); break;
    case ConsoleCmd::SCAN: handle_barcode_line(c.arg, strlen(c.arg)); break;
    case ConsoleCmd::TARE:
      if (logic.has_session()) Serial.println("tu choi: dang co phien mua hang (go 'end' truoc)");
      else { tare_now(); Serial.println("da ve 0"); }
      break;
    case ConsoleCmd::CAL: {
      long loaded = scale.read_average(10);
      float cpg = calibration_from_samples(tare_raw, loaded, c.num);
      if (cpg == 0.0f) {
        Serial.println("loi: so doc gan nhu khong doi – hay tare luc xe trong, roi dat vat nang len can truoc khi go 'cal'");
      } else {
        counts_per_gram = cpg;
        prefs.putFloat("cpg", cpg);
        weight_filter.reset();
        Serial.printf("da hieu chuan: %.3f dem/gram (raw trong=%ld, raw co vat=%ld) – da luu vao NVS\n", cpg, tare_raw, loaded);
        flash("DA HIEU CHUAN");
        beep(PAT_OK);
      }
      break;
    }
    case ConsoleCmd::START: strcpy(cmd.type, "START_SESSION"); cmd.session_id = logic.has_session() ? logic.session_id() : 1000 + console_seq; cmd.has_session_id = true; apply_command(cmd); break;
    case ConsoleCmd::END: strcpy(cmd.type, "END_SESSION"); apply_command(cmd); break;
    case ConsoleCmd::LOCK: strcpy(cmd.type, "LOCK_CART"); apply_command(cmd); break;
    case ConsoleCmd::UNLOCK: strcpy(cmd.type, "UNLOCK_CART"); apply_command(cmd); break;
    case ConsoleCmd::SIM_WEIGHT:
      sim_weight = c.num;
      if (sim_weight >= 0) Serial.printf("gia lap can = %.0f g (go 'weight auto' de dung cam bien that)\n", sim_weight);
      else Serial.println("da dung lai cam bien can that");
      iv_telemetry.fire_next();
      break;
    case ConsoleCmd::SIM_BATTERY:
      sim_battery = c.num < 0 ? -1 : (int)(c.num + 0.5f);
      if (sim_battery >= 0) Serial.printf("gia lap pin = %d %%\n", sim_battery);
      else Serial.println("da dung lai do pin that");
      battery_poll();
      iv_telemetry.fire_next();
      break;
    case ConsoleCmd::UNKNOWN: Serial.println("lenh khong hop le – go 'help'"); break;
    case ConsoleCmd::NONE: break;
  }
}

static void console_poll() {
  static char line[600];                              // đủ cho "cmd <json lệnh>" (~250 ký tự)
  static size_t n = 0;
  while (Serial.available() > 0) {
    int ch = Serial.read();
    if (ch < 0) break;
    if (ch == '\n' || ch == '\r') {
      if (n > 0) {
        line[n] = 0;
        if (strncmp(line, "cmd {", 5) == 0) handle_command_payload(line + 4);   // lệnh Backend do cầu nối chuyển vào
        else console_command(parse_console(line));
        n = 0;
      }
    } else if (n + 1 < sizeof line) {
      line[n++] = (char)ch;
    } else {
      n = 0;                                          // dòng quá dài: bỏ
    }
  }
}

// ------------------------------------------------------------------ setup / loop
void setup() {
  Serial.setRxBufferSize(1024);                        // phải gọi TRƯỚC begin(): dòng "cmd {json}" của cầu nối dài ~250 byte
  Serial.begin(115200);
  Serial.printf("\n[boot] Smart Cart firmware, cart=%s\n", CART_ID);

  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BTN_MODE, INPUT_PULLUP);
  pinMode(PIN_BTN_TARE, INPUT_PULLUP);
  digitalWrite(PIN_BUZZER, LOW);
#if BATTERY_ENABLED
  analogSetPinAttenuation(PIN_BATTERY_ADC, ADC_11db);   // đo tới ~3.1 V tại chân
#endif

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.setClock(400000);
  oled_ok = oled.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR);
  if (!oled_ok) Serial.println("[oled] khong tim thay man hinh, tiep tuc khong co OLED");
  if (oled_ok) {
    oled.clearDisplay();
    oled.setTextColor(SSD1306_WHITE);
    oled.setTextSize(1);
    oled.setCursor(0, 0);
    oled.println("Smart Cart");
    oled.println(CART_ID);
    oled.println("Khoi dong...");
    oled.display();
  }

  Serial2.begin(SCANNER_BAUD, SERIAL_8N1, PIN_SCANNER_RX, PIN_SCANNER_TX);

  prefs.begin("cart", false);
  counts_per_gram = prefs.getFloat("cpg", HX711_COUNTS_PER_GRAM);   // hệ số hiệu chuẩn đã lưu (nếu có)
  Serial.printf("[scale] he so %.3f dem/gram%s\n", counts_per_gram, prefs.isKey("cpg") ? " (da hieu chuan)" : " (mac dinh)");

  scale.begin(PIN_HX711_DT, PIN_HX711_SCK);
  tare_now();                                          // xe phải TRỐNG khi bật nguồn

  snprintf(topic_cmd, sizeof topic_cmd, "%s/%s/command", MQTT_TOPIC_ROOT, CART_ID);
  snprintf(topic_scan, sizeof topic_scan, "%s/%s/scan", MQTT_TOPIC_ROOT, CART_ID);
  snprintf(topic_event, sizeof topic_event, "%s/%s/event", MQTT_TOPIC_ROOT, CART_ID);
  snprintf(topic_tele, sizeof topic_tele, "%s/%s/telemetry", MQTT_TOPIC_ROOT, CART_ID);
  snprintf(topic_hb, sizeof topic_hb, "%s/%s/heartbeat", MQTT_TOPIC_ROOT, CART_ID);
  snprintf(topic_ack, sizeof topic_ack, "%s/%s/ack", MQTT_TOPIC_ROOT, CART_ID);

#ifdef CART_KEY_HEX
  have_key = hex_decode(CART_KEY_HEX, cart_key, 32);
  key_error = !have_key;
  if (key_error) Serial.println("[sec] LOI: CART_KEY_HEX phai la 64 ky tu hex – xe se KHONG gui gi cho den khi sua");
#endif
#ifdef SECRETS_CART_ID
  if (strcmp(SECRETS_CART_ID, CART_ID) != 0) {        // khoá/mật khẩu sinh cho xe khác -> Backend sẽ từ chối mọi gói
    key_error = true;
    Serial.printf("[sec] LOI: cart_secrets.h la cua %s nhung CART_ID=%s – xe se KHONG gui gi\n", SECRETS_CART_ID, CART_ID);
  }
#endif
#if !STANDALONE_MODE
#ifdef MQTT_TLS
  wifi_client.setCACert(MQTT_CA_PEM);
  wifi_client.setTimeout(3);
#endif
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(1024);                            // mặc định 256 B là không đủ cho envelope
  mqtt.setKeepAlive(30);
  mqtt.setSocketTimeout(3);                            // connect() không treo vòng lặp quá lâu
  mqtt.setCallback(on_mqtt_message);

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
#endif
  battery_poll();
  self_test();
  print_help();
#if SERIAL_BRIDGE
  Serial.println("[mode] CAU NOI SERIAL: cho lenh tu Backend qua tools/wokwi_bridge.py (khong tu bat dau phien).");
#elif STANDALONE_MODE
  Serial.println("[mode] DOC LAP: khong Wi-Fi/MQTT. Tu dong bat dau phien mua hang noi bo.");
  Command start;
  memset(&start, 0, sizeof start);
  strcpy(start.command_id, "standalone-start");
  strcpy(start.type, "START_SESSION");
  start.session_id = 1;
  start.has_session_id = true;
  apply_command(start);
#endif
  beep(PAT_OK);
}

void loop() {
  uint32_t now = millis();

#if !STANDALONE_MODE
  ensure_wifi(now);
  ensure_mqtt(now);
  mqtt.loop();
#endif

  console_poll();
  scanner_poll(now);
  buttons_poll(now);
  if (iv_weight.due(now)) weight_poll();
  if (iv_battery.due(now)) battery_poll();

  if (net_ready()) {
#if !STANDALONE_MODE || SERIAL_BRIDGE
    if (iv_heartbeat.due(now)) send_heartbeat();
#endif
    bool post_scan = tele_pending && (int32_t)(now - tele_at) >= 0;
    if (iv_telemetry.due(now) || post_scan) {
      send_telemetry();
      tele_pending = false;
      iv_telemetry.reset(now);
    }
  }

  buzzer_update(now);
  leds_update(now);
  if (iv_display.due(now)) display_update(now);
}
