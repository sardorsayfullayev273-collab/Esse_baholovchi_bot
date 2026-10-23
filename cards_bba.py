"""BBA uslubidagi kartalar (yashil fon, oltin ramka, BBA muhri): kechki (1 kun oldin), tong va imtihondan keyingi.
Shablon: assets/bba_template.jpg. Pastki matn qismi tozalanib, xotirada BIR MARTA saqlanadi; har foydalanuvchi uchun faqat matn chiziladi."""
import io, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "assets", "bba_template.jpg")
F = lambda n: os.path.join(HERE, "fonts", n)
GOLD = (255, 176, 0); WHITE = (255, 255, 255); SOFT = (235, 252, 246)
CX = 540
BASE = {"name": 859, "head": 962, "sub1": 1037, "sub2": 1095}           # asl rasmga moslangan (Poppins)
_BASE = None

TEXTS = {
    "morning": {"greet": "Hurmatli {n}!", "head": "Oxirgi qadam — ishonch bilan!",
                "sub": ["Eng muhim qadam — oxirgisi.", "Xotirjam bo‘ling, uddalaysiz."]},
    "eve": {"greet": "Hurmatli {n}!", "head": "Ertaga — katta kun!",
            "sub": ["Bugun erta uxlang, pasportni", "tayyorlab qo‘ying. Siz tayyorsiz."]},
    "after": {"greet": "Tabriklaymiz, {n}!", "head": "Eslagan savollaringizni yuboring!",
              "sub": ["Birgalikda testni to‘liq tiklaymiz,", "natijani birinchilardan bilasiz."]},
}


def _font(name, size):
    try: return ImageFont.truetype(F(name), size)
    except Exception: return ImageFont.load_default()


def _base():
    global _BASE
    if _BASE is None:
        im = Image.open(TEMPLATE).convert("RGB"); px = im.load(); d = ImageDraw.Draw(im)
        for y in range(804, 1239):                                   # matn qismini fon rangi bilan tozalash (chap chetdan olingan rang)
            col = tuple(sum(px[x, y][i] for x in range(70, 131)) // 61 for i in range(3))
            d.line((60, y, 1019, y), fill=col)
        _BASE = im
    return _BASE.copy()


def _has_exotic(s):
    return any(ord(ch) > 0x24F and ch not in "‘’—ʻʼ" for ch in s)


def _fit(d, text, bold, max_w, start, minimum=30, fallback=False):
    s = start
    name = ("DejaVuSans-Bold.ttf" if fallback else "Poppins-Bold.ttf") if bold else ("DejaVuSans.ttf" if fallback else "Poppins-Regular.ttf")
    while s >= minimum:
        f = _font(name, s)
        if d.textlength(text, font=f) <= max_w: return f
        s -= 2
    return _font(name, minimum)


def _spaced(d, cx, y, text, font, fill, sp=3):
    w = sum(d.textlength(ch, font=font) for ch in text) + sp * (len(text) - 1); x = cx - w / 2
    for ch in text:
        d.text((x, y), ch, font=font, fill=fill, anchor="ls"); x += d.textlength(ch, font=font) + sp


def make_card_bba(kind, name="", label="", bot_username=""):
    """kind: morning | eve | after. label: pastdagi oltin yorliq (sana/smena/vaqt), bo'sh bo'lsa chizilmaydi. JPEG baytlari."""
    t = TEXTS[kind]; im = _base(); d = ImageDraw.Draw(im)
    n = (name or "do‘stim").strip() or "do‘stim"
    greet = t["greet"].format(n=n)
    f = _fit(d, greet, True, 840, 64, 40, fallback=_has_exotic(greet))
    d.text((CX, BASE["name"]), greet, font=f, fill=WHITE, anchor="ms")
    d.line((140, 890, 940, 890), fill=(180, 150, 30), width=2)
    fh = _fit(d, t["head"], True, 840, 44, 32)
    d.text((CX, BASE["head"]), t["head"], font=fh, fill=GOLD, anchor="ms")
    for i, ln in enumerate(t["sub"]):
        fs = _fit(d, ln, False, 840, 40, 28)
        d.text((CX, BASE["sub1"] if i == 0 else BASE["sub2"]), ln, font=fs, fill=SOFT, anchor="ms")
    if label:
        fl = _font("Poppins-Medium.ttf", 27); lab = label.upper()
        while sum(d.textlength(ch, font=fl) for ch in lab) + 3 * len(lab) > 780 and fl.size > 18: fl = _font("Poppins-Medium.ttf", fl.size - 1)
        w = sum(d.textlength(ch, font=fl) for ch in lab) + 3 * (len(lab) - 1) + 70
        d.rounded_rectangle((CX - w / 2, 1138, CX + w / 2, 1206), 34, outline=GOLD, width=2)
        _spaced(d, CX, 1181, lab, fl, GOLD)
    out = io.BytesIO(); im.save(out, "JPEG", quality=92, optimize=True)
    return out.getvalue()
