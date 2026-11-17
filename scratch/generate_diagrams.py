"""Sinh toàn bộ 8 sơ đồ kỹ thuật chuẩn xác, sắc nét (250 DPI), thiết kế hiện đại tối giản cho bộ slide."""
from __future__ import annotations

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_DIR = "scratch/diagrams"
os.makedirs(OUT_DIR, exist_ok=True)

# Bảng màu đồng bộ Design System
BG_LIGHT = "#FFFFFF"
NAVY = "#101A2B"
TEAL = "#12A6B8"
TEAL_BG = "#ECFEFF"
BLUE = "#2563EB"
BLUE_BG = "#EFF6FF"
SLATE_DARK = "#1E293B"
SLATE_MUTED = "#64748B"
SLATE_BORDER = "#CBD5E1"
SLATE_BG = "#F8FAFC"
EMERALD = "#059669"
EMERALD_BG = "#ECFDF5"
AMBER = "#D97706"
AMBER_BG = "#FFFBEB"
ROSE = "#DC2626"
ROSE_BG = "#FEF2F2"

plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Arial"]
plt.rcParams["axes.unicode_minus"] = False


def box(ax, x, y, w, h, title="", lines=None, fc=SLATE_BG, ec=SLATE_BORDER, tc=NAVY, lw=1.5, title_size=10, body_size=8.5, r=0.12):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, zorder=2)
    ax.add_patch(p)
    if title and lines:
        ax.text(x + w / 2, y + h - 0.22, title, ha="center", va="top", fontsize=title_size, fontweight="bold", color=tc, zorder=3)
        body = "\n".join(lines)
        ax.text(x + w / 2, y + h - 0.52, body, ha="center", va="top", fontsize=body_size, color=SLATE_DARK, linespacing=1.35, zorder=3)
    elif title:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=title_size, fontweight="bold", color=tc, zorder=3)


def arrow(ax, x1, y1, x2, y2, label="", color=SLATE_MUTED, lw=1.6, rad=0.0, lx_off=0, ly_off=0.14, ls="-"):
    a = FancyArrowPatch((x1, y1), (x2, y2), connectionstyle=f"arc3,rad={rad}",
                        arrowstyle="-|>,head_length=6,head_width=3.5", color=color, lw=lw, linestyle=ls, zorder=4)
    ax.add_patch(a)
    if label:
        mx, my = (x1 + x2) / 2 + lx_off, (y1 + y2) / 2 + ly_off
        ax.text(mx, my, label, ha="center", va="center", fontsize=8, fontweight="bold", color=color,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9), zorder=5)


def init_fig(w=11.0, h=5.6):
    fig, ax = plt.subplots(figsize=(w, h), dpi=250)
    fig.patch.set_facecolor(BG_LIGHT)
    ax.set_facecolor(BG_LIGHT)
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def make_architecture():
    fig, ax = init_fig(11.5, 6.0)
    ax.text(5.75, 5.75, "KIẾN TRÚC TỔNG THỂ HỆ THỐNG (SAU HOÀN THIỆN)", ha="center", va="top", fontsize=12.5, fontweight="bold", color=NAVY)

    # Cột 1: Edge / Devices
    box(ax, 0.3, 3.2, 2.7, 2.1, "Python Smart Cart Simulator",
        ["• 3 xe độc lập: CART_001..003", "• Nhiễu cân ±3g, sụt pin thực", "• Offline Queue (FIFO ≤ 50)", "• Control API :8090 (Token)"],
        fc=TEAL_BG, ec=TEAL, tc=NAVY)

    box(ax, 0.3, 0.7, 2.7, 2.1, "ESP32 Firmware & Wokwi",
        ["• lib/cartcore (C++11 thuần)", "• Lọc cân Median-5 + EMA", "• UART GM65 · HX711 · OLED", "• PlatformIO build 100% PASS"],
        fc=SLATE_BG, ec=SLATE_BORDER, tc=NAVY)

    # Cột 2: Broker
    box(ax, 3.7, 2.0, 2.3, 2.3, "MQTT Broker (:1883)",
        ["• Dev: tools/dev_broker.py", "• Docker: eclipse-mosquitto:2", "• 6 Topics: smartcart/{id}/...", "• Auth + ACL + TLS (:8883)", "• Client: shared/mqttlite.py"],
        fc=AMBER_BG, ec=AMBER, tc=NAVY)

    # Cột 3: Backend FastAPI
    box(ax, 6.6, 2.1, 2.6, 3.2, "Backend FastAPI (:8000)",
        ["• 26 REST Endpoints + Swagger", "• /docs & /redoc OpenAPI 3.0.3", "• RBAC + PBKDF2 + Anti-IDOR", "• MQTT Gateway (HMAC + Dedupe)", "• Alert Engine & Monitor (2s)", "• Native WebSocket /ws (:8000)"],
        fc=BLUE_BG, ec=BLUE, tc=NAVY)

    # CSDL Dual-Engine bên dưới Backend
    box(ax, 6.6, 0.5, 2.6, 1.25, "Dual-Engine Database",
        ["• PostgreSQL 16 (psycopg 3)", "• SQLite WAL (Test & Local)", "• 7 Bảng + cart_commands + tx()"],
        fc=EMERALD_BG, ec=EMERALD, tc=NAVY)

    # Cột 4: Frontend React
    box(ax, 9.7, 3.1, 1.6, 2.2, "Customer UI",
        ["/customer", "• Chọn xe", "• Giỏ realtime", "• Checkout", "(React 19)"],
        fc=SLATE_BG, ec=NAVY, tc=NAVY)

    box(ax, 9.7, 0.6, 1.6, 2.2, "Admin & Sim UI",
        ["/admin · /sim", "• Giám sát xe", "• Cảnh báo", "• Khoá xe ACK", "• Test giả lập"],
        fc=SLATE_BG, ec=NAVY, tc=NAVY)

    # Arrows
    arrow(ax, 3.0, 4.3, 3.7, 3.5, "Pub", color=TEAL)
    arrow(ax, 3.7, 3.1, 3.0, 3.9, "Cmd", color=ROSE, ly_off=-0.16)
    arrow(ax, 3.0, 1.75, 3.7, 2.6, "Bridge", color=SLATE_MUTED)
    arrow(ax, 6.0, 3.3, 6.6, 3.6, "Sub +/+", color=BLUE)
    arrow(ax, 6.6, 3.0, 6.0, 2.8, "Cmd", color=ROSE, ly_off=-0.16)
    arrow(ax, 7.9, 2.1, 7.9, 1.75, "SQL", color=EMERALD, lx_off=0.35, ly_off=0)
    arrow(ax, 9.2, 4.3, 9.7, 4.3, "REST/WS", color=BLUE, ly_off=0.2)
    arrow(ax, 9.2, 2.4, 9.7, 1.8, "REST/WS", color=NAVY, ly_off=-0.2)

    fig.savefig(f"{OUT_DIR}/diagram_architecture.png", bbox_inches="tight", dpi=250)
    plt.close(fig)


def make_dataflow():
    fig, ax = init_fig(11.5, 5.4)
    ax.text(5.75, 5.15, "LUỒNG DỮ LIỆU KHÉP KÍN (END-TO-END DATA FLOW)", ha="center", va="top", fontsize=12.5, fontweight="bold", color=NAVY)

    # Hàng trên (Uplink)
    box(ax, 0.3, 3.0, 1.9, 1.6, "1. Edge Node", ["Quét mã / Cân", "Pin / Offline Q", "(Sim / ESP32)"], fc=TEAL_BG, ec=TEAL)
    box(ax, 2.6, 3.0, 1.9, 1.6, "2. JSON MQTT", ["Envelope v1", "UUID + Time", "HMAC-SHA256"], fc=SLATE_BG, ec=SLATE_BORDER)
    box(ax, 4.9, 3.0, 1.9, 1.6, "3. Broker", ["Mosquitto / Dev", "6 Topics", "smartcart/{id}"], fc=AMBER_BG, ec=AMBER)
    box(ax, 7.2, 3.0, 1.9, 1.6, "4. Gateway", ["Verify HMAC", "Skew & Dedupe", "Rule Engine"], fc=BLUE_BG, ec=BLUE)
    box(ax, 9.5, 3.0, 1.7, 1.6, "5. Database", ["PostgreSQL 16", "/ SQLite WAL", "7 Bảng + tx()"], fc=EMERALD_BG, ec=EMERALD)

    arrow(ax, 2.2, 3.8, 2.6, 3.8, "", color=TEAL)
    arrow(ax, 4.5, 3.8, 4.9, 3.8, "", color=BLUE)
    arrow(ax, 6.8, 3.8, 7.2, 3.8, "", color=AMBER)
    arrow(ax, 9.1, 3.8, 9.5, 3.8, "", color=EMERALD)

    # Hàng dưới (Realtime UI & Downlink)
    box(ax, 7.2, 0.6, 2.1, 1.6, "6. WS Hub (/ws)", ["FastAPI :8000", "hub.project()", "Lọc theo Role"], fc=BLUE_BG, ec=BLUE)
    box(ax, 4.1, 0.6, 2.3, 1.6, "7. React Web UI", ["Customer: Giỏ hàng", "Admin: Fleet/Alert", "Checkout / Lock"], fc=SLATE_BG, ec=NAVY)
    box(ax, 1.0, 0.6, 2.3, 1.6, "8. Downlink Cmd", ["POST /lock", "Lưu cart_commands", "Đợi ACK ≤ 5s"], fc=ROSE_BG, ec=ROSE)

    arrow(ax, 8.15, 3.0, 8.15, 2.2, "Broadcast", color=BLUE, lx_off=0.55, ly_off=0)
    arrow(ax, 7.2, 1.4, 6.4, 1.4, "WS Push", color=BLUE, ly_off=0.22)
    arrow(ax, 4.1, 1.4, 3.3, 1.4, "REST API", color=ROSE, ly_off=0.22)
    arrow(ax, 2.15, 2.2, 5.6, 3.0, "command / ack", color=ROSE, rad=-0.12, ly_off=0.25)

    fig.savefig(f"{OUT_DIR}/diagram_dataflow.png", bbox_inches="tight", dpi=250)
    plt.close(fig)


def make_esp32_wokwi():
    fig, ax = init_fig(11.5, 5.6)
    ax.text(5.75, 5.35, "KIẾN TRÚC PHẦN CỨNG MÔ PHỎNG ESP32 & 3 CHẾ ĐỘ WOKWI", ha="center", va="top", fontsize=12, fontweight="bold", color=NAVY)

    # Cảm biến trái
    box(ax, 0.3, 3.9, 2.0, 0.9, "Barcode GM65", ["UART2: GPIO16/17"], fc=TEAL_BG, ec=TEAL, body_size=8)
    box(ax, 0.3, 2.75, 2.0, 0.9, "Load Cell HX711", ["2-Wire: GPIO32/33"], fc=EMERALD_BG, ec=EMERALD, body_size=8)
    box(ax, 0.3, 1.6, 2.0, 0.9, "Pin LiPo (ADC1)", ["GPIO34 (100k/100k)"], fc=AMBER_BG, ec=AMBER, body_size=8)
    box(ax, 0.3, 0.45, 2.0, 0.9, "Nút MODE/TARE", ["GPIO13 / GPIO14"], fc=SLATE_BG, ec=SLATE_BORDER, body_size=8)

    # ESP32 giữa
    box(ax, 2.8, 0.9, 2.5, 3.6, "ESP32 DevKit V1",
        ["• lib/cartcore (C++11 thuần)", "  WeightFilter (Median5+EMA)", "  CartLogic State Machine", "  HMAC-SHA256 Security", "", "• src/main.cpp", "  Non-blocking millis()", "  PlatformIO Build 100%"],
        fc=BLUE_BG, ec=BLUE, body_size=8.2)

    # Ngoại vi phải của ESP32
    box(ax, 5.8, 3.6, 1.9, 0.95, "OLED SSD1306", ["I2C GPIO21/22"], fc=TEAL_BG, ec=TEAL, body_size=8)
    box(ax, 5.8, 2.25, 1.9, 0.95, "Active Buzzer", ["GPIO25 (Mẫu kêu)"], fc=AMBER_BG, ec=AMBER, body_size=8)
    box(ax, 5.8, 0.9, 1.9, 0.95, "LED Xanh / Đỏ", ["GPIO26 / GPIO27"], fc=ROSE_BG, ec=ROSE, body_size=8)

    for y in [4.35, 3.2, 2.05, 0.9]:
        arrow(ax, 2.3, y, 2.8, y, "", color=NAVY)
    for y in [4.05, 2.7, 1.35]:
        arrow(ax, 5.3, y, 5.8, y, "", color=NAVY)

    # 3 chế độ Wokwi bên phải
    box(ax, 8.1, 3.6, 3.1, 1.25, "1. esp32dev_sim (Độc lập)",
        ["Không cần mạng; tự mở phiên #1", "Kiểm thử OLED, cân, còi qua Serial"], fc=SLATE_BG, ec=SLATE_BORDER, body_size=8)
    box(ax, 8.1, 2.05, 3.1, 1.25, "2. esp32dev_wokwi_online",
        ["Wi-Fi ảo Wokwi-GUEST -> HiveMQ", "Dùng topic root riêng biệt"], fc=TEAL_BG, ec=TEAL, body_size=8)
    box(ax, 8.1, 0.5, 3.1, 1.25, "3. esp32dev_sim_bridge",
        ["TCP RFC2217 :4000 <-> wokwi_bridge", "Gắn timestamp thực, ký HMAC -> Broker"], fc=EMERALD_BG, ec=EMERALD, body_size=8)

    fig.savefig(f"{OUT_DIR}/diagram_esp32_wokwi.png", bbox_inches="tight", dpi=250)
    plt.close(fig)


def make_mqtt_pipeline():
    fig, ax = init_fig(11.5, 5.2)
    ax.text(5.75, 4.95, "PIPELINE GATEWAY & CƠ CHẾ ĐỒNG BỘ MẤT MẠNG", ha="center", va="top", fontsize=12, fontweight="bold", color=NAVY)

    steps = [
        ("1. Parse Topic", ["smartcart/{id}/{kind}", "5 uplink kinds"], SLATE_BG, SLATE_BORDER),
        ("2. Verify HMAC", ["Kiểm sig TRƯỚC", "Chống giả mạo"], ROSE_BG, ROSE),
        ("3. Validate JSON", ["schema_version=1", "Khớp cart_id"], BLUE_BG, BLUE),
        ("4. Clock Skew", ["|now - ts| ≤ 300s", "Chống Replay"], AMBER_BG, AMBER),
        ("5. LRU Dedupe", ["2000 message_id", "+ scan_id"], TEAL_BG, TEAL),
        ("DB & Hub", ["Lưu CSDL", "Phát WS"], EMERALD_BG, EMERALD),
    ]
    x = 0.25
    for i, (t, ls, fc, ec) in enumerate(steps):
        w = 1.65 if i < 5 else 1.35
        box(ax, x, 2.8, w, 1.65, t, ls, fc=fc, ec=ec, title_size=9.5, body_size=8)
        if i < 5:
            arrow(ax, x + w, 3.6, x + w + 0.28, 3.6, "", color=NAVY)
        x += w + 0.28

    # Banner lỗi
    box(ax, 0.5, 2.0, 10.5, 0.5, "Nếu lỗi bất kỳ bước nào: Ghi log cảnh báo + Tăng biến đếm /api/health -> BỎ QUA (Không sập Consumer)",
        fc=ROSE_BG, ec=ROSE, tc=ROSE, title_size=9)

    # Khối phục hồi mạng
    box(ax, 0.5, 0.35, 10.5, 1.35, "Cơ chế đồng bộ khi xe mất kết nối và phục hồi (OFFLINE -> ONLINE Reconciliation)",
        [
            "1. Client (mqttlite / PubSubClient) tự reconnect với Exponential Backoff (0.5s -> 8s) và tự SUBSCRIBE lại topic command.",
            "2. Ngay khi kết nối lại, Simulator kích hoạt drain_offline_queue() gửi bù toàn bộ sự kiện quét trong hàng đợi (FIFO).",
            "3. Backend phát hiện xe chuyển OFFLINE -> ONLINE -> tự đóng cảnh báo OFFLINE và gọi _reconcile() đồng bộ lại trạng thái."
        ],
        fc=BLUE_BG, ec=BLUE, tc=NAVY, title_size=10, body_size=8.5)

    fig.savefig(f"{OUT_DIR}/diagram_mqtt_pipeline.png", bbox_inches="tight", dpi=250)
    plt.close(fig)


def make_sequence():
    fig, ax = init_fig(11.5, 6.2)
    ax.text(5.75, 5.98, "SEQUENCE DIAGRAM: MUA HÀNG REALTIME & KHOÁ XE QUA ACK", ha="center", va="top", fontsize=12, fontweight="bold", color=NAVY)

    actors = [
        (1.1, "Customer UI", BLUE),
        (3.4, "Admin UI", NAVY),
        (5.7, "Backend FastAPI", EMERALD),
        (8.0, "MQTT Broker", AMBER),
        (10.3, "Smart Cart", TEAL),
    ]
    for x, name, c in actors:
        box(ax, x - 0.85, 5.2, 1.7, 0.48, name, fc=c, ec=c, tc=BG_LIGHT, title_size=9.5, r=0.08)
        ax.plot([x, x], [0.25, 5.2], color=SLATE_BORDER, ls="--", lw=1.4, zorder=1)

    # Phần A: Luồng mua hàng (y từ 4.8 xuống 2.6)
    ax.text(0.25, 4.9, "A. Luồng mua hàng", fontsize=9.5, fontweight="bold", color=BLUE)
    arrow(ax, 1.1, 4.65, 5.7, 4.65, "1. POST /api/sessions {cart_id}", color=BLUE, ly_off=0.14)
    arrow(ax, 5.7, 4.30, 8.0, 4.30, "2. pub command: START_SESSION", color=EMERALD, ly_off=0.14)
    arrow(ax, 8.0, 3.95, 10.3, 3.95, "3. deliver START_SESSION -> ack OK", color=AMBER, ly_off=0.14)
    arrow(ax, 10.3, 3.55, 8.0, 3.55, "4. pub scan {barcode, ADD} + telemetry", color=TEAL, ly_off=0.14)
    arrow(ax, 8.0, 3.20, 5.7, 3.20, "5. forward -> Lưu DB + Rule Engine", color=AMBER, ly_off=0.14)
    arrow(ax, 5.7, 2.85, 1.1, 2.85, "6. WS /ws (:8000): CART_UPDATED -> Cập nhật giỏ", color=EMERALD, ly_off=0.14)
    arrow(ax, 1.1, 2.45, 5.7, 2.45, "7. POST /api/sessions/{id}/checkout (db.tx())", color=BLUE, ly_off=0.14)
    arrow(ax, 5.7, 2.15, 10.3, 2.15, "8. END_SESSION -> Xe hiển thị Cảm ơn", color=EMERALD, ly_off=0.14)

    # Đường phân cách
    ax.plot([0.2, 11.3], [1.90, 1.90], color=SLATE_BORDER, ls=":", lw=1.5)

    # Phần B: Luồng khoá xe (y từ 1.7 xuống 0.3)
    ax.text(0.25, 1.68, "B. Luồng khoá xe (Sync-over-Async)", fontsize=9.5, fontweight="bold", color=ROSE)
    arrow(ax, 3.4, 1.42, 5.7, 1.42, "1. POST /api/carts/{id}/lock (chờ ACK ≤ 5s)", color=NAVY, ly_off=0.14)
    arrow(ax, 5.7, 1.12, 8.0, 1.12, "2. Ghi cart_commands (PENDING) & pub LOCK_CART", color=ROSE, ly_off=0.14)
    arrow(ax, 8.0, 0.85, 10.3, 0.85, "3. Xe khoá quét + bật LED đỏ", color=AMBER, ly_off=0.14)
    arrow(ax, 10.3, 0.58, 5.7, 0.58, "4. ack {command_id, OK} -> Cập nhật DB & Event.set()", color=TEAL, ly_off=0.14)
    arrow(ax, 5.7, 0.30, 3.4, 0.30, "5. HTTP 200 OK (hoặc 504 TIMEOUT)", color=NAVY, ly_off=0.14)

    fig.savefig(f"{OUT_DIR}/diagram_sequence.png", bbox_inches="tight", dpi=250)
    plt.close(fig)


def make_alerts():
    fig, ax = init_fig(11.5, 5.2)
    ax.text(5.75, 4.95, "CƠ CHẾ XỬ LÝ CẢNH BÁO TỰ ĐỘNG (ALERT ENGINE)", ha="center", va="top", fontsize=12, fontweight="bold", color=NAVY)

    box(ax, 0.3, 2.6, 3.4, 1.95, "1. LOW_BATTERY",
        ["Nguồn: telemetry", "Kích hoạt: battery_percent < 20%", "Phục hồi: battery >= 20%", "-> Tự động đóng ALERT_RESOLVED"],
        fc=AMBER_BG, ec=AMBER, title_size=10.5, body_size=8.8)

    box(ax, 4.05, 2.6, 3.4, 1.95, "2. WEIGHT_MISMATCH",
        ["Nguồn: telemetry", "Kích hoạt: IN_USE & phiên ACTIVE", "và |actual - expected| > 100g", "Phục hồi: <= 100g hoặc checkout"],
        fc=ROSE_BG, ec=ROSE, title_size=10.5, body_size=8.8)

    box(ax, 7.8, 2.6, 3.4, 1.95, "3. CART_OFFLINE",
        ["Nguồn: HeartbeatMonitor (2s/lần)", "Kích hoạt: (now - last_seen) > 15s", "Phục hồi: Nhận tin mới", "-> touch_online() tự động đóng"],
        fc=BLUE_BG, ec=BLUE, title_size=10.5, body_size=8.8)

    box(ax, 0.3, 0.35, 10.9, 1.65, "Chống Spam Cảnh Báo & Đồng Bộ Realtime (backend/services/alerts.py)",
        [
            "• Partial Unique Index: CREATE UNIQUE INDEX ux_alert_active ON alerts(cart_id, alert_type) WHERE status = 'ACTIVE'",
            "• Kiểm tra trong giao dịch db.tx(): Nếu cảnh báo cùng loại trên cùng xe đang ACTIVE -> không tạo bản ghi mới.",
            "• Phát sự kiện WebSocket tức thời tới Staff: ALERT_TRIGGERED (khi mở mới) và ALERT_RESOLVED (khi tự đóng).",
            "• Khi Checkout còn cảnh báo chưa đóng -> tự động ghi vết vào cột shopping_sessions.note để đối soát."
        ],
        fc=SLATE_BG, ec=NAVY, title_size=10.5, body_size=8.8)

    arrow(ax, 2.0, 2.6, 2.5, 2.0, "", color=AMBER)
    arrow(ax, 5.75, 2.6, 5.75, 2.0, "", color=ROSE)
    arrow(ax, 9.5, 2.6, 9.0, 2.0, "", color=BLUE)

    fig.savefig(f"{OUT_DIR}/diagram_alerts.png", bbox_inches="tight", dpi=250)
    plt.close(fig)


def make_erd():
    fig, ax = init_fig(11.5, 6.0)
    ax.text(5.75, 5.78, "SƠ ĐỒ THỰC THỂ LIÊN KẾT (ERD) — 7 BẢNG DUAL-ENGINE (POSTGRES 16 & SQLITE)", ha="center", va="top", fontsize=11.5, fontweight="bold", color=NAVY)

    box(ax, 4.1, 3.4, 3.3, 2.05, "smart_carts",
        ["PK cart_id : TEXT", "name : TEXT", "cart_status : AVAILABLE|IN_USE|LOCKED", "connection_status : ONLINE|OFFLINE", "battery_percent : DOUBLE / REAL", "current_weight : DOUBLE / REAL", "last_seen, created_at, updated_at"],
        fc=BLUE_BG, ec=BLUE, body_size=8)

    box(ax, 0.3, 3.4, 3.1, 2.05, "shopping_sessions",
        ["PK id : SERIAL / INTEGER", "FK cart_id -> smart_carts", "status : ACTIVE|COMPLETED|CANCELLED", "started_at, ended_at", "total_amount : INTEGER", "note : TEXT", "UX: <= 1 ACTIVE / cart_id"],
        fc=TEAL_BG, ec=TEAL, body_size=8)

    box(ax, 0.3, 0.45, 3.1, 2.05, "cart_items",
        ["PK id : SERIAL / INTEGER", "FK session_id -> shopping_sessions", "FK product_id -> products", "quantity : INTEGER (>0)", "unit_price : INTEGER (snapshot)", "UQ: (session_id, product_id)"],
        fc=TEAL_BG, ec=TEAL, body_size=8)

    box(ax, 4.1, 0.45, 3.3, 2.05, "products",
        ["PK id : SERIAL / INTEGER", "UQ barcode : TEXT", "name : TEXT", "price : INTEGER (>=0 VND)", "unit_weight : DOUBLE (>0 g)", "image : TEXT, active : INTEGER"],
        fc=EMERALD_BG, ec=EMERALD, body_size=8)

    box(ax, 8.1, 3.8, 3.1, 1.65, "device_telemetry",
        ["PK id : SERIAL / INTEGER", "FK cart_id -> smart_carts", "battery_percent, actual_weight", "cart_status, recorded_at", "IX: (cart_id, id DESC)"],
        fc=SLATE_BG, ec=SLATE_BORDER, body_size=8)

    box(ax, 8.1, 2.0, 3.1, 1.6, "alerts",
        ["PK id : SERIAL / INTEGER", "FK cart_id -> smart_carts", "alert_type : LOW_BAT|WEIGHT|OFF", "status : ACTIVE|RESOLVED", "UX: (cart_id, alert_type) ACTIVE"],
        fc=AMBER_BG, ec=AMBER, body_size=8)

    box(ax, 8.1, 0.25, 3.1, 1.55, "cart_commands",
        ["PK id : SERIAL / INTEGER", "UQ command_id : TEXT", "FK cart_id -> smart_carts", "command_type, parameters, status", "created_at, acked_at"],
        fc=ROSE_BG, ec=ROSE, body_size=8)

    arrow(ax, 4.1, 4.4, 3.4, 4.4, "1 : N", color=BLUE, ly_off=0.18)
    arrow(ax, 1.85, 3.4, 1.85, 2.5, "1 : N\n(CASCADE)", color=TEAL, lx_off=0.55, ly_off=0)
    arrow(ax, 4.1, 1.45, 3.4, 1.45, "1 : N", color=EMERALD, ly_off=0.18)
    arrow(ax, 7.4, 4.6, 8.1, 4.6, "1 : N", color=NAVY, ly_off=0.18)
    arrow(ax, 7.4, 4.1, 8.1, 2.8, "1 : N", color=AMBER, lx_off=-0.1, ly_off=0.2)
    arrow(ax, 7.4, 3.7, 8.1, 1.1, "1 : N", color=ROSE, lx_off=-0.2, ly_off=-0.1)

    fig.savefig(f"{OUT_DIR}/diagram_erd.png", bbox_inches="tight", dpi=250)
    plt.close(fig)


def make_testing():
    fig, ax = plt.subplots(figsize=(6.8, 4.2), dpi=250)
    fig.patch.set_facecolor(BG_LIGHT)
    ax.set_facecolor(BG_LIGHT)

    categories = ["Unit Tests\n(Python)", "Integration\nTests", "E2E UI\n(Playwright)", "Firmware\n(PlatformIO\nBuild)"]
    passed = [47, 64, 20, 2]
    skipped = [15, 1, 0, 0]

    x = range(len(categories))
    w = 0.48
    b1 = ax.bar(x, passed, width=w, label="PASSED / SUCCESS", color=EMERALD, zorder=3)
    b2 = ax.bar(x, skipped, bottom=passed, width=w, label="SKIPPED (C++ host g++ / Mock)", color=AMBER, alpha=0.8, zorder=3)

    ax.set_xticks(list(x))
    ax.set_xticklabels(categories, fontsize=9.5, fontweight="bold", color=NAVY)
    ax.set_ylabel("Số lượng kiểm thử / Targets", fontsize=9.5, fontweight="bold", color=SLATE_DARK)
    ax.set_ylim(0, 78)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(SLATE_BORDER)
    ax.spines["bottom"].set_color(SLATE_BORDER)

    for i in range(len(categories)):
        p_val = passed[i]
        s_val = skipped[i]
        lbl = f"{p_val} PASS" if s_val == 0 else f"{p_val}P / {s_val}S"
        if i == 3:
            lbl = "2 Targets\n100% OK"
        ax.text(i, p_val + s_val + 1.8, lbl, ha="center", va="bottom", fontsize=9, fontweight="bold", color=NAVY)

    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor=SLATE_BORDER, fontsize=8.5)
    ax.set_title("Kết quả thực thi bộ kiểm thử (131 Python Tests PASS · 0 Fail)", fontsize=11, fontweight="bold", color=NAVY, pad=12)

    fig.savefig(f"{OUT_DIR}/diagram_testing.png", bbox_inches="tight", dpi=250)
    plt.close(fig)


if __name__ == "__main__":
    make_architecture()
    make_dataflow()
    make_esp32_wokwi()
    make_mqtt_pipeline()
    make_sequence()
    make_alerts()
    make_erd()
    make_testing()
    print("Generated all 8 updated diagrams cleanly into", OUT_DIR)
