# -*- coding: utf-8 -*-
"""v121 — oddiy testlarda 1–3-o‘rin sovrindorlari uchun «bilimdon» sertifikati (A4 gorizontal, 1754×1240).

Beshta uslub: «3D», «4D», «5D», «6D», «7D» — raqam chuqurlik/qatlam darajasini bildiradi
(3D — bo‘rtma; 4D — qatlamli qog‘oz; 5D — zumrad folga; 6D — shisha; 7D — golografik, ko‘p qatlamli). Ranglar — Mini App yashil palitrasi.
Faqat Pillow ishlatiladi (numpy kerak emas). Shrift/yordamchilar cert_design bilan umumiy.
render(data, code) -> PNG baytlari (cert_design.render('topaward', ...) shu funksiyani chaqiradi).
"""
import io, math, random, threading

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import cert_design as cd

W, H = 1754, 1240
STYLES = ("3D", "4D", "5D", "6D", "7D")
DEFAULT_STYLE = "5D"
STYLE_NAMES = {"3D": "Bo‘rtma zumrad", "4D": "Qatlamli qog‘oz", "5D": "Zumrad folga", "6D": "Yashil shisha", "7D": "Zumrad golografik"}

_RL = threading.Lock()

# medal ranglari: (yorug‘, asosiy, qorong‘i)
MEDAL = {1: ((255, 238, 168), (230, 180, 60), (140, 92, 22)),
         2: ((248, 250, 255), (196, 202, 214), (104, 112, 128)),
         3: ((248, 206, 164), (204, 134, 78), (120, 70, 34))}
RANK_WORD = {1: "1-o‘rin", 2: "2-o‘rin", 3: "3-o‘rin"}

# Mini App palitrasi (miniapp/style.css): --g1 #08402f, --g2 #0b5a41, --g3 #128a63, --mint #e3f1ea, --ink #0d2b22, --mut #5f7a6e, nur #19c28a
G1, G2, G3 = (8, 64, 47), (11, 90, 65), (18, 138, 99)
MINT, PAPER, INK, MUT, GLOW = (227, 241, 234), (243, 248, 245), (13, 43, 34), (95, 122, 110), (25, 194, 138)
GREEN_FOIL = [(0, (6, 70, 50)), (0.22, (150, 232, 196)), (0.42, (18, 138, 99)), (0.64, (196, 246, 222)), (0.84, (11, 100, 72)), (1, (96, 206, 164))]
MINT_FOIL = [(0, (214, 255, 236)), (0.35, (150, 232, 196)), (0.65, (66, 176, 130)), (1, (186, 246, 214))]


# ------------------------------------------------------------------ yordamchilar
def font(sz, bold=False, serif=True):
    return cd._font(int(sz), bold, serif)


def tlen(f, t, tr=0):
    return (sum(f.getlength(c) + tr for c in t) - tr) if tr else f.getlength(t)


def _mix(a, b, k):
    return tuple(int(a[i] * (1 - k) + b[i] * k) for i in range(len(a)))


def _grad_v(w, h, stops):
    """Vertikal gradient: stops=[(0..1, rgb)]."""
    col = Image.new("RGB", (1, h))
    px = col.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = stops[-1][1]
        for i in range(len(stops) - 1):
            a, ca = stops[i]
            b, cb = stops[i + 1]
            if a <= t <= b:
                c = _mix(ca, cb, (t - a) / (b - a) if b > a else 0)
                break
        px[0, y] = c
    return col.resize((w, h))


def _grad_d(w, h, stops, angle=0.6):
    """Diagonal gradient (angle ~ burchak nisbati)."""
    big = _grad_v(max(w, h) * 2, max(w, h) * 2, stops)
    big = big.rotate(-math.degrees(math.atan(angle)) * 1.0, resample=Image.BICUBIC)
    cx, cy = big.size[0] // 2, big.size[1] // 2
    return big.crop((cx - w // 2, cy - h // 2, cx - w // 2 + w, cy - h // 2 + h))


def _radial(size, inner, outer, power=1.0):
    """Radial gradient (markazda inner, chetda outer)."""
    m = Image.radial_gradient("L").resize(size, Image.BICUBIC)
    if power != 1.0:
        m = m.point(lambda v: int(255 * ((v / 255) ** power)))
    return Image.composite(Image.new("RGB", size, outer), Image.new("RGB", size, inner), m)


def _noise(size, amp=10):
    try:
        n = Image.effect_noise(size, 64).point(lambda v: 128 + (v - 128) * amp // 64)
        return n
    except Exception:
        return Image.new("L", size, 128)


def _blank():
    return Image.new("L", (W, H), 0)


def _text_mask(cx, y, text, f, tr=0, anchor="c"):
    m = _blank()
    d = ImageDraw.Draw(m)
    if not tr:
        if anchor == "c":
            d.text((cx, y), text, font=f, fill=255, anchor="mt")
        elif anchor == "l":
            d.text((cx, y), text, font=f, fill=255, anchor="lt")
        else:
            d.text((cx, y), text, font=f, fill=255, anchor="rt")
        return m
    w = tlen(f, text, tr)
    x = cx - w / 2 if anchor == "c" else (cx if anchor == "l" else cx - w)
    base = y + f.getmetrics()[0]   # bitta umumiy baseline — harflar tekis turadi
    for ch in text:
        d.text((x, base), ch, font=f, fill=255, anchor="ls")
        x += f.getlength(ch) + tr
    return m


def _shift(m, dx, dy):
    return ImageChops.offset(m, dx, dy)


def _paint(im, mask, color, dx=0, dy=0, blur=0, alpha=1.0):
    m = _shift(mask, dx, dy) if (dx or dy) else mask
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 1.0:
        m = m.point(lambda v: int(v * alpha))
    im.paste(color, (0, 0), m)


def _paint_grad(im, mask, stops, glare=True):
    """Metall gradient: faqat maska chegarasi uchun quriladi + yorug‘lik chizig‘i."""
    bb = mask.getbbox()
    if not bb:
        return
    x0, y0, x1, y1 = bb
    g = _grad_v(x1 - x0, max(1, y1 - y0), stops)
    if glare:
        gl = Image.new("L", g.size, 0)
        ImageDraw.Draw(gl).polygon([(0, 0), (g.size[0] * 0.35, 0), (g.size[0] * 0.15, g.size[1]), (0, g.size[1])], fill=70)
        g.paste((255, 255, 255), (0, 0), gl.filter(ImageFilter.GaussianBlur(10)))
    im.paste(g, (x0, y0), mask.crop(bb))


def _soft_shadow(im, shape_mask, dx, dy, blur, alpha=0.55, color=(0, 0, 0)):
    _paint(im, shape_mask, color, dx, dy, blur, alpha)


def _wrap2(text, f, max_w):
    words = text.split()
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        w = max(tlen(f, a), tlen(f, b))
        if best is None or w < best[0]:
            best = (w, a, b)
    return [best[1], best[2]] if best else [text]


def fit_lines(text, max_w, sizes, bold=True, serif=True, tr=0):
    """Matnni max_w ga sig‘dirish: avval bir qator (shrift kichrayadi), bo‘lmasa ikki qator."""
    for sz in sizes:
        f = font(sz, bold, serif)
        if tlen(f, text, tr) <= max_w:
            return [text], f
    for sz in sizes:
        f = font(sz, bold, serif)
        ls = _wrap2(text, f, max_w)
        if max(tlen(f, l, tr) for l in ls) <= max_w:
            return ls, f
    f = font(sizes[-1], bold, serif)
    return _wrap2(text, f, max_w), f


def _wrap_text(text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if tlen(f, t) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------------------ medal (2x tilda chiziladi — silliq chetlar)
def medal_tile(R, rank, dark_bg=False, ribbon=(150, 30, 48), extrude=0):
    S = 2
    pad = int(R * 0.35)
    sz = (int(R * 2 + pad * 2) * S, int(R * 3.0 + pad) * S)
    t = Image.new("RGBA", sz, (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    cx, cy = sz[0] // 2, int((pad + R) * S)
    hi, base, lo = MEDAL[rank]
    r = R * S
    # lenta
    for s in (-1, 1):
        pts = [(cx + s * 0.10 * r, cy + 0.55 * r), (cx + s * 0.95 * r, cy + 1.55 * r), (cx + s * 0.60 * r, cy + 1.42 * r),
               (cx + s * 0.32 * r, cy + 1.95 * r), (cx - s * 0.08 * r, cy + 0.70 * r)]
        d.polygon(pts, fill=ribbon)
        d.polygon([pts[0], pts[1], pts[2], (cx + s * 0.24 * r, cy + 0.9 * r)], fill=_mix(ribbon, (255, 255, 255), 0.18))
        d.line([pts[0], pts[1]], fill=_mix(ribbon, (0, 0, 0), 0.35), width=3 * S)
    # tashqi halqa (radial gradient: konussimon yaltirash imitatsiyasi)
    ring = Image.new("RGBA", sz, (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    steps = 40
    for i in range(steps):
        k = i / (steps - 1)
        c = _mix(hi, lo, abs(k - 0.35) * 1.5 if k > 0.35 else (0.35 - k) * 1.2)
        rr = r * (1.0 - 0.0016 * i * 8 / steps * 10)
        rd.ellipse([cx - rr * (1 - k * 0.22), cy - rr * (1 - k * 0.22), cx + rr * (1 - k * 0.22), cy + rr * (1 - k * 0.22)], fill=c + (255,))
    # tishlangan chet
    star = Image.new("L", sz, 0)
    sd = ImageDraw.Draw(star)
    N = 36
    pts = []
    for i in range(N * 2):
        a = math.pi * i / N
        rr = r if i % 2 == 0 else r * 0.945
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    sd.polygon(pts, fill=255)
    if extrude:
        for k in range(extrude, 0, -1):
            sh = Image.new("RGBA", sz, _mix(lo, (0, 0, 0), 0.4) + (255,))
            t.paste(sh, (0, k * S), star)
    t.paste(ring, (0, 0), star)
    d = ImageDraw.Draw(t)
    d.ellipse([cx - r * 0.84, cy - r * 0.84, cx + r * 0.84, cy + r * 0.84], outline=_mix(hi, (255, 255, 255), 0.5), width=3 * S)
    d.ellipse([cx - r * 0.74, cy - r * 0.74, cx + r * 0.74, cy + r * 0.74], outline=_mix(lo, (0, 0, 0), 0.2), width=2 * S)
    # ichki disk
    inner = _radial((int(r * 1.4), int(r * 1.4)), _mix(base, (255, 255, 255), 0.35), _mix(base, lo, 0.55), 1.2)
    msk = Image.new("L", inner.size, 0)
    ImageDraw.Draw(msk).ellipse([0, 0, inner.size[0] - 1, inner.size[1] - 1], fill=255)
    t.paste(inner, (int(cx - r * 0.7), int(cy - r * 0.7)), msk)
    # raqam
    f = cd._font(int(r * 1.05), True, True)
    ink = _mix(lo, (0, 0, 0), 0.25)
    d.text((cx + 2 * S, cy - r * 0.02 + 2 * S), str(rank), font=f, fill=_mix(hi, (255, 255, 255), 0.6), anchor="mm")
    d.text((cx, cy - r * 0.02), str(rank), font=f, fill=ink, anchor="mm")
    f2 = cd._font(int(r * 0.2), True, False)
    d.text((cx, cy + r * 0.48), "O‘RIN", font=f2, fill=ink, anchor="mm")
    return t.resize((sz[0] // S, sz[1] // S), Image.LANCZOS), (cx // S, cy // S)


def paste_medal(im, cx, cy, R, rank, shadow=True, **kw):
    t, (ox, oy) = medal_tile(R, rank, **kw)
    if shadow:
        a = t.split()[3]
        sh = Image.new("L", im.size, 0)
        sh.paste(a, (int(cx - ox + 10), int(cy - oy + 16)))
        im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(12)).point(lambda v: int(v * 0.5)))
    im.paste(t, (int(cx - ox), int(cy - oy)), t)


def _rosette(im, cx, cy, size, R, r, p, col):
    """Gilloshe (gipotroxoida) naqshi: yopiq, nozik chiziqli rozetka."""
    d = ImageDraw.Draw(im, "RGBA")
    k = size / float((R - r) + p)
    T = 2 * math.pi * r / math.gcd(R, r)
    n = 3000
    pts = []
    for i in range(n + 1):
        t = T * i / n
        pts.append((cx + k * ((R - r) * math.cos(t) + p * math.cos((R - r) / r * t)), cy + k * ((R - r) * math.sin(t) - p * math.sin((R - r) / r * t))))
    d.line(pts, fill=col, width=1)


def _sparkle(d, x, y, r, col):
    d.polygon([(x, y - r), (x + r * 0.18, y - r * 0.18), (x + r, y), (x + r * 0.18, y + r * 0.18), (x, y + r), (x - r * 0.18, y + r * 0.18), (x - r, y), (x - r * 0.18, y - r * 0.18)], fill=col)


def _leaf(d, x, y, ang, L, wd, col):
    pts = []
    for i in range(0, 21):
        t = i / 20
        u = L * t
        v = wd * math.sin(math.pi * t) ** 0.9
        pts.append((u, v))
    pts += [(u, -v) for (u, v) in reversed(pts)]
    ca, sa = math.cos(ang), math.sin(ang)
    d.polygon([(x + u * ca - v * sa, y + u * sa + v * ca) for (u, v) in pts], fill=col)


def _laurel(im, cx, cy, R, col, side=1, n=9):
    """Lavr shoxi: yoy bo‘ylab qo‘sh barglar (side=-1 chap, +1 o‘ng)."""
    d = ImageDraw.Draw(im, "RGBA")
    dark = _mix(col[:3], (0, 0, 0), 0.35) + (col[3] if len(col) > 3 else 255,)
    prev = None
    for i in range(n):
        a = math.radians(100 - i * 17) if side > 0 else math.radians(80 + i * 17)
        px, py = cx + math.cos(a) * R * 1.0, cy + math.sin(a) * R * 1.15
        if prev:
            d.line([prev, (px, py)], fill=dark, width=3)
        prev = (px, py)
        tang = a + (math.pi / 2 if side > 0 else -math.pi / 2)
        L = 40 - i * 1.6
        for sgn in (-1, 1):
            ang = tang + sgn * math.radians(38)
            if side < 0:
                ang += math.pi
            _leaf(d, px, py, ang if side > 0 else ang, L, 11 - i * 0.4, col if sgn > 0 else dark)


# ------------------------------------------------------------------ matn tayyorlash
def _prep(data, code):
    rank = min(max(int(data.get("rank", 1) or 1), 1), 3)
    correct = int(data.get("correct", 0) or 0)
    total = int(data.get("total", 0) or 0)
    pct = int(round(correct / total * 100)) if total else int(data.get("percent", 0) or 0)
    testname = str(data.get("testname") or "").strip()[:64]
    sent = (f"«{testname}» testida {RANK_WORD[rank]}ni egallagani uchun taqdirlanadi" if testname
            else f"Test natijalariga ko‘ra {RANK_WORD[rank]}ni egallagani uchun taqdirlanadi")
    return dict(rank=rank, award=str(data.get("award") or "Test bilimdoni").strip()[:60], name=str(data.get("name") or "Talabgor").strip()[:44],
                sentence=sent, correct=correct, total=total, pct=pct, date=str(data.get("date") or ""), code=str(code),
                subject=str(data.get("subject") or "").strip()[:60])


def _chips(P):
    return [("O‘RIN", RANK_WORD[P["rank"]].split("-")[0] + "-o‘rin"), ("TO‘G‘RI JAVOB", f"{P['correct']} / {P['total']}" if P["total"] else str(P["correct"])), ("NATIJA", f"{P['pct']}%")]


# ------------------------------------------------------------------ umumiy joylashuv (matn qatlamlari uslubga qarab effekt oladi)
def layout(im, P, style_fx, palette, cx=W // 2, left=230, right=W - 230):
    """style_fx: dict — brand/sub/title/who/name/sentence/chip_label/chip_value uchun chizish funksiyalari (im, mask)."""
    fx = style_fx
    # brend
    f = font(24, True, False)
    fx["brand"](im, _text_mask(cx, 140, "ESSE AKADEMIYASI", f, tr=9))
    f = font(27, True, False)
    fx["sub"](im, _text_mask(cx, 186, "MAXSUS SERTIFIKAT", f, tr=7))
    # sarlavha (bilimdon nomi)
    lines, f = fit_lines(P["award"].upper(), 1320, [92, 84, 76, 68, 60, 54])
    y = 246 if len(lines) == 1 else 232
    for i, ln in enumerate(lines):
        fx["title"](im, _text_mask(cx, y + i * (f.size + 8), ln, f, tr=2))
    ty = y + len(lines) * (f.size + 8) + 8
    # egasi
    fx["who"](im, _text_mask(cx, ty + 22, "ushbu sertifikat egasi", font(24, False, False), tr=3))
    lines, f = fit_lines(P["name"], 1250, [88, 80, 72, 64, 56, 48])
    fx["name"](im, _text_mask(cx, ty + 64, lines[0] if len(lines) == 1 else " ".join(lines), f))
    ny = ty + 64 + f.size + 22
    # tavsif
    f = font(29, False, False)
    ls = _wrap_text(P["sentence"], f, 1180)[:2]
    for i, ln in enumerate(ls):
        fx["sentence"](im, _text_mask(cx, ny + i * 42, ln, f))
    return ny + len(ls) * 42 + 24


def chips(im, P, y, draw_chip):
    cw, gap = 330, 26
    x0 = W / 2 - (3 * cw + 2 * gap) / 2
    for i, (a, b) in enumerate(_chips(P)):
        draw_chip(im, int(x0 + i * (cw + gap)), int(y), cw, 112, a, b, i == 0)


def footer(im, P, fx, y_sign=985):
    d = ImageDraw.Draw(im)
    f = font(20, False, False)
    d.line([230, y_sign, 560, y_sign], fill=fx["line"], width=2)
    d.line([W - 560, y_sign, W - 230, y_sign], fill=fx["line"], width=2)
    d.text((230, y_sign + 10), "Akademiya rahbari", font=f, fill=fx["muted"], anchor="lt")
    d.text((W - 230, y_sign + 10), "Imtihon markazi", font=f, fill=fx["muted"], anchor="rt")
    fx["code"](im, _text_mask(W // 2, 1062, f"Sertifikat №  {P['code']}   •   {P['date']}", font(21, True, False)))
    fx["note"](im, _text_mask(W // 2, 1096, "Esse Akademiyasi ichki test mukofoti — rasmiy davlat hujjati emas.", font(18, False, False)))


# ====================================================================== 3D — «Bo‘rtma zumrad»
def style_3d(P):
    im = Image.new("RGB", (W, H), (230, 244, 237))
    n = _noise((W, H), 6)
    im = ImageChops.add(im, Image.merge("RGB", (n, n, n)), 1, -128)
    d = ImageDraw.Draw(im)
    # bo‘rtma yashil ramka: yorug‘ (yuqori-chap) / qorong‘i (past-o‘ng) qirralar
    for i, (off, w) in enumerate(((34, 18), (74, 8), (96, 4))):
        for k in range(w):
            c_hi = _mix((236, 252, 244), G3, i * 0.35)
            c_lo = _mix(G2, (3, 30, 22), 0.55 + 0.1 * i)
            d.line([(off + k, off + k), (W - off - k, off + k)], fill=c_hi)
            d.line([(off + k, off + k), (off + k, H - off - k)], fill=c_hi)
            d.line([(off + k, H - off - k), (W - off - k, H - off - k)], fill=c_lo)
            d.line([(W - off - k, off + k), (W - off - k, H - off - k)], fill=c_lo)
    d.rectangle([118, 118, W - 118, H - 118], outline=G2, width=3)
    for sx, sy in ((130, 130), (W - 130, 130), (130, H - 130), (W - 130, H - 130)):
        for rr, w in ((44, 3), (30, 2), (16, 2)):
            d.ellipse([sx - rr, sy - rr, sx + rr, sy + rr], outline=G3 if rr != 30 else G1, width=w)

    def emb(base, hi=(255, 255, 255), lo=(20, 60, 44), off=2):
        def f(im, m):
            _paint(im, m, lo, off, off, 1.2, 0.55)
            _paint(im, m, hi, -1, -1, 0, 0.9)
            _paint(im, m, base)
        return f

    def flat3(c):
        return lambda im, m: _paint(im, m, c)
    fx = {"brand": emb(G1), "sub": emb(G3), "title": emb(G1, off=3), "who": flat3(MUT), "name": emb(INK, off=3),
          "sentence": flat3((40, 72, 60)), "code": flat3(G2), "note": flat3(MUT),
          "line": G1, "muted": MUT}
    y = layout(im, P, fx, None)

    def chip(im, x, y, w, h, a, b, big):
        dd = ImageDraw.Draw(im)
        bg = G2 if big else MINT
        dd.rounded_rectangle([x + 4, y + 6, x + w + 4, y + h + 6], radius=16, fill=(150, 184, 168))
        dd.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=bg, outline=G3, width=3)
        dd.line([(x + 18, y + 4), (x + w - 18, y + 4)], fill=_mix(bg, (255, 255, 255), 0.35), width=2)
        _paint(im, _text_mask(x + w // 2, y + 16, a, font(17, True, False), tr=3), (190, 244, 218) if big else MUT)
        _paint(im, _text_mask(x + w // 2, y + 48, b, font(40, True, True)), (255, 255, 255) if big else INK)
    chips(im, P, y, chip)
    footer(im, P, fx)
    paste_medal(im, W // 2, 868, 78, P["rank"], extrude=6, ribbon=G2)
    return im


# ====================================================================== 4D — «Qatlamli qog‘oz»
def style_4d(P):
    bg = _grad_d(W, H, [(0, (3, 34, 26)), (0.5, G2), (1, (3, 28, 21))], 0.5)
    im = bg.copy()
    d = ImageDraw.Draw(im, "RGBA")
    for k in range(9):   # fon naqshi: yumshoq doiralar
        r = 140 + k * 62
        d.ellipse([W * 0.82 - r, H * 0.1 - r, W * 0.82 + r, H * 0.1 + r], outline=(150, 240, 200, 14), width=2)

    def sheet(w, h, col, ang, dx, dy, shadow=True):
        t = Image.new("RGBA", (w, h), col + (255,))
        t = t.rotate(ang, expand=True, resample=Image.BICUBIC)
        x, y = (W - t.size[0]) // 2 + dx, (H - t.size[1]) // 2 + dy
        if shadow:
            sh = Image.new("L", im.size, 0)
            sh.paste(t.split()[3], (x + 6, y + 22))
            im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(20)).point(lambda v: int(v * 0.6)))
        im.paste(t, (x, y), t)
    sheet(1480, 1060, (178, 214, 196), -2.0, -6, 8)
    sheet(1480, 1060, (206, 232, 218), 1.5, 6, -2)
    main = Image.new("RGB", (1500, 1090), (236, 247, 241))
    n = _noise(main.size, 5)
    main = ImageChops.add(main, Image.merge("RGB", (n, n, n)), 1, -128)
    md = ImageDraw.Draw(main)
    md.rectangle([14, 14, main.size[0] - 15, main.size[1] - 15], outline=G3, width=6)
    md.rectangle([30, 30, main.size[0] - 31, main.size[1] - 31], outline=G1, width=2)
    ox, oy = (W - main.size[0]) // 2, (H - main.size[1]) // 2 + 2
    sh = Image.new("L", im.size, 0)
    sh.paste(Image.new("L", main.size, 255), (ox + 4, oy + 18))
    im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(22)).point(lambda v: int(v * 0.65)))
    im.paste(main, (ox, oy))

    def flat(c, shadow=False):
        def f(im, m):
            if shadow:
                _paint(im, m, (0, 0, 0), 2, 3, 3, 0.25)
            _paint(im, m, c)
        return f

    def foil(im, m):
        _paint(im, m, (4, 40, 28), 2, 3, 2, 0.5)
        _paint_grad(im, m, [(0, (3, 46, 33)), (0.35, (14, 112, 80)), (0.6, (6, 64, 46)), (0.85, (20, 130, 94)), (1, (4, 52, 38))], glare=False)
    fx = {"brand": flat(G1), "sub": flat(G3), "title": foil, "who": flat(MUT), "name": flat(INK, True),
          "sentence": flat((40, 72, 60)), "code": flat(G2), "note": flat(MUT), "line": G1, "muted": MUT}
    y = layout(im, P, fx, None, left=250, right=W - 250)

    def chip(im, x, y, w, h, a, b, big):
        sh = Image.new("L", im.size, 0)
        ImageDraw.Draw(sh).rounded_rectangle([x, y + 10, x + w, y + h + 10], radius=16, fill=255)
        im.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * 0.45)))
        dd = ImageDraw.Draw(im)
        dd.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=G2 if big else MINT, outline=G3, width=3)
        _paint(im, _text_mask(x + w // 2, y + 16, a, font(17, True, False), tr=3), (190, 244, 218) if big else MUT)
        _paint(im, _text_mask(x + w // 2, y + 48, b, font(40, True, True)), (255, 255, 255) if big else INK)
    chips(im, P, y, chip)
    footer(im, P, fx)
    paste_medal(im, W // 2, 866, 76, P["rank"], ribbon=G2)
    return im


# ====================================================================== 5D — «Oltin folga» (qirollik)
def style_5d(P):
    im = _grad_d(W, H, [(0, (3, 36, 27)), (0.55, G2), (1, (3, 28, 21))], 0.4)
    for (R, r, p, size, col) in ((60, 7, 9, 520, (190, 255, 225, 44)), (72, 11, 14, 380, (255, 255, 255, 32)), (45, 8, 12, 250, (190, 255, 225, 48))):
        _rosette(im, W / 2, H / 2 + 10, size, R, r, p, col)
    # zumrad folga ramka (qalin, bo‘rtma)
    fr = _blank()
    fd = ImageDraw.Draw(fr)
    fd.rectangle([34, 34, W - 34, H - 34], outline=255, width=26)
    fd.rectangle([84, 84, W - 84, H - 84], outline=255, width=5)
    fd.rectangle([100, 100, W - 100, H - 100], outline=255, width=2)
    _soft_shadow(im, fr, 4, 6, 6, 0.6)
    _paint_grad(im, fr, GREEN_FOIL, glare=False)
    for sx, sy in ((60, 60), (W - 60, 60), (60, H - 60), (W - 60, H - 60)):
        m = _blank()
        ImageDraw.Draw(m).ellipse([sx - 26, sy - 26, sx + 26, sy + 26], fill=255)
        _soft_shadow(im, m, 2, 3, 3, 0.5)
        _paint_grad(im, m, [(0, (210, 255, 236)), (0.5, G3), (1, (4, 50, 36))], glare=False)
    # ichki yorug‘lik (spotlight)
    spot = _radial((W, H), (255, 255, 255), (0, 0, 0), 0.9).convert("L").point(lambda v: 255 - v)
    im.paste(GLOW, (0, 0), spot.point(lambda v: int(v * 0.16)))

    def foil(sz_off=2):
        def f(im, m):
            _paint(im, m, (0, 24, 16), sz_off, sz_off + 1, 2, 0.6)
            _paint_grad(im, m, MINT_FOIL)
        return f

    def soft(c, sh=False):
        def f(im, m):
            if sh:
                _paint(im, m, (0, 0, 0), 2, 3, 3, 0.4)
            _paint(im, m, c)
        return f
    fx = {"brand": foil(1), "sub": soft((196, 240, 218)), "title": foil(3), "who": soft((150, 206, 182)), "name": soft((255, 255, 255), True),
          "sentence": soft((214, 240, 228)), "code": foil(1), "note": soft((150, 206, 182)), "line": (110, 200, 160), "muted": (150, 206, 182)}
    y = layout(im, P, fx, None)

    def chip(im, x, y, w, h, a, b, big):
        m = _blank()
        ImageDraw.Draw(m).rounded_rectangle([x, y, x + w, y + h], radius=18, fill=255)
        _soft_shadow(im, m, 3, 8, 8, 0.55)
        dd = ImageDraw.Draw(im, "RGBA")
        if big:
            _hi, _ba, _lo = MEDAL[P['rank']]
            im.paste(_grad_v(w, h, [(0, _hi), (0.5, _ba), (1, _lo)]), (x, y), m.crop((x, y, x + w, y + h)))
        else:
            dd.rounded_rectangle([x, y, x + w, y + h], radius=18, fill=(255, 255, 255, 24), outline=(130, 220, 180, 200), width=3)
        dd.rounded_rectangle([x, y, x + w, y + h], radius=18, outline=(255, 240, 190, 255) if big else (130, 220, 180, 200), width=3)
        _paint(im, _text_mask(x + w // 2, y + 16, a, font(17, True, False), tr=3), (70, 44, 6) if big else (170, 230, 200))
        _paint(im, _text_mask(x + w // 2, y + 48, b, font(40, True, True)), (40, 24, 0) if big else (255, 255, 255))
    chips(im, P, y, chip)
    footer(im, P, fx)
    paste_medal(im, W // 2, 866, 80, P["rank"], extrude=5, ribbon=G3)
    return im


# ====================================================================== 6D — «Shisha aurora»
def style_6d(P):
    im = _grad_d(W, H, [(0, (4, 34, 28)), (0.5, (8, 74, 58)), (1, (3, 26, 22))], 0.7)
    orbs = Image.new("RGB", (W, H), (0, 0, 0))
    od = ImageDraw.Draw(orbs)
    for (x, y, r, c) in ((260, 220, 330, (18, 138, 99)), (1500, 1020, 420, (25, 194, 138)), (1450, 140, 260, (120, 230, 150)), (240, 1060, 300, (20, 150, 140))):
        od.ellipse([x - r, y - r, x + r, y + r], fill=c)
    orbs = orbs.filter(ImageFilter.GaussianBlur(120)).point(lambda v: int(v * 0.62))
    im = ImageChops.add(im, orbs, 1.0, 0)
    # yulduzchalar
    rnd = random.Random(P["code"])
    sp = ImageDraw.Draw(im, "RGBA")
    for _ in range(70):
        x, y = rnd.randint(40, W - 40), rnd.randint(40, H - 40)
        sp.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(255, 255, 255, rnd.randint(60, 150)))
    # shisha karta
    cx0, cy0, cx1, cy1 = 110, 90, W - 110, H - 90
    card = _blank()
    ImageDraw.Draw(card).rounded_rectangle([cx0, cy0, cx1, cy1], radius=46, fill=255)
    _soft_shadow(im, card, 0, 26, 30, 0.55)
    blur = im.filter(ImageFilter.GaussianBlur(26))
    im.paste(blur, (0, 0), card)
    glass = Image.new("RGB", (W, H), (255, 255, 255))
    im.paste(glass, (0, 0), card.point(lambda v: int(v * 0.10)))
    im.paste((2, 24, 18), (0, 0), card.point(lambda v: int(v * 0.30)))
    hl = _grad_v(W, H, [(0, (255, 255, 255)), (0.45, (255, 255, 255)), (0.5, (255, 255, 255)), (1, (255, 255, 255))])
    streak = Image.new("L", (W, H), 0)
    ImageDraw.Draw(streak).polygon([(cx0, cy0), (cx0 + 760, cy0), (cx0 + 380, cy1), (cx0, cy1)], fill=26)
    streak = ImageChops.multiply(streak.filter(ImageFilter.GaussianBlur(30)), card)
    im.paste(hl, (0, 0), streak)
    d = ImageDraw.Draw(im, "RGBA")
    d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=46, outline=(255, 255, 255, 120), width=3)
    d.rounded_rectangle([cx0 + 14, cy0 + 14, cx1 - 14, cy1 - 14], radius=36, outline=(255, 255, 255, 40), width=2)

    def glow(c, g=None, r=10, a=0.7):
        def f(im, m):
            if g:
                _paint(im, m, g, 0, 0, r, a)
            _paint(im, m, c)
        return f
    gold = (196, 250, 224)
    fx = {"brand": glow(gold, GLOW, 8, .55), "sub": glow((226, 248, 238)), "title": glow((255, 255, 255), GLOW, 16, .8),
          "who": glow((176, 222, 202)), "name": glow(gold, GLOW, 14, .65), "sentence": glow((226, 248, 238)), "code": glow(gold),
          "note": glow((176, 222, 202)), "line": (255, 255, 255, 150), "muted": (176, 222, 202)}
    y = layout(im, P, fx, None)

    def chip(im, x, y, w, h, a, b, big):
        m = _blank()
        ImageDraw.Draw(m).rounded_rectangle([x, y, x + w, y + h], radius=22, fill=255)
        _soft_shadow(im, m, 0, 10, 12, 0.35)
        dd = ImageDraw.Draw(im, "RGBA")
        dd.rounded_rectangle([x, y, x + w, y + h], radius=22, fill=(25, 194, 138, 90) if big else (255, 255, 255, 28), outline=(190, 255, 225, 230) if big else (255, 255, 255, 110), width=3)
        dd.rounded_rectangle([x + 6, y + 6, x + w - 6, y + h // 2], radius=16, fill=(255, 255, 255, 22))
        _paint(im, _text_mask(x + w // 2, y + 16, a, font(17, True, False), tr=3), (214, 255, 236) if big else (176, 222, 202))
        _paint(im, _text_mask(x + w // 2, y + 48, b, font(40, True, True)), (255, 255, 255))
    chips(im, P, y, chip)
    footer(im, P, fx)
    # medal: yorug‘lik gardishi + aks
    halo = _blank()
    ImageDraw.Draw(halo).ellipse([W // 2 - 150, 866 - 150, W // 2 + 150, 866 + 150], fill=255)
    _paint(im, halo, MEDAL[P["rank"]][1], 0, 0, 40, 0.45)
    paste_medal(im, W // 2, 866, 78, P["rank"], ribbon=G3)
    return im


# ====================================================================== 7D — «Golografik prestij»
def style_7d(P):
    im = _grad_d(W, H, [(0, (2, 14, 11)), (0.5, (6, 36, 28)), (1, (2, 12, 9))], 0.5)
    orbs = Image.new("RGB", (W, H), (0, 0, 0))
    od = ImageDraw.Draw(orbs)
    for (x, y, r, c) in ((200, 160, 360, (18, 138, 99)), (1560, 180, 320, (20, 170, 150)), (880, 1240, 460, (25, 194, 138)), (1700, 1000, 260, (110, 220, 120))):
        od.ellipse([x - r, y - r, x + r, y + r], fill=c)
    im = ImageChops.add(im, orbs.filter(ImageFilter.GaussianBlur(130)).point(lambda v: int(v * 0.6)), 1.0, 0)
    # golografik ramka (kamalak gradienti)
    holo = _grad_d(W, H, [(0, (25, 194, 138)), (0.2, (190, 255, 150)), (0.4, (60, 230, 200)), (0.6, (18, 138, 99)), (0.8, (200, 255, 214)), (1, (25, 194, 138))], 0.9)
    fr = _blank()
    fd = ImageDraw.Draw(fr)
    fd.rounded_rectangle([50, 50, W - 50, H - 50], radius=40, outline=255, width=14)
    fd.rounded_rectangle([84, 84, W - 84, H - 84], radius=30, outline=255, width=3)
    _soft_shadow(im, fr, 0, 0, 14, 0.9, (25, 194, 138))
    im.paste(holo, (0, 0), fr)
    # ichki qorong‘i shisha
    card = _blank()
    ImageDraw.Draw(card).rounded_rectangle([96, 96, W - 96, H - 96], radius=26, fill=255)
    im.paste((3, 18, 14), (0, 0), card.point(lambda v: int(v * 0.74)))
    # mikro-matn (xavfsizlik chizig‘i)
    mt = _blank()
    f = font(11, True, False)
    unit = "ESSE AKADEMIYASI • "
    txt = unit * (int((W - 260) / tlen(f, unit)) + 1)
    while tlen(f, txt) > W - 260:
        txt = txt[:-1]
    ImageDraw.Draw(mt).text((130, 110), txt, font=f, fill=255)
    ImageDraw.Draw(mt).text((130, H - 124), txt, font=f, fill=255)
    _paint(im, mt, (120, 200, 170), alpha=0.5)
    # diagonal yaltirash
    sheen = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sheen).polygon([(W * 0.50, 0), (W * 0.64, 0), (W * 0.34, H), (W * 0.20, H)], fill=26)
    sheen = ImageChops.multiply(sheen.filter(ImageFilter.GaussianBlur(40)), card)
    im.paste((255, 255, 255), (0, 0), sheen)
    # laurellar
    _laurel(im, W // 2, 862, 134, (150, 232, 190, 235), -1)
    _laurel(im, W // 2, 862, 134, (150, 232, 190, 235), 1)
    # yulduzlar
    rnd = random.Random(P["code"])
    sp = ImageDraw.Draw(im, "RGBA")
    for _ in range(26):
        x, y = rnd.randint(130, W - 130), rnd.randint(130, H - 130)
        if 300 < x < W - 300 and 130 < y < H - 130:
            continue
        _sparkle(sp, x, y, rnd.randint(6, 14), (255, 255, 255, rnd.randint(90, 200)))

    def extrude(face, side, depth=5, glow_c=None):
        def f(im, m):
            if glow_c:
                _paint(im, m, glow_c, 0, 0, 16, 0.55)
            for k in range(depth, 0, -1):
                _paint(im, m, side, k, k)
            _paint_grad(im, m, face)
        return f

    def glow(c, g=None, r=10, a=0.65):
        def f(im, m):
            if g:
                _paint(im, m, g, 0, 0, r, a)
            _paint(im, m, c)
        return f
    goldf = [(0, (236, 255, 244)), (0.35, (150, 240, 196)), (0.65, (40, 170, 120)), (1, (196, 255, 224))]
    whitef = [(0, (255, 255, 255)), (0.5, (214, 250, 232)), (1, (150, 220, 190))]
    fx = {"brand": glow((196, 250, 224), GLOW, 8), "sub": glow((170, 255, 214), GLOW, 8, .5),
          "title": extrude(goldf, (4, 56, 40), 6, GLOW), "who": glow((150, 210, 186)), "name": extrude(whitef, (6, 70, 50), 4, GLOW),
          "sentence": glow((214, 244, 230)), "code": glow((170, 255, 214), GLOW, 6, .4), "note": glow((150, 210, 186)),
          "line": (120, 210, 170), "muted": (150, 210, 186)}
    y = layout(im, P, fx, None)

    def chip(im, x, y, w, h, a, b, big):
        m = _blank()
        ImageDraw.Draw(m).rounded_rectangle([x, y, x + w, y + h], radius=20, fill=255)
        _soft_shadow(im, m, 0, 0, 14, 0.8, GLOW if not big else MEDAL[P['rank']][1])
        dd = ImageDraw.Draw(im, "RGBA")
        if big:
            _hi, _ba, _lo = MEDAL[P['rank']]
            im.paste(_grad_d(w, h, [(0, _hi), (0.5, _ba), (1, _lo)], 0.5), (x, y), m.crop((x, y, x + w, y + h)))
            dd.rounded_rectangle([x + 5, y + 5, x + w - 5, y + h // 2], radius=15, fill=(255, 255, 255, 50))
        else:
            dd.rounded_rectangle([x, y, x + w, y + h], radius=20, fill=(255, 255, 255, 20), outline=(60, 220, 170, 210), width=3)
        _paint(im, _text_mask(x + w // 2, y + 16, a, font(17, True, False), tr=3), (70, 44, 6) if big else (160, 230, 200))
        _paint(im, _text_mask(x + w // 2, y + 48, b, font(40, True, True)), (40, 24, 0) if big else (255, 255, 255))
    chips(im, P, y, chip)
    footer(im, P, fx)
    halo = _blank()
    ImageDraw.Draw(halo).ellipse([W // 2 - 140, 866 - 140, W // 2 + 140, 866 + 140], fill=255)
    _paint(im, halo, MEDAL[P["rank"]][1], 0, 0, 38, 0.5)
    paste_medal(im, W // 2, 866, 80, P["rank"], extrude=7, ribbon=(18, 138, 99))
    return im


_FN = {"3D": style_3d, "4D": style_4d, "5D": style_5d, "6D": style_6d, "7D": style_7d}


def render(data, code, style=None):
    """PNG baytlari. style: '3D'..'7D' (bo‘sh bo‘lsa data['style'], keyin DEFAULT_STYLE)."""
    st = str(style or data.get("style") or DEFAULT_STYLE).upper()
    if st not in _FN:
        st = DEFAULT_STYLE
    with _RL:   # bir vaqtda bitta sertifikat chiziladi (xotira tejash — cert_design bilan bir xil qoida)
        im = _FN[st](_prep(data, code)).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        return buf.getvalue()


SAMPLE = {"name": "Dilnoza Karimova", "rank": 1, "award": "G‘azal bilimdoni", "testname": "G‘azal — 1-mavzu", "correct": 19, "total": 20,
          "date": "06.11.2026", "subject": "G‘azal"}
