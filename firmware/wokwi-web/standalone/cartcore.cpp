#include "cartcore.h"
#include "cartsec.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace cartcore {

// =============================================================== JSON đầu vào
static const char* skip_ws(const char* p) {
  while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
  return p;
}

// p trỏ vào dấu " mở đầu; trả con trỏ ngay sau dấu " đóng, hoặc nullptr nếu chuỗi hỏng.
static const char* skip_string(const char* p) {
  if (*p != '"') return nullptr;
  p++;
  while (*p) {
    if (*p == '\\') { if (!p[1]) return nullptr; p += 2; continue; }
    if (*p == '"') return p + 1;
    p++;
  }
  return nullptr;
}

// Trả con trỏ tới đầu giá trị của key (sau dấu ':'), hoặc nullptr.
static const char* find_value(const char* json, const char* key) {
  if (!json || !key) return nullptr;
  size_t klen = strlen(key);
  const char* p = json;
  while (*p) {
    if (*p != '"') { p++; continue; }
    const char* start = p + 1;
    const char* end = skip_string(p);
    if (!end) return nullptr;
    const char* after = skip_ws(end);
    if (*after == ':') {                      // chuỗi này là một key
      size_t len = (size_t)(end - 1 - start);
      if (len == klen && strncmp(start, key, klen) == 0) return skip_ws(after + 1);
      p = after + 1;
    } else {
      p = end;                                // chuỗi này là giá trị -> bỏ qua nguyên khối
    }
  }
  return nullptr;
}

bool json_get_string(const char* json, const char* key, char* out, size_t out_size) {
  const char* v = find_value(json, key);
  if (!v || *v != '"' || out_size == 0) return false;
  v++;
  size_t n = 0;
  while (*v && *v != '"') {
    char c = *v;
    if (c == '\\') {
      v++;
      switch (*v) {
        case 'n': c = '\n'; break;
        case 't': c = '\t'; break;
        case 'r': c = '\r'; break;
        case 'u':
          for (int i = 1; i <= 4; i++) if (!v[i]) return false;   // không đọc vượt NUL
          c = '?'; v += 4; break;     // không giải mã \uXXXX (contract không dùng cho các trường này)
        case '"': case '\\': case '/': c = *v; break;
        default: return false;
      }
      if (!*v) return false;
    }
    if (n + 1 >= out_size) return false;      // quá dài -> từ chối thay vì cắt cụt
    out[n++] = c;
    v++;
  }
  if (*v != '"') return false;
  out[n] = 0;
  return true;
}

bool json_get_long(const char* json, const char* key, long* out) {
  const char* v = find_value(json, key);
  if (!v) return false;
  bool neg = false;
  if (*v == '-') { neg = true; v++; }
  if (*v < '0' || *v > '9') return false;
  long n = 0;
  while (*v >= '0' && *v <= '9') {
    if (n > 100000000L) return false;
    n = n * 10 + (*v - '0');
    v++;
  }
  if (*v == '.' || *v == 'e' || *v == 'E') return false;   // chỉ nhận số nguyên
  *out = neg ? -n : n;
  return true;
}

bool json_is_null(const char* json, const char* key) {
  const char* v = find_value(json, key);
  return v && strncmp(v, "null", 4) == 0;
}

size_t json_escape(const char* in, char* out, size_t out_size) {
  size_t n = 0;
  for (; *in; in++) {
    unsigned char c = (unsigned char)*in;
    const char* rep = nullptr;
    char tmp[7];
    if (c == '"') rep = "\\\"";
    else if (c == '\\') rep = "\\\\";
    else if (c == '\n') rep = "\\n";
    else if (c == '\r') rep = "\\r";
    else if (c == '\t') rep = "\\t";
    else if (c < 0x20) { snprintf(tmp, sizeof tmp, "\\u%04x", c); rep = tmp; }
    size_t add = rep ? strlen(rep) : 1;
    if (n + add + 1 > out_size) return 0;
    if (rep) { memcpy(out + n, rep, add); } else { out[n] = (char)c; }
    n += add;
  }
  if (n + 1 > out_size) return 0;
  out[n] = 0;
  return n;
}

// =============================================================== Thời gian & ID
bool time_valid(long long epoch_s) { return epoch_s > 1700000000LL; }

void iso8601_utc(long long t, char out[21]) {
  // Thuật toán civil_from_days (Howard Hinnant) – không phụ thuộc múi giờ/locale của libc.
  long long days = t / 86400, rem = t % 86400;
  if (rem < 0) { rem += 86400; days--; }
  long long z = days + 719468;
  long long era = (z >= 0 ? z : z - 146096) / 146097;
  long long doe = z - era * 146097;
  long long yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  long long y = yoe + era * 400;
  long long doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  long long mp = (5 * doy + 2) / 153;
  long long d = doy - (153 * mp + 2) / 5 + 1;
  long long m = mp < 10 ? mp + 3 : mp - 9;
  if (m <= 2) y++;
  char tmp[96];
  snprintf(tmp, sizeof tmp, "%04lld-%02lld-%02lldT%02lld:%02lld:%02lldZ", y, m, d, rem / 3600, (rem % 3600) / 60, rem % 60);
  memcpy(out, tmp, 20);   // với epoch hợp lệ (năm 0000–9999) chuỗi luôn đúng 20 ký tự
  out[20] = 0;
}

void uuid4(const uint8_t r[16], char out[37]) {
  uint8_t b[16];
  memcpy(b, r, 16);
  b[6] = (uint8_t)((b[6] & 0x0F) | 0x40);
  b[8] = (uint8_t)((b[8] & 0x3F) | 0x80);
  snprintf(out, 37, "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
           b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]);
}

// =============================================================== JSON đầu ra
// Ghép envelope; data_json là object con đã build sẵn.
static int envelope(char* buf, size_t n, const Meta& m, const char* kind, const char* data_json) {
  char id[96], cart[96], ts[48];
  if (!json_escape(m.message_id, id, sizeof id) || !json_escape(m.cart_id, cart, sizeof cart) ||
      !json_escape(m.timestamp, ts, sizeof ts))
    return -1;
  int w;
  if (m.key) {      // có khoá => ký HMAC-SHA256 trên chính chuỗi data_json sẽ được gửi (xem cartsec.h)
    char sig[65];
    sign_message(m.key, m.message_id, m.cart_id, m.timestamp, kind, data_json, strlen(data_json), sig);
    w = snprintf(buf, n, "{\"message_id\":\"%s\",\"cart_id\":\"%s\",\"schema_version\":1,\"timestamp\":\"%s\",\"sig\":\"%s\",\"data\":%s}",
                 id, cart, ts, sig, data_json);
  } else {
    w = snprintf(buf, n, "{\"message_id\":\"%s\",\"cart_id\":\"%s\",\"schema_version\":1,\"timestamp\":\"%s\",\"data\":%s}",
                 id, cart, ts, data_json);
  }
  return (w < 0 || (size_t)w >= n) ? -1 : w;
}

int build_heartbeat(char* buf, size_t n, const Meta& m, uint32_t uptime_s, const char* cart_status) {
  char d[96];
  snprintf(d, sizeof d, "{\"uptime_s\":%lu,\"cart_status\":\"%s\"}", (unsigned long)uptime_s, cart_status);
  return envelope(buf, n, m, "heartbeat", d);
}

int build_telemetry(char* buf, size_t n, const Meta& m, double weight_g, double battery_pct,
                    const char* cart_status, bool wifi_ok, bool mqtt_ok) {
  if (weight_g < 0) weight_g = 0;
  if (battery_pct < 0) battery_pct = 0;
  if (battery_pct > 100) battery_pct = 100;
  char d[200];
  snprintf(d, sizeof d,
           "{\"actual_weight\":%.1f,\"battery_percent\":%.1f,\"cart_status\":\"%s\",\"wifi_status\":\"%s\",\"mqtt_status\":\"%s\"}",
           weight_g, battery_pct, cart_status, wifi_ok ? "CONNECTED" : "DISCONNECTED", mqtt_ok ? "CONNECTED" : "DISCONNECTED");
  return envelope(buf, n, m, "telemetry", d);
}

int build_scan(char* buf, size_t n, const Meta& m, const char* scan_id, const char* barcode, const char* action) {
  char sid[96], bc[160];
  if (!json_escape(scan_id, sid, sizeof sid) || !json_escape(barcode, bc, sizeof bc)) return -1;
  char d[320];
  snprintf(d, sizeof d, "{\"scan_id\":\"%s\",\"barcode\":\"%s\",\"action\":\"%s\"}", sid, bc, action);
  return envelope(buf, n, m, "scan", d);
}

int build_event(char* buf, size_t n, const Meta& m, const char* event_type, const char* description) {
  char t[96], desc[256];
  if (!json_escape(event_type, t, sizeof t) || !json_escape(description, desc, sizeof desc)) return -1;
  char d[400];
  snprintf(d, sizeof d, "{\"event_type\":\"%s\",\"description\":\"%s\"}", t, desc);
  return envelope(buf, n, m, "event", d);
}

int build_ack(char* buf, size_t n, const Meta& m, const char* command_id, const char* result, const char* message) {
  char cid[96], msg[256];
  if (!json_escape(command_id, cid, sizeof cid) || !json_escape(message, msg, sizeof msg)) return -1;
  char d[400];
  snprintf(d, sizeof d, "{\"command_id\":\"%s\",\"result\":\"%s\",\"message\":\"%s\"}", cid, result, msg);
  return envelope(buf, n, m, "ack", d);
}

// =============================================================== Lệnh
bool parse_command(const char* payload, const char* my_cart_id, Command* out) {
  memset(out, 0, sizeof *out);
  long ver = 0;
  char cart[48];
  if (!json_get_long(payload, "schema_version", &ver) || ver != 1) return false;
  if (!json_get_string(payload, "cart_id", cart, sizeof cart) || strcmp(cart, my_cart_id) != 0) return false;
  if (!json_get_string(payload, "command_id", out->command_id, sizeof out->command_id) || !out->command_id[0]) return false;
  if (!json_get_string(payload, "command_type", out->type, sizeof out->type)) return false;
  out->has_session_id = json_get_long(payload, "session_id", &out->session_id);
  return true;
}

// =============================================================== Trạng thái
const char* status_name(CartStatus s) {
  switch (s) {
    case AVAILABLE: return "AVAILABLE";
    case IN_USE: return "IN_USE";
    default: return "LOCKED";
  }
}

CartLogic::CartLogic() : seen_count_(0), seen_next_(0), locked_(false), has_session_(false), session_id_(0) {
  memset(seen_, 0, sizeof seen_);
}

CartStatus CartLogic::status() const {
  if (locked_) return LOCKED;
  return has_session_ ? IN_USE : AVAILABLE;
}

const CartLogic::Seen* CartLogic::find_seen(const char* id) const {
  for (int i = 0; i < seen_count_; i++)
    if (strcmp(seen_[i].id, id) == 0) return &seen_[i];
  return nullptr;
}

void CartLogic::remember(const char* id, bool ok, const char* msg) {
  Seen& s = seen_[seen_next_];
  strncpy(s.id, id, sizeof s.id - 1);
  s.id[sizeof s.id - 1] = 0;
  s.ok = ok;
  s.msg = msg;
  seen_next_ = (seen_next_ + 1) % kSeen;
  if (seen_count_ < kSeen) seen_count_++;
}

AckInfo CartLogic::handle(const Command& c) {
  if (const Seen* s = find_seen(c.command_id)) return AckInfo{s->ok, s->msg, EFFECT_NONE, true};

  AckInfo a{true, "", EFFECT_NONE, false};
  if (strcmp(c.type, "LOCK_CART") == 0) {
    a.effect = locked_ ? EFFECT_NONE : EFFECT_LOCKED;
    locked_ = true;
    a.message = "Đã khoá xe";
  } else if (strcmp(c.type, "UNLOCK_CART") == 0) {
    a.effect = locked_ ? EFFECT_UNLOCKED : EFFECT_NONE;
    locked_ = false;
    a.message = "Đã mở khoá";
  } else if (strcmp(c.type, "START_SESSION") == 0) {
    if (!c.has_session_id) {
      a = AckInfo{false, "Thiếu session_id", EFFECT_NONE, false};
    } else {
      a.effect = (has_session_ && session_id_ == c.session_id) ? EFFECT_NONE : EFFECT_SESSION_STARTED;
      has_session_ = true;
      session_id_ = c.session_id;
      a.message = "Đã bắt đầu phiên";
    }
  } else if (strcmp(c.type, "END_SESSION") == 0) {
    a.effect = has_session_ ? EFFECT_SESSION_ENDED : EFFECT_NONE;
    has_session_ = false;
    session_id_ = 0;
    a.message = "Đã kết thúc phiên";
  } else {
    a = AckInfo{false, "Lệnh không hỗ trợ", EFFECT_NONE, false};
  }
  remember(c.command_id, a.ok, a.message);
  return a;
}

CartLogic::ScanDecision CartLogic::can_scan(bool mqtt_connected) const {
  if (locked_) return SCAN_LOCKED;
  if (!has_session_) return SCAN_NO_SESSION;
  if (!mqtt_connected) return SCAN_OFFLINE;
  return SCAN_OK;
}

// =============================================================== Mã vạch
bool normalize_barcode(const char* raw, size_t len, char* out, size_t out_size) {
  size_t a = 0, b = len;
  while (a < b && (raw[a] == ' ' || raw[a] == '\r' || raw[a] == '\n' || raw[a] == '\t' || raw[a] == 0)) a++;
  while (b > a && (raw[b - 1] == ' ' || raw[b - 1] == '\r' || raw[b - 1] == '\n' || raw[b - 1] == '\t' || raw[b - 1] == 0)) b--;
  size_t n = b - a;
  if (n < 4 || n > 64 || n + 1 > out_size) return false;
  for (size_t i = a; i < b; i++) {
    char c = raw[i];
    bool ok = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '-';
    if (!ok) return false;
  }
  memcpy(out, raw + a, n);
  out[n] = 0;
  return true;
}

bool LineAssembler::feed(uint8_t byte, uint32_t now_ms) {
  last_ms_ = now_ms;
  if (byte == '\r' || byte == '\n') {
    if (len_ > 0 && !overflow_) { ready_ = true; return true; }
    len_ = 0; overflow_ = false;               // dòng rỗng hoặc dòng tràn: bỏ
    return false;
  }
  if (ready_) return false;                    // chờ take()
  if (len_ + 1 < kMax) buf_[len_++] = (char)byte; else overflow_ = true;
  return false;
}

bool LineAssembler::poll_timeout(uint32_t now_ms) {
  if (!ready_ && len_ > 0 && !overflow_ && (uint32_t)(now_ms - last_ms_) >= idle_ms_) ready_ = true;
  if (overflow_ && (uint32_t)(now_ms - last_ms_) >= idle_ms_) { len_ = 0; overflow_ = false; }
  return ready_;
}

size_t LineAssembler::take(char* out, size_t out_size) {
  size_t n = len_ < out_size - 1 ? len_ : out_size - 1;
  memcpy(out, buf_, n);
  out[n] = 0;
  len_ = 0; overflow_ = false; ready_ = false;
  return n;
}

// =============================================================== Cân
void WeightFilter::reset() { n_ = 0; idx_ = 0; has_ema_ = false; ema_ = 0; }

float WeightFilter::update(float g) {
  win_[idx_] = g;
  idx_ = (idx_ + 1) % 5;
  if (n_ < 5) n_++;
  float tmp[5];
  for (int i = 0; i < n_; i++) tmp[i] = win_[i];
  for (int i = 1; i < n_; i++) {               // sắp xếp chèn (n <= 5)
    float k = tmp[i]; int j = i - 1;
    while (j >= 0 && tmp[j] > k) { tmp[j + 1] = tmp[j]; j--; }
    tmp[j + 1] = k;
  }
  float med = tmp[n_ / 2];
  ema_ = has_ema_ ? ema_ + alpha_ * (med - ema_) : med;
  has_ema_ = true;
  float out = ema_ < 1.0f && ema_ > -1.0f ? 0.0f : ema_;
  return out < 0 ? 0.0f : out;
}

float raw_to_grams(long raw, long tare_raw, float counts_per_gram) {
  if (counts_per_gram == 0.0f) return 0.0f;
  return (float)(raw - tare_raw) / counts_per_gram;
}

// =============================================================== Pin
float battery_mv_from_pin(float pin_mv, float ratio) { return pin_mv * ratio; }

int battery_percent(float mv) {
  // Đường cong xả LiPo 1S (xấp xỉ): mV -> %
  static const float pts[][2] = {{3300, 0}, {3500, 5}, {3600, 15}, {3700, 35}, {3800, 55}, {3900, 72}, {4000, 85}, {4100, 94}, {4200, 100}};
  const int n = (int)(sizeof pts / sizeof pts[0]);
  if (mv <= pts[0][0]) return 0;
  if (mv >= pts[n - 1][0]) return 100;
  for (int i = 1; i < n; i++) {
    if (mv <= pts[i][0]) {
      float t = (mv - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0]);
      return (int)(pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1]) + 0.5f);
    }
  }
  return 100;
}

bool LowBatteryMonitor::update(int percent) {
  if (!low_ && percent < 20) low_ = true;
  else if (low_ && percent >= 25) low_ = false;
  return low_;
}

// =============================================================== Nút, định thời
Button::Event Button::update(bool pressed, uint32_t now) {
  if (pressed != raw_) { raw_ = pressed; raw_since_ = now; }
  if ((uint32_t)(now - raw_since_) >= debounce_ && stable_ != raw_) {
    stable_ = raw_;
    if (stable_) { down_since_ = now; long_sent_ = false; }
    else if (!long_sent_) return SHORT_PRESS;
  }
  if (stable_ && !long_sent_ && (uint32_t)(now - down_since_) >= long_) { long_sent_ = true; return LONG_PRESS; }
  return NONE;
}

bool Interval::due(uint32_t now) {
  if (!started_ || (uint32_t)(now - last_) >= period_) { last_ = now; started_ = true; return true; }
  return false;
}


// =============================================================== Console
static bool ieq(const char* a, const char* b) {
  for (; *a && *b; a++, b++) {
    char x = *a, y = *b;
    if (x >= 'A' && x <= 'Z') x = (char)(x + 32);
    if (y >= 'A' && y <= 'Z') y = (char)(y + 32);
    if (x != y) return false;
  }
  return *a == 0 && *b == 0;
}

ConsoleCmd parse_console(const char* line) {
  ConsoleCmd c;
  c.type = ConsoleCmd::NONE;
  c.arg[0] = 0;
  c.num = 0;
  if (!line) return c;
  while (*line == ' ' || *line == '\t') line++;
  char word[16];
  size_t n = 0;
  while (line[n] && line[n] != ' ' && line[n] != '\t' && line[n] != '\r' && line[n] != '\n') n++;
  if (n == 0) return c;
  if (n >= sizeof word) { c.type = ConsoleCmd::UNKNOWN; return c; }
  memcpy(word, line, n);
  word[n] = 0;
  const char* rest = line + n;
  while (*rest == ' ' || *rest == '\t') rest++;
  size_t rl = strlen(rest);
  while (rl > 0 && (rest[rl - 1] == '\r' || rest[rl - 1] == '\n' || rest[rl - 1] == ' ')) rl--;

  if (ieq(word, "help") || ieq(word, "?")) c.type = ConsoleCmd::HELP;
  else if (ieq(word, "status")) c.type = ConsoleCmd::STATUS;
  else if (ieq(word, "tare")) c.type = ConsoleCmd::TARE;
  else if (ieq(word, "lock")) c.type = ConsoleCmd::LOCK;
  else if (ieq(word, "unlock")) c.type = ConsoleCmd::UNLOCK;
  else if (ieq(word, "start")) c.type = ConsoleCmd::START;
  else if (ieq(word, "end")) c.type = ConsoleCmd::END;
  else if (ieq(word, "selftest")) c.type = ConsoleCmd::SELFTEST;
  else if (ieq(word, "scan")) {
    if (rl == 0 || rl >= sizeof c.arg) { c.type = ConsoleCmd::UNKNOWN; return c; }
    memcpy(c.arg, rest, rl);
    c.arg[rl] = 0;
    c.type = ConsoleCmd::SCAN;
  } else if (ieq(word, "cal")) {
    char tmp[24];
    if (rl == 0 || rl >= sizeof tmp) { c.type = ConsoleCmd::UNKNOWN; return c; }
    memcpy(tmp, rest, rl);
    tmp[rl] = 0;
    char* end = nullptr;
    double v = strtod(tmp, &end);
    if (end == tmp || *end != 0 || !(v > 0.0 && v <= 500000.0)) { c.type = ConsoleCmd::UNKNOWN; return c; }
    c.num = (float)v;
    c.type = ConsoleCmd::CAL;
  } else if (ieq(word, "weight") || ieq(word, "battery")) {   // giả lập cảm biến khi chưa có linh kiện thật
    bool is_w = ieq(word, "weight");
    char tmp[24];
    if (rl == 0 || rl >= sizeof tmp) { c.type = ConsoleCmd::UNKNOWN; return c; }
    memcpy(tmp, rest, rl);
    tmp[rl] = 0;
    if (ieq(tmp, "auto")) {
      c.num = -1.0f;
    } else {
      char* end = nullptr;
      double v = strtod(tmp, &end);
      double hi = is_w ? 100000.0 : 100.0;
      if (end == tmp || *end != 0 || !(v >= 0.0 && v <= hi)) { c.type = ConsoleCmd::UNKNOWN; return c; }
      c.num = (float)v;
    }
    c.type = is_w ? ConsoleCmd::SIM_WEIGHT : ConsoleCmd::SIM_BATTERY;
  } else c.type = ConsoleCmd::UNKNOWN;
  return c;
}

float calibration_from_samples(long raw_empty, long raw_loaded, float known_grams) {
  if (!(known_grams > 0.0f)) return 0.0f;
  long diff = raw_loaded - raw_empty;
  if (diff > -100 && diff < 100) return 0.0f;      // gần như không đổi -> chưa đặt vật lên cân / cảm biến lỗi
  return (float)diff / known_grams;
}

}  // namespace cartcore
