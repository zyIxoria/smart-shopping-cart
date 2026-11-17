// cartsec – SHA-256 / HMAC-SHA256 và ký/kiểm tra message MQTT (portable C++, không phụ thuộc mbedtls/Arduino).
// Thuật toán và định dạng khớp shared/security.py + shared/contract.py (Backend/Simulator):
//   sig = HMAC-SHA256(key, message_id "\n" cart_id "\n" timestamp "\n" kind "\n" data_raw)   (hex thường, 64 ký tự)
// `data_raw` là NGUYÊN VĂN chuỗi JSON của trường "data" như nằm trong payload – không chuẩn hoá lại.
#pragma once
#include <stddef.h>
#include <stdint.h>

namespace cartcore {

class Sha256 {
 public:
  Sha256() { init(); }
  void init();
  void update(const void* data, size_t len);
  void final(uint8_t out[32]);
 private:
  void block(const uint8_t* p);
  uint32_t h_[8];
  uint8_t buf_[64];
  uint64_t total_;
  size_t fill_;
};

class Hmac256 {
 public:
  Hmac256(const uint8_t* key, size_t key_len) { init(key, key_len); }
  void init(const uint8_t* key, size_t key_len);
  void update(const void* data, size_t len) { inner_.update(data, len); }
  void final(uint8_t out[32]);
 private:
  Sha256 inner_;
  uint8_t okey_[64];
};

void sha256(const void* data, size_t len, uint8_t out[32]);
void hmac_sha256(const uint8_t* key, size_t key_len, const void* msg, size_t msg_len, uint8_t out[32]);

bool hex_decode(const char* hex, uint8_t* out, size_t out_len);   // đúng 2*out_len ký tự hex; false nếu sai
void hex_encode(const uint8_t* in, size_t len, char* out);        // ghi 2*len + 1 byte (có '\0')
bool ct_equal(const uint8_t* a, const uint8_t* b, size_t n);      // so sánh thời gian không đổi

// Ký: ghi 64 ký tự hex + '\0' vào sig_hex[65].
void sign_message(const uint8_t key[32], const char* message_id, const char* cart_id, const char* timestamp,
                  const char* kind, const char* data_raw, size_t data_len, char sig_hex[65]);

// ----- JSON mức gốc (dùng để lấy đúng chuỗi "data" và kiểm tra chữ ký)
// Tìm giá trị của khoá `key` ở CẤP GỐC của object. false nếu thiếu, trùng lặp, hoặc JSON hỏng.
bool json_top_level(const char* json, const char* key, const char** start, size_t* len);

enum VerifyResult { VERIFY_OK = 0, VERIFY_MISSING = 1, VERIFY_BAD = 2 };
// Kiểm tra chữ ký của payload thô (ví dụ lệnh từ Backend). kind: "command", ...
VerifyResult verify_signed_payload(const char* payload, const char* kind, const uint8_t key[32]);

// ----- Chống phát lại: tuổi message
bool parse_iso8601(const char* s, long long* epoch_s);            // "YYYY-MM-DDTHH:MM:SSZ"
// true nếu |now - timestamp| <= max_skew_s. Chỉ gọi khi đồng hồ đã đồng bộ (time_valid).
bool timestamp_fresh(const char* ts, long long now_epoch_s, long max_skew_s);

}  // namespace cartcore
