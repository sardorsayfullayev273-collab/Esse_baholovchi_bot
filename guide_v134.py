# -*- coding: utf-8 -*-
"""v134: Yo'riqnoma (tanishuv) + mavjud foydalanuvchilarga XAVFSIZ yangilanish.

• tour_screen(n, existing) — botdagi 3 ekranli tanishuv (yangi: gd_t1..3, mavjud foydalanuvchi: gd_u1..3)
• api_get('/api/guide/prices') — Mini App uchun joriy narxlar (manual_pay / akademiya'dan; kodga qo'lda yozilmaydi)
• Yangilanish xabari (rollout): push_guard orqali (faol, bloklamagan, /eslatma off qilmagan, 09–21, kuniga/haftasiga limit),
  3 bosqich (5% → 30% → 100%), har bir odamga FAQAT BIR MARTA, ovozsiz. Bloklash ulushi chegaradan oshsa — o'zi to'xtaydi.
  Admin: /yangilik [holat|test|boshla|davom|toxtat]
"""
import os, time, logging, threading
from datetime import datetime, timezone

log = logging.getLogger("guide_v134")
try:
    from national_certificate import setting, set_setting
except Exception:                                   # test muhiti
    _mem = {}
    def setting(k, d=""): return _mem.get(k, d)
    def set_setting(k, v): _mem[k] = v

CAPS = [0.05, 0.30, 1.0]                            # bosqichlar: umumiy havzaning ulushi
WAVE = int(os.getenv("GD_WAVE", "150") or 150)      # bir sikldagi eng ko'p xabar
CYCLE = int(os.getenv("GD_CYCLE_SEC", "600") or 600)
BLOCK_STOP = float(os.getenv("GD_BLOCK_STOP", "1.5") or 1.5)   # % — oshsa, avtomatik to'xtaydi
MIN_SAMPLE = int(os.getenv("GD_MIN_SAMPLE", "40") or 40)
SLEEP = 0.08

_C = {"send": None, "mark_block": None, "is_banned": None, "admin": 0, "db": None, "pg": None, "mp": None, "ak": None}
_lock = threading.Lock()


def configure(send, mark_block, is_banned, admin_id, get_db, pg=None, mp=None, ak=None):
    _C.update(send=send, mark_block=mark_block, is_banned=is_banned, admin=int(admin_id or 0), db=get_db, pg=pg, mp=mp, ak=ak)
    try:
        if pg is not None: pg.KIND_TITLES["update"] = "Yangilik (v134)"
    except Exception: pass


def init():
    with _C["db"]() as c:
        c.execute("CREATE TABLE IF NOT EXISTS guide_push(user_id INTEGER PRIMARY KEY, sent_at TEXT, status TEXT)")
        c.commit()


# ------------------------------------------------------------------ narxlar
def _fmt(n):
    return f"{int(n):,}".replace(",", " ")


def prices():
    mp, ak = _C["mp"], _C["ak"]
    p = {}
    try:
        books = int(mp.BOOKS_UZS)
        p.update(books=_fmt(books), books_each=_fmt(round(books / 40)), expert1=_fmt(mp.EXPERT_ONE_UZS), expert3=_fmt(mp.EXPERT_PACK_UZS),
                 gazallib=_fmt(mp.GAZAL_LIB_UZS), gazal=_fmt(mp.GAZAL_GROUP_UZS))
    except Exception: log.exception("prices(mp)")
    try:
        if ak is not None:
            p.update(akad=_fmt(ak.PRICE), akad_days=str(ak.DAYS), akad_daily=str(ak.DAILY), akad_ai=str(ak.AI_DAILY))
    except Exception: log.exception("prices(ak)")
    return p


def api_get(path):
    if path.split("?")[0] == "/api/guide/prices":
        return {"ok": True, "p": prices()}, 200
    return None


# ------------------------------------------------------------------ bot ekranlari
def tour_screen(n, existing=False):
    """(html_matn, qatorlar). Qator elementi: (yozuv, 'cb'|'web', qiymat)."""
    pre = "u" if existing else "t"
    if n <= 1:
        head = ("🧭 <b>Bot yangilandi!</b> Mana nimalar bor:" if existing
                else "<b>Assalomu alaykum! Men Milliy sertifikatga tayyorlovchi botman.</b>\n\nMen bilan nima qilasiz:")
        txt = (head + "\n\n"
               "🧪 <b>Darajangizni aniqlang</b>\nDiagnostik test, 10–15 daqiqa\n\n"
               "✍️ <b>Esse tekshirtiring</b>\nAI orqali: 1 ta bepul, keyin qulay paketlar\n\n"
               "📚 <b>Lug‘atlardan foydalaning</b>\nImlo, mumtoz lug‘at, sinonim, paronim, omonim\n\n"
               "🎮 <b>O‘ynab o‘rganing</b>\nKunlik mashq va xatolar ustida ishlash")
        return txt, [[("Davom etish ›", "cb", f"gd_{pre}2")]]
    if n == 2:
        txt = ("<b>Qayerdan boshlaysiz?</b>\n\n"
               "1️⃣ <b>Diagnostik test</b>\nDarajangiz va zaif mavzularingiz aniqlanadi\n\n"
               "2️⃣ <b>Zaif mavzular mashqi</b>\nFaqat xato qilgan joylaringiz\n\n"
               "3️⃣ <b>Kunlik mashq</b>\nHar kuni 5 daqiqa, seriya yig‘iladi")
        return txt, [[("🎓 Diagnostik testni boshlash", "web", "")], [("‹ Orqaga", "cb", f"gd_{pre}1"), ("Keyingi ›", "cb", f"gd_{pre}3")]]
    txt = ("<b>Hammasi Mini ilovada</b>\n\n"
           "Bu bot ichidagi to‘liq ilova. Chap pastdagi «Milliy sertifikat» tugmasi ham shu yerga olib boradi. "
           "Birinchi kirishda qisqa yo‘riqnoma sizni kutadi.")
    if existing:
        txt += "\n\n📚 <b>Yangi:</b> «Kurslar» bo‘limida esse kursi, badiiy asarlar va mumtoz adabiyot imkoniyatlari batafsil yoritilgan."
    return txt, [[("🚀 Mini ilovani ochish", "web", "")], [("‹ Orqaga", "cb", f"gd_{pre}2")]]


UPDATE_TEXT = ("🧭 <b>Bot yangilandi!</b>\n\nEndi har bir bo‘lim nima berishini bir qarashda bilib olasiz: "
               "yangi yo‘riqnoma tayyor. Bir daqiqa vaqtingizni oladi.")


def update_markup():
    return {"inline_keyboard": [[{"text": "🧭 Ko‘rish", "callback_data": "gd_u1"}], [{"text": "🔕 Bunday xabar kerak emas", "callback_data": "rem_off"}]]}


# ------------------------------------------------------------------ rollout
def _all_ids():
    with _C["db"]() as c:
        rows = c.execute("""SELECT user_id FROM (SELECT user_id FROM users UNION SELECT user_id FROM mini_users)
                            WHERE user_id NOT IN (SELECT user_id FROM reminders WHERE optout=1)""").fetchall()
    return [int(r[0]) for r in rows]


def _done_ids():
    with _C["db"]() as c:
        return {int(r[0]) for r in c.execute("SELECT user_id FROM guide_push").fetchall()}


def _counts():
    with _C["db"]() as c:
        r = c.execute("SELECT COUNT(*), SUM(status='ok'), SUM(status='blocked') FROM guide_push").fetchone()
    return int(r[0] or 0), int(r[1] or 0), int(r[2] or 0)


def _eligible(ids):
    pg = _C["pg"]
    if pg is None: return list(ids)
    return [int(x) for x in pg.allow_many(list(ids), "update", need_active=True, window=False)]   # oyna (09–21) pastda tekshiriladi


def _in_window():
    pg = _C["pg"]
    try: return pg.in_window() if pg is not None else True
    except Exception: return True


def _notify_admin(text):
    try:
        if _C["admin"] and _C["send"]: _C["send"]("sendMessage", {"chat_id": _C["admin"], "text": text})
    except Exception: log.exception("notify_admin")


def run_wave():
    """Bitta sikl. Yuborilganlar soni."""
    if setting("gd_roll", "0") != "1" or not _in_window(): return 0
    with _lock:
        total = int(setting("gd_total", "0") or 0); stage = min(int(setting("gd_stage", "0") or 0), len(CAPS) - 1)
        attempted, _ok, _bl = _counts()
        left = int(total * CAPS[stage]) - attempted
        if left <= 0: return 0
        done = _done_ids()
        cand = [u for u in _all_ids() if u not in done and not (_C["is_banned"] and _C["is_banned"](u))]
        ok_ids = _eligible(cand)[:min(WAVE, left)]
        sent = 0
        for uid in ok_ids:
            if setting("gd_roll", "0") != "1": break
            payload = {"chat_id": uid, "text": UPDATE_TEXT, "parse_mode": "HTML", "disable_notification": True, "reply_markup": update_markup()}
            ok, code = _C["send"]("sendMessage", payload)
            st = "ok" if ok else ("blocked" if code in (400, 403) else "err")
            with _C["db"]() as c:
                c.execute("INSERT OR REPLACE INTO guide_push(user_id,sent_at,status) VALUES(?,?,?)", (uid, datetime.now(timezone.utc).isoformat(timespec="seconds"), st)); c.commit()
            if ok:
                sent += 1
                try: _C["pg"] and _C["pg"].record(uid, "update")
                except Exception: pass
            elif st == "blocked":
                try: _C["mark_block"](uid)
                except Exception: pass
            if (sent + 1) % 10 == 0 or st != "ok":
                if _check_stop(): break
            time.sleep(SLEEP)
        _check_stop()
        return sent


def _check_stop():
    """Bloklash ulushi chegaradan oshsa — yuborishni o'zi to'xtatadi va adminni ogohlantiradi."""
    att, ok_n, bl = _counts()
    if att >= MIN_SAMPLE and bl * 100.0 / att > BLOCK_STOP and setting("gd_roll", "0") == "1":
        set_setting("gd_roll", "0")
        _notify_admin(f"⚠️ Yangilik yuborish AVTOMATIK TO‘XTADI: bloklash {bl * 100.0 / att:.1f}% (chegara {BLOCK_STOP}%). Yuborilgan: {att}. Holat: /yangilik holat")
        return True
    return False


def _loop():
    while True:
        try: run_wave()
        except Exception: log.exception("guide wave")
        time.sleep(CYCLE)


def start_thread():
    threading.Thread(target=_loop, daemon=True, name="guide_rollout").start()


def status_text():
    att, ok_n, bl = _counts()
    total = int(setting("gd_total", "0") or 0); stage = int(setting("gd_stage", "0") or 0)
    rate = (bl * 100.0 / att) if att else 0.0
    return (f"🧭 Yangilik (v134)\nYuborish: {'YOQILGAN' if setting('gd_roll', '0') == '1' else 'o‘chiq'}\n"
            f"Bosqich: {stage + 1}/{len(CAPS)} (chegara {int(CAPS[min(stage, 2)] * 100)}%)\nFaol havza: {total}\n"
            f"Urinilgan: {att} • yetkazilgan: {ok_n} • bloklagan: {bl} ({rate:.1f}%)\nAvto-to‘xtash chegarasi: {BLOCK_STOP}%")


def admin(args):
    """/yangilik buyrug'i. Qaytaradi: javob matni."""
    a = (args[0].lower() if args else "holat")
    if a == "holat": return status_text()
    if a == "test":
        ok, code = _C["send"]("sendMessage", {"chat_id": _C["admin"], "text": UPDATE_TEXT, "parse_mode": "HTML", "reply_markup": update_markup()})
        return "Test xabari sizga yuborildi." if ok else f"Xato: {code}"
    if a == "boshla":
        total = len(_eligible(_all_ids()))
        set_setting("gd_total", str(total)); set_setting("gd_stage", "0"); set_setting("gd_roll", "1")
        return f"Boshlandi. Faol havza: {total}. 1-bosqich: {int(total * CAPS[0])} ta. Natijani /yangilik holat bilan kuzating, so‘ng /yangilik davom."
    if a == "davom":
        s = min(int(setting("gd_stage", "0") or 0) + 1, len(CAPS) - 1)
        set_setting("gd_stage", str(s)); set_setting("gd_roll", "1")
        return f"{s + 1}-bosqich yoqildi (jami {int(CAPS[s] * 100)}%)."
    if a == "toxtat":
        set_setting("gd_roll", "0"); return "To‘xtatildi."
    return "/yangilik [holat|test|boshla|davom|toxtat]"
