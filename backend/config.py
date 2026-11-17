"""Cấu hình Backend – đọc từ biến môi trường (xem .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass
class Settings:
    # HTTP / WebSocket
    host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _i("API_PORT", 8000))
    ws_port: int = field(default_factory=lambda: _i("WS_PORT", 8000))
    cors_origins: list = field(
        default_factory=lambda: [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
    )
    # MQTT
    mqtt_host: str = field(default_factory=lambda: os.getenv("MQTT_HOST", "localhost"))
    mqtt_port: int = field(default_factory=lambda: _i("MQTT_PORT", 1883))
    mqtt_enabled: bool = field(default_factory=lambda: os.getenv("MQTT_ENABLED", "1") != "0")
    # client id phải DUY NHẤT trên broker (broker công cộng sẽ ngắt kết nối khi trùng id)
    mqtt_client_id: str = field(default_factory=lambda: os.getenv("MQTT_CLIENT_ID", "smartcart-backend"))
    # MQTT bảo mật (xem docs/SECURITY.md): đăng nhập broker + TLS
    mqtt_username: str = field(default_factory=lambda: os.getenv("MQTT_USERNAME", ""))
    mqtt_password: str = field(default_factory=lambda: os.getenv("MQTT_PASSWORD", ""))
    mqtt_tls: bool = field(default_factory=lambda: os.getenv("MQTT_TLS", "0") not in ("", "0", "false"))
    mqtt_ca_file: str = field(default_factory=lambda: os.getenv("MQTT_CA_FILE", ""))
    mqtt_tls_insecure: bool = field(default_factory=lambda: os.getenv("MQTT_TLS_INSECURE", "0") == "1")
    # Ký message: khoá chủ để sinh khoá riêng cho từng xe. Đặt khoá => Backend ký lệnh và (mặc định) bắt buộc xe ký.
    device_master_key: str = field(default_factory=lambda: os.getenv("DEVICE_MASTER_KEY", ""))
    require_signature: bool | None = field(
        default_factory=lambda: None if os.getenv("REQUIRE_SIGNATURE") is None else os.getenv("REQUIRE_SIGNATURE") != "0")
    # Đăng nhập API / WebSocket
    auth_enabled: bool = field(default_factory=lambda: os.getenv("AUTH_ENABLED", "1") != "0")
    admin_username: str = field(default_factory=lambda: os.getenv("ADMIN_USERNAME", "admin"))
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", ""))
    admin_password_hash: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD_HASH", ""))
    viewer_username: str = field(default_factory=lambda: os.getenv("VIEWER_USERNAME", ""))
    viewer_password: str = field(default_factory=lambda: os.getenv("VIEWER_PASSWORD", ""))
    token_secret: str = field(default_factory=lambda: os.getenv("TOKEN_SECRET", ""))
    admin_token_ttl_s: float = field(default_factory=lambda: _f("ADMIN_TOKEN_TTL_S", 8 * 3600))
    session_token_ttl_s: float = field(default_factory=lambda: _f("SESSION_TOKEN_TTL_S", 4 * 3600))
    login_max_attempts: int = field(default_factory=lambda: _i("LOGIN_MAX_ATTEMPTS", 5))
    login_lockout_s: float = field(default_factory=lambda: _f("LOGIN_LOCKOUT_S", 60))
    # Database
    db_backend: str = field(default_factory=lambda: os.getenv("DB_BACKEND", "sqlite").lower())
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    postgres_host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    postgres_port: int = field(default_factory=lambda: _i("POSTGRES_PORT", 5432))
    postgres_db: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "smartcart"))
    postgres_user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "postgres"))
    postgres_password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "postgres"))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", str(ROOT / "data" / "smartcart.db")))
    seed_on_start: bool = field(default_factory=lambda: os.getenv("SEED_ON_START", "1") != "0")
    # Quy tắc cảnh báo (đơn vị: % / gram / giây)
    battery_low_percent: float = field(default_factory=lambda: _f("BATTERY_LOW_PERCENT", 20))
    weight_tolerance_g: float = field(default_factory=lambda: _f("WEIGHT_TOLERANCE_G", 100))
    heartbeat_timeout_s: float = field(default_factory=lambda: _f("HEARTBEAT_TIMEOUT_S", 15))
    monitor_interval_s: float = field(default_factory=lambda: _f("MONITOR_INTERVAL_S", 2))
    # Chống phát lại / lệch giờ
    max_clock_skew_s: float = field(default_factory=lambda: _f("MAX_CLOCK_SKEW_S", 300))
    dedupe_size: int = field(default_factory=lambda: _i("DEDUPE_SIZE", 2000))
    command_ack_timeout_s: float = field(default_factory=lambda: _f("COMMAND_ACK_TIMEOUT_S", 5))
    # Frontend build (backend phục vụ tĩnh nếu tồn tại)
    frontend_dist: str = field(default_factory=lambda: os.getenv("FRONTEND_DIST", str(ROOT / "frontend" / "dist")))
    telemetry_keep: int = field(default_factory=lambda: _i("TELEMETRY_KEEP_PER_CART", 5000))

    def signature_required(self) -> bool:
        """Có bắt buộc message từ xe phải có chữ ký hợp lệ không."""
        if not self.device_master_key:
            return False
        return True if self.require_signature is None else self.require_signature

    def mqtt_client_options(self) -> dict:
        """kwargs bảo mật cho MqttClient (username/password/TLS)."""
        from shared.mqttlite import make_tls_context
        opts: dict = {}
        if self.mqtt_username:
            opts["username"], opts["password"] = self.mqtt_username, self.mqtt_password
        if self.mqtt_tls:
            opts["tls"] = make_tls_context(self.mqtt_ca_file or None, self.mqtt_tls_insecure)
        return opts
