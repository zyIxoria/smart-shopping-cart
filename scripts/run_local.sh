#!/usr/bin/env bash
# Chạy toàn bộ hệ thống cục bộ KHÔNG cần Docker/Mosquitto:
#   dev broker (cổng 1883) + Backend (8000, WS 8081) + Simulator (3 xe, nền).
# Nếu máy bạn có Mosquitto, bỏ dòng dev_broker và trỏ MQTT_HOST/MQTT_PORT tới nó.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"
# Đăng nhập quản trị: KHÔNG dùng mật khẩu mặc định cố định. Không đặt ADMIN_PASSWORD thì sinh ngẫu nhiên cho lần chạy này.
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(python -c 'import secrets;print(secrets.token_urlsafe(9))')}"
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
# MQTT_BIND=0.0.0.0 để ESP32 trong cùng mạng LAN kết nối được (mặc định chỉ localhost)
python -m tools.dev_broker --host "${MQTT_BIND:-127.0.0.1}" --port "${MQTT_PORT:-1883}" & pids+=($!)
sleep 1
python -m backend.main & pids+=($!)
sleep 2
python -m simulator.main --no-cli ${SIM_ARGS:-} & pids+=($!)
echo "Giao diện: http://localhost:${API_PORT:-8000}   Swagger: /api/docs   (Ctrl+C để dừng)"
echo "Quản trị: đăng nhập ${ADMIN_USERNAME:-admin} / ${ADMIN_PASSWORD}   (khách hàng không cần đăng nhập)"
wait
