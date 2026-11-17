"""Kiểm tra gói mô phỏng Wokwi + cấu hình PlatformIO (không cần Wokwi/PlatformIO).

Giới hạn: đây là kiểm tra TĨNH. Tên chân linh kiện đối chiếu với docs.wokwi.com (chân ESP32 DevKit V1 lấy từ wokwi-boards),
cú pháp C++ kiểm tra bằng g++ với header Arduino GIẢ (firmware/tools/arduino_stubs) – KHÔNG thay cho một lần build thật.
"""
import configparser
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FW = ROOT / "firmware"

# Tên chân hợp lệ của từng loại linh kiện (docs.wokwi.com/parts/<type>, wokwi-boards/boards/esp32-devkit-v1/board.json)
PINS = {
    "wokwi-esp32-devkit-v1": {"EN", "VN", "VP", "D34", "D35", "D32", "D33", "D25", "D26", "D27", "D14", "D12", "D13", "GND.2",
                              "VIN", "3V3", "GND.1", "D15", "D2", "D4", "RX2", "TX2", "D5", "D18", "D19", "D21", "RX0", "TX0",
                              "D22", "D23"},
    "board-ssd1306": {"GND", "VCC", "SCL", "SDA"},
    "wokwi-hx711": {"VCC", "DT", "SCK", "GND"},
    "wokwi-buzzer": {"1", "2"},
    "wokwi-led": {"A", "C"},
    "wokwi-resistor": {"1", "2"},
    "wokwi-pushbutton": {"1.l", "1.r", "2.l", "2.r"},
}
SERIAL_PINS = {"$serialMonitor": {"RX", "TX"}}


def _defs(path):
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"^#define\s+(PIN_\w+)\s+(\d+)", path.read_text(), re.M)}


def _diagram(path=FW / "diagram.json"):
    return json.loads(path.read_text(encoding="utf-8"))


def test_diagram_parts_and_pins_exist():
    d = _diagram()
    parts = {p["id"]: p["type"] for p in d["parts"]}
    assert len(parts) == len(d["parts"]), "id linh kiện trùng"
    for t in parts.values():
        assert t in PINS, f"loại linh kiện chưa được đối chiếu với tài liệu Wokwi: {t}"
    for a, b, *_ in d["connections"]:
        for end in (a, b):
            comp, pin = end.split(":", 1)
            if comp in SERIAL_PINS:
                assert pin in SERIAL_PINS[comp], end
            else:
                assert comp in parts, f"{end}: không có linh kiện {comp}"
                assert pin in PINS[parts[comp]], f"{end}: {parts[comp]} không có chân {pin}"


def test_diagram_gpio_matches_pins_h():
    """Dây trong sơ đồ phải khớp include/pins.h – đổi chân ở một nơi mà quên nơi kia là lỗi dễ gặp."""
    pins = _defs(FW / "include" / "pins.h")
    d = _diagram()
    links = {}
    for a, b, *_ in d["connections"]:
        links.setdefault(a, set()).add(b)
        links.setdefault(b, set()).add(a)

    def esp_pin_of(part_pin, via=None):
        """GPIO của ESP32 nối (trực tiếp hoặc qua một điện trở) tới chân linh kiện."""
        for other in links.get(part_pin, ()):
            if other.startswith("esp:"):
                return other[4:]
            if via and other.split(":")[0] == via:
                res = other.split(":")[0]
                for o2 in links.get(f"{res}:{'2' if other.endswith(':1') else '1'}", ()):
                    if o2.startswith("esp:"):
                        return o2[4:]
        return None

    expect = {
        ("oled:SDA", None): "PIN_I2C_SDA", ("oled:SCL", None): "PIN_I2C_SCL",
        ("hx711:DT", None): "PIN_HX711_DT", ("hx711:SCK", None): "PIN_HX711_SCK",
        ("bz1:2", None): "PIN_BUZZER",
        ("ledG:A", "rG"): "PIN_LED_GREEN", ("ledR:A", "rR"): "PIN_LED_RED",
        ("btnMode:1.l", None): "PIN_BTN_MODE", ("btnTare:1.l", None): "PIN_BTN_TARE",
    }
    for (pp, via), name in expect.items():
        assert esp_pin_of(pp, via) == f"D{pins[name]}", f"{pp} phải nối D{pins[name]} ({name})"
    # LED qua điện trở: A -> điện trở -> ESP
    assert "esp:D26" in links["rG:1"] and "ledG:A" in links["rG:2"]
    # Mọi linh kiện đều có đường về GND
    for comp in ("oled", "hx711", "bz1", "ledG", "ledR", "btnMode", "btnTare"):
        assert any(o.startswith("esp:GND") for k, v in links.items() if k.startswith(comp + ":") for o in v), f"{comp} thiếu GND"


def test_wokwi_toml_points_to_existing_env():
    toml = (FW / "wokwi.toml").read_text()
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(FW / "platformio.ini", encoding="utf-8")
    envs = {s.split(":", 1)[1] for s in ini.sections() if s.startswith("env:")}
    m = re.search(r"firmware\s*=\s*'\.pio/build/(\w+)/firmware\.bin'", toml)
    e = re.search(r"elf\s*=\s*'\.pio/build/(\w+)/firmware\.elf'", toml)
    assert m and e and m.group(1) == e.group(1) and m.group(1) in envs
    assert "rfc2217ServerPort = 4000" in toml


def test_platformio_envs_complete():
    ini = configparser.ConfigParser(interpolation=None)
    ini.read(FW / "platformio.ini", encoding="utf-8")
    for s in ini.sections():
        if not s.startswith("env:") or s == "env:native":
            continue
        sec = ini[s]
        assert sec["framework"] == "arduino" and sec["board"] == "esp32dev", s
        libs = sec["lib_deps"]
        for lib in ("PubSubClient", "HX711", "Adafruit SSD1306", "Adafruit GFX"):
            assert lib in libs, f"{s} thiếu {lib}"
    sims = {"esp32dev_sim": ["STANDALONE_MODE=1"], "esp32dev_sim_bridge": ["STANDALONE_MODE=1", "SERIAL_BRIDGE=1"],
            "esp32dev_wokwi_online": ["WOKWI_ONLINE=1"]}
    for env, flags in sims.items():
        bf = ini[f"env:{env}"]["build_flags"]
        for f in flags + ["BATTERY_ENABLED=0", "HX711_COUNTS_PER_GRAM=0.42f"]:
            assert f"-D{f}" in bf, f"{env} thiếu -D{f}"


def test_wokwi_web_package_in_sync():
    r = subprocess.run([sys.executable, str(FW / "tools" / "make_wokwi_web.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_wokwi_web_package_content():
    for mode in ("standalone", "online"):
        d = FW / "wokwi-web" / mode
        for f in ("sketch.ino", "smartcart.cpp", "cartcore.h", "cartcore.cpp", "cartsec.h", "cartsec.cpp", "pins.h",
                  "diagram.json", "libraries.txt"):
            assert (d / f).is_file(), f"{mode}/{f}"
        # cờ build phải đứng TRƯỚC #include đầu tiên
        src = (d / "smartcart.cpp").read_text()
        first_inc = src.index("#include")
        assert "#define BATTERY_ENABLED 0" in src[:first_inc] and "#define HX711_COUNTS_PER_GRAM 0.42f" in src[:first_inc]
        assert ("#define STANDALONE_MODE 1" if mode == "standalone" else "#define WOKWI_ONLINE 1") in src[:first_inc]
        libs = (d / "libraries.txt").read_text()
        assert "PubSubClient" in libs and "Adafruit SSD1306" in libs and "HX711" in libs
        assert _diagram(d / "diagram.json") == _diagram()
    assert (FW / "wokwi-web" / "online" / "wokwi_online.h").is_file()
    assert not (FW / "wokwi-web" / "standalone" / "wokwi_online.h").exists()


# ------------------------------------------------------------------ cú pháp C++ với header giả
needs_gxx = pytest.mark.skipif(shutil.which("g++") is None, reason="cần g++")
STUBS = FW / "tools" / "arduino_stubs"
BASE = ["g++", "-std=gnu++11", "-fsyntax-only", "-Wall", "-Wextra", "-Wno-unused-function", f"-I{STUBS}",
        f"-I{FW / 'lib' / 'cartcore'}", f"-I{FW / 'include'}"]


def _syntax(args, srcs):
    r = subprocess.run(BASE + args + [str(s) for s in srcs], capture_output=True, text=True)
    assert r.returncode == 0 and "warning" not in r.stderr, r.stderr[:2000]


SIM = ["-DBATTERY_ENABLED=0", "-DHX711_COUNTS_PER_GRAM=0.42f"]


@needs_gxx
@pytest.mark.parametrize("flags", [
    ["-DSTANDALONE_MODE=1"],
    ["-DSTANDALONE_MODE=1"] + SIM,
    ["-DSTANDALONE_MODE=1", "-DSERIAL_BRIDGE=1"] + SIM,
    ["-DWOKWI_ONLINE=1"] + SIM,
], ids=["standalone", "sim", "sim_bridge", "wokwi_online"])
def test_main_cpp_syntax_sim_envs(flags):
    _syntax(flags, [FW / "src" / "main.cpp"])


@needs_gxx
def test_main_cpp_syntax_real_env_and_secure(tmp_path):
    inc = tmp_path / "inc"
    inc.mkdir()
    shutil.copy(FW / "include" / "cart_config.example.h", inc / "cart_config.h")
    _syntax([f"-I{inc}"], [FW / "src" / "main.cpp"])                       # esp32dev (không bảo mật)
    sys.path.insert(0, str(ROOT))
    from tools import provision
    for tls in ([False, True] if shutil.which("openssl") else [False]):
        out = tmp_path / f"sec{int(tls)}"
        provision.provision(out, ["CART_004"], tls=tls)
        shutil.copy(out / "firmware" / "CART_004" / "cart_secrets.h", inc / "cart_secrets.h")
        _syntax([f"-I{inc}"], [FW / "src" / "main.cpp"])                   # esp32dev + cart_secrets.h (có/không TLS)


@needs_gxx
@pytest.mark.parametrize("mode", ["standalone", "online"])
def test_wokwi_web_sketch_syntax(mode):
    d = FW / "wokwi-web" / mode
    r = subprocess.run(["g++", "-std=gnu++11", "-fsyntax-only", "-Wall", "-Wextra", "-Wno-unused-function", f"-I{STUBS}", f"-I{d}",
                        str(d / "smartcart.cpp"), str(d / "cartcore.cpp"), str(d / "cartsec.cpp")], capture_output=True, text=True)
    assert r.returncode == 0 and "warning" not in r.stderr, r.stderr[:2000]
