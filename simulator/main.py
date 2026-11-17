"""Chạy Simulator:  python -m simulator.main [--carts 3] [--auto] [--no-cli]"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import threading

from simulator.cart import SmartCart
from simulator.cli import SimShell
from simulator.config import SimConfig
from simulator.control import ControlServer
from simulator.scenarios import AutoShopper


def build_carts(cfg: SimConfig) -> list[SmartCart]:
    catalog = cfg.catalog()
    return [SmartCart(cid, cfg, catalog) for cid in cfg.cart_ids()]


def main() -> None:
    ap = argparse.ArgumentParser(description="Smart Cart Simulator")
    ap.add_argument("--carts", type=int, help="số xe (mặc định 3)")
    ap.add_argument("--host", help="MQTT host")
    ap.add_argument("--port", type=int, help="MQTT port")
    ap.add_argument("--control-port", type=int, default=int(os.getenv("SIM_CONTROL_PORT", 8090)),
                    help="cổng API điều khiển cho trang web /simulator (0 = tắt)")
    ap.add_argument("--auto", action="store_true", help="tự động quét hàng ngẫu nhiên khi xe đang IN_USE")
    ap.add_argument("--no-cli", action="store_true", help="không mở CLI (chạy nền, dùng trong Docker)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO if a.verbose or a.no_cli else logging.WARNING,
                        format="%(asctime)s %(name)s: %(message)s")
    cfg = SimConfig()
    if a.carts:
        cfg.cart_count = a.carts
    if a.host:
        cfg.mqtt_host = a.host
    if a.port:
        cfg.mqtt_port = a.port
    carts = build_carts(cfg)
    for c in carts:
        c.start()
    control = None
    if a.control_port:
        try:
            control = ControlServer(carts, os.getenv("SIM_CONTROL_HOST", "127.0.0.1"), a.control_port).start()
            print(f"Giao diện điều khiển xe: mở trang /simulator (API http://{control.host}:{control.port}/sim/carts)")
        except OSError as e:
            print(f"Không mở được cổng điều khiển {a.control_port}: {e} (bỏ qua, vẫn dùng CLI)")
    auto = AutoShopper(carts) if a.auto else None
    if auto:
        auto.start()
    print(f"Đã khởi động {len(carts)} xe -> MQTT {cfg.mqtt_host}:{cfg.mqtt_port}")
    try:
        if a.no_cli:
            threading.Event().wait()
        else:
            SimShell(carts, auto).cmdloop()
    except KeyboardInterrupt:
        pass
    finally:
        if auto:
            auto.stop()
        if control:
            control.stop()
        for c in carts:
            c.stop()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    main()
