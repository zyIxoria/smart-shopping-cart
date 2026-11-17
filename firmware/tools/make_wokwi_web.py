#!/usr/bin/env python3
"""Sinh gói dự án để dán/tải lên https://wokwi.com (Wokwi chạy trong trình duyệt, TỰ BIÊN DỊCH – không cần PlatformIO).

    python3 firmware/tools/make_wokwi_web.py            # ghi firmware/wokwi-web/{standalone,online}/
    python3 firmware/tools/make_wokwi_web.py --check    # chỉ kiểm tra thư mục đã sinh còn khớp nguồn (exit 1 nếu lệch)

Mỗi thư mục chứa: sketch.ino (rỗng – chỉ chú thích), smartcart.cpp (= src/main.cpp + cờ build) (+ các file lõi), diagram.json, libraries.txt.
Mã nguồn lấy từ firmware/src + firmware/lib/cartcore nên luôn đồng bộ với bản PlatformIO. KHÔNG sửa tay thư mục wokwi-web/.
Chế độ cầu nối Serial↔MQTT không có ở bản web (cần cổng RFC2217 của Wokwi cho VS Code).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

FW = Path(__file__).resolve().parent.parent
OUT = FW / "wokwi-web"

LIBS = ["PubSubClient", "HX711 Arduino Library", "Adafruit SSD1306", "Adafruit GFX Library", "Adafruit BusIO"]

MODES = {
    "standalone": {
        "title": "Chạy độc lập (không liên kết web)",
        "defines": ["STANDALONE_MODE 1", "BATTERY_ENABLED 0", "HX711_COUNTS_PER_GRAM 0.42f"],
        "extra": [],
    },
    "online": {
        "title": "Liên kết hệ thống web qua broker MQTT công cộng (Wi-Fi ảo Wokwi-GUEST)",
        "defines": ["WOKWI_ONLINE 1", "BATTERY_ENABLED 0", "HX711_COUNTS_PER_GRAM 0.42f"],
        "extra": ["include/wokwi_online.h"],
    },
}

CORE = ["lib/cartcore/cartcore.h", "lib/cartcore/cartcore.cpp", "lib/cartcore/cartsec.h", "lib/cartcore/cartsec.cpp", "include/pins.h"]


def build(mode: str) -> dict[str, str]:
    m = MODES[mode]
    files: dict[str, str] = {}
    files["sketch.ino"] = (
        f"// Smart Cart – {m['title']}\n"
        "// Toàn bộ mã nằm ở smartcart.cpp (+ cartcore.*, cartsec.*, pins.h) cùng thư mục; file này để trống có chủ đích.\n"
        "// Sinh bởi firmware/tools/make_wokwi_web.py – đừng sửa tay, hãy sửa firmware/src rồi sinh lại.\n"
    )
    main = (FW / "src/main.cpp").read_text(encoding="utf-8")
    # cờ build của PlatformIO (-D...) thay bằng #define ở đầu file; phải đứng TRƯỚC mọi #include
    head = "".join(f"#define {d}\n" for d in m["defines"])
    files["smartcart.cpp"] = f"// === Cờ build (tương đương build_flags của env PlatformIO) ===\n{head}// === Hết cờ build ===\n{main}"
    for rel in CORE + m["extra"]:
        files[Path(rel).name] = (FW / rel).read_text(encoding="utf-8")
    files["diagram.json"] = (FW / "diagram.json").read_text(encoding="utf-8")
    files["libraries.txt"] = "# Thư viện (tên theo Arduino Library Manager)\n" + "\n".join(LIBS) + "\n"
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    bad = 0
    for mode in MODES:
        for name, text in build(mode).items():
            p = OUT / mode / name
            if a.check:
                if not p.exists() or p.read_text(encoding="utf-8") != text:
                    print("LỆCH:", p.relative_to(FW)); bad += 1
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
    if a.check:
        print("wokwi-web khớp nguồn" if not bad else f"{bad} file lệch – chạy lại make_wokwi_web.py")
        return 1 if bad else 0
    print(f"Đã sinh {OUT}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
