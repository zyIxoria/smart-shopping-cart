// Unit test cho cartcore. Chạy:  pio test -e native   hoặc   tools/run_native_tests.sh
#include <string.h>
#include <unity.h>

#include "cartcore.h"
#include "cartsec.h"

using namespace cartcore;

void setUp(void) {}
void tearDown(void) {}

static Meta meta() { return Meta{"11111111-2222-4333-8444-555555555555", "CART_004", "2026-11-07T10:30:00Z"}; }
static Command cmd(const char* id, const char* type, long sid = -1) {
  Command c;
  memset(&c, 0, sizeof c);
  strcpy(c.command_id, id);
  strcpy(c.type, type);
  c.has_session_id = sid >= 0;
  c.session_id = sid < 0 ? 0 : sid;
  return c;
}

// ------------------------------------------------------------------ JSON
void test_json_get_basic() {
  const char* j = "{\"a\":\"x\",\"data\":{\"n\":42,\"neg\":-7,\"s\":\"hi\\\"there\",\"nul\":null}}";
  char out[32];
  long v;
  TEST_ASSERT_TRUE(json_get_string(j, "s", out, sizeof out));
  TEST_ASSERT_EQUAL_STRING("hi\"there", out);
  TEST_ASSERT_TRUE(json_get_long(j, "n", &v));
  TEST_ASSERT_EQUAL_INT(42, v);
  TEST_ASSERT_TRUE(json_get_long(j, "neg", &v));
  TEST_ASSERT_EQUAL_INT(-7, v);
  TEST_ASSERT_TRUE(json_is_null(j, "nul"));
  TEST_ASSERT_FALSE(json_get_long(j, "nul", &v));
  TEST_ASSERT_FALSE(json_get_string(j, "missing", out, sizeof out));
  TEST_ASSERT_FALSE(json_get_long(j, "s", &v));        // chuỗi không phải số
}

void test_json_key_inside_string_value_is_ignored() {
  const char* j = "{\"note\":\"\\\"command_id\\\":\\\"evil\\\"\",\"command_id\":\"real\"}";
  char out[32];
  TEST_ASSERT_TRUE(json_get_string(j, "command_id", out, sizeof out));
  TEST_ASSERT_EQUAL_STRING("real", out);
  const char* k = "{\"x\":\"command_id\",\"command_id\":\"real2\"}";   // "command_id" là GIÁ TRỊ của x
  TEST_ASSERT_TRUE(json_get_string(k, "command_id", out, sizeof out));
  TEST_ASSERT_EQUAL_STRING("real2", out);
}

void test_json_rejects_garbage_and_overflow() {
  char out[4];
  long v;
  TEST_ASSERT_FALSE(json_get_string("{\"a\":\"toolong\"}", "a", out, sizeof out));   // không cắt cụt
  char big[32];
  TEST_ASSERT_FALSE(json_get_string("{\"a\":\"unterminated", "a", big, sizeof big));
  TEST_ASSERT_FALSE(json_get_string("{\"a\":\"x\\u12", "a", big, sizeof big));   // \u cụt, không đọc vượt chuỗi
  TEST_ASSERT_FALSE(json_get_string("", "a", out, sizeof out));
  TEST_ASSERT_FALSE(json_get_long("{\"n\":1.5}", "n", &v));
  TEST_ASSERT_FALSE(json_get_long("not json at all", "n", &v));
  TEST_ASSERT_FALSE(json_get_string(nullptr, "a", out, sizeof out));
}

void test_json_escape() {
  char out[64];
  TEST_ASSERT_TRUE(json_escape("a\"b\\c\nd", out, sizeof out) > 0);
  TEST_ASSERT_EQUAL_STRING("a\\\"b\\\\c\\nd", out);
  char tiny[3];
  TEST_ASSERT_EQUAL_INT(0, (long)json_escape("abcdef", tiny, sizeof tiny));
}

// ------------------------------------------------------------------ Thời gian & UUID
void test_iso8601() {
  char s[21];
  iso8601_utc(0, s);
  TEST_ASSERT_EQUAL_STRING("1970-01-01T00:00:00Z", s);
  iso8601_utc(1794047400LL, s);                       // 2026-11-07T10:30:00Z
  TEST_ASSERT_EQUAL_STRING("2026-11-07T10:30:00Z", s);
  iso8601_utc(1709164800LL + 86399, s);               // 29/02/2024 (năm nhuận) 23:59:59
  TEST_ASSERT_EQUAL_STRING("2024-02-29T23:59:59Z", s);
  iso8601_utc(4102444799LL, s);
  TEST_ASSERT_EQUAL_STRING("2099-12-31T23:59:59Z", s);
  TEST_ASSERT_FALSE(time_valid(0));
  TEST_ASSERT_FALSE(time_valid(100000));
  TEST_ASSERT_TRUE(time_valid(1794047400LL));
}

void test_uuid4_format() {
  uint8_t r[16];
  for (int i = 0; i < 16; i++) r[i] = (uint8_t)(0xA0 + i);
  char u[37];
  uuid4(r, u);
  TEST_ASSERT_EQUAL_INT(36, (long)strlen(u));
  TEST_ASSERT_EQUAL_INT('-', u[8]);
  TEST_ASSERT_EQUAL_INT('4', u[14]);                  // version 4
  TEST_ASSERT_TRUE(u[19] == '8' || u[19] == '9' || u[19] == 'a' || u[19] == 'b');   // variant 10xx
  for (int i = 0; i < 16; i++) r[i] = 0xFF;
  uuid4(r, u);
  TEST_ASSERT_EQUAL_STRING("ffffffff-ffff-4fff-bfff-ffffffffffff", u);
}

// ------------------------------------------------------------------ Build message
void test_build_messages_shape() {
  char b[600];
  int n = build_heartbeat(b, sizeof b, meta(), 90, "IN_USE");
  TEST_ASSERT_TRUE(n > 0);
  TEST_ASSERT_EQUAL_STRING(
      "{\"message_id\":\"11111111-2222-4333-8444-555555555555\",\"cart_id\":\"CART_004\",\"schema_version\":1,"
      "\"timestamp\":\"2026-11-07T10:30:00Z\",\"data\":{\"uptime_s\":90,\"cart_status\":\"IN_USE\"}}", b);
  n = build_telemetry(b, sizeof b, meta(), -3.0, 140.0, "AVAILABLE", true, false);   // giá trị ngoài miền bị kẹp
  TEST_ASSERT_TRUE(n > 0);
  TEST_ASSERT_TRUE(strstr(b, "\"actual_weight\":0.0") != nullptr);
  TEST_ASSERT_TRUE(strstr(b, "\"battery_percent\":100.0") != nullptr);
  TEST_ASSERT_TRUE(strstr(b, "\"mqtt_status\":\"DISCONNECTED\"") != nullptr);
}

void test_build_overflow_returns_minus_one() {
  char tiny[40];
  TEST_ASSERT_EQUAL_INT(-1, build_heartbeat(tiny, sizeof tiny, meta(), 1, "IN_USE"));
}

void test_build_escapes_user_text() {
  char b[700];
  TEST_ASSERT_TRUE(build_event(b, sizeof b, meta(), "X", "có \"dấu\" nháy") > 0);
  TEST_ASSERT_TRUE(strstr(b, "có \\\"dấu\\\" nháy") != nullptr);
}

// ------------------------------------------------------------------ Lệnh
static const char* kLock =
    "{\"message_id\":\"m1\",\"cart_id\":\"CART_004\",\"schema_version\":1,\"timestamp\":\"2026-11-07T10:30:00Z\","
    "\"data\":{\"command_id\":\"c-1\",\"command_type\":\"LOCK_CART\",\"parameters\":{}}}";

void test_parse_command_ok() {
  Command c;
  TEST_ASSERT_TRUE(parse_command(kLock, "CART_004", &c));
  TEST_ASSERT_EQUAL_STRING("c-1", c.command_id);
  TEST_ASSERT_EQUAL_STRING("LOCK_CART", c.type);
  TEST_ASSERT_FALSE(c.has_session_id);
  const char* start =
      "{\"message_id\":\"m\",\"cart_id\":\"CART_004\",\"schema_version\":1,\"timestamp\":\"t\","
      "\"data\":{\"command_id\":\"c-2\",\"command_type\":\"START_SESSION\",\"parameters\":{\"session_id\":17}}}";
  TEST_ASSERT_TRUE(parse_command(start, "CART_004", &c));
  TEST_ASSERT_TRUE(c.has_session_id);
  TEST_ASSERT_EQUAL_INT(17, c.session_id);
  const char* end_null =
      "{\"message_id\":\"m\",\"cart_id\":\"CART_004\",\"schema_version\":1,\"timestamp\":\"t\","
      "\"data\":{\"command_id\":\"c-3\",\"command_type\":\"END_SESSION\",\"parameters\":{\"session_id\":null}}}";
  TEST_ASSERT_TRUE(parse_command(end_null, "CART_004", &c));
  TEST_ASSERT_FALSE(c.has_session_id);
}

void test_parse_command_rejects_bad_input() {
  Command c;
  TEST_ASSERT_FALSE(parse_command(kLock, "CART_005", &c));                 // sai xe
  TEST_ASSERT_FALSE(parse_command("{}", "CART_004", &c));
  TEST_ASSERT_FALSE(parse_command("xyz", "CART_004", &c));
  TEST_ASSERT_FALSE(parse_command("{\"cart_id\":\"CART_004\",\"schema_version\":2,\"data\":{\"command_id\":\"a\",\"command_type\":\"X\"}}", "CART_004", &c));
  TEST_ASSERT_FALSE(parse_command("{\"cart_id\":\"CART_004\",\"schema_version\":1,\"data\":{\"command_type\":\"LOCK_CART\"}}", "CART_004", &c));
  TEST_ASSERT_FALSE(parse_command("{\"cart_id\":\"CART_004\",\"schema_version\":1,\"data\":{\"command_id\":\"\",\"command_type\":\"LOCK_CART\"}}", "CART_004", &c));
}

// ------------------------------------------------------------------ Trạng thái xe
void test_session_and_lock_state_machine() {
  CartLogic l;
  TEST_ASSERT_EQUAL_INT(AVAILABLE, l.status());
  AckInfo a = l.handle(cmd("a", "START_SESSION", 5));
  TEST_ASSERT_TRUE(a.ok);
  TEST_ASSERT_EQUAL_INT(EFFECT_SESSION_STARTED, a.effect);
  TEST_ASSERT_EQUAL_INT(IN_USE, l.status());
  TEST_ASSERT_EQUAL_INT(5, l.session_id());
  a = l.handle(cmd("b", "LOCK_CART"));
  TEST_ASSERT_EQUAL_INT(EFFECT_LOCKED, a.effect);
  TEST_ASSERT_EQUAL_INT(LOCKED, l.status());
  a = l.handle(cmd("c", "UNLOCK_CART"));
  TEST_ASSERT_EQUAL_INT(EFFECT_UNLOCKED, a.effect);
  TEST_ASSERT_EQUAL_INT(IN_USE, l.status());                // còn phiên -> IN_USE
  a = l.handle(cmd("d", "END_SESSION"));
  TEST_ASSERT_EQUAL_INT(EFFECT_SESSION_ENDED, a.effect);
  TEST_ASSERT_EQUAL_INT(AVAILABLE, l.status());
}

void test_lock_without_session_then_unlock() {
  CartLogic l;
  l.handle(cmd("a", "LOCK_CART"));
  TEST_ASSERT_EQUAL_INT(LOCKED, l.status());
  l.handle(cmd("b", "UNLOCK_CART"));
  TEST_ASSERT_EQUAL_INT(AVAILABLE, l.status());
}

void test_commands_are_idempotent() {
  CartLogic l;
  l.handle(cmd("s1", "START_SESSION", 9));
  AckInfo again = l.handle(cmd("s1", "START_SESSION", 9));    // cùng command_id
  TEST_ASSERT_TRUE(again.replay);
  TEST_ASSERT_EQUAL_INT(EFFECT_NONE, again.effect);
  AckInfo same = l.handle(cmd("s2", "START_SESSION", 9));     // command mới nhưng cùng phiên (Backend reconcile)
  TEST_ASSERT_FALSE(same.replay);
  TEST_ASSERT_EQUAL_INT(EFFECT_NONE, same.effect);            // không "bắt đầu lại"
  TEST_ASSERT_EQUAL_INT(9, l.session_id());
  AckInfo other = l.handle(cmd("s3", "START_SESSION", 10));   // phiên khác -> bắt đầu mới
  TEST_ASSERT_EQUAL_INT(EFFECT_SESSION_STARTED, other.effect);
  AckInfo lk = l.handle(cmd("k1", "LOCK_CART"));
  AckInfo lk2 = l.handle(cmd("k2", "LOCK_CART"));             // đã khoá rồi
  TEST_ASSERT_EQUAL_INT(EFFECT_LOCKED, lk.effect);
  TEST_ASSERT_EQUAL_INT(EFFECT_NONE, lk2.effect);
  TEST_ASSERT_TRUE(lk2.ok);
}

void test_invalid_commands_fail() {
  CartLogic l;
  AckInfo a = l.handle(cmd("x", "START_SESSION"));            // thiếu session_id
  TEST_ASSERT_FALSE(a.ok);
  TEST_ASSERT_EQUAL_INT(AVAILABLE, l.status());
  a = l.handle(cmd("y", "SELF_DESTRUCT"));
  TEST_ASSERT_FALSE(a.ok);
  AckInfo r = l.handle(cmd("y", "SELF_DESTRUCT"));            // lệnh lỗi lặp lại -> ACK FAILED cũ
  TEST_ASSERT_TRUE(r.replay);
  TEST_ASSERT_FALSE(r.ok);
}

void test_seen_ring_forgets_oldest() {
  CartLogic l;
  char id[8];
  for (int i = 0; i < 9; i++) { snprintf(id, sizeof id, "c%d", i); l.handle(cmd(id, "LOCK_CART")); }
  TEST_ASSERT_FALSE(l.handle(cmd("c0", "UNLOCK_CART")).replay);   // c0 đã bị đẩy khỏi vòng nhớ 8 phần tử
  TEST_ASSERT_TRUE(l.handle(cmd("c8", "UNLOCK_CART")).replay);
}

void test_scan_decisions() {
  CartLogic l;
  TEST_ASSERT_EQUAL_INT(CartLogic::SCAN_NO_SESSION, l.can_scan(true));
  l.handle(cmd("a", "START_SESSION", 1));
  TEST_ASSERT_EQUAL_INT(CartLogic::SCAN_OK, l.can_scan(true));
  TEST_ASSERT_EQUAL_INT(CartLogic::SCAN_OFFLINE, l.can_scan(false));
  l.handle(cmd("b", "LOCK_CART"));
  TEST_ASSERT_EQUAL_INT(CartLogic::SCAN_LOCKED, l.can_scan(true));
}

void test_scan_mode_reverts_after_one_scan() {
  ScanMode m;
  TEST_ASSERT_EQUAL_STRING("ADD", m.action());
  m.toggle();
  TEST_ASSERT_EQUAL_STRING("REMOVE", m.action());
  m.after_scan();
  TEST_ASSERT_EQUAL_STRING("ADD", m.action());
}

// ------------------------------------------------------------------ Mã vạch
void test_normalize_barcode() {
  char o[70];
  TEST_ASSERT_TRUE(normalize_barcode("8934588012341\r\n", 15, o, sizeof o));
  TEST_ASSERT_EQUAL_STRING("8934588012341", o);
  TEST_ASSERT_TRUE(normalize_barcode("  ABC-123 ", 10, o, sizeof o));
  TEST_ASSERT_EQUAL_STRING("ABC-123", o);
  TEST_ASSERT_FALSE(normalize_barcode("123", 3, o, sizeof o));                 // quá ngắn
  TEST_ASSERT_FALSE(normalize_barcode("12 34", 5, o, sizeof o));               // khoảng trắng giữa
  TEST_ASSERT_FALSE(normalize_barcode("12\x01" "34", 5, o, sizeof o));         // ký tự điều khiển
  TEST_ASSERT_FALSE(normalize_barcode("", 0, o, sizeof o));
  char big[80];
  memset(big, '1', 70); big[70] = 0;
  TEST_ASSERT_FALSE(normalize_barcode(big, 70, o, sizeof o));                  // quá dài
}

void test_line_assembler_cr_terminated() {
  LineAssembler la;
  const char* s = "8934588012341\r";
  bool ready = false;
  for (const char* p = s; *p; p++) ready = la.feed((uint8_t)*p, 100);
  TEST_ASSERT_TRUE(ready);
  char out[100];
  TEST_ASSERT_EQUAL_INT(13, (long)la.take(out, sizeof out));
  TEST_ASSERT_EQUAL_STRING("8934588012341", out);
  TEST_ASSERT_FALSE(la.feed('\n', 101));                                       // CRLF: ký tự thừa không tạo dòng rỗng
}

void test_line_assembler_idle_timeout_and_overflow() {
  LineAssembler la(80);
  la.feed('1', 0); la.feed('2', 10); la.feed('3', 20); la.feed('4', 30);
  TEST_ASSERT_FALSE(la.poll_timeout(100));                                     // mới 70 ms
  TEST_ASSERT_TRUE(la.poll_timeout(115));                                      // >= 80 ms kể từ byte cuối
  char out[100];
  TEST_ASSERT_EQUAL_INT(4, (long)la.take(out, sizeof out));
  LineAssembler lb;
  for (int i = 0; i < 300; i++) lb.feed('9', 1000);                            // tràn buffer
  TEST_ASSERT_FALSE(lb.feed('\r', 1001));                                      // dòng tràn bị bỏ
  TEST_ASSERT_FALSE(lb.poll_timeout(5000));
}

// ------------------------------------------------------------------ Cân
void test_weight_filter_rejects_spike_and_smooths() {
  WeightFilter f(0.5f);
  float v = 0;
  for (int i = 0; i < 5; i++) v = f.update(500.0f);
  TEST_ASSERT_FLOAT_WITHIN(0.5f, 500.0f, v);
  v = f.update(5000.0f);                                                       // 1 mẫu nhiễu bị trung vị loại
  TEST_ASSERT_FLOAT_WITHIN(1.0f, 500.0f, v);
  for (int i = 0; i < 12; i++) v = f.update(800.0f);                           // thay đổi thật -> hội tụ
  TEST_ASSERT_FLOAT_WITHIN(2.0f, 800.0f, v);
}

void test_weight_filter_deadband_and_non_negative() {
  WeightFilter f;
  float v = 0;
  for (int i = 0; i < 6; i++) v = f.update(0.6f);
  TEST_ASSERT_EQUAL_INT(0, (long)v);
  WeightFilter g;
  for (int i = 0; i < 6; i++) v = g.update(-25.0f);
  TEST_ASSERT_TRUE(v >= 0.0f);
}

void test_raw_to_grams() {
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 100.0f, raw_to_grams(70000, 50000, 200.0f));
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, raw_to_grams(1, 1, 0.0f));             // hệ số 0 không chia cho 0
}

// ------------------------------------------------------------------ Pin
void test_battery_percent_curve() {
  TEST_ASSERT_EQUAL_INT(0, battery_percent(3000));
  TEST_ASSERT_EQUAL_INT(0, battery_percent(3300));
  TEST_ASSERT_EQUAL_INT(100, battery_percent(4200));
  TEST_ASSERT_EQUAL_INT(100, battery_percent(4350));
  TEST_ASSERT_EQUAL_INT(35, battery_percent(3700));
  int prev = -1;
  for (int mv = 3200; mv <= 4300; mv += 10) {                                  // đơn điệu không giảm
    int p = battery_percent((float)mv);
    TEST_ASSERT_TRUE(p >= prev);
    prev = p;
  }
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 3800.0f, battery_mv_from_pin(1900.0f, 2.0f));
}

void test_low_battery_hysteresis() {
  LowBatteryMonitor m;
  TEST_ASSERT_FALSE(m.update(50));
  TEST_ASSERT_FALSE(m.update(20));       // đúng 20 % chưa bật (đồng bộ với Backend: pin < 20)
  TEST_ASSERT_TRUE(m.update(19));
  TEST_ASSERT_TRUE(m.update(24));        // chưa đủ 25 % -> vẫn cảnh báo
  TEST_ASSERT_FALSE(m.update(25));
}

// ------------------------------------------------------------------ Nút, định thời
void test_button_short_long_and_debounce() {
  Button b(30, 2000);
  uint32_t t = 0;
  TEST_ASSERT_EQUAL_INT(Button::NONE, b.update(true, t));
  TEST_ASSERT_EQUAL_INT(Button::NONE, b.update(false, t + 10));                // nhiễu 10 ms: bỏ qua
  t = 100;
  b.update(true, t);
  b.update(true, t + 40);                                                      // ổn định
  Button::Event e = b.update(false, t + 300);        // nhả nút: cần ổn định >= 30 ms mới tính
  if (e == Button::NONE) e = b.update(false, t + 340);
  TEST_ASSERT_EQUAL_INT(Button::SHORT_PRESS, e);
  Button c(30, 2000);
  c.update(true, 0);
  c.update(true, 40);
  TEST_ASSERT_EQUAL_INT(Button::NONE, c.update(true, 1500));
  TEST_ASSERT_EQUAL_INT(Button::LONG_PRESS, c.update(true, 2100));
  TEST_ASSERT_EQUAL_INT(Button::NONE, c.update(true, 2600));                   // chỉ phát một lần
  c.update(false, 2700);
  TEST_ASSERT_EQUAL_INT(Button::NONE, c.update(false, 2800));                  // nhả sau LONG: không có SHORT
}

void test_interval_and_millis_rollover() {
  Interval iv(1000);
  TEST_ASSERT_TRUE(iv.due(5));                                                 // lần đầu: chạy ngay
  TEST_ASSERT_FALSE(iv.due(900));
  TEST_ASSERT_TRUE(iv.due(1005));
  Interval roll(100);
  TEST_ASSERT_TRUE(roll.due(0xFFFFFFF0u));
  TEST_ASSERT_FALSE(roll.due(0xFFFFFFF8u));
  TEST_ASSERT_TRUE(roll.due(0x00000060u));                                     // millis() tràn số 32 bit
}

void test_backoff() {
  Backoff b(500, 8000);
  TEST_ASSERT_EQUAL_UINT32(500, b.next());
  TEST_ASSERT_EQUAL_UINT32(1000, b.next());
  TEST_ASSERT_EQUAL_UINT32(2000, b.next());
  TEST_ASSERT_EQUAL_UINT32(4000, b.next());
  TEST_ASSERT_EQUAL_UINT32(8000, b.next());
  TEST_ASSERT_EQUAL_UINT32(8000, b.next());
  b.reset();
  TEST_ASSERT_EQUAL_UINT32(500, b.next());
}


// ------------------------------------------------------------------ Console & hiệu chuẩn
void test_parse_console() {
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::NONE, parse_console("").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::NONE, parse_console("   \r\n").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::HELP, parse_console("HELP").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::LOCK, parse_console("  Lock \r").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::END, parse_console("end").type);
  ConsoleCmd s = parse_console("scan 8934588012341\r\n");
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::SCAN, s.type);
  TEST_ASSERT_EQUAL_STRING("8934588012341", s.arg);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("scan").type);          // thiếu mã
  ConsoleCmd c = parse_console("cal 1000.5");
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::CAL, c.type);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 1000.5f, c.num);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("cal abc").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("cal -5").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("cal 0").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("cal 12x").type);
  ConsoleCmd w = parse_console("weight 750");
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::SIM_WEIGHT, w.type);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 750.0f, w.num);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, -1.0f, parse_console("WEIGHT auto").num);
  ConsoleCmd b = parse_console("battery 15");
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::SIM_BATTERY, b.type);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 15.0f, b.num);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("battery 150").type);   // ngoài 0..100
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("weight -3").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("weight").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("rm -rf /").type);
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console("averyveryverylongcommandword").type);
  char big[200];
  memset(big, 'a', 150); memcpy(big, "scan ", 5); big[150] = 0;
  TEST_ASSERT_EQUAL_INT(ConsoleCmd::UNKNOWN, parse_console(big).type);              // mã quá dài
}

void test_calibration_from_samples() {
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 420.0f, calibration_from_samples(1000, 1000 + 420000, 1000.0f));
  TEST_ASSERT_FLOAT_WITHIN(0.01f, -420.0f, calibration_from_samples(1000, 1000 - 420000, 1000.0f));   // đấu ngược dây
  TEST_ASSERT_FLOAT_WITHIN(0.0001f, 0.0f, calibration_from_samples(1000, 1050, 1000.0f));            // chưa đặt vật
  TEST_ASSERT_FLOAT_WITHIN(0.0001f, 0.0f, calibration_from_samples(1000, 900000, 0.0f));
  TEST_ASSERT_FLOAT_WITHIN(0.0001f, 0.0f, calibration_from_samples(1000, 900000, -3.0f));
}

// ------------------------------------------------------------------ SHA-256 / HMAC / ký message
static void hex32(const uint8_t* d, char out[65]) { hex_encode(d, 32, out); }

void test_sha256_vectors() {
  uint8_t d[32]; char h[65];
  sha256("", 0, d); hex32(d, h);
  TEST_ASSERT_EQUAL_STRING("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", h);
  sha256("abc", 3, d); hex32(d, h);
  TEST_ASSERT_EQUAL_STRING("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", h);
  const char* m = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";    // 56 byte: qua ranh giới padding
  sha256(m, strlen(m), d); hex32(d, h);
  TEST_ASSERT_EQUAL_STRING("248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1", h);
  // cập nhật từng mảnh nhỏ cho cùng kết quả
  Sha256 s;
  for (const char* p = m; *p; p++) s.update(p, 1);
  s.final(d); hex32(d, h);
  TEST_ASSERT_EQUAL_STRING("248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1", h);
}

void test_hmac_rfc4231_vectors() {
  uint8_t mac[32]; char h[65];
  uint8_t k1[20]; memset(k1, 0x0b, 20);
  hmac_sha256(k1, 20, "Hi There", 8, mac); hex32(mac, h);
  TEST_ASSERT_EQUAL_STRING("b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7", h);
  hmac_sha256((const uint8_t*)"Jefe", 4, "what do ya want for nothing?", 28, mac); hex32(mac, h);
  TEST_ASSERT_EQUAL_STRING("5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843", h);
  uint8_t k3[20], d3[50]; memset(k3, 0xaa, 20); memset(d3, 0xdd, 50);
  hmac_sha256(k3, 20, d3, 50, mac); hex32(mac, h);
  TEST_ASSERT_EQUAL_STRING("773ea91e36800e46854db8ebd09181a72959098b3ef8c122d9635514ced565fe", h);
  uint8_t k6[131]; memset(k6, 0xaa, 131);                                           // khoá dài hơn block -> băm trước
  const char* m6 = "Test Using Larger Than Block-Size Key - Hash Key First";
  hmac_sha256(k6, 131, m6, strlen(m6), mac); hex32(mac, h);
  TEST_ASSERT_EQUAL_STRING("60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54", h);
}

void test_hex_helpers() {
  uint8_t b[4];
  TEST_ASSERT_TRUE(hex_decode("00ff10Ab", b, 4));
  TEST_ASSERT_EQUAL_INT(0xab, b[3]);
  TEST_ASSERT_FALSE(hex_decode("00ff10", b, 4));      // sai độ dài
  TEST_ASSERT_FALSE(hex_decode("00ff10zz", b, 4));    // ký tự lạ
  TEST_ASSERT_FALSE(hex_decode(nullptr, b, 4));
  uint8_t x[3] = {1, 2, 3}, y[3] = {1, 2, 4};
  TEST_ASSERT_TRUE(ct_equal(x, x, 3));
  TEST_ASSERT_FALSE(ct_equal(x, y, 3));
}

static uint8_t KEY[32];
static void init_key() { for (int i = 0; i < 32; i++) KEY[i] = (uint8_t)(i * 7 + 1); }

void test_builders_sign_when_key_given() {
  init_key();
  Meta m{"11111111-2222-4333-8444-555555555555", "CART_004", "2026-11-07T10:30:00Z", KEY};
  char b[700];
  TEST_ASSERT_TRUE(build_scan(b, sizeof b, m, "s-1", "8934588012341", "ADD") > 0);
  const char* sv; size_t sn;
  TEST_ASSERT_TRUE(json_top_level(b, "sig", &sv, &sn));
  TEST_ASSERT_EQUAL_INT(66, sn);                                   // 64 hex + 2 dấu nháy
  TEST_ASSERT_EQUAL_INT(VERIFY_OK, verify_signed_payload(b, "scan", KEY));
  TEST_ASSERT_EQUAL_INT(VERIFY_BAD, verify_signed_payload(b, "event", KEY));      // chữ ký gắn với loại topic
  uint8_t other[32]; memset(other, 9, 32);
  TEST_ASSERT_EQUAL_INT(VERIFY_BAD, verify_signed_payload(b, "scan", other));
  // không khoá => không có sig
  Meta u{"11111111-2222-4333-8444-555555555555", "CART_004", "2026-11-07T10:30:00Z"};
  build_scan(b, sizeof b, u, "s-1", "8934588012341", "ADD");
  TEST_ASSERT_EQUAL_INT(VERIFY_MISSING, verify_signed_payload(b, "scan", KEY));
}

void test_verify_detects_tampering() {
  init_key();
  Meta m{"11111111-2222-4333-8444-555555555555", "CART_004", "2026-11-07T10:30:00Z", KEY};
  char b[700];
  build_ack(b, sizeof b, m, "cmd-1", "OK", "Đã khoá xe");
  TEST_ASSERT_EQUAL_INT(VERIFY_OK, verify_signed_payload(b, "ack", KEY));
  char t[700];
  strcpy(t, b); char* p = strstr(t, "\"OK\""); p[1] = 'N';                 // đổi kết quả
  TEST_ASSERT_EQUAL_INT(VERIFY_BAD, verify_signed_payload(t, "ack", KEY));
  strcpy(t, b); p = strstr(t, "CART_004"); p[7] = '5';                       // đổi cart_id
  TEST_ASSERT_EQUAL_INT(VERIFY_BAD, verify_signed_payload(t, "ack", KEY));
  strcpy(t, b); p = strstr(t, "10:30:00"); p[1] = '1';                       // đổi timestamp
  TEST_ASSERT_EQUAL_INT(VERIFY_BAD, verify_signed_payload(t, "ack", KEY));
  strcpy(t, b); p = strstr(t, "\"sig\":\""); p[7] = (p[7] == 'a') ? 'b' : 'a';  // đổi chữ ký
  TEST_ASSERT_EQUAL_INT(VERIFY_BAD, verify_signed_payload(t, "ack", KEY));
  // chèn thêm khoá "data" thứ hai ở cấp gốc để đánh lừa bộ phân tích: phải bị từ chối
  const char* dup = "{\"message_id\":\"m\",\"cart_id\":\"c\",\"timestamp\":\"t\",\"sig\":\"";
  char evil[400];
  snprintf(evil, sizeof evil, "%s%064d\",\"data\":{\"a\":1},\"data\":{\"a\":2}}", dup, 0);
  TEST_ASSERT_EQUAL_INT(VERIFY_BAD, verify_signed_payload(evil, "ack", KEY));
  TEST_ASSERT_EQUAL_INT(VERIFY_BAD, verify_signed_payload("{\"sig\":\"zz\"}", "ack", KEY));
  TEST_ASSERT_EQUAL_INT(VERIFY_MISSING, verify_signed_payload("{}", "ack", KEY));
  TEST_ASSERT_EQUAL_INT(VERIFY_MISSING, verify_signed_payload("rác", "ack", KEY));
}

void test_json_top_level() {
  const char* s; size_t n;
  const char* j = "{\"a\": \"x,}\" , \"data\" : { \"data\": 1, \"k\": [1,{\"z\":\"}\"}] } ,\"n\":-3.5e2}";
  TEST_ASSERT_TRUE(json_top_level(j, "data", &s, &n));
  TEST_ASSERT_TRUE(strncmp(s, "{ \"data\": 1, \"k\": [1,{\"z\":\"}\"}] }", n) == 0);   // khoá "data" lồng bên trong không bị nhầm
  TEST_ASSERT_TRUE(json_top_level(j, "n", &s, &n));
  TEST_ASSERT_EQUAL_INT(6, n);
  TEST_ASSERT_FALSE(json_top_level(j, "missing", &s, &n));
  TEST_ASSERT_FALSE(json_top_level("{\"a\":1,\"a\":2}", "a", &s, &n));                 // trùng khoá
  TEST_ASSERT_FALSE(json_top_level("{\"a\":", "a", &s, &n));                            // cụt
  TEST_ASSERT_FALSE(json_top_level("[1]", "a", &s, &n));
}

void test_timestamp_freshness() {
  long long t;
  TEST_ASSERT_TRUE(parse_iso8601("1970-01-01T00:00:00Z", &t));
  TEST_ASSERT_EQUAL_INT(0, t);
  TEST_ASSERT_TRUE(parse_iso8601("2026-11-07T10:30:00Z", &t));
  TEST_ASSERT_EQUAL_INT(1794047400LL, t);
  char back[21]; iso8601_utc(t, back);
  TEST_ASSERT_EQUAL_STRING("2026-11-07T10:30:00Z", back);                 // khớp bộ định dạng ngược
  TEST_ASSERT_TRUE(parse_iso8601("2024-02-29T23:59:59Z", &t));
  TEST_ASSERT_FALSE(parse_iso8601("2026-13-07T10:30:00Z", &t));
  TEST_ASSERT_FALSE(parse_iso8601("2026-11-07 10:30:00Z", &t));
  TEST_ASSERT_FALSE(parse_iso8601("2026-11-07T10:30:00+00:00", &t));
  TEST_ASSERT_FALSE(parse_iso8601(nullptr, &t));
  TEST_ASSERT_TRUE(timestamp_fresh("2026-11-07T10:30:00Z", 1794047400LL + 299, 300));
  TEST_ASSERT_TRUE(timestamp_fresh("2026-11-07T10:30:00Z", 1794047400LL - 299, 300));
  TEST_ASSERT_FALSE(timestamp_fresh("2026-11-07T10:30:00Z", 1794047400LL + 301, 300));
  TEST_ASSERT_FALSE(timestamp_fresh("2020-01-01T00:00:00Z", 1794047400LL, 300));
  TEST_ASSERT_FALSE(timestamp_fresh("rác", 1794047400LL, 300));
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_json_get_basic);
  RUN_TEST(test_json_key_inside_string_value_is_ignored);
  RUN_TEST(test_json_rejects_garbage_and_overflow);
  RUN_TEST(test_json_escape);
  RUN_TEST(test_iso8601);
  RUN_TEST(test_uuid4_format);
  RUN_TEST(test_build_messages_shape);
  RUN_TEST(test_build_overflow_returns_minus_one);
  RUN_TEST(test_build_escapes_user_text);
  RUN_TEST(test_parse_command_ok);
  RUN_TEST(test_parse_command_rejects_bad_input);
  RUN_TEST(test_session_and_lock_state_machine);
  RUN_TEST(test_lock_without_session_then_unlock);
  RUN_TEST(test_commands_are_idempotent);
  RUN_TEST(test_invalid_commands_fail);
  RUN_TEST(test_seen_ring_forgets_oldest);
  RUN_TEST(test_scan_decisions);
  RUN_TEST(test_scan_mode_reverts_after_one_scan);
  RUN_TEST(test_normalize_barcode);
  RUN_TEST(test_line_assembler_cr_terminated);
  RUN_TEST(test_line_assembler_idle_timeout_and_overflow);
  RUN_TEST(test_weight_filter_rejects_spike_and_smooths);
  RUN_TEST(test_weight_filter_deadband_and_non_negative);
  RUN_TEST(test_raw_to_grams);
  RUN_TEST(test_battery_percent_curve);
  RUN_TEST(test_low_battery_hysteresis);
  RUN_TEST(test_button_short_long_and_debounce);
  RUN_TEST(test_interval_and_millis_rollover);
  RUN_TEST(test_backoff);
  RUN_TEST(test_parse_console);
  RUN_TEST(test_calibration_from_samples);
  RUN_TEST(test_sha256_vectors);
  RUN_TEST(test_hmac_rfc4231_vectors);
  RUN_TEST(test_hex_helpers);
  RUN_TEST(test_builders_sign_when_key_given);
  RUN_TEST(test_verify_detects_tampering);
  RUN_TEST(test_json_top_level);
  RUN_TEST(test_timestamp_freshness);
  return UNITY_END();
}
