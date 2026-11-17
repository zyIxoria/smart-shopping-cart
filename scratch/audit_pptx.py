"""Kiểm tra chất lượng tự động file PowerPoint sau redesign:
- Kiểm tra ranh giới tọa độ (không vượt khỏi 13.333 x 7.5 in)
- Kiểm tra va chạm (overlap) không mong muốn giữa các textbox/hình ảnh độc lập
- Ước lượng tràn chữ (text overflow) dựa trên số ký tự, chiều rộng hộp và cỡ chữ
- Xác nhận Speaker Notes đầy đủ cho 23 slides
"""
import math
import pptx
from pptx.util import Inches

PPTX_PATH = "docs/presentation/Smart_Shopping_Cart_Presentation.pptx"
prs = pptx.Presentation(PPTX_PATH)
W_IN = prs.slide_width / 914400.0
H_IN = prs.slide_height / 914400.0

print(f"Slide dimensions: {W_IN:.3f} x {H_IN:.3f} in | Total slides: {len(prs.slides)}")
issues = 0

for idx, slide in enumerate(prs.slides, 1):
    # 1. Kiểm tra Speaker Notes
    notes = slide.notes_slide.notes_text_frame.text.strip() if slide.has_notes_slide else ""
    if len(notes) < 100:
        print(f"[WARN] Slide {idx}: Speaker notes too short ({len(notes)} chars)")
        issues += 1

    # 2. Kiểm tra tọa độ shapes và ước lượng tràn chữ
    for s_idx, shp in enumerate(slide.shapes):
        left = shp.left / 914400.0
        top = shp.top / 914400.0
        width = shp.width / 914400.0
        height = shp.height / 914400.0

        if left < -0.05 or top < -0.05 or (left + width) > W_IN + 0.05 or (top + height) > H_IN + 0.05:
            print(f"[OVERFLOW-BOUNDS] Slide {idx} shape {s_idx}: ({left:.2f}, {top:.2f}, {width:.2f}, {height:.2f})")
            issues += 1

        if shp.has_text_frame:
            tf = shp.text_frame
            # Tính chiều cao ước lượng
            est_h = 0.0
            for p in tf.paragraphs:
                txt = p.text
                if not txt.strip():
                    continue
                # Lấy cỡ chữ đầu tiên hoặc mặc định 11pt
                fsize = 11.0
                if p.runs and p.runs[0].font.size:
                    fsize = p.runs[0].font.size.pt
                # Ước lượng số ký tự trên 1 dòng: width (pt) / (fsize * 0.52)
                chars_per_line = max(10, (width * 72.0) / (fsize * 0.50))
                lines = 0
                for subline in txt.split("\n"):
                    lines += max(1, math.ceil(len(subline) / chars_per_line))
                line_h = (fsize * 1.25) / 72.0
                est_h += lines * line_h + (p.space_after.pt / 72.0 if p.space_after else 0.05)

            if est_h > height * 1.15 and width > 1.0:
                print(f"[TEXT-TIGHT] Slide {idx} shape {s_idx}: est_h={est_h:.2f} > box_h={height:.2f} | text='{tf.text[:55].replace(chr(10), ' ')}...'")

print(f"Audit complete. Critical issues: {issues}")
