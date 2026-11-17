-- Smart Shopping Cart – 6 bảng (khớp tài liệu thiết kế). SQLite mặc định;
-- PostgreSQL: đổi INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL/IDENTITY, xem docs/database.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  barcode     TEXT    NOT NULL UNIQUE,
  name        TEXT    NOT NULL,
  price       INTEGER NOT NULL CHECK (price >= 0),          -- VND
  unit_weight REAL    NOT NULL CHECK (unit_weight > 0),     -- gram
  image       TEXT    NOT NULL DEFAULT '',
  active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS smart_carts (
  cart_id           TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  cart_status       TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK (cart_status IN ('AVAILABLE','IN_USE','LOCKED')),
  connection_status TEXT NOT NULL DEFAULT 'OFFLINE'   CHECK (connection_status IN ('ONLINE','OFFLINE')),
  battery_percent   REAL,
  current_weight    REAL NOT NULL DEFAULT 0,               -- gram
  last_seen         TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shopping_sessions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  cart_id      TEXT NOT NULL REFERENCES smart_carts(cart_id),
  status       TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','COMPLETED')),
  started_at   TEXT NOT NULL,
  ended_at     TEXT,
  total_amount INTEGER NOT NULL DEFAULT 0,
  note         TEXT NOT NULL DEFAULT ''
);
-- Mỗi xe tối đa 1 phiên ACTIVE
CREATE UNIQUE INDEX IF NOT EXISTS ux_session_active_cart ON shopping_sessions(cart_id) WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS cart_items (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES shopping_sessions(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id),
  quantity   INTEGER NOT NULL CHECK (quantity > 0),
  unit_price INTEGER NOT NULL,
  UNIQUE (session_id, product_id)
);

CREATE TABLE IF NOT EXISTS device_telemetry (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  cart_id         TEXT NOT NULL REFERENCES smart_carts(cart_id),
  battery_percent REAL NOT NULL,
  actual_weight   REAL NOT NULL,
  cart_status     TEXT,
  timestamp       TEXT NOT NULL,
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_telemetry_cart_time ON device_telemetry(cart_id, id DESC);

CREATE TABLE IF NOT EXISTS alerts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  cart_id     TEXT NOT NULL REFERENCES smart_carts(cart_id),
  alert_type  TEXT NOT NULL CHECK (alert_type IN ('LOW_BATTERY','WEIGHT_MISMATCH','OFFLINE')),
  status      TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','RESOLVED')),
  detail      TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL,
  resolved_at TEXT
);
-- Không tạo trùng cảnh báo ACTIVE cùng loại cho cùng xe
CREATE UNIQUE INDEX IF NOT EXISTS ux_alert_active ON alerts(cart_id, alert_type) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS ix_alert_status ON alerts(status, id DESC);

CREATE TABLE IF NOT EXISTS cart_commands (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  command_id   TEXT    NOT NULL UNIQUE,
  cart_id      TEXT    NOT NULL REFERENCES smart_carts(cart_id),
  command_type TEXT    NOT NULL,
  parameters   TEXT    NOT NULL DEFAULT '{}',
  status       TEXT    NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','OK','FAILED','TIMEOUT')),
  message      TEXT    NOT NULL DEFAULT '',
  created_at   TEXT    NOT NULL,
  sent_at      TEXT,
  acked_at     TEXT
);
CREATE INDEX IF NOT EXISTS ix_command_cart ON cart_commands(cart_id, id DESC);

