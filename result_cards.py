# -*- coding: utf-8 -*-
"""Esse natijasi uchun telefonga mos, slaydli (4:5) rasm kartalari.

3 ta dizayn: "premium" (qora-oltin), "diplom" (ta'limiy, qog'oz-yashil), "fresh" (yorqin, o'yinlashtirilgan).
Ishlatish: make_result_slides(data, style, to75, total24) -> [BytesIO, ...]  (Telegram albomi uchun)
"""
import io, os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
_HERE = os.path.dirname(os.path.abspath(__file__))
_FONT_DIRS = [os.path.join(_HERE, "fonts"), "/usr/share/fonts/truetype/google-fonts",
              "/usr/share/fonts/truetype/dejavu"]
_FILES = {"r": ["Poppins-Regular.ttf", "DejaVuSans.ttf"],
          "m": ["Poppins-Medium.ttf", "DejaVuSans.ttf"],
          "b": ["Poppins-Bold.ttf", "DejaVuSans-Bold.ttf"]}
_cache = {}


def F(size, w="r"):
    k = (size, w)
    if k not in _cache:
        found = None
        for name in _FILES[w]:
            for d in _FONT_DIRS:
                p = os.path.join(d, name)
                if os.path.exists(p):
                    found = ImageFont.truetype(p, size)
                    break
            if found:
                break
        _cache[k] = found or ImageFont.load_default()
    return _cache[k]


def clean(t):
    """Poppins'da yo'q belgilarni almashtiradi."""
    return str(t or "").replace("ʻ", "’").replace("ʼ", "’").replace("`", "’").replace("\u200b", "")


def wrap(d, text, f, width, max_lines=None):
    words, lines, cur = clean(text).split(), [], ""
    for w in words:
        t = w if not cur else cur + " " + w
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        while d.textlength(lines[-1] + "…", font=f) > width and len(lines[-1]) > 3:
            lines[-1] = lines[-1][:-1].rstrip()
        lines[-1] += "…"
    return lines or [""]


# ---------------------------------------------------------------- THEMES
THEMES = {
    "premium": dict(name="Premium", bg=(14, 20, 33), bg2=(24, 34, 54), card=(27, 38, 60), ink=(244, 240, 228),
                    mute=(150, 163, 188), accent=(226, 183, 90), good=(104, 211, 145), mid=(240, 190, 90),
                    bad=(240, 113, 103), line=(48, 62, 92), onaccent=(20, 24, 36),
                    brand="BILIMNI BAHOLASH AGENTLIGI"),
    "diplom": dict(name="Ta’limiy diplom", bg=(250, 246, 234), bg2=(243, 236, 214), card=(255, 253, 246),
                   ink=(38, 52, 46), mute=(112, 120, 108), accent=(24, 112, 76), good=(30, 140, 90),
                   mid=(205, 140, 30), bad=(190, 70, 60), line=(224, 214, 184), onaccent=(255, 255, 255),
                   brand="BILIMNI BAHOLASH AGENTLIGI"),
    "fresh": dict(name="Fresh", bg=(244, 247, 255), bg2=(228, 236, 255), card=(255, 255, 255), ink=(28, 36, 64),
                  mute=(108, 118, 150), accent=(88, 86, 232), good=(22, 178, 120), mid=(255, 168, 38),
                  bad=(244, 84, 100), line=(224, 230, 248), onaccent=(255, 255, 255),
                  brand="BILIMNI BAHOLASH AGENTLIGI"),
}

CRIT = {1: "Publitsistik uslub", 2: "Ikkala qarash va shaxsiy qarash", 3: "Dalillash",
        4: "Kirish, asosiy qism, xulosa", 5: "Mantiqiy qurilish", 6: "Izchillik va takror",
        7: "Imlo", 8: "Punktuatsiya", 9: "Qo‘shimcha qo‘llash", 10: "So‘z qo‘llash",
        11: "Leksik xilma-xillik", 12: "Sheva, vulgarizm, parazit"}
TYPE = {7: "Imlo", 8: "Punktuatsiya", 9: "Qo‘shimcha", 10: "So‘z qo‘llash", 12: "Sheva/parazit"}


def level_of(total24):
    if total24 >= 21:
        return "A+ • Mukammal", "Siz yuqori marraga yaqinsiz!"
    if total24 >= 18:
        return "A • Juda yaxshi", "Bir oz sayqal — va natija a’lo bo‘ladi."
    if total24 >= 14:
        return "B • Yaxshi", "Asos mustahkam, o‘sish zonasi aniq."
    if total24 >= 9:
        return "C • O‘rta", "To‘g‘ri yo‘ldasiz — reja bilan tez o‘sasiz."
    return "D • Boshlang‘ich", "Har bir buyuk yozuvchi shu yerdan boshlagan."


def _col(t, score):
    return t["good"] if score >= 1.75 else t["mid"] if score >= 1 else t["bad"]


def _canvas(t, style):
    img = Image.new("RGB", (W, H), t["bg"])
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        c = tuple(int(t["bg"][i] * (1 - k) + t["bg2"][i] * k) for i in range(3))
        d.line((0, y, W, y), fill=c)
    if style == "diplom":
        d.rectangle((26, 26, W - 26, H - 26), outline=t["accent"], width=4)
        d.rectangle((40, 40, W - 40, H - 40), outline=t["line"], width=2)
    elif style == "fresh":
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.ellipse((W - 380, -160, W + 140, 360), fill=t["accent"] + (34,))
        od.ellipse((-200, H - 360, 300, H + 140), fill=t["good"] + (30,))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        d = ImageDraw.Draw(img)
    else:
        d.rectangle((0, 0, W, 8), fill=t["accent"])
    return img, d


def _header(d, t, n, total, page_title):
    d.text((70, 62), clean(page_title).upper(), font=F(26, "b"), fill=t["accent"])
    s = f"{n}/{total}"
    d.text((W - 70 - d.textlength(s, font=F(26, "m")), 62), s, font=F(26, "m"), fill=t["mute"])


def _footer(d, t):
    d.text((70, H - 92), t["brand"], font=F(22, "b"), fill=t["accent"])
    d.text((70, H - 62), "AI natija • Haqiqiy ekspert bahosidan biroz farq qilishi mumkin",
           font=F(18), fill=t["mute"])


def _card(d, t, box, r=30):
    d.rounded_rectangle(box, radius=r, fill=t["card"], outline=t["line"], width=2)


def _ring(img, t, cx, cy, R, frac, label, sub):
    S = 3
    size = (R + 24) * 2
    layer = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    c = size * S // 2
    rr = R * S
    wdt = 34 * S
    ld.arc((c - rr, c - rr, c + rr, c + rr), 0, 360, fill=t["line"] + (255,), width=wdt)
    if frac > 0:
        ld.arc((c - rr, c - rr, c + rr, c + rr), -90, -90 + 360 * min(1, frac),
               fill=t["accent"] + (255,), width=wdt)
    layer = layer.resize((size, size), Image.LANCZOS)
    img.paste(layer, (cx - size // 2, cy - size // 2), layer)
    d = ImageDraw.Draw(img)
    d.text((cx, cy - 22), label, font=F(104, "b"), fill=t["ink"], anchor="mm")
    d.text((cx, cy + 56), sub, font=F(28, "m"), fill=t["mute"], anchor="mm")


# ---------------------------------------------------------------- SLIDES
def slide_hero(t, style, data, total, eq, n, N):
    img, d = _canvas(t, style)
    _header(d, t, n, N, "Esse natijasi")
    lvl, motto = level_of(total)
    d.text((W // 2, 150), "Sizning natijangiz", font=F(40, "b"), fill=t["ink"], anchor="mm")
    _ring(img, t, W // 2, 430, 215, total / 24, f"{total:g}", "24 balldan")
    d = ImageDraw.Draw(img)
    bw = int(d.textlength(lvl, font=F(32, "b"))) + 70
    d.rounded_rectangle((W // 2 - bw // 2, 700, W // 2 + bw // 2, 764), radius=32, fill=t["accent"])
    d.text((W // 2, 732), lvl, font=F(32, "b"), fill=t["onaccent"], anchor="mm")
    d.text((W // 2, 806), motto, font=F(30, "m"), fill=t["mute"], anchor="mm")
    rows = sorted(data.get("scores", []), key=lambda x: int(x["criterion"]))
    words = int(data.get("word_count", 0) or 0)
    errs = sum(int(x.get("error_count", 0) or 0) for x in rows if int(x["criterion"]) in (7, 8, 9, 10, 12))
    stats = [("75 ballik", f"{eq}/75"), ("So‘zlar", str(words)), ("Xatolar", str(errs))]
    cw = (W - 140 - 40) // 3
    for i, (k, v) in enumerate(stats):
        x = 70 + i * (cw + 20)
        _card(d, t, (x, 880, x + cw, 1030), 26)
        d.text((x + cw // 2, 935), v, font=F(48, "b"), fill=t["ink"], anchor="mm")
        d.text((x + cw // 2, 996), k, font=F(24, "m"), fill=t["mute"], anchor="mm")
    strong = max(rows, key=lambda x: (float(x["score"]), -int(x["criterion"])))
    weak = min(rows, key=lambda x: (float(x["score"]), int(x["criterion"])))
    _card(d, t, (70, 1060, W - 70, 1250), 26)
    d.ellipse((105, 1096, 119, 1110), fill=t["good"])
    d.text((130, 1090), "Eng kuchli tomon", font=F(22, "m"), fill=t["good"])
    d.text((105, 1122), CRIT.get(int(strong["criterion"]), ""), font=F(30, "b"), fill=t["ink"])
    d.polygon([(105, 1190), (119, 1190), (112, 1177)], fill=t["mid"])
    d.text((130, 1172), "O‘sish zonasi", font=F(22, "m"), fill=t["mid"])
    d.text((105, 1204), CRIT.get(int(weak["criterion"]), ""), font=F(30, "b"), fill=t["ink"])
    _footer(d, t)
    return img


def slide_criteria(t, style, data, n, N):
    img, d = _canvas(t, style)
    _header(d, t, n, N, "12 mezon bo‘yicha")
    d.text((70, 120), "Mezonlar xaritasi", font=F(44, "b"), fill=t["ink"])
    rows = sorted(data.get("scores", []), key=lambda x: int(x["criterion"]))
    y, rh = 205, 86
    for it in rows:
        c, s = int(it["criterion"]), float(it["score"])
        col = _col(t, s)
        d.text((70, y), f"{c}", font=F(26, "b"), fill=t["accent"])
        d.text((118, y), CRIT.get(c, ""), font=F(28, "m"), fill=t["ink"])
        sc = f"{s:g}/2"
        d.text((W - 70 - d.textlength(sc, font=F(28, "b")), y), sc, font=F(28, "b"), fill=col)
        d.rounded_rectangle((118, y + 46, W - 70, y + 62), radius=8, fill=t["line"])
        if s > 0:
            d.rounded_rectangle((118, y + 46, 118 + int((W - 188) * s / 2), y + 62), radius=8, fill=col)
        y += rh
    _footer(d, t)
    return img


def _err_blocks(data):
    out = []
    for it in sorted(data.get("scores", []), key=lambda x: int(x["criterion"])):
        c = int(it["criterion"])
        for e in it.get("errors") or []:
            if isinstance(e, dict):
                out.append((c, e))
    return out


def _paginate_errors(d, errs):
    """Xatolarni balandligi bo'yicha sahifalarga bo'ladi (hech narsa kesilmaydi)."""
    pages, cur, used = [], [], 0
    avail = H - 250 - 150
    for c, e in errs:
        ex = e.get("explanation", "")
        w_l = wrap(d, e.get("wrong", ""), F(28, "m"), W - 260, 2)
        r_l = wrap(d, e.get("correct", ""), F(28, "m"), W - 260, 2)
        x_l = wrap(d, ex, F(23), W - 170, 2) if ex else []
        h = 28 + 34 + len(w_l) * 38 + len(r_l) * 38 + len(x_l) * 31 + 20
        if cur and used + h > avail:
            pages.append(cur)
            cur, used = [], 0
        cur.append((c, w_l, r_l, x_l, h))
        used += h + 14
    if cur:
        pages.append(cur)
    return pages


def slide_errors(t, style, page, n, N, k, K, total_errs):
    img, d = _canvas(t, style)
    _header(d, t, n, N, "Xatolar tahlili")
    d.text((70, 120), "Xatolar ustida ishlaymiz", font=F(44, "b"), fill=t["ink"])
    d.text((70, 182), f"Jami {total_errs} ta aniq xato • {k}/{K} sahifa", font=F(24), fill=t["mute"])
    y = 250
    for c, w_l, r_l, x_l, h in page:
        _card(d, t, (60, y, W - 60, y + h), 24)
        tag = TYPE.get(c, f"{c}-mezon")
        tw = int(d.textlength(tag, font=F(20, "b"))) + 28
        d.rounded_rectangle((90, y + 16, 90 + tw, y + 48), radius=16, fill=t["line"])
        d.text((104, y + 21), tag, font=F(20, "b"), fill=t["accent"])
        yy = y + 62
        d.ellipse((90, yy + 11, 104, yy + 25), fill=t["bad"])
        for ln in w_l:
            d.text((124, yy), ln, font=F(28, "m"), fill=t["bad"])
            yy += 38
        d.ellipse((90, yy + 11, 104, yy + 25), fill=t["good"])
        for ln in r_l:
            d.text((124, yy), ln, font=F(28, "m"), fill=t["good"])
            yy += 38
        for ln in x_l:
            d.text((90, yy + 2), ln, font=F(23), fill=t["mute"])
            yy += 31
        y += h + 14
    _footer(d, t)
    return img


def slide_clean(t, style, n, N):
    img, d = _canvas(t, style)
    _header(d, t, n, N, "Xatolar tahlili")
    d.text((W // 2, 560), "Aniq xato topilmadi", font=F(52, "b"), fill=t["good"], anchor="mm")
    d.text((W // 2, 640), "Imlo, punktuatsiya, qo‘shimcha va so‘z qo‘llash toza.", font=F(28),
           fill=t["mute"], anchor="mm")
    _footer(d, t)
    return img


def slide_plan(t, style, data, n, N):
    img, d = _canvas(t, style)
    _header(d, t, n, N, "Keyingi qadam")
    d.text((70, 120), "O‘sish rejangiz", font=F(44, "b"), fill=t["ink"])
    y = 210
    summary = str(data.get("summary", "") or "").strip()
    if summary:
        lines = wrap(d, summary, F(26), W - 190, 6)
        h = 40 + len(lines) * 38 + 40
        _card(d, t, (60, y, W - 60, y + h), 26)
        d.text((90, y + 22), "Umumiy xulosa", font=F(22, "b"), fill=t["accent"])
        for i, ln in enumerate(lines):
            d.text((90, y + 62 + i * 38), ln, font=F(26), fill=t["ink"])
        y += h + 24
    imps = [str(x) for x in (data.get("improvements") or []) if str(x).strip()][:4] or \
        ["Har bir xatoni daftarga yozib, to‘g‘risini 3 marta yozing.",
         "Keyingi esseda ikkala qarashga 2 tadan dalil keltiring."]
    for i, x in enumerate(imps, 1):
        lines = wrap(d, x, F(26), W - 250, 3)
        h = 36 + len(lines) * 36
        if y + h > H - 330:
            break
        _card(d, t, (60, y, W - 60, y + h), 24)
        d.ellipse((86, y + h // 2 - 24, 134, y + h // 2 + 24), fill=t["accent"])
        d.text((110, y + h // 2), str(i), font=F(26, "b"), fill=t["onaccent"], anchor="mm")
        for j, ln in enumerate(lines):
            d.text((158, y + 18 + j * 36), ln, font=F(26), fill=t["ink"])
        y += h + 14
    d.rounded_rectangle((60, H - 290, W - 60, H - 140), radius=30, fill=t["accent"])
    d.text((W // 2, H - 236), "Natijani yaxshilashga tayyormisiz?", font=F(32, "b"), fill=t["onaccent"], anchor="mm")
    d.text((W // 2, H - 184), "Yangi esse yuboring — har kuni bepul tekshiruv bor", font=F(24),
           fill=t["onaccent"], anchor="mm")
    _footer(d, t)
    return img


def make_result_slides(data, style="premium", to75=None, total24=None, max_error_pages=3):
    t = THEMES.get(style, THEMES["premium"])
    total = float(total24 if total24 is not None else data.get("total", 0) or 0)
    eq = to75(total) if to75 else int(round(27 + 2 * total))
    tmp = Image.new("RGB", (W, H))
    td = ImageDraw.Draw(tmp)
    errs = _err_blocks(data)
    pages = _paginate_errors(td, errs)[:max_error_pages]
    N = 3 + max(1, len(pages))
    slides = [slide_hero(t, style, data, total, eq, 1, N), slide_criteria(t, style, data, 2, N)]
    if pages:
        for k, p in enumerate(pages, 1):
            slides.append(slide_errors(t, style, p, 2 + k, N, k, len(pages), len(errs)))
    else:
        slides.append(slide_clean(t, style, 3, N))
    slides.append(slide_plan(t, style, data, N, N))
    outs = []
    for i, im in enumerate(slides, 1):
        b = io.BytesIO()
        im.save(b, "JPEG", quality=90, optimize=True)
        b.seek(0)
        b.name = f"esse_{i}.jpg"
        outs.append(b)
    return outs
