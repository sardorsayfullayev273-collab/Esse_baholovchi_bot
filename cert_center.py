"""cert_center — v105: «Rasmiy natija» bo'limi, sertifikat sanalari bildirishnomalari va bosh sahifa bo'limlari tartibi.

Sanalar rasmiy e'lonlarga ko'ra boshlang'ich qiymat bilan keladi, lekin ADMIN o'zgartira oladi (/sertifikat_sana).
Bildirishnomalar faqat foydalanuvchi o'zi tanlaganlarga boradi (Mini App -> Rasmiy natija -> eslatmalar).
Bosh sahifa: bo'limlar oxirgi 14 kunda eng ko'p noyob foydalanuvchi kirgan tartibda; admin bitta bo'limni birinchiga qadashi mumkin.
"""
import json, asyncio, logging
from datetime import datetime, timedelta, timezone, date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import CommandHandler

from national_certificate import db, setting, set_setting

log = logging.getLogger("cert_center")
TZ = timezone(timedelta(hours=5))

# ---- sozlama (admin o'zgartiradi)
DEFAULTS = {
    "exam_label": "Ona tili va adabiyot • 24–26-oktabr",
    "result_from": "2026-11-20",     # taxminiy oraliq (agentlik natijani ~21 ish kunida e'lon qiladi)
    "result_to": "2026-11-24",
    "result_date": "",               # rasmiy e'lon sanasi (admin kiritadi; kiritilsa o'sha kuni ertalab xabar ketadi)
    "reg_open": "2026-11-20",        # dekabr sertifikati: ro'yxatdan o'tish boshlanadi
    "reg_close": "2026-12-04",
    "pay_close": "2026-12-05",
    "exam_from": "2026-12-26",
    "exam_to": "2026-12-28",
    "fee": "594000",
}
DATE_KEYS = ("result_from", "result_to", "result_date", "reg_open", "reg_close", "pay_close", "exam_from", "exam_to")
SEND_HOUR = 9           # Toshkent vaqti bilan shu soatdan keyin yuboriladi
KINDS = {
    "result":   "📢 Natija e’lon qilinganda",
    "reg_open": "📝 Dekabr ro‘yxati ochilganda",
    "reg_soon": "⏳ Ro‘yxat yopilishiga 3 kun qolganda",
    "reg_last": "🚨 Ro‘yxatdan o‘tishning oxirgi kuni",
    "pay_last": "💳 To‘lovning oxirgi kuni",
}
HOME_SECS = ["national", "expert", "prep", "mashq", "eq", "alifbo", "dicts"]
HOME_NAMES = {"national": "Diagnostik test", "expert": "Esse tekshirish", "prep": "Tayyorlov", "mashq": "Mashq",
              "eq": "Tushgan savollar", "alifbo": "Yangi alifbo", "dicts": "Lug‘atlar"}
HOME_ALIAS = {"diagnostik": "national", "test": "national", "esse": "expert", "tekshirish": "expert", "tayyorlov": "prep",
              "mashq": "mashq", "savollar": "eq", "tushgan": "eq", "alifbo": "alifbo", "lugat": "dicts", "lugatlar": "dicts", "lug'at": "dicts"}
_ADMIN = {"id": None, "banned": None, "webapp": None}


def configure(admin_id, is_banned=None, webapp_url=None):
    _ADMIN.update(id=admin_id, banned=is_banned, webapp=webapp_url)


def init():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS cert_notify(user_id INTEGER NOT NULL, kind TEXT NOT NULL, at TEXT, PRIMARY KEY(user_id,kind))")
        c.execute("CREATE TABLE IF NOT EXISTS cert_sent(user_id INTEGER NOT NULL, key TEXT NOT NULL, at TEXT, PRIMARY KEY(user_id,key))")
        c.commit()


def now_tk():
    return datetime.now(TZ)


def cfg():
    out = dict(DEFAULTS)
    try:
        saved = json.loads(setting("cert_cfg", "") or "{}")
        if isinstance(saved, dict):
            for k, v in saved.items():
                if k in DEFAULTS: out[k] = str(v)
    except Exception:
        log.exception("cert cfg")
    return out


def _d(s):
    try: return date.fromisoformat(str(s)[:10])
    except Exception: return None


def set_cfg(key, value):
    if key not in DEFAULTS: return False, "Noma’lum kalit."
    v = str(value).strip()
    if key in DATE_KEYS and v and v != "-" and not _d(v): return False, "Sana YYYY-MM-DD ko‘rinishida bo‘lsin (masalan 2026-12-04)."
    if v == "-": v = ""
    cur = cfg(); cur[key] = v
    set_setting("cert_cfg", json.dumps({k: cur[k] for k in DEFAULTS}, ensure_ascii=False))
    return True, ""


# ---- foydalanuvchi tanlovlari
def prefs(uid):
    with db() as c:
        return sorted(r[0] for r in c.execute("SELECT kind FROM cert_notify WHERE user_id=?", (int(uid),)).fetchall())


def set_pref(uid, kind, on):
    kinds = list(KINDS) if kind == "all" else ([kind] if kind in KINDS else [])
    if not kinds: return False
    with db() as c:
        for k in kinds:
            if on: c.execute("INSERT OR IGNORE INTO cert_notify(user_id,kind,at) VALUES(?,?,?)", (int(uid), k, now_tk().isoformat(timespec="seconds")))
            else: c.execute("DELETE FROM cert_notify WHERE user_id=? AND kind=?", (int(uid), k))
        c.commit()
    return True


# ---- bosh sahifa tartibi
def home_pin():
    p = (setting("home_pin", "") or "").strip()
    return p if p in HOME_SECS else ""


def set_home_pin(sec):
    set_setting("home_pin", sec if sec in HOME_SECS else "")


def view_counts(days=14):
    since = (now_tk() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    out = {s: (0, 0) for s in HOME_SECS}
    try:
        with db() as c:
            for sec, u, n in c.execute("SELECT section, COUNT(DISTINCT user_id), COALESCE(SUM(n),0) FROM section_views WHERE day>=? GROUP BY section", (since,)).fetchall():
                if sec in out: out[sec] = (int(u), int(n))
    except Exception:
        log.exception("view_counts")
    return out


def home_order():
    cnt = view_counts()
    base = {s: i for i, s in enumerate(HOME_SECS)}
    order = sorted(HOME_SECS, key=lambda s: (-cnt[s][0], -cnt[s][1], base[s]))
    pin = home_pin()
    if pin:
        order = [pin] + [s for s in order if s != pin]
    return order, pin


# ---- API (bot-1-1.py HTTP handler chaqiradi)
def info(uid):
    c = cfg()
    t = now_tk().date()
    ro, rc = _d(c["reg_open"]), _d(c["reg_close"])
    state = "unknown"
    if ro and rc:
        state = "before" if t < ro else ("open" if t <= rc else "closed")
    return {"ok": True, "cfg": c, "kinds": KINDS, "prefs": prefs(uid) if uid else [], "today": t.isoformat(), "reg_state": state}


def api_get(path, uid, admin):
    p = path.split("?")[0]
    if p == "/api/sc/info": return 200, info(uid)
    if p == "/api/home/order":
        o, pin = home_order(); return 200, {"ok": True, "order": o, "pin": pin}
    return 404, {"ok": False, "error": "Topilmadi"}


def api_post(path, body, uid, admin):
    p = path.split("?")[0]
    if not isinstance(body, dict): return 400, {"ok": False, "error": "Noto‘g‘ri so‘rov."}
    if p == "/api/sc/notify":
        kind = str(body.get("kind", "")); on = bool(body.get("on"))
        if not set_pref(uid, kind, on): return 400, {"ok": False, "error": "Noto‘g‘ri tur."}
        return 200, {"ok": True, "prefs": prefs(uid)}
    return 404, {"ok": False, "error": "Topilmadi"}


# ---- xabar matnlari
def _fmt(s):
    d = _d(s)
    if not d: return str(s or "—")
    mon = ["", "yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"][d.month]
    return f"{d.day}-{mon}"


def message_for(kind, c=None):
    c = c or cfg()
    reg = f"{_fmt(c['reg_open'])} – {_fmt(c['reg_close'])}"
    exam = f"{_fmt(c['exam_from'])}–{_fmt(c['exam_to'])}"
    tail = ("\n\n🌐 my.gov.uz (OneID) orqali ro‘yxatdan o‘ting. Hududingizdagi o‘rinlar tugasa, ro‘yxat muddatidan oldin yopilib qolishi mumkin — "
            "kechiktirmang.")
    if kind == "reg_open":
        return (f"📝 <b>Ro‘yxatdan o‘tish boshlandi!</b>\n\nOna tili va adabiyot bo‘yicha dekabr sertifikat imtihoni: <b>{exam}</b>.\n"
                f"Ro‘yxat: {reg}\nTo‘lov: {_fmt(c['pay_close'])}gacha{tail}")
    if kind == "reg_soon":
        return (f"⏳ <b>Ro‘yxatdan o‘tishga 3 kun qoldi</b>\n\nOxirgi kun: <b>{_fmt(c['reg_close'])}</b>, to‘lov: {_fmt(c['pay_close'])}gacha.\n"
                f"Imtihon: {exam}.{tail}")
    if kind == "reg_last":
        return (f"🚨 <b>Bugun ro‘yxatdan o‘tishning OXIRGI kuni!</b>\n\nOna tili va adabiyot ({exam}) uchun bugun ariza topshirmasangiz, "
                f"imtihondan qolasiz. To‘lov: {_fmt(c['pay_close'])}gacha.{tail}")
    if kind == "pay_last":
        return (f"💳 <b>Bugun to‘lovning oxirgi kuni</b>\n\nAriza topshirgan bo‘lsangiz ham, to‘lov qilinmasa ro‘yxat bekor bo‘lishi mumkin.\n"
                f"Imtihon: {exam}.\n\n🌐 my.gov.uz")
    if kind == "result":
        return ("📢 <b>Natijalar e’lon qilindi</b>\n\nOna tili va adabiyot (24–26-oktabr) natijalarini my.gov.uz orqali ko‘rishingiz mumkin.\n"
                "Ballingizni botdagi «Rasmiy natija» kalkulyatoriga kiriting — daraja va kirishdagi imtiyozni ko‘rasiz.")
    return ""


def _trigger_dates(c):
    ro, rc, pc = _d(c["reg_open"]), _d(c["reg_close"]), _d(c["pay_close"])
    out = {}
    if ro: out["reg_open"] = ro
    if rc:
        out["reg_soon"] = rc - timedelta(days=3)
        out["reg_last"] = rc
    if pc: out["pay_last"] = pc
    rd = _d(c["result_date"])
    if rd: out["result"] = rd
    return out


def _keyboard(kind):
    rows = [[InlineKeyboardButton("🌐 my.gov.uz", url="https://my.gov.uz")]]
    try:
        url = _ADMIN["webapp"]() if _ADMIN["webapp"] else ""
    except Exception:
        url = ""
    if url:
        sep = "&" if "?" in url else "?"
        rows.append([InlineKeyboardButton("📋 Rasmiy natija bo‘limi", web_app=WebAppInfo(url=f"{url}{sep}go=certwin"))])
    return InlineKeyboardMarkup(rows)


def _blocked(uid):
    try:
        import exam_flow as ex
        if ex.is_blocked(uid): return True
    except Exception:
        pass
    try:
        return bool(_ADMIN["banned"] and _ADMIN["banned"](uid))
    except Exception:
        return False


async def send_kind(bot, kind, key, uids=None):
    """Obunachilarga (yoki ro'yxat berilsa shularga) bir marta yuboradi. Qaytaradi: (yuborildi, bloklangan, xato)."""
    text = message_for(kind)
    if not text: return 0, 0, 0
    with db() as c:
        ids = [int(r[0]) for r in c.execute("SELECT user_id FROM cert_notify WHERE kind=?", (kind,)).fetchall()] if uids is None else list(uids)
        done = {int(r[0]) for r in c.execute("SELECT user_id FROM cert_sent WHERE key=?", (key,)).fetchall()}
    sent = blocked = err = 0
    for uid in ids:
        if uid in done: continue
        if _blocked(uid): blocked += 1; continue
        try:
            await bot.send_message(chat_id=uid, text=text, parse_mode="HTML", reply_markup=_keyboard(kind), disable_web_page_preview=True)
            ok = True
        except Exception as e:
            name = type(e).__name__
            ok = False
            if name in ("Forbidden",):
                blocked += 1
                try:
                    import exam_flow as ex; ex.note_blocked(uid)
                except Exception: pass
                ok = None
            elif name == "RetryAfter":
                await asyncio.sleep(float(getattr(e, "retry_after", 2)) + 1)
                err += 1
            else:
                err += 1
        if ok:
            sent += 1
        if ok or ok is None:
            with db() as c:
                c.execute("INSERT OR IGNORE INTO cert_sent(user_id,key,at) VALUES(?,?,?)", (uid, key, now_tk().isoformat(timespec="seconds"))); c.commit()
        await asyncio.sleep(0.06)
    return sent, blocked, err


async def tick(bot, now=None):
    """Har 5 daqiqada: bugun sanasi kelgan turdagi bildirishnomalarni yuboradi (kuniga bir marta, 09:00 dan keyin)."""
    now = now or now_tk()
    if now.hour < SEND_HOUR or now.hour >= 21: return 0
    c = cfg(); today = now.date(); total = 0
    for kind, d in _trigger_dates(c).items():
        if d != today: continue
        s, b, e = await send_kind(bot, kind, f"{kind}:{d.isoformat()}")
        total += s
        if s or e: log.info("cert notify %s: sent=%s blocked=%s err=%s", kind, s, b, e)
    return total


async def scheduler_loop(bot):
    await asyncio.sleep(25)
    while True:
        try:
            await tick(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("cert tick")
        await asyncio.sleep(300)


# ---- admin buyruqlari
def _is_admin(update):
    return update.effective_user and update.effective_user.id == _ADMIN["id"]


async def sertifikat_sana_cmd(update, context):
    """/sertifikat_sana — sanalarni ko'rish; /sertifikat_sana reg_close 2026-12-04 — o'zgartirish ('-' = tozalash)."""
    if not _is_admin(update): return
    a = context.args or []
    if len(a) >= 2:
        ok, why = set_cfg(a[0], " ".join(a[1:]))
        if not ok: await update.message.reply_text("⚠️ " + why); return
    c = cfg()
    lines = ["📅 <b>Sertifikat sanalari</b> (Mini App va bildirishnomalar shundan oladi)", ""]
    lines += [f"<code>{k}</code> = {c[k] or '—'}" for k in DEFAULTS]
    lines += ["", "O‘zgartirish: /sertifikat_sana reg_close 2026-12-04", "result_date ni rasmiy e’londan keyin kiriting — o‘sha kuni 09:00 da obunachilarga xabar ketadi.",
              "Hozir eslatma tanlaganlar: " + ", ".join(f"{KINDS[k]} {_count(k)}" for k in KINDS)]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def _count(kind):
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM cert_notify WHERE kind=?", (kind,)).fetchone()[0]


async def natija_chiqdi_cmd(update, context):
    """/natija_chiqdi — natija e'lon qilindi xabarini obunachilarga hozir yuboradi (avval ko'rish, so'ng 'tasdiq')."""
    if not _is_admin(update): return
    n = _count("result")
    if "tasdiq" not in [x.lower() for x in (context.args or [])]:
        await update.message.reply_text(f"📢 «Natija e’lon qilindi» xabari {n} kishiga boradi.\nYuborish: /natija_chiqdi tasdiq"); return
    await update.message.reply_text(f"🚀 {n} kishiga yuborilmoqda…")
    s, b, e = await send_kind(context.bot, "result", "result:manual")
    await update.message.reply_text(f"✅ Yetdi: {s}\n🚫 Bloklagan: {b}\n⚠️ Xato: {e}")


async def bolim_royxat_cmd(update, context):
    """/bolim_royxat — bosh sahifa bo'limlari tartibi va oxirgi 14 kundagi ko'rishlar."""
    if not _is_admin(update): return
    cnt = view_counts(); order, pin = home_order()
    lines = ["🏠 <b>Bosh sahifa tartibi</b> (oxirgi 14 kun, noyob foydalanuvchi)", ""]
    for i, s in enumerate(order, 1):
        lines.append(f"{i}. {HOME_NAMES[s]} — {cnt[s][0]} kishi, {cnt[s][1]} marta" + ("  📌" if s == pin else ""))
    lines += ["", "Birinchiga qadash: /bolim_birinchi esse  (yoki mashq, alifbo, savollar, lugat, tayyorlov, diagnostik)", "Qo‘yib yuborish: /bolim_birinchi off"]
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def bolim_birinchi_cmd(update, context):
    if not _is_admin(update): return
    a = [x.lower() for x in (context.args or [])]
    if not a:
        await bolim_royxat_cmd(update, context); return
    if a[0] in ("off", "yoq", "yo‘q", "-"):
        set_home_pin(""); await update.message.reply_text("📌 Qadash olib tashlandi: tartib faqat ko‘rishlarga qarab.")
        return
    sec = HOME_ALIAS.get(a[0]) or (a[0] if a[0] in HOME_SECS else "")
    if not sec:
        await update.message.reply_text("Bunday bo‘lim yo‘q. Namuna: /bolim_birinchi esse"); return
    set_home_pin(sec)
    await update.message.reply_text(f"📌 «{HOME_NAMES[sec]}» bosh sahifada birinchi turadi. Qolganlar ko‘rishlar soniga qarab tartiblanadi.\nOlib tashlash: /bolim_birinchi off")


def register(app):
    app.add_handler(CommandHandler("sertifikat_sana", sertifikat_sana_cmd))
    app.add_handler(CommandHandler("natija_chiqdi", natija_chiqdi_cmd))
    app.add_handler(CommandHandler("bolim_royxat", bolim_royxat_cmd))
    app.add_handler(CommandHandler("bolim_birinchi", bolim_birinchi_cmd))
