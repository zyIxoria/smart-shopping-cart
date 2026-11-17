#!/usr/bin/env bash
# Chạy toàn bộ hệ thống ở CHẾ ĐỘ BẢO MẬT, không cần Docker/Mosquitto:
#   MQTT có đăng nhập + ACL + TLS · message ký HMAC · API/Admin có đăng nhập.
# Lần đầu tự sinh bí mật vào ./secrets (xem docs/SECURITY.md). Cần `openssl` để sinh chứng chỉ TLS.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD"
if [ ! -f secrets/state.json ]; then
  python -m tools.provision ${PROVISION_ARGS:-}
fi
set -a; . secrets/secure.env; set +a
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

TLS_ARGS=()
if [ -f secrets/tls/server.crt ]; then TLS_ARGS=(--tls-cert secrets/tls/server.crt --tls-key secrets/tls/server.key); fi
python -m tools.dev_broker --host "${MQTT_BIND:-127.0.0.1}" --port "${MQTT_PORT:-8883}" --users secrets/mqtt_users.json "${TLS_ARGS[@]}" & pids+=($!)
sleep 1
MQTT_USERNAME="$MQTT_BACKEND_USER" MQTT_PASSWORD="$MQTT_BACKEND_PASS" python -m backend.main & pids+=($!)
sleep 2
MQTT_USERNAME="$MQTT_SIM_USER" MQTT_PASSWORD="$MQTT_SIM_PASS" python -m simulator.main --no-cli ${SIM_ARGS:-} & pids+=($!)
echo "Giao diện: http://localhost:${API_PORT:-8000}   Đăng nhập quản trị: ${ADMIN_USERNAME} / ${ADMIN_PASSWORD}   (Ctrl+C để dừng)"
wait
