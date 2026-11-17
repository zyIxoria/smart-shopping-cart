"""Lớp MQTT của một xe giả lập: đóng gói envelope, ký HMAC, subscribe topic command."""
from __future__ import annotations

import logging
import os

from shared import contract
from shared.mqttlite import MqttClient, options_from_env

log = logging.getLogger("sim.mqtt")


class CartMqtt:
    def __init__(self, cart_id: str, host: str, port: int, on_command, on_connect=None, *,
                 key: bytes | None = None, max_skew_s: float = 300, mqtt_options: dict | None = None):
        self.cart_id = cart_id
        self.key = key                      # khoá riêng của xe: có => ký mọi message gửi đi và bắt buộc lệnh phải ký
        self.max_skew_s = max_skew_s
        self.rejected = {"unsigned": 0, "bad_signature": 0, "stale": 0}
        opts = options_from_env() if mqtt_options is None else mqtt_options
        self.client = MqttClient(f"{os.getenv('MQTT_CLIENT_PREFIX', 'sim')}-{cart_id}", host, port, keepalive=30, **opts)
        self._on_command = on_command
        self._on_connect = on_connect
        self.client.on_message = self._message
        self.client.on_connect = self._connected
        # Sau reconnect, MqttClient tự subscribe lại danh sách này
        self.client.subscribe(contract.topic(cart_id, "command"))

    @property
    def connected(self) -> bool:
        return self.client.connected

    def start(self):
        self.client.start()

    def stop(self, clean: bool = True):
        self.client.stop(clean=clean)

    def publish(self, kind: str, data: dict) -> bool:
        env = contract.envelope(self.cart_id, data)
        payload = contract.encode_signed(env, self.key, kind) if self.key else contract.encode(env)
        return self.client.publish(contract.topic(self.cart_id, kind), payload)

    def _connected(self, _c):
        if self._on_connect:
            self._on_connect()

    def _message(self, topic: str, payload: bytes):
        parsed = contract.parse_topic(topic)
        if not parsed or parsed[0] != self.cart_id or parsed[1] != "command":
            return
        if self.key:    # xe chỉ nghe lệnh do Backend (người giữ khoá chủ) ký
            try:
                contract.verify_payload("command", self.key, payload)
            except contract.SignatureError as e:
                self.rejected["unsigned" if e.missing else "bad_signature"] += 1
                log.warning("%s: bỏ lệnh – %s", self.cart_id, e)
                return
            except contract.ContractError:
                return
        try:
            env = contract.decode_and_validate("command", self.cart_id, payload)
            if self.key:
                contract.check_freshness(env, self.max_skew_s)
        except contract.ContractError as e:
            if self.key and "timestamp lệch" in str(e):
                self.rejected["stale"] += 1
                log.warning("%s: bỏ lệnh cũ – %s", self.cart_id, e)
            return
        self._on_command(env)
