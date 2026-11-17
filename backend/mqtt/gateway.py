"""Cầu nối MQTT của Backend: subscribe 5 topic từ xe, publish command."""
from __future__ import annotations

import logging

from backend.services import ingest
from shared import contract, security
from shared.mqttlite import MqttClient

log = logging.getLogger("gateway")

SUBSCRIBE_KINDS = ("scan", "event", "telemetry", "heartbeat", "ack")


class Gateway:
    def __init__(self, ctx, client: MqttClient | None = None):
        self.ctx = ctx
        s = ctx.settings
        self.client = client or MqttClient(s.mqtt_client_id, s.mqtt_host, s.mqtt_port, **s.mqtt_client_options())
        if s.device_master_key and not s.signature_required():
            log.warning("REQUIRE_SIGNATURE=0: chấp nhận cả message KHÔNG ký (chỉ dùng khi chuyển đổi)")
        self.client.on_message = self.on_message
        for k in SUBSCRIBE_KINDS:
            self.client.subscribe(f"{contract.TOPIC_ROOT}/+/{k}")

    def start(self) -> None:
        self.client.start()

    def stop(self) -> None:
        self.client.stop()

    @property
    def connected(self) -> bool:
        return self.client.connected

    def publish_command(self, cart_id: str, command_id: str, command_type: str, parameters: dict) -> bool:
        env = contract.envelope(cart_id, {"command_id": command_id, "command_type": command_type, "parameters": parameters})
        key = self.cart_key(cart_id)
        payload = contract.encode_signed(env, key, "command") if key else contract.encode(env)
        return self.client.publish(contract.topic(cart_id, "command"), payload)

    def cart_key(self, cart_id: str) -> bytes | None:
        master = self.ctx.settings.device_master_key
        return security.derive_cart_key(master, cart_id) if master else None

    # --- nhận message -----------------------------------------------------
    def on_message(self, topic: str, payload: bytes) -> None:
        ctx = self.ctx
        ctx.stats["mqtt_received"] += 1
        parsed = contract.parse_topic(topic)
        if not parsed or parsed[1] not in SUBSCRIBE_KINDS:
            ctx.stats["mqtt_invalid"] += 1
            log.warning("Topic không hợp lệ: %s", topic)
            return
        cart_id, kind = parsed
        # 1) Chữ ký TRƯỚC mọi thứ khác: message giả không được chạm tới bộ nhớ chống trùng hay DB.
        key = self.cart_key(cart_id)
        if key:
            try:
                contract.verify_payload(kind, key, payload)
            except contract.SignatureError as e:
                if e.missing and not ctx.settings.signature_required():
                    pass                      # chế độ chuyển đổi: cho phép xe cũ chưa ký
                else:
                    ctx.stats["mqtt_unsigned" if e.missing else "mqtt_bad_signature"] += 1
                    log.warning("Từ chối %s: %s", topic, e)
                    return
            except contract.ContractError as e:
                ctx.stats["mqtt_invalid"] += 1
                log.warning("Bỏ qua %s: %s", topic, e)
                return
        try:
            env = contract.decode_and_validate(kind, cart_id, payload)
        except contract.ContractError as e:
            ctx.stats["mqtt_invalid"] += 1
            log.warning("Bỏ qua %s: %s", topic, e)
            return
        skew = ctx.settings.max_clock_skew_s
        if skew > 0:
            delta = abs((contract.utcnow() - contract.parse_ts(env["timestamp"])).total_seconds())
            if delta > skew:
                ctx.stats["mqtt_stale"] += 1
                log.warning("Bỏ qua %s: timestamp lệch %.0fs (> %.0fs)", topic, delta, skew)
                return
        if ctx.dedupe.seen(f"msg:{env['message_id']}"):
            ctx.stats["mqtt_duplicate"] += 1
            return
        try:
            ingest.handle(ctx, kind, cart_id, env)
        except Exception:  # noqa: BLE001 - lỗi xử lý không được làm chết consumer
            log.exception("Lỗi xử lý %s", topic)


