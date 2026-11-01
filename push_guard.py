# -*- coding: utf-8 -*-
"""push_guard (v114) — ommaviy / eslatma xabarlarini BITTA joydan cheklaydi, shunda foydalanuvchilar botni bloklamaydi.

Rejim (admin: /xabarlar low|normal|off; yoki Render'da PUSH_MODE):
  low     (standart) kuniga 1, haftada 3 tagacha; faqat oxirgi 14 kunda faol bo'lganlarga; 09:00–21:00 (Toshkent);
          «kunlik mavzu» foydalanuvchilarga shaxsiy emas, faqat kanalga.
  normal  kuniga 2, haftada 7 tagacha; oxirgi 30 kun faol; 08:00–22:00; kunlik mavzu foydalanuvchilarga ham boradi.
  off     barcha ommaviy/eslatma xabarlari o'chiq.

CHEKLANMAYDIGAN (tranzaksion) xabarlar: to'lov, test natijasi, sertifikat, imtihon oqimi, foydalanuvchi so'roviga javob,
admin qo'lda yuborgan xabarlar. Botni bloklagan (tg_blocked) yoki /eslatma off qilgan odamga hech qachon yuborilmaydi.
"""
import os, sqlite3, threading, time, logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger("push_guard")
UZ = timezone(timedelta(hours=5))
DB_PATH = os.getenv("BOT_DB_PATH", "esse_bot.sqlite3")

PROFILES = {
    "low":    {"day": 1, "week": 3, "active_days": 14, "from_h": 9, "to_h": 21},
    "normal": {"day": 2, "week": 7, "active_days": 30, "from_h": 8, "to_h": 22},
    "off":    {"day": 0, "week": 0, "active_days": 0,  "from_h": 0, "to_h": 0},
}
KIND_TITLES = {"topic": "Kunlik mavzu", "ai_renew": "AI limit yangilandi", "streak": "Seriya eslatmasi",
               "digest": "Haftalik hisobot", "winback": "Qaytarish (win-back)"}

_get = lambda k, d="": d
_set = lambda k, v: None
_lock = threading.Lock()
_last_prune = 0.0


def configure(get_setting, set_setting):
    """bot-1-1.py: setting / set_setting funksiyalarini ulaydi (rejim bazada saqlanadi)."""
    global _get, _set
    _get, _set = get_setting, set_setting


def _db():
    c = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _lock:
        c = _db()
        try:
            c.execute("CREATE TABLE IF NOT EXISTS push_log(user_id INTEGER NOT NULL, kind TEXT NOT NULL, at TEXT NOT NULL)")
            c.execute("CREATE INDEX IF NOT EXISTS ix_push_user_at ON push_log(user_id, at)")
            c.commit()
        finally:
            c.close()


def mode():
    m = str(_get("push_mode", "") or os.getenv("PUSH_MODE", "low") or "low").strip().lower()
    return m if m in PROFILES else "low"


def set_mode(m):
    m = str(m).strip().lower()
    if m in PROFILES:
        _set("push_mode", m)
    return mode()


def profile():
    return PROFILES[mode()]


def now_tk():
    return datetime.now(UZ)


def _utc_iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def in_window(now=None):
    p = profile()
    h = (now or now_tk()).hour
    return p["from_h"] <= h < p["to_h"]


def effective_topic_mode(configured):
    """Kunlik mavzu: low/off rejimda shaxsiy xabar (users/both) o'rniga faqat kanalga."""
    configured = (configured or "channel").strip().lower()
    if configured in ("users", "both") and mode() != "normal":
        return "channel"
    return configured


def _blocked_set(c):
    try:
        return {int(r[0]) for r in c.execute("SELECT user_id FROM tg_blocked WHERE unblocked_at IS NULL")}
    except Exception:
        return set()


def is_blocked(uid):
    c = _db()
    try:
        r = c.execute("SELECT 1 FROM tg_blocked WHERE user_id=? AND unblocked_at IS NULL", (int(uid),)).fetchone()
        return r is not None
    except Exception:
        return False
    finally:
        c.close()


def allow_many(ids, kind, need_active=True, window=True):
    """Berilgan foydalanuvchilardan hozir xabar YUBORISH MUMKINLARINI qaytaradi (tartib saqlanadi)."""
    ids = [int(i) for i in ids]
    p = profile()
    if not ids or p["day"] <= 0:
        return []
    if window and not in_window():
        return []
    now = datetime.now(timezone.utc)
    day_cut = _utc_iso(now - timedelta(hours=24))
    week_cut = _utc_iso(now - timedelta(days=7))
    act_cut = (now_tk() - timedelta(days=p["active_days"])).strftime("%Y-%m-%d")
    c = _db()
    try:
        blocked = _blocked_set(c)
        try:
            optout = {int(r[0]) for r in c.execute("SELECT user_id FROM reminders WHERE optout=1")}
        except Exception:
            optout = set()
        active = None
        if need_active:
            active = set()
            for tbl in ("users", "mini_users"):
                try:
                    active |= {int(r[0]) for r in c.execute(
                        "SELECT user_id FROM %s WHERE substr(last_seen,1,10)>=?" % tbl, (act_cut,))}
                except Exception:
                    pass
        day_n, week_n = {}, {}
        try:
            for r in c.execute("SELECT user_id, COUNT(*) FROM push_log WHERE at>=? GROUP BY user_id", (day_cut,)):
                day_n[int(r[0])] = int(r[1])
            for r in c.execute("SELECT user_id, COUNT(*) FROM push_log WHERE at>=? GROUP BY user_id", (week_cut,)):
                week_n[int(r[0])] = int(r[1])
        except Exception:
            pass
    finally:
        c.close()
    out = []
    for u in ids:
        if u in blocked or u in optout:
            continue
        if active is not None and u not in active:
            continue
        if day_n.get(u, 0) >= p["day"] or week_n.get(u, 0) >= p["week"]:
            continue
        out.append(u)
    return out


def allow(uid, kind, need_active=True, window=True):
    return bool(allow_many([uid], kind, need_active, window))


def record(uid, kind):
    """Xabar yuborilgach chaqiriladi (kunlik/haftalik hisob shundan olinadi)."""
    global _last_prune
    try:
        with _lock:
            c = _db()
            try:
                c.execute("INSERT INTO push_log(user_id,kind,at) VALUES(?,?,?)",
                          (int(uid), str(kind)[:20], _utc_iso(datetime.now(timezone.utc))))
                if time.time() - _last_prune > 86400:
                    _last_prune = time.time()
                    c.execute("DELETE FROM push_log WHERE at<?", (_utc_iso(datetime.now(timezone.utc) - timedelta(days=30)),))
                c.commit()
            finally:
                c.close()
    except Exception:
        log.exception("push_guard.record")


def stats():
    """Admin uchun: oxirgi 24 soat / 7 kun bo'yicha turi bo'yicha xabarlar soni va bloklaganlar."""
    now = datetime.now(timezone.utc)
    out = {"day": {}, "week": {}, "blocked": 0, "users_day": 0}
    c = _db()
    try:
        for key, cut in (("day", now - timedelta(hours=24)), ("week", now - timedelta(days=7))):
            try:
                for r in c.execute("SELECT kind, COUNT(*) FROM push_log WHERE at>=? GROUP BY kind", (_utc_iso(cut),)):
                    out[key][r[0]] = int(r[1])
            except Exception:
                pass
        try:
            out["users_day"] = int(c.execute("SELECT COUNT(DISTINCT user_id) FROM push_log WHERE at>=?",
                                             (_utc_iso(now - timedelta(hours=24)),)).fetchone()[0])
        except Exception:
            pass
        out["blocked"] = len(_blocked_set(c))
    finally:
        c.close()
    return out
