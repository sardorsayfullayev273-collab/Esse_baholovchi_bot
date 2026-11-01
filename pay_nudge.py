"""pay_nudge — tugallanmagan to'lovlarga eslatma va to'lov voronkasi hisoboti (v96).

Zipda bu fayl yo'q edi (v72 dan beri), shuning uchun eslatma tsikli ishlamas edi. Qayta yozildi.
manual_pay.py ga TEGMAYDI: faqat manual_orders jadvalidagi mavjud remind_n / remind_at ustunlarini ishlatadi.

Qoidalar:
 - faqat status='awaiting_proof' (chek hali yuborilmagan) va muhlati tugamagan buyurtmalar;
 - 1-eslatma: yaratilgandan 2 soat keyin; 2-eslatma: muhlat tugashiga ~3 soat qolganda (jami 2 ta);
 - faqat Toshkent vaqti 09:00–21:00; bloklangan / /eslatma off qilganlarga yuborilmaydi;
 - Telegram xatosi (bot bloklangan) bo'lsa — qayta urinmaydi.
O'chirish: PAY_NUDGE=0.
"""
import os, asyncio, logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger("pay_nudge")
UZ = timezone(timedelta(hours=5))
ENABLED = os.getenv("PAY_NUDGE", "1") != "0"
FIRST_AFTER_H = float(os.getenv("PAY_NUDGE_FIRST_H", "2") or 2)
LAST_BEFORE_H = float(os.getenv("PAY_NUDGE_LAST_LEFT_H", "3") or 3)
FROM_HOUR = int(os.getenv("PAY_NUDGE_FROM_HOUR", "9") or 9)
TO_HOUR = int(os.getenv("PAY_NUDGE_TO_HOUR", "21") or 21)
CHECK_EVERY_S = 600


def _parse(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _utcnow():
    return datetime.now(timezone.utc)


def _due(order, ttl_h):
    """Buyurtmaga hozir eslatma kerakmi? 1 / 2 / 0 qaytaradi."""
    created = _parse(order["created_at"])
    if not created:
        return 0
    age_h = (_utcnow() - created).total_seconds() / 3600.0
    if age_h >= ttl_h:
        return 0
    n = int(order["remind_n"] or 0)
    if n == 0 and age_h >= FIRST_AFTER_H:
        return 1
    if n == 1 and (ttl_h - age_h) <= LAST_BEFORE_H:
        return 2
    return 0


def _text(order, stage, ttl_h, fmt_uzs):
    left_h = max(1, int(ttl_h - ((_utcnow() - _parse(order["created_at"])).total_seconds() / 3600.0)))
    amount = fmt_uzs(order["amount"])
    if stage == 1:
        return ("🕓 To‘lovingiz yakunlanmagan\n\n"
                f"Siz {amount} so‘mlik buyurtma boshlagansiz — uni tugatish uchun atigi bir qadam qoldi.\n"
                "To‘lovni qilib, chekni shu botga yuborsangiz, xizmat darhol ochiladi.\n\n"
                f"⏳ Buyurtma yana ~{left_h} soat amal qiladi.")
    return ("⏰ Buyurtma muddati tugayapti\n\n"
            f"{amount} so‘mlik buyurtmangiz ~{left_h} soatdan keyin bekor bo‘ladi.\n"
            "Hali ham kerak bo‘lsa — to‘lovni yakunlang yoki quyidan boshqa paketni tanlang.")


async def nudge_once(bot, mp, pack_keyboard, is_banned=None, optout=None):
    now_tk = datetime.now(UZ)
    if not (FROM_HOUR <= now_tk.hour < TO_HOUR):
        return 0
    ttl_h = float(getattr(mp, "PROOF_TTL_HOURS", 24))
    cutoff = (_utcnow() - timedelta(hours=ttl_h)).isoformat(timespec="seconds").replace("+00:00", "Z")
    with mp.db() as c:
        rows = c.execute(
            "SELECT id,user_id,kind,amount,created_at,remind_n FROM manual_orders "
            "WHERE status='awaiting_proof' AND created_at>=? AND COALESCE(remind_n,0)<2 ORDER BY id LIMIT 200",
            (cutoff,)).fetchall()
    sent = 0
    for o in rows:
        stage = _due(o, ttl_h)
        if not stage:
            continue
        uid = int(o["user_id"])
        try:
            if (is_banned and is_banned(uid)) or (optout and optout(uid)):
                continue
            import push_guard as _pg   # v114: botni bloklaganga yubormaymiz
            if _pg.is_blocked(uid):
                continue
        except ImportError:
            pass
        except Exception:
            pass
        # avval belgilaymiz (qayta yuborilib ketmasligi uchun), keyin yuboramiz
        with mp.db() as c:
            cur = c.execute("UPDATE manual_orders SET remind_n=?, remind_at=? WHERE id=? AND status='awaiting_proof' AND COALESCE(remind_n,0)=?",
                            (stage, mp.now(), int(o["id"]), stage - 1))
            c.commit()
            if cur.rowcount != 1:
                continue
        try:
            kb = None
            try:
                kb = pack_keyboard(o["kind"], uid)
            except Exception:
                kb = None
            await bot.send_message(chat_id=uid, text=_text(o, stage, ttl_h, mp.fmt_uzs), reply_markup=kb)
            sent += 1
        except Exception as e:
            log.info("nudge uid=%s: %s", uid, e)
        await asyncio.sleep(0.1)
    return sent


async def nudge_loop(bot, mp, pack_keyboard, is_banned=None, optout=None):
    if not ENABLED:
        log.info("pay_nudge o'chirilgan (PAY_NUDGE=0)")
        return
    await asyncio.sleep(90)
    while True:
        try:
            n = await nudge_once(bot, mp, pack_keyboard, is_banned, optout)
            if n:
                log.info("pay_nudge: %s ta eslatma yuborildi", n)
        except Exception:
            log.exception("pay_nudge tsikli")
        await asyncio.sleep(CHECK_EVERY_S)


def funnel_report(mp, days=7):
    """To'lov voronkasi (faqat o'qiydi): boshlangan -> chek yuborilgan -> tasdiqlangan, 7 kun."""
    since = (_utcnow() - timedelta(days=days)).isoformat(timespec="seconds").replace("+00:00", "Z")
    with mp.db() as c:
        rows = c.execute("SELECT status, COUNT(*) n, COALESCE(SUM(amount),0) s FROM manual_orders WHERE created_at>=? GROUP BY status", (since,)).fetchall()
        reminded = c.execute("SELECT COUNT(*) FROM manual_orders WHERE created_at>=? AND COALESCE(remind_n,0)>0", (since,)).fetchone()[0]
        reminded_paid = c.execute("SELECT COUNT(*) FROM manual_orders WHERE created_at>=? AND COALESCE(remind_n,0)>0 AND status='approved'", (since,)).fetchone()[0]
    d = {r["status"]: (int(r["n"]), int(r["s"])) for r in rows}
    total = sum(v[0] for v in d.values())
    appr_n, appr_s = d.get("approved", (0, 0))
    sent = appr_n + d.get("pending_review", (0, 0))[0] + d.get("rejected", (0, 0))[0]
    pct = lambda a, b: ("%d%%" % round(100.0 * a / b)) if b else "—"
    lines = [f"💳 TO‘LOV VORONKASI — oxirgi {days} kun", "",
             f"1) Buyurtma boshlandi: {total}",
             f"2) Chek yuborildi: {sent} ({pct(sent, total)})",
             f"3) Tasdiqlandi: {appr_n} ({pct(appr_n, total)}) — {mp.fmt_uzs(appr_s)} so‘m",
             f"   ⏳ tekshiruvda: {d.get('pending_review', (0, 0))[0]} • bekor/muddati o‘tgan: {d.get('cancelled', (0, 0))[0]}",
             "", f"🔔 Eslatma yuborilgan buyurtmalar: {reminded}, shundan to‘langan: {reminded_paid}"]
    return "\n".join(lines)
