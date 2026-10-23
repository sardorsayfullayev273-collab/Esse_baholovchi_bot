"""exam_flow — v97: imtihon sanasi so'rovnomasi, smenaga qarab xabarlar, imtihondan keyingi fikr-mulohaza.

To'lov tizimiga (manual_pay.py) TEGMAYDI. Yangi jadvallar: exam_slot, exam_sent, exam_fb, exam_survey_log.

Oqim:
  1) Admin: /sorov_yubor tasdiq  -> hamma foydalanuvchiga rasmli so'rovnoma ("Imtihoningiz qaysi kuni?").
  2) Foydalanuvchi sana/smena tanlaydi -> ismli tasdiq kartasi.
  3) Jadval (Toshkent vaqti): oldingi kuni 20:00 "ertaga imtihon"; imtihon kuni ertalab "omad" kartasi;
     smena tugagach "qanday o'tdi?"; ertasi kuni javob bermaganlarga bitta eslatma.
  4) "Qanday o'tdi?" -> mavzular (ko'p tanlov) -> esse mavzusi (ixtiyoriy) -> "Men imtihon topshirdim" kartasi + bonus.
Mavzular statistikasi FAQAT o'z smenasi tugagan foydalanuvchiga ko'rsatiladi (hali topshirmaganlarga oldindan ma'lumot ketmaydi).
Imtihon savollarining O'ZI so'ralmaydi — faqat mavzu nomlari.
"""
import os, io, re, json, html, asyncio, logging, random, time
from datetime import datetime, timedelta, timezone, date

from PIL import Image, ImageDraw, ImageFont
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, WebAppInfo
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram.error import RetryAfter, Forbidden, BadRequest
try:
    from telegram.ext import ApplicationHandlerStop
except ImportError:      # sinov (stub) muhiti
    class ApplicationHandlerStop(Exception):
        pass

from national_certificate import db

log = logging.getLogger("exam_flow")
TZ = timezone(timedelta(hours=5))   # Toshkent
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_B = os.path.join(HERE, "fonts", "DejaVuSans-Bold.ttf")
FONT_R = os.path.join(HERE, "fonts", "DejaVuSans.ttf")
FONT_NUM = os.path.join(HERE, "fonts", "Poppins-Bold.ttf")

ENABLED = os.getenv("EXAM_FLOW", "1") != "0"
YEAR = int(os.getenv("EXAM_YEAR", "2026") or 2026)
MONTH = int(os.getenv("EXAM_MONTH", "10") or 10)
DAYS = [int(x) for x in os.getenv("EXAM_DAYS", "24,25,26").split(",") if x.strip()]
REWARD_ESSAYS = int(os.getenv("EXAM_REWARD_ESSAYS", "1") or 0)
# v102: yangi kirganlarga so'rovnoma AVTOMATIK (admin /sorov_yubor ni kutmaydi)
AUTO_SURVEY = os.getenv("EXAM_AUTO_SURVEY", "1") != "0"
AUTO_DELAY_MIN = int(os.getenv("EXAM_AUTO_DELAY_MIN", "3") or 0)     # kirgandan necha daqiqa o'tgach (salom xabari bilan to'qnashmasin)
AUTO_BATCH = int(os.getenv("EXAM_AUTO_BATCH", "20") or 20)           # bir o'tishda eng ko'pi
AUTO_FROM = os.getenv("EXAM_AUTO_FROM", "").strip()                  # ixtiyoriy: shu UTC vaqtdan (2026-10-20T00:00:00Z) keyin kirganlar
DUA = os.getenv("EXAM_DUA_TEXT", "Alloh taolo yuzingizni yorug‘ qilsin.\nDuo bilan kiring. Ko‘proq istig‘for va salovotlar bilan boshlang 🙂")
TOTAL_Q = int(os.getenv("EXAM_Q_TOTAL", "44") or 44)
Q_REWARD = int(os.getenv("EXAM_Q_REWARD", "0") or 0)       # (ixtiyoriy) savollar uchun bepul esse; standart: o'chiq — asosiy rag'bat: javoblarni birinchi ko'rish
Q_MIN = int(os.getenv("EXAM_Q_MIN", "10") or 10)           # mukofot uchun kamida shuncha savol
ARRIVE_BEFORE_MIN = int(os.getenv("EXAM_ARRIVE_BEFORE_MIN", "60") or 60)
MIN_STATS_N = int(os.getenv("EXAM_MIN_STATS_N", "10") or 10)

# smena: kirish, chiqish, "omad" xabari, "tugadi" xabari
SHIFTS = {
    1: dict(name="I smena",  enter=(7, 0),  exit=(11, 30), morning=(5, 0),  after=(12, 0)),
    2: dict(name="II smena", enter=(13, 0), exit=(17, 15), morning=(9, 30), after=(17, 45)),
}
TOPICS = ["Tilshunoslik nazariyasi", "Badiiy asar", "Ilmiy matn", "Badiiy matn",
          "G‘azal", "Lingvistik tahlil", "Mumtoz tahlil", "Esse"]
MONTH_UZ = {1: "yanvar", 2: "fevral", 3: "mart", 4: "aprel", 5: "may", 6: "iyun", 7: "iyul", 8: "avgust",
            9: "sentyabr", 10: "oktabr", 11: "noyabr", 12: "dekabr"}

_cfg = dict(admin_id=0, miniapp_url=lambda: "", ref_link=lambda uid: "", is_banned=lambda u: False,
            optout=lambda u: False, add_credits=None, bot_username=lambda: "")
_PENDING = {}          # uid -> muddat (esse mavzusi matnini kutish)
_TASKS = set()


def configure(**kw):
    _cfg.update({k: v for k, v in kw.items() if v is not None})


# ----------------------------------------------------------------------------- vaqt / slotlar
def now_tk():
    return datetime.now(TZ)


def slot_codes():
    return [f"{d}-{s}" for d in DAYS for s in (1, 2)]


def parse_slot(code):
    try:
        d, s = str(code).split("-"); d = int(d); s = int(s)
        if d in DAYS and s in SHIFTS:
            return date(YEAR, MONTH, d), s
    except Exception:
        pass
    return None


def slot_label(code):
    p = parse_slot(code)
    if not p:
        return "Keyinroq topshiraman"
    d, s = p
    return f"{d.day}-{MONTH_UZ[d.month]} • {SHIFTS[s]['name']}"


def _at(d, hm):
    return datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=TZ)


def windows(code):
    """kind -> (boshlanish, tugash). Bot qayta ishga tushsa ham, oyna ichida bo'lsa yuboriladi."""
    d, s = parse_slot(code)
    sh = SHIFTS[s]
    mid = _at(d, (0, 0))
    return {
        "eve": (_at(d - timedelta(days=1), (20, 0)), mid),
        "morning": (_at(d, sh["morning"]), _at(d, sh["enter"])),
        "after": (_at(d, sh["after"]), _at(d + timedelta(days=1), (10, 0))),
        "late": (_at(d + timedelta(days=1), (10, 0)), _at(d + timedelta(days=1), (22, 0))),
    }


def slot_end(code):
    d, s = parse_slot(code)
    return _at(d, SHIFTS[s]["exit"])


def enter_text(code):
    d, s = parse_slot(code)
    h, m = SHIFTS[s]["enter"]
    return f"{h:02d}:{m:02d}"


def arrive_text(code):
    d, s = parse_slot(code)
    t = _at(d, SHIFTS[s]["enter"]) - timedelta(minutes=ARRIVE_BEFORE_MIN)
    return t.strftime("%H:%M")


def days_left(code, now=None):
    d, _ = parse_slot(code)
    return (d - (now or now_tk()).date()).days


# ----------------------------------------------------------------------------- baza
def init():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS exam_slot(user_id INTEGER PRIMARY KEY, slot TEXT NOT NULL, chosen_at TEXT, updated_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS exam_sent(user_id INTEGER NOT NULL, kind TEXT NOT NULL, at TEXT, PRIMARY KEY(user_id,kind))")
        c.execute("CREATE TABLE IF NOT EXISTS exam_fb(user_id INTEGER PRIMARY KEY, how TEXT, topics TEXT DEFAULT '', essay TEXT, rewarded INTEGER DEFAULT 0, updated_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS exam_q(user_id INTEGER NOT NULL, qno INTEGER NOT NULL, qtext TEXT, ans TEXT, skipped INTEGER DEFAULT 0, updated_at TEXT, PRIMARY KEY(user_id,qno))")
        c.execute("CREATE TABLE IF NOT EXISTS exam_pub(id INTEGER PRIMARY KEY AUTOINCREMENT, slot TEXT, src_user INTEGER, src_qno INTEGER, name TEXT, question TEXT, answer TEXT, status TEXT DEFAULT 'draft', created_at TEXT, updated_at TEXT)")
        for _col in ("opts TEXT", "explain TEXT"):
            try: c.execute("ALTER TABLE exam_pub ADD COLUMN " + _col)
            except Exception: pass
        c.execute("CREATE TABLE IF NOT EXISTS exam_vote(user_id INTEGER NOT NULL, pub_id INTEGER NOT NULL, letter TEXT, at TEXT, PRIMARY KEY(user_id,pub_id))")
        c.execute("CREATE TABLE IF NOT EXISTS exam_anon(user_id INTEGER PRIMARY KEY, n INTEGER NOT NULL)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_exam_pub_src ON exam_pub(src_user,src_qno) WHERE src_user IS NOT NULL")
        c.execute("CREATE TABLE IF NOT EXISTS exam_survey_log(user_id INTEGER NOT NULL, kind TEXT NOT NULL, ok INTEGER, at TEXT, PRIMARY KEY(user_id,kind))")
        c.execute("CREATE TABLE IF NOT EXISTS exam_kv(k TEXT PRIMARY KEY, v TEXT)")
        # v101: savol klasterlari (bir xil savollar bitta qatorda), obuna kutayotgan savol havolasi
        c.execute("CREATE TABLE IF NOT EXISTS exam_qc(id INTEGER PRIMARY KEY AUTOINCREMENT, qno INTEGER NOT NULL, slot TEXT, stem TEXT, opts TEXT, created_at TEXT, updated_at TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_exam_qc_qno ON exam_qc(qno)")
        c.execute("CREATE TABLE IF NOT EXISTS exam_pendq(user_id INTEGER PRIMARY KEY, qid INTEGER NOT NULL, at TEXT)")
        for _t, _col in (("exam_q", "cid INTEGER"), ("exam_pub", "cid INTEGER")):
            try: c.execute(f"ALTER TABLE {_t} ADD COLUMN " + _col)
            except Exception: pass
        c.execute("CREATE INDEX IF NOT EXISTS ix_exam_q_cid ON exam_q(cid)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_exam_q_qno ON exam_q(qno)")
        c.commit()
    try:
        migrate_legacy()
    except Exception:
        log.exception("migrate_legacy")


def _iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def get_slot(uid):
    with db() as c:
        r = c.execute("SELECT slot FROM exam_slot WHERE user_id=?", (int(uid),)).fetchone()
    return r[0] if r else None


def set_slot(uid, code):
    with db() as c:
        c.execute("INSERT INTO exam_slot(user_id,slot,chosen_at,updated_at) VALUES(?,?,?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET slot=excluded.slot, updated_at=excluded.updated_at",
                  (int(uid), code, _iso(), _iso()))
        c.commit()


def get_fb(uid):
    with db() as c:
        r = c.execute("SELECT how,topics,essay,rewarded FROM exam_fb WHERE user_id=?", (int(uid),)).fetchone()
    return dict(how=r[0], topics=r[1] or "", essay=r[2], rewarded=int(r[3] or 0)) if r else None


def _fb_upsert(uid, **kw):
    cur = get_fb(uid) or dict(how=None, topics="", essay=None, rewarded=0)
    cur.update(kw)
    with db() as c:
        c.execute("INSERT INTO exam_fb(user_id,how,topics,essay,rewarded,updated_at) VALUES(?,?,?,?,?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET how=excluded.how, topics=excluded.topics, essay=excluded.essay, "
                  "rewarded=excluded.rewarded, updated_at=excluded.updated_at",
                  (int(uid), cur["how"], cur["topics"], cur["essay"], int(cur["rewarded"]), _iso()))
        c.commit()


def user_name(uid):
    try:
        with db() as c:
            r = c.execute("SELECT first_name FROM users WHERE user_id=?", (int(uid),)).fetchone()
        n = (r[0] or "").strip() if r else ""
        return n[:20] if n else "do‘stim"
    except Exception:
        return "do‘stim"


# ----------------------------------------------------------------------------- rasm kartalari
PALETTES = {
    "survey":  ((12, 30, 80), (47, 111, 237), (255, 200, 60)),
    "confirm": ((6, 70, 56), (16, 185, 129), (255, 222, 89)),
    "eve":     ((26, 22, 70), (109, 40, 217), (255, 224, 130)),
    "morning": ((120, 40, 16), (234, 88, 12), (255, 214, 64)),
    "after":   ((4, 44, 58), (14, 165, 164), (255, 255, 255)),
    "shared":  ((46, 40, 120), (219, 39, 119), (255, 214, 64)),
}
W, H = 1080, 1350
try:                                    # v101: BBA uslubidagi kartalar (cards_bba.py / assets bo'lmasa yoki xato bersa eski kartaga qaytadi)
    from cards_bba import make_card_bba
except Exception:
    make_card_bba = None


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _fit(draw, text, path, max_w, start, minimum=40):
    size = start
    while size > minimum:
        f = _font(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 4
    return _font(path, minimum)


def _gradient(top, bottom):
    col = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        col.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return col.resize((W, H))


def _center(draw, text, y, font, fill, shadow=True):
    w = draw.textlength(text, font=font)
    x = (W - w) / 2
    if shadow:
        draw.text((x + 3, y + 4), text, font=font, fill=(0, 0, 0, 70))
    draw.text((x, y), text, font=font, fill=fill)


def _icon(draw, kind, cx, cy, accent):
    white = (255, 255, 255, 255)
    if kind == "survey":      # taqvim
        x0, y0, x1, y1 = cx - 150, cy - 140, cx + 150, cy + 150
        draw.rounded_rectangle((x0, y0, x1, y1), 36, fill=white)
        draw.rounded_rectangle((x0, y0, x1, y0 + 80), 36, fill=accent + (255,))
        draw.rectangle((x0, y0 + 50, x1, y0 + 80), fill=accent + (255,))
        for rx in (x0 + 60, x1 - 60):
            draw.rounded_rectangle((rx - 10, y0 - 28, rx + 10, y0 + 32), 10, fill=(255, 255, 255, 255))
        for r in range(3):
            for c_ in range(4):
                bx, by = x0 + 40 + c_ * 62, y0 + 110 + r * 52
                col = accent + (255,) if (r, c_) == (1, 2) else (205, 214, 235, 255)
                draw.rounded_rectangle((bx, by, bx + 40, by + 34), 8, fill=col)
    elif kind == "eve":       # oy va yulduzlar
        draw.ellipse((cx - 130, cy - 130, cx + 130, cy + 130), fill=accent + (255,))
        draw.ellipse((cx - 70, cy - 160, cx + 190, cy + 100), fill=(60, 30, 140, 255))
        for dx, dy, r in ((-190, -90, 10), (170, -170, 8), (200, 60, 12), (-120, 150, 8)):
            draw.ellipse((cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r), fill=white)
    elif kind == "morning":   # quyosh
        for i in range(12):
            import math
            a = i * math.pi / 6
            draw.line((cx + 140 * math.cos(a), cy + 140 * math.sin(a), cx + 200 * math.cos(a), cy + 200 * math.sin(a)),
                      fill=accent + (255,), width=18)
        draw.ellipse((cx - 105, cy - 105, cx + 105, cy + 105), fill=accent + (255,))
    elif kind in ("after", "shared"):   # tasdiq belgisi
        draw.ellipse((cx - 150, cy - 150, cx + 150, cy + 150), fill=white)
        draw.line((cx - 70, cy + 5, cx - 20, cy + 60), fill=PALETTES[kind][1] + (255,), width=34)
        draw.line((cx - 24, cy + 62, cx + 78, cy - 62), fill=PALETTES[kind][1] + (255,), width=34)


def _ring(draw, cx, cy, number, accent):
    r = 190
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 90), width=14)
    draw.arc((cx - r, cy - r, cx + r, cy + r), -90, 200, fill=accent + (255,), width=18)
    f = _font(FONT_NUM, 230)
    t = str(number)
    w = draw.textlength(t, font=f)
    draw.text((cx - w / 2, cy - 150), t, font=f, fill=(255, 255, 255, 255))
    f2 = _font(FONT_B, 44)
    t2 = "kun qoldi" if number != 0 else "bugun!"
    w2 = draw.textlength(t2, font=f2)
    draw.text((cx - w2 / 2, cy + 85), t2, font=f2, fill=accent + (255,))


def _wrap_center(draw, lines, y, path, max_w, start, fill, gap=14):
    for ln in lines:
        f = _fit(draw, ln, path, max_w, start)
        _center(draw, ln, y, f, fill)
        y += int(f.size * 1.18) + gap
    return y


def make_card(kind, name="", label="", number=None, sub="", bot_username=""):
    """Kartani JPEG baytlari sifatida qaytaradi. kind: survey|confirm|eve|morning|after|shared."""
    top, bottom, accent = PALETTES[kind]
    img = _gradient(top, bottom).convert("RGBA")
    rnd = random.Random(f"{kind}{name}{label}")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for _ in range(5):                       # yumshoq yarim shaffof doiralar
        r = rnd.randint(140, 340)
        x, y = rnd.randint(-100, W + 100), rnd.randint(-100, H + 100)
        od.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rnd.randint(10, 24)))
    for _ in range(36):                      # mayda yulduzchalar
        x, y, r = rnd.randint(30, W - 30), rnd.randint(30, H - 30), rnd.randint(2, 5)
        od.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rnd.randint(50, 130)))
    img = Image.alpha_composite(img, ov)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # barcha chizmalar shu qatlamda: yarim shaffoflik to'g'ri aralashadi
    d = ImageDraw.Draw(layer)
    white = (255, 255, 255, 255)

    # yuqori yorliq
    tag = "MILLIY SERTIFIKAT  •  ONA TILI"
    ft = _font(FONT_B, 30)
    tw = d.textlength(tag, font=ft)
    d.rounded_rectangle(((W - tw) / 2 - 34, 70, (W + tw) / 2 + 34, 70 + 62), 31, fill=(255, 255, 255, 40))
    d.text(((W - tw) / 2, 86), tag, font=ft, fill=white)

    cy_icon = 420
    if kind in ("confirm",):
        _ring(d, W // 2, cy_icon, number if number is not None else 0, accent)
    else:
        _icon(d, kind, W // 2, cy_icon, accent)

    heads = {
        "survey":  ["Imtihoningiz", "qaysi kuni?"],
        "confirm": ["Qabul qilindi,", (name or "do‘stim") + "!"],
        "eve":     ["Ertaga", "imtihon!"],
        "morning": ["Omad,", (name or "do‘stim") + "!"],
        "after":   ["Imtihon", "tugadi!"],
        "shared":  ["Men imtihon", "topshirdim!"],
    }[kind]
    y = _wrap_center(d, heads, 690, FONT_B, W - 140, 104, white)
    if sub:
        for ln in sub.split("\n"):
            f = _fit(d, ln, FONT_R, W - 160, 46, 28)
            _center(d, ln, y + 6, f, (255, 255, 255, 225), shadow=False)
            y += int(f.size * 1.35)
    if label:                                 # pastki "chip"
        fl = _fit(d, label, FONT_B, W - 200, 52, 32)
        lw = d.textlength(label, font=fl)
        cy = H - 190
        d.rounded_rectangle(((W - lw) / 2 - 44, cy, (W + lw) / 2 + 44, cy + 96), 48, fill=accent + (255,))
        dark = (30, 30, 40, 255) if kind != "after" else (4, 44, 58, 255)
        d.text(((W - lw) / 2, cy + 20), label, font=fl, fill=dark)
    foot = f"t.me/{bot_username}" if bot_username else "Ona tili va adabiyot • tayyorgarlik boti"
    ff = _font(FONT_R, 30)
    _center(d, foot, H - 70, ff, (255, 255, 255, 190), shadow=False)

    img = Image.alpha_composite(img, layer)
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=88, optimize=True)
    return out.getvalue()


# ----------------------------------------------------------------------------- tugmalar / matnlar
def _e(x):
    return html.escape(str(x), quote=False)


def survey_markup():
    rows = []
    for d in DAYS:
        rows.append([InlineKeyboardButton(f"{d}-{MONTH_UZ[MONTH][:3]}. • I smena", callback_data=f"ex_s_{d}_1"),
                     InlineKeyboardButton(f"{d}-{MONTH_UZ[MONTH][:3]}. • II smena", callback_data=f"ex_s_{d}_2")])
    rows.append([InlineKeyboardButton("⏳ Keyinroq topshiraman", callback_data="ex_s_later")])
    return InlineKeyboardMarkup(rows)


def survey_caption(name):
    s1, s2 = SHIFTS[1], SHIFTS[2]
    return (f"🎓 <b>{_e(name)}, imtihoningiz qaysi kuni?</b>\n\n"
            "Kuningizni tanlang — biz sizga:\n"
            "✅ imtihon kuni <b>omad kartasi</b> va xotirjamlik maslahatlari\n"
            "✅ aynan <b>o‘z smenangizga</b> mos vaqtda eslatmalar\n"
            "✅ imtihondan keyin <b>mavzular statistikasi</b> yuboramiz\n\n"
            f"🕖 I smena: {s1['enter'][0]:02d}:{s1['enter'][1]:02d} dan   •   "
            f"🕐 II smena: {s2['enter'][0]:02d}:{s2['enter'][1]:02d} dan\n\n"
            "👇 Sana va smenangizni tanlang:")


def _app_button(text):
    url = _cfg["miniapp_url"]()
    return [InlineKeyboardButton(text, web_app=WebAppInfo(url=url))] if url else None


def confirm_caption(name, code):
    n = days_left(code)
    left = "<b>bugun</b>" if n <= 0 else f"<b>{n} kun</b>"
    return (f"✅ <b>Qabul qilindi, {_e(name)}!</b>\n\n"
            f"📅 {slot_label(code)}\n⏱ Kirish: <b>{enter_text(code)}</b>\n⏳ Imtihongacha: {left}\n\n"
            "Siz uchun eslatmalar o‘z vaqtida keladi. Hozircha yengil takrorlab turing — kuniga 10 daqiqa ham foyda beradi 💙")


def eve_caption(name, code):
    return (f"🌙 <b>{_e(name)}, ertaga katta kun!</b>\n\n"
            f"Siz <b>{slot_label(code)}</b> da topshirasiz — kirish soat <b>{enter_text(code)}</b>.\n\n"
            "✅ <b>Bugun kechqurun:</b>\n"
            "• 🛂 <b>Pasportingizni</b> tayyorlab qo‘ying\n"
            f"• ⏰ Imtihon boshlanishidan kamida <b>1 soat oldin</b> — <b>{arrive_text(code)}</b> gacha — joyida bo‘ling\n"
            "• Yangi mavzu boshlamang — faqat yengil takrorlang (15–20 daqiqa)\n"
            "• Telefonni erta qo‘yib, kamida <b>7 soat uxlang</b>\n"
            "• Yo‘lga chiqish vaqtini hisoblab, yo‘lda zaxira vaqt qoldiring\n\n"
            "Siz tayyorgarlik ko‘rdingiz. Tinch bo‘ling 💙")


def morning_caption(name, code):
    return (f"☀️ <b>Xayrli tong, {_e(name)}!</b>\n\n"
            f"Bugun soat <b>{enter_text(code)}</b> da imtihon. Kamida 1 soat oldin — <b>{arrive_text(code)}</b> gacha — yetib boring. "
            "🛂 Pasportingiz yoningizdami?\n\n"
            f"{_e(DUA)}\n\n"
            "💡 <b>Imtihonda 5 ta maslahat:</b>\n"
            "1. Avval barcha savolni ko‘zdan kechiring, oson savollardan boshlang\n"
            "2. Bitta savolga yopishib qolmang — keyinga qoldirib, qaytib keling\n"
            "3. Essega <b>1 soatdan ko‘p vaqt</b> ajrating; avval 5 daqiqa reja: kirish → 2–3 dalil → xulosa\n"
            "4. Qog‘oz javoblar varag‘ida hech bir savol belgilanmay qolmaganini topshirishdan oldin tekshiring\n"
            "5. Chuqur nafas oling — xotirjamlik ballni oshiradi\n\n"
            f"Omad, {_e(name)}! 🍀 Chiqqach yozing — qanday o‘tganini bilmoqchimiz.")


def after_caption(name):
    return (f"🎓 <b>{_e(name)}, imtihon tugadi — tabriklaymiz!</b>\n\n"
            "Eng og‘ir qism ortda qoldi. Qanday o‘tdi?\n\n"
            "📋 Esingizda qolgan savollarni yuborsangiz, testni birgalikda <b>to‘liq tiklaymiz</b> va natijangizni <b>birinchilardan bo‘lib</b> bilasiz.")


def how_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("😊 Yaxshi", callback_data="ex_h_g"),
                                  InlineKeyboardButton("😐 O‘rtacha", callback_data="ex_h_m"),
                                  InlineKeyboardButton("😓 Qiyin", callback_data="ex_h_h")],
                                 [InlineKeyboardButton("📋 Eslagan savollarimni yuboraman", callback_data="ex_q_start")]])


def topics_markup(selected):
    sel = {int(x) for x in selected.split(",") if x.strip().isdigit()}
    rows, row = [], []
    for i, t in enumerate(TOPICS):
        row.append(InlineKeyboardButton(("✅ " if i in sel else "▫️ ") + t, callback_data=f"ex_t_{i}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✔️ Tayyor", callback_data="ex_t_done")])
    return InlineKeyboardMarkup(rows)


TOPICS_TEXT = ("📝 <b>Qaysi mavzulardan savollar tushdi?</b>\n"
               "Bir nechtasini tanlang. Bu keyingi nomzodlarga yordam beradi.\n\n"
               "<i>Savollarning o‘zini yozmang — faqat mavzu nomini belgilang.</i>")

HOW_REPLY = {"g": "😊 Yaxshi", "m": "😐 O‘rtacha", "h": "😓 Qiyin"}


# ----------------------------------------------------------------------------- yuborish yordamchilari
async def _send_photo(bot, uid, jpeg, caption, markup=None):
    return await bot.send_photo(chat_id=int(uid), photo=InputFile(io.BytesIO(jpeg), filename="card.jpg"),
                                caption=caption[:1024], parse_mode="HTML", reply_markup=markup)


async def _safe(coro_fn, retries=2):
    """RetryAfter bo'lsa kutib qayta urinadi. (ok, 'forbidden'|'err'|None) qaytaradi."""
    for _ in range(retries + 1):
        try:
            await coro_fn()
            return True, None
        except RetryAfter as e:
            ra = getattr(e, "retry_after", 3)
            try: ra = ra.total_seconds()          # PTB 21+ da timedelta bo'lishi mumkin
            except AttributeError: pass
            await asyncio.sleep(float(ra) + 1)
        except Forbidden:
            return False, "forbidden"
        except BadRequest as e:
            log.info("badrequest %s", e)
            return False, "forbidden" if "chat not found" in str(e).lower() else "err"
        except Exception:
            log.exception("exam_flow send")
            return False, "err"
    return False, "err"


_survey_cache = {}


def survey_card():
    if "j" not in _survey_cache:
        _survey_cache["j"] = make_card("survey", label=" • ".join(str(x) for x in DAYS) + f"-{MONTH_UZ[MONTH]}",
                                       sub="Kuningizni tanlang —\no‘z vaqtida eslatib, omad tilaymiz",
                                       bot_username=_cfg["bot_username"]())
    return _survey_cache["j"]


async def _card3d_or_old(kind, name, label, sub, bu):
    """eve | morning | after kartalari BBA uslubida (nomi tarixiy). label — pastdagi oltin yorliq."""
    if make_card_bba is not None and kind in ("eve", "morning", "after"):
        try:
            return await asyncio.to_thread(make_card_bba, kind, name, label, bu)
        except Exception:
            log.exception("card bba")
    return await asyncio.to_thread(make_card, kind, name, label, None, sub, bu)


DUA_MSG = os.getenv("EXAM_DUA_MSG", "1") != "0"
DUA_FULL = os.getenv("EXAM_DUA_FULL", "") .replace("\\n", "\n")


def dua_message():
    """Imtihon oldidan o'qiladigan duolar (EXAM_DUA_FULL bilan butunlay almashtirsa bo'ladi)."""
    if DUA_FULL.strip():
        return _e(DUA_FULL)
    return ("🤲 <b>Imtihon oldidan duolar</b>\n\n"
            "<b>1.</b> Kirishdan oldin: <i>«Bismillahir rohmanir rohiym»</i>\n\n"
            "<b>2.</b> (Toha surasi, 25–28)\n"
            "رَبِّ اشْرَحْ لِي صَدْرِي * وَيَسِّرْ لِي أَمْرِي * وَاحْلُلْ عُقْدَةً مِّن لِّسَانِي * يَفْقَهُوا قَوْلِي\n"
            "<i>Robbishrah lii sodrii, va yassir lii amrii, vahlul uqdatam min lisaanii, yafqohu qoulii.</i>\n"
            "Ma’nosi: «Ey Robbim, ko‘ksimni kengaytir, ishimni oson qil, tilimdagi tugunni yech — so‘zimni tushunsinlar».\n\n"
            "<b>3.</b> (Toha surasi, 114)\n"
            "رَّبِّ زِدْنِي عِلْمًا\n"
            "<i>Robbi zidnii ilmaa.</i> — «Ey Robbim, ilmimni ziyoda qil».\n\n"
            "<b>4.</b> Qiyin savolda:\n"
            "اللَّهُمَّ لَا سَهْلَ إِلَّا مَا جَعَلْتَهُ سَهْلًا وَأَنْتَ تَجْعَلُ الْحَزْنَ إِذَا شِئْتَ سَهْلًا\n"
            "<i>Allohumma laa sahla illaa maa ja’altahu sahlaa, va anta taj’alul hazna izaa shi’ta sahlaa.</i>\n"
            "«Ey Alloh, Sen oson qilganingdan boshqa oson narsa yo‘q; xohlasang, mushkulni ham oson qilasan».\n\n"
            "<b>5.</b> (Kahf surasi, 10)\n"
            "رَبَّنَا آتِنَا مِن لَّدُنكَ رَحْمَةً وَهَيِّئْ لَنَا مِنْ أَمْرِنَا رَشَدًا\n"
            "<i>Robbanaa aatinaa min ladunka rahmatan va hayyi’ lanaa min amrinaa rashadaa.</i>\n"
            "«Ey Robbimiz, bizga O‘z huzuringdan rahmat ber va ishimizni to‘g‘ri yo‘lga yo‘nalt».\n\n"
            "Alloh taolo yuzingizni yorug‘ qilsin, omad! 🍀")


async def send_kind(bot, uid, kind, code=None):
    """kind: survey | confirm | eve | morning | after."""
    name = user_name(uid)
    bu = _cfg["bot_username"]()
    if kind == "survey":
        return await _send_photo(bot, uid, survey_card(), survey_caption(name), survey_markup())
    label = slot_label(code)
    if kind == "confirm":
        jpeg = await asyncio.to_thread(make_card, "confirm", name, label, max(0, days_left(code)),
                                       "Eslatmalar o‘z vaqtida keladi", bu)
        rows = [[InlineKeyboardButton("✏️ Sanani o‘zgartirish", callback_data="ex_chg")]]
        ab = _app_button("⚡ Tezkor takrorlash")
        if ab: rows.insert(0, ab)
        return await _send_photo(bot, uid, jpeg, confirm_caption(name, code), InlineKeyboardMarkup(rows))
    if kind == "eve":
        jpeg = await _card3d_or_old("eve", name, f"{label} • {enter_text(code)}", f"{name}, bugun erta yoting", bu)
        rows = []
        ab = _app_button("⚡ 10 daqiqalik yengil takrorlash")
        if ab: rows.append(ab)
        return await _send_photo(bot, uid, jpeg, eve_caption(name, code), InlineKeyboardMarkup(rows) if rows else None)
    if kind == "morning":
        jpeg = await _card3d_or_old("morning", name, f"{label} • {enter_text(code)}", "Siz tayyorsiz. Ishonch bilan kiring!", bu)
        res = await _send_photo(bot, uid, jpeg, morning_caption(name, code))
        if DUA_MSG:                                  # duolar alohida xabar (rasm izohi 1024 belgi bilan cheklangan)
            try: await bot.send_message(chat_id=int(uid), text=dua_message(), parse_mode="HTML")
            except Exception: log.debug("dua msg", exc_info=True)
        return res
    if kind == "after":
        jpeg = await _card3d_or_old("after", name, "Savol yuboring — natijani biling", f"{name}, siz buni uddaladingiz", bu)
        return await _send_photo(bot, uid, jpeg, after_caption(name), how_markup())
    raise ValueError(kind)


# ----------------------------------------------------------------------------- jadval (scheduler)
def _due_users(code, kind, limit=400):
    with db() as c:
        if kind == "late":
            rows = c.execute("SELECT s.user_id FROM exam_slot s WHERE s.slot=? "
                             "AND s.user_id NOT IN (SELECT user_id FROM exam_sent WHERE kind='late') "
                             "AND s.user_id NOT IN (SELECT user_id FROM exam_fb WHERE how IS NOT NULL) LIMIT ?", (code, limit)).fetchall()
        else:
            rows = c.execute("SELECT s.user_id FROM exam_slot s WHERE s.slot=? "
                             "AND s.user_id NOT IN (SELECT user_id FROM exam_sent WHERE kind=?) LIMIT ?", (code, kind, limit)).fetchall()
    return [int(r[0]) for r in rows]


def _mark_sent(uid, kind):
    with db() as c:
        c.execute("INSERT OR IGNORE INTO exam_sent(user_id,kind,at) VALUES(?,?,?)", (int(uid), kind, _iso()))
        c.commit()


async def tick(bot, now=None):
    """Bir o'tish: oynasi ochiq barcha (slot, kind) uchun yuborilmaganlarga yuboradi. Yuborilganlar sonini qaytaradi."""
    now = now or now_tk()
    sent = 0
    for code in slot_codes():
        for kind, (a, b) in windows(code).items():
            if not (a <= now < b):
                continue
            for uid in _due_users(code, kind):
                try:
                    if _cfg["is_banned"](uid) or _cfg["optout"](uid):
                        _mark_sent(uid, kind); continue
                except Exception:
                    pass
                if kind == "late":
                    name = user_name(uid)
                    ok, why = await _safe(lambda: bot.send_message(
                        chat_id=uid, parse_mode="HTML",
                        text=(f"👋 <b>{_e(name)}</b>, imtihon qanday o‘tdi?\n\n"
                              "Bir daqiqa ajrating — javobingiz keyingi nomzodlarga yordam beradi va sizga sovg‘a ham bor 🎁"),
                        reply_markup=how_markup()))
                else:
                    ok, why = await _safe(lambda: send_kind(bot, uid, kind, code))
                if ok or why == "forbidden":
                    _mark_sent(uid, kind)
                    sent += 1 if ok else 0
                await asyncio.sleep(0.06)
    try:
        await flush_dups(bot)                          # takroriy savollar Word fayli (yetarli yig'ilganda)
    except Exception:
        log.exception("flush_dups")
    # har smena tugaganidan 2 soat keyin adminga jamlangan savollar fayli (bir marta)
    for code in slot_codes():
        a = slot_end(code) + timedelta(hours=2)
        if a <= now < a + timedelta(hours=20):
            with db() as c:
                done = c.execute("SELECT 1 FROM exam_sent WHERE user_id=0 AND kind=?", (f"adm_{code}",)).fetchone()
            if not done:
                try:
                    n = await _send_export(bot, _cfg["admin_id"], slot=code, caption=f"📋 {slot_label(code)} — jamlangan savollar")
                    if n: _mark_sent(0, f"adm_{code}")
                except Exception:
                    log.exception("admin export")
    return sent


async def auto_survey_tick(bot, now=None):
    """Yangi kirgan (hali sana tanlamagan va so'rovnoma olmagan) foydalanuvchiga so'rovnomani o'zi yuboradi.
    Xavfsizlik: faqat funksiya birinchi ishga tushgan paytdan (yoki EXAM_AUTO_FROM dan) KEYIN kirganlarga —
    eski foydalanuvchilarga kutilmaganda ommaviy yuborilmaydi (ular uchun admin /sorov_yubor tasdiq).
    Oxirgi imtihon kuni o'tgach to'xtaydi."""
    if not AUTO_SURVEY or not DAYS:
        return 0
    now = now or now_tk()
    if now.date() > date(YEAR, MONTH, max(DAYS)):
        return 0
    with db() as c:
        since = AUTO_FROM
        if not since:
            row = c.execute("SELECT v FROM exam_kv WHERE k='auto_since'").fetchone()
            if row:
                since = row[0]
            else:
                since = _iso()
                c.execute("INSERT OR IGNORE INTO exam_kv(k,v) VALUES('auto_since',?)", (since,)); c.commit()
        upto = (datetime.utcnow() - timedelta(minutes=AUTO_DELAY_MIN)).isoformat(timespec="seconds") + "Z"
        rows = c.execute("SELECT user_id FROM users WHERE joined_at>=? AND joined_at<=? "
                         "AND user_id NOT IN (SELECT user_id FROM exam_survey_log) "
                         "AND user_id NOT IN (SELECT user_id FROM exam_slot) ORDER BY joined_at LIMIT ?",
                         (since, upto, AUTO_BATCH)).fetchall()
    sent = 0
    for (uid,) in rows:
        uid = int(uid)
        if uid == _cfg["admin_id"] or _cfg["is_banned"](uid) or _cfg["optout"](uid):
            with db() as c:
                c.execute("INSERT OR IGNORE INTO exam_survey_log(user_id,kind,ok,at) VALUES(?,?,?,?)", (uid, "auto_skip", 0, _iso())); c.commit()
            continue
        r, why = await _safe(lambda: send_kind(bot, uid, "survey"))
        with db() as c:
            c.execute("INSERT OR REPLACE INTO exam_survey_log(user_id,kind,ok,at) VALUES(?,?,?,?)", (uid, "survey", 1 if r else 0, _iso())); c.commit()
        sent += 1 if r else 0
        await asyncio.sleep(0.05)
    return sent


async def scheduler_loop(bot):
    if not ENABLED:
        log.info("exam_flow o'chirilgan (EXAM_FLOW=0)"); return
    await asyncio.sleep(45)
    while True:
        try:
            n = await tick(bot)
            if n: log.info("exam_flow: %s ta xabar yuborildi", n)
            m = await auto_survey_tick(bot)
            if m: log.info("exam_flow: %s ta yangi foydalanuvchiga so'rovnoma yuborildi", m)
        except Exception:
            log.exception("exam_flow tick")
        await asyncio.sleep(60)


# ----------------------------------------------------------------------------- foydalanuvchi callbacklari
async def slot_cb(update, context):
    q = update.callback_query; uid = q.from_user.id; d = q.data or ""
    if d == "ex_chg":
        await q.answer()
        await context.bot.send_message(uid, "📅 Imtihon sanangizni qayta tanlang:", reply_markup=survey_markup())
        return
    if d == "ex_s_later":
        await q.answer("Mayli 🙂")
        set_slot(uid, "later")
        try: await q.edit_message_reply_markup(reply_markup=None)
        except Exception: pass
        await context.bot.send_message(uid, "👌 Yaxshi, vaqti aniq bo‘lganda <b>/imtihon</b> deb yozib sanani belgilashingiz mumkin. "
                                            "Hozircha mashq qilib turing — tayyorgarlik hech qachon ortiqcha emas 💙", parse_mode="HTML")
        return
    parts = d.split("_")
    code = f"{parts[2]}-{parts[3]}" if len(parts) == 4 else ""
    if not parse_slot(code):
        await q.answer(); return
    set_slot(uid, code)
    await q.answer("✅ Saqlandi")
    try: await q.edit_message_reply_markup(reply_markup=None)
    except Exception: pass
    await _safe(lambda: send_kind(context.bot, uid, "confirm", code))


async def imtihon_cmd(update, context):
    """/imtihon — foydalanuvchi sanani o'zi belgilaydi yoki o'zgartiradi."""
    uid = update.effective_user.id
    cur = get_slot(uid)
    txt = "📅 <b>Imtihoningiz qaysi kuni?</b>"
    if cur and cur != "later":
        txt += f"\nHozirgi tanlov: <b>{slot_label(cur)}</b>"
    await update.message.reply_text(txt, parse_mode="HTML", reply_markup=survey_markup())


def _ended(uid):
    if uid == _cfg["admin_id"]:
        return True
    code = get_slot(uid)
    return bool(code and parse_slot(code) and now_tk() >= slot_end(code))


async def how_cb(update, context):
    q = update.callback_query; uid = q.from_user.id; k = (q.data or "")[-1]
    if k not in HOW_REPLY:
        await q.answer(); return
    if not _ended(uid):
        await q.answer("Imtihon tugagach javob bering 🙂", show_alert=True); return
    await q.answer()
    _fb_upsert(uid, how=k)
    try:
        if q.message.caption:
            await q.edit_message_caption(caption=(q.message.caption + f"\n\nJavobingiz: {HOW_REPLY[k]}")[:1024], reply_markup=None)
        else:
            await q.edit_message_text(text=(q.message.text or "") + f"\n\nJavobingiz: {HOW_REPLY[k]}", reply_markup=None)
    except Exception:
        try: await q.edit_message_reply_markup(reply_markup=None)
        except Exception: pass
    await context.bot.send_message(uid, TOPICS_TEXT, parse_mode="HTML", reply_markup=topics_markup((get_fb(uid) or {}).get("topics", "")))


async def topic_cb(update, context):
    q = update.callback_query; uid = q.from_user.id; arg = (q.data or "")[5:]
    if not _ended(uid):
        await q.answer("Imtihon tugagach javob bering 🙂", show_alert=True); return
    fb = get_fb(uid) or dict(how=None, topics="", essay=None, rewarded=0)
    if arg == "done":
        await q.answer()
        sel = sorted({int(x) for x in fb["topics"].split(",") if x.strip().isdigit()})
        chosen = ", ".join(TOPICS[i] for i in sel if i < len(TOPICS)) or "—"
        try: await q.edit_message_text(f"📝 Tanlangan mavzular: <b>{_e(chosen)}</b>", parse_mode="HTML", reply_markup=None)
        except Exception: pass
        rewarded_now = False
        if REWARD_ESSAYS > 0 and not fb["rewarded"] and _cfg["add_credits"]:
            try:
                _cfg["add_credits"](uid, REWARD_ESSAYS); _fb_upsert(uid, rewarded=1); rewarded_now = True
            except Exception:
                log.exception("exam reward")
        context.user_data["ex_rewarded_now"] = rewarded_now
        _PENDING[uid] = time.time() + 3600
        await context.bot.send_message(
            uid, "✍️ <b>Esse mavzusi nima edi?</b>\nEslaganingizcha bir-ikki jumlada yozib yuboring (ixtiyoriy).",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭ O‘tkazib yuborish", callback_data="ex_e_skip")]]))
        return
    if not arg.isdigit() or int(arg) >= len(TOPICS):
        await q.answer(); return
    sel = {int(x) for x in fb["topics"].split(",") if x.strip().isdigit()}
    sel ^= {int(arg)}
    _fb_upsert(uid, topics=",".join(str(i) for i in sorted(sel)))
    await q.answer()
    try: await q.edit_message_reply_markup(reply_markup=topics_markup(",".join(str(i) for i in sorted(sel))))
    except Exception: pass


async def _finish(bot, uid, rewarded_now):
    fb = get_fb(uid) or {}
    name = user_name(uid)
    how = fb.get("how")
    _PENDING.pop(uid, None)
    if how == "g":
        head = f"🌟 <b>Zo‘r, {_e(name)}!</b> Natijangiz yaxshi bo‘lishiga ishonamiz."
    elif how == "m":
        head = f"💪 <b>{_e(name)}</b>, o‘rtacha o‘tgan bo‘lsa ham — bu imtihon ortda. Natijani xotirjam kuting."
    else:
        head = f"🤝 <b>{_e(name)}</b>, qiyin bo‘lgani tabiiy — ko‘pchilik shunday his qiladi. Natija chiqmaguncha hech narsa hal bo‘lmagan."
    body = head + "\n\nNatijalar e’lon qilinganda sizga xabar beramiz."
    body += ("\n\n📋 <b>Bir iltimos:</b> eslagan savollaringizni raqami bilan yuborib bering (variant yoki savolni to‘liq eslolmasangiz ham bo‘ladi) — shunda:\n"
             "🔑 savollar tekshirilgach to‘g‘ri javoblarni <b>boshqalardan oldin</b> ko‘rasiz\n"
             "📈 taxminiy natijangizni birinchilardan bo‘lib bilasiz\n"
             "🏅 «Savol ovchisi» nishonini olasiz")
    if rewarded_now:
        body += f"\n🎁 Rahmat uchun hisobingizga <b>+{REWARD_ESSAYS} ta bepul esse tekshiruvi</b> qo‘shildi."
    bu = _cfg["bot_username"]()
    link = _cfg["ref_link"](uid)
    rows = []
    if link:
        from urllib.parse import quote
        rows.append([InlineKeyboardButton("📤 Do‘stlarga ulashish", url=f"https://t.me/share/url?url={quote(link, safe='')}&text={quote('Men Milliy sertifikat imtihonini topshirdim! Tayyorgarlik boti:', safe='')}")])
    rows.insert(0, [InlineKeyboardButton("📋 Savol yuborish 🔑", callback_data="ex_q_start")])
    rows.append([InlineKeyboardButton("📊 Tushgan mavzular statistikasi", callback_data="ex_stats")])
    ab = _app_button("🎯 Natijani kutayotganda mashq")
    if ab: rows.append(ab)
    code = get_slot(uid)
    jpeg = await asyncio.to_thread(make_card, "shared", name, slot_label(code) if code and parse_slot(code) else "", None, "Milliy sertifikat • ona tili", bu)
    await _safe(lambda: _send_photo(bot, uid, jpeg, body, InlineKeyboardMarkup(rows)))


async def essay_skip_cb(update, context):
    q = update.callback_query; await q.answer()
    try: await q.edit_message_reply_markup(reply_markup=None)
    except Exception: pass
    await _finish(context.bot, q.from_user.id, bool(context.user_data.pop("ex_rewarded_now", False)))


class _PendingFilter(filters.MessageFilter):
    def filter(self, message):
        u = message.from_user
        if not u or not message.text: return False
        qs = _Q.get(int(u.id))
        if qs:
            if qs["exp"] > time.time(): return True
            _Q.pop(int(u.id), None)
        exp = _PENDING.get(int(u.id))
        if not exp: return False
        if exp < time.time():
            _PENDING.pop(int(u.id), None); return False
        return True


async def essay_text_cb(update, context):
    uid = update.effective_user.id
    if uid in _Q:
        await q_text_cb(update, context); return
    _fb_upsert(uid, essay=(update.message.text or "").strip()[:300])
    await update.message.reply_text("✅ Rahmat, yozib oldik!")
    await _finish(context.bot, uid, bool(context.user_data.pop("ex_rewarded_now", False)))


def topic_stats():
    with db() as c:
        rows = c.execute("SELECT topics FROM exam_fb WHERE how IS NOT NULL AND topics<>''").fetchall()
    n = len(rows); cnt = {}
    for (t,) in rows:
        for x in {int(i) for i in t.split(",") if i.strip().isdigit()}:
            cnt[x] = cnt.get(x, 0) + 1
    return n, cnt


async def stats_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    if not _ended(uid):
        await q.answer("Statistika imtihoningiz tugagach ochiladi 🙂", show_alert=True); return
    await q.answer()
    n, cnt = topic_stats()
    if n < MIN_STATS_N:
        await context.bot.send_message(uid, "📊 Hozircha javoblar kam — statistika yetarli javob yig‘ilgach ko‘rinadi. Qayta urinib ko‘ring 🙂"); return
    lines = [f"📊 <b>Qaysi mavzular tushgan?</b> ({n} kishi javobi)\n"]
    for i, c_ in sorted(cnt.items(), key=lambda x: -x[1]):
        pct = round(100 * c_ / n); bar = "█" * max(1, pct // 10) + "░" * (10 - max(1, pct // 10))
        lines.append(f"{bar} {pct}% — {TOPICS[i]}")
    await context.bot.send_message(uid, "\n".join(lines), parse_mode="HTML")



# ----------------------------------------------------------------------------- v101: savollarni erkin formatda yig'ish
# Foydalanuvchi savollarni RAQAMI bilan bir xabarda (yoki bir nechta xabarda) yuboradi:
#     1. Savol matni
#     A) ...  B) ...  C) ...  D) ...
#     Men A javobni oldim.
#     2. Qabilida            <- faqat bir qismi ham bo'ladi; qolganini keyin shu raqam bilan yuborsa QO'SHILADI
# Bir xil (o'xshash) savollar bazada KO'PAYTIRILMAYDI: har bir savol raqami uchun bitta "klaster" (exam_qc) saqlanadi,
# foydalanuvchiga esa faqat kichik yozuv (user, qno, belgilagan javob, klaster) yoziladi. Takroriy matnlar faylga (spool) yig'ilib,
# yetarli bo'lganda WORD (.docx) sifatida adminga yuboriladi va fayl tozalanadi.
# Qamrov: har bir savol raqami kamida COVER_TARGET kishidan kelguncha so'raladi; yetgach shu savol ro'yxatdan AVTOMATIK tushadi.
_Q = {}      # uid -> {"exp": muddat}  (savol matni kutilmoqda)
ANS = ["A", "B", "C", "D"]
COVER_TARGET = int(os.getenv("EXAM_Q_COVER", "10") or 10)          # har bir savolni kamida shuncha kishi yuborsin
DUP_BATCH = int(os.getenv("EXAM_DUP_BATCH", "100") or 100)          # takroriy matnlar shuncha bo'lganda Word adminga ketadi
DUP_FLUSH_MIN = int(os.getenv("EXAM_DUP_FLUSH_MIN", "90") or 90)    # yoki eng eskisi shuncha daqiqadan oshganda
Q_STATE_MIN = int(os.getenv("EXAM_Q_STATE_MIN", "40") or 40)        # "savol kutilmoqda" holati (har xabarda yangilanadi)
SIM_THRESHOLD = 0.82
SHOW_NEED = 10

_LETMAP = {"A": 0, "B": 1, "C": 2, "D": 3, "a": 0, "b": 1, "c": 2, "d": 3,
           "\u0410": 0, "\u0412": 1, "\u0421": 2, "\u0430": 0, "\u0432": 1, "\u0441": 2}     # kirill A, B, C ham qabul qilinadi
_LET_CLS = "ABCDabcd\u0410\u0412\u0421\u0430\u0432\u0441"
_HDR_RE = re.compile(r"^\s*(\d{1,2})\s*[\.\):\-\u2013\u2014]\s*(.*)$")
_OPTL_RE = re.compile(r"^\s*([" + _LET_CLS + r"])\s*[\)\.:]\s*(.*)$")
_PICK_RES = [
    re.compile(r"(?i)\bmen\s+([a-d\u0430\u0432\u0441])\s*(?:javob|variant)"),
    re.compile(r"(?i)\b(?:javobim|javob|belgilagan(?:im)?|belgiladim)\s*[:\-\u2013]?\s*([a-d\u0430\u0432\u0441])\s*(?:[\.\!]|$)"),
    re.compile(r"(?i)^\s*([a-d\u0430\u0432\u0441])\s*(?:javob(?:ni)?|variant(?:ni)?)\s*(?:oldim|belgiladim|tanladim)"),
]
_APOS = str.maketrans({"\u02bb": "'", "\u02bc": "'", "\u2018": "'", "\u2019": "'", "`": "'", "\u00b4": "'", "\u2032": "'"})
_JUNK = {"bilmayman", "eslolmayman", "eslamayman", "eslamadim", "yoq", "yo'q", "esimda yoq", "esimda yo'q", "hechnima",
         "bilmadim", "savol", "qiyin", "ha", "yo'q esimda", "yoq esimda", "test", "salom"}


def _norm(s):
    s = (s or "").translate(_APOS).lower()
    s = re.sub(r"[^\w']+", " ", s).replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def _clean_opt(t):
    t = (t or "").strip()
    return "" if re.fullmatch(r"[\s\.\u2026_\-\u2013\u2014?]*", t) else t[:200]


def _fmt_q(stem, opts):
    out = (stem or "").strip()
    ol = [f"{L}) {t}" for L, t in zip(ANS, list(opts) + [""] * 4) if t]
    return out + (("\n" + "\n".join(ol)) if ol else "")


def _pick_of(line):
    ln = (line or "").strip()
    if not ln or len(ln) > 70:
        return ""
    for rx in _PICK_RES:
        m = rx.search(ln)
        if m:
            return ANS[_LETMAP[m.group(1)]]
    return ""


def _parse_body(lines):
    stem = []; opts = ["", "", "", ""]; cur = None; pick = ""
    for ln in lines:
        pk = _pick_of(ln)
        if pk:
            pick = pk; continue
        m = _OPTL_RE.match(ln)
        if m:
            cur = _LETMAP[m.group(1)]
            opts[cur] = (opts[cur] + " " + m.group(2)).strip(); continue
        if not ln.strip():
            continue
        if cur is None:
            stem.append(ln.strip())
        else:
            opts[cur] = (opts[cur] + " " + ln.strip()).strip()
    stem_t = " ".join(stem).strip()
    if not any(opts) and stem_t:                       # variantlar bir qatorda yozilgan bo'lishi mumkin: "A) x B) y C) z D) w"
        s2, o2 = parse_opts(stem_t)
        if any(o2):
            stem_t, opts = s2, o2
    return stem_t[:600], [_clean_opt(o) for o in opts], pick


def parse_submission(text):
    """Xabardan savollarni ajratadi -> [{qno, stem, opts, pick}]. Sarlavha: «12. matn» yoki «12) matn» (1..TOTAL_Q)."""
    items = []; cur = None
    for ln in (text or "").replace("\r", "").split("\n"):
        m = _HDR_RE.match(ln)
        if m and 1 <= int(m.group(1)) <= TOTAL_Q:
            if cur: items.append(cur)
            cur = {"qno": int(m.group(1)), "lines": [m.group(2)]}
        elif cur is not None:
            cur["lines"].append(ln)
    if cur: items.append(cur)
    out = []
    for it in items[:TOTAL_Q]:
        stem, opts, pick = _parse_body(it["lines"])
        out.append({"qno": it["qno"], "stem": stem, "opts": opts, "pick": pick})
    return out


def validate_item(stem, opts):
    allt = " ".join([stem or ""] + [o for o in opts if o])
    n = _norm(allt)
    if sum(ch.isalpha() for ch in allt) < 4:
        return False, "juda qisqa"
    if n in _JUNK or n.startswith(("eslolmayman", "bilmayman", "eslamayman", "eslamadim")):
        return False, "mazmunsiz"
    if len(set(n.replace(" ", ""))) < 4:
        return False, "mazmunsiz"
    return True, ""


# --- o'xshash savolni topish va birlashtirish
def _opts_conflict(oa, ob):
    from difflib import SequenceMatcher
    for x, y in zip(oa, ob):
        nx, ny = _norm(x), _norm(y)
        if nx and ny and nx != ny and SequenceMatcher(None, nx, ny).ratio() < 0.7:
            return True
    return False


def _same_q(stem_a, opts_a, stem_b, opts_b):
    from difflib import SequenceMatcher
    if _opts_conflict(opts_a, opts_b):
        return False
    na, nb = _norm(stem_a), _norm(stem_b)
    if na and nb:
        if na == nb:
            return True
        short, long_ = (na, nb) if len(na) <= len(nb) else (nb, na)
        if len(short) >= 6 and short in long_:
            return True
        return SequenceMatcher(None, na, nb).ratio() >= SIM_THRESHOLD
    ja = _norm(" ".join(o for o in opts_a if o)); jb = _norm(" ".join(o for o in opts_b if o))
    return bool(ja) and ja == jb                      # savol matni yo'q — variantlar bir xil bo'lsa


def _merge_info(cur_stem, cur_opts, stem, opts):
    s = cur_stem; o = list(cur_opts); changed = False
    ns, nc = _norm(stem), _norm(cur_stem)
    if stem and (not cur_stem or (len(ns) > len(nc) * 1.15 and nc in ns)):
        if stem != cur_stem: s = stem; changed = True
    for i in range(4):
        if not o[i] and opts[i]:
            o[i] = opts[i]; changed = True
    return s, o, changed


def _json_opts(v):
    try:
        o = json.loads(v or "[]")
    except Exception:
        o = []
    return (list(o) + ["", "", "", ""])[:4]


def ingest(uid, qno, stem, opts, pick=""):
    """Bitta savolni qabul qiladi. -> 'new' | 'merged' | 'dup' | 'same'. Takroriy matn bazaga yozilmaydi (faylga yig'iladi)."""
    slot = get_slot(uid)
    slot = slot if slot and parse_slot(slot) else ""
    status = "new"; spool = None
    with db() as c:
        prev = c.execute("SELECT cid,ans FROM exam_q WHERE user_id=? AND qno=?", (int(uid), int(qno))).fetchone()
        match = None
        for r in c.execute("SELECT id,stem,opts FROM exam_qc WHERE qno=? ORDER BY id", (int(qno),)).fetchall():
            if _same_q(stem, opts, r["stem"] or "", _json_opts(r["opts"])):
                match = r; break
        if match:
            cid = match["id"]
            ns, no, changed = _merge_info(match["stem"] or "", _json_opts(match["opts"]), stem, opts)
            if changed:
                c.execute("UPDATE exam_qc SET stem=?,opts=?,updated_at=? WHERE id=?", (ns, json.dumps(no, ensure_ascii=False), _iso(), cid))
                status = "merged"
            elif prev and prev["cid"] == cid:
                status = "same"
            else:
                status = "dup"
                spool = {"t": _iso(), "qno": int(qno), "cid": cid, "slot": slot, "pick": pick, "text": _fmt_q(stem, opts)}
        else:
            cur = c.execute("INSERT INTO exam_qc(qno,slot,stem,opts,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                            (int(qno), slot, stem, json.dumps(opts, ensure_ascii=False), _iso(), _iso()))
            cid = cur.lastrowid
        c.execute("INSERT INTO exam_q(user_id,qno,qtext,ans,skipped,cid,updated_at) VALUES(?,?,NULL,?,0,?,?) "
                  "ON CONFLICT(user_id,qno) DO UPDATE SET qtext=NULL, cid=excluded.cid, skipped=0, "
                  "ans=COALESCE(excluded.ans, ans), updated_at=excluded.updated_at",
                  (int(uid), int(qno), pick or None, cid, _iso()))
        if prev and prev["cid"] and prev["cid"] != cid:      # eski klaster bo'sh qolsa (va nashr qilinmagan bo'lsa) o'chadi
            left = c.execute("SELECT COUNT(*) FROM exam_q WHERE cid=?", (prev["cid"],)).fetchone()[0]
            used = c.execute("SELECT 1 FROM exam_pub WHERE cid=?", (prev["cid"],)).fetchone()
            if not left and not used:
                c.execute("DELETE FROM exam_qc WHERE id=?", (prev["cid"],))
        c.commit()
    if spool:
        _spool_add(spool)
    return status, cid


# --- takroriy matnlar: bazaga emas, faylga -> Word -> admin
def _dup_path():
    from national_certificate import DB_PATH
    return os.path.join(os.path.dirname(os.path.abspath(DB_PATH)) or ".", "exam_dups.jsonl")


def _spool_add(entry):
    try:
        with open(_dup_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        log.exception("dup spool")


def spool_count():
    try:
        with open(_dup_path(), encoding="utf-8") as f:
            return sum(1 for ln in f if ln.strip())
    except Exception:
        return 0


def _xml(s):
    from xml.sax.saxutils import escape
    return escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(s)))


def _docx_bytes(blocks):
    """Kutubxonasiz minimal .docx. blocks: [(\"h1\"|\"h2\"|\"b\"|\"p\", matn)]. Word va LibreOffice'da ochiladi."""
    import zipfile
    body = []
    for kind, text in blocks:
        parts = []
        for i, ln in enumerate(str(text).split("\n")):
            if i: parts.append("<w:br/>")
            parts.append(f'<w:t xml:space="preserve">{_xml(ln)}</w:t>')
        rpr = "<w:rPr><w:b/></w:rPr>" if kind == "b" else ""
        ppr = {"h1": '<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>', "h2": '<w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'}.get(kind, "")
        body.append(f"<w:p>{ppr}<w:r>{rpr}{''.join(parts)}</w:r></w:p>")
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {ns}><w:body>{"".join(body)}'
           '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
           'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr></w:body></w:document>')
    styles = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {ns}>'
              '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>'
              '<w:pPrDefault><w:pPr><w:spacing w:after="100" w:line="264" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
              '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
              '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
              '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
              '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/>'
              '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>'
              '</w:styles>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    drels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct); z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc); z.writestr("word/styles.xml", styles); z.writestr("word/_rels/document.xml.rels", drels)
    return buf.getvalue()


def build_dup_docx(entries):
    """Takroriy savollar Word fayli: savol raqami bo'yicha, bir xil matnlar «×N» bilan birlashtiriladi."""
    by = {}
    for e in entries:
        key = (int(e.get("qno") or 0), int(e.get("cid") or 0))
        by.setdefault(key, {}).setdefault(_norm(e.get("text", "")), {"text": e.get("text", ""), "n": 0, "picks": {}, "slots": {}})
        g = by[key][_norm(e.get("text", ""))]; g["n"] += 1
        if e.get("pick"): g["picks"][e["pick"]] = g["picks"].get(e["pick"], 0) + 1
        sl = slot_label(e["slot"]) if e.get("slot") and parse_slot(e["slot"]) else "—"
        g["slots"][sl] = g["slots"].get(sl, 0) + 1
    blocks = [("h1", "Takroriy savollar"), ("p", f"Yaratildi: {now_tk().strftime('%d.%m.%Y %H:%M')} • jami yozuv: {len(entries)} ta • "
                                              "Bular bazada saqlanmagan: asosiy (klaster) matni Mini App → Tushgan savollar → «Kelgan savollar» da.")]
    for (qno, cid) in sorted(by):
        blocks.append(("h2", f"{qno}-savol • klaster #{cid}"))
        for g in sorted(by[(qno, cid)].values(), key=lambda x: -x["n"]):
            pk = ", ".join(f"{k}:{v}" for k, v in sorted(g["picks"].items())) or "—"
            sl = ", ".join(f"{k}:{v}" for k, v in sorted(g["slots"].items()))
            blocks.append(("b", f"×{g['n']} marta • belgilagan javoblar: {pk} • smena: {sl}"))
            blocks.append(("p", g["text"]))
    return _docx_bytes(blocks)


async def flush_dups(bot, force=False):
    """Takroriy matnlar yetarli bo'lsa Word qilib adminga yuboradi va faylni tozalaydi. -> yuborilgan yozuvlar soni."""
    path = _dup_path()
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
    except Exception:
        return 0
    n = len(lines)
    if not n:
        return 0
    entries = []
    for ln in lines:
        try: entries.append(json.loads(ln))
        except Exception: pass
    old = False
    try:
        t0 = datetime.fromisoformat(entries[0]["t"].replace("Z", "")); old = (datetime.utcnow() - t0) > timedelta(minutes=DUP_FLUSH_MIN)
    except Exception:
        old = True
    if not (force or n >= DUP_BATCH or old):
        return 0
    data = await asyncio.to_thread(build_dup_docx, entries)
    stamp = now_tk().strftime("%d%m_%H%M")
    ok, _ = await _safe(lambda: bot.send_document(chat_id=_cfg["admin_id"], document=InputFile(io.BytesIO(data), filename=f"takroriy_savollar_{stamp}.docx"),
                                                  caption=f"📄 Takroriy savollar: {n} ta yozuv (bazada saqlanmaydi, shu fayl bilan tozalandi)"))
    if not ok:
        return 0
    try:                                                   # yuborilgan qatorlarni o'chiramiz (shu orada yangilari qo'shilgan bo'lishi mumkin)
        with open(path, encoding="utf-8") as f:
            rest = [ln for ln in f if ln.strip()][n:]
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(rest)
    except Exception:
        log.exception("dup flush cleanup")
    return n


# --- qamrov: qaysi savol yetishmayapti (avtomatik yangilanadi)
def coverage():
    with db() as c:
        return {int(n): int(k) for n, k in c.execute("SELECT qno, COUNT(*) FROM exam_q WHERE cid IS NOT NULL AND skipped=0 GROUP BY qno")}


def _my_nos(uid):
    with db() as c:
        return {int(r[0]) for r in c.execute("SELECT qno FROM exam_q WHERE user_id=? AND cid IS NOT NULL AND skipped=0", (int(uid),))}


def needed_for(uid, limit=SHOW_NEED, cov=None):
    cov = cov if cov is not None else coverage(); mine = _my_nos(uid)
    need = [n for n in range(1, TOTAL_Q + 1) if cov.get(n, 0) < COVER_TARGET and n not in mine]
    need.sort(key=lambda n: (cov.get(n, 0) // 3, (n * 7919 + int(uid)) % 97, n))      # kam yig'ilganlar oldin; odamlarga turlicha beriladi
    return sorted(need[:limit]), len(need)


def need_text(uid):
    cov = coverage()
    done = sum(1 for n in range(1, TOTAL_Q + 1) if cov.get(n, 0) >= COVER_TARGET)
    if done >= TOTAL_Q:
        return f"🎉 Hamma {TOTAL_Q} ta savol yig‘ildi — rahmat! Yana yangi narsa eslasangiz, yuboraverishingiz mumkin."
    first, total = needed_for(uid, cov=cov)
    head = f"📊 To‘plam: <b>{done}/{TOTAL_Q}</b> savol kamida {COVER_TARGET} kishidan yig‘ildi."
    if not first:
        return head + "\nSiz hozir kerak bo‘lgan hamma savolni yuborgansiz 🙏"
    more = f" (yana {total - len(first)} ta)" if total > len(first) else ""
    return f"🎯 Hozir eng kerak savollar: <b>{', '.join(map(str, first))}</b>{more}\n{head}"


def can_submit(uid):
    """Imtihon tugagan bo'lsa. Sana tanlamagan / «keyinroq» degan foydalanuvchi ham birinchi smena tugagach kira oladi."""
    if uid == _cfg["admin_id"]:
        return True
    code = get_slot(uid)
    if code and parse_slot(code):
        return now_tk() >= slot_end(code)
    codes = slot_codes()
    return bool(codes) and now_tk() >= slot_end(codes[0])


def _q_count(uid):
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM exam_q WHERE user_id=? AND skipped=0 AND (cid IS NOT NULL OR qtext IS NOT NULL)", (int(uid),)).fetchone()[0]


def migrate_legacy():
    """v97-v100 da yozilgan (matni foydalanuvchi qatorida turgan) savollarni klasterlarga o'tkazadi."""
    with db() as c:
        rows = c.execute("SELECT user_id,qno,qtext,ans FROM exam_q WHERE qtext IS NOT NULL AND cid IS NULL AND skipped=0").fetchall()
    n = 0
    for r in rows:
        try:
            stem, opts = parse_opts(r["qtext"] or "")
            opts = [_clean_opt(o) for o in opts]
            ok, _ = validate_item(stem, opts)
            if ok:
                ingest(int(r["user_id"]), int(r["qno"]), stem[:600], opts, r["ans"] or ""); n += 1
            else:
                with db() as c:
                    c.execute("UPDATE exam_q SET skipped=1 WHERE user_id=? AND qno=?", (int(r["user_id"]), int(r["qno"]))); c.commit()
        except Exception:
            log.exception("migrate_legacy")
    return n


SUBMIT_HELP = (
    "📋 <b>Savol yuborish</b>\n\n"
    "Eslab qolgan savollaringizni shu formatda yuboring (bir xabarda bir nechtasini ham mumkin):\n\n"
    "<code>1. To‘g‘ri yozilgan so‘zlarni aniqlang.\n"
    "A) ...\nB) ...\nC) ...\nD) ...\n"
    "Men A javobni oldim.\n\n"
    "2. Qabilida</code>\n\n"
    "• <b>Raqam</b> — imtihon varag‘idagi savol raqami.\n"
    "• Variant yoki savolni to‘liq eslolmasangiz — bor qismini yozing. Qolganini keyinroq <b>shu raqam bilan</b> qayta yuborsangiz, qo‘shiladi.\n"
    "• Belgilagan javobingizni eslamasangiz, «Men ... javobni oldim» qatorini yozmang.\n"
    "• Qachon xohlasangiz /savol deb yozib davom ettirasiz.\n\n"
)


def _q_markup():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎯 Qaysi savollar kerak?", callback_data="ex_q_need")],
                                 [InlineKeyboardButton("✔️ Tugatdim", callback_data="ex_q_done")]])


async def q_prompt(bot, uid):
    _Q[int(uid)] = {"exp": time.time() + Q_STATE_MIN * 60}
    await _safe(lambda: bot.send_message(chat_id=int(uid), text=SUBMIT_HELP + need_text(uid), parse_mode="HTML", reply_markup=_q_markup()))


async def _open_submit(bot, uid):
    if not can_submit(uid):
        await bot.send_message(uid, "Bu bo‘lim imtihon tugagach ochiladi 🙂"); return
    code = get_slot(uid)
    if uid != _cfg["admin_id"] and not (code and parse_slot(code)):
        rows = [[InlineKeyboardButton(slot_label(c_), callback_data="ex_qs_" + c_.replace("-", "_"))] for c_ in slot_codes() if now_tk() >= slot_end(c_)]
        rows.append([InlineKeyboardButton("Boshqa / eslolmayman", callback_data="ex_qs_x")])
        await bot.send_message(uid, "📅 <b>Imtihonni qaysi kuni topshirdingiz?</b>\nSavollarni to‘g‘ri smenaga joylash uchun kerak.", parse_mode="HTML",
                               reply_markup=InlineKeyboardMarkup(rows))
        return
    await q_prompt(bot, uid)


async def q_start_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    if not can_submit(uid):
        await q.answer("Imtihon tugagach ochiladi 🙂", show_alert=True); return
    await q.answer()
    await _open_submit(context.bot, uid)


async def q_slot_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    p = (q.data or "").split("_")
    if len(p) == 4 and p[2].isdigit() and p[3] in ("1", "2"):
        code = f"{p[2]}-{p[3]}"
        if not parse_slot(code) or now_tk() < slot_end(code):
            await q.answer("Bu smena hali tugamagan 🙂", show_alert=True); return
        set_slot(uid, code)
    await q.answer("✅")
    try: await q.edit_message_reply_markup(reply_markup=None)
    except Exception: pass
    await q_prompt(context.bot, uid)


async def savollar_cmd(update, context):
    """/savol (yoki /savollar) — savol yuborishni boshlash yoki davom ettirish."""
    await _open_submit(context.bot, update.effective_user.id)


async def q_need_cb(update, context):
    q = update.callback_query; await q.answer()
    await context.bot.send_message(q.from_user.id, need_text(q.from_user.id), parse_mode="HTML")


def _item_line(it, status, reason=""):
    if status == "bad":
        return f"⚠️ {it['qno']}-savol: qabul qilinmadi ({reason}). Savol matnini yozing."
    n_opts = sum(1 for o in it["opts"] if o)
    extra = []
    if n_opts < 4: extra.append("variantlar to‘liq emas — keyin to‘ldirsangiz bo‘ladi")
    if not it["stem"]: extra.append("savol matni yo‘q")
    return f"✅ {it['qno']}-savol qabul qilindi" + (f" ({'; '.join(extra)})" if extra else "")


async def q_text_cb(update, context):
    uid = update.effective_user.id
    st = _Q.get(uid)
    if not st:
        return
    text = (update.message.text or "").strip()[:8000]
    items = parse_submission(text)
    if not items:
        if len(text) > 400:                              # uzun matn — esse bo'lishi mumkin: bu holatdan chiqamiz va xabarga tegmaymiz
            _Q.pop(uid, None); return
        await update.message.reply_text("🤔 Savol raqamini topa olmadim. Shunday yozing:\n\n<code>7. Savol matni\nA) ...\nB) ...\nMen B javobni oldim.</code>\n\n"
                                        "Raqamdan keyin nuqta qo‘ying. To‘xtatish: ✔️ Tugatdim.", parse_mode="HTML", reply_markup=_q_markup())
        raise ApplicationHandlerStop
    st["exp"] = time.time() + Q_STATE_MIN * 60
    lines = []; okn = 0
    for it in items:
        ok, why = validate_item(it["stem"], it["opts"])
        if not ok:
            lines.append(_item_line(it, "bad", why)); continue
        try:
            await asyncio.to_thread(ingest, uid, it["qno"], it["stem"], it["opts"], it["pick"])
            okn += 1; lines.append(_item_line(it, "ok"))
        except Exception:
            log.exception("ingest"); lines.append(f"⚠️ {it['qno']}-savol: vaqtincha xato, qayta yuboring.")
    cnt = _q_count(uid)
    tail = f"\n\n📝 Siz yuborgan savollar: <b>{cnt}</b> ta"
    tail += " 🔑 (hissa qo‘shuvchi)" if cnt >= Q_MIN else f" (hissa qo‘shuvchi bo‘lish uchun kamida {Q_MIN} ta kerak)"
    msg = "\n".join(lines[:30]) + (f"\n… va yana {len(lines) - 30} ta" if len(lines) > 30 else "") + tail + "\n\n" + need_text(uid)
    await update.message.reply_text(msg[:4000], parse_mode="HTML", reply_markup=_q_markup())
    await _milestone(context.bot, uid)
    raise ApplicationHandlerStop


MILESTONES = [
    (10, "🥉 <b>«Savol kuzatuvchisi»</b> nishoni!\n🔑 Siz endi hissa qo‘shuvchisiz — savollar tekshirilib, to‘g‘ri javoblar ochilganda birinchilar qatorida ko‘rasiz."),
    (25, "🥈 <b>«Savol ovchisi»</b> nishoni! Yarmidan ko‘pi tayyor — davom eting 💪"),
]


async def _milestone(bot, uid):
    cnt = _q_count(uid)
    ms = MILESTONES + [(TOTAL_Q, f"🥇 <b>«To‘liq to‘plam»</b> nishoni! {TOTAL_Q}/{TOTAL_Q} — siz haqiqiy qahramonsiz 🏆")]
    for thr, txt in ms:
        if cnt >= thr:
            with db() as c:
                got = c.execute("SELECT 1 FROM exam_sent WHERE user_id=? AND kind=?", (int(uid), f"ms{thr}")).fetchone()
            if not got:
                _mark_sent(uid, f"ms{thr}")
                await _safe(lambda: bot.send_message(chat_id=int(uid), text=f"🎉 {txt}", parse_mode="HTML"))


async def q_done_cb(update, context):
    q = update.callback_query; await q.answer()
    try: await q.edit_message_reply_markup(reply_markup=None)
    except Exception: pass
    _Q.pop(q.from_user.id, None)
    await q_finish(context.bot, q.from_user.id)


async def q_finish(bot, uid):
    _Q.pop(int(uid), None)
    cnt = _q_count(uid)
    txt = f"🙏 <b>Katta rahmat!</b> {cnt} ta savol qabul qilindi."
    if Q_REWARD > 0 and cnt >= Q_MIN and _cfg["add_credits"]:
        with db() as c:
            got = c.execute("SELECT 1 FROM exam_sent WHERE user_id=? AND kind='qreward'", (int(uid),)).fetchone()
        if not got:
            try:
                _cfg["add_credits"](uid, Q_REWARD); _mark_sent(uid, "qreward")
                txt += f"\n🎁 Hisobingizga yana <b>+{Q_REWARD} ta bepul esse tekshiruvi</b> qo‘shildi."
            except Exception:
                log.exception("q reward")
    elif Q_REWARD > 0 and cnt < Q_MIN:
        txt += f"\n(Bonus uchun kamida {Q_MIN} ta savol kerak — /savol bilan davom ettirishingiz mumkin.)"
    if cnt >= Q_MIN:
        txt += "\n🔑 Siz <b>hissa qo‘shuvchi</b>siz: to‘g‘ri javoblar ochilganda birinchilar qatorida ko‘rasiz."
    txt += ("\n\n⏳ Savollar <b>to‘liq yig‘ilgach</b> admin tekshiradi, to‘g‘ri javoblarni belgilaydi va <b>shundan so‘ng</b> "
            "javoblar hamda taxminiy natijangiz chiqariladi. Tayyor bo‘lganda sizga xabar beramiz.\n"
            "Esingizga yangi savol tushsa — /savol deb yozing (savollar «Tushgan savollar» bo‘limida <b>anonim</b> ko‘rinadi).")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📈 Taxminiy natijam", callback_data="ex_score")]])
    await _safe(lambda: bot.send_message(chat_id=int(uid), text=txt, parse_mode="HTML", reply_markup=kb))


# --- javoblar kaliti va taxminiy natija
def _get_key():
    from national_certificate import setting
    k = (setting("exam_key", "") or "").strip().upper()
    return k if len(k) == TOTAL_Q else ""


def score_of(uid, key):
    with db() as c:
        rows = c.execute("SELECT qno,ans FROM exam_q WHERE user_id=? AND ans IS NOT NULL", (int(uid),)).fetchall()
    marked = [(int(n), a) for n, a in rows if 1 <= int(n) <= TOTAL_Q and a in ANS]
    ok = sum(1 for n, a in marked if key[n - 1] == a)
    return ok, len(marked)


def score_text(uid, key):
    ok, marked = score_of(uid, key)
    t = (f"📈 <b>Taxminiy natijangiz</b>\n\n✅ To‘g‘ri: <b>{ok}</b> ta\n📝 Siz belgilaganingizni eslagan savollar: {marked} ta (jami {TOTAL_Q} ta)\n\n")
    if marked < TOTAL_Q // 2:
        t += "⚠️ Ko‘p savol belgilanmagani uchun natija aniq emas.\n"
    t += "<i>Bu rasmiy natija emas — xotirangizdagi javoblar asosida hisoblandi.</i>"
    return t


async def score_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    key = _get_key()
    if not key:
        await q.answer("Savollar to‘liq yig‘ilib, admin tekshirgach natija chiqadi. Tayyor bo‘lganda sizga xabar beramiz 🙂", show_alert=True); return
    await q.answer()
    await context.bot.send_message(uid, score_text(uid, key), parse_mode="HTML")


# --- admin uchun jamlangan fayl
def build_export(qno=None, slot=None):
    """(docx_bytes, klaster_soni). Admin uchun jamlangan savollar: savol raqami bo'yicha, har bir klaster alohida (user ID/ism YO'Q)."""
    with db() as c:
        cl = c.execute("SELECT * FROM exam_qc ORDER BY qno,id").fetchall()
        sql = "SELECT q.cid, COALESCE(q.ans,''), COUNT(*) FROM exam_q q"
        args = []
        if slot:
            sql += " JOIN exam_slot s ON s.user_id=q.user_id WHERE q.cid IS NOT NULL AND s.slot=?"; args.append(slot)
        else:
            sql += " WHERE q.cid IS NOT NULL"
        sql += " GROUP BY q.cid, q.ans"
        stat = c.execute(sql, args).fetchall()
    picks = {}; tot = {}
    for cid, a, k in stat:
        tot[cid] = tot.get(cid, 0) + k
        if a: picks.setdefault(cid, {})[a] = k
    cov = coverage(); done = sum(1 for n in range(1, TOTAL_Q + 1) if cov.get(n, 0) >= COVER_TARGET)
    rows = [r for r in cl if r["id"] in tot and (not qno or r["qno"] == int(qno))]
    blocks = [("h1", "Tushgan savollar — jamlanma" + (f" ({slot_label(slot)})" if slot else "")),
              ("p", f"Yaratildi: {now_tk().strftime('%d.%m.%Y %H:%M')} • klasterlar: {len(rows)} • qamrov: {done}/{TOTAL_Q} savol kamida {COVER_TARGET} kishidan.\n"
                    "Foydalanuvchi ismi/ID si bu faylda yo‘q. To‘g‘ri javobni Mini App → Tushgan savollar → Kelgan savollar da belgilang.")]
    by = {}
    for r in rows: by.setdefault(r["qno"], []).append(r)
    for n in sorted(by):
        blocks.append(("h2", f"{n}-savol • {len(by[n])} ta variant"))
        for r in sorted(by[n], key=lambda x: -tot.get(x["id"], 0)):
            pk = ", ".join(f"{k}:{v}" for k, v in sorted(picks.get(r["id"], {}).items())) or "—"
            sl = slot_label(r["slot"]) if r["slot"] and parse_slot(r["slot"]) else "—"
            blocks.append(("b", f"Klaster #{r['id']} • {tot.get(r['id'], 0)} kishi • belgilashlar: {pk} • {sl}"))
            blocks.append(("p", _fmt_q(r["stem"] or "", _json_opts(r["opts"])) or "(matn yo‘q)"))
    miss = [n for n in range(1, TOTAL_Q + 1) if cov.get(n, 0) < COVER_TARGET]
    if miss:
        blocks.append(("h2", "Hali yetarli emas"))
        blocks.append(("p", ", ".join(f"{n} ({cov.get(n, 0)})" for n in miss)))
    return _docx_bytes(blocks), len(rows)


async def _send_export(bot, chat_id, qno=None, slot=None, caption=""):
    data, n = await asyncio.to_thread(build_export, qno, slot)
    if not n:
        return 0
    stamp = now_tk().strftime("%d%m_%H%M")
    tag = f"_{qno}-savol" if qno else (f"_{slot}" if slot else "")
    await bot.send_document(chat_id=chat_id, document=InputFile(io.BytesIO(data), filename=f"savollar{tag}_{stamp}.docx"),
                            caption=(caption or f"📋 Savollar: {n} ta klaster (Word)")[:1000])
    return n


async def savollar_fayl_cmd(update, context):
    """/savollar_fayl — jamlangan savollar (Word); /savollar_fayl 12 — faqat 12-savol; /savollar_fayl 25-1 — faqat shu smena."""
    if not _is_admin(update): return
    a = (context.args or [None])[0]
    qno = int(a) if a and a.isdigit() else None
    slot = a if a and parse_slot(a) else None
    n = await _send_export(context.bot, update.effective_user.id, qno, slot)
    if not n:
        await update.message.reply_text("Hozircha savollar yo‘q.")


async def yigish_cmd(update, context):
    """/yigish — savollar yig'ilish holati: qaysi raqamdan nechta kishi yuborgan."""
    if not _is_admin(update): return
    cov = coverage()
    with db() as c:
        users = c.execute("SELECT COUNT(DISTINCT user_id) FROM exam_q WHERE cid IS NOT NULL AND skipped=0").fetchone()[0]
        ncl = c.execute("SELECT COUNT(*) FROM exam_qc").fetchone()[0]
        contrib = c.execute("SELECT COUNT(*) FROM (SELECT user_id FROM exam_q WHERE cid IS NOT NULL AND skipped=0 GROUP BY user_id HAVING COUNT(*)>=?)", (Q_MIN,)).fetchone()[0]
    done = [n for n in range(1, TOTAL_Q + 1) if cov.get(n, 0) >= COVER_TARGET]
    weak = [n for n in range(1, TOTAL_Q + 1) if cov.get(n, 0) < COVER_TARGET]
    lines = [f"📊 <b>SAVOLLAR YIG‘ILISHI</b> (maqsad: har bir savol ≥ {COVER_TARGET} kishidan)",
             f"✅ Tayyor: <b>{len(done)}/{TOTAL_Q}</b> • Yuborgan: {users} kishi • Hissa qo‘shuvchi (≥{Q_MIN}): {contrib}",
             f"Klasterlar (turli variantlar): {ncl} • Takroriy yozuvlar fayli: {spool_count()} ta (≥{DUP_BATCH} bo‘lsa Word keladi)"]
    if weak:
        lines.append("\n⏳ Yetmayotganlar (savol: kishi soni):\n" + ", ".join(f"{n}: {cov.get(n, 0)}" for n in weak))
    else:
        lines.append("\n🎉 Hamma savol yetarlicha yig‘ildi. Endi Mini App → Tushgan savollar → «Kelgan savollar» da tekshirib, to‘g‘ri javoblarni belgilang.")
    lines.append("\n/savollar_fayl — jamlanma Word • /takror_fayl — takroriylarni hoziroq Word qilib yuborish")
    await update.message.reply_text("\n".join(lines)[:4000], parse_mode="HTML")


async def takror_fayl_cmd(update, context):
    """/takror_fayl — yig'ilgan takroriy savollarni hoziroq Word qilib yuboradi va tozalaydi."""
    if not _is_admin(update): return
    n = await flush_dups(context.bot, force=True)
    if not n:
        await update.message.reply_text("Takroriy yozuvlar yo‘q (yoki yuborib bo‘lmadi).")


async def kalit_cmd(update, context):
    """/kalit ABCD...  (jami TOTAL_Q ta harf: A/B/C/D; ochiq yoki noma'lum savol uchun '-'). /kalit — holat."""
    if not _is_admin(update): return
    from national_certificate import set_setting
    a = "".join(context.args or []).strip().upper().replace(",", "").replace(" ", "")
    if not a:
        k = _get_key()
        await update.message.reply_text(("✅ Kalit o‘rnatilgan: " + k) if k else f"Kalit yo‘q. Misol: /kalit {'ABCD' * (TOTAL_Q // 4)}"); return
    if len(a) != TOTAL_Q or any(ch not in "ABCD-" for ch in a):
        await update.message.reply_text(f"❌ Kalit {TOTAL_Q} ta belgidan iborat bo‘lishi kerak (A/B/C/D yoki '-'). Siz {len(a)} ta yubordingiz."); return
    set_setting("exam_key", a)
    with db() as c:
        users = c.execute("SELECT COUNT(DISTINCT user_id) FROM exam_q WHERE ans IS NOT NULL").fetchone()[0]
    await update.message.reply_text(f"✅ Kalit saqlandi. Javob belgilagan foydalanuvchilar: {users}.\n"
                                    "Foydalanuvchilar 📈 tugmasi orqali o‘zi ko‘radi. Hammaga yuborish: /natija_yubor")


async def _run_scores(bot, redo):
    key = _get_key()
    with db() as c:
        ids = [int(r[0]) for r in c.execute("SELECT DISTINCT user_id FROM exam_q WHERE ans IS NOT NULL")]
        done = {int(r[0]) for r in c.execute("SELECT user_id FROM exam_sent WHERE kind='score'")}
    ok = 0; vals = []
    for uid in ids:
        if (uid in done and not redo) or _cfg["is_banned"](uid): continue
        r, _ = await _safe(lambda: bot.send_message(chat_id=uid, text=score_text(uid, key), parse_mode="HTML"))
        if r:
            ok += 1; _mark_sent(uid, "score"); vals.append(score_of(uid, key)[0])
        await asyncio.sleep(0.05)
    avg = (sum(vals) / len(vals)) if vals else 0
    await bot.send_message(_cfg["admin_id"], f"✅ Taxminiy natija yuborildi: {ok} kishi. O‘rtacha to‘g‘ri javob: {avg:.1f}/{TOTAL_Q}")


async def natija_yubor_cmd(update, context):
    """/natija_yubor — javob belgilaganlarning hammasiga taxminiy natijani yuboradi. /natija_yubor qayta — kalit o'zgargan bo'lsa yana."""
    if not _is_admin(update): return
    if not _get_key():
        await update.message.reply_text("Avval /kalit bilan javoblar kalitini kiriting."); return
    redo = bool(context.args and context.args[0].lower() == "qayta")
    t = asyncio.create_task(_run_scores(context.bot, redo)); _TASKS.add(t); t.add_done_callback(_TASKS.discard)
    await update.message.reply_text("🚀 Natijalar yuborilmoqda (fon rejimida). Tugagach hisobot keladi.")


# ----------------------------------------------------------------------------- "Tushgan savollar" bo'limi (Mini App + bot)
# Oqim: foydalanuvchi savol yozadi (exam_q) -> admin Mini App'da tahrirlaydi (matn, variantlar A-D, TO'G'RI javob, izoh) -> "Nashr qilish"
# -> bo'limga avtomatik tushadi (exam_pub). Foydalanuvchi nomi anonim: "1-foydalanuvchi", "2-foydalanuvchi"...
# Bo'lim hammaga faqat admin "ochganda" ko'rinadi (/tushgan_och). Javob uch holatda: yopiq | hissa qo'shuvchilarga (birinchi) | hammaga.
# Ulashishda savol matni YUBORILMAYDI: faqat teaser + bot manzili (t.me/<bot>?start=q_<id>). Havolani ochgan odam savolni ko'rib,
# javob variantini belgilaydi ("test"); javoblar ochilganda bot unga natijasini yozadi.
OPT_LETTERS = ["A", "B", "C", "D"]
SHARE_TEASER = "🧠 Imtihonda tushgan savol! To‘g‘ri javobni topa olasizmi? Bot orqali sinab ko‘ring 👇"
_OPT_RE = re.compile(r"(?:(?<=\s)|^)([A-Da-d])\s*[\)\.]\s+")


def _setting(k, d=""):
    from national_certificate import setting
    return setting(k, d)


def _set(k, v):
    from national_certificate import set_setting
    set_setting(k, v)


def eq_public():
    return _setting("eq_public", "0") == "1"


def ans_mode(slot):
    """'all' | 'contrib' | 'closed'"""
    a = _setting("eq_ans_all", "0"); sv = _setting(f"eq_ans_{slot}", "0")
    if a == "1" or sv == "1":
        return "all"
    if a == "c" or sv == "c":
        return "contrib"
    return "closed"


def is_contributor(uid):
    return _q_count(uid) >= Q_MIN


def can_see(slot, uid, admin, contrib=None):
    if admin:
        return True
    m = ans_mode(slot)
    if m == "all":
        return True
    if m == "contrib":
        return is_contributor(uid) if contrib is None else bool(contrib)
    return False


def anon_label(uid):
    with db() as c:
        r = c.execute("SELECT n FROM exam_anon WHERE user_id=?", (int(uid),)).fetchone()
        if not r:
            c.execute("INSERT OR IGNORE INTO exam_anon(user_id,n) SELECT ?, COALESCE(MAX(n),0)+1 FROM exam_anon", (int(uid),)); c.commit()
            r = c.execute("SELECT n FROM exam_anon WHERE user_id=?", (int(uid),)).fetchone()
    return f"{r[0]}-foydalanuvchi"


def parse_opts(text):
    """Foydalanuvchi yozgan matndan savol va A-D variantlarni ajratadi (admin tahririni yengillashtirish uchun)."""
    t = text or ""
    seq = []; want = 0
    for m in _OPT_RE.finditer(t):
        if m.group(1).upper() == OPT_LETTERS[want]:
            seq.append((m.start(), m.end(), m.group(1).upper())); want += 1
            if want == 4: break
    if len(seq) < 2:
        return t.strip(), ["", "", "", ""]
    opts = ["", "", "", ""]
    for i, (st, en, L) in enumerate(seq):
        end = seq[i + 1][0] if i + 1 < len(seq) else len(t)
        opts[OPT_LETTERS.index(L)] = t[en:end].strip()
    return (t[:seq[0][0]].strip() or t.strip()), opts


def _opts_of(r):
    try:
        o = json.loads(r["opts"] or "[]")
    except Exception:
        o = []
    return (list(o) + ["", "", "", ""])[:4]


def _slot_order(code):
    codes = slot_codes()
    return codes.index(code) if code in codes else len(codes)


def _group_label(code):
    return slot_label(code) if code and parse_slot(code) else "Boshqa"


def _display_name(r):
    nm = (r["name"] or "").strip()
    if nm:
        return nm
    return anon_label(r["src_user"]) if r["src_user"] else "Foydalanuvchi"


def _pub_item(r, uid, admin, contrib, votes):
    slot = r["slot"] or ""
    mode = ans_mode(slot)
    see = can_see(slot, uid, admin, contrib)
    return {"id": r["id"], "slot": slot, "name": _display_name(r), "question": r["question"] or "", "opts": _opts_of(r),
            "answer": (r["answer"] or "") if see else None, "explain": (r["explain"] or "") if see else None,
            "lock": None if see else ("contrib" if mode == "contrib" else "closed"),
            "mode": mode, "status": r["status"], "src_qno": r["src_qno"],
            "my_vote": votes.get(r["id"])}


def _group(items):
    groups = {}
    for it in items:
        groups.setdefault(it["slot"], []).append(it)
    return [{"slot": k, "label": _group_label(k), "items": v} for k, v in sorted(groups.items(), key=lambda kv: _slot_order(kv[0]))]


def _votes_of(uid):
    with db() as c:
        return {int(r[0]): r[1] for r in c.execute("SELECT pub_id,letter FROM exam_vote WHERE user_id=?", (int(uid),))}


def api_list(uid, admin):
    out = {"ok": True, "is_admin": bool(admin), "public": eq_public(), "bot": _cfg["bot_username"](),
           "slots": [{"code": c, "label": slot_label(c), "mode": ans_mode(c)} for c in slot_codes()],
           "answers_all": _setting("eq_ans_all", "0"), "contributor": is_contributor(uid), "q_min": Q_MIN,
           "share_text": SHARE_TEASER, "groups": []}
    if not out["public"] and not admin:
        return 200, out
    votes = _votes_of(uid); contrib = out["contributor"]
    with db() as c:
        rows = c.execute("SELECT * FROM exam_pub WHERE status='published' ORDER BY slot,id").fetchall()
    out["groups"] = _group([_pub_item(r, uid, admin, contrib, votes) for r in rows])
    if admin:
        with db() as c:
            dr = c.execute("SELECT * FROM exam_pub WHERE status='draft' ORDER BY slot,id").fetchall()
        out["drafts"] = _group([_pub_item(r, uid, True, True, votes) for r in dr])
    return 200, out


def api_raw(admin):
    """Admin: kelgan savollar KLASTERLAR bo'yicha (bir xil savollar bitta kartochkada, nechta kishi yozgani va belgilashlar bilan)."""
    if not admin:
        return 403, {"ok": False, "error": "Faqat admin."}
    with db() as c:
        cl = c.execute("SELECT c.id,c.qno,c.slot,c.stem,c.opts,p.id AS pid,p.status,p.name,p.question,p.answer,p.opts AS popts,p.explain "
                       "FROM exam_qc c LEFT JOIN exam_pub p ON p.cid=c.id ORDER BY c.qno,c.id LIMIT 3000").fetchall()
        st = c.execute("SELECT cid, COALESCE(ans,''), COUNT(*) FROM exam_q WHERE cid IS NOT NULL AND skipped=0 GROUP BY cid, ans").fetchall()
    picks = {}; tot = {}
    for cid, a, k in st:
        tot[cid] = tot.get(cid, 0) + k
        if a: picks.setdefault(cid, {})[a] = k
    groups = {}
    for r in cl:
        pid = r["pid"]
        opts = _json_opts(r["popts"]) if pid else _json_opts(r["opts"])
        stem = (r["question"] or "") if pid else (r["stem"] or "")
        pk = picks.get(r["id"], {})
        top = ", ".join(f"{k}:{v}" for k, v in sorted(pk.items(), key=lambda kv: -kv[1])) or "—"
        groups.setdefault(r["qno"], []).append({
            "cid": r["id"], "slot": r["slot"] if parse_slot(r["slot"] or "") else "", "src_qno": r["qno"], "n": tot.get(r["id"], 0), "picks": pk, "user_pick": top,
            "name": (r["name"] or "") if pid else "", "question": stem, "opts": opts, "answer": (r["answer"] or "") if pid else "",
            "explain": (r["explain"] or "") if pid else "", "pub_id": pid, "status": r["status"] or "new",
            "raw_question": _fmt_q(r["stem"] or "", _json_opts(r["opts"]))})
    out = [{"slot": f"q{n}", "label": f"{n}-savol", "items": sorted(v, key=lambda x: -x["n"])} for n, v in sorted(groups.items())]
    cov = coverage()
    return 200, {"ok": True, "groups": out, "cover": {"target": COVER_TARGET, "done": sum(1 for n in range(1, TOTAL_Q + 1) if cov.get(n, 0) >= COVER_TARGET), "total": TOTAL_Q}}


def _clean(s_, n):
    return str(s_ or "").replace("\x00", "").strip()[:n]


def api_save(body):
    slot = _clean(body.get("slot"), 8)
    if slot and not parse_slot(slot):
        slot = ""
    question = _clean(body.get("question"), 3000)
    if not question:
        return 400, {"ok": False, "error": "Savol matni bo‘sh."}
    raw_opts = body.get("opts") or []
    if isinstance(raw_opts, dict):
        raw_opts = [raw_opts.get(L, "") for L in OPT_LETTERS]
    opts = [_clean(x, 200) for x in (list(raw_opts) + ["", "", "", ""])[:4]]
    answer = _clean(body.get("answer"), 300)
    if any(opts):
        a_ = answer.upper()
        if a_ and a_ not in OPT_LETTERS:
            return 400, {"ok": False, "error": "Javob A, B, C yoki D harfi bo‘lishi kerak (variantlar kiritilgan)."}
        if a_ and not opts[OPT_LETTERS.index(a_)]:
            return 400, {"ok": False, "error": f"{a_} varianti bo‘sh — javob harfini tekshiring."}
        answer = a_
    explain = _clean(body.get("explain"), 500)
    status = "published" if body.get("publish") else "draft"
    pid = body.get("id"); su = body.get("src_user"); sq = body.get("src_qno")
    cid = body.get("cid")
    name = _clean(body.get("name"), 40)
    if cid:                                              # v101: klasterdan nashr — muallif ID si saqlanmaydi (anonim)
        try: cid = int(cid)
        except Exception: cid = None
    if cid:
        with db() as c:
            cr = c.execute("SELECT qno FROM exam_qc WHERE id=?", (cid,)).fetchone()
        if cr: sq = cr["qno"]
        else: cid = None
    if su and not cid:
        with db() as c:
            fr = c.execute("SELECT first_name FROM users WHERE user_id=?", (int(su),)).fetchone()
        real = ((fr[0] if fr else "") or "").strip().lower()
        if not name or name.lower() == real:      # haqiqiy ism hech qachon ochiq chiqmaydi
            name = anon_label(int(su))
    elif not name:
        name = "Foydalanuvchilar" if cid else "Foydalanuvchi"
    if cid and name and name != "Foydalanuvchilar":     # klasterga yozgan odamlarning haqiqiy ismi hech qachon ochiq chiqmaydi
        with db() as c:
            reals = {(r[0] or "").strip().lower() for r in c.execute("SELECT u.first_name FROM exam_q q JOIN users u ON u.user_id=q.user_id WHERE q.cid=?", (cid,))}
        if name.lower() in reals:
            name = "Foydalanuvchilar"
    with db() as c:
        row = None
        if pid:
            row = c.execute("SELECT id FROM exam_pub WHERE id=?", (int(pid),)).fetchone()
        elif cid:
            row = c.execute("SELECT id FROM exam_pub WHERE cid=?", (cid,)).fetchone()
        elif su and sq:
            row = c.execute("SELECT id FROM exam_pub WHERE src_user=? AND src_qno=?", (int(su), int(sq))).fetchone()
        if row:
            c.execute("UPDATE exam_pub SET slot=?,name=?,question=?,answer=?,opts=?,explain=?,status=?,updated_at=? WHERE id=?",
                      (slot, name, question, answer, json.dumps(opts, ensure_ascii=False), explain, status, _iso(), row[0])); rid = row[0]
        else:
            cur = c.execute("INSERT INTO exam_pub(slot,src_user,src_qno,name,question,answer,opts,explain,status,created_at,updated_at,cid) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (slot, int(su) if (su and not cid) else None, int(sq) if sq else None, name, question, answer,
                             json.dumps(opts, ensure_ascii=False), explain, status, _iso(), _iso(), cid))
            rid = cur.lastrowid
        if cid and slot:
            c.execute("UPDATE exam_qc SET slot=? WHERE id=?", (slot, cid))
        c.commit()
    return 200, {"ok": True, "id": rid, "status": status, "name": name}


def api_delete(body):
    try:
        pid = int(body.get("id"))
    except Exception:
        return 400, {"ok": False, "error": "id noto‘g‘ri."}
    with db() as c:
        c.execute("DELETE FROM exam_pub WHERE id=?", (pid,)); c.execute("DELETE FROM exam_vote WHERE pub_id=?", (pid,)); c.commit()
    return 200, {"ok": True}


def _mode_value(mode):
    return {"all": "1", "contrib": "c", "closed": "0"}.get(mode, "0")


def api_settings(body):
    if "public" in body:
        _set("eq_public", "1" if body.get("public") else "0")
    a = body.get("answers")
    if isinstance(a, dict):
        target = str(a.get("slot", "all"))
        mode = a.get("mode") or ("all" if a.get("open") else "closed")
        v = _mode_value(mode)
        if target == "all":
            _set("eq_ans_all", v)
            if v == "0":
                for c_ in slot_codes(): _set(f"eq_ans_{c_}", "0")
        elif parse_slot(target):
            _set(f"eq_ans_{target}", v)
    return 200, {"ok": True, "public": eq_public(), "answers_all": _setting("eq_ans_all", "0")}


def api_vote(uid, body):
    """Test savoli: foydalanuvchi variantni belgilaydi. Javob yopiq bo'lsa natija keyin (ochilganda) xabar qilinadi."""
    try:
        pid = int(body.get("id")); L = str(body.get("letter", "")).upper()
    except Exception:
        return 400, {"ok": False, "error": "So‘rov noto‘g‘ri."}
    if L not in OPT_LETTERS:
        return 400, {"ok": False, "error": "Variant noto‘g‘ri."}
    admin = int(uid) == int(_cfg["admin_id"])
    with db() as c:
        r = c.execute("SELECT * FROM exam_pub WHERE id=? AND status='published'", (pid,)).fetchone()
    if not r or (not eq_public() and not admin):
        return 404, {"ok": False, "error": "Savol topilmadi."}
    opts = _opts_of(r)
    if not opts[OPT_LETTERS.index(L)]:
        return 400, {"ok": False, "error": "Bunday variant yo‘q."}
    slot = r["slot"] or ""
    see = can_see(slot, uid, admin)
    prior = None
    with db() as c:
        prior = c.execute("SELECT letter FROM exam_vote WHERE user_id=? AND pub_id=?", (int(uid), pid)).fetchone()
        saved = False
        if not see:                                   # javob ochilmaguncha o'zgartirish mumkin
            c.execute("INSERT INTO exam_vote(user_id,pub_id,letter,at) VALUES(?,?,?,?) ON CONFLICT(user_id,pub_id) DO UPDATE SET letter=excluded.letter, at=excluded.at",
                      (int(uid), pid, L, _iso())); c.commit(); saved = True
        elif not prior:                               # javob ochiq bo'lsa birinchi urinish ham yoziladi
            c.execute("INSERT INTO exam_vote(user_id,pub_id,letter,at) VALUES(?,?,?,?)", (int(uid), pid, L, _iso())); c.commit(); saved = True
    out = {"ok": True, "saved": saved, "visible": see, "letter": L, "lock": None if see else ("contrib" if ans_mode(slot) == "contrib" else "closed"),
           "dist": vote_dist(pid)}
    if see:
        correct = (r["answer"] or "").upper()
        out.update(correct=correct, is_right=bool(correct) and correct == L, explain=r["explain"] or "")
    return 200, out


def api_get(path, uid, admin):
    p = path.split("?")[0]
    if p == "/api/eq/list":
        return api_list(uid, admin)
    if p == "/api/eq/raw":
        return api_raw(admin)
    return 404, {"ok": False, "error": "Topilmadi"}


def api_post(path, body, uid, admin):
    if not isinstance(body, dict):
        return 400, {"ok": False, "error": "Noto‘g‘ri so‘rov."}
    p = path.split("?")[0]
    if p == "/api/eq/vote":
        return api_vote(uid, body)
    if not admin:
        return 403, {"ok": False, "error": "Faqat admin."}
    return {"/api/eq/save": api_save, "/api/eq/delete": api_delete, "/api/eq/settings": api_settings}.get(
        p, lambda b: (404, {"ok": False, "error": "Topilmadi"}))(body)


# --- bot ichida ko'rish, test va ulashish
def share_url(qid):
    bu = _cfg["bot_username"]()
    if not bu:
        return ""
    from urllib.parse import quote
    link = f"https://t.me/{bu}?start=q_{int(qid)}"
    return f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(SHARE_TEASER, safe='')}"


def _opt_line(L, t):
    return f"{L}) {t}"


def pub_text(r, show_answer, lock="closed"):
    opts = _opts_of(r)
    body = _e(r["question"])
    if any(opts):
        body += "\n\n" + "\n".join(_e(_opt_line(L, t)) for L, t in zip(OPT_LETTERS, opts) if t)
    if show_answer:
        a = (r["answer"] or "").upper()
        if a in OPT_LETTERS and opts[OPT_LETTERS.index(a)]:
            ans = _e(_opt_line(a, opts[OPT_LETTERS.index(a)]))
        else:
            ans = _e(r["answer"] or "—")
        if r["explain"]:
            ans += f"\n💡 {_e(r['explain'])}"
    elif lock == "contrib":
        ans = "🔑 Hissa qo‘shuvchilarga birinchi ochiladi — /savollar orqali savollaringizni kiriting"
    else:
        ans = "🔒 Admin ochganda ko‘rinadi"
    return (f"📋 <b>Tushgan savol</b> • {_e(_group_label(r['slot']))}\n\n"
            f"👤 <b>Foydalanuvchi:</b> {_e(_display_name(r))}\n\n"
            f"❓ <b>Tushgan savol:</b>\n{body}\n\n"
            f"✅ <b>Javob:</b> {ans}")


def vote_dist(pid, min_total=5):
    """Boshqalar qaysi variantni tanlagani (foizda). Kam ovoz bo'lsa None."""
    with db() as c:
        rows = c.execute("SELECT letter, COUNT(*) FROM exam_vote WHERE pub_id=? GROUP BY letter", (int(pid),)).fetchall()
    tot = sum(k for _, k in rows)
    if tot < min_total:
        return None
    d = {L: 0 for L in OPT_LETTERS}
    for L, k in rows:
        if L in d: d[L] = round(100 * k / tot)
    d["total"] = tot
    return d


def _dist_line(d):
    if not d:
        return ""
    return "📊 <b>Boshqalar ({} kishi):</b> ".format(d["total"]) + " • ".join(f"{L} {d[L]}%" for L in OPT_LETTERS if d.get(L))


def _pub_markup(r, see, uid, voted=None):
    qid = int(r["id"]); opts = _opts_of(r); rows = []
    if any(opts) and not (see and voted):
        rows.append([InlineKeyboardButton(("✅ " if voted == L else "") + L, callback_data=f"ex_v_{qid}_{L}") for L, t in zip(OPT_LETTERS, opts) if t])
    if any(opts):
        rows.append([InlineKeyboardButton("Keyingi savol ▶", callback_data=f"ex_nx_{qid}")])
    url = _cfg["miniapp_url"]()
    if url:
        sep = "&" if "?" in url else "?"
        rows.append([InlineKeyboardButton("📚 Barcha tushgan savollar", web_app=WebAppInfo(url=f"{url}{sep}eq={qid}"))])
    su = share_url(qid)
    if su:
        rows.append([InlineKeyboardButton("📤 Ulashish", url=su)])
    return InlineKeyboardMarkup(rows) if rows else None


async def _send_pub(bot, uid, r, admin=False):
    slot = r["slot"] or ""
    see = can_see(slot, uid, admin)
    opts = _opts_of(r)
    txt = pub_text(r, see, "contrib" if ans_mode(slot) == "contrib" else "closed")
    if any(opts):
        txt += "\n\n👇 <b>Sizningcha to‘g‘ri javob qaysi?</b> Variantni belgilang:"
    kw = dict(chat_id=int(uid), text=txt, parse_mode="HTML", reply_markup=_pub_markup(r, see, uid))
    try:
        await bot.send_message(protect_content=True, **kw)
    except TypeError:
        await bot.send_message(**kw)


async def send_deeplink_question(bot, uid, qid):
    """/start q_<id>: savolni ko'rsatadi (nashr qilingan va bo'lim ochiq bo'lsa; admin har doim ko'radi) + test tugmalari."""
    with db() as c:
        r = c.execute("SELECT * FROM exam_pub WHERE id=?", (int(qid),)).fetchone()
    admin = int(uid) == int(_cfg["admin_id"])
    if not r or (r["status"] != "published" and not admin):
        await bot.send_message(chat_id=int(uid), text="Bu savol topilmadi yoki hali tayyor emas.")
        return
    if not eq_public() and not admin:
        await bot.send_message(chat_id=int(uid), text="🛠 Tushgan savollar bo‘limi hozir tayyorlanmoqda. Tez orada shu yerda ochiladi 💙")
        return
    await _send_pub(bot, uid, r, admin)


def _next_pub(uid, after_id):
    with db() as c:
        rows = [(int(r[0]), r[1]) for r in c.execute("SELECT id,opts FROM exam_pub WHERE status='published' ORDER BY slot,id")]
        voted = {int(r[0]) for r in c.execute("SELECT pub_id FROM exam_vote WHERE user_id=?", (int(uid),))}
    ids = [i for i, o in rows if any(_json_opts(o))]
    todo = [i for i in ids if i not in voted]
    if not todo:
        return None
    pos = ids.index(after_id) if after_id in ids else -1
    for i in ids[pos + 1:]:
        if i in todo: return i
    return todo[0]


async def next_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    try: cur = int((q.data or "").split("_")[2])
    except Exception:
        await q.answer(); return
    admin = int(uid) == int(_cfg["admin_id"])
    if not eq_public() and not admin:
        await q.answer("Bo‘lim hozir tayyorlanmoqda 🛠", show_alert=True); return
    await q.answer()
    nid = _next_pub(uid, cur)
    if nid is None:
        url = _cfg["miniapp_url"]()
        kb = None
        if url:
            sep = "&" if "?" in url else "?"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("📚 Barcha tushgan savollar", web_app=WebAppInfo(url=f"{url}{sep}eq=1"))]])
        await context.bot.send_message(uid, "🎉 Hamma savolga javob berdingiz! Yangi savollar qo‘shilsa, xabar beramiz.", reply_markup=kb); return
    with db() as c:
        r = c.execute("SELECT * FROM exam_pub WHERE id=?", (nid,)).fetchone()
    await _send_pub(context.bot, uid, r, admin)


def pend_q_set(uid, qid):
    """Obuna bo'lmagan odam havola ochgan: obunadan keyin shu savol ko'rsatiladi."""
    with db() as c:
        c.execute("INSERT INTO exam_pendq(user_id,qid,at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET qid=excluded.qid, at=excluded.at", (int(uid), int(qid), _iso())); c.commit()


def pend_q_pop(uid):
    with db() as c:
        r = c.execute("SELECT qid FROM exam_pendq WHERE user_id=?", (int(uid),)).fetchone()
        if r:
            c.execute("DELETE FROM exam_pendq WHERE user_id=?", (int(uid),)); c.commit()
    return int(r[0]) if r else None


async def vote_cb(update, context):
    q = update.callback_query; uid = q.from_user.id
    try:
        parts = (q.data or "").split("_"); body = {"id": int(parts[2]), "letter": parts[3]}
    except Exception:
        await q.answer(); return
    st, res = api_vote(uid, body)
    if not res.get("ok"):
        await q.answer(res.get("error", "Xatolik"), show_alert=True); return
    if res["visible"]:
        if res.get("is_right"):
            short = f"✅ To‘g‘ri! Javob: {res['correct']}"
        else:
            short = f"❌ Noto‘g‘ri. To‘g‘ri javob: {res.get('correct') or '—'}"
        res_line = short + (f"\n💡 {_e(res['explain'])}" if res.get("explain") else "")
    elif res.get("lock") == "contrib":
        short = f"✅ Qabul qilindi: {res['letter']}"
        res_line = (f"✅ Javobingiz qabul qilindi: <b>{res['letter']}</b>.\n🔑 To‘g‘ri javob hissa qo‘shuvchilarga birinchi ochiladi — /savol orqali "
                    "eslagan savollaringizni yuboring.")
    else:
        short = f"✅ Qabul qilindi: {res['letter']}"
        res_line = f"✅ Javobingiz qabul qilindi: <b>{res['letter']}</b>.\n🔒 To‘g‘ri javob ochilganda sizga xabar beramiz."
    await q.answer(short[:200])
    try:                                                 # xabarni natija bilan yangilaymiz: to'liq izoh, foizlar, «Keyingi savol»
        with db() as c:
            r = c.execute("SELECT * FROM exam_pub WHERE id=?", (int(body["id"]),)).fetchone()
        admin = int(uid) == int(_cfg["admin_id"])
        see = can_see(r["slot"] or "", uid, admin)
        base = pub_text(r, see, "contrib" if ans_mode(r["slot"] or "") == "contrib" else "closed")
        txt = base + "\n\n" + res_line
        dl = _dist_line(res.get("dist"))
        if dl: txt += "\n" + dl
        await q.edit_message_text(text=txt[:4000], parse_mode="HTML", reply_markup=_pub_markup(r, see, uid, voted=res["letter"]))
    except Exception:
        log.debug("vote_cb edit", exc_info=True)


async def notify_answers(bot, slots, mode):
    """Javoblar ochilganda: test belgilaganlarga natija, hissa qo'shuvchilarga 'birinchi ko'ryapsiz' xabari (har biriga bir marta)."""
    if not eq_public() or not slots:
        return 0
    url = _cfg["miniapp_url"]()
    kb = None
    if url:
        sep = "&" if "?" in url else "?"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📚 Tushgan savollarni ochish", web_app=WebAppInfo(url=f"{url}{sep}eq=1"))]])
    ph = ",".join("?" * len(slots))
    with db() as c:
        rows = c.execute(f"SELECT v.user_id,p.slot,p.answer,v.letter FROM exam_vote v JOIN exam_pub p ON p.id=v.pub_id "
                         f"WHERE p.status='published' AND p.slot IN ({ph})", list(slots)).fetchall()
        contribs = [int(r[0]) for r in c.execute("SELECT user_id FROM exam_q WHERE skipped=0 AND cid IS NOT NULL GROUP BY user_id HAVING COUNT(*)>=?", (Q_MIN,))]
    per = {}
    for uid, slot, ans, letter in rows:
        uid = int(uid)
        if mode == "contrib" and not is_contributor(uid):
            continue
        d = per.setdefault((uid, slot), [0, 0]); d[0] += 1; d[1] += 1 if ans and letter == ans else 0
    sent = 0
    for (uid, slot), (n, k) in per.items():
        kind = f"an_{slot}_{mode}"
        with db() as c:
            if c.execute("SELECT 1 FROM exam_sent WHERE user_id=? AND kind=?", (uid, kind)).fetchone(): continue
        txt = f"🔓 <b>Javoblar ochildi!</b> {_e(_group_label(slot))}: {n} ta savolga javob bergan edingiz — <b>{k} tasi to‘g‘ri</b> 👏"
        ok, _ = await _safe(lambda: bot.send_message(chat_id=uid, text=txt, parse_mode="HTML", reply_markup=kb))
        _mark_sent(uid, kind); sent += 1 if ok else 0
        await asyncio.sleep(0.05)
    if mode == "contrib":
        for uid in contribs:
            kind = "an_contrib_" + ",".join(sorted(slots))
            with db() as c:
                if c.execute("SELECT 1 FROM exam_sent WHERE user_id=? AND kind=?", (uid, kind)).fetchone(): continue
            ok, _ = await _safe(lambda: bot.send_message(chat_id=uid, parse_mode="HTML", reply_markup=kb,
                                text="🔑 <b>Siz savollarni kiritganingiz uchun javoblarni birinchilar qatorida ko‘ryapsiz!</b> Rahmat 🙏"))
            _mark_sent(uid, kind); sent += 1 if ok else 0
            await asyncio.sleep(0.05)
    return sent


# --- admin buyruqlari
async def tushgan_cmd(update, context):
    """/tushgan — holat; /tushgan_och — bo'lim hammaga ochiladi; /tushgan_yop — yana faqat admin ko'radi."""
    if not _is_admin(update): return
    with db() as c:
        pub = c.execute("SELECT COUNT(*) FROM exam_pub WHERE status='published'").fetchone()[0]
        dr = c.execute("SELECT COUNT(*) FROM exam_pub WHERE status='draft'").fetchone()[0]
        raw = c.execute("SELECT COUNT(*) FROM exam_qc").fetchone()[0]
        votes = c.execute("SELECT COUNT(*) FROM exam_vote").fetchone()[0]
    names = {"all": "hammaga ochiq", "contrib": "hissa qo‘shuvchilarga", "closed": "yopiq"}
    am = _setting("eq_ans_all", "0")
    summary = names[ans_mode("")] if am in ("1", "c") else ", ".join(f"{slot_label(c_)}: {names[ans_mode(c_)]}" for c_ in slot_codes() if ans_mode(c_) != "closed") or "hammasi yopiq"
    await update.message.reply_text(
        "📋 <b>TUSHGAN SAVOLLAR</b>\n\n"
        f"Bo‘lim: <b>{'hammaga ochiq ✅' if eq_public() else 'faqat admin (jarayonda) 🔒'}</b>\n"
        f"Nashr qilingan: {pub} • Qoralama: {dr} • Klasterlar (kelgan xom savollar): {raw} • Belgilangan javoblar: {votes}\n"
        f"Javoblar: <b>{_e(summary)}</b>\n\n"
        "/tushgan_och — bo‘limni hammaga ochish\n/tushgan_yop — yopish\n"
        "/javob_och 24-1 hissa — javob avval hissa qo‘shuvchilarga\n/javob_och 24-1 — javob hammaga\n/javob_yop 24-1 (yoki hammasi)\n"
        "/kalit_avto — nashr qilingan javoblardan 44 talik kalit\nTahrirlash: Mini App → 📋 Tushgan savollar.", parse_mode="HTML")


async def tushgan_och_cmd(update, context):
    if not _is_admin(update): return
    _set("eq_public", "1"); await update.message.reply_text("✅ «Tushgan savollar» bo‘limi endi hammaga ochiq.")


async def tushgan_yop_cmd(update, context):
    if not _is_admin(update): return
    _set("eq_public", "0"); await update.message.reply_text("🔒 Bo‘lim yopildi: hamma uchun «tayyorlanmoqda», faqat siz ko‘rasiz.")


async def _javob_toggle(update, context, on):
    if not _is_admin(update): return
    args = [x.lower() for x in (context.args or [])]
    target = args[0] if args else "hammasi"
    mode = "contrib" if (len(args) > 1 and args[1] in ("hissa", "hissador", "birinchi")) else "all"
    if target in ("hammasi", "hamma", "all"):
        slots = slot_codes(); _set("eq_ans_all", _mode_value(mode) if on else "0")
        if not on:
            for c_ in slot_codes(): _set(f"eq_ans_{c_}", "0")
    elif parse_slot(target):
        slots = [target]; _set(f"eq_ans_{target}", _mode_value(mode) if on else "0")
    else:
        await update.message.reply_text("Misol: /javob_och 24-1 hissa   •   /javob_och 24-1   •   /javob_och hammasi   •   /javob_yop hammasi"); return
    lab = "hammasi" if target in ("hammasi", "hamma", "all") else slot_label(target)
    if not on:
        await update.message.reply_text(f"🔒 {lab}: javoblar yopildi."); return
    await update.message.reply_text(f"🔓 {lab}: javoblar {'avval hissa qo‘shuvchilarga ochildi 🔑' if mode == 'contrib' else 'hammaga ochildi'}. Xabarlar yuborilmoqda…")
    t = asyncio.create_task(notify_answers(context.bot, slots, mode)); _TASKS.add(t); t.add_done_callback(_TASKS.discard)


async def javob_och_cmd(update, context): await _javob_toggle(update, context, True)
async def javob_yop_cmd(update, context): await _javob_toggle(update, context, False)


async def kalit_avto_cmd(update, context):
    """/kalit_avto — nashr qilingan savollarning to'g'ri javoblaridan (savol raqami bo'yicha, ko'pchilik) 44 talik kalit tuzadi."""
    if not _is_admin(update): return
    with db() as c:
        rows = c.execute("SELECT src_qno,UPPER(answer) FROM exam_pub WHERE status='published' AND src_qno IS NOT NULL AND UPPER(answer) IN ('A','B','C','D')").fetchall()
    by = {}
    for n, a in rows:
        by.setdefault(int(n), {}).setdefault(a, 0); by[int(n)][a] += 1
    key = "".join((max(by[n], key=by[n].get) if n in by else "-") for n in range(1, TOTAL_Q + 1))
    if key.count("-") == TOTAL_Q:
        await update.message.reply_text("Nashr qilingan savollar orasida to‘g‘ri javobi (A–D) kiritilgani yo‘q."); return
    _set("exam_key", key)
    cov = coverage(); weak = [n for n in range(1, TOTAL_Q + 1) if cov.get(n, 0) < COVER_TARGET]
    warn = (f"\n⚠️ Hali {len(weak)} ta savol {COVER_TARGET} kishidan kam yig‘ilgan ({', '.join(map(str, weak[:15]))}{'…' if len(weak) > 15 else ''}) — natijani shoshilmay yuboring.") if weak else ""
    await update.message.reply_text(f"✅ Kalit tuzildi: {TOTAL_Q - key.count('-')}/{TOTAL_Q} ta savol.\n{key}\nNoma’lum joylar '-' . /natija_yubor bilan natijalarni yuboring.{warn}")


# ----------------------------------------------------------------------------- admin
def _is_admin(update):
    return bool(update.effective_user and update.effective_user.id == _cfg["admin_id"])


async def sorov_test_cmd(update, context):
    """/sorov_test — so'rovnomani faqat adminning o'ziga yuboradi (ko'rib chiqish)."""
    if not _is_admin(update): return
    await send_kind(context.bot, update.effective_user.id, "survey")


async def imtihon_test_cmd(update, context):
    """/imtihon_test <confirm|eve|morning|after> [24-1] — xabarni faqat adminga yuboradi."""
    if not _is_admin(update): return
    a = context.args or []
    kind = (a[0] if a else "morning").lower(); code = a[1] if len(a) > 1 else f"{DAYS[1]}-1"
    if kind not in ("survey", "confirm", "eve", "morning", "after") or (kind != "survey" and not parse_slot(code)):
        await update.message.reply_text("Misol: /imtihon_test morning 25-1\nTurlar: confirm, eve, morning, after, survey"); return
    await send_kind(context.bot, update.effective_user.id, kind, code)


async def broadcast_survey(bot, kind="survey", only_unanswered=False):
    with db() as c:
        ids = [int(r[0]) for r in c.execute("SELECT user_id FROM users")]
        done = {int(r[0]) for r in c.execute("SELECT user_id FROM exam_survey_log WHERE kind=?", (kind,))}
        have = {int(r[0]) for r in c.execute("SELECT user_id FROM exam_slot")}
    todo = [u for u in ids if u not in done and u not in have and not _cfg["is_banned"](u)]
    ok = bad = 0
    for uid in todo:
        r, why = await _safe(lambda: send_kind(bot, uid, "survey"))
        with db() as c:
            c.execute("INSERT OR REPLACE INTO exam_survey_log(user_id,kind,ok,at) VALUES(?,?,?,?)", (uid, kind, 1 if r else 0, _iso())); c.commit()
        ok += 1 if r else 0; bad += 0 if r else 1
        await asyncio.sleep(0.05)
    return len(todo), ok, bad


async def _run_broadcast(bot, kind):
    try:
        total, ok, bad = await broadcast_survey(bot, kind)
        await bot.send_message(_cfg["admin_id"], f"✅ So‘rovnoma tugadi.\nYuborildi: {ok}\nYetmadi (bot bloklangan va b.): {bad}\nJami urinish: {total}")
    except Exception as e:
        log.exception("broadcast_survey")
        try: await bot.send_message(_cfg["admin_id"], f"⚠️ So‘rovnoma yuborishda xato: {e}")
        except Exception: pass


def build_roster(mode="answered"):
    """/sorov_royxat uchun ro'yxat. mode: 'answered' (hammasi), 'yoq' (javob bermaganlar), 'later' yoki slot kodi (masalan 25-1).
    Qaytaradi: (csv_bytes, qatorlar_soni, sanalar_boyicha_hisob)"""
    import csv
    with db() as c:
        users = {int(r[0]): (r[1] or "", r[2] or "", r[3] or "") for r in c.execute("SELECT user_id, username, first_name, last_name FROM users")}
        slots = {int(r[0]): (r[1], r[2] or "") for r in c.execute("SELECT user_id, slot, chosen_at FROM exam_slot")}
        got = {int(r[0]): int(r[1] or 0) for r in c.execute("SELECT user_id, ok FROM exam_survey_log WHERE kind IN ('survey','survey2')")}
    rows, per = [], {}
    for uid, (un, fn, ln) in users.items():
        sl = slots.get(uid)
        if mode == "yoq":
            if sl: continue
        elif mode == "answered":
            if not sl: continue
        elif sl is None or sl[0] != mode:
            continue
        code = sl[0] if sl else ""
        label = slot_label(code) if sl else "Javob bermagan"
        per[label] = per.get(label, 0) + 1
        status = "yetmagan (bloklangan)" if (uid in got and not got[uid]) else ("yetgan" if uid in got else "")
        rows.append([uid, (fn + " " + ln).strip(), ("@" + un) if un else "", label, code, (sl[1][:16].replace("T", " ") if sl else ""), status])
    rows.sort(key=lambda r: (r[4] or "zz", r[1].lower()))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "ism", "username", "imtihon_sanasi", "kod", "tanlagan_vaqti_UTC", "sorovnoma"])
    w.writerows(rows)
    return ("\ufeff" + buf.getvalue()).encode("utf-8"), len(rows), per


async def sorov_royxat_cmd(update, context):
    """/sorov_royxat — sana tanlaganlar (kim qaysi sanani tanlagan) CSV fayl bilan.
    /sorov_royxat 25-1  — faqat shu smena;  /sorov_royxat later — 'keyinroq' deganlar;  /sorov_royxat yoq — javob bermaganlar."""
    if not _is_admin(update): return
    a = [x.lower() for x in (context.args or [])]
    mode = "answered"
    if a:
        if a[0] in ("yoq", "later") or parse_slot(a[0]): mode = a[0]
        else:
            await update.message.reply_text("Misol:\n/sorov_royxat — sana tanlaganlar\n/sorov_royxat 25-1 — shu smena\n/sorov_royxat later — keyinroq deganlar\n/sorov_royxat yoq — javob bermaganlar"); return
    csv_b, n, per = await asyncio.to_thread(build_roster, mode)
    if not n:
        await update.message.reply_text("Bu bo‘yicha foydalanuvchi topilmadi."); return
    title = {"answered": "Sana tanlaganlar", "yoq": "Javob bermaganlar", "later": "Keyinroq deganlar"}.get(mode, slot_label(mode))
    lines = [f"📋 <b>{_e(title)}</b>: {n} kishi"] + [f"• {_e(k)}: <b>{v}</b>" for k, v in sorted(per.items())]
    stamp = now_tk().strftime("%d%m_%H%M")
    await update.message.reply_text("\n".join(lines)[:3500], parse_mode="HTML")
    await context.bot.send_document(chat_id=update.effective_user.id, document=InputFile(io.BytesIO(csv_b), filename=f"sorov_{mode}_{stamp}.csv"),
                                    caption="Excel yoki Google Sheets'da oching.")



async def sorov_yubor_cmd(update, context):
    """/sorov_yubor — oldindan ko'rish; /sorov_yubor tasdiq — hammaga; /sorov_yubor qayta — javob bermaganlarga 2-eslatma."""
    if not _is_admin(update): return
    a = [x.lower() for x in (context.args or [])]
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        have = c.execute("SELECT COUNT(*) FROM exam_slot").fetchone()[0]
    if not a:
        await update.message.reply_text(f"👥 Foydalanuvchilar: {total}\n✅ Sana tanlaganlar: {have}\n\n"
                                        "Avval /sorov_test bilan ko‘rib chiqing.\n"
                                        "Hammaga yuborish: /sorov_yubor tasdiq\n"
                                        "Javob bermaganlarga qayta: /sorov_yubor qayta")
        return
    if a[0] == "tasdiq": kind = "survey"
    elif a[0] == "qayta": kind = "survey2"
    else:
        await update.message.reply_text("Noto‘g‘ri. /sorov_yubor tasdiq  yoki  /sorov_yubor qayta"); return
    t = asyncio.create_task(_run_broadcast(context.bot, kind)); _TASKS.add(t); t.add_done_callback(_TASKS.discard)
    await update.message.reply_text("🚀 Yuborish boshlandi (fon rejimida). Tugagach hisobot keladi. Qayta ishga tushirsangiz, yuborilganlarga takror ketmaydi.")


async def sorov_stat_cmd(update, context):
    if not _is_admin(update): return
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        per = dict(c.execute("SELECT slot, COUNT(*) FROM exam_slot GROUP BY slot").fetchall())
        sent = c.execute("SELECT COUNT(*) FROM exam_survey_log WHERE ok=1").fetchone()[0]
        hows = dict(c.execute("SELECT how, COUNT(*) FROM exam_fb WHERE how IS NOT NULL GROUP BY how").fetchall())
        essays = [r[0] for r in c.execute("SELECT essay FROM exam_fb WHERE essay IS NOT NULL AND essay<>'' ORDER BY updated_at DESC LIMIT 15")]
    ans = sum(per.values())
    lines = [f"📊 <b>IMTIHON SO‘ROVNOMASI</b>", f"Foydalanuvchilar: {total} • So‘rovnoma yetgan: {sent} • Javob: {ans}", ""]
    for code in slot_codes():
        lines.append(f"{slot_label(code)}: <b>{per.get(code, 0)}</b>")
    lines.append(f"Keyinroq topshiraman: <b>{per.get('later', 0)}</b>")
    if hows:
        lines += ["", f"Imtihondan keyin: 😊 {hows.get('g', 0)} • 😐 {hows.get('m', 0)} • 😓 {hows.get('h', 0)}"]
        n, cnt = topic_stats()
        if n:
            lines.append(f"\nMavzular ({n} javob):")
            for i, c_ in sorted(cnt.items(), key=lambda x: -x[1]):
                lines.append(f"• {TOPICS[i]}: {c_} ({round(100 * c_ / n)}%)")
    with db() as c:
        qu = c.execute("SELECT COUNT(DISTINCT user_id), COUNT(*) FROM exam_q WHERE skipped=0 AND cid IS NOT NULL").fetchone()
    if qu and qu[1]:
        lines += ["", f"📋 Savol yozganlar: {qu[0]} kishi, jami {qu[1]} ta savol (/savollar_fayl — Word, /yigish — qamrov)"]
    if essays:
        lines += ["", "✍️ Oxirgi esse mavzulari (faqat admin ko‘radi):"] + [f"• {_e(x)}" for x in essays]
    await update.message.reply_text("\n".join(lines)[:4000], parse_mode="HTML")


def register(app):
    app.add_handler(CallbackQueryHandler(slot_cb, pattern=r"^ex_(s_(" + "|".join(str(x) for x in DAYS) + r")_[12]|s_later|chg)$"))
    app.add_handler(CallbackQueryHandler(how_cb, pattern=r"^ex_h_[gmh]$"))
    app.add_handler(CallbackQueryHandler(topic_cb, pattern=r"^ex_t_([0-9]+|done)$"))
    app.add_handler(CallbackQueryHandler(essay_skip_cb, pattern=r"^ex_e_skip$"))
    app.add_handler(CallbackQueryHandler(stats_cb, pattern=r"^ex_stats$"))
    app.add_handler(CallbackQueryHandler(q_start_cb, pattern=r"^ex_q_start$"))
    app.add_handler(CallbackQueryHandler(q_done_cb, pattern=r"^ex_q_done$"))
    app.add_handler(CallbackQueryHandler(q_need_cb, pattern=r"^ex_q_need$"))
    app.add_handler(CallbackQueryHandler(q_slot_cb, pattern=r"^ex_qs_([0-9]+_[12]|x)$"))
    app.add_handler(CallbackQueryHandler(next_cb, pattern=r"^ex_nx_[0-9]+$"))
    app.add_handler(CallbackQueryHandler(score_cb, pattern=r"^ex_score$"))
    app.add_handler(CommandHandler(["savol", "savollar"], savollar_cmd))
    app.add_handler(CommandHandler("yigish", yigish_cmd))
    app.add_handler(CommandHandler("takror_fayl", takror_fayl_cmd))
    app.add_handler(CommandHandler("savollar_fayl", savollar_fayl_cmd))
    app.add_handler(CommandHandler("kalit", kalit_cmd))
    app.add_handler(CommandHandler("natija_yubor", natija_yubor_cmd))
    app.add_handler(CallbackQueryHandler(vote_cb, pattern=r"^ex_v_[0-9]+_[A-D]$"))
    app.add_handler(CommandHandler("kalit_avto", kalit_avto_cmd))
    app.add_handler(CommandHandler("tushgan", tushgan_cmd))
    app.add_handler(CommandHandler("tushgan_och", tushgan_och_cmd))
    app.add_handler(CommandHandler("tushgan_yop", tushgan_yop_cmd))
    app.add_handler(CommandHandler("javob_och", javob_och_cmd))
    app.add_handler(CommandHandler("javob_yop", javob_yop_cmd))
    app.add_handler(CommandHandler("imtihon", imtihon_cmd))
    app.add_handler(CommandHandler("sorov_test", sorov_test_cmd))
    app.add_handler(CommandHandler("sorov_yubor", sorov_yubor_cmd))
    app.add_handler(CommandHandler("sorov_stat", sorov_stat_cmd))
    app.add_handler(CommandHandler("sorov_royxat", sorov_royxat_cmd))
    app.add_handler(CommandHandler("imtihon_test", imtihon_test_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & _PendingFilter(), essay_text_cb), group=-4)
