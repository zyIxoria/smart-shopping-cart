"""Render preview PNG chính xác theo từng run (font, size, bold, color, pixel width wrapping)."""
import io
import os
from PIL import Image, ImageDraw, ImageFont
import pptx
from pptx.enum.shapes import MSO_SHAPE_TYPE

OUT_DIR = "scratch/slide_previews"
os.makedirs(OUT_DIR, exist_ok=True)

DPI = 120
PRS = pptx.Presentation("docs/presentation/Smart_Shopping_Cart_Presentation.pptx")
W_PX = int((PRS.slide_width / 914400.0) * DPI)
H_PX = int((PRS.slide_height / 914400.0) * DPI)

_FONT_CACHE = {}

def load_font(size_pt, bold=False, mono=False):
    px = max(8, int(round(size_pt * DPI / 72.0)))
    key = (px, bold, mono)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    if mono:
        cands = [r"C:\Windows\Fonts\consolab.ttf" if bold else r"C:\Windows\Fonts\consola.ttf"]
    else:
        cands = [
            r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        ]
    for c in cands:
        if os.path.exists(c):
            f = ImageFont.truetype(c, px)
            _FONT_CACHE[key] = f
            return f
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f

def get_rgb(color_obj, default=(255, 255, 255)):
    try:
        if color_obj and color_obj.type is not None and color_obj.rgb is not None:
            r = color_obj.rgb
            return (r[0], r[1], r[2])
    except Exception:
        pass
    return default

def draw_wrapped_runs(draw, x, y, max_w, runs_info, line_mult=1.22):
    """Vẽ danh sách runs [(text, font, color)] tự động xuống dòng theo đúng pixel width."""
    cur_x = x
    cur_y = y
    max_line_h = 16
    for text, font, color in runs_info:
        # Lấy chiều cao chữ
        bbox = font.getbbox("Ag")
        lh = int((bbox[3] - bbox[1]) * line_mult) + 2
        if lh > max_line_h:
            max_line_h = lh

        parts = text.split("\n")
        for p_idx, part in enumerate(parts):
            if p_idx > 0:
                cur_x = x
                cur_y += max_line_h
            words = part.split(" ")
            for w_idx, word in enumerate(words):
                token = word if (w_idx == 0 and cur_x == x) else (" " + word if w_idx > 0 else word)
                if cur_x > x and not token.startswith(" "):
                    token = token
                tw = draw.textlength(token, font=font)
                if cur_x + tw > x + max_w and cur_x > x:
                    cur_x = x
                    cur_y += max_line_h
                    token = word
                    tw = draw.textlength(token, font=font)
                draw.text((cur_x, cur_y), token, fill=color, font=font)
                cur_x += tw
    return cur_y + max_line_h

for idx, slide in enumerate(PRS.slides, 1):
    bg_rgb = (245, 247, 250)
    try:
        if slide.background.fill.type is not None:
            bg_rgb = get_rgb(slide.background.fill.fore_color, bg_rgb)
    except Exception:
        pass

    img = Image.new("RGB", (W_PX, H_PX), bg_rgb)
    draw = ImageDraw.Draw(img)

    for shp in slide.shapes:
        x = int((shp.left / 914400.0) * DPI)
        y = int((shp.top / 914400.0) * DPI)
        w = int((shp.width / 914400.0) * DPI)
        h = int((shp.height / 914400.0) * DPI)

        if shp.shape_type == MSO_SHAPE_TYPE.PICTURE:
            try:
                pic = Image.open(io.BytesIO(shp.image.blob)).convert("RGBA")
                pic = pic.resize((max(1, w), max(1, h)), Image.Resampling.LANCZOS)
                img.paste(pic, (x, y), pic)
            except Exception:
                pass
            continue

        if shp.has_table:
            tbl = shp.table
            cy = y
            row_h = max(18, h // len(tbl.rows))
            for ri, row in enumerate(tbl.rows):
                cx = x
                for ci, cell in enumerate(row.cells):
                    cw = int((tbl.columns[ci].width / 914400.0) * DPI)
                    fill_c = (16, 26, 43) if ri == 0 else ((255, 255, 255) if ri % 2 == 1 else (248, 250, 252))
                    draw.rectangle([cx, cy, cx + cw, cy + row_h], fill=fill_c, outline=(226, 232, 240))
                    txt_c = (255, 255, 255) if ri == 0 else (30, 41, 59)
                    r0 = cell.text_frame.paragraphs[0].runs[0] if cell.text_frame.paragraphs[0].runs else None
                    fsize = r0.font.size.pt if (r0 and r0.font.size) else 9.5
                    is_b = bool(r0 and r0.font.bold)
                    if ri > 0 and r0:
                        txt_c = get_rgb(r0.font.color, txt_c)
                    f = load_font(fsize, bold=is_b)
                    draw_wrapped_runs(draw, cx + 10, cy + 6, cw - 18, [(cell.text.strip(), f, txt_c)], 1.15)
                    cx += cw
                cy += row_h
            continue

        if shp.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
            fill_c = None
            try:
                if shp.fill.type == 1:
                    fill_c = get_rgb(shp.fill.fore_color, None)
            except Exception:
                pass
            border_c = None
            try:
                if shp.line.fill.type == 1:
                    border_c = get_rgb(shp.line.color, None)
            except Exception:
                pass
            if fill_c or border_c:
                draw.rectangle([x, y, x + w, y + h], fill=fill_c, outline=border_c, width=1)

        if shp.has_text_frame:
            ty = y
            for p in shp.text_frame.paragraphs:
                if not p.text.strip():
                    ty += 6
                    continue
                runs_info = []
                for r in p.runs:
                    fsize = r.font.size.pt if r.font.size else 11.0
                    is_b = bool(r.font.bold)
                    is_m = (r.font.name == "Consolas")
                    tcol = get_rgb(r.font.color, (30, 41, 59))
                    runs_info.append((r.text, load_font(fsize, bold=is_b, mono=is_m), tcol))
                if not runs_info:
                    runs_info.append((p.text, load_font(11.0), (30, 41, 59)))
                ty = draw_wrapped_runs(draw, x + 2, ty, w - 4, runs_info, 1.2)
                ty += 4

    out_path = os.path.join(OUT_DIR, f"slide_{idx:02d}.png")
    img.save(out_path)

print(f"Rendered {len(PRS.slides)} pixel-accurate previews into {OUT_DIR}")
