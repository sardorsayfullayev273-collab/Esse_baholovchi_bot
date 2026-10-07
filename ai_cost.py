"""v29: OpenAI sarfini kunma-kun hisoblash (token -> dollar -> so'm). Faqat admin ko'radi (/xarajat).

Narxlar Render Environment orqali o'zgartiriladi (1 mln token uchun, USD):
  AI_PRICE_IN=0.20  AI_PRICE_OUT=1.20  USD_UZS=12500  (AI_PRICE_CACHED ixtiyoriy, bo'sh bo'lsa kirish narxi olinadi)
Reasoning tokenlari chiqish tokenlari ichida allaqachon hisoblangan (OpenAI shunday hisoblaydi).
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from national_certificate import db

log = logging.getLogger(__name__)
UZ = timezone(timedelta(hours=5))


def _f(name, default):
    try:
        return float(os.getenv(name, "") or default)
    except Exception:
        return float(default)


def prices():
    pin = _f("AI_PRICE_IN", 0.20)
    return pin, _f("AI_PRICE_OUT", 1.20), _f("AI_PRICE_CACHED", pin), _f("USD_UZS", 12500)


def init_ai_cost_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS ai_cost_usage(
            day TEXT NOT NULL, model TEXT NOT NULL, calls INTEGER NOT NULL DEFAULT 0,
            in_tok INTEGER NOT NULL DEFAULT 0, cached_tok INTEGER NOT NULL DEFAULT 0,
            out_tok INTEGER NOT NULL DEFAULT 0, reasoning_tok INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(day, model))''')
        c.execute('''CREATE TABLE IF NOT EXISTS ai_cost_events(
            day TEXT NOT NULL, name TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(day, name))''')
        c.commit()


def event(name):
    """Kichik hisoblagich (masalan, adjudikator o'tkazib yuborilgan holatlar). Hech qachon xato ko'tarmaydi."""
    try:
        day = datetime.now(UZ).strftime("%Y-%m-%d")
        with db() as c:
            c.execute("INSERT OR IGNORE INTO ai_cost_events(day,name) VALUES(?,?)", (day, str(name)))
            c.execute("UPDATE ai_cost_events SET n=n+1 WHERE day=? AND name=?", (day, str(name)))
            c.commit()
    except Exception:
        log.exception("ai_cost.event xatosi")


def _events(day):
    with db() as c:
        return {r["name"]: r["n"] for r in c.execute("SELECT name,n FROM ai_cost_events WHERE day=?", (day,)).fetchall()}


def record(resp):
    """Har bir muvaffaqiyatli OpenAI javobini hisobga oladi. Hech qachon xato ko'tarmaydi. Javobni o'zini qaytaradi."""
    try:
        u = getattr(resp, "usage", None)
        if u is None:
            return resp
        i = int(getattr(u, "input_tokens", 0) or 0)
        o = int(getattr(u, "output_tokens", 0) or 0)
        cached = int(getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0)
        reas = int(getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0)
        day = datetime.now(UZ).strftime("%Y-%m-%d")
        model = str(getattr(resp, "model", "") or "?")
        with db() as c:
            c.execute("INSERT OR IGNORE INTO ai_cost_usage(day,model) VALUES(?,?)", (day, model))
            c.execute("UPDATE ai_cost_usage SET calls=calls+1, in_tok=in_tok+?, cached_tok=cached_tok+?, out_tok=out_tok+?, reasoning_tok=reasoning_tok+? WHERE day=? AND model=?",
                      (i, cached, o, reas, day, model))
            c.commit()
    except Exception:
        log.exception("ai_cost.record xatosi (e'tiborsiz qoldirildi)")
    return resp


def _usd(r):
    pin, pout, pc, _ = prices()
    fresh = max(int(r["in_tok"]) - int(r["cached_tok"]), 0)
    return (fresh * pin + int(r["cached_tok"]) * pc + int(r["out_tok"]) * pout) / 1e6


def _sum(rows):
    return {"calls": sum(r["calls"] for r in rows), "usd": sum(_usd(r) for r in rows),
            "in": sum(r["in_tok"] for r in rows), "out": sum(r["out_tok"] for r in rows),
            "reas": sum(r["reasoning_tok"] for r in rows)}


def _fmt(s, rate):
    return f"${s['usd']:.3f} ≈ {round(s['usd'] * rate):,} so‘m • {s['calls']} ta chaqiruv".replace(",", " ")


def report():
    _, _, _, rate = prices()
    now = datetime.now(UZ).date()
    def period(a, b):
        with db() as c:
            return _sum(c.execute("SELECT * FROM ai_cost_usage WHERE day>=? AND day<=?", (a.isoformat(), b.isoformat())).fetchall())
    t = period(now, now); y = period(now - timedelta(days=1), now - timedelta(days=1))
    w = period(now - timedelta(days=6), now); m = period(now.replace(day=1), now)
    days_passed = max(now.day, 1)
    forecast = m["usd"] / days_passed * 30
    avg = (t["usd"] / t["calls"]) if t["calls"] else 0
    lines = ["💸 OPENAI XARAJATI", "",
             "Bugun: " + _fmt(t, rate),
             "Kecha: " + _fmt(y, rate),
             "7 kun: " + _fmt(w, rate),
             "Shu oy: " + _fmt(m, rate), "",
             f"Oy oxirigacha prognoz: ≈ ${forecast:.1f} ({round(forecast * rate):,} so‘m)".replace(",", " "),
             f"Bugungi tokenlar: kirish {t['in']:,} • chiqish {t['out']:,} (shundan reasoning {t['reas']:,})".replace(",", " ")]
    if avg:
        lines.append(f"Bitta chaqiruv o‘rtacha: ${avg:.4f}")
    ev = _events(now.isoformat())
    sk, ru = ev.get("adj_skipped", 0), ev.get("adj_run", 0)
    if sk or ru:
        lines.append(f"Adjudikator bugun: o‘tkazib yuborildi {sk} ta, ishladi {ru} ta (tejam ≈ {sk * 1} ta chaqiruv)")
    pin, pout, _, _ = prices()
    lines += ["", f"Narx: ${pin}/${pout} (1 mln token, kirish/chiqish) • kurs {int(rate)} so‘m",
              "Eslatma: bu faqat shu v29 dan keyingi chaqiruvlar. Haqiqiy hisob — OpenAI paneli (Usage)."]
    return "\n".join(lines)
