# -*- coding: utf-8 -*-
"""Esse natijasi — ko'k-yashil "natija varaqasi" (namuna #4 uslubida), bot hisobiga mos.

make_result_blue(data, total24, eq75, level, user_name="", topic="", when=None, bot_username="") -> BytesIO (JPEG)
Eslatma: bu rasmiy hujjat emas — vazirlik/BBA nomi, gerbi va "Milliy sertifikat" yozuvi ATAYLAB ishlatilmagan.
"""
import io
import datetime
from PIL import Image, ImageDraw

from result_cards import F, clean, wrap

ERR_CRITERIA = (7, 8, 9, 10, 12)
TIPS = {
    1: "Publitsistik uslubda yozing: sodda, aniq gaplar, badiiy bezaksiz.",
    2: "Ikkala qarashni ham kamida 2 tadan sabab bilan yoriting.",
    3: "Dalil formulasi: fikr › misol › xulosa. Statistika, tadqiqot yoki asardan misol keltiring.",
    4: "Kirish, asosiy qism va xulosa bo‘lsin; xulosada bitta qarashni aniq tanlang.",
    5: "Abzaslarni bog‘lovchi so‘zlar bilan ulang; har abzas bitta fikrni ochsin.",
    6: "Bir xil so‘z va fikrni takrorlamang; mavzudan chetga chiqmang.",
    7: "Shubhali so‘zlarning imlosini yozishdan oldin lug‘atdan tekshiring.",
    8: "Bog‘lovchi va kiritma so‘zlar atrofida vergul qoidalarini takrorlang.",
    9: "Kelishik va egalik qo‘shimchalarini gap oxirida qayta o‘qib tekshiring.",
    10: "So‘z ma’nosiga ishonchingiz komil bo‘lmasa, uni aniqroq so‘z bilan almashtiring.",
    11: "Takrorlangan so‘zlarni sinonim, ibora yoki termin bilan almashtiring.",
    12: "Sheva, so‘kish va parazit so‘zlardan saqlaning.",
}


def collect_errors(data):
    """[(mezon, xato_dict), ...] — 7, 8, 9, 10, 12-mezonlar bo'yicha."""
    rows = {}
    for it in data.get("scores") or []:
        try:
            rows[int(it.get("criterion"))] = it
        except Exception:
            pass
    out = []
    for c in ERR_CRITERIA:
        for e in rows.get(c, {}).get("errors") or []:
            if isinstance(e, dict) and (e.get("wrong") or e.get("correct")):
                out.append((c, e))
    return out


GROUPS = [(7, "📝 Imlo"), (8, "✏️ Punktuatsiya"), (9, "🔤 Qo‘shimcha qo‘llash"),
          (10, "💬 So‘z qo‘llash"), (12, "🚫 Sheva / parazit so‘zlar")]


def errors_text_chunks(data, limit=3800):
    """Barcha xatolar — mezonlar bo'yicha guruhlangan yozma xabar(lar). Xato bo'lmasa []."""
    by = {}
    for c, e in collect_errors(data):
        by.setdefault(c, []).append(e)
    total = sum(len(v) for v in by.values())
    if not total:
        return []
    lines = [f"❌ XATOLAR ({total} ta)", ""]
    for c, title in GROUPS:
        errs = by.get(c)
        if not errs:
            continue
        lines.append(f"{title} ({len(errs)} ta)")
        for i, e in enumerate(errs, 1):
            w, r = str(e.get("wrong", "")).strip(), str(e.get("correct", "")).strip()
            lines.append(f"{i}. {w} → {r}" if r else f"{i}. {w}")
            ex = str(e.get("explanation", "")).strip()
            if ex:
                lines.append(f"   Izoh: {ex}")
        lines.append("")
    chunks, cur = [], ""
    for ln in lines:
        while len(ln) > limit:           # juda uzun bitta qator
            if cur:
                chunks.append(cur.rstrip()); cur = ""
            chunks.append(ln[:limit]); ln = ln[limit:]
        if len(cur) + len(ln) + 1 > limit:
            chunks.append(cur.rstrip()); cur = ""
        cur += ln + "\n"
    if cur.strip():
        chunks.append(cur.rstrip())
    return chunks

W = 1080
M = 44
NAVY = (14, 40, 100)
NAVY2 = (30, 78, 160)
INK = (20, 38, 78)
MUTE = (92, 106, 130)
SKY = (232, 243, 253)
CARD = (255, 255, 255)
LINE = (203, 220, 238)
GREEN = (24, 150, 92)
GREEN_L = (226, 245, 236)
GOLD = (212, 165, 60)
GOLD_L = (253, 243, 214)
RED = (200, 62, 52)
RED_L = (253, 236, 233)
AMBER = (214, 140, 30)

NAMES = {1: "Publitsistik uslub", 2: "Ikkala qarash", 3: "Dalillar bilan asoslash", 4: "Esse tuzilmasi",
         5: "Mantiqiy qurilish", 6: "Izchillik va takror", 7: "Imlo", 8: "Punktuatsiya",
         9: "Qo‘shimcha qo‘llash", 10: "So‘z qo‘llash", 11: "Leksik xilma-xillik", 12: "Sheva va parazit so‘zlar"}
WEAK = {1: "Uslub to‘liq publitsistik emas", 2: "Qarashlar yetarlicha yoritilmagan",
        3: "Dalillar yetarlicha aniq emas", 4: "Esse tuzilmasida kamchilik bor",
        5: "Mantiqiy bog‘lanishda uzilishlar bor", 6: "Fikr takrorlari uchraydi",
        7: "Imlo xatolari", 8: "Punktuatsiya xatolari", 9: "Qo‘shimcha xatolari",
        10: "So‘z qo‘llashda noaniqlik", 11: "Leksik xilma-xillik yetarli emas",
        12: "Sheva yoki parazit so‘zlar bor"}
QUOTE = "Yozgan har bir esse — fikr va imkoniyatlaringiz aksidir!"


def _sc_col(s):
    return GREEN if s >= 1.75 else AMBER if s >= 1 else RED


def _grad(w, h, a, b, vertical=True):
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    n = h if vertical else w
    for i in range(n):
        k = i / max(1, n - 1)
        c = tuple(int(a[j] * (1 - k) + b[j] * k) for j in range(3))
        d.line((0, i, w, i) if vertical else (i, 0, i, h), fill=c)
    return im


def _icon(d, kind, x, y, col):
    """24 px belgi: user | calendar | doc (oddiy chizma)."""
    if kind == "user":
        d.ellipse((x + 7, y, x + 21, y + 14), outline=col, width=3)
        d.arc((x, y + 14, x + 28, y + 42), 180, 360, fill=col, width=3)
    elif kind == "cal":
        d.rounded_rectangle((x, y + 4, x + 28, y + 32), radius=5, outline=col, width=3)
        d.line((x, y + 14, x + 28, y + 14), fill=col, width=3)
        d.line((x + 8, y, x + 8, y + 8), fill=col, width=3)
        d.line((x + 20, y, x + 20, y + 8), fill=col, width=3)
    else:
        d.rounded_rectangle((x + 2, y, x + 26, y + 32), radius=4, outline=col, width=3)
        d.line((x + 8, y + 12, x + 20, y + 12), fill=col, width=3)
        d.line((x + 8, y + 20, x + 20, y + 20), fill=col, width=3)


def _bullets(d, x, y, w, items, font, fill, dot, gap=10, maxl=3):
    for it in items:
        ls = wrap(d, it, font, w - 26, maxl)
        d.ellipse((x, y + 11, x + 9, y + 20), fill=dot)
        for ln in ls:
            d.text((x + 24, y), ln, font=font, fill=fill)
            y += 30
        y += gap
    return y


def _height_bullets(d, w, items, font, gap=10, maxl=3):
    return sum(len(wrap(d, it, font, w - 26, maxl)) * 30 + gap for it in items)


def make_result_blue(data, total24, eq75, level, user_name="", topic="", when=None, bot_username=""):
    total = float(total24)
    user = str(bot_username or "").lstrip("@")
    when = when or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5)))
    by = {}
    for it in data.get("scores") or []:
        try:
            by[int(it.get("criterion"))] = it
        except Exception:
            pass

    def sc(c):
        try:
            return float(by.get(c, {}).get("score", 0) or 0)
        except Exception:
            return 0.0

    special = str(data.get("status", "")) == "special_case"
    img = Image.new("RGB", (W, 5000), SKY)
    img.paste(_grad(W, 5000, (247, 251, 255), (226, 240, 252)), (0, 0))
    d = ImageDraw.Draw(img)

    # ---- yuqori lenta
    band = _grad(W, 150, NAVY, NAVY2, vertical=False)
    img.paste(band, (0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 150, W, 156), fill=GOLD)
    d.text((M, 36), "ESSE BAHOLOVCHI BOT", font=F(40, "b"), fill=(255, 255, 255))
    d.text((M, 92), "Sun’iy intellekt bilan esse baholash", font=F(24), fill=(206, 222, 246))
    if user:
        d.text((W - M, 62), f"@{user}", font=F(28, "m"), fill=(255, 226, 150), anchor="rm")

    # ---- sarlavha
    d.text((W // 2, 218), "ESSE BAHOLASH NATIJASI", font=F(52, "b"), fill=NAVY, anchor="mm")
    sub = wrap(d, "Sizning yozgan essengiz BBA mezonlari asosida sun’iy intellekt tomonidan tekshirildi",
               F(24), W - 2 * M, 2)
    for i, ln in enumerate(sub):
        d.text((W // 2, 268 + i * 32), ln, font=F(24), fill=MUTE, anchor="mm")
    y = 268 + len(sub) * 32 + 26

    # ---- ma'lumot kartasi + medal
    cw = W - 2 * M
    tl = wrap(d, topic or "—", F(24, "m"), cw - 330, 2)
    ch = 150 + max(0, len(tl) - 1) * 30
    d.rounded_rectangle((M, y, M + cw, y + ch), radius=26, fill=CARD, outline=LINE, width=2)
    rows = [("user", "Foydalanuvchi:", clean(user_name or "—")),
            ("cal", "Tekshirish sanasi:", when.strftime("%d.%m.%Y   |   %H:%M")),
            ("doc", "Esse mavzusi:", None)]
    ry = y + 22
    for kind, lab, val in rows:
        _icon(d, kind, M + 26, ry - 2, NAVY2)
        d.text((M + 78, ry + 2), lab, font=F(22), fill=MUTE)
        if val is not None:
            d.text((M + 78 + 250, ry), wrap(d, val, F(26, "b"), cw - 340, 1)[0], font=F(26, "b"), fill=INK)
            ry += 44
        else:
            for ln in tl:
                d.text((M + 78 + 250, ry), ln, font=F(24, "m"), fill=INK)
                ry += 30
    y += ch + 28

    # ---- ball qutilari
    bh = 210
    lw = 470
    box = _grad(lw, bh, NAVY, NAVY2, vertical=False)
    mask = Image.new("L", (lw, bh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, lw, bh), radius=28, fill=255)
    img.paste(box, (M, y), mask)
    d = ImageDraw.Draw(img)
    d.text((M + 30, y + 26), "BBA bo‘yicha olingan ball (24)", font=F(24, "m"), fill=(214, 228, 250))
    d.text((M + 30, y + 150), f"{total:.1f}", font=F(104, "b"), fill=(255, 255, 255), anchor="ls")
    nw = d.textlength(f"{total:.1f}", font=F(104, "b"))
    d.text((M + 30 + nw + 10, y + 150), "/ 24", font=F(44, "m"), fill=(214, 228, 250), anchor="ls")
    x2 = M + lw + 22
    d.rounded_rectangle((x2, y, W - M, y + bh), radius=28, fill=CARD, outline=GREEN, width=3)
    d.text((x2 + 30, y + 26), "75 ballik tizimda", font=F(26, "b"), fill=INK)
    d.text((x2 + 30, y + 150), str(int(eq75)), font=F(100, "b"), fill=GREEN, anchor="ls")
    ew = d.textlength(str(int(eq75)), font=F(100, "b"))
    d.text((x2 + 30 + ew + 10, y + 150), "/ 75", font=F(44, "m"), fill=MUTE, anchor="ls")
    lv = clean(str(level or "—"))
    lvtxt = f"Daraja: {lv}" if lv in ("A+", "A", "B+", "B", "C+", "C") else "Daraja: C dan past"
    pw = int(d.textlength(lvtxt, font=F(24, "b"))) + 36
    d.rounded_rectangle((W - M - 28 - pw, y + 26, W - M - 28, y + 70), radius=22, fill=GOLD_L, outline=GOLD, width=2)
    d.text((W - M - 28 - pw / 2, y + 48), lvtxt, font=F(24, "b"), fill=(120, 84, 14), anchor="mm")
    d.text((x2 + 30, y + 176), "taxminiy ekvivalent", font=F(20), fill=MUTE)
    y += bh + 28

    # ---- jadval (chap) + kartalar (o'ng)
    tx0, tw = M, 590
    rx0 = M + tw + 22
    rw = W - M - rx0
    ty = y
    if special:
        reason = str(data.get("special_reason") or "Esse baholashga yaroqsiz.")
        ls = wrap(d, reason, F(26), W - 2 * M - 80, 4)
        hh = 110 + len(ls) * 38
        d.rounded_rectangle((M, y, W - M, y + hh), radius=28, fill=GOLD_L, outline=GOLD, width=2)
        d.text((M + 36, y + 28), "Maxsus holat", font=F(32, "b"), fill=(120, 84, 14))
        for i, ln in enumerate(ls):
            d.text((M + 36, y + 80 + i * 38), ln, font=F(26), fill=INK)
        y += hh + 30
    else:
        d.rounded_rectangle((tx0, ty, tx0 + tw, ty + 64), radius=18, fill=NAVY)
        d.text((tx0 + 24, ty + 32), "Baholash mezonlari", font=F(24, "b"), fill=(255, 255, 255), anchor="lm")
        d.text((tx0 + 400, ty + 32), "Maks.", font=F(22, "b"), fill=(255, 255, 255), anchor="mm")
        d.text((tx0 + 508, ty + 32), "Sizning", font=F(22, "b"), fill=(255, 255, 255), anchor="mm")
        ty += 64
        rh = 52
        d.rectangle((tx0, ty, tx0 + tw, ty + rh * 12 + 60), fill=CARD, outline=LINE, width=2)
        for c in range(1, 13):
            ry = ty + (c - 1) * rh
            if c % 2 == 0:
                d.rectangle((tx0 + 2, ry, tx0 + tw - 2, ry + rh), fill=(244, 249, 254))
            d.ellipse((tx0 + 16, ry + 11, tx0 + 46, ry + 41), fill=SKY, outline=NAVY2, width=2)
            d.text((tx0 + 31, ry + 26), str(c), font=F(18, "b"), fill=NAVY, anchor="mm")
            d.text((tx0 + 62, ry + 26), clean(NAMES[c]), font=F(22, "m"), fill=INK, anchor="lm")
            d.text((tx0 + 400, ry + 26), "2", font=F(22), fill=MUTE, anchor="mm")
            s = sc(c)
            d.text((tx0 + 508, ry + 26), f"{s:.1f}", font=F(24, "b"), fill=_sc_col(s), anchor="mm")
        jy = ty + rh * 12
        d.rectangle((tx0 + 2, jy, tx0 + tw - 2, jy + 60), fill=(224, 236, 250))
        d.text((tx0 + 24, jy + 30), "Jami", font=F(26, "b"), fill=NAVY, anchor="lm")
        d.text((tx0 + 400, jy + 30), "24", font=F(26, "b"), fill=NAVY, anchor="mm")
        d.text((tx0 + 508, jy + 30), f"{total:.1f}", font=F(26, "b"), fill=NAVY, anchor="mm")
        table_end = jy + 60

        # kamchiliklar
        errs = {}
        for c, e in collect_errors(data):
            errs[c] = errs.get(c, 0) + 1
        weak = sorted([c for c in range(1, 13) if sc(c) < 2], key=lambda c: (sc(c), c))[:3]
        defects = []
        for c in weak:
            n = errs.get(c) or int(by.get(c, {}).get("error_count", 0) or 0)
            defects.append(f"{WEAK[c]}: {n} ta" if c in (7, 8, 9, 10) and n else WEAK[c])
        if not defects:
            defects = ["Jiddiy kamchilik aniqlanmadi"]
        recs = [str(x) for x in (data.get("improvements") or []) if str(x).strip()][:3]
        if not recs:
            recs = [TIPS[c] for c in weak[:3]] or ["Shu darajani yangi mavzularda ham saqlang."]
        f22 = F(22)
        h1 = 70 + _height_bullets(d, rw - 40, defects, f22, 8, 3) + 14
        h2 = 70 + _height_bullets(d, rw - 40, recs, f22, 8, 6) + 14
        gap = 18
        # o'ng ustun jadval balandligiga sig'sin: kerak bo'lsa balandlik oshadi
        d.rounded_rectangle((rx0, y, rx0 + rw, y + h1), radius=24, fill=RED_L, outline=(240, 200, 194), width=2)
        d.ellipse((rx0 + 20, y + 20, rx0 + 54, y + 54), fill=RED)
        d.text((rx0 + 37, y + 37), "!", font=F(24, "b"), fill=(255, 255, 255), anchor="mm")
        d.text((rx0 + 66, y + 22), "Asosiy kamchiliklar", font=F(24, "b"), fill=INK)
        _bullets(d, rx0 + 20, y + 70, rw - 40, defects, f22, INK, RED, 8, 3)
        y2 = y + h1 + gap
        d.rounded_rectangle((rx0, y2, rx0 + rw, y2 + h2), radius=24, fill=GREEN_L, outline=(190, 230, 208), width=2)
        d.ellipse((rx0 + 20, y2 + 20, rx0 + 54, y2 + 54), fill=GREEN)
        d.line([(rx0 + 28, y2 + 38), (rx0 + 35, y2 + 45), (rx0 + 47, y2 + 29)], fill=(255, 255, 255), width=4, joint="curve")
        d.text((rx0 + 66, y2 + 22), "Tavsiyalar", font=F(24, "b"), fill=INK)
        _bullets(d, rx0 + 20, y2 + 70, rw - 40, recs, f22, INK, GREEN, 8, 6)
        y = max(table_end, y2 + h2) + 34
        if len(collect_errors(data)):
            note = f"Barcha xatolar ({len(collect_errors(data))} ta) rasm ortidagi xabarda yuboriladi."
            d.text((W // 2, y), note, font=F(24, "m"), fill=NAVY2, anchor="mm")
            y += 50

    # ---- pastki qism: to'lqin, kitoblar, iqtibos
    fh = 340
    foot = Image.new("RGB", (W, fh), (226, 240, 252))
    fd = ImageDraw.Draw(foot)
    fd.polygon([(0, 150), (300, 120), (700, 190), (W, 130), (W, fh), (0, fh)], fill=(150, 214, 178))
    fd.polygon([(0, 200), (350, 170), (760, 230), (W, 180), (W, fh), (0, fh)], fill=GREEN)
    fd.polygon([(0, 226), (400, 206), (800, 240), (W, 212), (W, fh), (0, fh)], fill=NAVY)
    # kitoblar
    for i, (cx, cw2, col) in enumerate(((W - 250, 170, (255, 255, 255)), (W - 236, 140, (212, 165, 60)), (W - 258, 150, (30, 78, 160)))):
        by0 = 186 - i * 24
        fd.rounded_rectangle((cx, by0, cx + cw2, by0 + 20), radius=5, fill=col)
        fd.line((cx + 12, by0 + 6, cx + cw2 - 12, by0 + 6), fill=(255, 255, 255), width=2)
    img.paste(foot, (0, y))
    d = ImageDraw.Draw(img)
    qs = wrap(d, "“" + QUOTE + "”", F(28, "m"), W - 2 * M - 360, 2)
    for i, ln in enumerate(qs):
        d.text((W // 2 - 90, y + 40 + i * 40), ln, font=F(28, "m"), fill=NAVY, anchor="mm")
    d.text((W // 2, y + 262), clean("Esse baholovchi bot" + (f"  •  @{user}" if user else "")), font=F(26, "b"), fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, y + 304), "Sun’iy intellekt natijasi — rasmiy hujjat emas; ekspert bahosidan biroz farq qilishi mumkin.",
           font=F(20), fill=(206, 222, 246), anchor="mm")
    y += fh
    img = img.crop((0, 0, W, y))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=90, optimize=True)
    out.seek(0)
    out.name = "esse_natijasi.jpg"
    return out
