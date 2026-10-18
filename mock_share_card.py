# -*- coding: utf-8 -*-
"""v80: MOCK ulashish kartasi (Telegram/Instagram stories uchun 1080x1350 rasm)."""
import io, os, unicodedata
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
LV_COL = {"A+": "#d4a72c", "A": "#9fb3ad", "B+": "#3aa57a", "B": "#5fb88a", "C+": "#d9a21b", "C": "#d9a21b", "NC": "#c0392b"}


def _f(size, bold=False):
    for nm in (("Poppins-Bold.ttf" if bold else "Poppins-Medium.ttf"), ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")):
        try: return ImageFont.truetype(os.path.join(FONT_DIR, nm), size)
        except Exception: continue
    return ImageFont.load_default()


def _clean(name, safe):
    n = safe(unicodedata.normalize("NFKC", str(name or ""))).strip()
    return n if n.strip(" -'.") else ""


def render(name, title, score, level, place, total, percentile, safe_text, footer="@milliysertifikat_ona_tili1"):
    W, H = 1080, 1350
    im = Image.new("RGB", (W, H), "#08402f"); d = ImageDraw.Draw(im)
    for y in range(H):   # vertikal gradient
        t = y / H; c = (int(8 + 6 * t), int(64 - 24 * t), int(47 - 12 * t)); d.line([(0, y), (W, y)], fill=c)
    gold = LV_COL.get(level, "#d4a72c")
    d.rounded_rectangle([40, 40, W - 40, H - 40], 36, outline="#d4a72c", width=5)
    d.text((W / 2, 130), "MILLIY SERTIFIKAT MOCK", font=_f(40, True), fill="#f3d77a", anchor="mm")
    d.text((W / 2, 185), safe_text(title)[:40], font=_f(28), fill="#cfe5db", anchor="mm")
    nm = _clean(name, safe_text)
    if nm: d.text((W / 2, 300), nm[:28], font=_f(54, True), fill="#ffffff", anchor="mm")
    cy = 640
    d.ellipse([W / 2 - 230, cy - 230, W / 2 + 230, cy + 230], fill="#0b5a41", outline=gold, width=10)
    d.text((W / 2, cy - 70), str(level), font=_f(150, True), fill=gold, anchor="mm")
    d.text((W / 2, cy + 70), f"{float(score):.1f} / 75", font=_f(64, True), fill="#ffffff", anchor="mm")
    d.text((W / 2, cy + 150), "yakuniy ball", font=_f(30), fill="#cfe5db", anchor="mm")
    chips = [(f"{place}-o'rin", f"{total} kishi ichida"), (f"{percentile}%", "ishtirokchidan yuqori")]
    for i, (a, b) in enumerate(chips):
        x0 = 90 + i * 460
        d.rounded_rectangle([x0, 960, x0 + 440, 1110], 26, fill="#0b5a41")
        d.text((x0 + 220, 1015), a, font=_f(54, True), fill="#f3d77a", anchor="mm")
        d.text((x0 + 220, 1075), b, font=_f(26), fill="#cfe5db", anchor="mm")
    d.text((W / 2, 1200), "Sen ham o'zingni sinab ko'r!", font=_f(40, True), fill="#ffffff", anchor="mm")
    d.text((W / 2, 1255), str(footer)[:40], font=_f(30), fill="#f3d77a", anchor="mm")
    b = io.BytesIO(); im.convert("RGB").save(b, "JPEG", quality=88, optimize=True); return b.getvalue()
