// Công cụ kiểm tra chéo firmware <-> contract Python (tests/unit/test_firmware_protocol.py).
//   protocol_tool build [KEYHEX]            : in mỗi dòng "<kind>\t<payload JSON>" do cartcore dựng (có KEYHEX => ký HMAC)
//   protocol_tool command CART_ID [KEYHEX [NOW_EPOCH]] : đọc mỗi dòng stdin là 1 payload command, in
//        "<type>\t<command_id>\t<session|->\t<status>\t<ack JSON>"; có KEYHEX thì kiểm chữ ký (+ độ mới nếu có NOW_EPOCH)
//        và in REJECT_UNSIGNED / REJECT_SIG / REJECT_STALE khi bị từ chối. Ngoài ra: protocol_tool hmac KEYHEX MSG
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <iostream>
#include <string>

#include "cartcore.h"
#include "cartsec.h"

using namespace cartcore;

int main(int argc, char** argv) {
  uint8_t key[32];
  bool have_key = false;
  int key_arg = (argc >= 2 && !strcmp(argv[1], "build")) ? 2 : (argc >= 2 && !strcmp(argv[1], "command")) ? 3 : -1;
  if (key_arg > 0 && argc > key_arg) {
    if (!hex_decode(argv[key_arg], key, 32)) { fprintf(stderr, "KEYHEX phải là 64 ký tự hex\n"); return 2; }
    have_key = true;
  }
  Meta m{"0b8f6a3e-6c1d-4f6b-9a52-3c2d1e0f9a88", "CART_004", "2026-11-07T10:30:00Z", have_key ? key : nullptr};
  char b[700];
  if (argc >= 4 && !strcmp(argv[1], "hmac")) {       // hmac KEYHEX MSG -> hex
    uint8_t k[32], mac[32]; char h[65];
    if (!hex_decode(argv[2], k, 32)) return 2;
    hmac_sha256(k, 32, argv[3], strlen(argv[3]), mac); hex_encode(mac, 32, h); printf("%s\n", h);
    return 0;
  }
  if (argc >= 2 && !strcmp(argv[1], "build")) {
    build_heartbeat(b, sizeof b, m, 125, "IN_USE");                 printf("heartbeat\t%s\n", b);
    build_telemetry(b, sizeof b, m, 842.5, 76.0, "IN_USE", true, true);  printf("telemetry\t%s\n", b);
    build_telemetry(b, sizeof b, m, 0.0, 12.0, "AVAILABLE", true, true); printf("telemetry\t%s\n", b);
    build_scan(b, sizeof b, m, "5d3c1f7a-0000-4000-8000-000000000001", "8934588012341", "ADD");    printf("scan\t%s\n", b);
    build_scan(b, sizeof b, m, "5d3c1f7a-0000-4000-8000-000000000002", "ABC-123", "REMOVE");      printf("scan\t%s\n", b);
    build_event(b, sizeof b, m, "SCAN_REJECTED", "Xe đang bị khoá \"test\"");                   printf("event\t%s\n", b);
    build_ack(b, sizeof b, m, "cmd-1", "OK", "Đã khoá xe");                                      printf("ack\t%s\n", b);
    build_ack(b, sizeof b, m, "cmd-2", "FAILED", "Lệnh không hỗ trợ");                           printf("ack\t%s\n", b);
    return 0;
  }
  if (argc >= 3 && !strcmp(argv[1], "command")) {
    CartLogic logic;
    std::string line;
    long long now = argc >= 5 ? atoll(argv[4]) : 0;
    while (std::getline(std::cin, line)) {
      Command c;
      if (have_key) {
        VerifyResult v = verify_signed_payload(line.c_str(), "command", key);
        if (v == VERIFY_MISSING) { printf("REJECT_UNSIGNED\n"); continue; }
        if (v == VERIFY_BAD) { printf("REJECT_SIG\n"); continue; }
        char ts[40];
        if (now > 0 && (!json_get_string(line.c_str(), "timestamp", ts, sizeof ts) || !timestamp_fresh(ts, now, 300))) {
          printf("REJECT_STALE\n");
          continue;
        }
      }
      if (!parse_command(line.c_str(), argv[2], &c)) { printf("REJECT\n"); continue; }
      AckInfo a = logic.handle(c);
      build_ack(b, sizeof b, m, c.command_id, a.ok ? "OK" : "FAILED", a.message);
      char sid[24] = "-";
      if (c.has_session_id) snprintf(sid, sizeof sid, "%ld", c.session_id);
      printf("%s\t%s\t%s\t%s\t%s\n", c.type, c.command_id, sid, status_name(logic.status()), b);
    }
    return 0;
  }
  fprintf(stderr, "usage: protocol_tool build | command CART_ID\n");
  return 2;
}
