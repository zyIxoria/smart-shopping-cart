#!/usr/bin/env bash
# Chạy CHỈ Backend (+ giao diện) nối vào MQTT broker CÔNG CỘNG để firmware trong Wokwi liên kết được.
# Cấu hình (broker, gốc topic, mã xe) được đọc từ firmware/include/wokwi_online.h nên luôn khớp với firmware.
# Không chạy dev broker và không chạy Simulator Python.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"
HDR=firmware/include/wokwi_online.h
def() { sed -n "s/^#define[[:space:]]\+$1[[:space:]]\+\"\([^\"]*\)\".*/\1/p" "$HDR" | head -1; }
export MQTT_HOST="$(def MQTT_HOST)"
export MQTT_PORT="${MQTT_PORT:-1883}"
export MQTT_TOPIC_ROOT="$(def MQTT_TOPIC_ROOT)"
export MQTT_CLIENT_ID="backend-$MQTT_TOPIC_ROOT"
CART_ID="$(def CART_ID)"
API_PORT="${API_PORT:-8000}"
# Đăng nhập quản trị: không đặt ADMIN_PASSWORD thì sinh ngẫu nhiên cho lần chạy này (khách hàng không cần đăng nhập)
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(python -c 'import secrets;print(secrets.token_urlsafe(9))')}"
echo "Broker: $MQTT_HOST:$MQTT_PORT  gốc topic: $MQTT_TOPIC_ROOT  mã xe: $CART_ID"
echo "Quản trị: đăng nhập ${ADMIN_USERNAME:-admin} / $ADMIN_PASSWORD"
( sleep 5; python - "$CART_ID" "http://127.0.0.1:$API_PORT" <<'PY' || true
import os, sys
from tools.wokwi_bridge import admin_token, register_cart
cart, api = sys.argv[1], sys.argv[2]
tok = admin_token(api, os.getenv("ADMIN_USERNAME", "admin"), os.environ["ADMIN_PASSWORD"])
print(register_cart(api, cart, tok))
PY
) &
exec python -m backend.main
