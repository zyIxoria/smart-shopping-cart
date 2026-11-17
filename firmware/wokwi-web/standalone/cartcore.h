// cartcore – logic thuần C++ của firmware Smart Cart (KHÔNG phụ thuộc Arduino/ESP32).
// Nhờ đó biên dịch và kiểm thử được trên máy tính (g++ / `pio test -e native`) và kiểm tra chéo
// với contract MQTT của Backend (docs/mqtt/MQTT_CONTRACT.md).
#pragma once
#include <stddef.h>
#include <stdint.h>

namespace cartcore {

// ----------------------------------------------------------------- JSON tối giản
// Duyệt đúng cú pháp chuỗi nên không nhầm "key" nằm trong giá trị chuỗi. Lấy lần xuất hiện đầu tiên
// của key ở bất kỳ độ sâu nào (đủ cho envelope của contract: các key không trùng nhau).
bool json_get_string(const char* json, const char* key, char* out, size_t out_size);
bool json_get_long(const char* json, const char* key, long* out);   // chỉ số nguyên; null/chuỗi -> false
bool json_is_null(const char* json, const char* key);               // key có và giá trị là null

size_t json_escape(const char* in, char* out, size_t out_size);     // trả độ dài, 0 nếu tràn

// ----------------------------------------------------------------- Thời gian & ID
bool time_valid(long long epoch_s);                                  // đã đồng bộ NTP chưa (> 2023-11)
void iso8601_utc(long long epoch_s, char out[21]);                   // "2026-11-07T10:30:00Z"
void uuid4(const uint8_t random16[16], char out[37]);                // UUID v4 từ 16 byte ngẫu nhiên

// ----------------------------------------------------------------- Build message (envelope + data)
// Trả độ dài chuỗi JSON, hoặc -1 nếu buffer quá nhỏ.
// key != nullptr (32 byte): message được ký HMAC-SHA256, thêm trường "sig" ngay trước "data" (xem cartsec.h).
struct Meta {
  const char* message_id;
  const char* cart_id;
  const char* timestamp;
  const uint8_t* key;
  Meta() : message_id(nullptr), cart_id(nullptr), timestamp(nullptr), key(nullptr) {}
  Meta(const char* id, const char* cart, const char* ts, const uint8_t* k = nullptr)
      : message_id(id), cart_id(cart), timestamp(ts), key(k) {}
};
int build_heartbeat(char* buf, size_t n, const Meta& m, uint32_t uptime_s, const char* cart_status);
int build_telemetry(char* buf, size_t n, const Meta& m, double weight_g, double battery_pct,
                    const char* cart_status, bool wifi_ok, bool mqtt_ok);
int build_scan(char* buf, size_t n, const Meta& m, const char* scan_id, const char* barcode, const char* action);
int build_event(char* buf, size_t n, const Meta& m, const char* event_type, const char* description);
int build_ack(char* buf, size_t n, const Meta& m, const char* command_id, const char* result, const char* message);

// ----------------------------------------------------------------- Lệnh từ Backend
struct Command {
  char command_id[64];
  char type[24];            // LOCK_CART | UNLOCK_CART | START_SESSION | END_SESSION
  long session_id;
  bool has_session_id;
};
// Kiểm tra payload của topic smartcart/<cart_id>/command. false nếu sai envelope / thiếu trường.
bool parse_command(const char* payload, const char* my_cart_id, Command* out);

// ----------------------------------------------------------------- Trạng thái xe
enum CartStatus { AVAILABLE = 0, IN_USE = 1, LOCKED = 2 };
const char* status_name(CartStatus s);

enum Effect { EFFECT_NONE, EFFECT_LOCKED, EFFECT_UNLOCKED, EFFECT_SESSION_STARTED, EFFECT_SESSION_ENDED };
struct AckInfo {
  bool ok;
  const char* message;      // tiếng Việt, gửi trong ACK
  Effect effect;            // để main.cpp phát còi/hiển thị (NONE khi lệnh lặp)
  bool replay;              // true: lệnh đã xử lý trước đó -> chỉ gửi lại ACK cũ
};

class CartLogic {
 public:
  CartLogic();
  CartStatus status() const;
  bool locked() const { return locked_; }
  bool has_session() const { return has_session_; }
  long session_id() const { return session_id_; }

  // Idempotent theo command_id; START_SESSION cùng session_id không làm gì thêm.
  AckInfo handle(const Command& c);

  enum ScanDecision { SCAN_OK, SCAN_LOCKED, SCAN_NO_SESSION, SCAN_OFFLINE };
  // Quyết định có nhận lần quét này không (cùng quy tắc với Simulator + chặn khi mất MQTT để khỏi mất gói QoS 0).
  ScanDecision can_scan(bool mqtt_connected) const;

 private:
  struct Seen { char id[64]; bool ok; const char* msg; };
  static const int kSeen = 8;
  Seen seen_[kSeen];
  int seen_count_, seen_next_;
  bool locked_, has_session_;
  long session_id_;
  const Seen* find_seen(const char* id) const;
  void remember(const char* id, bool ok, const char* msg);
};

// Chế độ quét: mặc định ADD; nút bấm chuyển sang REMOVE cho đúng 1 lần quét rồi tự về ADD (tránh quên).
class ScanMode {
 public:
  ScanMode() : remove_(false) {}
  void toggle() { remove_ = !remove_; }
  bool is_remove() const { return remove_; }
  const char* action() const { return remove_ ? "REMOVE" : "ADD"; }
  void after_scan() { remove_ = false; }
 private:
  bool remove_;
};

// ----------------------------------------------------------------- Mã vạch từ máy quét UART (GM65/GM66/GM861)
// Chuẩn hoá: bỏ khoảng trắng/CR/LF đầu cuối; chỉ nhận [0-9A-Za-z-], dài 4..64. false nếu không hợp lệ.
bool normalize_barcode(const char* raw, size_t len, char* out, size_t out_size);

// Gom byte thành dòng: kết thúc bởi CR/LF hoặc khi im lặng > idle_ms.
class LineAssembler {
 public:
  explicit LineAssembler(uint32_t idle_ms = 80) : idle_ms_(idle_ms), len_(0), last_ms_(0), overflow_(false) {}
  // Trả true khi có một dòng hoàn chỉnh (lấy bằng take()).
  bool feed(uint8_t byte, uint32_t now_ms);
  bool poll_timeout(uint32_t now_ms);
  size_t take(char* out, size_t out_size);   // copy + xoá; trả độ dài
 private:
  static const size_t kMax = 96;
  char buf_[kMax];
  uint32_t idle_ms_;
  size_t len_;
  uint32_t last_ms_;
  bool overflow_, ready_ = false;
};

// ----------------------------------------------------------------- Cảm biến cân (HX711)
// Trung vị 5 mẫu rồi làm mượt EMA; vùng chết < 1 g về 0; không bao giờ âm.
class WeightFilter {
 public:
  explicit WeightFilter(float alpha = 0.4f) : alpha_(alpha) { reset(); }
  void reset();
  float update(float grams);
 private:
  float win_[5];
  int n_, idx_;
  float ema_;
  bool has_ema_;
  float alpha_;
};
float raw_to_grams(long raw, long tare_raw, float counts_per_gram);

// ----------------------------------------------------------------- Pin (cầu chia áp + ADC)
// pin_mv: điện áp đo được tại chân ADC (analogReadMilliVolts), ratio: hệ số cầu chia (vd 2.0 cho 100k/100k).
float battery_mv_from_pin(float pin_mv, float ratio);
int battery_percent(float battery_mv);                  // LiPo 1S: 3300 mV = 0 %, 4200 mV = 100 %
class LowBatteryMonitor {                               // trễ: bật khi < 20 %, tắt khi >= 25 % để không nhấp nháy
 public:
  LowBatteryMonitor() : low_(false) {}
  bool update(int percent);
 private:
  bool low_;
};

// ----------------------------------------------------------------- Nút bấm, định thời, reconnect
class Button {
 public:
  enum Event { NONE, SHORT_PRESS, LONG_PRESS };
  Button(uint32_t debounce_ms = 30, uint32_t long_ms = 2000)
      : debounce_(debounce_ms), long_(long_ms), stable_(false), raw_(false), raw_since_(0), down_since_(0), long_sent_(false) {}
  Event update(bool pressed, uint32_t now_ms);   // SHORT khi nhả (nếu chưa LONG); LONG phát đúng 1 lần khi giữ đủ lâu
 private:
  uint32_t debounce_, long_;
  bool stable_, raw_;
  uint32_t raw_since_, down_since_;
  bool long_sent_;
};

class Interval {                                  // an toàn khi millis() tràn số
 public:
  explicit Interval(uint32_t period_ms) : period_(period_ms), last_(0), started_(false) {}
  bool due(uint32_t now_ms);
  void reset(uint32_t now_ms) { last_ = now_ms; started_ = true; }
  void fire_next() { started_ = false; }
 private:
  uint32_t period_, last_;
  bool started_;
};

class Backoff {                                   // 0,5 s -> 8 s, nhân đôi
 public:
  Backoff(uint32_t min_ms = 500, uint32_t max_ms = 8000) : min_(min_ms), max_(max_ms), cur_(min_ms) {}
  uint32_t next() { uint32_t v = cur_; cur_ = cur_ * 2 > max_ ? max_ : cur_ * 2; return v; }
  void reset() { cur_ = min_; }
 private:
  uint32_t min_, max_, cur_;
};

// ----------------------------------------------------------------- Console qua Serial (gỡ lỗi/hiệu chuẩn, không cần mạng)
struct ConsoleCmd {
  enum Type { NONE, HELP, STATUS, TARE, CAL, LOCK, UNLOCK, START, END, SCAN, SELFTEST, SIM_WEIGHT, SIM_BATTERY, UNKNOWN };
  Type type;
  char arg[70];       // SCAN: mã vạch
  float num;          // CAL: khối lượng (g); SIM_WEIGHT: gram; SIM_BATTERY: %; -1 = "auto" (bỏ giá trị giả lập)
};
// Phân tích 1 dòng lệnh ("cal 1000", "scan 8934588012341", "lock"...). Không phân biệt hoa/thường ở tên lệnh.
ConsoleCmd parse_console(const char* line);
// Hệ số hiệu chuẩn HX711 (đếm/gram) từ giá trị thô lúc trống và lúc có vật nặng đã biết khối lượng; 0 nếu không hợp lệ
// (khối lượng <= 0 hoặc chênh lệch thô quá nhỏ, tức là chưa đặt vật lên cân).
float calibration_from_samples(long raw_empty, long raw_loaded, float known_grams);

}  // namespace cartcore
