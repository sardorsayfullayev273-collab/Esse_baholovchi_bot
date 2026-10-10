# -*- coding: utf-8 -*-
"""v44 — «Ona tilini o'ynab o'rganamiz» taklif/bellashuv kartasi (1200x630).
Telegram'da rasm + «Qabul qilaman» tugmasi bilan chiqadi. Rasm imzo (HMAC) bilan himoyalangan:
faqat bot o'zi yaratgan parametrlar bilan ochiladi."""
import hmac, hashlib, io
from PIL import Image, ImageDraw
from result_cards import F, clean

W, H = 1200, 630
GREEN_D, GREEN_M, GREEN_L = (4, 47, 36), (11, 118, 86), (232, 245, 239)
GOLD, GOLD_L, WHITE = (200, 168, 91), (227, 196, 111), (255, 255, 255)


def sign(secret, kind, name, c, t, rank):
    msg = f"{kind}|{name}|{c}|{t}|{rank}".encode("utf-8")
    return hmac.new(str(secret).encode("utf-8"), msg, hashlib.sha256).hexdigest()[:20]


def _grad(img):
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(GREEN_D[i] + (GREEN_M[i] - GREEN_D[i]) * k * 0.95) for i in range(3)))


def _glow(img, cx, cy, r, color, alpha):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for i in range(r, 0, -8):
        d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=color + (int(alpha * (1 - i / r) ** 1.6),))
    img.paste(Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB"))


def _fit(d, text, size, w, weight="b", min_size=30):
    while size > min_size and d.textlength(clean(text), font=F(size, weight)) > w:
        size -= 2
    return F(size, weight)


def render_card(kind="duel", name="Do'stingiz", correct=0, total=5, rank=""):
    name = clean(name or "Do'stingiz")[:22]
    img = Image.new("RGB", (W, H), GREEN_D); _grad(img)
    _glow(img, 1080, 40, 420, GOLD, 120); _glow(img, 60, 640, 360, (60, 200, 150), 70)
    d = ImageDraw.Draw(img)
    # tepada belgi
    label = "BELLASHUV" if kind == "duel" else "O'YNAB O'RGANAMIZ"
    f = F(26, "b"); tw = d.textlength(label, font=f)
    d.rounded_rectangle([60, 56, 60 + tw + 52, 108], radius=26, fill=GOLD)
    d.text((86, 62), label, font=f, fill=(59, 45, 5))
    d.text((60, 140), "ONA TILI", font=F(30, "m"), fill=GOLD_L)
    # ism va chaqiriq
    d.text((60, 196), name, font=_fit(d, name, 74, 560), fill=WHITE)
    line = ["seni bellashuvga", "chaqirmoqda!"] if kind == "duel" else ["seni o'yinga", "chaqirmoqda!"]
    d.text((60, 290), clean(line[0]), font=F(40, "m"), fill=GREEN_L)
    d.text((60, 342), clean(line[1]), font=F(40, "m"), fill=GREEN_L)
    if rank:
        rf = F(26, "m"); rt = clean(rank); rw = d.textlength(rt, font=rf)
        d.rounded_rectangle([60, 420, 60 + rw + 40, 466], radius=23, outline=GOLD, width=3)
        d.text((80, 425), rt, font=rf, fill=GOLD_L)
    # o'ng karta
    x0, y0, x1, y1 = 700, 90, 1140, 470
    d.rounded_rectangle([x0 + 8, y0 + 12, x1 + 8, y1 + 12], radius=42, fill=(2, 30, 23))
    d.rounded_rectangle([x0, y0, x1, y1], radius=42, fill=WHITE)
    cx = (x0 + x1) // 2
    if kind == "duel":
        t = max(1, int(total)); c = max(0, min(int(correct), t))
        sc = f"{c}/{t}"; f1 = F(150, "b"); w1 = d.textlength(sc, font=f1)
        d.text((cx - w1 / 2, y0 + 40), sc, font=f1, fill=GREEN_M)
        s = "uning natijasi"; f2 = F(30, "m"); d.text((cx - d.textlength(s, font=f2) / 2, y0 + 228), s, font=f2, fill=(108, 126, 118))
        r, gap = 22, 30; tot_w = t * 2 * r + (t - 1) * gap; sx = cx - tot_w / 2
        for i in range(t):
            ccx = sx + r + i * (2 * r + gap); cy = y0 + 318
            d.ellipse([ccx - r, cy - r, ccx + r, cy + r], fill=GOLD if i < c else (222, 233, 227))
    else:
        s = "O'YNA"; f1 = F(96, "b"); d.text((cx - d.textlength(s, font=f1) / 2, y0 + 40), s, font=f1, fill=GREEN_M)
        s = "va o'rgan!"; f1 = F(60, "b"); d.text((cx - d.textlength(s, font=f1) / 2, y0 + 150), s, font=f1, fill=GOLD)
        chips = ["DTM sinov", "Imlo", "Sinonim", "Paronim"]; f3 = F(26, "m")
        for i, ch in enumerate(chips):
            cw = d.textlength(ch, font=f3) + 36; ccx = x0 + 36 + (i % 2) * 196; cy = y0 + 250 + (i // 2) * 56
            d.rounded_rectangle([ccx, cy, ccx + 180, cy + 44], radius=22, fill=GREEN_L)
            d.text((ccx + 90 - d.textlength(ch, font=f3) / 2, cy + 5), ch, font=f3, fill=GREEN_D)
    # pastki tasma
    d.rounded_rectangle([60, 520, 1140, 580], radius=30, fill=GOLD_L)
    bt = "5 ta savol  •  2 daqiqa  •  Yenga olasanmi?" if kind == "duel" else "Kunlik 5 savol  •  Seriya  •  Do'stlar bilan bellashuv"
    f4 = _fit(d, bt, 30, 1000, "b", 22); d.text((600 - d.textlength(clean(bt), font=f4) / 2, 531), clean(bt), font=f4, fill=(59, 45, 5))
    d.text((60, 592), "Milliy sertifikat akademiyasi", font=F(20, "m"), fill=(168, 204, 190))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=88, optimize=True); buf.seek(0)
    return buf


if __name__ == "__main__":
    open("/tmp/c_duel.jpg", "wb").write(render_card("duel", "Sardor", 4, 5, "Bilimdon").read())
    open("/tmp/c_play.jpg", "wb").write(render_card("play", "Sardor", 0, 5, "Alloma • 1250 XP").read())
