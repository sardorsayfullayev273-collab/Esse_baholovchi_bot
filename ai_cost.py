"""AI (OpenAI) xarajatini hisoblash: har bir chaqiruv uchun token va taxminiy narx bazaga yoziladi.

Narxlar (1 mln token uchun, USD) — model nomiga qarab; kerak bo'lsa muhitdan o'zgartiring:
  AI_PRICE_IN_PER_M, AI_PRICE_OUT_PER_M   (ikkalasi berilsa, hamma modelga shu narx qo'llanadi)
  AI_USD_UZS                              (so'mga o'tkazish kursi, taxminiy; standart 12500)
Eslatma: bu TAXMINIY hisob. Rasmiy summa — platform.openai.com -> Usage / Billing.
"""
import os, contextvars, logging
from datetime import datetime, timedelta, timezone
from national_certificate import db, now

UZ = timezone(timedelta(hours=5))
FEATURE = contextvars.ContextVar("ai_feature", default="esse_tekshiruv")
UID = contextvars.ContextVar("ai_uid", default=0)

FEATURE_NAMES = {
    "esse_tekshiruv": "Esse tekshiruvi (asosiy baholash)",
    "xato_auditi": "Xatolar auditi/qayta tekshiruv",
    "esse_mashq": "Esse mashqi (Mini App)",
    "esse_reja": "Esse rejasi",
    "dalil_topish": "Dalil/argument topish",
    "boshqa": "Boshqa",
}
# (kirish, chiqish) USD / 1 mln token — OpenAI e'lon qilgan narxlar, 2026-avgust holatida
KNOWN_PRICES = [("luna", 0.20, 1.20), ("terra", 2.00, 12.00), ("sol", 5.00, 30.00)]


def init_cost_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS ai_costs(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, day TEXT NOT NULL, user_id INTEGER, feature TEXT NOT NULL,
            model TEXT, in_tok INTEGER NOT NULL DEFAULT 0, out_tok INTEGER NOT NULL DEFAULT 0, usd REAL NOT NULL DEFAULT 0)''')
        c.execute("CREATE INDEX IF NOT EXISTS ix_ai_costs_day ON ai_costs(day)")
        c.commit()


def prices(model):
    pin, pout = os.getenv("AI_PRICE_IN_PER_M"), os.getenv("AI_PRICE_OUT_PER_M")
    if pin and pout:
        try: return float(pin), float(pout)
        except ValueError: pass
    m = (model or "").lower()
    for key, a, b in KNOWN_PRICES:
        if key in m: return a, b
    return KNOWN_PRICES[0][1], KNOWN_PRICES[0][2]


def usd_uzs():
    try: return float(os.getenv("AI_USD_UZS", "12500") or 12500)
    except ValueError: return 12500.0


def record_response(resp, model=None, feature=None):
    """OpenAI javobidagi usage ni yozadi. Xato bo'lsa asosiy oqimga halaqit bermaydi."""
    try:
        u = getattr(resp, "usage", None)
        if u is None: return
        it = int(getattr(u, "input_tokens", 0) or getattr(u, "prompt_tokens", 0) or 0)
        ot = int(getattr(u, "output_tokens", 0) or getattr(u, "completion_tokens", 0) or 0)
        model = model or getattr(resp, "model", "") or ""
        pin, pout = prices(model)
        usd = it / 1e6 * pin + ot / 1e6 * pout
        t = datetime.now(UZ)
        with db() as c:
            c.execute("INSERT INTO ai_costs(ts,day,user_id,feature,model,in_tok,out_tok,usd) VALUES(?,?,?,?,?,?,?,?)",
                      (now(), t.strftime("%Y-%m-%d"), int(UID.get() or 0), feature or FEATURE.get() or "boshqa", model, it, ot, usd))
            c.commit()
    except Exception:
        logging.getLogger(__name__).exception("ai_cost record failed")


def _since(period):
    t = datetime.now(UZ).date()
    days = {"bugun": 0, "hafta": 6, "oy": 29}.get(period, 0)
    return (t - timedelta(days=days)).strftime("%Y-%m-%d")


def summary(period="bugun"):
    since = _since(period)
    with db() as c:
        tot = c.execute("SELECT COUNT(*) n, COALESCE(SUM(in_tok),0) i, COALESCE(SUM(out_tok),0) o, COALESCE(SUM(usd),0) usd FROM ai_costs WHERE day>=?", (since,)).fetchone()
        feats = c.execute("SELECT feature, COUNT(*) n, SUM(usd) usd, SUM(in_tok) i, SUM(out_tok) o FROM ai_costs WHERE day>=? GROUP BY feature ORDER BY usd DESC", (since,)).fetchall()
        users = c.execute("SELECT user_id, COUNT(*) n, SUM(usd) usd FROM ai_costs WHERE day>=? AND user_id<>0 GROUP BY user_id ORDER BY usd DESC LIMIT 5", (since,)).fetchall()
        days = c.execute("SELECT day, SUM(usd) usd, COUNT(*) n FROM ai_costs WHERE day>=? GROUP BY day ORDER BY day DESC LIMIT 7", (since,)).fetchall()
        chk = c.execute("SELECT COUNT(*) FROM ai_costs WHERE feature='esse_tekshiruv'").fetchone()[0]
        chk_usd = c.execute("SELECT COALESCE(SUM(usd),0) FROM ai_costs WHERE feature IN ('esse_tekshiruv','xato_auditi')").fetchone()[0]
        try:
            free_test = c.execute("SELECT COUNT(*) FROM test_refs WHERE rewarded=1").fetchone()[0]
        except Exception:
            free_test = 0
    return {"since": since, "total": dict(tot), "features": [dict(r) for r in feats], "users": [dict(r) for r in users],
            "days": [dict(r) for r in days], "avg_check": (chk_usd / chk if chk else 0.0), "free_test_bonuses": free_test}


def fmt_money(usd):
    return f"${usd:,.2f}" if usd >= 0.01 else f"${usd:,.4f}"


def fmt_report(period, name_of=lambda uid: str(uid), model=""):
    s = summary(period); t = s["total"]; rate = usd_uzs(); pin, pout = prices(model)
    title = {"bugun": "bugun", "hafta": "oxirgi 7 kun", "oy": "oxirgi 30 kun"}.get(period, period)
    L = [f"💰 AI XARAJATI — {title}", "",
         f"📞 Chaqiruvlar: {t['n']}", f"🔤 Token: kirish {t['i']:,} • chiqish {t['o']:,}".replace(",", " "),
         f"💵 Taxminiy narx: {fmt_money(t['usd'])} (≈ {int(t['usd']*rate):,} so‘m)".replace(",", " ")]
    if s["features"]:
        L += ["", "Nimalarga ketdi:"]
        for f in s["features"]:
            share = (f["usd"] / t["usd"] * 100) if t["usd"] else 0
            L.append(f"• {FEATURE_NAMES.get(f['feature'], f['feature'])}: {fmt_money(f['usd'])} ({share:.0f}%) — {f['n']} ta, o‘rtacha {fmt_money(f['usd']/f['n'])}")
    if s["users"]:
        L += ["", "Eng ko‘p sarflaganlar:"]
        for i, u in enumerate(s["users"], 1):
            L.append(f"{i}. {name_of(u['user_id'])} — {fmt_money(u['usd'])} ({u['n']} ta)")
    if period != "bugun" and len(s["days"]) > 1:
        L += ["", "Kunlar bo‘yicha:"] + [f"• {d['day'][5:]}: {fmt_money(d['usd'])} ({d['n']} ta)" for d in s["days"]]
    if s["avg_check"]:
        L += ["", f"📝 Bitta esse tekshiruvi o‘rtacha ≈ {fmt_money(s['avg_check'])}"]
        if s["free_test_bonuses"]:
            L.append(f"🎁 Test havolasi bonusi bilan berilgan bepul tekshiruvlar: {s['free_test_bonuses']} ta (≈ {fmt_money(s['free_test_bonuses']*s['avg_check'])})")
    rate_s = f"{int(rate):,}".replace(",", " ")
    L += ["", f"ℹ️ Narx: ${pin:g} / ${pout:g} (1 mln kirish / chiqish token), kurs {rate_s} so‘m.",
          "Bu taxminiy hisob. Aniq summa: platform.openai.com → Usage.",
          "Boshqa davr: /xarajat hafta  yoki  /xarajat oy"]
    return "\n".join(L)
