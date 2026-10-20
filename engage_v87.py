# -*- coding: utf-8 -*-
"""v87: mock eslatmalari, admin kunlik hisoboti, chek kuzatuvi.
Bot faylidan alohida — faqat bot-1-1.py chaqiradigan funksiyalar."""
import asyncio
import html as _html
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("engage_v87")
TZ = timezone(timedelta(hours=5))   # Toshkent

REMIND_HOURS = sorted({int(x) for x in os.getenv("MOCK_REMIND_HOURS", "72,24,3").replace(" ", "").split(",") if x.isdigit()}) or [3, 24, 72]
DAILY_REPORT_HOUR = int(os.getenv("DAILY_REPORT_HOUR", "8") or 8)      # Toshkent vaqti bilan
PROOF_FOLLOWUP_MIN = int(os.getenv("PROOF_FOLLOWUP_MIN", "25") or 25)  # chek tekshiruvi cho'zilsa — eslatma (daqiqa)
LINE = "━━━━━━━━━━━━━━━"

_ready = False


def _init(mk):
    global _ready
    if _ready: return
    mk._init()
    with mk._lock, mk._db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS mock_remind_sent(mock_id INTEGER NOT NULL, user_id INTEGER NOT NULL, stage INTEGER NOT NULL, at TEXT, PRIMARY KEY(mock_id,user_id,stage))")
        c.commit()
    _ready = True


def _left(sec):
    sec = int(sec)
    d, h, m = sec // 86400, sec % 86400 // 3600, sec % 3600 // 60
    if d: return f"{d} kun" + (f" {h} soat" if h else "")
    if h: return f"{h} soat" + (f" {m} daqiqa" if m else "")
    return f"{max(m, 1)} daqiqa"


# ------------------------------------------------------------------ 2) Mock eslatmalari
async def mock_reminder_pass(mk, mp, need_essay, topic_of, tg_api, bot_username):
    """Bir o'tish: mock boshlanishigacha REMIND_HOURS soat qolganda, esse balli yo'q ro'yxatdagilarga eslatma."""
    _init(mk)
    now = datetime.now(timezone.utc)
    with mk._lock, mk._db() as c:
        rows = c.execute("SELECT * FROM mocks WHERE test_code<>''").fetchall()
    for r in rows:
        try:
            opens = mk._parse(r["opens_at"])
        except Exception:
            continue
        rem = (opens - now).total_seconds()
        if rem <= 0: continue
        eligible = [h for h in REMIND_HOURS if rem <= h * 3600]
        if not eligible: continue
        target = min(eligible)
        code = str(r["test_code"]).upper()
        with mk._lock, mk._db() as c:
            uids = [x[0] for x in c.execute("SELECT user_id FROM mock_regs WHERE mock_id=?", (r["id"],)).fetchall()]
        topic = (topic_of(code) or "").strip()
        for uid in uids:
            try:
                with mk._lock, mk._db() as c:
                    if c.execute("SELECT 1 FROM mock_remind_sent WHERE mock_id=? AND user_id=? AND stage=?", (r["id"], uid, target)).fetchone():
                        continue
                    # kech ro'yxatdan o'tganlarga katta bosqichlar qayta yuborilmasin
                    for h in eligible:
                        c.execute("INSERT OR IGNORE INTO mock_remind_sent(mock_id,user_id,stage,at) VALUES(?,?,?,?)", (r["id"], uid, h, now.isoformat(timespec="seconds")))
                    c.commit()
                if not need_essay(uid, code):
                    continue   # esse balli bor (yoki ekspert tekshirmoqda) — bezovta qilmaymiz
                bu = bot_username()
                kb = {"inline_keyboard": [
                    [{"text": "🤖 AI bilan bepul tekshirish", "url": f"https://t.me/{bu}?start=mockai_{code}"}],
                    [{"text": f"👨‍🏫 Ekspert — {mp.fmt_uzs(mp.MOCK_EXPERT_UZS)} so‘m", "url": f"https://t.me/{bu}?start=mockexpert_{code}"}],
                ]} if bu else None
                text = (f"⏰ <b>Testgacha {_left(rem)} qoldi!</b>\n{LINE}\n\n"
                        f"📝 Mock: <b>{_html.escape(str(r['title']))}</b>\n"
                        + (f"📌 Esse mavzusi: «{_html.escape(topic)}»\n" if topic else "")
                        + f"\n⚠️ Esse balli bo‘lmasa test natijasi hisoblanmaydi. Esseni testgacha yozib tekshirtiring:\n\n"
                          f"🤖 <b>Sun‘iy intellekt</b> — bepul, 1 martalik\n"
                          f"👨‍🏫 <b>Ekspert</b> — {mp.fmt_uzs(mp.MOCK_EXPERT_UZS)} so‘m, ball {mp.EXPERT_HOURS} soat ichida\n\n"
                          f"{LINE}\n💡 Ekspert tekshiruviga vaqt kerak — kechiktirmang.")
                payload = {"chat_id": int(uid), "text": text, "parse_mode": "HTML"}
                if kb: payload["reply_markup"] = kb
                await asyncio.to_thread(tg_api, "sendMessage", payload)
                await asyncio.sleep(0.07)
            except Exception:
                logger.warning("mock eslatma yuborilmadi uid=%s", uid, exc_info=False)


async def mock_reminder_loop(mk, mp, need_essay, topic_of, tg_api, bot_username):
    await asyncio.sleep(40)
    while True:
        try:
            await mock_reminder_pass(mk, mp, need_essay, topic_of, tg_api, bot_username)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("mock_reminder_loop")
        await asyncio.sleep(600)


# ------------------------------------------------------------------ 6) Admin kunlik hisoboti
def _utc_range(day_tk):
    """Toshkent kuni (date) -> UTC chegaralari ('YYYY-MM-DDTHH:MM:SS')."""
    start = datetime(day_tk.year, day_tk.month, day_tk.day, tzinfo=TZ).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    f = "%Y-%m-%dT%H:%M:%S"
    return start.strftime(f), end.strftime(f)


def build_report(db, lock, mk, mp, day_tk, title="KUNLIK HISOBOT"):
    a, b = _utc_range(day_tk)
    out = {}
    with lock, db() as c:
        def one(q, args=()):
            try:
                r = c.execute(q, args).fetchone()
                return (r[0] or 0) if r else 0
            except Exception:
                return 0
        out["new_users"] = one("SELECT COUNT(*) FROM users WHERE substr(joined_at,1,19)>=? AND substr(joined_at,1,19)<?", (a, b))
        out["users"] = one("SELECT COUNT(*) FROM users")
        out["orders"] = one("SELECT COUNT(*) FROM manual_orders WHERE status='approved' AND amount>0 AND substr(updated_at,1,19)>=? AND substr(updated_at,1,19)<?", (a, b))
        out["revenue"] = one("SELECT COALESCE(SUM(amount),0) FROM manual_orders WHERE status='approved' AND amount>0 AND substr(updated_at,1,19)>=? AND substr(updated_at,1,19)<?", (a, b))
        out["pending"] = one("SELECT COUNT(*) FROM manual_orders WHERE status='pending_review'")
        out["checks"] = one("SELECT COUNT(*) FROM checks WHERE mode NOT IN ('expert') AND substr(created_at,1,19)>=? AND substr(created_at,1,19)<?", (a, b))
        out["expert"] = one("SELECT COUNT(*) FROM checks WHERE mode='expert' AND substr(created_at,1,19)>=? AND substr(created_at,1,19)<?", (a, b))
        out["mock_new"] = one("SELECT COUNT(*) FROM mock_regs WHERE substr(joined_at,1,19)>=? AND substr(joined_at,1,19)<?", (a, b))
        try:
            kinds = c.execute("SELECT kind, COUNT(*), COALESCE(SUM(amount),0) FROM manual_orders WHERE status='approved' AND amount>0 AND substr(updated_at,1,19)>=? AND substr(updated_at,1,19)<? GROUP BY kind ORDER BY 3 DESC", (a, b)).fetchall()
        except Exception:
            kinds = []
        try:
            mocks = c.execute("SELECT m.title, (SELECT COUNT(*) FROM mock_regs g WHERE g.mock_id=m.id) FROM mocks m ORDER BY m.opens_at DESC LIMIT 3").fetchall()
        except Exception:
            mocks = []
    names = {"essay": "Esse paketi", "tool": "AI mashq", "growth": "Esse kursi", "expert": "Ekspert", "mock": "Mock", "group": "Guruh",
             "books": "Badiiy asarlar", "gazal_lib": "G‘azal bo‘limi", "gazal_item": "G‘azal qo‘llanma", "teacher": "Ustoz Pro"}
    t = [f"📊 <b>{title}</b>", f"🗓 {day_tk.strftime('%d.%m.%Y')}", LINE, ""]
    t.append(f"👥 Yangi foydalanuvchi: <b>{out['new_users']}</b>  (jami {mp.fmt_uzs(out['users'])})")
    t.append(f"💰 To‘lovlar: <b>{out['orders']}</b> ta — <b>{mp.fmt_uzs(out['revenue'])} so‘m</b>")
    for k, n, sm in kinds:
        t.append(f"    • {names.get(k, k)}: {n} ta — {mp.fmt_uzs(sm)}")
    t.append(f"⏳ Tekshiruvda turgan to‘lov: <b>{out['pending']}</b>")
    t.append(f"📝 Esse tekshiruvi: <b>{out['checks']}</b> (AI)  •  👨‍🏫 ekspert: <b>{out['expert']}</b>")
    t.append(f"🎯 Mockka yangi ro‘yxat: <b>{out['mock_new']}</b>")
    for ttl, n in mocks:
        t.append(f"    • {_html.escape(str(ttl))}: jami {n} ta")
    try:
        import growth_v92 as _g92
        t += [_html.escape(x) for x in _g92.report_lines(day_tk)]
    except Exception:
        logger.exception("v92 report block")
    t += ["", LINE]
    return "\n".join(t)


async def daily_report_loop(db, lock, mk, mp, tg_api, admin_id):
    """Har kuni DAILY_REPORT_HOUR:00 (Toshkent) da kechagi kun hisobotini adminga yuboradi (kuniga bir marta)."""
    await asyncio.sleep(60)
    while True:
        try:
            now = datetime.now(TZ)
            today = now.strftime("%Y-%m-%d")
            if now.hour >= DAILY_REPORT_HOUR and mp.setting("daily_report_last", "") != today:
                mp.set_setting("daily_report_last", today)
                text = build_report(db, lock, mk, mp, (now - timedelta(days=1)).date(), "KECHAGI KUN HISOBOTI")
                await asyncio.to_thread(tg_api, "sendMessage", {"chat_id": int(admin_id), "text": text, "parse_mode": "HTML"})
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("daily_report_loop")
        await asyncio.sleep(300)


# ------------------------------------------------------------------ 5) Chek tekshiruvi kuzatuvi
def schedule_proof_followup(loop, tg_api, mp, oid, uid, admin_id):
    """Chek yuborilgach PROOF_FOLLOWUP_MIN daqiqada hali ko'rilmagan bo'lsa: foydalanuvchiga holat xabari + adminga eslatma."""
    async def _job():
        await asyncio.sleep(PROOF_FOLLOWUP_MIN * 60)
        try:
            o = mp.get_order(oid)
            if not o or o["status"] != "pending_review": return
            await asyncio.to_thread(tg_api, "sendMessage", {"chat_id": int(uid), "parse_mode": "HTML", "text":
                f"⏳ <b>To‘lovingiz hali tekshiruvda</b> (#{oid})\n{LINE}\n"
                "Admin chekni ko‘rib chiqmoqda — ko‘p hollarda bir necha daqiqa kifoya.\n"
                "✅ Hech qayerga yozishingiz shart emas: tasdiqlanishi bilan xizmat <b>o‘zi ochiladi</b> va sizga xabar keladi."})
            await asyncio.to_thread(tg_api, "sendMessage", {"chat_id": int(admin_id), "text":
                f"⏰ Eslatma: #{oid} to‘lovi {PROOF_FOLLOWUP_MIN}+ daqiqadan beri tekshirilmay turibdi (id {uid}). Chek xabaridagi tugmalar orqali ko‘rib chiqing."})
        except Exception:
            logger.exception("proof_followup")
    try:
        loop.create_task(_job())
    except Exception:
        logger.exception("proof_followup schedule")
