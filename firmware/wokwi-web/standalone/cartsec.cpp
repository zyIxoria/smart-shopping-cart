#include "cartsec.h"

#include <string.h>

namespace cartcore {

// =============================================================== SHA-256 (FIPS 180-4)
static const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01,
    0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08,
    0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

static inline uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

void Sha256::init() {
  static const uint32_t H0[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
  memcpy(h_, H0, sizeof h_);
  total_ = 0;
  fill_ = 0;
}

void Sha256::block(const uint8_t* p) {
  uint32_t w[64];
  for (int i = 0; i < 16; i++)
    w[i] = ((uint32_t)p[i * 4] << 24) | ((uint32_t)p[i * 4 + 1] << 16) | ((uint32_t)p[i * 4 + 2] << 8) | p[i * 4 + 3];
  for (int i = 16; i < 64; i++) {
    uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
    uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
    w[i] = w[i - 16] + s0 + w[i - 7] + s1;
  }
  uint32_t a = h_[0], b = h_[1], c = h_[2], d = h_[3], e = h_[4], f = h_[5], g = h_[6], h = h_[7];
  for (int i = 0; i < 64; i++) {
    uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
    uint32_t ch = (e & f) ^ (~e & g);
    uint32_t t1 = h + S1 + ch + K[i] + w[i];
    uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
    uint32_t mj = (a & b) ^ (a & c) ^ (b & c);
    uint32_t t2 = S0 + mj;
    h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
  }
  h_[0] += a; h_[1] += b; h_[2] += c; h_[3] += d; h_[4] += e; h_[5] += f; h_[6] += g; h_[7] += h;
}

void Sha256::update(const void* data, size_t len) {
  const uint8_t* p = (const uint8_t*)data;
  total_ += len;
  while (len) {
    size_t n = 64 - fill_;
    if (n > len) n = len;
    memcpy(buf_ + fill_, p, n);
    fill_ += n; p += n; len -= n;
    if (fill_ == 64) { block(buf_); fill_ = 0; }
  }
}

void Sha256::final(uint8_t out[32]) {
  uint64_t bits = total_ * 8;
  uint8_t pad = 0x80;
  update(&pad, 1);
  uint8_t z = 0;
  while (fill_ != 56) update(&z, 1);
  uint8_t len[8];
  for (int i = 0; i < 8; i++) len[i] = (uint8_t)(bits >> (56 - 8 * i));
  update(len, 8);
  for (int i = 0; i < 8; i++) {
    out[i * 4] = (uint8_t)(h_[i] >> 24); out[i * 4 + 1] = (uint8_t)(h_[i] >> 16);
    out[i * 4 + 2] = (uint8_t)(h_[i] >> 8); out[i * 4 + 3] = (uint8_t)h_[i];
  }
}

void sha256(const void* data, size_t len, uint8_t out[32]) {
  Sha256 s;
  s.update(data, len);
  s.final(out);
}

// =============================================================== HMAC-SHA256 (RFC 2104)
void Hmac256::init(const uint8_t* key, size_t key_len) {
  uint8_t k[64];
  memset(k, 0, sizeof k);
  if (key_len > 64) sha256(key, key_len, k); else if (key_len) memcpy(k, key, key_len);
  uint8_t ipad[64];
  for (int i = 0; i < 64; i++) { ipad[i] = k[i] ^ 0x36; okey_[i] = k[i] ^ 0x5c; }
  inner_.init();
  inner_.update(ipad, 64);
}

void Hmac256::final(uint8_t out[32]) {
  uint8_t ih[32];
  inner_.final(ih);
  Sha256 o;
  o.update(okey_, 64);
  o.update(ih, 32);
  o.final(out);
}

void hmac_sha256(const uint8_t* key, size_t key_len, const void* msg, size_t msg_len, uint8_t out[32]) {
  Hmac256 h(key, key_len);
  h.update(msg, msg_len);
  h.final(out);
}

// =============================================================== hex & so sánh
static int hexval(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

bool hex_decode(const char* hex, uint8_t* out, size_t out_len) {
  if (!hex || strlen(hex) != out_len * 2) return false;
  for (size_t i = 0; i < out_len; i++) {
    int a = hexval(hex[2 * i]), b = hexval(hex[2 * i + 1]);
    if (a < 0 || b < 0) return false;
    out[i] = (uint8_t)((a << 4) | b);
  }
  return true;
}

void hex_encode(const uint8_t* in, size_t len, char* out) {
  static const char* D = "0123456789abcdef";
  for (size_t i = 0; i < len; i++) { out[2 * i] = D[in[i] >> 4]; out[2 * i + 1] = D[in[i] & 15]; }
  out[2 * len] = 0;
}

bool ct_equal(const uint8_t* a, const uint8_t* b, size_t n) {
  uint8_t d = 0;
  for (size_t i = 0; i < n; i++) d |= (uint8_t)(a[i] ^ b[i]);
  return d == 0;
}

// =============================================================== ký message
void sign_message(const uint8_t key[32], const char* message_id, const char* cart_id, const char* timestamp,
                  const char* kind, const char* data_raw, size_t data_len, char sig_hex[65]) {
  Hmac256 h(key, 32);
  h.update(message_id, strlen(message_id)); h.update("\n", 1);
  h.update(cart_id, strlen(cart_id));       h.update("\n", 1);
  h.update(timestamp, strlen(timestamp));   h.update("\n", 1);
  h.update(kind, strlen(kind));             h.update("\n", 1);
  h.update(data_raw, data_len);
  uint8_t mac[32];
  h.final(mac);
  hex_encode(mac, 32, sig_hex);
}

// =============================================================== JSON mức gốc
static const char* skip_ws(const char* p) {
  while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n') p++;
  return p;
}

// p trỏ vào '"'; trả con trỏ ngay sau dấu nháy đóng, hoặc nullptr
static const char* skip_string(const char* p) {
  p++;
  while (*p) {
    if (*p == '\\') { if (!p[1]) return nullptr; p += 2; continue; }
    if (*p == '"') return p + 1;
    p++;
  }
  return nullptr;
}

static const char* skip_value(const char* p) {
  if (*p == '"') return skip_string(p);
  if (*p == '{' || *p == '[') {
    int depth = 0;
    while (*p) {
      if (*p == '"') { p = skip_string(p); if (!p) return nullptr; continue; }
      if (*p == '{' || *p == '[') depth++;
      else if (*p == '}' || *p == ']') { if (--depth == 0) return p + 1; }
      p++;
    }
    return nullptr;
  }
  const char* s = p;
  while (*p && !strchr(",}] \t\r\n", *p)) p++;
  return p == s ? nullptr : p;
}

bool json_top_level(const char* json, const char* key, const char** start, size_t* len) {
  const char* p = skip_ws(json);
  if (*p != '{') return false;
  p++;
  size_t klen = strlen(key);
  bool found = false;
  for (;;) {
    p = skip_ws(p);
    if (*p == '}') return found;
    if (*p != '"') return false;
    const char* ks = p + 1;
    const char* ke = skip_string(p);
    if (!ke) return false;
    size_t kl = (size_t)(ke - 1 - ks);
    p = skip_ws(ke);
    if (*p != ':') return false;
    p = skip_ws(p + 1);
    const char* vs = p;
    const char* ve = skip_value(p);
    if (!ve) return false;
    if (kl == klen && memcmp(ks, key, klen) == 0) {
      if (found) return false;                     // khoá trùng lặp -> từ chối
      found = true;
      *start = vs;
      *len = (size_t)(ve - vs);
    }
    p = skip_ws(ve);
    if (*p == ',') p++;
    else if (*p != '}') return false;
  }
}

// lấy chuỗi đơn giản (không escape) ở cấp gốc
static bool top_string(const char* json, const char* key, char* out, size_t out_size) {
  const char* s; size_t n;
  if (!json_top_level(json, key, &s, &n) || n < 2 || s[0] != '"' || s[n - 1] != '"') return false;
  n -= 2;
  if (n >= out_size) return false;
  for (size_t i = 0; i < n; i++) if (s[1 + i] == '\\') return false;
  memcpy(out, s + 1, n);
  out[n] = 0;
  return true;
}

VerifyResult verify_signed_payload(const char* payload, const char* kind, const uint8_t key[32]) {
  char sig[80], mid[80], cart[48], ts[32];
  const char* sv; size_t sn;
  if (!json_top_level(payload, "sig", &sv, &sn)) return VERIFY_MISSING;
  if (!top_string(payload, "sig", sig, sizeof sig) || strlen(sig) != 64) return VERIFY_BAD;
  const char* data; size_t dlen;
  if (!json_top_level(payload, "data", &data, &dlen)) return VERIFY_BAD;
  if (!top_string(payload, "message_id", mid, sizeof mid) || !top_string(payload, "cart_id", cart, sizeof cart) ||
      !top_string(payload, "timestamp", ts, sizeof ts))
    return VERIFY_BAD;
  char want[65];
  sign_message(key, mid, cart, ts, kind, data, dlen, want);
  uint8_t a[32], b[32];
  if (!hex_decode(want, a, 32) || !hex_decode(sig, b, 32)) return VERIFY_BAD;
  return ct_equal(a, b, 32) ? VERIFY_OK : VERIFY_BAD;
}

// =============================================================== thời gian
static long long days_from_civil(long long y, unsigned m, unsigned d) {
  y -= m <= 2;
  long long era = (y >= 0 ? y : y - 399) / 400;
  unsigned yoe = (unsigned)(y - era * 400);
  unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
  unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  return era * 146097 + (long long)doe - 719468;
}

bool parse_iso8601(const char* s, long long* epoch_s) {
  if (!s || strlen(s) != 20 || s[4] != '-' || s[7] != '-' || s[10] != 'T' || s[13] != ':' || s[16] != ':' || s[19] != 'Z') return false;
  int v[6]; const int pos[6] = {0, 5, 8, 11, 14, 17}, w[6] = {4, 2, 2, 2, 2, 2};
  for (int i = 0; i < 6; i++) {
    int x = 0;
    for (int j = 0; j < w[i]; j++) {
      char c = s[pos[i] + j];
      if (c < '0' || c > '9') return false;
      x = x * 10 + (c - '0');
    }
    v[i] = x;
  }
  if (v[1] < 1 || v[1] > 12 || v[2] < 1 || v[2] > 31 || v[3] > 23 || v[4] > 59 || v[5] > 60) return false;
  *epoch_s = days_from_civil(v[0], (unsigned)v[1], (unsigned)v[2]) * 86400LL + v[3] * 3600 + v[4] * 60 + v[5];
  return true;
}

bool timestamp_fresh(const char* ts, long long now_epoch_s, long max_skew_s) {
  long long t;
  if (!parse_iso8601(ts, &t)) return false;
  long long d = now_epoch_s - t;
  if (d < 0) d = -d;
  return d <= max_skew_s;
}

}  // namespace cartcore
