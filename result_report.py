# -*- coding: utf-8 -*-
"""Esse natijasi — premium "hisobot" rasmi (medal, radar, vazifalar, Bilasizmi?, ...).

Ishlatish:
    make_result_report(data, total24, eq75, topic=None, bot_username="", ref_bonus=1) -> BytesIO (JPEG)
Telefon uchun bitta uzun rasm (1080 px eni). Matn hech qachon ustma-ust tushmaydi: balandlik dinamik.
"""
import io
import math
import datetime
from PIL import Image, ImageDraw

from result_cards import F, clean, wrap

W = 1080
M = 56            # tashqi chekka
CW = W - 2 * M    # karta eni

# ---- ranglar
BG = (233, 244, 237)
GREEN_D = (20, 70, 48)
GREEN = (27, 126, 83)
GREEN_L = (60, 160, 112)
PALE = (221, 240, 229)
GOLD = (222, 170, 60)
GOLD_D = (160, 112, 24)
CREAM = (255, 247, 222)
WHITE = (255, 255, 255)
BORDER = (212, 231, 221)
MUTE = (96, 112, 104)
RED = (186, 58, 48)
AMBER = (214, 140, 30)

SHORT = {1: "Uslub", 2: "Qarashlar", 3: "Dalillar", 4: "Tuzilma", 5: "Mantiq", 6: "Izchillik",
         7: "Imlo", 8: "Punktuatsiya", 9: "Qo‘shimcha", 10: "So‘z qo‘llash", 11: "Leksika", 12: "Sheva"}

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
TASK = {
    7: "Imlo xatolarini tuzating", 8: "Punktuatsiya xatolarini tuzating",
    9: "Qo‘shimcha xatolarini tuzating", 10: "So‘z qo‘llashni aniqlashtiring",
    12: "Sheva va parazit so‘zlarni almashtiring",
    1: "Uslubni publitsistik qiling", 2: "Ikkala qarashni 2 tadan sabab bilan yoriting",
    3: "Ikkala qarashga aniq dalil yoki misol qo‘shing",
    4: "Xulosada bitta qarashni aniq qo‘llab-quvvatlang",
    5: "Abzaslar o‘rtasidagi bog‘lanishni kuchaytiring",
    6: "Takrorlarni qisqartiring", 11: "Leksikani boyiting (ibora, termin)",
}

FACTS = [
    "«Esse» so‘zi fransuzcha «essai» — «urinish» degan ma’noni anglatadi. Demak, qayta urinish esse janrining aynan o‘zi!",
    "«Punktuatsiya» lotincha «punctum» — «nuqta» so‘ziga borib taqaladi.",
    "«Imlo» so‘zi arabchadan kirgan bo‘lib, «yozdirish» ma’nosini bildiradi.",
    "«Leksika» yunoncha «lexis» — «so‘z» so‘zidan olingan: tilning butun so‘z boyligi.",
    "«Sinonim» yunoncha «bir xil nom» demak. Takror o‘rniga sinonim ishlating — leksik xilma-xillik oshadi.",
    "«Paronim» — talaffuzi o‘xshash, ma’nosi har xil so‘zlar (masalan, «tuz» va «to‘z»). Ular imlo va so‘z qo‘llashda ko‘p adashtiradi.",
    "«Tezis» yunoncha «qo‘yilgan fikr» degani: esseda har bir dalil bitta aniq tezisga xizmat qilishi kerak.",
    "«Xulosa» arabchada «mohiyat, siqilgan natija» ma’nosida: xulosa yangi fikr emas, aytilganlarning yakuni.",
    "«Mantiq» arabcha «nutq» ildizidan: fikr nutqda izchil bo‘lsa, mantiqli bo‘ladi.",
    "Eng yaxshi tahrir usuli — esseni ovoz chiqarib o‘qish: vergul va uzun gaplar darrov bilinadi.",
]

LEVELS = [(0, "Boshlang‘ich"), (12, "O‘rta"), (16, "Ilg‘or"), (20, "Master")]
MEDAL = {  # halqa, ichki, yulduz, lenta1, lenta2
    "Boshlang‘ich": ((176, 120, 70), (214, 160, 104), (255, 240, 220), (120, 150, 140), (90, 120, 112)),
    "O‘rta": ((150, 160, 172), (205, 212, 222), (255, 255, 255), (70, 120, 150), (50, 96, 124)),
    "Ilg‘or": ((40, 140, 100), (110, 200, 160), (240, 255, 246), (30, 110, 85), (22, 86, 66)),
    "Master": ((222, 170, 60), (250, 215, 120), (255, 247, 222), (46, 150, 100), (30, 110, 75)),
}


def level_name(total):
    name = LEVELS[0][1]
    for thr, nm in LEVELS:
        if total >= thr:
            name = nm
    return name


def _next_level(total):
    for thr, nm in LEVELS:
        if total < thr:
            return thr, nm
    return None, None


def _score_col(s):
    return GREEN if s >= 1.75 else AMBER if s >= 1 else RED


def _card(d, box, fill=WHITE, outline=BORDER, r=30):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=2)


def _title(d, y, text, right=""):
    d.text((M, y), clean(text), font=F(38, "b"), fill=GREEN_D)
    d.rounded_rectangle((M, y + 56, M + 52, y + 61), radius=3, fill=GOLD)
    if right:
        d.text((W - M, y + 14), clean(right), font=F(21), fill=MUTE, anchor="ra")
    return y + 88


# ------------------------------------------------------------------ MEDAL
def _star(cx, cy, ro, ri):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = ro if i % 2 == 0 else ri
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _medal(img, cx, top, level):
    ring, inner, star, rib1, rib2 = MEDAL[level]
    S = 3
    lw, lh = 330, 360
    layer = Image.new("RGBA", (lw * S, lh * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = lw // 2
    cy = 150

    def P(pts):
        return [(x * S, y * S) for x, y in pts]
    d.polygon(P([(c - 66, cy + 66), (c - 4, cy + 92), (c - 4, cy + 168), (c - 34, cy + 142), (c - 66, cy + 152)]), fill=rib1 + (255,))
    d.polygon(P([(c + 66, cy + 66), (c + 4, cy + 92), (c + 4, cy + 168), (c + 34, cy + 142), (c + 66, cy + 152)]), fill=rib2 + (255,))
    d.ellipse(((c - 128) * S, (cy - 128) * S, (c + 128) * S, (cy + 128) * S), fill=(255, 255, 255, 140))
    d.ellipse(((c - 104) * S, (cy - 104) * S, (c + 104) * S, (cy + 104) * S), fill=ring + (255,))
    d.ellipse(((c - 84) * S, (cy - 84) * S, (c + 84) * S, (cy + 84) * S), fill=inner + (255,))
    d.polygon(P(_star(c, cy + 4, 58, 24)), fill=star + (255,))
    layer = layer.resize((lw, lh), Image.LANCZOS)
    img.paste(layer, (cx - lw // 2, top), layer)


# ------------------------------------------------------------------ HEADER
def _header(img, total, eq, words, special):
    level = level_name(total)
    Hh = 800
    grad = Image.new("RGB", (W, Hh))
    gd = ImageDraw.Draw(grad)
    top, bot = (205, 236, 218), (143, 208, 176)
    for y in range(Hh):
        k = y / Hh
        gd.line((0, y, W, y), fill=tuple(int(top[i] * (1 - k) + bot[i] * k) for i in range(3)))
    mask = Image.new("L", (W, Hh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, -120, W, Hh), radius=80, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # logotip
    d.ellipse((M, 56, M + 64, 120), fill=GOLD, outline=CREAM, width=4)
    d.text((M + 32, 88), "E", font=F(32, "b"), fill=GREEN_D, anchor="mm")
    d.text((M + 84, 58), "Esse baholovchi bot", font=F(30, "b"), fill=GREEN_D)
    d.text((M + 84, 98), "Sizning darajangiz", font=F(21), fill=MUTE)
    _medal(img, W // 2, 118, level)
    d = ImageDraw.Draw(img)
    lc = GOLD_D
    d.text((W // 2, 466), level.upper(), font=F(30, "b"), fill=lc, anchor="mm")
    num = f"{total:g}"
    fn, fs = F(132, "b"), F(44, "m")
    wn = d.textlength(num, font=fn)
    sl = " / 24"
    ws = d.textlength(sl, font=fs)
    x0 = W // 2 - (wn + ws) / 2
    d.text((x0, 590), num, font=fn, fill=GREEN_D, anchor="ls")
    d.text((x0 + wn, 590), sl, font=fs, fill=MUTE, anchor="ls")
    d.text((W // 2, 640), clean(f"{eq} / 75 ball  •  {words} so‘z"), font=F(24), fill=MUTE, anchor="mm")
    # daraja chizig'i
    bx0, bx1, by = M, W - M, 706
    total_span = 24.0
    gap = 8
    for i, (thr, nm) in enumerate(LEVELS):
        nxt = LEVELS[i + 1][0] if i + 1 < len(LEVELS) else 24
        x_a = bx0 + (bx1 - bx0) * thr / total_span + (gap / 2 if i else 0)
        x_b = bx0 + (bx1 - bx0) * nxt / total_span - (gap / 2 if i + 1 < len(LEVELS) else 0)
        d.rounded_rectangle((x_a, by, x_b, by + 18), radius=9, fill=(222, 238, 229))
        fill_to = min(max(total, thr), nxt)
        if total > thr and not special:
            xf = bx0 + (bx1 - bx0) * fill_to / total_span - (gap / 2 if (i + 1 < len(LEVELS) and fill_to == nxt) else 0)
            d.rounded_rectangle((x_a, by, max(xf, x_a + 18), by + 18), radius=9, fill=GREEN)
        d.text(((x_a + x_b) / 2, by + 50), clean(nm), font=F(19), fill=MUTE, anchor="mm")
    mx = bx0 + (bx1 - bx0) * min(total, 24) / total_span
    d.polygon([(mx - 12, by - 22), (mx + 12, by - 22), (mx, by - 5)], fill=GREEN_D)
    return Hh + 36


# ------------------------------------------------------------------ SECTIONS
def _goal(d, y, total, special):
    gap = round(24 - total, 1)
    _card(d, (M, y, W - M, y + 150), r=30)
    d.rounded_rectangle((M + 28, y + 30, M + 118, y + 120), radius=22, fill=GOLD)
    d.text((M + 73, y + 75), "24", font=F(38, "b"), fill=GREEN_D, anchor="mm")
    if special:
        t1, t2 = "Qoidalarga amal qiling — natija o‘sadi!", "Quyidagi izohni o‘qib, esseni qayta yuboring."
    elif gap <= 0:
        t1, t2 = "Mukammal natija — 24/24!", "Siz eng yuqori marradasiz. Do‘stlaringizga ulashing!"
    elif gap <= 4:
        t1 = f"Mukammal natijagacha atigi {gap:g} ball!"
        t2 = "Keyingi urinishda 75/75 ga chiqing."
    else:
        thr, nm = _next_level(total)
        t1 = f"Keyingi daraja — {nm}: yana {thr - total:g} ball"
        t2 = "Quyidagi vazifalar sizni u yerga olib boradi."
    d.text((M + 150, y + 36), clean(t1), font=F(32, "b"), fill=GREEN_D)
    d.text((M + 150, y + 86), clean(t2), font=F(24), fill=MUTE)
    return y + 150 + 44


def _radar(img, y, score_of):
    d = ImageDraw.Draw(img)
    y = _title(d, y, "Mezonlar radari", "12 mezon bir ko‘rishda")
    ch = 760
    _card(d, (M, y, W - M, y + ch), r=34)
    cx, cy, R = W // 2, y + ch // 2, 262
    S = 2
    size = (R + 40) * 2
    layer = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    c = size * S // 2

    def pt(i, frac):
        a = -math.pi / 2 + i * math.pi / 6
        return (c + R * S * frac * math.cos(a), c + R * S * frac * math.sin(a))
    for k in (0.25, 0.5, 0.75, 1.0):
        pts = [pt(i, k) for i in range(12)]
        ld.polygon(pts, outline=(196, 222, 208, 255), width=2 * S)
    for i in range(12):
        ld.line((c, c, *pt(i, 1.0)), fill=(214, 232, 222, 255), width=S)
    vals = [max(0.0, min(2.0, score_of(i + 1))) / 2 for i in range(12)]
    pts = [pt(i, max(v, 0.04)) for i, v in enumerate(vals)]
    ld.polygon(pts, fill=GREEN + (70,))
    ld.line(pts + [pts[0]], fill=GREEN + (255,), width=5 * S, joint="curve")
    for (px, py), v in zip(pts, vals):
        r = 9 * S
        col = GREEN if v >= 0.99 else GREEN_L
        ld.ellipse((px - r, py - r, px + r, py + r), fill=col + (255,), outline=(255, 255, 255, 255), width=2 * S)
    layer = layer.resize((size, size), Image.LANCZOS)
    img.paste(layer, (cx - size // 2, cy - size // 2), layer)
    d = ImageDraw.Draw(img)
    for i in range(12):
        a = -math.pi / 2 + i * math.pi / 6
        ca, sa = math.cos(a), math.sin(a)
        lx, ly = cx + (R + 34) * ca, cy + (R + 34) * sa
        s = score_of(i + 1)
        name, sc = clean(SHORT[i + 1]), f"{s:g}"
        anchor = "l" if ca > 0.3 else "r" if ca < -0.3 else "m"
        ty = ly - 28 + (-8 if sa < -0.8 else 8 if sa > 0.8 else 0)
        d.text((lx, ty), name, font=F(22, "m"), fill=MUTE, anchor=anchor + "a")
        d.text((lx, ty + 28), sc, font=F(24, "b"), fill=_score_col(s), anchor=anchor + "a")
    return y + ch + 44


def _advice(img, y, rows):
    d = ImageDraw.Draw(img)
    y = _title(d, y, "Yozuvchi maslahati", "eng muhim 3 ta")
    weak = sorted([r for r in rows if r["s"] < 2], key=lambda r: (r["s"], r["c"]))[:3]
    if not weak:
        _card(d, (M, y, W - M, y + 130))
        d.ellipse((M + 28, y + 33, M + 92, y + 97), fill=GREEN)
        d.line([(M + 44, y + 66), (M + 56, y + 78), (M + 78, y + 52)], fill=WHITE, width=7, joint="curve")
        d.text((M + 120, y + 30), "Barcha mezonlar 2/2", font=F(30, "b"), fill=GREEN_D)
        d.text((M + 120, y + 76), "Bu darajani yangi mavzularda ham saqlang.", font=F(23), fill=MUTE)
        return y + 130 + 44
    for r in weak:
        lines = wrap(d, TIPS[r["c"]], F(24), CW - 190, 3)
        h = 78 + len(lines) * 34 + 22
        _card(d, (M, y, W - M, y + h), r=26)
        d.ellipse((M + 26, y + h // 2 - 36, M + 98, y + h // 2 + 36), fill=GREEN)
        d.text((M + 62, y + h // 2), str(r["c"]), font=F(32, "b"), fill=WHITE, anchor="mm")
        d.text((M + 124, y + 22), clean(f"{SHORT[r['c']]}  •  {r['s']:g}/2"), font=F(23, "b"), fill=GREEN)
        for i, ln in enumerate(lines):
            d.text((M + 124, y + 62 + i * 34), ln, font=F(24), fill=GREEN_D)
        y += h + 18
    return y + 26


def _short_pair(wrong, correct):
    """Uzun gapda faqat farqlanadigan joyni (1 ta kontekst so'z bilan) ko'rsatadi."""
    wrong, correct = str(wrong or ""), str(correct or "")
    if len(wrong) <= 34 and len(correct) <= 34:
        return wrong, correct
    wa, ca = wrong.split(), correct.split()
    p = 0
    while p < min(len(wa), len(ca)) and wa[p] == ca[p]:
        p += 1
    q = 0
    while q < min(len(wa), len(ca)) - p and wa[-1 - q] == ca[-1 - q]:
        q += 1
    st = max(0, p - 1)
    wd = " ".join(wa[st:len(wa) - q])
    cd = " ".join(ca[st:len(ca) - q])
    return (wd or wrong), (cd or correct)


def _tasks(img, y, rows):
    d = ImageDraw.Draw(img)
    items = []
    errs = sorted([r for r in rows if r["c"] in (7, 8, 9, 10, 12) and r["errs"]],
                  key=lambda r: (r["s"], r["c"]))
    for r in errs:
        e0 = r["errs"][0]
        w0, c0 = _short_pair(e0.get("wrong", ""), e0.get("correct", ""))
        sub = f"{w0} › {c0}" if c0 else w0
        if len(r["errs"]) > 1:
            sub += f"  (+{len(r['errs']) - 1} ta)"
        items.append((TASK[r["c"]], sub, max(0.5, 2 - r["s"])))
    for r in sorted([r for r in rows if r["c"] in (1, 2, 3, 4, 5, 6, 11) and r["s"] < 2],
                    key=lambda r: (r["s"], r["c"])):
        items.append((TASK[r["c"]], "", 0.5))
    items = items[:4]
    y = _title(d, y, "Keyingi urinish vazifalari", f"{max(1, len(items))} ta vazifa")
    if not items:
        items = [("Shu natijani yangi mavzuda takrorlang", "", 0)]
    for title, sub, gain in items:
        sub_l = wrap(d, sub, F(21), CW - 330, 1)[0] if sub else ""
        h = 120 if sub_l else 96
        _card(d, (M, y, W - M, y + h), r=26)
        d.rounded_rectangle((M + 28, y + h // 2 - 20, M + 68, y + h // 2 + 20), radius=9, outline=GREEN, width=4)
        tl = wrap(d, title, F(27, "b"), CW - 330, 1)[0]
        d.text((M + 96, y + (22 if sub_l else h // 2 - 16)), tl, font=F(27, "b"), fill=GREEN_D)
        if sub_l:
            d.text((M + 96, y + 70), sub_l, font=F(21), fill=RED)
        if gain:
            gt = f"+{gain:g}"
            pw = int(d.textlength(gt, font=F(24, "b"))) + 40
            d.rounded_rectangle((W - M - 28 - pw, y + h // 2 - 22, W - M - 28, y + h // 2 + 22), radius=22, fill=GOLD)
            d.text((W - M - 28 - pw // 2, y + h // 2), gt, font=F(24, "b"), fill=GREEN_D, anchor="mm")
        y += h + 16
    return y + 28


def _fact(d, y, text):
    lines = wrap(d, text, F(24), CW - 170, 5)
    h = 72 + len(lines) * 34 + 26
    _card(d, (M, y, W - M, y + h), fill=CREAM, outline=(238, 220, 160), r=28)
    d.ellipse((M + 28, y + 28, M + 92, y + 92), fill=GOLD)
    d.text((M + 60, y + 60), "?", font=F(36, "b"), fill=WHITE, anchor="mm")
    d.text((M + 118, y + 26), "Bilasizmi?", font=F(28, "b"), fill=GOLD_D)
    for i, ln in enumerate(lines):
        d.text((M + 118, y + 72 + i * 34), ln, font=F(24), fill=(94, 78, 40))
    return y + h + 28


def _topic(d, y, topic):
    tl = wrap(d, topic, F(23), CW - 80, 3) if topic else []
    h = 58 + 52 + (len(tl) * 33 + 10 if tl else 0) + 30
    _card(d, (M, y, W - M, y + h), fill=(224, 241, 232), outline=(200, 226, 212), r=28)
    d.text((M + 36, y + 26), "BUGUNGI MAVZU", font=F(18, "b"), fill=GOLD_D)
    d.text((M + 36, y + 56), "Yangi esse yozing — yangi rekord qo‘ying", font=F(31, "b"), fill=GREEN_D)
    for i, ln in enumerate(tl):
        d.text((M + 36, y + 112 + i * 33), ln, font=F(23), fill=MUTE)
    return y + h + 28


def _cta(img, y):
    h = 250
    grad = Image.new("RGB", (CW, h))
    gd = ImageDraw.Draw(grad)
    a, b = (181, 133, 40), (238, 190, 84)
    for x in range(CW):
        k = x / CW
        gd.line((x, 0, x, h), fill=tuple(int(a[i] * (1 - k) + b[i] * k) for i in range(3)))
    ov = Image.new("RGBA", (CW, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.ellipse((CW - 250, -90, CW + 60, 220), fill=(255, 255, 255, 36))
    od.ellipse((CW - 460, 150, CW - 250, 360), fill=(255, 255, 255, 30))
    grad = Image.alpha_composite(grad.convert("RGBA"), ov).convert("RGB")
    mask = Image.new("L", (CW, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, CW, h), radius=34, fill=255)
    img.paste(grad, (M, y), mask)
    d = ImageDraw.Draw(img)
    d.text((M + 40, y + 36), "Rekordingizni yangilang!", font=F(40, "b"), fill=GREEN_D)
    d.text((M + 40, y + 98), "Esseni tuzatib qayta yuboring yoki bugungi mavzuda yangi esse yozing.",
           font=F(21), fill=(70, 52, 14))
    bw = int(d.textlength("Qayta tekshirish  ›", font=F(26, "b"))) + 70
    d.rounded_rectangle((M + 40, y + 148, M + 40 + bw, y + 212), radius=32, fill=GREEN_D)
    d.text((M + 40 + bw // 2, y + 180), "Qayta tekshirish  ›", font=F(26, "b"), fill=WHITE, anchor="mm")
    return y + h + 28


def _summary(d, y, text):
    lines = wrap(d, text, F(24), CW - 90, 7)
    h = 80 + len(lines) * 36 + 30
    _card(d, (M, y, W - M, y + h), r=28)
    d.rounded_rectangle((M + 32, y + 34, M + 40, y + 70), radius=4, fill=GOLD)
    d.text((M + 62, y + 30), "Ustoz xulosasi", font=F(30, "b"), fill=GREEN_D)
    for i, ln in enumerate(lines):
        d.text((M + 36, y + 90 + i * 36), ln, font=F(24), fill=MUTE)
    return y + h + 28


def _special(d, y, reason):
    lines = wrap(d, reason, F(26), CW - 150, 4)
    h = 80 + len(lines) * 38 + 30
    _card(d, (M, y, W - M, y + h), fill=(255, 244, 222), outline=(240, 214, 150), r=28)
    d.ellipse((M + 28, y + 30, M + 88, y + 90), fill=AMBER)
    d.text((M + 58, y + 60), "!", font=F(36, "b"), fill=WHITE, anchor="mm")
    d.text((M + 112, y + 36), "Maxsus holat", font=F(30, "b"), fill=GOLD_D)
    for i, ln in enumerate(lines):
        d.text((M + 112, y + 88 + i * 38), ln, font=F(26), fill=(94, 78, 40))
    return y + h + 28


def _invite(d, y, bonus):
    _card(d, (M, y, W - M, y + 150), fill=(224, 241, 232), outline=(200, 226, 212), r=30)
    d.ellipse((M + 30, y + 35, M + 110, y + 115), fill=GREEN)
    d.text((M + 70, y + 75), f"+{bonus}", font=F(32, "b"), fill=WHITE, anchor="mm")
    d.text((M + 138, y + 34), "Do‘stingni chaqir — bepul esse ol", font=F(30, "b"), fill=GREEN_D)
    d.text((M + 138, y + 86), clean(f"Do‘sting birinchi essesini tekshirtirsa, sizga +{bonus} tekshiruv."),
           font=F(23), fill=MUTE)
    return y + 150 + 36


def _footer(d, y, bot):
    d.line((M, y, W - M, y), fill=BORDER, width=2)
    brand = "Esse baholovchi bot" + (f"  •  @{bot}" if bot else "")
    d.text((M, y + 28), clean(brand), font=F(26, "b"), fill=GREEN)
    d.text((M, y + 70), "Sun’iy intellekt bahosi; haqiqiy ekspert bahosidan biroz farq qilishi mumkin.",
           font=F(19), fill=MUTE)
    return y + 130


# ------------------------------------------------------------------ MAIN
def make_result_report(data, total24, eq75, topic=None, bot_username="", ref_bonus=1):
    total = float(total24)
    special = str(data.get("status", "")) == "special_case"
    by = {}
    for it in data.get("scores") or []:
        try:
            by[int(it.get("criterion"))] = it
        except Exception:
            continue

    def score_of(c):
        try:
            return float(by.get(c, {}).get("score", 0) or 0)
        except Exception:
            return 0.0
    rows = [{"c": c, "s": score_of(c),
             "errs": [e for e in (by.get(c, {}).get("errors") or []) if isinstance(e, dict)]}
            for c in range(1, 13)]
    words = int(data.get("word_count", 0) or 0)

    img = Image.new("RGB", (W, 9000), BG)
    y = _header(img, total, int(eq75), words, special)
    d = ImageDraw.Draw(img)
    y = _goal(d, y, total, special)
    if special:
        y = _special(d, y, str(data.get("special_reason") or "Esse baholashga yaroqsiz."))
    else:
        y = _radar(img, y, score_of)
        y = _advice(img, y, rows)
        y = _tasks(img, y, rows)
        d = ImageDraw.Draw(img)
        seed = datetime.date.today().toordinal() + words
        y = _fact(d, y, FACTS[seed % len(FACTS)])
    d = ImageDraw.Draw(img)
    y = _topic(d, y, topic)
    y = _cta(img, y)
    d = ImageDraw.Draw(img)
    summary = str(data.get("summary", "") or "").strip()
    if summary and not special:
        y = _summary(d, y, summary)
    y = _invite(d, y, int(ref_bonus))
    y = _footer(d, y, str(bot_username or "").lstrip("@"))
    img = img.crop((0, 0, W, y))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=90, optimize=True)
    out.seek(0)
    out.name = "esse_natijasi.jpg"
    return out
