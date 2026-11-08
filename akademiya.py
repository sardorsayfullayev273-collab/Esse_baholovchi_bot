# -*- coding: utf-8 -*-
"""v123: «Sardor Sayfullayev: Mumtoz tahlil maktabi» — pullik bo'lim (G'azal tabdili + She'riy san'atlar).
Obuna: 30 000 so'm / 30 kun (mavjud karta to'lovi orqali, kind='akad', plan='pro').
Bo'lim admin buyrug'i bilan ochiladi (/mumtoz_och). Savollar serverda qoladi, bittalab beriladi."""
import json, os, re, time, random, hashlib, logging
from datetime import datetime, timedelta
from national_certificate import db, setting, set_setting

log = logging.getLogger("akademiya")
HERE = os.path.dirname(os.path.abspath(__file__))
PRICE = int(os.getenv("AKAD_UZS", "30000") or 30000)
DAYS = int(os.getenv("AKAD_DAYS", "30") or 30)
DAILY = int(os.getenv("AKAD_DAILY", "80") or 80)          # obunachi uchun kuniga beriladigan savol soni
AI_DAILY = int(os.getenv("AKAD_AI_DAILY", "30") or 30)    # kuniga AI tekshiruvlari
TITLE = "Sardor Sayfullayev: Mumtoz tahlil maktabi"
_ADMIN = 0
_AI = None          # sync funksiya: (system, user) -> dict
_BOT_NOTIFY = None


def configure(admin_id, ai_json=None):
    global _ADMIN, _AI
    _ADMIN = int(admin_id or 0); _AI = ai_json
    try:
        import manual_pay as _mp; install_payments(_mp)
    except Exception: log.exception("akad payments")



# ------------------------------------------------------------ mavjud to'lov tizimiga ulanish (manual_pay.py O'ZGARTIRILMAYDI — v92 xavfsizlik testi)
def install_payments(mp):
    """kind='akad', plan='pro' ni manual_pay ga qo'shadi (narx, nom, tekshiruv). Karta/chek/admin tasdig'i — mavjud tizim."""
    if getattr(mp, "_akad_patched", False): return
    mp.AKAD_UZS = PRICE; mp.AKAD_DAYS = DAYS
    o_valid, o_title, o_amt, o_stars, o_price, o_pstars = mp.valid_plan, mp.plan_title, mp.plan_amount_uzs, mp.plan_amount_stars, mp.price_uzs, mp.price_stars
    mp.valid_plan = lambda kind, plan: (plan == "pro") if kind == "akad" else o_valid(kind, plan)
    mp.plan_title = lambda kind, plan: f"{TITLE} — {DAYS} kun" if kind == "akad" else o_title(kind, plan)
    mp.plan_amount_uzs = lambda kind, plan: PRICE if kind == "akad" else o_amt(kind, plan)
    mp.plan_amount_stars = lambda kind, plan: 0 if kind == "akad" else o_stars(kind, plan)
    mp.price_uzs = lambda uid, kind, plan: PRICE if kind == "akad" else o_price(uid, kind, plan)   # qat'iy narx, chegirmasiz
    mp.price_stars = lambda uid, kind, plan: 0 if kind == "akad" else o_pstars(uid, kind, plan)
    mp._akad_patched = True


def _load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)

try:
    SAN = _load("akad_sanat.json"); TAB = _load("akad_tabdil.json")
except Exception:
    log.exception("akad data"); SAN = {"savollar": [], "qoidalar": {}, "chalgitish": {}, "free_qid": "", "free_art": ""}; TAB = {"savollar": [], "qoidalar": [], "free_id": ""}
SQ = {q["id"]: q for q in SAN["savollar"]}
TQ = {q["id"]: q for q in TAB["savollar"]}
RULES = {str(r["id"]): r for r in TAB["qoidalar"]}


def _now(): return datetime.utcnow().replace(microsecond=0)
def _iso(d): return d.isoformat(timespec="seconds")
def _today(): return (datetime.utcnow() + timedelta(hours=5)).strftime("%Y-%m-%d")
def _key(s): return re.sub(r"[^a-z0-9]", "", str(s).lower().replace("‘", "").replace("’", "").replace("'", "").replace("`", ""))


def init():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS akad_sub(user_id INTEGER PRIMARY KEY, until TEXT NOT NULL, warned INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS akad_orders(okey TEXT PRIMARY KEY, user_id INTEGER, at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS akad_ans(qid TEXT PRIMARY KEY, javob TEXT, confirmed INTEGER DEFAULT 0, at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS akad_prog(user_id INTEGER, qid TEXT, ok INTEGER, at TEXT, PRIMARY KEY(user_id,qid))")
        c.execute("CREATE TABLE IF NOT EXISTS akad_day(user_id INTEGER, day TEXT, kind TEXT, n INTEGER DEFAULT 0, PRIMARY KEY(user_id,day,kind))")
        c.execute("CREATE TABLE IF NOT EXISTS akad_flag(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, qid TEXT, text TEXT, at TEXT)")
        c.commit()


# ------------------------------------------------------------ ochiq/yopiq va obuna
def is_open(): return setting("akad_open", "0") == "1"
def set_open(on): set_setting("akad_open", "1" if on else "0")


def sub_until(uid):
    with db() as c:
        r = c.execute("SELECT until FROM akad_sub WHERE user_id=?", (int(uid),)).fetchone()
    if not r: return None
    try: d = datetime.fromisoformat(r[0])
    except Exception: return None
    return d if d > _now() else None


def grant(uid, days, okey):
    """Obunani uzaytiradi; bir buyurtma ikki marta hisoblanmaydi. Tugash sanasini qaytaradi."""
    uid = int(uid)
    with db() as c:
        if c.execute("SELECT 1 FROM akad_orders WHERE okey=?", (okey,)).fetchone(): return sub_until(uid)
        cur = sub_until(uid); base = max(_now(), cur) if cur else _now()
        until = base + timedelta(days=int(days))
        c.execute("INSERT INTO akad_sub(user_id,until,warned) VALUES(?,?,0) ON CONFLICT(user_id) DO UPDATE SET until=excluded.until, warned=0", (uid, _iso(until)))
        c.execute("INSERT INTO akad_orders(okey,user_id,at) VALUES(?,?,?)", (okey, uid, _iso(_now())))
        c.commit()
    return until


def has_access(uid, admin=False):
    return bool(admin or (uid and sub_until(uid)))


def _used(uid, kind):
    with db() as c:
        r = c.execute("SELECT n FROM akad_day WHERE user_id=? AND day=? AND kind=?", (int(uid), _today(), kind)).fetchone()
    return int(r[0]) if r else 0


def _bump(uid, kind):
    with db() as c:
        c.execute("INSERT INTO akad_day(user_id,day,kind,n) VALUES(?,?,?,1) ON CONFLICT(user_id,day,kind) DO UPDATE SET n=n+1", (int(uid), _today(), kind)); c.commit()


# ------------------------------------------------------------ javoblar (admin tuzatishi bilan)
def _overrides():
    with db() as c:
        return {r[0]: (r[1], int(r[2])) for r in c.execute("SELECT qid,javob,confirmed FROM akad_ans").fetchall()}


def answer_of(qid):
    q = SQ.get(qid)
    if not q: return None
    ov = _overrides().get(qid)
    return ov[0] if ov and ov[0] else q["javob"]


def set_answer(qid, art):
    q = SQ.get(qid)
    art = match_art(art)
    if not q or not art: return False
    with db() as c:
        c.execute("INSERT INTO akad_ans(qid,javob,confirmed,at) VALUES(?,?,1,?) ON CONFLICT(qid) DO UPDATE SET javob=excluded.javob, confirmed=1, at=excluded.at", (qid, art, _iso(_now()))); c.commit()
    return True


def confirm(qid):
    if qid not in SQ: return False
    cur = answer_of(qid)
    with db() as c:
        c.execute("INSERT INTO akad_ans(qid,javob,confirmed,at) VALUES(?,?,1,?) ON CONFLICT(qid) DO UPDATE SET confirmed=1", (qid, cur, _iso(_now()))); c.commit()
    return True


def match_art(name):
    k = _key(name)
    for a in SAN["qoidalar"]:
        if _key(a) == k: return a
    return None


def qid_norm(s):
    s = str(s or "").strip().lower().replace(" ", "")
    m = re.match(r"^d?(\d)[-_.](\d{1,2})$", s)
    return f"d{m.group(1)}-{int(m.group(2))}" if m else s


# ------------------------------------------------------------ savol berish
def _options(uid, qid):
    right = answer_of(qid)
    pool = list(SAN["chalgitish"].get(right, []))
    allarts = [a for a in SAN["qoidalar"] if a != right and a not in pool]
    rnd = random.Random(hashlib.sha1(f"{uid}:{qid}".encode()).hexdigest())
    while len(pool) < 3 and allarts:
        pool.append(allarts.pop(rnd.randrange(len(allarts))))
    opts = pool[:3] + [right]
    rnd.shuffle(opts)
    return opts


def _wm(uid): return f"ID {uid}"


def _need_pay(msg="Bu bo‘lim obuna orqali ochiladi."):
    return 403, {"ok": False, "need_pay": True, "price": PRICE, "days": DAYS, "error": msg}


def state(uid, admin):
    op = is_open()
    if not op and not admin: return {"ok": True, "visible": False}
    until = sub_until(uid) if uid else None
    acc = has_access(uid, admin)
    with db() as c:
        done = c.execute("SELECT COUNT(*), COALESCE(SUM(ok),0) FROM akad_prog WHERE user_id=?", (int(uid),)).fetchone() if uid else (0, 0)
    lessons = {}
    for q in SAN["savollar"]:
        lessons.setdefault(q["dars"], {"dars": q["dars"], "nom": q["dars_nom"], "n": 0})["n"] += 1
    return {"ok": True, "visible": True, "open": op, "title": TITLE, "access": acc, "admin": bool(admin), "price": PRICE, "days": DAYS,
            "until": until.strftime("%d.%m.%Y") if until else "", "days_left": max(0, (until - _now()).days) if until else 0,
            "wm": _wm(uid), "done": int(done[0] or 0), "right": int(done[1] or 0), "total": len(SQ), "tab_total": len(TQ),
            "lessons": sorted(lessons.values(), key=lambda x: x["dars"]), "free_qid": SAN.get("free_qid"), "free_tab": TAB.get("free_id"),
            "left_today": max(0, DAILY - _used(uid, "serve")) if uid else 0}


def theory_list(uid, admin):
    acc = has_access(uid, admin); out = []
    for a, t in SAN["qoidalar"].items():
        free = (a == SAN.get("free_art"))
        out.append({"art": a, "locked": not (acc or free), "text": t if (acc or free) else ""})
    return {"ok": True, "items": out, "access": acc}


def san_next(uid, admin, dars=0):
    acc = has_access(uid, admin)
    if acc and not admin and _used(uid, "serve") >= DAILY:
        return 429, {"ok": False, "error": f"Bugungi limit ({DAILY} ta savol) tugadi. Ertaga davom eting."}
    with db() as c:
        seen = {r[0]: r[1] for r in c.execute("SELECT qid,ok FROM akad_prog WHERE user_id=?", (int(uid),)).fetchall()}
    ids = [q["id"] for q in SAN["savollar"] if (not dars or q["dars"] == int(dars))]
    if not acc:
        qid = SAN.get("free_qid")
        if not qid or qid not in SQ: return _need_pay()
        if qid in seen:
            return _need_pay("Bepul namuna ishlandi. Davom etish uchun obuna bo‘ling.")
    else:
        todo = [i for i in ids if i not in seen] or [i for i in ids if seen.get(i) == 0] or ids
        if not todo: return 404, {"ok": False, "error": "Savol topilmadi."}
        qid = todo[0]
        if not admin: _bump(uid, "serve")
    q = SQ[qid]
    return 200, {"ok": True, "qid": qid, "dars": q["dars"], "dars_nom": q["dars_nom"], "raqam": q["raqam"], "bayt": q["bayt"],
                 "ajratilgan": q["ajratilgan"], "options": _options(uid, qid), "free": (not acc), "wm": _wm(uid)}


def san_answer(uid, admin, qid, choice):
    qid = qid_norm(qid); q = SQ.get(qid)
    if not q: return 404, {"ok": False, "error": "Savol topilmadi."}
    if not has_access(uid, admin) and qid != SAN.get("free_qid"): return _need_pay()
    right = answer_of(qid); ok = (_key(choice) == _key(right))
    with db() as c:
        c.execute("INSERT INTO akad_prog(user_id,qid,ok,at) VALUES(?,?,?,?) ON CONFLICT(user_id,qid) DO UPDATE SET ok=excluded.ok, at=excluded.at", (int(uid), qid, 1 if ok else 0, _iso(_now()))); c.commit()
    return 200, {"ok": True, "correct": ok, "right": right, "qoida": SAN["qoidalar"].get(right, ""), "tanlangan_qoida": SAN["qoidalar"].get(match_art(choice) or "", "") if not ok else ""}


# ------------------------------------------------------------ tabdil
def tab_rules(uid, admin):
    acc = has_access(uid, admin); free_rule = str(TQ.get(TAB.get("free_id"), {}).get("ish", ""))
    return {"ok": True, "access": acc, "items": [{"id": r["id"], "nom": r["nom"], "locked": not (acc or str(r["id"]) == free_rule), "matn": r["matn"] if (acc or str(r["id"]) == free_rule) else ""} for r in TAB["qoidalar"]]}


def tab_next(uid, admin):
    acc = has_access(uid, admin)
    if acc and not admin and _used(uid, "serve") >= DAILY: return 429, {"ok": False, "error": f"Bugungi limit ({DAILY} ta savol) tugadi."}
    with db() as c:
        seen = {r[0] for r in c.execute("SELECT qid FROM akad_prog WHERE user_id=? AND qid LIKE 't%'", (int(uid),)).fetchall()}
    if not acc:
        tid = TAB.get("free_id")
        if not tid or tid not in TQ or tid in seen: return _need_pay("Bepul namuna ishlandi. Davom etish uchun obuna bo‘ling.")
    else:
        todo = [i for i in TQ if i not in seen] or list(TQ)
        tid = todo[0]
        if not admin: _bump(uid, "serve")
    q = TQ[tid]; right = str(q["ish"])
    rnd = random.Random(hashlib.sha1(f"{uid}:{tid}".encode()).hexdigest())
    others = [k for k in RULES if k != right]; rnd.shuffle(others)
    opts = [{"id": k, "nom": RULES[k]["nom"]} for k in (others[:2] + [right])]; rnd.shuffle(opts)
    return 200, {"ok": True, "id": tid, "bayt": q["bayt"], "options": opts, "free": (not acc), "wm": _wm(uid)}


def tab_rule(uid, admin, tid, choice):
    q = TQ.get(str(tid))
    if not q: return 404, {"ok": False, "error": "Bayt topilmadi."}
    if not has_access(uid, admin) and tid != TAB.get("free_id"): return _need_pay()
    right = str(q["ish"])
    return 200, {"ok": True, "correct": str(choice) == right, "right": right, "nom": RULES[right]["nom"], "qoida": RULES[right]["matn"]}


def _overlap(a, b):
    ta = set(re.findall(r"\w+", a.lower())); tb = set(re.findall(r"\w+", b.lower()))
    return int(100 * len(ta & tb) / max(1, len(tb)))


def tab_check(uid, admin, tid, text):
    q = TQ.get(str(tid)); text = str(text or "").strip()
    if not q: return 404, {"ok": False, "error": "Bayt topilmadi."}
    if not has_access(uid, admin) and tid != TAB.get("free_id"): return _need_pay()
    if len(text) < 15 or len(text) > 700: return 400, {"ok": False, "error": "Tabdilni to‘liq yozing (15–700 belgi)."}
    if not admin and _used(uid, "ai") >= AI_DAILY: return 429, {"ok": False, "error": f"Bugungi AI tekshiruv limiti ({AI_DAILY}) tugadi."}
    rule = RULES[str(q["ish"])]
    res = None
    if _AI:
        _bump(uid, "ai")
        sysm = ("Sen Sardor Sayfullayevning mumtoz adabiyot tahlil usuli bo‘yicha tekshiruvchisan. Faqat berilgan namunaviy tabdil va qoidaga tayanib baho ber. "
                "Foydalanuvchi tabdilini ma’no (0-60) va tartib/qoida (0-40) bo‘yicha baholaysan. Javobni FAQAT JSON qil: "
                '{"ball":0-100,"ma_no":"to‘g‘ri|qisman|noto‘g‘ri","tartib":"to‘g‘ri|xato","izoh":"2-3 jumla, o‘zbekcha, qaysi qoida buzilgani aniq","tuzatish":"1 jumla"}')
        usr = f"Bayt:\n{q['bayt']}\n\nQoida: {rule['nom']} — {rule['matn']}\n\nNamunaviy tabdil:\n{q['tabdil']}\n\nFoydalanuvchi tabdili:\n{text}"
        try: res = _AI(sysm, usr)
        except Exception: log.exception("akad ai")
    if not isinstance(res, dict) or "ball" not in res:
        sc = _overlap(text, q["tabdil"])
        res = {"ball": sc, "ma_no": "to‘g‘ri" if sc >= 60 else ("qisman" if sc >= 35 else "noto‘g‘ri"), "tartib": "to‘g‘ri" if sc >= 60 else "xato",
               "izoh": f"Qoidani takrorlang: {rule['nom']}. {rule['matn']}", "tuzatish": ""}
    try: ball = max(0, min(100, int(res.get("ball", 0))))
    except Exception: ball = 0
    with db() as c:
        c.execute("INSERT INTO akad_prog(user_id,qid,ok,at) VALUES(?,?,?,?) ON CONFLICT(user_id,qid) DO UPDATE SET ok=excluded.ok, at=excluded.at", (int(uid), str(tid), 1 if ball >= 70 else 0, _iso(_now()))); c.commit()
    return 200, {"ok": True, "ball": ball, "ma_no": str(res.get("ma_no", ""))[:20], "tartib": str(res.get("tartib", ""))[:20], "izoh": str(res.get("izoh", ""))[:600],
                 "tuzatish": str(res.get("tuzatish", ""))[:300], "namuna": q["tabdil"], "qoida": rule["matn"], "nom": rule["nom"]}


def flag(uid, qid, text):
    with db() as c:
        c.execute("INSERT INTO akad_flag(user_id,qid,text,at) VALUES(?,?,?,?)", (int(uid), str(qid)[:20], str(text or "")[:300], _iso(_now()))); c.commit()
    return {"ok": True}


# ------------------------------------------------------------ admin API
def admin_list(dars):
    ov = _overrides(); out = []
    for q in SAN["savollar"]:
        if dars and q["dars"] != int(dars): continue
        o = ov.get(q["id"]); out.append({"qid": q["id"], "bayt": q["bayt"], "javob": (o[0] if o and o[0] else q["javob"]), "tasdiq": bool(o and o[1]), "ishonch": q["ishonch"], "ajratilgan": q["ajratilgan"]})
    return {"ok": True, "items": out, "arts": list(SAN["qoidalar"].keys())}


# ------------------------------------------------------------ HTTP kirish nuqtalari
def api_get(path, uid, admin, query=None):
    p = path.split("?")[0]; qs = query or {}
    g = lambda k, d="": (qs.get(k) or [d])[0] if isinstance(qs.get(k), list) else qs.get(k, d)
    if p == "/api/akad/state": return 200, state(uid, admin)
    if not (is_open() or admin): return 404, {"ok": False, "error": "Bo‘lim hozircha jarayonda."}
    if p == "/api/akad/theory": return 200, theory_list(uid, admin)
    if p == "/api/akad/san/next":
        try: d = int(g("dars", "0") or 0)
        except Exception: d = 0
        return san_next(uid, admin, d)
    if p == "/api/akad/tab/rules": return 200, tab_rules(uid, admin)
    if p == "/api/akad/tab/next": return tab_next(uid, admin)
    if p == "/api/akad/admin/list":
        if not admin: return 403, {"ok": False, "error": "Faqat admin."}
        try: d = int(g("dars", "0") or 0)
        except Exception: d = 0
        return 200, admin_list(d)
    return 404, {"ok": False, "error": "Topilmadi"}


def api_post(path, body, uid, admin):
    p = path.split("?")[0]
    if not isinstance(body, dict): return 400, {"ok": False, "error": "Noto‘g‘ri so‘rov."}
    if not (is_open() or admin): return 404, {"ok": False, "error": "Bo‘lim hozircha jarayonda."}
    if p == "/api/akad/san/answer": return san_answer(uid, admin, body.get("qid"), body.get("choice"))
    if p == "/api/akad/tab/rule": return tab_rule(uid, admin, str(body.get("id")), body.get("choice"))
    if p == "/api/akad/tab/check": return tab_check(uid, admin, str(body.get("id")), body.get("text"))
    if p == "/api/akad/flag": return 200, flag(uid, body.get("qid"), body.get("text"))
    if p.startswith("/api/akad/admin/"):
        if not admin: return 403, {"ok": False, "error": "Faqat admin."}
        act = p.rsplit("/", 1)[-1]
        if act == "set": return (200, {"ok": True}) if set_answer(qid_norm(body.get("qid")), body.get("javob", "")) else (400, {"ok": False, "error": "Savol yoki san’at nomi noto‘g‘ri."})
        if act == "confirm": return (200, {"ok": True}) if confirm(qid_norm(body.get("qid"))) else (400, {"ok": False, "error": "Savol topilmadi."})
    return 404, {"ok": False, "error": "Topilmadi"}


# ------------------------------------------------------------ admin buyruqlari
async def _guard(update):
    if update.effective_user.id != _ADMIN: return False
    return True


async def och_cmd(update, context):
    if not await _guard(update): return
    set_open(True)
    await update.message.reply_text(f"✅ «{TITLE}» hamma uchun ochildi. Yopish: /mumtoz_yop")

async def yop_cmd(update, context):
    if not await _guard(update): return
    set_open(False)
    await update.message.reply_text("🚧 Bo‘lim yopildi (jarayonda). Faqat admin ko‘radi. Ochish: /mumtoz_och")

async def obuna_cmd(update, context):
    """/mumtoz_obuna ID [kun] — qo'lda obuna berish (to'lovsiz)."""
    if not await _guard(update): return
    a = context.args or []
    try: uid = int(a[0]); days = int(a[1]) if len(a) > 1 else DAYS
    except Exception:
        await update.message.reply_text("Format: /mumtoz_obuna 123456789 30"); return
    until = grant(uid, days, f"admin:{uid}:{int(time.time())}")
    await update.message.reply_text(f"✅ {uid} ga obuna berildi: {until.strftime('%d.%m.%Y')} gacha.")
    try: await context.bot.send_message(uid, f"🎉 «{TITLE}» ochildi — {until.strftime('%d.%m.%Y')} gacha.\nMini App → Boshqa imkoniyatlar.")
    except Exception: pass

async def holat_cmd(update, context):
    if not await _guard(update): return
    with db() as c:
        act = c.execute("SELECT COUNT(*) FROM akad_sub WHERE until>?", (_iso(_now()),)).fetchone()[0]
        allsub = c.execute("SELECT COUNT(*) FROM akad_sub").fetchone()[0]
        fl = c.execute("SELECT COUNT(*) FROM akad_flag").fetchone()[0]
        conf = c.execute("SELECT COUNT(*) FROM akad_ans WHERE confirmed=1").fetchone()[0]
    low = sum(1 for q in SAN["savollar"] if q["ishonch"] == "past")
    await update.message.reply_text(f"📊 {TITLE}\nHolat: {'🟢 ochiq' if is_open() else '🔴 yopiq (jarayonda)'}\nNarx: {PRICE:,} so‘m / {DAYS} kun\nFaol obunachilar: {act} (jami bo‘lgan: {allsub})\nSavollar: {len(SQ)} • tasdiqlangan javob: {conf} • «past ishonch»: {low}\nTabdil baytlari: {len(TQ)}\nShikoyatlar: {fl} (/san_shikoyat)")

async def javob_cmd(update, context):
    """/san_javob d3-24 Tajohuli orif — javobni tuzatish."""
    if not await _guard(update): return
    a = context.args or []
    if len(a) < 2:
        await update.message.reply_text("Format: /san_javob d3-24 Tajohuli orif\nTasdiqlash: /san_tasdiq d3-24\nSan’at nomlari: /san_nomlar"); return
    qid = qid_norm(a[0]); art = " ".join(a[1:])
    if set_answer(qid, art):
        await update.message.reply_text(f"✅ {qid}: javob «{match_art(art)}» deb o‘zgartirildi va tasdiqlandi.")
    else:
        await update.message.reply_text("⚠️ Savol raqami yoki san’at nomi topilmadi. /san_nomlar")

async def tasdiq_cmd(update, context):
    if not await _guard(update): return
    a = context.args or []
    if not a: await update.message.reply_text("Format: /san_tasdiq d3-24  (yoki /san_tasdiq hammasi)"); return
    if a[0].lower() == "hammasi":
        n = sum(1 for q in SQ if confirm(q)); await update.message.reply_text(f"✅ {n} ta javob tasdiqlandi."); return
    ok = confirm(qid_norm(a[0])); await update.message.reply_text("✅ Tasdiqlandi." if ok else "⚠️ Savol topilmadi.")

async def nomlar_cmd(update, context):
    if not await _guard(update): return
    await update.message.reply_text("San’atlar:\n" + ", ".join(SAN["qoidalar"].keys()))

async def shikoyat_cmd(update, context):
    if not await _guard(update): return
    with db() as c: rows = c.execute("SELECT qid,text,user_id FROM akad_flag ORDER BY id DESC LIMIT 15").fetchall()
    await update.message.reply_text("🚩 Oxirgi shikoyatlar:\n" + ("\n".join(f"{r[0]} • {r[2]}: {r[1] or '—'}" for r in rows) if rows else "— yo‘q —"))

async def _remind(context):
    """Obuna tugashiga 3 kun qolganda bir marta eslatadi."""
    try:
        lim = _iso(_now() + timedelta(days=3))
        with db() as c: rows = c.execute("SELECT user_id,until FROM akad_sub WHERE until>? AND until<=? AND warned=0", (_iso(_now()), lim)).fetchall()
        for uid, until in rows:
            try:
                await context.bot.send_message(uid, f"⏳ «{TITLE}» obunangiz {datetime.fromisoformat(until).strftime('%d.%m.%Y')} da tugaydi.\nDavom ettirish: Mini App → Boshqa imkoniyatlar → Mumtoz tahlil maktabi.")
            except Exception: pass
            with db() as c: c.execute("UPDATE akad_sub SET warned=1 WHERE user_id=?", (uid,)); c.commit()
    except Exception: log.exception("akad remind")


def register(app):
    from telegram.ext import CommandHandler
    for n, f in (("mumtoz_och", och_cmd), ("mumtoz_yop", yop_cmd), ("mumtoz_obuna", obuna_cmd), ("mumtoz_holat", holat_cmd),
                 ("san_javob", javob_cmd), ("san_tasdiq", tasdiq_cmd), ("san_nomlar", nomlar_cmd), ("san_shikoyat", shikoyat_cmd)):
        app.add_handler(CommandHandler(n, f))
    try:
        if app.job_queue: app.job_queue.run_repeating(_remind, interval=6 * 3600, first=120)
    except Exception: log.exception("akad job")
