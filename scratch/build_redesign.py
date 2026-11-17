"""Tạo lại toàn bộ bộ slide Smart_Shopping_Cart_Presentation.pptx theo phong cách
Professional Technology Presentation / Modern IoT & Smart Retail.
Bảo toàn 100% tính trung thực kỹ thuật, thông số đã kiểm chứng và Speaker Notes chuyên sâu.
"""
from __future__ import annotations

import json
import os
from PIL import Image
import pptx
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.xmlchemy import OxmlElement

# ==============================================================================
# DESIGN SYSTEM & BẢNG MÀU CHUẨN
# ==============================================================================
NAVY_DEEP = RGBColor(16, 26, 43)       # #101A2B
NAVY_SURFACE = RGBColor(22, 34, 56)    # #162238
NAVY_BORDER = RGBColor(40, 60, 95)     # #283C5F
TEAL = RGBColor(18, 166, 184)          # #12A6B8
TEAL_DARK = RGBColor(14, 132, 148)     # #0E8494
TEAL_SOFT = RGBColor(224, 247, 250)    # #E0F7FA
OFF_WHITE = RGBColor(245, 247, 250)    # #F5F7FA
WHITE = RGBColor(255, 255, 255)
SLATE_DARK = RGBColor(30, 41, 59)      # #1E293B
SLATE_BODY = RGBColor(51, 65, 85)      # #334155
SLATE_MUTED = RGBColor(100, 116, 139)  # #64748B
SLATE_LIGHT = RGBColor(170, 184, 200)  # #AAB8C8
SLATE_TEXT_ON_DARK = RGBColor(226, 232, 240)
BORDER_LIGHT = RGBColor(226, 232, 240) # #E2E8F0
ROW_ALT = RGBColor(248, 250, 252)      # #F8FAFC
EMERALD = RGBColor(5, 150, 105)        # #059669
EMERALD_SOFT = RGBColor(236, 253, 245)
AMBER = RGBColor(217, 119, 6)          # #D97706
AMBER_SOFT = RGBColor(255, 251, 235)
ROSE = RGBColor(220, 38, 38)           # #DC2626
ROSE_SOFT = RGBColor(254, 242, 242)
BLUE = RGBColor(37, 99, 235)

FONT_MAIN = "Segoe UI"
FONT_MONO = "Consolas"
OUT_PPTX = "docs/presentation/Smart_Shopping_Cart_Presentation.pptx"
DIAG_DIR = "scratch/diagrams"
SHOT_DIR = "docs/screenshots"


def set_bg(slide, color: RGBColor):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def set_cell_margins(cell, left=0.08, right=0.08, top=0.05, bottom=0.05):
    cell.margin_left = Inches(left)
    cell.margin_right = Inches(right)
    cell.margin_top = Inches(top)
    cell.margin_bottom = Inches(bottom)


def set_cell_border(cell, border_color="E2E8F0", border_width="12700"):
    tcPr = cell._tc.get_or_add_tcPr()
    for border_name in ["lnL", "lnR", "lnT", "lnB"]:
        ln = OxmlElement(f"a:{border_name}")
        if border_name in ("lnL", "lnR", "lnT"):
            ln.set("w", "0")
            noFill = OxmlElement("a:noFill")
            ln.append(noFill)
        else:
            ln.set("w", border_width)
            solidFill = OxmlElement("a:solidFill")
            srgbClr = OxmlElement("a:srgbClr")
            srgbClr.set("val", border_color)
            solidFill.append(srgbClr)
            ln.append(solidFill)
        tcPr.append(ln)


def add_rect(slide, x, y, w, h, fill=None, border=None, border_pt=0.75, rounded=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded and len(shp.adjustments) > 0:
        shp.adjustments[0] = 0.04
    if fill is not None:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    else:
        shp.fill.background()
    if border is not None:
        shp.line.color.rgb = border
        shp.line.width = Pt(border_pt)
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def add_text(slide, x, y, w, h, text, size=12, color=SLATE_DARK, bold=False, italic=False,
             align=PP_ALIGN.LEFT, font_name=FONT_MAIN, line_spacing=1.18, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Inches(0)
    tf.margin_right = Inches(0)
    tf.margin_top = Inches(0)
    tf.margin_bottom = Inches(0)
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    run = p.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    return tb


def add_bullets(slide, x, y, w, h, items, size=11.5, color=SLATE_BODY, lead_color=NAVY_DEEP,
                line_spacing=1.22, space_after=6, bullet_char="• "):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0)
    tf.margin_right = Inches(0)
    tf.margin_top = Inches(0)
    tf.margin_bottom = Inches(0)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        if isinstance(item, tuple):
            lead, body = item
            r0 = p.add_run()
            r0.text = bullet_char + lead
            r0.font.name = FONT_MAIN
            r0.font.size = Pt(size)
            r0.font.bold = True
            r0.font.color.rgb = lead_color
            if body:
                r1 = p.add_run()
                r1.text = " " + body
                r1.font.name = FONT_MAIN
                r1.font.size = Pt(size)
                r1.font.bold = False
                r1.font.color.rgb = color
        else:
            r0 = p.add_run()
            r0.text = bullet_char + item
            r0.font.name = FONT_MAIN
            r0.font.size = Pt(size)
            r0.font.color.rgb = color
    return tb


def add_header(slide, kicker, title, dark=False):
    kicker_col = TEAL
    title_col = WHITE if dark else NAVY_DEEP
    add_text(slide, 0.65, 0.34, 10.0, 0.25, kicker.upper(), size=9.5, color=kicker_col, bold=True)
    add_text(slide, 0.65, 0.58, 12.0, 0.48, title, size=22, color=title_col, bold=True, line_spacing=1.1)
    # Gạch nhấn tinh tế 0.55 inch thay vì kẻ ngang toàn slide
    add_rect(slide, 0.65, 1.10, 0.55, 0.04, fill=TEAL)


def add_footer(slide, num, total=23, dark=False):
    col = SLATE_LIGHT if dark else SLATE_MUTED
    num_col = TEAL if dark else NAVY_DEEP
    add_rect(slide, 0.65, 7.02, 12.03, 0.01, fill=NAVY_BORDER if dark else BORDER_LIGHT)
    add_text(slide, 0.65, 7.08, 9.5, 0.28,
             "Smart Shopping Cart IoT · Hệ thống mô phỏng xe đẩy hàng thông minh", size=9.5, color=col)
    add_text(slide, 11.4, 7.08, 1.28, 0.28, f"{num:02d} / {total}", size=9.5, color=num_col,
             bold=True, align=PP_ALIGN.RIGHT)


def add_pic_fit(slide, img_path, x, y, max_w, max_h, frame=True, border_col=BORDER_LIGHT):
    with Image.open(img_path) as im:
        pw, ph = im.size
    ratio = pw / ph
    box_ratio = max_w / max_h
    if ratio >= box_ratio:
        w = max_w
        h = w / ratio
    else:
        h = max_h
        w = h * ratio
    cx = x + (max_w - w) / 2
    cy = y + (max_h - h) / 2
    if frame:
        add_rect(slide, cx - 0.03, cy - 0.03, w + 0.06, h + 0.06, fill=WHITE, border=border_col, border_pt=0.75)
    slide.shapes.add_picture(img_path, Inches(cx), Inches(cy), width=Inches(w), height=Inches(h))
    return cx, cy, w, h


def add_modern_table(slide, x, y, w, h, rows, col_widths, font_size=10, header_bg=NAVY_DEEP):
    n_rows = len(rows)
    n_cols = len(rows[0])
    shape = slide.shapes.add_table(n_rows, n_cols, Inches(x), Inches(y), Inches(w), Inches(h))
    tbl = shape.table
    for ci, cw in enumerate(col_widths):
        tbl.columns[ci].width = Inches(cw)

    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            set_cell_margins(cell, 0.10, 0.10, 0.06, 0.06)
            cell.fill.solid()
            if ri == 0:
                cell.fill.fore_color.rgb = header_bg
                set_cell_border(cell, "101A2B", "12700")
            else:
                cell.fill.fore_color.rgb = WHITE if ri % 2 == 1 else ROW_ALT
                set_cell_border(cell, "E2E8F0", "9525")

            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.line_spacing = 1.15
            run = p.add_run()
            run.text = val
            run.font.name = FONT_MAIN
            if ri == 0:
                run.font.size = Pt(font_size)
                run.font.bold = True
                run.font.color.rgb = WHITE
            else:
                run.font.size = Pt(font_size - 0.5 if len(val) > 65 else font_size)
                run.font.bold = (ci == 0)
                if "PASS" in val or "Đã kiểm chứng" in val or "FastAPI" in val and ci == 2:
                    run.font.color.rgb = EMERALD if ("PASS" in val or "Đã kiểm chứng" in val) else NAVY_DEEP
                else:
                    run.font.color.rgb = NAVY_DEEP if ci == 0 else SLATE_BODY
    return shape


# ==============================================================================
# XÂY DỰNG TỪNG SLIDE (23 SLIDES)
# ==============================================================================
def build():
    with open("scratch/slide_meta.json", "r", encoding="utf-8") as f:
        meta = json.load(f)
    notes_map = {m["slide_index"] - 1: m["notes"] for m in meta}

    prs = pptx.Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # --------------------------------------------------------------------------
    # SLIDE 1: TRANG BÌA (ASYMMETRIC EDITORIAL, DEEP NAVY)
    # --------------------------------------------------------------------------
    s1 = prs.slides.add_slide(blank)
    set_bg(s1, NAVY_DEEP)

    # Cột Trái: Tiêu đề & Phân cấp rõ ràng
    add_text(s1, 0.80, 1.05, 6.8, 0.30, "ĐỒ ÁN HỆ THỐNG IoT  ·  SMART RETAIL", size=10.5, color=TEAL, bold=True)
    add_text(s1, 0.80, 1.50, 7.1, 0.60, "Hệ Thống Xe Đẩy Hàng Thông Minh", size=29, color=WHITE, bold=True)
    add_text(s1, 0.80, 2.08, 7.1, 0.55, "Ứng Dụng IoT", size=29, color=TEAL, bold=True)
    add_text(s1, 0.80, 2.72, 6.8, 0.35, "SMART SHOPPING CART SYSTEM", size=12.5, color=SLATE_LIGHT, bold=True)
    add_rect(s1, 0.80, 3.22, 1.10, 0.045, fill=TEAL)
    add_text(s1, 0.80, 3.48, 6.9, 1.05,
             "Phân tích kiến trúc, giao tiếp MQTT, xử lý nghiệp vụ Backend, cơ sở dữ liệu, giao diện Realtime và kiểm thử hệ thống mô phỏng.",
             size=13, color=SLATE_TEXT_ON_DARK, line_spacing=1.35)
    add_text(s1, 0.80, 5.10, 6.9, 0.65,
             "Báo cáo kỹ thuật chuyên sâu · Hoàn thiện toàn diện sau Technical Audit\n131/131 bài kiểm thử tự động PASS · PlatformIO Firmware Build 100%",
             size=10.5, color=SLATE_LIGHT, line_spacing=1.4)

    # Cột Phải: Phạm vi đề tài + Ngăn xếp công nghệ phân lớp
    # Khối 1: Phạm vi đề tài gọn, tinh tế
    add_rect(s1, 8.20, 1.05, 4.45, 2.05, fill=NAVY_SURFACE, border=NAVY_BORDER, border_pt=0.75, rounded=True)
    add_rect(s1, 8.20, 1.25, 0.06, 1.65, fill=TEAL)
    add_text(s1, 8.45, 1.22, 4.0, 0.28, "PHẠM VI ĐỀ TÀI & TÍNH TRUNG THỰC", size=9.5, color=TEAL, bold=True)
    add_text(s1, 8.45, 1.55, 3.98, 1.40,
             "Hệ thống mô phỏng bằng Python Smart Cart Simulator (3 xe) và Firmware ESP32 kết hợp cấu hình Wokwi. Không lắp ráp phần cứng vật lý. Dữ liệu cân nặng, pin và quét mã là dữ liệu mô phỏng phục vụ kiểm chứng kiến trúc phần mềm.",
             size=10.5, color=SLATE_TEXT_ON_DARK, line_spacing=1.32)

    # Khối 2: Công nghệ theo từng lớp kiến trúc (đồng đều, không tràn ô)
    add_rect(s1, 8.20, 3.30, 4.45, 3.15, fill=NAVY_SURFACE, border=NAVY_BORDER, border_pt=0.75, rounded=True)
    add_text(s1, 8.45, 3.48, 4.0, 0.28, "NGĂN XẾP CÔNG NGHỆ CHÍNH", size=9.5, color=TEAL, bold=True)

    tech_layers = [
        ("Backend API:", "FastAPI + Pydantic"),
        ("Cơ sở dữ liệu:", "PostgreSQL 16 & SQLite"),
        ("Giao tiếp IoT:", "MQTT 3.1.1 + HMAC"),
        ("Realtime:", "WebSocket (/ws :8000 & :8081)"),
        ("Giao diện Web:", "React 19 + esbuild"),
        ("Phần cứng biên:", "ESP32 / PlatformIO / Wokwi"),
    ]
    ty = 3.88
    for lbl, val in tech_layers:
        add_text(s1, 8.45, ty, 1.45, 0.34, lbl, size=10, color=SLATE_LIGHT, bold=False)
        add_text(s1, 9.88, ty, 2.65, 0.34, val, size=10, color=WHITE, bold=True)
        if ty < 5.9:
            add_rect(s1, 8.45, ty + 0.34, 3.98, 0.008, fill=NAVY_BORDER)
        ty += 0.40

    add_rect(s1, 0.80, 6.88, 11.85, 0.01, fill=NAVY_BORDER)
    add_text(s1, 0.80, 6.98, 8.5, 0.28, "Smart Shopping Cart IoT · Technical Architecture & Implementation", size=9.5, color=SLATE_LIGHT)
    add_text(s1, 10.6, 6.98, 2.05, 0.28, "2026 · 23 Slides", size=9.5, color=TEAL, bold=True, align=PP_ALIGN.RIGHT)

    # --------------------------------------------------------------------------
    # SLIDE 2: BỐI CẢNH & BÀI TOÁN CẦN GIẢI QUYẾT (3 CỘT TỐI GIẢN + BANNER)
    # --------------------------------------------------------------------------
    s2 = prs.slides.add_slide(blank)
    set_bg(s2, OFF_WHITE)
    add_header(s2, "01 · Bối cảnh & Đặt vấn đề", "Các Vấn Đề Cốt Lõi Trong Vận Hành Bán Lẻ Truyền Thống")
    add_footer(s2, 2)

    problems = [
        ("01", "Ùn tắc tại quầy thu ngân", [
            ("Xếp hàng giờ cao điểm:", "Khách hàng phải chờ nhân viên quét lại từng mặt hàng gây ùn ứ tại quầy."),
            ("Thiếu chủ động chi tiêu:", "Không nắm được tổng tiền giỏ hàng theo thời gian thực khi đang di chuyển."),
            ("Trải nghiệm gián đoạn:", "Quy trình thanh toán thủ công tốn nhân lực vận hành."),
        ]),
        ("02", "Sai sót & Thất thoát hàng hoá", [
            ("Bỏ hàng không quét:", "Khách quên hoặc cố ý bỏ sản phẩm vào giỏ mà không quét mã vạch."),
            ("Thiếu cơ chế đối soát:", "Xe đẩy truyền thống không có cảm biến trọng lượng kiểm chứng chéo."),
            ("Khó phát hiện tức thì:", "Chỉ phát hiện thất thoát khi kiểm kê cuối kỳ hoặc tại cổng từ."),
        ]),
        ("03", "Thiếu giám sát đội xe đẩy", [
            ("Không rõ trạng thái:", "Quản lý không biết xe nào đang rảnh, đang sử dụng hay gặp sự cố."),
            ("Xe sập nguồn giữa chừng:", "Không cảnh báo pin yếu sớm gây gián đoạn quá trình mua sắm."),
            ("Không có khả năng khoá từ xa:", "Thiếu kênh điều khiển khẩn cấp khi xe có dấu hiệu bất thường."),
        ]),
    ]
    cx = 0.65
    for idx_p, (num, ptitle, pbullets) in enumerate(problems):
        add_text(s2, cx, 1.40, 1.0, 0.50, num, size=26, color=TEAL, bold=True)
        add_text(s2, cx, 1.92, 3.65, 0.38, ptitle, size=14, color=NAVY_DEEP, bold=True)
        add_bullets(s2, cx, 2.38, 3.65, 2.45, pbullets, size=11, space_after=8)
        if idx_p < 2:
            add_rect(s2, cx + 3.92, 1.48, 0.012, 3.20, fill=BORDER_LIGHT)
        cx += 4.18

    # Solution Banner dưới chân (Deep Navy)
    add_rect(s2, 0.65, 5.05, 12.03, 1.65, fill=NAVY_DEEP, rounded=True)
    add_rect(s2, 0.65, 5.05, 0.08, 1.65, fill=TEAL)
    add_text(s2, 0.95, 5.20, 11.4, 0.30, "CƠ HỘI TỪ GIẢI PHÁP SMART SHOPPING CART IoT", size=10.5, color=TEAL, bold=True)
    add_bullets(s2, 0.95, 5.54, 11.4, 1.05, [
        ("Tự động hoá tại biên (Edge):", "Xe tự đọc mã vạch, đo cân nặng và giám sát pin, đẩy dữ liệu theo sự kiện qua giao thức MQTT nhẹ."),
        ("Đồng bộ hoá Realtime:", "Backend FastAPI xử lý tính tiền tức thì, cảnh báo lệch cân >100g, đồng bộ hai chiều tới Customer UI và Admin Dashboard."),
    ], size=11, color=SLATE_TEXT_ON_DARK, lead_color=WHITE, space_after=5)

    # --------------------------------------------------------------------------
    # SLIDE 3: MỤC TIÊU HỆ THỐNG & PHẠM VI (4 KPI STRIP + 2 SPLIT PANELS)
    # --------------------------------------------------------------------------
    s3 = prs.slides.add_slide(blank)
    set_bg(s3, OFF_WHITE)
    add_header(s3, "02 · Mục tiêu & Phạm vi", "Mục Tiêu Kỹ Thuật & Ranh Giới Trung Thực Đề Tài")
    add_footer(s3, 3)

    kpis = [
        ("3 Xe + ESP32", "Mô phỏng đồng thời qua MQTT", TEAL),
        ("3 Luật Cảnh Báo", "Pin <20% · Lệch >100g · Offline >15s", AMBER),
        ("Realtime /ws", "WebSocket gom cổng FastAPI (:8000)", BLUE),
        ("3 Lớp Bảo Mật", "RBAC · MQTT ACL/TLS · HMAC-SHA256", EMERALD),
    ]
    kx = 0.65
    for ktitle, ksub, kcol in kpis:
        add_rect(s3, kx, 1.38, 2.82, 1.15, fill=WHITE, border=BORDER_LIGHT, rounded=True)
        add_rect(s3, kx, 1.38, 2.82, 0.05, fill=kcol)
        add_text(s3, kx + 0.18, 1.56, 2.46, 0.40, ktitle, size=16, color=NAVY_DEEP, bold=True)
        add_text(s3, kx + 0.18, 2.00, 2.46, 0.42, ksub, size=10, color=SLATE_MUTED)
        kx += 3.07

    # 2 Panels dưới
    add_rect(s3, 0.65, 2.80, 5.88, 3.95, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_text(s3, 0.90, 3.00, 5.38, 0.34, "Mục tiêu kỹ thuật đã triển khai", size=14, color=NAVY_DEEP, bold=True)
    add_bullets(s3, 0.90, 3.45, 5.38, 3.15, [
        ("Vòng đời phiên mua hàng:", "Chọn xe rảnh & online -> quét ADD/REMOVE -> cập nhật giỏ hàng và tổng tiền tức thì -> checkout nguyên tử."),
        ("Cảnh báo bất thường tự động:", "Tự kích hoạt và tự đóng khi hết vi phạm, chống trùng cảnh báo nhờ Partial Unique Index."),
        ("Điều khiển từ xa có xác thực:", "Admin gửi lệnh LOCK/UNLOCK qua MQTT, chờ ACK tối đa 5s, lưu vết lệnh vào bảng cart_commands."),
        ("Chịu lỗi mất kết nối:", "Offline Queue FIFO trên Simulator tự động xả hàng đợi và _reconcile() trạng thái khi online lại."),
    ], size=11, space_after=8)

    add_rect(s3, 6.80, 2.80, 5.88, 3.95, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_rect(s3, 6.80, 2.80, 0.06, 3.95, fill=AMBER)
    add_text(s3, 7.08, 3.00, 5.38, 0.34, "Phạm vi & Ranh giới trung thực", size=14, color=NAVY_DEEP, bold=True)
    add_bullets(s3, 7.08, 3.45, 5.38, 3.15, [
        ("Hệ thống mô phỏng 100%:", "Dùng Python SmartCart Simulator (3 xe) để kiểm chứng nghiệp vụ end-to-end, không gắn phần cứng vật lý."),
        ("Firmware ESP32 & Wokwi:", "Mã nguồn C++11 đã biên dịch thành công 100% qua PlatformIO; cấu hình sẵn 3 chế độ Wokwi nhưng chưa đo trên mạch thật."),
        ("Dữ liệu cảm biến giả lập:", "Cân nặng (nhiễu Gauss ±3g), điện áp pin và mã vạch đều là dữ liệu mô phỏng, không phải dữ liệu đo vật lý."),
        ("Thanh toán trên Web UI:", "Tác vụ thanh toán được thiết kế trên Customer Web UI để tối ưu trải nghiệm thay vì thực hiện trên màn hình OLED nhỏ của xe."),
    ], size=11, space_after=8)

    # --------------------------------------------------------------------------
    # SLIDE 4: TỔNG QUAN GIẢI PHÁP & PHÂN QUYỀN RBAC
    # --------------------------------------------------------------------------
    s4 = prs.slides.add_slide(blank)
    set_bg(s4, OFF_WHITE)
    add_header(s4, "03 · Tổng quan giải pháp", "Ba Phân Hệ Giao Diện & Ma Trận Phân Quyền RBAC")
    add_footer(s4, 4)

    apps = [
        ("1. Customer UI (/customer)", TEAL, [
            ("Không cần tài khoản:", "Khách chọn xe AVAILABLE & ONLINE để mở phiên, nhận session_token gắn chặt ID phiên."),
            ("Giỏ hàng Realtime:", "Hiển thị sản phẩm, cân nặng kỳ vọng/thực tế, cảnh báo lệch cân và xác nhận thanh toán."),
        ]),
        ("2. Admin Dashboard (/admin)", BLUE, [
            ("Giám sát tập trung:", "Theo dõi trạng thái online/offline, pin, tải trọng của toàn bộ đội xe theo thời gian thực."),
            ("Điều khiển & Quản trị:", "Xem biểu đồ lịch sử telemetry SVG, lọc cảnh báo, khoá/mở khoá xe và CRUD sản phẩm."),
        ]),
        ("3. Simulator & ESP32 (/simulator)", EMERALD, [
            ("Điều khiển xe ảo:", "Bảng điều khiển tương tác qua HTTP :8090 mô phỏng quét mã, thay đổi pin, lệch cân và ngắt mạng."),
            ("Tương thích ESP32:", "Dùng chung hợp đồng 6 MQTT topic chuẩn với firmware ESP32 biên dịch từ PlatformIO."),
        ]),
    ]
    ax = 0.65
    for atitle, acol, abullets in apps:
        add_rect(s4, ax, 1.38, 3.82, 2.70, fill=WHITE, border=BORDER_LIGHT, rounded=True)
        add_rect(s4, ax, 1.38, 3.82, 0.05, fill=acol)
        add_text(s4, ax + 0.20, 1.54, 3.42, 0.34, atitle, size=13, color=NAVY_DEEP, bold=True)
        add_bullets(s4, ax + 0.20, 1.96, 3.42, 2.00, abullets, size=10.5, space_after=6)
        ax += 4.10

    add_text(s4, 0.65, 4.30, 6.0, 0.28, "MA TRẬN PHÂN QUYỀN 4 VAI TRÒ (backend/auth.py)", size=9.5, color=TEAL_DARK, bold=True)
    rbac_rows = [
        ["Vai trò (Role)", "Cơ chế xác thực", "Phạm vi truy cập thực tế"],
        ["anonymous", "Không cần token", "Xem sản phẩm đang bán, xem xe (đã che chi tiết giỏ), đăng nhập hoặc mở phiên mới (rate-limit 20/phút/IP)"],
        ["customer", "Session Token (hạn 4h)", "Chỉ xem/thêm/xoá/thanh toán/huỷ đúng phiên của mình (gắn sid & cart_id chống IDOR)"],
        ["viewer", "Bearer Token (hạn 8h)", "Nhân viên giám sát: xem toàn bộ Dashboard, danh sách cảnh báo, lịch sử telemetry & lệnh (chỉ đọc)"],
        ["admin", "Bearer Token (hạn 8h)", "Toàn quyền: đăng ký xe mới, khoá/mở khoá xe, huỷ phiên treo, thêm/sửa/ẩn sản phẩm"],
    ]
    add_modern_table(s4, 0.65, 4.62, 12.03, 2.15, rbac_rows, [1.80, 2.40, 7.83], font_size=10)

    # --------------------------------------------------------------------------
    # SLIDE 5: KIẾN TRÚC TỔNG THỂ & 5 TẦNG IoT
    # --------------------------------------------------------------------------
    s5 = prs.slides.add_slide(blank)
    set_bg(s5, OFF_WHITE)
    add_header(s5, "04 · Kiến trúc hệ thống", "Kiến Trúc IoT 5 Tầng & Sơ Đồ Kết Nối Thực Tế")
    add_footer(s5, 5)

    add_pic_fit(s5, f"{DIAG_DIR}/diagram_architecture.png", 0.65, 1.38, 8.15, 5.35, frame=True)

    add_rect(s5, 9.00, 1.38, 3.68, 5.35, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_text(s5, 9.20, 1.54, 3.28, 0.30, "Ánh xạ 5 tầng kiến trúc IoT", size=13, color=NAVY_DEEP, bold=True)

    tiers = [
        ("1. Perception", "Cảm biến cân, mã vạch, pin (mô phỏng bởi SmartCart Python & định nghĩa ở firmware/pins.h).", TEAL),
        ("2. Edge Processing", "Lọc trung vị-5 + EMA, chuẩn hoá mã, CartLogic idempotent, Offline Queue (FIFO ≤ 50).", EMERALD),
        ("3. Network", "MQTT 3.1.1 (mqttlite / PubSubClient) + cầu nối Wokwi RFC2217 (:4000).", AMBER),
        ("4. Platform", "Mosquitto / DevBroker + FastAPI Backend + Dual-Engine (Postgres 16 & SQLite) + Alert Engine.", BLUE),
        ("5. Application", "React 19 SPA (/customer, /admin, /simulator) cập nhật qua REST & WS /ws (:8000).", NAVY_DEEP),
    ]
    ty = 1.98
    for tname, tdesc, tcol in tiers:
        add_rect(s5, 9.20, ty + 0.04, 0.08, 0.72, fill=tcol)
        add_text(s5, 9.38, ty, 3.15, 0.25, tname, size=10.5, color=NAVY_DEEP, bold=True)
        add_text(s5, 9.38, ty + 0.25, 3.15, 0.55, tdesc, size=9.5, color=SLATE_BODY, line_spacing=1.18)
        ty += 0.92

    # --------------------------------------------------------------------------
    # SLIDE 6: STACK CÔNG NGHỆ & ĐỐI CHIẾU THIẾT KẾ
    # --------------------------------------------------------------------------
    s6 = prs.slides.add_slide(blank)
    set_bg(s6, OFF_WHITE)
    add_header(s6, "05 · Công nghệ sử dụng", "Ngăn Xếp Công Nghệ & Đối Chiếu Kiểm Chứng Source Code")
    add_footer(s6, 6)

    stack_rows = [
        ["Thành phần", "Công nghệ triển khai", "Vai trò & Chi tiết trong Source Code", "Trạng thái"],
        ["Backend & API", "FastAPI + Uvicorn + Pydantic", "26 REST endpoints, Swagger UI (/docs), ReDoc (/redoc), tương thích /api/docs", "Đã kiểm chứng"],
        ["Cơ sở dữ liệu", "PostgreSQL 16 (psycopg 3) & SQLite", "Kiến trúc Dual-Engine (db.py): 7 bảng, giao dịch nguyên tử tx(), bảng cart_commands", "Đã kiểm chứng"],
        ["WebSocket", "Native FastAPI /ws (:8000) & :8081", "Gom cổng trên FastAPI + auth handshake + lọc sự kiện theo vai trò (Hub.project)", "Đã kiểm chứng"],
        ["MQTT Client/Broker", "mqttlite.py + Mosquitto / DevBroker", "6 topics chuẩn (QoS 0), HMAC-SHA256, chống trùng LRU 2000, backoff reconnect", "Đã kiểm chứng"],
        ["Python Simulator", "SmartCart + ControlServer (:8090)", "3 xe ảo, nhiễu cân ±3g, Offline Queue FIFO, bảo vệ bằng SIM_CONTROL_TOKEN", "Đã kiểm chứng"],
        ["ESP32 & Wokwi", "C++11 (cartcore) + PlatformIO", "Tách logic thuần khỏi Arduino.h; build firmware.bin thành công 2 target", "Build 100% OK"],
        ["Frontend Web", "React 19 + esbuild + CSS thuần", "Đóng gói tĩnh vào frontend/dist/, biểu đồ SVG, 20/20 E2E Playwright tests", "Đã kiểm chứng"],
    ]
    add_modern_table(s6, 0.65, 1.38, 12.03, 4.45, stack_rows, [1.85, 2.85, 5.73, 1.60], font_size=10)

    add_rect(s6, 0.65, 6.02, 12.03, 0.80, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_rect(s6, 0.65, 6.02, 0.06, 0.80, fill=TEAL)
    add_text(s6, 0.90, 6.12, 11.5, 0.24, "Thiết kế ranh giới module (Clean Architectural Boundaries)", size=10.5, color=NAVY_DEEP, bold=True)
    add_text(s6, 0.90, 6.38, 11.5, 0.36,
             "Mỗi tầng hạ tầng (Database Dual-Engine, FastAPI Router, WebSocket Hub, MQTT Gateway) đều nằm sau interface tách biệt, cho phép chuyển đổi giữa SQLite (test nhanh) và PostgreSQL 16 (Docker/Prod) mà không sửa tầng nghiệp vụ services/.",
             size=10, color=SLATE_BODY)

    # --------------------------------------------------------------------------
    # SLIDE 7: LUỒNG DỮ LIỆU END-TO-END (DFD)
    # --------------------------------------------------------------------------
    s7 = prs.slides.add_slide(blank)
    set_bg(s7, OFF_WHITE)
    add_header(s7, "06 · Luồng dữ liệu", "Quy Trình Hoạt Động & Luồng Dữ Liệu End-to-End")
    add_footer(s7, 7)

    add_pic_fit(s7, f"{DIAG_DIR}/diagram_dataflow.png", 0.65, 1.35, 12.03, 4.25, frame=True)

    checkpoints = [
        ("Luồng Uplink (Thiết bị -> DB)", "Mọi gói scan, telemetry, heartbeat đi qua Gateway xác thực chữ ký HMAC và chống trùng trước khi lưu CSDL và kích hoạt Alert Engine.", TEAL),
        ("Single Source of Truth", "Trạng thái giỏ hàng và xe luôn lấy Backend làm chuẩn. Telemetry chỉ cập nhật cân/pin, không tự ý đổi trạng thái phiên.", BLUE),
        ("Luồng Downlink (Admin -> Xe)", "Lệnh khoá/mở xe lưu vào cart_commands (PENDING), đẩy qua MQTT command và đợi xe phản hồi ACK trước khi trả kết quả HTTP.", ROSE),
    ]
    cx = 0.65
    for ctitle, cbody, ccol in checkpoints:
        add_rect(s7, cx, 5.75, 3.82, 1.05, fill=WHITE, border=BORDER_LIGHT, rounded=True)
        add_rect(s7, cx, 5.75, 0.06, 1.05, fill=ccol)
        add_text(s7, cx + 0.18, 5.83, 3.52, 0.24, ctitle, size=10.5, color=NAVY_DEEP, bold=True)
        add_text(s7, cx + 0.18, 6.08, 3.52, 0.66, cbody, size=9.2, color=SLATE_BODY, line_spacing=1.18)
        cx += 4.10

    # --------------------------------------------------------------------------
    # SLIDE 8: FIRMWARE ESP32 & WOKWI
    # --------------------------------------------------------------------------
    s8 = prs.slides.add_slide(blank)
    set_bg(s8, OFF_WHITE)
    add_header(s8, "07 · Phần cứng nhúng & Wokwi", "Thiết Kế Firmware ESP32 & 3 Chế Độ Mô Phỏng Wokwi")
    add_footer(s8, 8)

    add_pic_fit(s8, f"{DIAG_DIR}/diagram_esp32_wokwi.png", 0.65, 1.35, 12.03, 4.15, frame=True)

    add_rect(s8, 0.65, 5.65, 5.88, 1.15, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_rect(s8, 0.65, 5.65, 0.06, 1.15, fill=TEAL)
    add_text(s8, 0.88, 5.74, 5.45, 0.25, "Kiến trúc tách lớp lib/cartcore (C++11 thuần)", size=11, color=NAVY_DEEP, bold=True)
    add_text(s8, 0.88, 6.02, 5.45, 0.70,
             "Tách logic nghiệp vụ (JSON parser, WeightFilter median-5 + EMA, CartLogic state machine, HMAC-SHA256) khỏi Arduino.h để unit test trên PC. Vòng lặp main.cpp chạy non-blocking theo millis(); đo pin qua ADC1 GPIO34 tránh xung đột Wi-Fi.",
             size=9.5, color=SLATE_BODY, line_spacing=1.2)

    add_rect(s8, 6.80, 5.65, 5.88, 1.15, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_rect(s8, 6.80, 5.65, 0.06, 1.15, fill=EMERALD)
    add_text(s8, 7.03, 5.74, 5.45, 0.25, "Kết quả kiểm chứng PlatformIO & Ranh giới", size=11, color=NAVY_DEEP, bold=True)
    add_text(s8, 7.03, 6.02, 5.45, 0.70,
             "Đã biên dịch thành công 100% file nhị phân firmware.bin cho cả esp32dev_sim (41.96s) và esp32dev_sim_bridge (62.54s). Khớp toàn bộ sơ đồ chân GPIO giữa diagram.json và pins.h. Chưa chạy thử nghiệm trên board ESP32 vật lý thật.",
             size=9.5, color=SLATE_BODY, line_spacing=1.2)

    # --------------------------------------------------------------------------
    # SLIDE 9: PYTHON SIMULATOR & OFFLINE QUEUE
    # --------------------------------------------------------------------------
    s9 = prs.slides.add_slide(blank)
    set_bg(s9, OFF_WHITE)
    add_header(s9, "08 · Python Simulator", "Python Smart Cart Simulator & Hàng Đợi Ngoại Tuyến")
    add_footer(s9, 9)

    add_pic_fit(s9, f"{SHOT_DIR}/13_simulator_phan_cung.png", 0.65, 1.40, 6.85, 4.95, frame=True)
    add_text(s9, 0.65, 6.42, 6.85, 0.28, "Ảnh chụp thực tế trang điều khiển /simulator (Playwright E2E)",
             size=9.5, color=SLATE_MUTED, italic=True, align=PP_ALIGN.CENTER)

    sim_cards = [
        ("1. Mô phỏng đa xe độc lập", [
            ("3 xe đồng thời:", "CART_001..003 chạy các luồng MQTT và vật lý độc lập hoàn toàn."),
            ("Nhiễu & Pin thực tế:", "Cân nặng có nhiễu Gaussian ±3g; pin tự sụt 0.2%/phút khi hoạt động."),
        ], TEAL),
        ("2. Offline Queue FIFO & Tự phục hồi", [
            ("Chống mất gói QoS 0:", "Khi xe mất mạng (go_offline), các lượt quét được đẩy vào offline_queue (≤ 50)."),
            ("Xả hàng đợi tự động:", "Khi online lại, _on_connected() gọi drain_offline_queue() gửi bù theo FIFO."),
        ], EMERALD),
        ("3. Simulator Control API (:8090)", [
            ("Giao diện điều khiển:", "Cung cấp REST API cho trang /simulator thao tác quét mã, pin, độ lệch cân, ngắt mạng."),
            ("Bảo mật Token:", "Hỗ trợ xác thực Bearer / X-Sim-Token qua biến SIM_CONTROL_TOKEN."),
        ], BLUE),
    ]
    sy = 1.40
    for stitle, sbullets, scol in sim_cards:
        add_rect(s9, 7.75, sy, 4.93, 1.65, fill=WHITE, border=BORDER_LIGHT, rounded=True)
        add_rect(s9, 7.75, sy, 0.06, 1.65, fill=scol)
        add_text(s9, 7.98, sy + 0.12, 4.55, 0.28, stitle, size=12, color=NAVY_DEEP, bold=True)
        add_bullets(s9, 7.98, sy + 0.44, 4.55, 1.12, sbullets, size=10, space_after=4)
        sy += 1.82

    # --------------------------------------------------------------------------
    # SLIDE 10: GIAO TIẾP MQTT (6 TOPICS & JSON ENVELOPE)
    # --------------------------------------------------------------------------
    s10 = prs.slides.add_slide(blank)
    set_bg(s10, OFF_WHITE)
    add_header(s10, "09 · Giao tiếp MQTT", "Hợp Đồng MQTT: 6 Topics & JSON Envelope Thống Nhất")
    add_footer(s10, 10)

    # Code Snippet Envelope (Dark Navy panel)
    add_rect(s10, 0.65, 1.35, 12.03, 1.18, fill=NAVY_DEEP, rounded=True)
    add_rect(s10, 0.65, 1.35, 0.07, 1.18, fill=TEAL)
    add_text(s10, 0.90, 1.45, 4.5, 0.24, "JSON ENVELOPE CHUẨN (schema_version = 1)", size=9.5, color=TEAL, bold=True)
    add_text(s10, 0.90, 1.74, 11.6, 0.70,
             '{"message_id": "6f1c2a9e-...", "cart_id": "CART_001", "schema_version": 1, "timestamp": "2026-11-17T10:30:00Z", "sig": "<HMAC-SHA256>", "data": {...}}',
             size=10.5, color=WHITE, font_name=FONT_MONO)

    mqtt_rows = [
        ["Topic (smartcart/{cart_id}/...)", "Hướng", "Tần suất", "Nội dung data chính (shared/contract.py)"],
        [".../scan", "Xe -> Backend", "Khi quét", '{"scan_id":"uuid", "barcode":"8934673100019", "action":"ADD|REMOVE"}'],
        [".../telemetry", "Xe -> Backend", "5s / thay đổi", '{"actual_weight":1030.0, "battery_percent":85.0, "cart_status":"IN_USE", "wifi_status":"..."}'],
        [".../heartbeat", "Xe -> Backend", "Mỗi 5s", '{"uptime_s":1240, "cart_status":"AVAILABLE"}'],
        [".../event", "Xe -> Backend", "Khi có sự cố", '{"event_type":"UNKNOWN_BARCODE|CART_LOCKED|SCAN_REJECTED", "description":"..."}'],
        [".../command", "Backend -> Xe", "Theo lệnh", '{"command_id":"uuid", "command_type":"LOCK_CART|UNLOCK_CART|START_SESSION|END_SESSION"}'],
        [".../ack", "Xe -> Backend", "Ngay sau cmd", '{"command_id":"uuid", "result":"OK|FAILED", "message":"Đã khoá xe"}'],
    ]
    add_modern_table(s10, 0.65, 2.72, 12.03, 3.35, mqtt_rows, [2.75, 1.55, 1.45, 6.28], font_size=9.5)

    add_text(s10, 0.65, 6.22, 12.03, 0.50,
             "Lưu ý kỹ thuật: mqttlite.py sử dụng QoS 0 để tối ưu nhẹ gọn trên nhúng; độ tin cậy được bù đắp hoàn toàn ở tầng ứng dụng qua Offline Queue (Simulator), Command + ACK (chờ 5s), HeartbeatMonitor (thay cho LWT) và _reconcile() (thay cho Retained).",
             size=10, color=SLATE_MUTED, italic=True)

    # --------------------------------------------------------------------------
    # SLIDE 11: PIPELINE GATEWAY & PHỤC HỒI MẤT MẠNG
    # --------------------------------------------------------------------------
    s11 = prs.slides.add_slide(blank)
    set_bg(s11, OFF_WHITE)
    add_header(s11, "10 · Độ tin cậy MQTT", "Pipeline Xử Lý Gateway, Chống Trùng & Phục Hồi Kết Nối")
    add_footer(s11, 11)

    add_pic_fit(s11, f"{DIAG_DIR}/diagram_mqtt_pipeline.png", 0.65, 1.35, 12.03, 5.45, frame=True)

    # --------------------------------------------------------------------------
    # SLIDE 12: SEQUENCE DIAGRAM
    # --------------------------------------------------------------------------
    s12 = prs.slides.add_slide(blank)
    set_bg(s12, OFF_WHITE)
    add_header(s12, "11 · Trình tự tương tác", "Sequence Diagram: Mua Hàng Realtime & Khoá Xe Qua ACK")
    add_footer(s12, 12)

    add_pic_fit(s12, f"{DIAG_DIR}/diagram_sequence.png", 0.65, 1.32, 12.03, 4.75, frame=True)

    add_rect(s12, 0.65, 6.18, 5.88, 0.65, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_text(s12, 0.85, 6.25, 5.50, 0.50,
             "A. Eventual Realtime: Quét mã bất đồng bộ qua MQTT -> Backend cập nhật CSDL -> Đẩy CART_UPDATED qua WebSocket tới Customer UI.",
             size=9.5, color=SLATE_BODY)

    add_rect(s12, 6.80, 6.18, 5.88, 0.65, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_text(s12, 7.00, 6.25, 5.50, 0.50,
             "B. Sync-over-Async: HTTP /lock lưu PENDING vào CSDL, giữ kết nối chờ Event.wait(5s) cho đến khi xe gửi MQTT ack để trả HTTP 200 / 504.",
             size=9.5, color=SLATE_BODY)

    # --------------------------------------------------------------------------
    # SLIDE 13: BACKEND FASTAPI & 26 REST ENDPOINTS
    # --------------------------------------------------------------------------
    s13 = prs.slides.add_slide(blank)
    set_bg(s13, OFF_WHITE)
    add_header(s13, "12 · Backend & REST API", "Kiến Trúc Backend FastAPI & Thiết Kế 26 REST Endpoints")
    add_footer(s13, 13)

    # Cột trái: Kiến trúc & Concurrency
    add_rect(s13, 0.65, 1.38, 4.15, 5.38, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_rect(s13, 0.65, 1.38, 4.15, 0.05, fill=TEAL)
    add_text(s13, 0.88, 1.56, 3.70, 0.34, "Tổ chức Backend FastAPI", size=13.5, color=NAVY_DEEP, bold=True)
    add_bullets(s13, 0.88, 2.00, 3.70, 4.55, [
        ("FastAPI ASGI + OpenAPI:", "Tự động sinh Swagger UI tại /docs, ReDoc tại /redoc và giữ /api/docs tương thích ngược."),
        ("4 Luồng xử lý đồng thời:",
         "\n  1. Threadpool cho HTTP REST đồng bộ\n  2. Thread MQTT Consumer xử lý tuần tự\n  3. Thread HeartbeatMonitor quét 2s/lần\n  4. Event loop cho WebSocket /ws"),
        ("Security Headers:", "Middleware tự động chèn CSP, X-Frame-Options: DENY, nosniff, Cache-Control: no-store."),
        ("Validation & Rate Limit:", "Pydantic v2 kiểm tra payload đầu vào; giới hạn 64KB body và chống spam tạo phiên."),
    ], size=10.5, space_after=8)

    # Cột phải: Bảng 26 REST endpoints
    api_rows = [
        ["Nhóm (Số lượng)", "Các Endpoint chính (backend/api/routes.py)", "Quyền (auth)"],
        ["System (1)", "GET /api/health (CSDL, MQTT, WS, uptime, stats)", "public / staff"],
        ["Products (5)", "GET/POST /api/products, PUT/GET /api/products/{id}, GET .../barcode/{code}", "public / admin"],
        ["Carts (7)", "GET/POST /api/carts, GET .../telemetry, .../session, POST .../lock, .../unlock", "public / staff / admin"],
        ["Sessions (6)", "POST /api/sessions, GET .../sessions/{id}, POST/DEL .../items, .../checkout, .../cancel", "public / session"],
        ["Alerts (1)", "GET /api/alerts (lọc theo status=ACTIVE|RESOLVED & cart_id)", "staff"],
        ["Commands (2)", "GET /api/commands (lịch sử lệnh), GET /api/commands/{command_id}", "staff"],
        ["Auth (4)", "GET /api/auth/config, POST .../login, GET .../me, POST .../logout", "public / authenticated"],
    ]
    add_modern_table(s13, 5.05, 1.38, 7.63, 5.38, api_rows, [1.55, 4.48, 1.60], font_size=9.5)

    # --------------------------------------------------------------------------
    # SLIDE 14: NGHIỆP VỤ CỐT LÕI (VÒNG ĐỜI XE, PHIÊN & CHECKOUT)
    # --------------------------------------------------------------------------
    s14 = prs.slides.add_slide(blank)
    set_bg(s14, OFF_WHITE)
    add_header(s14, "13 · Nghiệp vụ cốt lõi", "Vòng Đời Xe, Toàn Vẹn Giỏ Hàng & Giao Dịch Checkout")
    add_footer(s14, 14)

    # Máy trạng thái xe trực quan phía trên
    add_rect(s14, 0.65, 1.38, 12.03, 1.85, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_text(s14, 0.90, 1.50, 5.0, 0.28, "MÁY TRẠNG THÁI XE ĐẨY (CART STATE MACHINE)", size=10, color=TEAL_DARK, bold=True)

    states = [
        (1.25, "AVAILABLE", "Sẵn sàng phục vụ\nChờ mở phiên mới", EMERALD, EMERALD_SOFT),
        (5.15, "IN_USE", "Đang có phiên ACTIVE\nCho phép quét & checkout", BLUE, TEAL_SOFT),
        (9.10, "LOCKED", "Khoá khẩn cấp từ Admin\nChặn quét & chặn checkout", ROSE, ROSE_SOFT),
    ]
    for sx, stitle, sdesc, scol, sbg in states:
        add_rect(s14, sx, 1.88, 2.95, 1.10, fill=sbg, border=scol, border_pt=1.5, rounded=True)
        add_text(s14, sx, 2.00, 2.95, 0.34, stitle, size=13, color=scol, bold=True, align=PP_ALIGN.CENTER)
        add_text(s14, sx, 2.38, 2.95, 0.50, sdesc, size=9.5, color=SLATE_DARK, align=PP_ALIGN.CENTER)

    # Mũi tên chuyển trạng thái bằng shape chuẩn PowerPoint (tránh lỗi thiếu font glyph)
    a1_r = s14.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(4.32), Inches(2.08), Inches(0.70), Inches(0.18))
    a1_r.fill.solid(); a1_r.fill.fore_color.rgb = NAVY_DEEP; a1_r.line.fill.background()
    a1_l = s14.shapes.add_shape(MSO_SHAPE.LEFT_ARROW, Inches(4.32), Inches(2.30), Inches(0.70), Inches(0.18))
    a1_l.fill.solid(); a1_l.fill.fore_color.rgb = TEAL; a1_l.line.fill.background()
    add_text(s14, 4.18, 2.54, 0.98, 0.45, "Start / End\nCheckout", size=8.5, color=SLATE_MUTED, align=PP_ALIGN.CENTER)

    a2_r = s14.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(8.22), Inches(2.08), Inches(0.70), Inches(0.18))
    a2_r.fill.solid(); a2_r.fill.fore_color.rgb = ROSE; a2_r.line.fill.background()
    a2_l = s14.shapes.add_shape(MSO_SHAPE.LEFT_ARROW, Inches(8.22), Inches(2.30), Inches(0.70), Inches(0.18))
    a2_l.fill.solid(); a2_l.fill.fore_color.rgb = EMERALD; a2_l.line.fill.background()
    add_text(s14, 8.12, 2.54, 0.96, 0.45, "LOCK / UNLOCK\n(ACK OK)", size=8.5, color=SLATE_MUTED, align=PP_ALIGN.CENTER)

    # 3 cột quy tắc nghiệp vụ phía dưới
    biz_cols = [
        ("1. Ràng buộc phiên duy nhất", [
            ("Tiền điều kiện:", "Chỉ mở phiên khi xe ONLINE và AVAILABLE."),
            ("Partial Unique Index:", "ux_active_session_per_cart bảo đảm ở mức CSDL mỗi xe tối đa 1 phiên ACTIVE dù request đến đồng thời."),
            ("Lưu vết lệnh:", "Mọi lệnh khoá/mở đều ghi vào bảng cart_commands."),
        ], TEAL),
        ("2. Toàn vẹn giỏ & Price Snapshot", [
            ("Gộp dòng hàng:", "Quét trùng sản phẩm tự tăng quantity; REMOVE giảm hoặc xoá dòng khi về 0."),
            ("Price Snapshot:", "Lưu trực tiếp unit_price vào cart_items lúc thêm. Admin sửa giá sau này không ảnh hưởng giỏ đang mua."),
            ("Chống trùng:", "Loại bỏ scan_id trùng lặp khi xe xả Offline Queue."),
        ], BLUE),
        ("3. Checkout nguyên tử (tx())", [
            ("Transaction:", "Cập nhật status=COMPLETED, tổng tiền, giải phóng xe -> AVAILABLE trong khối db.tx() duy nhất."),
            ("Rollback an toàn:", "Nếu lỗi giữa chừng hoặc xe đang LOCKED, giao dịch bị huỷ toàn bộ."),
            ("Ghi chú đối soát:", "Nếu còn cảnh báo ACTIVE lúc checkout -> lưu tự động vào cột note."),
        ], EMERALD),
    ]
    bx = 0.65
    for btitle, bbullets, bcol in biz_cols:
        add_rect(s14, bx, 3.45, 3.82, 3.30, fill=WHITE, border=BORDER_LIGHT, rounded=True)
        add_rect(s14, bx, 3.45, 3.82, 0.05, fill=bcol)
        add_text(s14, bx + 0.20, 3.62, 3.42, 0.32, btitle, size=12.5, color=NAVY_DEEP, bold=True)
        add_bullets(s14, bx + 0.20, 4.02, 3.42, 2.60, bbullets, size=10.5, space_after=6)
        bx += 4.10

    # --------------------------------------------------------------------------
    # SLIDE 15: ALERT ENGINE & HEARTBEAT MONITOR
    # --------------------------------------------------------------------------
    s15 = prs.slides.add_slide(blank)
    set_bg(s15, OFF_WHITE)
    add_header(s15, "14 · Alert Engine", "Hệ Thống Cảnh Báo Tự Động & Giám Sát Nhịp Tim")
    add_footer(s15, 15)

    add_pic_fit(s15, f"{DIAG_DIR}/diagram_alerts.png", 0.65, 1.35, 12.03, 5.45, frame=True)

    # --------------------------------------------------------------------------
    # SLIDE 16: WEBSOCKET REALTIME & PHÂN QUYỀN
    # --------------------------------------------------------------------------
    s16 = prs.slides.add_slide(blank)
    set_bg(s16, OFF_WHITE)
    add_header(s16, "15 · WebSocket Realtime", "WebSocket Gom Cổng (/ws) & Phân Quyền Sự Kiện")
    add_footer(s16, 16)

    # Cột trái: Thiết kế kỹ thuật
    add_rect(s16, 0.65, 1.38, 4.65, 5.38, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_rect(s16, 0.65, 1.38, 4.65, 0.05, fill=BLUE)
    add_text(s16, 0.88, 1.56, 4.20, 0.34, "Kiến trúc WebSocket Gom Cổng", size=13.5, color=NAVY_DEEP, bold=True)
    add_bullets(s16, 0.88, 2.00, 4.20, 4.55, [
        ("Tích hợp FastAPI /ws (:8000):", "Dùng @app.websocket('/ws') trên cổng HTTP chính qua adapter FastAPIWsConnection (đồng thời giữ :8081 tương thích)."),
        ("Xác thực an toàn:", "Kết nối xong gửi {'type':'AUTH', 'token':'...'}. Không truyền token lên URL để tránh lộ qua access log."),
        ("Hàng đợi không nghẽn:", "Hub dùng loop.call_soon_threadsafe() đẩy event vào asyncio.Queue riêng của từng client (giới hạn 200 clients)."),
        ("Fallback Polling 5s:", "Nếu mất kết nối WebSocket, React Store tự động fallback sang HTTP polling 5s/lần cho đến khi socket nối lại."),
    ], size=10.5, space_after=8)

    # Cột phải: Bảng Hub.project()
    ws_rows = [
        ["Sự kiện WebSocket", "Staff (Admin/Viewer)", "Customer (đúng xe)", "Anonymous"],
        ["CART_UPDATED", "Đầy đủ dữ liệu", "Che chi tiết giỏ (public_cart)", "Che chi tiết giỏ"],
        ["ALERT_TRIGGERED", "Đầy đủ dữ liệu", "Không nhận", "Không nhận"],
        ["ALERT_RESOLVED", "Đầy đủ dữ liệu", "Không nhận", "Không nhận"],
        ["COMMAND_ACK", "Đầy đủ dữ liệu", "Không nhận", "Không nhận"],
        ["SCAN_REJECTED", "Đầy đủ dữ liệu", "Chỉ nhận đúng cart_id của mình", "Không nhận"],
    ]
    add_text(s16, 5.55, 1.38, 7.13, 0.30, "MA TRẬN LỌC SỰ KIỆN THEO VAI TRÒ (hub.project())", size=10, color=TEAL_DARK, bold=True)
    add_modern_table(s16, 5.55, 1.72, 7.13, 3.60, ws_rows, [2.00, 1.65, 1.98, 1.50], font_size=9.8)

    add_rect(s16, 5.55, 5.50, 7.13, 1.26, fill=NAVY_DEEP, rounded=True)
    add_text(s16, 5.78, 5.62, 6.68, 0.24, "LỢI ÍCH BẢO MẬT CỦA HUB.PROJECT()", size=9.5, color=TEAL, bold=True)
    add_text(s16, 5.78, 5.90, 6.68, 0.72,
             "Người dùng ẩn danh hoặc khách hàng ở xe khác không thể nghe lén danh sách mặt hàng, giá trị giỏ hàng hay cảnh báo nội bộ của xe khác qua kênh broadcast WebSocket dùng chung.",
             size=10, color=SLATE_TEXT_ON_DARK, line_spacing=1.25)

    # --------------------------------------------------------------------------
    # SLIDE 17: DATABASE DUAL-ENGINE & SƠ ĐỒ ERD
    # --------------------------------------------------------------------------
    s17 = prs.slides.add_slide(blank)
    set_bg(s17, OFF_WHITE)
    add_header(s17, "16 · Thiết kế Database", "Kiến Trúc Dual-Engine (PostgreSQL 16 & SQLite) & ERD")
    add_footer(s17, 17)

    add_pic_fit(s17, f"{DIAG_DIR}/diagram_erd.png", 0.65, 1.35, 8.20, 5.42, frame=True)

    add_rect(s17, 9.05, 1.35, 3.63, 5.42, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_rect(s17, 9.05, 1.35, 3.63, 0.05, fill=EMERALD)
    add_text(s17, 9.25, 1.52, 3.25, 0.34, "Kiến trúc Dual-Engine", size=13, color=NAVY_DEEP, bold=True)
    add_bullets(s17, 9.25, 1.94, 3.25, 4.70, [
        ("PostgreSQL 16 (Docker):", "Dùng driver psycopg 3.3.9, schema_postgres.sql (SERIAL, TIMESTAMPTZ, DOUBLE PRECISION)."),
        ("SQLite WAL (Local/Test):", "Chạy nhanh không cần dịch vụ ngoài, bảo vệ ghi đồng thời bằng RLock + BEGIN IMMEDIATE."),
        ("Adapter thông minh (db.py):", "Tự động dịch placeholder ? -> %s và thêm RETURNING id khi INSERT."),
        ("Bảng cart_commands mới:", "Lưu bền vững toàn bộ lệnh điều khiển và ACK, không mất khi restart Backend."),
        ("Partial Unique Indexes:", "Bảo đảm 1 phiên ACTIVE/xe và chống trùng cảnh báo ACTIVE."),
    ], size=9.8, space_after=6)

    # --------------------------------------------------------------------------
    # SLIDE 18: BẢO MẬT HỆ THỐNG (OWASP IoT TOP 10)
    # --------------------------------------------------------------------------
    s18 = prs.slides.add_slide(blank)
    set_bg(s18, OFF_WHITE)
    add_header(s18, "17 · Bảo mật hệ thống", "Kiến Trúc Bảo Mật Đa Lớp Đối Chiếu OWASP IoT Top 10")
    add_footer(s18, 18)

    sec_layers = [
        ("LỚP 1: ỨNG DỤNG & API", BLUE, [
            ("Xác thực mạnh:", "Băm mật khẩu PBKDF2-HMAC-SHA256 (200.000 vòng) + salt ngẫu nhiên 16 byte."),
            ("Phân quyền & Chống IDOR:", "Token ký HMAC-SHA256; token khách hàng gắn chặt session_id + cart_id."),
            ("Chống Brute-Force & Web:", "Khoá IP sau 5 lần sai/60s; giới hạn 20 phiên/phút; header CSP, DENY, no-store."),
            ("Simulator Token:", "Bảo vệ API :8090 qua SIM_CONTROL_TOKEN."),
        ]),
        ("LỚP 2: MẠNG & MQTT BROKER", TEAL, [
            ("Username / Password:", "Mỗi xe và dịch vụ Backend có tài khoản MQTT riêng (tools/provision.py)."),
            ("Kiểm soát truy cập (ACL):", "Xe chỉ được publish/subscribe đúng topic chứa cart_id của chính nó, cấm subscribe wildcard."),
            ("Mã hoá TLS 1.2+ (:8883):", "Mosquitto profile 'secure' hỗ trợ xác thực chứng chỉ server CA và mã hoá đường truyền."),
        ]),
        ("LỚP 3: TOÀN VẸN DỮ LIỆU", EMERALD, [
            ("Chữ ký từng gói tin:", "Mỗi envelope có trường sig (HMAC-SHA256) tính trên JSON canonical bằng khoá dẫn xuất derive_cart_key."),
            ("Chống giả mạo sớm:", "Gateway kiểm tra sig TRƯỚC khi phân tích JSON hoặc lưu cache chống trùng."),
            ("Chống Replay Attack:", "Từ chối gói tin lệch đồng hồ > 300s (Clock Skew) và loại message_id trùng qua LRU 2000."),
        ]),
    ]
    sx = 0.65
    for stitle, scol, sbullets in sec_layers:
        add_rect(s18, sx, 1.38, 3.82, 4.45, fill=WHITE, border=BORDER_LIGHT, rounded=True)
        add_rect(s18, sx, 1.38, 3.82, 0.42, fill=scol)
        add_text(s18, sx + 0.18, 1.46, 3.46, 0.28, stitle, size=10.5, color=WHITE, bold=True)
        add_bullets(s18, sx + 0.20, 1.98, 3.42, 3.70, sbullets, size=10.2, space_after=8)
        sx += 4.10

    add_rect(s18, 0.65, 6.00, 12.03, 0.80, fill=AMBER_SOFT, border=AMBER, border_pt=0.75, rounded=True)
    add_text(s18, 0.88, 6.10, 11.55, 0.22, "Ghi nhận minh bạch về giới hạn bảo mật hiện tại", size=10, color=AMBER, bold=True)
    add_text(s18, 0.88, 6.34, 11.55, 0.36,
             "Trên môi trường phát triển cục bộ, kênh HTTP/WS sử dụng giao thức truyền tải thuần (không HTTPS/WSS); khi triển khai thực tế cần đặt sau Reverse Proxy (Nginx/Traefik) bọc chứng chỉ SSL/TLS.",
             size=9.8, color=SLATE_DARK)

    # --------------------------------------------------------------------------
    # SLIDE 19: DEMO CUSTOMER UI (4 ẢNH THẬT PLAYWRIGHT)
    # --------------------------------------------------------------------------
    s19 = prs.slides.add_slide(blank)
    set_bg(s19, OFF_WHITE)
    add_header(s19, "18 · Demo Customer UI", "Hành Trình Khách Hàng Thực Tế (/customer — Ảnh Chụp Playwright)")
    add_footer(s19, 19)

    cust_shots = [
        (0.65, 1.35, "01_customer_chon_xe.png", "Bước 1: Chọn xe đẩy khả dụng", "Chỉ cho phép bắt đầu phiên với xe ONLINE & AVAILABLE; xe bận/khoá tự động làm mờ."),
        (6.80, 1.35, "02_customer_gio_hang.png", "Bước 2: Quét sản phẩm & Giỏ Realtime", "Nhận cập nhật tức thì qua WebSocket /ws: số lượng, đơn giá snapshot và tổng trọng lượng."),
        (0.65, 4.18, "03_customer_canh_bao_lech_can.png", "Bước 3: Cảnh báo lệch trọng lượng", "Banner cảnh báo tự động hiện khi cân thực tế sai lệch >100g so với cân kỳ vọng."),
        (6.80, 4.18, "05_customer_hoan_tat.png", "Bước 4: Xác nhận thanh toán & Hoá đơn", "Checkout nguyên tử db.tx(), đóng phiên, giải phóng xe và hiển thị hoá đơn hoàn tất."),
    ]
    for sx, sy, sfile, stitle, sdesc in cust_shots:
        add_rect(s19, sx, sy, 5.88, 2.65, fill=WHITE, border=BORDER_LIGHT, rounded=True)
        add_pic_fit(s19, f"{SHOT_DIR}/{sfile}", sx + 0.14, sy + 0.14, 3.15, 2.37, frame=True)
        add_text(s19, sx + 3.42, sy + 0.24, 2.32, 0.54, stitle, size=10.5, color=NAVY_DEEP, bold=True)
        add_text(s19, sx + 3.42, sy + 0.86, 2.32, 1.50, sdesc, size=9.6, color=SLATE_BODY, line_spacing=1.28)

    # --------------------------------------------------------------------------
    # SLIDE 20: DEMO ADMIN DASHBOARD (3 ẢNH THẬT PLAYWRIGHT)
    # --------------------------------------------------------------------------
    s20 = prs.slides.add_slide(blank)
    set_bg(s20, OFF_WHITE)
    add_header(s20, "19 · Demo Admin Dashboard", "Giám Sát Đội Xe & Điều Khiển Từ Xa (/admin — Ảnh Chụp Playwright)")
    add_footer(s20, 20)

    # Ảnh chính bên trái
    add_rect(s20, 0.65, 1.38, 6.75, 5.38, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_pic_fit(s20, f"{SHOT_DIR}/08_admin_tong_quan.png", 0.80, 1.52, 6.45, 4.35, frame=True)
    add_text(s20, 0.80, 5.95, 6.45, 0.28, "Màn hình Tổng quan đội xe (/admin)", size=11.5, color=NAVY_DEEP, bold=True)
    add_text(s20, 0.80, 6.24, 6.45, 0.42,
             "Hiển thị tức thời trạng thái 3 xe (AVAILABLE/IN_USE/LOCKED), chỉ số pin, trọng lượng thực, thời điểm last_seen và tổng số cảnh báo đang mở.",
             size=9.8, color=SLATE_BODY)

    # 2 ảnh phụ xếp chồng bên phải
    admin_right = [
        (1.38, "09_admin_canh_bao.png", "Trung tâm cảnh báo Realtime", "Lọc theo loại sự cố & xe; tự động cập nhật khi có ALERT_TRIGGERED hoặc RESOLVED."),
        (4.15, "11_admin_chi_tiet_xe.png", "Chi tiết xe & Điều khiển ACK", "Biểu đồ SVG lịch sử pin/cân nặng và nút Khoá/Mở khoá xe gửi lệnh MQTT chờ ACK ≤ 5s."),
    ]
    for ry, rfile, rtitle, rdesc in admin_right:
        add_rect(s20, 7.60, ry, 5.08, 2.60, fill=WHITE, border=BORDER_LIGHT, rounded=True)
        add_pic_fit(s20, f"{SHOT_DIR}/{rfile}", 7.72, ry + 0.14, 2.85, 2.32, frame=True)
        add_text(s20, 10.68, ry + 0.22, 1.88, 0.48, rtitle, size=10.5, color=NAVY_DEEP, bold=True)
        add_text(s20, 10.68, ry + 0.78, 1.88, 1.55, rdesc, size=9.2, color=SLATE_BODY, line_spacing=1.24)

    # --------------------------------------------------------------------------
    # SLIDE 21: DOCKER COMPOSE & TRIỂN KHAI WINDOWS
    # --------------------------------------------------------------------------
    s21 = prs.slides.add_slide(blank)
    set_bg(s21, OFF_WHITE)
    add_header(s21, "20 · Docker & Triển khai", "Đóng Gói Docker Compose & Tự Động Hoá Trên Windows")
    add_footer(s21, 21)

    docker_rows = [
        ["Service (docker-compose.yml)", "Image / Build Context", "Cấu hình Cổng, Volume & Healthcheck"],
        ["postgres", "postgres:16-alpine", "5432:5432 · Volume bền vững postgres-data · Healthcheck pg_isready"],
        ["mqtt-broker", "eclipse-mosquitto:2", "1883:1883, 9001:9001 · Mount ./mosquitto/config/mosquitto.conf:ro"],
        ["backend", "backend/Dockerfile (Multi-stage)", "8000:8000 (REST + WS /ws), 8081:8081 · Depends on postgres (healthy) & broker"],
        ["simulator", "simulator/Dockerfile", "8090:8090 · Profile 'sim' · SIM_CONTROL_TOKEN · Kết nối mqtt-broker"],
    ]
    add_modern_table(s21, 0.65, 1.38, 12.03, 2.75, docker_rows, [2.45, 3.10, 6.48], font_size=10)

    # 2 khối dưới
    add_rect(s21, 0.65, 4.35, 5.88, 2.40, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_rect(s21, 0.65, 4.35, 5.88, 0.05, fill=BLUE)
    add_text(s21, 0.88, 4.52, 5.45, 0.32, "Multi-stage Build & Cấu hình môi trường (.env)", size=12.5, color=NAVY_DEEP, bold=True)
    add_bullets(s21, 0.88, 4.92, 5.45, 1.70, [
        ("Tối ưu dung lượng Image:", "Stage 1 (Node 22) build React vào frontend/dist/; Stage 2 (Python 3.12-slim) chỉ copy bản build tĩnh và chạy FastAPI."),
        ("Tách biệt cấu hình:", "Toàn bộ thông số DB_BACKEND, POSTGRES_*, MQTT_HOST, SIM_CONTROL_TOKEN quản lý qua biến môi trường (.env.example)."),
    ], size=10.2, space_after=6)

    add_rect(s21, 6.80, 4.35, 5.88, 2.40, fill=WHITE, border=BORDER_LIGHT, rounded=True)
    add_rect(s21, 6.80, 4.35, 5.88, 0.05, fill=TEAL)
    add_text(s21, 7.03, 4.52, 5.45, 0.32, "Khởi chạy Native Windows (scripts/run_local.ps1)", size=12.5, color=NAVY_DEEP, bold=True)
    add_bullets(s21, 7.03, 4.92, 5.45, 1.70, [
        ("1 Lệnh duy nhất:", "Kiểm tra phụ thuộc Python, tự động giải phóng cổng 8000/8081/8090 bị kẹt và khởi chạy tuần tự Broker -> FastAPI -> Simulator."),
        ("Dọn dẹp sạch sẽ:", "Bắt sự kiện Ctrl + C để dừng toàn bộ tiến trình con, tránh lỗi treo port khi chạy lại nhiều lần."),
    ], size=10.2, space_after=6)

    # --------------------------------------------------------------------------
    # SLIDE 22: KIỂM THỬ TOÀN DIỆN (131 TESTS PASS)
    # --------------------------------------------------------------------------
    s22 = prs.slides.add_slide(blank)
    set_bg(s22, OFF_WHITE)
    add_header(s22, "21 · Kiểm thử & Độ tin cậy", "Kiểm Thử Đa Tầng & Kết Quả Thực Thi Toàn Hệ Thống")
    add_footer(s22, 22)

    add_pic_fit(s22, f"{DIAG_DIR}/diagram_testing.png", 0.65, 1.38, 7.25, 5.38, frame=True)

    # Cột phải: Metric nổi bật + 3 kịch bản trọng tâm
    add_rect(s22, 8.10, 1.38, 4.58, 1.45, fill=NAVY_DEEP, rounded=True)
    add_text(s22, 8.35, 1.52, 4.10, 0.55, "131 / 131 PASS", size=26, color=EMERALD, bold=True)
    add_text(s22, 8.35, 2.12, 4.10, 0.55,
             "47 Unit + 64 Integration + 20 E2E Playwright (0 Fail)\nPlatformIO Firmware Build: 2 Targets 100% OK",
             size=10, color=WHITE, line_spacing=1.25)

    test_highlights = [
        ("1. Đa xe & Phục hồi mất mạng", "3 xe CART_001..003 chạy đồng thời; ngắt mạng đột ngột, quét 2 món vào Offline Queue -> nối lại tự xả sạch và đồng bộ đủ giỏ hàng.", TEAL),
        ("2. Toàn vẹn Lệnh & Chống trùng", "Kiểm chứng bảng cart_commands sống qua restart Backend; lọc trùng message_id/scan_id, chống Replay >300s và rollback khi checkout lỗi.", BLUE),
        ("3. E2E Trình duyệt & Bảo mật", "20 test Playwright kiểm chứng Customer/Admin/Simulator UI; xác nhận phân quyền RBAC, chống IDOR và chữ ký HMAC.", EMERALD),
    ]
    ty = 3.00
    for ttitle, tdesc, tcol in test_highlights:
        add_rect(s22, 8.10, ty, 4.58, 1.15, fill=WHITE, border=BORDER_LIGHT, rounded=True)
        add_rect(s22, 8.10, ty, 0.06, 1.15, fill=tcol)
        add_text(s22, 8.30, ty + 0.10, 4.25, 0.25, ttitle, size=10.5, color=NAVY_DEEP, bold=True)
        add_text(s22, 8.30, ty + 0.38, 4.25, 0.70, tdesc, size=9.2, color=SLATE_BODY, line_spacing=1.2)
        ty += 1.28

    # --------------------------------------------------------------------------
    # SLIDE 23: TỔNG KẾT & HƯỚNG PHÁT TRIỂN (BOOKEND DEEP NAVY)
    # --------------------------------------------------------------------------
    s23 = prs.slides.add_slide(blank)
    set_bg(s23, NAVY_DEEP)
    add_header(s23, "22 · Tổng kết", "Kết Quả Đạt Được, Hạn Chế & Hướng Phát Triển", dark=True)
    add_footer(s23, 23, dark=True)

    closing_cols = [
        ("01 · Kết quả đạt được", EMERALD, [
            ("Kiến trúc hoàn chỉnh:", "Hoàn thiện đồng bộ Backend FastAPI, Dual-Engine (PostgreSQL 16 & SQLite), WebSocket /ws gom cổng và MQTT 6 topics."),
            ("Độ tin cậy cao:", "Cơ chế Offline Queue FIFO, lưu vết lệnh cart_commands, Alert Engine tự động và bảo mật 3 lớp OWASP."),
            ("Kiểm chứng toàn diện:", "131/131 bài test tự động PASS (gồm 20 E2E Playwright) và biên dịch firmware PlatformIO thành công 100%."),
        ]),
        ("02 · Hạn chế trung thực", AMBER, [
            ("Phần cứng mô phỏng:", "Chưa triển khai và hiệu chuẩn trực tiếp trên mạch ESP32 vật lý, Load Cell HX711 và máy quét GM65 thật."),
            ("Mạng cục bộ:", "HTTP/WS local chưa bật chứng chỉ TLS (mới cấu hình TLS ở tầng MQTT); cần Reverse Proxy khi lên Production."),
            ("C++ Host Test:", "15 unit test C++ bị bỏ qua trên Windows host do thiếu compiler MinGW g++ (đã biên dịch thành công qua xtensa-g++)."),
        ]),
        ("03 · Hướng phát triển", TEAL, [
            ("Lắp ráp phần cứng thật:", "Tích hợp mạch ESP32, Load Cell hiệu chuẩn cơ khí và pin Li-ion thực tế lên xe đẩy mẫu."),
            ("Nhận diện AI Camera:", "Bổ sung camera nhận diện hình ảnh sản phẩm chống gian lận tráo mã vạch đối với mặt hàng cùng trọng lượng."),
            ("Thanh toán thực tế:", "Kết nối cổng thanh toán QR (VNPay / MoMo) và xuất hoá đơn điện tử trực tiếp sau checkout."),
        ]),
    ]
    cx = 0.65
    for ctitle, ccol, cbullets in closing_cols:
        add_rect(s23, cx, 1.38, 3.82, 4.35, fill=NAVY_SURFACE, border=NAVY_BORDER, rounded=True)
        add_rect(s23, cx, 1.38, 3.82, 0.05, fill=ccol)
        add_text(s23, cx + 0.22, 1.56, 3.38, 0.34, ctitle, size=13, color=WHITE, bold=True)
        add_bullets(s23, cx + 0.22, 2.02, 3.38, 3.55, cbullets, size=10.5, color=SLATE_TEXT_ON_DARK, lead_color=ccol, space_after=8)
        cx += 4.10

    add_rect(s23, 0.65, 5.95, 12.03, 0.82, fill=NAVY_SURFACE, border=TEAL, border_pt=0.75, rounded=True)
    add_text(s23, 0.90, 6.08, 11.53, 0.56,
             "KẾT LUẬN: Đề tài đã xây dựng thành công nền tảng Smart Shopping Cart IoT hoàn chỉnh về kiến trúc phần mềm, chuẩn hoá giao tiếp, bảo đảm tính nguyên tử dữ liệu và sẵn sàng chuyển giao sang giai đoạn tích hợp phần cứng thương mại.",
             size=10.2, color=WHITE, bold=True, line_spacing=1.25)

    # Gắn toàn bộ Speaker Notes cho 23 slides
    for idx, slide in enumerate(prs.slides):
        if idx in notes_map:
            ns = slide.notes_slide
            ns.notes_text_frame.text = notes_map[idx]

    prs.save(OUT_PPTX)
    print(f"Successfully created redesigned presentation: {OUT_PPTX} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    build()
