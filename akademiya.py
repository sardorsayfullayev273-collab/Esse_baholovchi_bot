# -*- coding: utf-8 -*-
"""v123: «Sardor Sayfullayev: Mumtoz tahlil maktabi» — pullik bo'lim (G'azal tabdili + She'riy san'atlar).
Obuna: 30 000 so'm / 30 kun (mavjud karta to'lovi orqali, kind='akad', plan='pro').
Bo'lim admin buyrug'i bilan ochiladi (/mumtoz_och). Savollar serverda qoladi, bittalab beriladi."""
import copy, json, os, re, time, random, hashlib, logging
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
_SEED_SAN = copy.deepcopy(SAN); _SEED_TAB = copy.deepcopy(TAB)   # v124: asl (fayldagi) ma'lumot; admin tahrirlari bazada, ustiga qo'yiladi
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
        if "done" not in {r[1] for r in c.execute("PRAGMA table_info(akad_flag)").fetchall()}:
            c.execute("ALTER TABLE akad_flag ADD COLUMN done INTEGER DEFAULT 0")
        c.execute("CREATE TABLE IF NOT EXISTS akad_item(kind TEXT NOT NULL, iid TEXT NOT NULL, data TEXT, deleted INTEGER DEFAULT 0, at TEXT, PRIMARY KEY(kind,iid))")
        c.commit()
    _reload()


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
    pool = [a for a in SAN["chalgitish"].get(right, []) if a in SAN["qoidalar"] and a != right]
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
        _pr = c.execute("SELECT qid, ok FROM akad_prog WHERE user_id=?", (int(uid),)).fetchall() if uid else []
    done = (sum(1 for r in _pr if r[0] in SQ), sum(int(r[1] or 0) for r in _pr if r[0] in SQ))   # o'chirilgan savollar hisobga olinmaydi
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
    return 200, {"ok": True, "correct": ok, "right": right, "qoida": SAN["qoidalar"].get(right, ""), "izoh": q.get("izoh", ""), "tanlangan_qoida": SAN["qoidalar"].get(match_art(choice) or "", "") if not ok else ""}


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



# ------------------------------------------------------------ v124: KONTENT MUHARRIRI (Mini App ichida; admin)
# Asl ma'lumot — akad_sanat.json / akad_tabdil.json (kod bilan keladi). Admin qo'shgan/tuzatgan/o'chirganlari — bazada (akad_item) va
# asl ma'lumot USTIGA qo'yiladi: Render qayta ishga tushsa ham, yangi versiya yuklansa ham yo'qolmaydi.
def _err(msg, code=400): return code, {"ok": False, "error": msg}


def _rows():
    try:
        with db() as c: return c.execute("SELECT kind,iid,data,deleted FROM akad_item").fetchall()
    except Exception: return []


def _reload():
    """Asl ma'lumot + admin tahrirlari -> SAN/TAB/SQ/TQ/RULES (joyida yangilanadi: boshqa modullar havolasi buzilmaydi)."""
    san = copy.deepcopy(_SEED_SAN); tab = copy.deepcopy(_SEED_TAB)
    qs = {q["id"]: q for q in san["savollar"]}; tqs = {q["id"]: q for q in tab["savollar"]}; rules = {str(r["id"]): r for r in tab["qoidalar"]}
    for kind, iid, data, dele in _rows():
        try: d = json.loads(data or "{}")
        except Exception: d = {}
        if kind == "art":
            if dele: san["qoidalar"].pop(iid, None); san["chalgitish"].pop(iid, None)
            else:
                san["qoidalar"][iid] = d.get("text", "")
                if "chalgitish" in d: san["chalgitish"][iid] = [x for x in d["chalgitish"] if x]
        elif kind == "rule":
            if dele: rules.pop(iid, None)
            else: rules[iid] = {"id": int(iid) if str(iid).isdigit() else iid, "nom": d.get("nom", ""), "matn": d.get("matn", "")}
        elif kind == "q":
            if dele: qs.pop(iid, None)
            else:
                b = dict(qs.get(iid) or {}); b.update(d); b["id"] = iid; b["ishonch"] = "yuqori"; b["tasdiqlangan"] = True; b.setdefault("izoh", ""); qs[iid] = b
        elif kind == "tq":
            if dele: tqs.pop(iid, None)
            else:
                b = dict(tqs.get(iid) or {}); b.update(d); b["id"] = iid; b["tasdiqlangan"] = True; tqs[iid] = b
    san["savollar"] = sorted(qs.values(), key=lambda q: (int(q.get("dars", 0)), int(q.get("raqam", 0))))
    tab["savollar"] = list(tqs.values())
    tab["qoidalar"] = sorted(rules.values(), key=lambda r: int(r["id"]) if str(r["id"]).isdigit() else 9999)
    fq, fa, ft = setting("akad_free_q", ""), setting("akad_free_art", ""), setting("akad_free_tq", "")
    if fq and fq in qs: san["free_qid"] = fq
    if fa and fa in san["qoidalar"]: san["free_art"] = fa
    if ft and ft in tqs: tab["free_id"] = ft
    SAN.clear(); SAN.update(san); TAB.clear(); TAB.update(tab)
    SQ.clear(); SQ.update({q["id"]: q for q in san["savollar"]})
    TQ.clear(); TQ.update({q["id"]: q for q in tab["savollar"]})
    RULES.clear(); RULES.update({str(r["id"]): r for r in tab["qoidalar"]})


def _put(kind, iid, data=None, deleted=0):
    with db() as c:
        c.execute("INSERT INTO akad_item(kind,iid,data,deleted,at) VALUES(?,?,?,?,?) ON CONFLICT(kind,iid) DO UPDATE SET data=excluded.data, deleted=excluded.deleted, at=excluded.at",
                  (kind, str(iid), json.dumps(data or {}, ensure_ascii=False), int(deleted), _iso(_now())))
        c.commit()
    _reload()


def _ws(s): return re.sub(r"\s+", " ", str(s or "")).strip()


def _fold(s): return _ws(re.sub(r"[‘’ʻ`´ʼ]", "'", str(s or ""))).lower()


def _lines(v, n=6, m=200):
    if isinstance(v, str): v = v.replace("\r", "").split("\n")
    out = []
    for x in (v or []):
        x = _ws(x)
        if x and x not in out: out.append(x[:m])
    return out[:n]


def _used_ids(kind):
    """Allaqachon band (o'chirilgan ham) identifikatorlar — qayta ishlatilmaydi."""
    seed = {"q": [q["id"] for q in _SEED_SAN["savollar"]], "tq": [q["id"] for q in _SEED_TAB["savollar"]], "rule": [str(r["id"]) for r in _SEED_TAB["qoidalar"]]}.get(kind, [])
    return set(seed) | {r[1] for r in _rows() if r[0] == kind}


def _flags_done(qid):
    with db() as c: c.execute("UPDATE akad_flag SET done=1 WHERE qid=?", (str(qid),)); c.commit()


def save_question(b):
    bayt = str(b.get("bayt") or "").replace("\r", "").strip()
    if not (8 <= len(bayt) <= 700): return _err("Bayt matni 8–700 belgi bo‘lsin.")
    art = match_art(b.get("javob", ""))
    if not art: return _err("San’at nomi topilmadi. Avval «San’at ma’lumoti» bo‘limida qo‘shing yoki ro‘yxatdan tanlang.")
    aj = _lines(b.get("ajratilgan"))
    for a in aj:
        if _fold(a) not in _fold(bayt): return _err(f"Ajratilgan «{a[:40]}» baytda topilmadi — baytdagi yozilishi bilan bir xil bo‘lsin.")
    izoh = str(b.get("izoh") or "").strip()[:400]
    qid = qid_norm(b.get("qid")) if b.get("qid") else ""
    if qid:
        old = SQ.get(qid)
        if not old: return _err("Savol topilmadi (o‘chirilgan bo‘lishi mumkin).", 404)
        dars, dnom, raqam = old["dars"], old["dars_nom"], old["raqam"]
    else:
        try: dars = int(b.get("dars") or 0)
        except Exception: dars = 0
        if not (1 <= dars <= 99): return _err("Dars raqami 1–99 bo‘lsin.")
        dnom = next((q["dars_nom"] for q in SAN["savollar"] if q["dars"] == dars), "")
        if not dnom:
            dnom = _ws(b.get("dars_nom"))
            if not (3 <= len(dnom) <= 80): return _err("Yangi dars uchun nomini yozing (3–80 belgi).")
        used = _used_ids("q")
        raqam = 1 + max([int(i.split("-")[1]) for i in used if i.startswith(f"d{dars}-") and i.split("-")[1].isdigit()] or [0])
        qid = f"d{dars}-{raqam}"
    _put("q", qid, {"dars": dars, "dars_nom": dnom, "raqam": raqam, "bayt": bayt, "ajratilgan": aj, "javob": art, "izoh": izoh})
    with db() as c:   # javob ham tasdiqlanadi (akad_ans — mavjud tuzatish mexanizmi)
        c.execute("INSERT INTO akad_ans(qid,javob,confirmed,at) VALUES(?,?,1,?) ON CONFLICT(qid) DO UPDATE SET javob=excluded.javob, confirmed=1, at=excluded.at", (qid, art, _iso(_now()))); c.commit()
    _flags_done(qid)
    if b.get("free"): set_setting("akad_free_q", qid); _reload()
    return 200, {"ok": True, "qid": qid}


def save_art(b):
    name = _ws(b.get("art")); cur = match_art(name)
    name = cur or name
    if not (2 <= len(name) <= 60): return _err("San’at nomi 2–60 belgi bo‘lsin.")
    text = str(b.get("text") or "").strip()
    if not (20 <= len(text) <= 900): return _err("Ta’rif 20–900 belgi bo‘lsin.")
    if not cur and any(_key(a) == _key(name) for a in SAN["qoidalar"]): return _err("Bunday nomli san’at bor.")
    if b.get("chalgitish") is None: ch = list(SAN["chalgitish"].get(name, []))
    else:
        ch = []
        for x in _lines(b.get("chalgitish"), 3, 60):
            m = match_art(x)
            if not m: return _err(f"Chalg‘itish varianti «{x[:30]}» san’atlar ro‘yxatida yo‘q.")
            if m != name and m not in ch: ch.append(m)
    _put("art", name, {"text": text, "chalgitish": ch})
    if b.get("free"): set_setting("akad_free_art", name); _reload()
    return 200, {"ok": True, "art": name}


def save_rule(b):
    nom = _ws(b.get("nom")); matn = str(b.get("matn") or "").strip()
    if not (3 <= len(nom) <= 80): return _err("Qoida nomi 3–80 belgi bo‘lsin.")
    if not (20 <= len(matn) <= 900): return _err("Qoida matni 20–900 belgi bo‘lsin.")
    rid = str(b.get("id") or "").strip()
    if rid:
        if rid not in RULES: return _err("Qoida topilmadi.", 404)
    else:
        rid = str(1 + max([int(i) for i in _used_ids("rule") if str(i).isdigit()] or [0]))
    _put("rule", rid, {"nom": nom, "matn": matn})
    return 200, {"ok": True, "id": rid}


def save_tq(b):
    bayt = str(b.get("bayt") or "").replace("\r", "").strip(); tabdil = str(b.get("tabdil") or "").strip(); ish = str(b.get("ish") or "").strip()
    if not (8 <= len(bayt) <= 600): return _err("Bayt matni 8–600 belgi bo‘lsin.")
    if ish not in RULES: return _err("Qoida tanlanmagan yoki topilmadi.")
    if not (15 <= len(tabdil) <= 700): return _err("Namunaviy tabdil 15–700 belgi bo‘lsin.")
    tid = str(b.get("id") or "").strip()
    if tid:
        if tid not in TQ: return _err("Bayt topilmadi (o‘chirilgan bo‘lishi mumkin).", 404)
    else:
        tid = "t" + str(1 + max([int(i[1:]) for i in _used_ids("tq") if i[1:].isdigit()] or [0]))
    _put("tq", tid, {"bayt": bayt, "ish": int(ish) if ish.isdigit() else ish, "tabdil": tabdil})
    _flags_done(tid)
    if b.get("free"): set_setting("akad_free_tq", tid); _reload()
    return 200, {"ok": True, "id": tid}


def _snapshot(kind, iid):
    if kind == "q":
        q = SQ.get(iid)
        if not q: return None
        d = {k: q.get(k, "") for k in ("dars", "dars_nom", "raqam", "bayt", "ajratilgan", "javob", "izoh")}; d["javob"] = answer_of(iid); return d
    if kind == "tq": q = TQ.get(iid); return q and {k: q.get(k, "") for k in ("bayt", "ish", "tabdil")}
    if kind == "art": return iid in SAN["qoidalar"] and {"text": SAN["qoidalar"][iid], "chalgitish": SAN["chalgitish"].get(iid, [])}
    if kind == "rule": r = RULES.get(iid); return r and {"nom": r["nom"], "matn": r["matn"]}
    return None


def delete_item(kind, iid):
    iid = str(iid or "").strip()
    if kind == "q": iid = qid_norm(iid)
    snap = _snapshot(kind, iid)
    if not snap: return _err("Topilmadi.", 404)
    if kind == "q" and SAN.get("free_qid") == iid: return _err("Bu — bepul namuna savol. Avval boshqa savolni «Bepul namuna» qiling.")
    if kind == "tq" and TAB.get("free_id") == iid: return _err("Bu — bepul namuna bayt. Avval boshqasini «Bepul namuna» qiling.")
    if kind == "art":
        if SAN.get("free_art") == iid: return _err("Bu — bepul namuna nazariya. Avval boshqasini «Bepul namuna» qiling.")
        n = sum(1 for q in SQ.values() if answer_of(q["id"]) == iid)
        if n: return _err(f"Bu san’at {n} ta savolda javob sifatida ishlatilgan. Avval o‘sha savollarni tuzating.")
    if kind == "rule":
        n = sum(1 for q in TQ.values() if str(q["ish"]) == iid)
        if n: return _err(f"Bu qoida {n} ta baytda ishlatilgan. Avval o‘sha baytlarni tuzating.")
    _put(kind, iid, snap, deleted=1)
    return 200, {"ok": True}


def restore_item(kind, iid):
    iid = str(iid or "").strip()
    with db() as c: r = c.execute("SELECT data FROM akad_item WHERE kind=? AND iid=? AND deleted=1", (kind, iid)).fetchone()
    if not r: return _err("Topilmadi.", 404)
    _put(kind, iid, json.loads(r[0] or "{}"), deleted=0)
    return 200, {"ok": True}


def set_free(kind, iid):
    iid = str(iid or "").strip()
    if kind == "q" and qid_norm(iid) in SQ: set_setting("akad_free_q", qid_norm(iid))
    elif kind == "tq" and iid in TQ: set_setting("akad_free_tq", iid)
    elif kind == "art" and iid in SAN["qoidalar"]: set_setting("akad_free_art", iid)
    else: return _err("Topilmadi.", 404)
    _reload(); return 200, {"ok": True}


def flag_clear(fid):
    try: fid = int(fid)
    except Exception: return _err("Noto‘g‘ri raqam.")
    with db() as c: c.execute("UPDATE akad_flag SET done=1 WHERE id=?", (fid,)); c.commit()
    return 200, {"ok": True}


def admin_content():
    """Muharrir ekrani uchun to'liq ma'lumot (faqat admin)."""
    ov = _overrides(); edited = {(r[0], r[1]) for r in _rows() if not r[3]}
    lessons = {}
    for q in SAN["savollar"]: lessons.setdefault(q["dars"], q["dars_nom"])
    used_art = {}
    for q in SQ.values(): a = answer_of(q["id"]); used_art[a] = used_art.get(a, 0) + 1
    used_rule = {}
    for q in TQ.values(): used_rule[str(q["ish"])] = used_rule.get(str(q["ish"]), 0) + 1
    qs = []
    for q in SAN["savollar"]:
        o = ov.get(q["id"])
        qs.append({"qid": q["id"], "dars": q["dars"], "dars_nom": q["dars_nom"], "raqam": q["raqam"], "bayt": q["bayt"], "ajratilgan": q.get("ajratilgan", []), "javob": answer_of(q["id"]),
                   "izoh": q.get("izoh", ""), "tasdiq": bool(o and o[1]) or bool(q.get("tasdiqlangan")), "ishonch": q.get("ishonch", ""), "free": q["id"] == SAN.get("free_qid"), "edited": ("q", q["id"]) in edited})
    arts = [{"art": a, "text": t, "chalgitish": SAN["chalgitish"].get(a, []), "used": used_art.get(a, 0), "free": a == SAN.get("free_art"), "edited": ("art", a) in edited} for a, t in SAN["qoidalar"].items()]
    tq = [{"id": q["id"], "bayt": q["bayt"], "ish": str(q["ish"]), "tabdil": q["tabdil"], "free": q["id"] == TAB.get("free_id"), "edited": ("tq", q["id"]) in edited} for q in TAB["savollar"]]
    rules = [{"id": str(r["id"]), "nom": r["nom"], "matn": r["matn"], "used": used_rule.get(str(r["id"]), 0)} for r in TAB["qoidalar"]]
    with db() as c:
        fl = c.execute("SELECT id,user_id,qid,text,at FROM akad_flag WHERE COALESCE(done,0)=0 ORDER BY id DESC LIMIT 100").fetchall()
        dl = c.execute("SELECT kind,iid,data FROM akad_item WHERE deleted=1 ORDER BY at DESC").fetchall()
    deleted = []
    for k, i, d in dl:
        try: dd = json.loads(d or "{}")
        except Exception: dd = {}
        lab = (dd.get("bayt") or dd.get("nom") or i)[:60].replace("\n", " / ") if k != "art" else i
        deleted.append({"kind": k, "id": i, "label": lab})
    return {"ok": True, "lessons": [{"dars": k, "nom": v} for k, v in sorted(lessons.items())], "q": qs, "arts": arts, "tq": tq, "rules": rules,
            "flags": [{"id": r[0], "user_id": r[1], "qid": r[2], "text": r[3], "at": r[4]} for r in fl], "deleted": deleted}


_ADMIN_ROUTES = {
    "q/save": save_question, "art/save": save_art, "rule/save": save_rule, "tq/save": save_tq,
    "q/delete": lambda b: delete_item("q", b.get("qid")), "art/delete": lambda b: delete_item("art", b.get("art")),
    "rule/delete": lambda b: delete_item("rule", b.get("id")), "tq/delete": lambda b: delete_item("tq", b.get("id")),
    "restore": lambda b: restore_item(str(b.get("kind") or ""), b.get("id")), "free": lambda b: set_free(str(b.get("kind") or ""), b.get("id")),
    "flag/clear": lambda b: flag_clear(b.get("id")),
}


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
    if p == "/api/akad/admin/content":
        if not admin: return 403, {"ok": False, "error": "Faqat admin."}
        return 200, admin_content()
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
        h = _ADMIN_ROUTES.get(p[len("/api/akad/admin/"):])   # v124: muharrir
        if h:
            try: return h(body)
            except Exception:
                log.exception("akad admin %s", p); return _err("Saqlab bo‘lmadi. Qayta urinib ko‘ring.", 500)
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
        fl = c.execute("SELECT COUNT(*) FROM akad_flag WHERE COALESCE(done,0)=0").fetchone()[0]
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
    with db() as c: rows = c.execute("SELECT qid,text,user_id FROM akad_flag WHERE COALESCE(done,0)=0 ORDER BY id DESC LIMIT 15").fetchall()
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
