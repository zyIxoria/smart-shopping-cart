-- Smart Shopping Cart – Schema PostgreSQL 16
-- Khớp hoàn toàn với mô hình dữ liệu và quy tắc nghiệp vụ hệ thống.

CREATE TABLE IF NOT EXISTS products (
  id          SERIAL PRIMARY KEY,
  barcode     VARCHAR(64) NOT NULL UNIQUE,
  name        VARCHAR(255) NOT NULL,
  price       INTEGER NOT NULL CHECK (price >= 0),
  unit_weight DOUBLE PRECISION NOT NULL CHECK (unit_weight > 0),
  image       VARCHAR(500) NOT NULL DEFAULT '',
  active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS smart_carts (
  cart_id           VARCHAR(32) PRIMARY KEY,
  name              VARCHAR(128) NOT NULL,
  cart_status       VARCHAR(32) NOT NULL DEFAULT 'AVAILABLE' CHECK (cart_status IN ('AVAILABLE','IN_USE','LOCKED')),
  connection_status VARCHAR(32) NOT NULL DEFAULT 'OFFLINE' CHECK (connection_status IN ('ONLINE','OFFLINE')),
  battery_percent   DOUBLE PRECISION,
  current_weight    DOUBLE PRECISION NOT NULL DEFAULT 0,
  last_seen         TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL,
  updated_at        TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS shopping_sessions (
  id           SERIAL PRIMARY KEY,
  cart_id      VARCHAR(32) NOT NULL REFERENCES smart_carts(cart_id),
  status       VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','COMPLETED')),
  started_at   TIMESTAMPTZ NOT NULL,
  ended_at     TIMESTAMPTZ,
  total_amount INTEGER NOT NULL DEFAULT 0,
  note         TEXT NOT NULL DEFAULT ''
);
-- Mỗi xe tối đa 1 phiên ACTIVE
CREATE UNIQUE INDEX IF NOT EXISTS ux_session_active_cart ON shopping_sessions(cart_id) WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS cart_items (
  id         SERIAL PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES shopping_sessions(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id),
  quantity   INTEGER NOT NULL CHECK (quantity > 0),
  unit_price INTEGER NOT NULL,
  UNIQUE (session_id, product_id)
);

CREATE TABLE IF NOT EXISTS device_telemetry (
  id              SERIAL PRIMARY KEY,
  cart_id         VARCHAR(32) NOT NULL REFERENCES smart_carts(cart_id),
  battery_percent DOUBLE PRECISION NOT NULL,
  actual_weight   DOUBLE PRECISION NOT NULL,
  cart_status     VARCHAR(32),
  timestamp       TIMESTAMPTZ NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_telemetry_cart_time ON device_telemetry(cart_id, id DESC);

CREATE TABLE IF NOT EXISTS alerts (
  id          SERIAL PRIMARY KEY,
  cart_id     VARCHAR(32) NOT NULL REFERENCES smart_carts(cart_id),
  alert_type  VARCHAR(32) NOT NULL CHECK (alert_type IN ('LOW_BATTERY','WEIGHT_MISMATCH','OFFLINE')),
  status      VARCHAR(32) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','RESOLVED')),
  detail      TEXT NOT NULL DEFAULT '',
  created_at  TIMESTAMPTZ NOT NULL,
  resolved_at TIMESTAMPTZ
);
-- Không tạo trùng cảnh báo ACTIVE cùng loại cho cùng xe
CREATE UNIQUE INDEX IF NOT EXISTS ux_alert_active ON alerts(cart_id, alert_type) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS ix_alert_status ON alerts(status, id DESC);

CREATE TABLE IF NOT EXISTS cart_commands (
  id           SERIAL PRIMARY KEY,
  command_id   VARCHAR(64) NOT NULL UNIQUE,
  cart_id      VARCHAR(32) NOT NULL REFERENCES smart_carts(cart_id),
  command_type VARCHAR(32) NOT NULL,
  parameters   TEXT NOT NULL DEFAULT '{}',
  status       VARCHAR(32) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','OK','FAILED','TIMEOUT')),
  message      TEXT NOT NULL DEFAULT '',
  created_at   TIMESTAMPTZ NOT NULL,
  sent_at      TIMESTAMPTZ,
  acked_at     TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_command_cart ON cart_commands(cart_id, id DESC);
