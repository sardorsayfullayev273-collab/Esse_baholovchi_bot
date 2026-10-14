# -*- coding: utf-8 -*-
"""v55: to'lovni yakunlamaganlarga yumshoq eslatmalar (xarajatsiz, AI chaqirilmaydi).

1) Buyurtma ochilib, chek yuborilmagan bo'lsa:
   - 45 daqiqadan keyin: 1-eslatma (chekni yuboring)
   - muddat tugagach: 2-eslatma + qaytish chegirmasi (faqat esse/tool paketlari uchun)
   Har buyurtmaga eng ko'pi bilan 2 ta xabar, bir foydalanuvchiga 12 soatda 1 tadan ko'p emas.
2) «Birinchi xarid chegirmasi» tugashiga <=4 soat qolganda 1 marta eslatma.
3) Tunda (22:00–08:00 Toshkent) hech narsa yuborilmaydi.
Admin: /tolamaganlar — voronka (nechta odam qayerda to'xtagan).
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger("pay_nudge")

FIRST_REMIND_MIN = 45
USER_GAP_HOURS = 12
MAX_PER_CYCLE = 25
CYCLE_SECONDS = 300


def _iso(dt):
    return dt.replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def _parse(s):
    return datetime.fromisoformat(str(s).rstrip("Z"))


def _quiet(mp):
    h = datetime.now(mp.TZ).hour
    return h < 8 or h >= 22


def _recent_nudge(c, uid, gap_iso):
    return c.execute("SELECT 1 FROM manual_orders WHERE user_id=? AND remind_at>=? LIMIT 1", (uid, gap_iso)).fetchone() is not None


def _due_orders(mp):
    n = datetime.utcnow()
    since = _iso(n - timedelta(hours=96))
    gap = _iso(n - timedelta(hours=USER_GAP_HOURS))
    out = []
    with mp.db() as c:
        rows = c.execute(
            "SELECT id,user_id,kind,plan,amount,created_at,remind_n FROM manual_orders "
            "WHERE status='awaiting_proof' AND remind_n<2 AND created_at>=? ORDER BY id", (since,)).fetchall()
        for r in rows:
            uid = int(r["user_id"]); age = n - _parse(r["created_at"])
            rn = int(r["remind_n"] or 0)
            if rn == 0 and age < timedelta(minutes=FIRST_REMIND_MIN): continue
            if rn == 1 and age < timedelta(hours=mp.PROOF_TTL_HOURS): continue
            # keyinroq shu odam yangi buyurtma bergan yoki allaqachon to'lagan bo'lsa — bezovta qilmaymiz
            if c.execute("SELECT 1 FROM manual_orders WHERE user_id=? AND id>? AND status IN ('awaiting_proof','pending_review','approved') LIMIT 1", (uid, r["id"])).fetchone(): continue
            if c.execute("SELECT 1 FROM manual_orders WHERE user_id=? AND status='approved' AND kind=? LIMIT 1", (uid, r["kind"])).fetchone(): continue
            if _recent_nudge(c, uid, gap): continue
            out.append(r)
            if len(out) >= MAX_PER_CYCLE: break
    return out


def _mark(mp, oid, rn, dead=False):
    with mp.db() as c:
        c.execute("UPDATE manual_orders SET remind_n=?, remind_at=? WHERE id=?", (9 if dead else rn, mp.now(), int(oid)))
        c.commit()


async def _send_order_nudge(bot, mp, r):
    uid = int(r["user_id"]); oid = int(r["id"]); rn = int(r["remind_n"] or 0)
    title = mp.plan_title(r["kind"], r["plan"])
    amount = mp.fmt_uzs(r["amount"])
    disc_kind = r["kind"] in ("essay", "tool")
    if rn == 0:
        left = max(0, mp.PROOF_TTL_HOURS * 60 - int((datetime.utcnow() - _parse(r["created_at"])).total_seconds() // 60))
        text = (f"⏳ Buyurtmangiz kutmoqda: {title} — {amount} so‘m.\n\n"
                "To‘lovni o‘tkazgan bo‘lsangiz, chek skrinshotini shu chatga yuboring — admin tekshirib, xizmatni darhol ochadi.\n"
                f"Muddat: yana ~{max(1, left // 60)} soat.\n\n"
                "Qiyinchilik bo‘lsa, shu xabarga javob yozing — yordam beramiz.")
        kb = None
    else:
        pct = mp.RECOVERY_PCT if disc_kind else 0
        if pct > 0:
            until = datetime.utcnow() + timedelta(hours=mp.RECOVERY_HOURS)
            with mp.db() as c:
                c.execute("INSERT INTO pay_recovery(user_id,until) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET until=excluded.until", (uid, _iso(until)))
                c.commit()
            until_t = until.replace(tzinfo=timezone.utc).astimezone(mp.TZ).strftime("%d.%m %H:%M")
            text = (f"🔔 Buyurtmangiz muddati tugadi: {title}.\n\n"
                    f"Sizga maxsus: −{pct}% chegirma, {until_t} gacha (Toshkent vaqti). "
                    "Tugmani bosing — yangi summa bilan qayta ochiladi.")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 −{pct}% bilan davom etish", callback_data=f"cardpay_{r['kind']}_{r['plan']}")]])
        else:
            text = (f"🔔 Buyurtmangiz muddati tugadi: {title}.\n\nXohlasangiz, qaytadan boshlashingiz mumkin.")
            _k = {"gazal_lib": "gazallib"}.get(r["kind"], r["kind"])
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("💳 Qayta boshlash", callback_data=f"cardpay_{_k}_{r['plan']}")]]) if _k in ("essay", "tool", "growth", "group", "books", "gazallib", "expert", "teacher") else None
    try:
        await bot.send_message(uid, text, reply_markup=kb)
        _mark(mp, oid, rn + 1)
    except Exception as e:   # bloklagan / chat topilmadi — qayta urinmaymiz
        logger.info("nudge send failed uid=%s: %s", uid, e)
        _mark(mp, oid, rn + 1, dead=True)


async def _offer_expiring(bot, mp, kb_factory):
    n = datetime.utcnow()
    with mp.db() as c:
        rows = c.execute("SELECT user_id,until FROM first_offer WHERE until>? AND until<=? LIMIT 30",
                         (_iso(n), _iso(n + timedelta(hours=4)))).fetchall()
        todo = [int(r["user_id"]) for r in rows if not c.execute("SELECT 1 FROM offer_nudged WHERE user_id=?", (int(r["user_id"]),)).fetchone()]
    for uid in todo:
        with mp.db() as c:
            c.execute("INSERT OR IGNORE INTO offer_nudged(user_id,at) VALUES(?,?)", (uid, mp.now())); c.commit()
        fo = mp.first_offer(uid)       # sotib olgan bo'lsa None
        if not fo: continue
        text = (f"⏰ −{fo[0]}% chegirma {fo[1].strftime('%H:%M')} da tugaydi (Toshkent vaqti).\n\n"
                "Esse tekshiruvlari paketini hozir olsangiz, eng arzon narxda bo‘ladi. Tanlang 👇")
        try:
            await bot.send_message(uid, text, reply_markup=kb_factory("essay", uid))
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.info("offer nudge failed uid=%s: %s", uid, e)


async def nudge_loop(bot, mp, kb_factory):
    await asyncio.sleep(60)
    while True:
        try:
            if not _quiet(mp):
                for r in _due_orders(mp):
                    await _send_order_nudge(bot, mp, r)
                    await asyncio.sleep(0.05)
                await _offer_expiring(bot, mp, kb_factory)
        except Exception:
            logger.exception("nudge loop")
        await asyncio.sleep(CYCLE_SECONDS)


def funnel_report(mp, days=7):
    since = _iso(datetime.utcnow() - timedelta(days=days))
    with mp.db() as c:
        def cnt(q, *a): return c.execute(q, a).fetchone()[0]
        created = cnt("SELECT COUNT(DISTINCT user_id) FROM manual_orders WHERE created_at>=?", since)
        proof = cnt("SELECT COUNT(DISTINCT user_id) FROM manual_orders WHERE created_at>=? AND status IN ('pending_review','approved','rejected')", since)
        paid = cnt("SELECT COUNT(DISTINCT user_id) FROM manual_orders WHERE created_at>=? AND status='approved'", since)
        rejected = cnt("SELECT COUNT(DISTINCT user_id) FROM manual_orders WHERE created_at>=? AND status='rejected'", since)
        waiting = c.execute("SELECT id,user_id,kind,plan,amount,created_at,remind_n FROM manual_orders WHERE status='awaiting_proof' AND created_at>=? ORDER BY id DESC LIMIT 15", (since,)).fetchall()
        rec = cnt("SELECT COUNT(*) FROM pay_recovery WHERE until>?", _iso(datetime.utcnow()))
    lines = [f"📊 To‘lov voronkasi — oxirgi {days} kun",
             f"1) Buyurtma ochganlar: {created}",
             f"2) Chek yuborganlar: {proof}",
             f"3) To‘lov tasdiqlangan: {paid}" + (f"  (rad etilgan: {rejected})" if rejected else ""),
             f"❌ Chek yubormay ketganlar: {max(0, created - proof)}",
             f"🎟 Qaytish chegirmasi faol: {rec}", ""]
    if waiting:
        lines.append("Chek kutilayotganlar (oxirgi 15):")
        for r in waiting:
            age_h = int((datetime.utcnow() - _parse(r["created_at"])).total_seconds() // 3600)
            lines.append(f"• #{r['id']} id {r['user_id']} — {mp.plan_title(r['kind'], r['plan'])}, {mp.fmt_uzs(r['amount'])} so‘m, {age_h} soat oldin, eslatma: {min(int(r['remind_n'] or 0), 2)}")
    return "\n".join(lines)
