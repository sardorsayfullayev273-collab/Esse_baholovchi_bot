"""v29: voronka (start -> test -> birinchi esse -> 2+ esse -> to'lov). Faqat admin: /voronka.

Foydalanuvchi guruhi (kogorta) = shu davrda birinchi marta kelganlar (bot yoki Mini App).
Vaqt UTC bo'yicha, Toshkent kuni boshlanishiga moslab olinadi. Mavjud jadvallardan o'qiladi, yangi jadval yo'q.
"""
import logging
from datetime import datetime, timedelta, timezone
from national_certificate import db

log = logging.getLogger(__name__)
UZ = timezone(timedelta(hours=5))


def _q(c, sql, args=()):
    try:
        return c.execute(sql, args).fetchall()
    except Exception:
        log.exception("voronka so'rovi xatosi")
        return []


def _cut(days):
    """Toshkent kunining boshi (days kun oldin) -> UTC 'YYYY-MM-DDTHH:MM:SS' (formatga bog'liq bo'lmagan solishtirish uchun)."""
    d = datetime.now(UZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def collect():
    with db() as c:
        first = {}
        for r in _q(c, "SELECT user_id, joined_at t FROM users"):
            first[r["user_id"]] = min(first.get(r["user_id"], "9"), (r["t"] or "")[:19] or "9")
        for r in _q(c, "SELECT user_id, first_seen t FROM mini_users"):
            first[r["user_id"]] = min(first.get(r["user_id"], "9"), (r["t"] or "")[:19] or "9")
        tests = {r[0] for r in _q(c, "SELECT user_id FROM national_attempts UNION SELECT user_id FROM simple_attempts")}
        essays = {r["user_id"]: r["n"] for r in _q(c, "SELECT user_id, COUNT(*) n FROM checks WHERE COALESCE(mode,'') NOT LIKE 'growth%' GROUP BY user_id")}
        paid_card = {r["user_id"]: r["s"] for r in _q(c, "SELECT user_id, SUM(amount) s FROM manual_orders WHERE status='approved' GROUP BY user_id")}
        paid_stars = {r["user_id"]: r["s"] for r in _q(c, "SELECT user_id, SUM(stars) s FROM star_payments GROUP BY user_id")}
    return first, tests, essays, paid_card, paid_stars


def _pct(a, b):
    return f"{(100 * a / b):.0f}%" if b else "—"


def report():
    first, tests, essays, paid_card, paid_stars = collect()
    paid = set(paid_card) | set(paid_stars)
    out = ["📉 VORONKA (yangi kelganlar bo‘yicha)", ""]
    biggest = None
    for title, days in (("Bugun", 0), ("7 kun", 6), ("30 kun", 29), ("Hammasi", None)):
        cut = _cut(days) if days is not None else ""
        cohort = [u for u, t in first.items() if t != "9" and t >= cut]
        n = len(cohort)
        s_test = sum(1 for u in cohort if u in tests)
        s_e1 = sum(1 for u in cohort if essays.get(u, 0) >= 1)
        s_e2 = sum(1 for u in cohort if essays.get(u, 0) >= 2)
        s_pay = sum(1 for u in cohort if u in paid)
        som = sum(paid_card.get(u, 0) for u in cohort)
        stars = sum(paid_stars.get(u, 0) for u in cohort)
        out.append(f"■ {title}: {n} ta yangi")
        if n:
            out.append(f"  Test ishlagan: {s_test} ({_pct(s_test, n)})")
            out.append(f"  1-esse: {s_e1} ({_pct(s_e1, n)})")
            out.append(f"  2+ esse: {s_e2} ({_pct(s_e2, n)})")
            pay = f"  To‘lagan: {s_pay} ({_pct(s_pay, n)})"
            if som or stars:
                pay += f" • {int(som):,} so‘m".replace(",", " ") + (f" + {int(stars)}⭐" if stars else "")
            out.append(pay)
        out.append("")
        if days == 29 and n >= 10:
            steps = [("start", n), ("test", s_test), ("1-esse", s_e1), ("2+ esse", s_e2), ("to‘lov", s_pay)]
            drops = [(steps[i][1] - steps[i + 1][1], steps[i][0], steps[i + 1][0], steps[i][1]) for i in range(len(steps) - 1) if steps[i][1]]
            biggest = max(drops, key=lambda x: x[0] / x[3]) if drops else None
    if biggest and biggest[3]:
        out.append(f"⚠️ 30 kunda eng katta yo‘qotish: {biggest[1]} → {biggest[2]} ({100 * biggest[0] / biggest[3]:.0f}% to‘kilgan)")
    out.append("Eslatma: test/esse/to‘lov — o‘sha foydalanuvchi hozirgacha qilgan ishlari. Esse = botdagi tekshiruv (mashq emas).")
    return "\n".join(out)
