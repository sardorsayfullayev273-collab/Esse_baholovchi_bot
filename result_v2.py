# -*- coding: utf-8 -*-
"""result_v2 (v116) — esse natijasi uchun yangi rasm albomi (haqiqiy ma'lumotlar bilan).

make_result_v2(data, total24, eq75, level, topic="", when=None, bot_username="", prev_total=None, percentile=None)
  -> [BytesIO(jpg), ...]   1) asosiy natija  2..n) batafsil tahlil (ball yo'qotilgan mezonlar + xatolar izohi bilan)
                           oxirida (oldingi ball bor bo'lsa) 3) «ball o'sdi» kartasi.
Hech narsa o'ylab topilmaydi: iqtiboslar, izohlar, xatolar AI natijasidan olinadi; foiz faqat yetarli ma'lumot bo'lsa chiqadi.
Brend: «Esse baholovchi bot» (rasmiy idora nomi ishlatilmaydi).
"""
import io, math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from result_cards import F as _F, clean, wrap as _wrap
from result_blue import NAMES, TIPS, WEAK, ERR_CRITERIA

S = 2
G1 = (8, 64, 47); G2 = (11, 90, 65); G3 = (18, 138, 99); GOLD = (245, 179, 1); GOLD2 = (250, 214, 110)
INK = (13, 43, 34); MUTE = (95, 122, 110); WHITE = (252, 253, 252); RED = (217, 83, 79); AMB = (224, 144, 47); GOOD = (26, 157, 109)
LIGHT = (190, 215, 203)
_DEJAVU = {}
_BOT = ["Esse_baholovchi_bot"]
SHORT = {1: "Uslub", 2: "Qarashlar", 3: "Dalillash", 4: "Tuzilma", 5: "Mantiq", 6: "Takror", 7: "Imlo", 8: "Punktuatsiya", 9: "Qo‘shimcha", 10: "So‘z qo‘llash", 11: "Leksika", 12: "Sheva"}
TAG = {7: "Imlo", 8: "Punktuatsiya", 9: "Qo‘shimcha", 10: "So‘z qo‘llash", 12: "Sheva/parazit"}


def _latin_ok(t):
    return all(ord(ch) < 0x250 or 0x2000 <= ord(ch) <= 0x206F for ch in str(t))


def font(size, w="r", text=""):
    if text and not _latin_ok(text):          # kirill/emoji bo'lsa Poppins o'rniga DejaVu (kvadratchalar chiqmasin)
        import os
        k = (size, w)
        if k not in _DEJAVU:
            for d in ("/usr/share/fonts/truetype/dejavu", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")):
                p = os.path.join(d, "DejaVuSans-Bold.ttf" if w == "b" else "DejaVuSans.ttf")
                if os.path.exists(p):
                    _DEJAVU[k] = ImageFont.truetype(p, size * S); break
            else:
                _DEJAVU[k] = _F(size * S, w)
        return _DEJAVU[k]
    return _F(size * S, w)


def fix(t):
    t = clean(t)
    return t.replace("\u2192", "->") if False else t


class Cv:
    def __init__(self, W, H, top, bot, dry=False):
        self.W, self.H, self.dry = W, H, dry
        if dry:
            self.im = Image.new("RGB", (4, 4)); self.d = ImageDraw.Draw(self.im); return
        g = Image.linear_gradient("L").resize((W * S, H * S)).transpose(Image.FLIP_TOP_BOTTOM)
        self.im = Image.composite(Image.new("RGB", (W * S, H * S), top), Image.new("RGB", (W * S, H * S), bot), g)
        self.d = ImageDraw.Draw(self.im)

    def _r(self): self.d = ImageDraw.Draw(self.im)

    def rr(self, box, r, fill=None, outline=None, w=1, shadow=0):
        if self.dry: return
        x0, y0, x1, y1 = [v * S for v in box]
        if shadow:
            sh = Image.new("RGBA", self.im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((x0, y0 + shadow * S * .6, x1, y1 + shadow * S * .6), radius=r * S, fill=(0, 0, 0, 80))
            sh = sh.filter(ImageFilter.GaussianBlur(shadow * S)); self.im.paste(sh, (0, 0), sh); self._r()
        self.d.rounded_rectangle((x0, y0, x1, y1), radius=r * S, fill=fill, outline=outline, width=w * S)

    def t(self, xy, text, size, w="r", fill=INK, anchor="la"):
        if self.dry: return
        text = fix(text); self.d.text((xy[0] * S, xy[1] * S), text, font=font(size, w, text), fill=fill, anchor=anchor)

    def tw(self, text, size, w="r"):
        text = fix(text); return self.d.textlength(text, font=font(size, w, text)) / S

    def lines(self, text, size, width, w="r", max_lines=None):
        text = fix(text); f = font(size, w, text)
        return _wrap(self.d, text, f, width * S, max_lines)

    def ell(self, box, fill=None, outline=None, w=1):
        if self.dry: return
        self.d.ellipse([v * S for v in box], fill=fill, outline=outline, width=w * S)

    def line(self, pts, fill, w=1):
        if self.dry: return
        self.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(w * S))

    def tri(self, cx, cy, sz, col):
        if self.dry: return
        self.d.polygon([(cx * S, (cy - sz) * S), ((cx - sz) * S, (cy + sz * .7) * S), ((cx + sz) * S, (cy + sz * .7) * S)], fill=col)

    def ring(self, cx, cy, R, frac, col, track, wd):
        if self.dry: return
        box = [(cx - R) * S, (cy - R) * S, (cx + R) * S, (cy + R) * S]
        self.d.arc(box, 0, 360, fill=track, width=wd * S)
        if frac > 0:
            self.d.arc(box, -90, -90 + 360 * min(frac, 1), fill=col, width=wd * S)
            for a in (-90, -90 + 360 * min(frac, 1)):
                x = cx + (R - wd / 2) * math.cos(math.radians(a)); y = cy + (R - wd / 2) * math.sin(math.radians(a))
                self.ell((x - wd / 2, y - wd / 2, x + wd / 2, y + wd / 2), fill=col)

    def pill(self, cx, cy, text, size, fg, bg, padx=26, h=None, w="b"):
        tw = self.tw(text, size, w); h = h or size + 22
        self.rr((cx - tw / 2 - padx, cy - h / 2, cx + tw / 2 + padx, cy + h / 2), h / 2, fill=bg); self.t((cx, cy), text, size, w, fg, "mm")

    def jpg(self):
        b = io.BytesIO(); self.im.resize((self.W, self.H), Image.LANCZOS).save(b, "JPEG", quality=92, optimize=True); b.seek(0); return b


def _rows(data):
    out = {}
    for it in data.get("scores") or []:
        try:
            out[int(it.get("criterion"))] = it
        except Exception:
            pass
    return out


def _score(it):
    try:
        return float(it.get("score", 0) or 0)
    except Exception:
        return 0.0


def _short(t, n):
    t = " ".join(str(t or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _first_example(it):
    for e in (it.get("examples") or []):
        if isinstance(e, dict):
            e = e.get("text") or e.get("quote") or e.get("example") or ""
        e = " ".join(str(e or "").split())
        if len(e) >= 6:
            return e
    return ""


def _header(c, right):
    c.ell((60, 58, 78, 76), fill=GOLD); c.t((92, 68), "ESSE BAHOLOVCHI BOT", 26, "b", WHITE, "lm")
    c.t((1020, 68), right, 22, "m", LIGHT, "rm")


def hero(data, total, eq75, level, when, percentile, prev_total):
    rows = _rows(data)
    lost = [(k, 2 - _score(v)) for k, v in sorted(rows.items()) if _score(v) < 2 - 1e-9]
    full = sum(1 for v in rows.values() if _score(v) >= 2 - 1e-9)
    c = Cv(1080, 1350, G3, (6, 48, 36))
    _header(c, (when or datetime.now()).strftime("%d.%m.%Y  •  %H:%M"))
    c.t((540, 150), "Esseingiz tekshirildi", 46, "b", WHITE, "mm"); c.t((540, 198), "12 ta mezon bo‘yicha AI tahlili", 26, "m", LIGHT, "mm")
    cx, cy = 540, 440
    c.ell((cx - 215, cy - 215, cx + 215, cy + 215), fill=(8, 66, 49)); c.ring(cx, cy, 192, total / 24.0, GOLD, (20, 100, 74), 28)
    c.t((cx, cy - 12), f"{total:g}", 132, "b", WHITE, "mm"); c.t((cx, cy + 74), "24 balldan", 28, "m", LIGHT, "mm")
    lv = _short(level, 18)
    lvl_txt = "Daraja: C dan past" if str(level).lower().startswith("sertifikat") else f"Daraja: {lv}"
    c.pill(cx - 150, 712, lvl_txt, 30, INK, GOLD2); c.pill(cx + 170, 712, f"{eq75} / 75 ball", 30, WHITE, (14, 100, 72))
    c.rr((60, 770, 1020, 850), 40, fill=(10, 76, 56), outline=(30, 120, 90), w=2)
    if prev_total is not None and total > prev_total + 1e-9:
        c.t((540, 810), f"Oldingi esseingizdan +{total - prev_total:g} ball yuqori", 29, "b", GOLD2, "mm")
    elif percentile is not None:
        c.t((540, 810), f"Siz bot foydalanuvchilarining {int(percentile)}% idan yuqorisiz", 29, "b", GOLD2, "mm")
    else:
        c.t((540, 810), f"{full} ta mezonda to‘liq ball (2/2)", 29, "b", GOLD2, "mm")
    gap = round(24 - total, 1)
    c.rr((60, 880, 1020, 1030), 34, fill=WHITE, shadow=14)
    if lost:
        c.t((96, 918), f"To‘liq ballga {gap:g} ball qoldi", 32, "b", INK, "lm"); c.t((984, 918), f"{total:g} dan 24 gacha", 26, "b", MUTE, "rm")
        c.rr((96, 950, 984, 972), 11, fill=(222, 235, 228)); c.rr((96, 950, 96 + 888 * min(total, 24) / 24, 972), 11, fill=G3)
        chips = lost[:3]; cw = 888 / max(1, len(chips)) - 12
        for i, (k, d) in enumerate(chips):
            x = 96 + i * (cw + 12); nm = SHORT.get(k, str(k))
            c.rr((x, 990, x + cw, 1022), 16, fill=(253, 236, 200)); c.t((x + cw / 2, 1006), f"{nm} +{d:g}", 19, "b", (150, 95, 0), "mm")
    else:
        c.t((540, 955), "Mukammal natija — hamma mezonda to‘liq ball!", 32, "b", G2, "mm")
    c.rr((60, 1060, 530, 1190), 30, fill=(231, 246, 238)); c.t((90, 1096), "Kuchli tomon", 21, "m", G2, "lm")
    c.t((90, 1136), f"{full} ta mezonda 2/2", 30, "b", INK, "lm"); c.t((90, 1168), "to‘liq ball olingan", 22, "m", MUTE, "lm")
    c.rr((550, 1060, 1020, 1190), 30, fill=(253, 240, 214)); c.t((580, 1096), "O‘sish zonasi", 21, "m", (150, 95, 0), "lm")
    if lost:
        names = " • ".join(SHORT.get(k, "") for k, _ in lost[:3]) + (f" +{len(lost) - 3}" if len(lost) > 3 else "")
        c.t((580, 1136), names, 25, "b", INK, "lm"); c.t((580, 1168), f"{len(lost)} ta mezon 2/2 dan past", 22, "m", MUTE, "lm")
    else:
        c.t((580, 1136), "Yo‘q", 30, "b", INK, "lm")
    c.rr((60, 1218, 1020, 1296), 39, fill=GOLD, shadow=10)
    if lost:
        c.t((540, 1250), "Tuzatib qayta yuboring — o‘sishni ko‘rsatamiz", 30, "b", INK, "mm"); c.t((540, 1281), f"Oldin: {total:g}   •   Hozir: ?", 22, "m", (110, 75, 0), "mm")
    else:
        c.t((540, 1257), "Ajoyib! Yangi mavzuda ham sinab ko‘ring", 30, "b", INK, "mm")
    c.t((540, 1326), "AI natijasi rasmiy hujjat emas • @" + _BOT[0], 20, "m", (160, 190, 176), "mm")
    return c


# ---------------- batafsil tahlil: bloklar -> sahifalar ----------------
def _lost_block(c, y, k, it, dry):
    sc = _score(it); name = NAMES.get(k, str(k)); h = 70
    quote = _first_example(it); reason = " ".join(str(it.get("reason") or "").split()); tip = TIPS.get(k, "")
    ql = c.lines("“" + _short(quote, 140) + "”", 24, 840, "m", 2) if quote else []
    rl = c.lines(_short(reason or WEAK.get(k, ""), 220), 24, 840, "m", 3)
    tl = c.lines(_short(tip, 160), 24, 840, "m", 2) if tip else []
    h = 82 + (54 + len(ql) * 32 if ql else 0) + (54 + len(rl) * 32) + (54 + len(tl) * 32 if tl else 0) + 6
    if dry: return h
    c.rr((60, y, 1020, y + h), 32, fill=WHITE, shadow=10)
    c.ell((90, y + 20, 140, y + 70), fill=G2); c.t((115, y + 45), str(k), 24, "b", WHITE, "mm")
    c.t((158, y + 45), name, 30, "b", INK, "lm"); c.pill(930, y + 45, f"{sc:g} / 2", 24, (150, 95, 0), (253, 236, 200), padx=20, h=42)
    yy = y + 82
    if ql:
        c.t((90, yy), "Esseingizdan:", 20, "m", MUTE, "la"); yy += 28
        c.rr((90, yy, 990, yy + 12 + len(ql) * 32), 16, fill=(253, 238, 236)); c.rr((90, yy, 97, yy + 12 + len(ql) * 32), 4, fill=RED)
        for i, ln in enumerate(ql): c.t((116, yy + 6 + i * 32 + 16), ln, 24, "m", INK, "lm")
        yy += 12 + len(ql) * 32 + 14
    c.t((90, yy), "Nima uchun ball ketdi:", 20, "m", MUTE, "la"); yy += 28
    c.rr((90, yy, 990, yy + 12 + len(rl) * 32), 16, fill=(246, 244, 236))
    for i, ln in enumerate(rl): c.t((116, yy + 6 + i * 32 + 16), ln, 24, "m", INK, "lm")
    yy += 12 + len(rl) * 32 + 14
    if tl:
        c.t((90, yy), "Qanday tuzatish:", 20, "m", MUTE, "la"); yy += 28
        c.rr((90, yy, 990, yy + 12 + len(tl) * 32), 16, fill=(231, 246, 238)); c.rr((90, yy, 97, yy + 12 + len(tl) * 32), 4, fill=GOOD)
        for i, ln in enumerate(tl): c.t((116, yy + 6 + i * 32 + 16), ln, 24, "m", INK, "lm")
    return h


def _fit(c, text, size, w, maxw):
    text = " ".join(str(text or "").split())
    while text and c.tw(text, size, w) > maxw:
        text = text[:-2].rstrip() + "…"
        if len(text) < 4: break
    return text


def _err_block(c, y, k, e, dry):
    wrong = _fit(c, e.get("wrong", ""), 30, "m", 690); right = _fit(c, e.get("correct", ""), 32, "b", 610); ex = " ".join(str(e.get("explanation") or "").split())
    el = c.lines(_short(ex, 200), 22, 880, "r", 3) if ex else []
    x = 292; ww = c.tw(wrong or "—", 30, "m"); rw = c.tw(right, 32, "b") if right else 0
    stack = bool(right) and (x + ww + 22 + 34 + 20 + rw > 996)
    ex_y = 84 + (46 if stack else 0)
    h = ex_y + (len(el) * 30 + 18 if el else 0) + 10
    if dry: return h
    c.rr((60, y, 1020, y + h), 26, fill=WHITE, shadow=8)
    c.pill(170, y + 42, TAG.get(k, "Xato"), 20, G2, (227, 241, 234), padx=18, h=38)
    c.t((x, y + 42), wrong or "—", 30, "m", RED, "lm"); c.line([(x, y + 43), (x + ww, y + 43)], RED, 3)
    if right:
        if stack: ax, ay = x, y + 88
        else: ax, ay = x + ww + 22, y + 42
        c.line([(ax, ay), (ax + 34, ay)], MUTE, 4); c.line([(ax + 22, ay - 11), (ax + 34, ay), (ax + 22, ay + 11)], MUTE, 4)
        c.t((ax + 54, ay), right, 32, "b", GOOD, "lm")
    for i, ln in enumerate(el): c.t((96, y + ex_y + i * 30 + 6), ln, 22, "r", MUTE, "lm")
    return h


def _pages(data):
    """[(blocks), ...] — har sahifa uchun (tur, kalit, obyekt) bloklari."""
    rows = _rows(data); blocks = []
    for k, it in sorted(rows.items()):
        if _score(it) < 2 - 1e-9:
            blocks.append(("lost", k, it))
    errs = []
    for k in ERR_CRITERIA:
        for e in (rows.get(k, {}).get("errors") or []):
            if isinstance(e, dict) and (e.get("wrong") or e.get("correct")):
                errs.append(("err", k, e))
    probe = Cv(1080, 10, G1, G1, dry=True)
    MAXH = 1560; pages = []; cur = []; used = 0
    def flush():
        nonlocal cur, used
        if cur: pages.append(cur); cur = []; used = 0
    first_err = True
    for b in blocks + errs:
        if b[0] == "err" and first_err:
            first_err = False; used += 70; cur.append(("title", 0, "Xatolar va to‘g‘ri variantlari"))
        h = (_lost_block(probe, 0, b[1], b[2], True) if b[0] == "lost" else _err_block(probe, 0, b[1], b[2], True)) + 22
        if b[0] == "lost" and not any(x[0] == "lost" for x in cur) and not cur: used += 70; cur.append(("title", 0, "Ball qayerda yo‘qoldi"))
        if used + h > MAXH: flush()
        if b[0] == "err" and not cur: cur.append(("title", 0, "Xatolar (davomi)")); used += 70
        cur.append(b); used += h
    flush()
    return pages


def detail_pages(data, total, max_pages=3):
    out = []
    pages = _pages(data)[:max_pages]
    probe = Cv(1080, 10, G1, G1, dry=True); n = len(pages)
    for pi, blocks in enumerate(pages, 1):
        H = 140 + 30
        for b in blocks:
            H += 70 if b[0] == "title" else (_lost_block(probe, 0, b[1], b[2], True) if b[0] == "lost" else _err_block(probe, 0, b[1], b[2], True)) + 22
        H += 90
        c = Cv(1080, H, (246, 251, 248), (228, 241, 234))
        c.rr((0, 0, 1080, 140), 0, fill=G1); c.ell((60, 56, 78, 74), fill=GOLD); c.t((92, 66), "ESSE BAHOLOVCHI BOT", 26, "b", WHITE, "lm")
        c.t((1020, 66), f"Batafsil tahlil  {pi}/{n}", 22, "m", LIGHT, "rm")
        y = 170
        for b in blocks:
            if b[0] == "title":
                c.t((60, y + 28), b[2], 40, "b", INK, "lm"); y += 70
            elif b[0] == "lost":
                y += _lost_block(c, y, b[1], b[2], False) + 22
            else:
                y += _err_block(c, y, b[1], b[2], False) + 22
        c.t((540, H - 40), "AI natijasi rasmiy hujjat emas; ekspert bahosidan biroz farq qilishi mumkin • @" + _BOT[0], 19, "m", MUTE, "mm")
        out.append(c)
    return out


def growth(data, total, prev_total, prev_rows, when):
    rows = _rows(data); c = Cv(1080, 1350, G3, (6, 48, 36)); diff = round(total - prev_total, 1)
    _header(c, "Qayta tekshiruv")
    c.t((540, 150), "Ball o‘sdi!", 58, "b", GOLD2, "mm"); c.t((540, 205), "Tuzatilgan esse oldingi natija bilan taqqoslandi", 25, "m", LIGHT, "mm")
    cx, cy = 540, 440
    c.ell((cx - 215, cy - 215, cx + 215, cy + 215), fill=(8, 66, 49)); c.ring(cx, cy, 192, total / 24.0, GOLD, (20, 100, 74), 28)
    c.t((cx, cy - 12), f"{total:g}", 132, "b", WHITE, "mm"); c.t((cx, cy + 74), f"oldin {prev_total:g}", 28, "m", LIGHT, "mm")
    c.pill(540, 712, f"+{diff:g} ball", 34, WHITE, GOOD)
    changes = []
    for k in sorted(rows):
        a = _score(prev_rows.get(k, {})) if prev_rows.get(k) else None; b = _score(rows[k])
        if a is not None and abs(a - b) > 1e-9: changes.append((k, a, b))
    changes.sort(key=lambda x: -(x[2] - x[1]))
    shown = changes[:4]
    c.rr((60, 780, 1020, 780 + 70 + max(1, len(shown)) * 72), 34, fill=WHITE, shadow=14)
    c.t((96, 815), "Mezonlar bo‘yicha o‘zgarish", 24, "b", MUTE, "lm")
    for i, (k, a, b) in enumerate(shown):
        y = 870 + i * 72; col = GOOD if b > a else RED
        c.t((96, y), _short(NAMES.get(k, ""), 26), 28, "m", INK, "lm"); c.t((690, y), f"{a:g}", 28, "m", MUTE, "rm")
        c.line([(710, y), (750, y)], MUTE, 4); c.line([(738, y - 10), (750, y), (738, y + 10)], MUTE, 4); c.t((830, y), f"{b:g}", 32, "b", col, "rm")
        c.tri(900, y, 14, col) if b > a else c.rr((884, y - 3, 916, y + 3), 3, fill=col)
    if not shown:
        c.t((96, 886), "Mezon ballari o‘zgarmadi, lekin jami ball oshdi", 26, "m", INK, "lm")
    lost = [(k, 2 - _score(v)) for k, v in sorted(rows.items()) if _score(v) < 2 - 1e-9]
    ytxt = 780 + 70 + max(1, len(shown)) * 72 + 52
    if lost:
        k0 = max(lost, key=lambda x: x[1])[0]
        c.t((540, ytxt), f"To‘liq ballgacha {24 - total:g} ball qoldi: {_short(NAMES.get(k0, ''), 24)}", 26, "b", WHITE, "mm")
    c.rr((60, 1204, 1020, 1286), 41, fill=GOLD, shadow=10); c.t((540, 1245), "Yana bir marta tuzatib ko‘rish" if lost else "Mukammal! Yangi mavzuni sinang", 32, "b", INK, "mm")
    c.t((540, 1326), "AI natijasi rasmiy hujjat emas • @" + _BOT[0], 20, "m", (160, 190, 176), "mm")
    return c


def make_result_v2(data, total24, eq75, level, topic="", when=None, bot_username="", prev_total=None, prev_data=None, percentile=None, max_detail_pages=3):
    _BOT[0] = (bot_username or "Esse_baholovchi_bot").lstrip("@")
    total = float(total24)
    cvs = [hero(data, total, eq75, level, when, percentile, prev_total)]
    cvs += detail_pages(data, total, max_detail_pages)
    if prev_total is not None and prev_data is not None and total > float(prev_total) + 1e-9:
        cvs.append(growth(data, total, float(prev_total), _rows(prev_data), when))
    outs = []
    for i, c in enumerate(cvs, 1):
        b = c.jpg(); b.name = f"esse_{i}.jpg"; outs.append(b)
    return outs
