# -*- coding: utf-8 -*-
"""v123 — «Yutuqlar zinasi»: har kuni olishga undaydigan yutuq kartalari (1080×1350, Telegram/Mini App uchun).
Zina (oddiydan qiyinga — dizayn ham boyib boradi):
  3D  Kun qahramoni      — bugungi eng faol o‘quvchi
  4D  Seriya olovi       — ketma-ket kunlar
  5D  Shon-sharaf devori — hafta/oy sardorlari
  6D  Sertifikat bilimdoni — sertifikatlar kolleksiyasi
  7D  Mavsum afsonasi    — mavsum chempioni
Dizayn tili va yordamchilar cert_award.py bilan umumiy (yashil Mini App palitrasi). render(kind, data, code) -> PNG baytlari.
"""
import io, math, random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import cert_award as ca
from cert_award import (G1, G2, G3, MINT, INK, MUT, GLOW, MEDAL, GREEN_FOIL, MINT_FOIL, _mix, _grad_d, _grad_v, _noise, _blank, _text_mask, _paint,
                        _paint_grad, _soft_shadow, _rosette, _sparkle, _laurel, fit_lines, font, tlen, paste_medal, _wrap_text)

AW, AH = 1080, 1350
KINDS = ("hero", "streak", "wall", "bilimdon", "legend")
STYLE_OF = {"hero": "3D", "streak": "4D", "wall": "5D", "bilimdon": "6D", "legend": "7D"}
TITLES = {"hero": "KUN QAHRAMONI", "streak": "SERIYA OLOVI", "wall": "SHON-SHARAF DEVORI", "bilimdon": "SERTIFIKAT BILIMDONI", "legend": "MAVSUM AFSONASI"}
LABELS = {"hero": "BUGUNGI YUTUQ", "streak": "ODAT YUTUQI", "wall": "HAFTA SARDORLARI", "bilimdon": "KOLLEKSIYA YUTUQI", "legend": "ENG YUQORI DARAJA"}

SAMPLE = {
    "hero": {"name": "Dilnoza Karimova", "desc": "Bugun 18 ta savolga to‘g‘ri javob berib, eng faol o‘quvchi bo‘ldi", "stats": [("KUNLIK BALL", "240"), ("TO‘G‘RI", "18 / 20"), ("SERIYA", "12 kun")], "date": "7-noyabr, 2026"},
    "streak": {"name": "Sardor Aliyev", "desc": "30 kun ketma-ket har kuni mashq qildi — odat shakllandi", "stats": [("SERIYA", "30 kun"), ("JAMI BALL", "4 820"), ("REKORD", "41 kun")], "date": "7-noyabr, 2026", "days": 30},
    "wall": {"name": "", "desc": "", "stats": [], "date": "1–7 noyabr, 2026", "period": "Hafta · 1–7 noyabr",
             "top": [("Dilnoza K.", 1240), ("Sardor A.", 1110), ("Madina R.", 980), ("Jasur T.", 905), ("Nilufar S.", 870)]},
    "bilimdon": {"name": "Madina Rahimova", "desc": "7 ta sertifikat to‘pladi. Keyingi daraja uchun yana 3 ta kerak", "stats": [("SERTIFIKAT", "7 ta"), ("DARAJA", "2-daraja"), ("KEYINGISI", "10 ta")], "date": "7-noyabr, 2026", "count": 7, "next": 10},
    "legend": {"name": "Jasur Toshmatov", "desc": "Mavsum davomida eng ko‘p XP to‘plab, reytingda 1-o‘rinni egalladi", "stats": [("MAVSUM BALLI", "18 450"), ("O‘RIN", "1"), ("NOYOBLIK", "0,1%")], "date": "Kuz mavsumi, 2026"},
}


# ------------------------------------------------------------------ fon va ramka (uslublar)
def _paper(col, noise=6):
    im = Image.new("RGB", (AW, AH), col)
    n = _noise((AW, AH), noise)
    return ImageChops.add(im, Image.merge("RGB", (n, n, n)), 1, -128)


def bg_3d():
    im = _paper((230, 244, 237))
    d = ImageDraw.Draw(im)
    for i, (off, w) in enumerate(((26, 16), (60, 7), (80, 4))):
        for k in range(w):
            hi = _mix((236, 252, 244), G3, i * 0.35)
            lo = _mix(G2, (3, 30, 22), 0.55 + 0.1 * i)
            d.line([(off + k, off + k), (AW - off - k, off + k)], fill=hi)
            d.line([(off + k, off + k), (off + k, AH - off - k)], fill=hi)
            d.line([(off + k, AH - off - k), (AW - off - k, AH - off - k)], fill=lo)
            d.line([(AW - off - k, off + k), (AW - off - k, AH - off - k)], fill=lo)
    d.rectangle([100, 100, AW - 100, AH - 100], outline=G2, width=3)
    for sx, sy in ((112, 112), (AW - 112, 112), (112, AH - 112), (AW - 112, AH - 112)):
        for rr, w in ((38, 3), (26, 2), (14, 2)):
            d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], outline=G3 if rr != 26 else G1, width=w)
    return im


def bg_4d():
    im = _grad_d(AW, AH, [(0, (3, 34, 26)), (0.5, G2), (1, (3, 28, 21))], 0.6)
    d = ImageDraw.Draw(im, "RGBA")
    for k in range(9):
        r = 140 + k * 60
        d.ellipse([AW * 0.9 - r, AH * 0.08 - r, AW * 0.9 + r, AH * 0.08 + r], outline=(150, 240, 200, 14), width=2)

    def sheet(w, h, col, ang, dx, dy):
        t = Image.new("RGBA", (w, h), col + (255,)).rotate(ang, expand=True, resample=Image.BICUBIC)
        x, y = (AW - t.size[0]) // 2 + dx, (AH - t.size[1]) // 2 + dy
        sh = Image.new("L", im.size, 0)
        sh.paste(t.split()[3], (x + 6, y + 22))
        im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(20)).point(lambda v: int(v * 0.6)))
        im.paste(t, (x, y), t)
    sheet(900, 1230, (178, 214, 196), -2.0, -6, 8)
    sheet(900, 1230, (206, 232, 218), 1.6, 6, -2)
    main = _paper((236, 247, 241), 5)
    main = main.crop((0, 0, 920, 1270))
    md = ImageDraw.Draw(main)
    md.rectangle([14, 14, 905, 1255], outline=G3, width=6)
    md.rectangle([30, 30, 889, 1239], outline=G1, width=2)
    ox, oy = (AW - 920) // 2, (AH - 1270) // 2 + 2
    sh = Image.new("L", im.size, 0)
    sh.paste(Image.new("L", main.size, 255), (ox + 4, oy + 18))
    im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.65)))
    im.paste(main, (ox, oy))
    return im


def bg_5d():
    im = _grad_d(AW, AH, [(0, (3, 36, 27)), (0.55, G2), (1, (3, 28, 21))], 0.5)
    for (R, r, p, size, col) in ((60, 7, 9, 560, (190, 255, 225, 44)), (72, 11, 14, 400, (255, 255, 255, 30))):
        _rosette(im, AW / 2, 470, size, R, r, p, col)
    fr = _blank()
    fd = ImageDraw.Draw(fr)
    fd.rectangle([26, 26, AW - 26, AH - 26], outline=255, width=22)
    fd.rectangle([66, 66, AW - 66, AH - 66], outline=255, width=4)
    _soft_shadow(im, fr, 4, 6, 6, 0.6)
    _paint_grad(im, fr, GREEN_FOIL, glare=False)
    for sx, sy in ((48, 48), (AW - 48, 48), (48, AH - 48), (AW - 48, AH - 48)):
        m = _blank()
        ImageDraw.Draw(m).ellipse([sx - 22, sy - 22, sx + 22, sy + 22], fill=255)
        _soft_shadow(im, m, 2, 3, 3, 0.5)
        _paint_grad(im, m, [(0, (210, 255, 236)), (0.5, G3), (1, (4, 50, 36))], glare=False)
    return im


def bg_6d():
    im = _grad_d(AW, AH, [(0, (4, 34, 28)), (0.5, (8, 74, 58)), (1, (3, 26, 22))], 0.8)
    orbs = Image.new("RGB", (AW, AH), (0, 0, 0))
    od = ImageDraw.Draw(orbs)
    for (x, y, r, c) in ((160, 200, 320, (18, 138, 99)), (940, 1180, 380, (25, 194, 138)), (900, 120, 240, (120, 230, 150)), (140, 1180, 280, (20, 150, 140))):
        od.ellipse([x - r, y - r, x + r, y + r], fill=c)
    im = ImageChops.add(im, orbs.filter(ImageFilter.GaussianBlur(110)).point(lambda v: int(v * 0.62)), 1.0, 0)
    rnd = random.Random(7)
    sp = ImageDraw.Draw(im, "RGBA")
    for _ in range(60):
        x, y = rnd.randint(30, AW - 30), rnd.randint(30, AH - 30)
        sp.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, rnd.randint(60, 150)))
    c0 = (70, 70, AW - 70, AH - 70)
    card = _blank()
    ImageDraw.Draw(card).rounded_rectangle(c0, radius=46, fill=255)
    _soft_shadow(im, card, 0, 24, 28, 0.55)
    im.paste(im.filter(ImageFilter.GaussianBlur(26)), (0, 0), card)
    im.paste((255, 255, 255), (0, 0), card.point(lambda v: int(v * 0.10)))
    im.paste((2, 24, 18), (0, 0), card.point(lambda v: int(v * 0.30)))
    streak = Image.new("L", (AW, AH), 0)
    ImageDraw.Draw(streak).polygon([(70, 70), (600, 70), (260, AH - 70), (70, AH - 70)], fill=24)
    im.paste((255, 255, 255), (0, 0), ImageChops.multiply(streak.filter(ImageFilter.GaussianBlur(30)), card))
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle(c0, radius=46, outline=(255, 255, 255, 120), width=3)
    d.rounded_rectangle((84, 84, AW - 84, AH - 84), radius=36, outline=(255, 255, 255, 40), width=2)
    return im


def bg_7d():
    im = _grad_d(AW, AH, [(0, (2, 14, 11)), (0.5, (6, 36, 28)), (1, (2, 12, 9))], 0.6)
    orbs = Image.new("RGB", (AW, AH), (0, 0, 0))
    od = ImageDraw.Draw(orbs)
    for (x, y, r, c) in ((120, 160, 320, (18, 138, 99)), (980, 200, 300, (20, 170, 150)), (540, 1380, 420, (25, 194, 138)), (1040, 1000, 240, (110, 220, 120))):
        od.ellipse([x - r, y - r, x + r, y + r], fill=c)
    im = ImageChops.add(im, orbs.filter(ImageFilter.GaussianBlur(120)).point(lambda v: int(v * 0.6)), 1.0, 0)
    holo = _grad_d(AW, AH, [(0, (25, 194, 138)), (0.2, (190, 255, 150)), (0.4, (60, 230, 200)), (0.6, (18, 138, 99)), (0.8, (200, 255, 214)), (1, (25, 194, 138))], 0.9)
    fr = _blank()
    fd = ImageDraw.Draw(fr)
    fd.rounded_rectangle([34, 34, AW - 34, AH - 34], radius=40, outline=255, width=13)
    fd.rounded_rectangle([66, 66, AW - 66, AH - 66], radius=30, outline=255, width=3)
    _soft_shadow(im, fr, 0, 0, 14, 0.9, (25, 194, 138))
    im.paste(holo, (0, 0), fr)
    card = _blank()
    ImageDraw.Draw(card).rounded_rectangle([76, 76, AW - 76, AH - 76], radius=26, fill=255)
    im.paste((3, 18, 14), (0, 0), card.point(lambda v: int(v * 0.74)))
    mt = _blank()
    f = font(11, True, False)
    unit = "ESSE AKADEMIYASI • "
    txt = unit * (int((AW - 220) / tlen(f, unit)) + 1)
    while tlen(f, txt) > AW - 220:
        txt = txt[:-1]
    ImageDraw.Draw(mt).text((110, 88), txt, font=f, fill=255)
    ImageDraw.Draw(mt).text((110, AH - 104), txt, font=f, fill=255)
    _paint(im, mt, (120, 200, 170), alpha=0.5)
    sheen = Image.new("L", (AW, AH), 0)
    ImageDraw.Draw(sheen).polygon([(AW * 0.45, 0), (AW * 0.65, 0), (AW * 0.30, AH), (AW * 0.10, AH)], fill=24)
    im.paste((255, 255, 255), (0, 0), ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(40)), card))
    rnd = random.Random(11)
    sp = ImageDraw.Draw(im, "RGBA")
    for _ in range(24):
        x, y = rnd.randint(110, AW - 110), rnd.randint(110, AH - 110)
        if 200 < x < AW - 200 and 190 < y < AH - 190:
            continue
        _sparkle(sp, x, y, rnd.randint(6, 13), (255, 255, 255, rnd.randint(90, 200)))
    return im


BG = {"3D": bg_3d, "4D": bg_4d, "5D": bg_5d, "6D": bg_6d, "7D": bg_7d}


# ------------------------------------------------------------------ matn effektlari
def make_fx(st):
    def emb(base, off=3):
        return lambda im, m: (_paint(im, m, (20, 60, 44), off, off, 1.2, .55), _paint(im, m, (255, 255, 255), -1, -1, 0, .9), _paint(im, m, base))

    def flat(c, sh=False):
        return lambda im, m: ((_paint(im, m, (0, 0, 0), 2, 3, 3, .3) if sh else None), _paint(im, m, c))

    def foil(stops, dark=(0, 24, 16), off=3):
        return lambda im, m: (_paint(im, m, dark, off, off + 1, 2, .6), _paint_grad(im, m, stops))

    def glow(c, g=GLOW, r=12, a=.7):
        return lambda im, m: ((_paint(im, m, g, 0, 0, r, a) if g else None), _paint(im, m, c))

    def extrude(face, side, depth=6, g=GLOW):
        def f(im, m):
            _paint(im, m, g, 0, 0, 16, .55)
            for k in range(depth, 0, -1):
                _paint(im, m, side, k, k)
            _paint_grad(im, m, face)
        return f
    if st == "3D":
        return dict(brand=emb(G1, 2), label=emb(G3, 2), title=emb(G1, 4), who=flat(MUT), name=emb(INK, 3), desc=flat((40, 72, 60)), foot=flat(MUT), ink=INK, mut=MUT)
    if st == "4D":
        return dict(brand=flat(G1), label=flat(G3), title=foil([(0, (3, 46, 33)), (0.35, (14, 112, 80)), (0.6, (6, 64, 46)), (0.85, (20, 130, 94)), (1, (4, 52, 38))], (4, 40, 28)), who=flat(MUT),
                    name=flat(INK, True), desc=flat((40, 72, 60)), foot=flat(MUT), ink=INK, mut=MUT)
    if st == "5D":
        return dict(brand=foil(MINT_FOIL, off=1), label=flat((196, 240, 218)), title=foil(MINT_FOIL), who=flat((150, 206, 182)), name=flat((255, 255, 255), True),
                    desc=flat((214, 240, 228)), foot=flat((150, 206, 182)), ink=(255, 255, 255), mut=(150, 206, 182))
    if st == "6D":
        return dict(brand=glow((196, 250, 224), GLOW, 8, .55), label=glow((226, 248, 238)), title=glow((255, 255, 255), GLOW, 16, .8), who=glow((176, 222, 202)),
                    name=glow((196, 250, 224), GLOW, 14, .65), desc=glow((226, 248, 238)), foot=glow((176, 222, 202)), ink=(255, 255, 255), mut=(176, 222, 202))
    goldf = [(0, (236, 255, 244)), (0.35, (150, 240, 196)), (0.65, (40, 170, 120)), (1, (196, 255, 224))]
    whitef = [(0, (255, 255, 255)), (0.5, (214, 250, 232)), (1, (150, 220, 190))]
    return dict(brand=glow((196, 250, 224), GLOW, 8), label=glow((170, 255, 214), GLOW, 8, .5), title=extrude(goldf, (4, 56, 40), 6), who=glow((150, 210, 186)),
                name=extrude(whitef, (6, 70, 50), 4), desc=glow((214, 244, 230)), foot=glow((150, 210, 186)), ink=(255, 255, 255), mut=(150, 210, 186))


def chip(im, x, y, w, h, a, b, st, big=False):
    m = _blank()
    ImageDraw.Draw(m).rounded_rectangle([x, y, x + w, y + h], radius=22, fill=255)
    dd = ImageDraw.Draw(im, "RGBA")
    if st in ("3D", "4D"):
        if st == "4D":
            _soft_shadow(im, m, 0, 10, 9, .45)
        else:
            dd.rounded_rectangle([x + 4, y + 6, x + w + 4, y + h + 6], radius=22, fill=(150, 184, 168))
        dd.rounded_rectangle([x, y, x + w, y + h], radius=22, fill=G2 if big else MINT, outline=G3, width=3)
        la, lb = ((190, 244, 218), (255, 255, 255)) if big else (MUT, INK)
    elif st == "5D":
        _soft_shadow(im, m, 3, 8, 8, .55)
        dd.rounded_rectangle([x, y, x + w, y + h], radius=22, fill=(255, 255, 255, 24), outline=(130, 220, 180, 200), width=3)
        la, lb = (170, 230, 200), (255, 255, 255)
    elif st == "6D":
        _soft_shadow(im, m, 0, 10, 12, .35)
        dd.rounded_rectangle([x, y, x + w, y + h], radius=22, fill=(25, 194, 138, 90) if big else (255, 255, 255, 28), outline=(190, 255, 225, 230) if big else (255, 255, 255, 110), width=3)
        dd.rounded_rectangle([x + 6, y + 6, x + w - 6, y + h // 2], radius=16, fill=(255, 255, 255, 22))
        la, lb = ((214, 255, 236) if big else (176, 222, 202)), (255, 255, 255)
    else:
        _soft_shadow(im, m, 0, 0, 14, .8, GLOW)
        dd.rounded_rectangle([x, y, x + w, y + h], radius=22, fill=(255, 255, 255, 20), outline=(60, 220, 170, 210), width=3)
        la, lb = (160, 230, 200), (255, 255, 255)
    _paint(im, _text_mask(x + w // 2, y + 18, a, font(17, True, False), tr=3), la)
    _paint(im, _text_mask(x + w // 2, y + 50, b, font(38, True, True)), lb)


def chips_row(im, y, stats, st):
    n = len(stats)
    cw, gap = 290, 24
    x0 = AW / 2 - (n * cw + (n - 1) * gap) / 2
    for i, (a, b) in enumerate(stats):
        chip(im, int(x0 + i * (cw + gap)), y, cw, 112, a, b, st, i == 0)


# ------------------------------------------------------------------ emblemalar
def _smooth(pts, it=3):
    for _ in range(it):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            out += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]), (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
        pts = out
    return pts


def emblem_flame(im, cx, cy, S):
    base = [(0, -1.0), (0.22, -0.62), (0.5, -0.3), (0.64, 0.12), (0.52, 0.62), (0.2, 0.92), (0, 0.98), (-0.2, 0.92), (-0.52, 0.62), (-0.64, 0.1), (-0.4, -0.25), (-0.3, -0.55)]
    halo = _blank()
    ImageDraw.Draw(halo).ellipse([cx - S * 1.1, cy - S * 1.1, cx + S * 1.1, cy + S * 1.1], fill=255)
    _paint(im, halo, (255, 190, 60), 0, 0, 50, .35)
    for k, (col, sc, dy) in enumerate((((214, 96, 8), 1.0, 0), ((255, 170, 20), 0.82, 0.12), ((255, 226, 110), 0.56, 0.3), ((255, 250, 214), 0.3, 0.5))):
        pts = _smooth([(cx + x * S * sc, cy + (y * sc + dy) * S) for x, y in base])
        m = _blank()
        ImageDraw.Draw(m).polygon(pts, fill=255)
        if k == 0:
            _soft_shadow(im, m, 6, 14, 12, .45)
        im.paste(col, (0, 0), m.filter(ImageFilter.GaussianBlur(1.2)))


def emblem_hero(im, cx, cy, R):
    rays = _blank()
    rd = ImageDraw.Draw(rays)
    for i in range(24):
        a = math.pi * 2 * i / 24
        rd.polygon([(cx, cy), (cx + math.cos(a - .05) * R * 2.6, cy + math.sin(a - .05) * R * 2.6), (cx + math.cos(a + .05) * R * 2.6, cy + math.sin(a + .05) * R * 2.6)], fill=60)
    _paint(im, rays.filter(ImageFilter.GaussianBlur(3)), (255, 255, 255), alpha=.28)
    _laurel(im, cx, cy + 10, R * 1.45, (18, 138, 99, 240), -1, n=10)
    _laurel(im, cx, cy + 10, R * 1.45, (18, 138, 99, 240), 1, n=10)
    paste_medal(im, cx, cy - 20, R, 1, extrude=8, ribbon=G2)


def emblem_wall(im, top, st, fx):
    """Devor: 3 plastina (1-o‘rin markazda balandroq), pastida 4–5-o‘rinlar."""
    cx = AW // 2
    spec = ((2, cx - 300, 400, 250), (1, cx, 360, 310), (3, cx + 300, 425, 215))   # (o‘rin, markaz x, y-yuqori, balandlik)
    for rank, x, y, h in spec:
        w = 250
        m = _blank()
        ImageDraw.Draw(m).rounded_rectangle([x - w // 2, y, x + w // 2, y + h], radius=20, fill=255)
        _soft_shadow(im, m, 4, 12, 10, .6)
        hi, ba, lo = MEDAL[rank]
        plate = _grad_v(w, h, [(0, hi), (0.5, ba), (1, lo)])
        im.paste(plate, (x - w // 2, y), m.crop((x - w // 2, y, x + w // 2, y + h)))
        dd = ImageDraw.Draw(im)
        dd.rounded_rectangle([x - w // 2 + 8, y + 8, x + w // 2 - 8, y + h - 8], radius=14, outline=_mix(hi, (255, 255, 255), .5), width=3)
        for px, py in ((x - w // 2 + 20, y + 20), (x + w // 2 - 20, y + 20)):
            dd.ellipse([px - 6, py - 6, px + 6, py + 6], fill=_mix(lo, (0, 0, 0), .3))
        ink = _mix(lo, (0, 0, 0), .55)
        dd.text((x, y + 70), str(rank), font=font(86, True, True), fill=ink, anchor="mm")
        name, xp = top[rank - 1]
        lines, f = fit_lines(name, w - 36, [30, 26, 22], True, False)
        dd.text((x, y + 142), lines[0], font=f, fill=ink, anchor="mm")
        dd.text((x, y + 182), f"{xp:,g} ball".replace(",", " "), font=font(24, True, False), fill=_mix(lo, (0, 0, 0), .35), anchor="mm")
    # 4–5-o‘rinlar
    for i, (name, xp) in enumerate(top[3:5]):
        y = 712 + i * 76
        m = _blank()
        ImageDraw.Draw(m).rounded_rectangle([160, y, AW - 160, y + 64], radius=18, fill=255)
        dd = ImageDraw.Draw(im, "RGBA")
        dd.rounded_rectangle([160, y, AW - 160, y + 64], radius=18, fill=(255, 255, 255, 26), outline=(130, 220, 180, 170), width=2)
        dd.text((200, y + 32), f"{i + 4}", font=font(30, True, True), fill=(190, 244, 218), anchor="lm")
        dd.text((260, y + 32), name, font=font(28, True, False), fill=(255, 255, 255), anchor="lm")
        dd.text((AW - 200, y + 32), f"{xp:,g} ball".replace(",", " "), font=font(26, True, False), fill=(190, 244, 218), anchor="rm")


def _mini_cert(w, h, rank):
    t = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=12, fill=(240, 249, 244, 255), outline=(190, 255, 225, 255), width=3)
    d.rounded_rectangle([8, 8, w - 9, h - 9], radius=8, outline=G3, width=2)
    d.line([(w * .22, h * .30), (w * .78, h * .30)], fill=G2, width=6)
    d.line([(w * .30, h * .44), (w * .70, h * .44)], fill=(150, 190, 172), width=4)
    d.line([(w * .26, h * .54), (w * .74, h * .54)], fill=(190, 214, 202), width=4)
    hi, ba, lo = MEDAL[rank]
    d.ellipse([w / 2 - 22, h * .68 - 22, w / 2 + 22, h * .68 + 22], fill=ba, outline=hi, width=3)
    return t


def emblem_stack(im, cx, cy, count):
    for ang, dx, dy, rk in ((-12, -150, 20, 3), (11, 150, 24, 2), (-2, 0, -8, 1)):
        t = _mini_cert(300, 210, rk).rotate(ang, expand=True, resample=Image.BICUBIC)
        sh = Image.new("L", im.size, 0)
        sh.paste(t.split()[3], (int(cx + dx - t.size[0] / 2 + 8), int(cy + dy - t.size[1] / 2 + 18)))
        im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * .5)))
        im.paste(t, (int(cx + dx - t.size[0] / 2), int(cy + dy - t.size[1] / 2)), t)
    badge = _blank()
    ImageDraw.Draw(badge).ellipse([cx - 78, cy + 108, cx + 78, cy + 264], fill=255)
    _soft_shadow(im, badge, 0, 8, 10, .5)
    d = ImageDraw.Draw(im)
    d.ellipse([cx - 78, cy + 108, cx + 78, cy + 264], fill=G2, outline=(190, 255, 225), width=6)
    d.text((cx, cy + 184), str(count), font=font(92, True, True), fill=(255, 255, 255), anchor="mm")


def emblem_trophy(im, cx, cy, S):
    halo = _blank()
    ImageDraw.Draw(halo).ellipse([cx - S * 1.5, cy - S * 1.3, cx + S * 1.5, cy + S * 1.3], fill=255)
    _paint(im, halo, MEDAL[1][1], 0, 0, 60, .35)
    _laurel(im, cx, cy + 40, S * 1.18, (150, 232, 190, 235), -1, n=11)
    _laurel(im, cx, cy + 40, S * 1.18, (150, 232, 190, 235), 1, n=11)
    parts = []
    cup = _blank()
    cd = ImageDraw.Draw(cup)
    cd.polygon([(cx - S * .62, cy - S * .78), (cx + S * .62, cy - S * .78), (cx + S * .48, cy + S * .1), (cx + S * .22, cy + S * .38), (cx - S * .22, cy + S * .38), (cx - S * .48, cy + S * .1)], fill=255)
    for s in (-1, 1):
        cd.arc([cx + s * S * .62 - S * .36, cy - S * .68, cx + s * S * .62 + S * .36, cy - S * .06], 90 if s < 0 else -90, 270 if s < 0 else 90, fill=255, width=int(S * .1))
    cd.rectangle([cx - S * .1, cy + S * .38, cx + S * .1, cy + S * .62], fill=255)
    cd.polygon([(cx - S * .5, cy + S * .62), (cx + S * .5, cy + S * .62), (cx + S * .56, cy + S * .78), (cx - S * .56, cy + S * .78)], fill=255)
    _soft_shadow(im, cup, 8, 16, 12, .55)
    for k in range(9, 0, -1):
        _paint(im, cup, (96, 62, 12), k // 2 + 1, k)
    _paint_grad(im, cup, [(0, (255, 244, 196)), (0.35, (246, 206, 108)), (0.65, (196, 146, 52)), (1, (255, 226, 140))], glare=True)
    d = ImageDraw.Draw(im)
    _sparkle(d, cx, cy - S * .28, S * .22, (255, 255, 255, 240))


# ------------------------------------------------------------------ kartani yig‘ish
def render(kind, data=None, code="YT-0000000000", style=None):
    st = (style or STYLE_OF[kind]).upper()
    P = dict(SAMPLE[kind]); P.update(data or {})
    with ca._RL:
        old = (ca.W, ca.H); ca.W, ca.H = AW, AH
        try:
            im = BG[st]()
            fx = make_fx(st)
            cx = AW // 2
            fx["brand"](im, _text_mask(cx, 112, "ESSE AKADEMIYASI", font(24, True, False), tr=9))
            fx["label"](im, _text_mask(cx, 156, LABELS[kind], font(26, True, False), tr=7))
            # emblema
            if kind == "hero":
                emblem_hero(im, cx, 400, 120)
            elif kind == "streak":
                emblem_flame(im, cx, 388, 170)
                d = ImageDraw.Draw(im)
                d.text((cx, 452), str(P.get("days", 30)), font=font(110, True, True), fill=(120, 40, 0), anchor="mm")
            elif kind == "bilimdon":
                emblem_stack(im, cx, 360, P["count"])
            elif kind == "legend":
                emblem_trophy(im, cx, 372, 134)
            # sarlavha
            lines, f = fit_lines(TITLES[kind], 820, [92, 84, 76, 68, 60, 54, 48])
            y = 650
            if kind == "wall":
                y = 212
            for i, ln in enumerate(lines):
                fx["title"](im, _text_mask(cx, y + i * (f.size + 8), ln, f, tr=2))
            ty = y + len(lines) * (f.size + 8)
            if kind == "wall":
                fx["who"](im, _text_mask(cx, ty + 6, P["period"], font(28, True, False), tr=4))
                emblem_wall(im, P["top"], st, fx)
                fx["desc"](im, _text_mask(cx, 880, P.get("wall_note") or "Devorga chiqish uchun: kuniga bitta mashq yetarli", font(27, False, False)))
                chips_row(im, 950, P.get("chips") or [("HAFTA SARDORI", "1 240 ball"), ("ISHTIROKCHI", "86 kishi"), ("KEYINGI HAFTA", "dushanba")], st)
                fx["foot"](im, _text_mask(cx, 1190, P["date"], font(24, True, False), tr=2))
                fx["foot"](im, _text_mask(cx, 1230, "Har dushanba yangilanadi • Esse Akademiyasi", font(20, False, False)))
            else:
                fx["who"](im, _text_mask(cx, ty + 22, "ushbu yutuq egasi", font(24, False, False), tr=3))
                nl, nf = fit_lines(P["name"], 860, [84, 76, 68, 60, 52])
                fx["name"](im, _text_mask(cx, ty + 64, nl[0] if len(nl) == 1 else " ".join(nl), nf))
                ny = ty + 64 + nf.size + 26
                for i, ln in enumerate(_wrap_text(P["desc"], font(30, False, False), 800)[:3]):
                    fx["desc"](im, _text_mask(cx, ny + i * 44, ln, font(30, False, False)))
                chips_row(im, 1000, P["stats"], st)
                fx["foot"](im, _text_mask(cx, 1150, P["date"], font(24, True, False), tr=2))
                fx["foot"](im, _text_mask(cx, 1188, "Ertaga navbat sizniki — bugun bitta mashq qiling", font(21, False, False)))
                fx["foot"](im, _text_mask(cx, 1222, f"№ {code}", font(18, True, False), tr=2))
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "PNG", optimize=True)
            return buf.getvalue()
        finally:
            ca.W, ca.H = old
