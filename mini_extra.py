"""Mini App qo'shimcha moduli: himoya (spam/ban), reyting, mukofotlar, sertifikatlar."""
import io, os, json, time, secrets, threading, uuid
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from national_certificate import db, now, level_for

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti
PERIOD_NAMES = {"day": "Kunlik", "week": "Haftalik", "month": "Oylik"}

# ---------------------------------------------------------------- DB
def init_extra_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS mini_users(user_id INTEGER PRIMARY KEY, name TEXT, username TEXT, first_seen TEXT, last_seen TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS mini_banned(user_id INTEGER PRIMARY KEY, reason TEXT, banned_at TEXT, banned_by INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS mini_awards(id INTEGER PRIMARY KEY AUTOINCREMENT, period TEXT, period_key TEXT, rank INTEGER,
            user_id INTEGER, points REAL, tests INTEGER, cert_code TEXT, created_at TEXT, UNIQUE(period, period_key, rank))""")
        c.execute("""CREATE TABLE IF NOT EXISTS mini_certs(code TEXT PRIMARY KEY, user_id INTEGER, kind TEXT, data_json TEXT, created_at TEXT)""")
        c.commit()

# ---------------------------------------------------------------- Limiter (xotirada)
_hits = defaultdict(deque); _lock = threading.Lock()

def allow(key, limit, window):
    """True: ruxsat. `window` soniya ichida `limit` tadan ko'p bo'lsa False."""
    t = time.time()
    with _lock:
        q = _hits[key]
        while q and q[0] <= t - window: q.popleft()
        if len(q) >= limit: return False
        q.append(t)
        if len(_hits) > 20000:  # xotira nazorati
            for k in [k for k, v in _hits.items() if not v or v[-1] < t - 3600][:5000]: _hits.pop(k, None)
        return True

# ---------------------------------------------------------------- Foydalanuvchilar / ban
_seen = {}
def touch_user(u):
    try:
        uid = int(u["id"]); t = time.time()
        if t - _seen.get(uid, 0) < 300: return
        _seen[uid] = t
        name = " ".join(x for x in [u.get("first_name", ""), u.get("last_name", "")] if x).strip()[:80]
        with db() as c:
            c.execute("""INSERT INTO mini_users(user_id,name,username,first_seen,last_seen) VALUES(?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, username=excluded.username, last_seen=excluded.last_seen""",
                (uid, name, (u.get("username") or "")[:60], now(), now()))
            c.commit()
    except Exception:
        pass

def user_name(uid):
    with db() as c:
        r = c.execute("SELECT name,username FROM mini_users WHERE user_id=?", (uid,)).fetchone()
    if r and r["name"]: return r["name"]
    if r and r["username"]: return "@" + r["username"]
    return f"Talabgor {uid}"

_ban_cache = {"t": 0, "ids": set()}
def banned_ids():
    if time.time() - _ban_cache["t"] > 15:
        with db() as c: _ban_cache["ids"] = {r[0] for r in c.execute("SELECT user_id FROM mini_banned")}
        _ban_cache["t"] = time.time()
    return _ban_cache["ids"]

def is_banned(uid): return uid is not None and int(uid) in banned_ids()

def ban(uid, reason, by):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO mini_banned(user_id,reason,banned_at,banned_by) VALUES(?,?,?,?)", (int(uid), str(reason)[:200], now(), int(by))); c.commit()
    _ban_cache["t"] = 0

def unban(uid):
    with db() as c: c.execute("DELETE FROM mini_banned WHERE user_id=?", (int(uid),)); c.commit()
    _ban_cache["t"] = 0

# ---------------------------------------------------------------- Testlar (admin nazorati)
def list_tests_ex(admin_id, include_hidden=False):
    q = """SELECT t.id,t.code,t.title,t.subject,t.duration_min,t.created_at,t.created_by,t.published,
           (SELECT COUNT(*) FROM national_attempts a WHERE a.test_id=t.id) AS attempts
           FROM national_tests t """ + ("" if include_hidden else "WHERE t.published=1 ") + "ORDER BY t.id DESC LIMIT 200"
    with db() as c: rows = [dict(r) for r in c.execute(q)]
    for r in rows: r["official"] = int(r["created_by"] or 0) == int(admin_id)
    return rows

def count_user_tests(uid, since_iso):
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM national_tests WHERE created_by=? AND created_at>=?", (uid, since_iso)).fetchone()[0]

def overview(admin_id):
    day0 = period_bounds("day")[0]
    with db() as c:
        o = {"users": c.execute("SELECT COUNT(*) FROM mini_users").fetchone()[0],
             "tests": c.execute("SELECT COUNT(*) FROM national_tests WHERE published=1").fetchone()[0],
             "user_tests": c.execute("SELECT COUNT(*) FROM national_tests WHERE published=1 AND created_by<>?", (admin_id,)).fetchone()[0],
             "attempts_today": c.execute("SELECT COUNT(*) FROM national_attempts WHERE created_at>=?", (day0,)).fetchone()[0],
             "banned": [dict(r) for r in c.execute("SELECT user_id,reason,banned_at FROM mini_banned ORDER BY banned_at DESC LIMIT 50")]}
    tests = list_tests_ex(admin_id)[:60]
    for t in tests: t["creator"] = user_name(t["created_by"]) if t["created_by"] else "—"
    o["recent_tests"] = tests
    return o

# ---------------------------------------------------------------- Reyting
def period_bounds(kind, ref=None):
    """(boshlanish_utc_iso, tugash_utc_iso, kalit, nom) — Toshkent vaqti bo'yicha."""
    d = (ref or datetime.now(TZ)).astimezone(TZ)
    if kind == "day": s = d.replace(hour=0, minute=0, second=0, microsecond=0); e = s + timedelta(days=1); key = s.strftime("%Y-%m-%d"); name = s.strftime("%d.%m.%Y")
    elif kind == "week":
        s = (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0); e = s + timedelta(days=7)
        key = s.strftime("%Y-W%W"); name = f"{s.strftime('%d.%m')} – {(e - timedelta(days=1)).strftime('%d.%m.%Y')}"
    else:
        s = d.replace(day=1, hour=0, minute=0, second=0, microsecond=0); e = (s + timedelta(days=32)).replace(day=1)
        key = s.strftime("%Y-%m"); name = s.strftime("%m.%Y")
    u = lambda x: x.astimezone(timezone.utc).isoformat(timespec="seconds")
    return u(s), u(e), key, name

def leaderboard(kind, admin_id, limit=20, start=None, end=None):
    """Faqat admin kiritgan (rasmiy) testlar, har bir testning birinchi urinishi hisoblanadi."""
    if start is None: start, end = period_bounds(kind)[:2]
    q = """SELECT a.user_id, SUM(a.raw_score) AS pts, COUNT(*) AS n, MIN(a.created_at) AS first
           FROM national_attempts a JOIN national_tests t ON t.id=a.test_id AND t.created_by=? AND t.published=1
           WHERE a.id IN (SELECT MIN(id) FROM national_attempts GROUP BY user_id, test_id)
             AND a.created_at>=? AND a.created_at<? AND a.user_id<>?
             AND a.user_id NOT IN (SELECT user_id FROM mini_banned)
           GROUP BY a.user_id ORDER BY pts DESC, n DESC, first ASC"""
    with db() as c: rows = [dict(r) for r in c.execute(q, (admin_id, start, end, admin_id))]
    for i, r in enumerate(rows, 1): r["rank"] = i; r["pts"] = round(r["pts"], 1)
    return rows

def rating_payload(kind, uid, admin_id):
    s, e, key, name = period_bounds(kind)
    rows = leaderboard(kind, admin_id, start=s, end=e)
    top = [{"rank": r["rank"], "name": user_name(r["user_id"]), "pts": r["pts"], "n": r["n"], "me": r["user_id"] == uid} for r in rows[:20]]
    me = next(({"rank": r["rank"], "pts": r["pts"], "n": r["n"]} for r in rows if r["user_id"] == uid), None)
    return {"period": kind, "label": PERIOD_NAMES[kind], "range": name, "top": top, "me": me, "total": len(rows)}

# ---------------------------------------------------------------- Sertifikatlar
def new_cert(uid, kind, data):
    code = ("DG-" if kind == "diag" else "MX-") + secrets.token_hex(5).upper()
    with db() as c:
        c.execute("INSERT INTO mini_certs(code,user_id,kind,data_json,created_at) VALUES(?,?,?,?,?)", (code, uid, kind, json.dumps(data, ensure_ascii=False), now())); c.commit()
    return code

def get_cert(code):
    with db() as c: r = c.execute("SELECT * FROM mini_certs WHERE code=?", (str(code).upper().strip(),)).fetchone()
    if not r: return None
    d = dict(r); d["data"] = json.loads(d.pop("data_json")); return d

_FONT_DIRS = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"), "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation2", "/usr/share/fonts/truetype/liberation"]
def _font(size, bold=False, serif=True):
    from PIL import ImageFont
    names = ([("DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf")] if serif else []) + [("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), ("LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf")]
    for d in _FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p): return ImageFont.truetype(p, size)
    try: return ImageFont.load_default(size)
    except TypeError: return ImageFont.load_default()

LEVELS = [("C", "46–49,9"), ("C+", "50–54,9"), ("B", "55–59,9"), ("B+", "60–64,9"), ("A", "65–69,9"), ("A+", "70–75")]

def render_certificate(kind, data, code):
    """PNG bayt qaytaradi. kind: 'diag' (diagnostik natija) yoki 'award' (kun/hafta/oy bilimdoni). Dizayn: cert_design.py"""
    import cert_design
    key = (kind, code, json.dumps(data, sort_keys=True, ensure_ascii=False))
    with _lock:
        hit = _png_cache.get(key)
    if hit: return hit
    png = cert_design.render(kind, data, code)
    with _lock:
        if len(_png_cache) >= 30: _png_cache.pop(next(iter(_png_cache)))
        _png_cache[key] = png
    return png
_png_cache = {}

def send_photo(token, chat_id, png, caption=""):
    """Telegram'ga rasm (hujjat sifatida emas, oddiy rasm) yuboradi — multipart, qo'shimcha kutubxonasiz."""
    b = uuid.uuid4().hex
    parts = []
    for k, v in (("chat_id", str(chat_id)), ("caption", caption[:900])):
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="sertifikat.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + png + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendPhoto", data=b"".join(parts), headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode())

# ---------------------------------------------------------------- Mukofotlash (kun/hafta/oy)
def award_due(admin_id):
    """Tugagan davrlar uchun TOP-3 ni bir marta belgilaydi; yangi mukofotlar ro'yxatini qaytaradi."""
    out = []
    for kind in ("day", "week", "month"):
        cur_start = datetime.fromisoformat(period_bounds(kind)[0])
        s, e, key, name = period_bounds(kind, cur_start - timedelta(seconds=1))
        with db() as c:
            if c.execute("SELECT 1 FROM mini_awards WHERE period=? AND period_key=? LIMIT 1", (kind, key)).fetchone(): continue
        top = leaderboard(kind, admin_id, start=s, end=e)[:3]
        if not top:
            with db() as c: c.execute("INSERT OR IGNORE INTO mini_awards(period,period_key,rank,user_id,points,tests,created_at) VALUES(?,?,0,0,0,0,?)", (kind, key, now())); c.commit()
            continue
        for r in top:
            data = {"name": user_name(r["user_id"]), "rank": r["rank"], "pts": r["pts"], "tests": r["n"], "range": name,
                    "period_name": PERIOD_NAMES[kind], "date": datetime.now(TZ).strftime("%d.%m.%Y")}
            code = new_cert(r["user_id"], "award", data)
            with db() as c:
                c.execute("INSERT OR IGNORE INTO mini_awards(period,period_key,rank,user_id,points,tests,cert_code,created_at) VALUES(?,?,?,?,?,?,?,?)", (kind, key, r["rank"], r["user_id"], r["pts"], r["n"], code, now())); c.commit()
            out.append({"user_id": r["user_id"], "code": code, "kind": kind, "rank": r["rank"], "data": data})
    return out

def award_loop(token, admin_id, log=print):
    def run():
        time.sleep(30)
        while True:
            try:
                for a in award_due(admin_id):
                    try:
                        png = render_certificate("award", a["data"], a["code"])
                        send_photo(token, a["user_id"], png, f"🏆 Tabriklaymiz! {a['data']['period_name']} reytingida {a['rank']}-o‘rin! Maxsus sertifikatingiz tayyor.")
                        time.sleep(0.5)
                    except Exception as e: log(f"award send error {a['user_id']}: {e}")
            except Exception as e: log(f"award loop error: {e}")
            time.sleep(600)
    threading.Thread(target=run, daemon=True).start()
