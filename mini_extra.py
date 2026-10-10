import re
"""Mini App qo'shimcha moduli: himoya (spam/ban), reyting, mukofotlar, sertifikatlar."""
import io, os, json, time, secrets, threading, uuid, sqlite3
from contextlib import closing
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from national_certificate import db, now, level_for

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti
PERIOD_NAMES = {"day": "Kunlik", "week": "Haftalik", "month": "Oylik"}

def _envi(name, default):
    try: return int(os.getenv(name, str(default)))
    except Exception: return int(default)

# 1-o'rin sovrini: Premium necha kun (0 = o'chirilgan). Render Environment orqali o'zgaradi.
PRIZE_DAYS = {"day": _envi("PRIZE_DAY_DAYS", 0), "week": _envi("PRIZE_WEEK_DAYS", 7), "month": _envi("PRIZE_MONTH_DAYS", 30)}
REMIND_EVERY_DAYS = _envi("REMIND_EVERY_DAYS", 3)    # bitta odamga eslatma orasidagi eng kam kun
REMIND_MAX_PER_DAY = _envi("REMIND_MAX_PER_DAY", 400)

# ---------------------------------------------------------------- DB
def init_extra_db():
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS section_views(day TEXT NOT NULL, section TEXT NOT NULL, user_id INTEGER NOT NULL, n INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(day, section, user_id))")
        c.execute("""CREATE TABLE IF NOT EXISTS mini_users(user_id INTEGER PRIMARY KEY, name TEXT, username TEXT, first_seen TEXT, last_seen TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS mini_banned(user_id INTEGER PRIMARY KEY, reason TEXT, banned_at TEXT, banned_by INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS mini_awards(id INTEGER PRIMARY KEY AUTOINCREMENT, period TEXT, period_key TEXT, rank INTEGER,
            user_id INTEGER, points REAL, tests INTEGER, cert_code TEXT, created_at TEXT, UNIQUE(period, period_key, rank))""")
        c.execute("""CREATE TABLE IF NOT EXISTS mini_certs(code TEXT PRIMARY KEY, user_id INTEGER, kind TEXT, data_json TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS ai_usage(user_id INTEGER, day TEXT, n INTEGER DEFAULT 0, PRIMARY KEY(user_id, day))""")
        c.execute("""CREATE TABLE IF NOT EXISTS essay_usage(user_id INTEGER, day TEXT, n INTEGER DEFAULT 0, PRIMARY KEY(user_id, day))""")
        c.execute("""CREATE TABLE IF NOT EXISTS ai_credits(user_id INTEGER, kind TEXT, balance INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id, kind))""")
        c.execute("""CREATE TABLE IF NOT EXISTS star_payments(charge_id TEXT PRIMARY KEY, user_id INTEGER, kind TEXT, stars INTEGER, credits INTEGER, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS quiz_items(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, question TEXT, kind TEXT, options_json TEXT,
            correct TEXT, answers_json TEXT, points INTEGER DEFAULT 1, explanation TEXT, created_by INTEGER, created_at TEXT, published INTEGER DEFAULT 1)""")
        c.execute("""CREATE TABLE IF NOT EXISTS quiz_attempts(id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER, user_id INTEGER, answer TEXT, is_correct INTEGER,
            points REAL, created_at TEXT, UNIQUE(item_id, user_id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS reminders(user_id INTEGER PRIMARY KEY, last_sent TEXT, optout INTEGER NOT NULL DEFAULT 0)""")
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
    """Faqat admin kiritgan (rasmiy) testlar va savollar; har biriga faqat birinchi urinish hisoblanadi."""
    if start is None: start, end = period_bounds(kind)[:2]
    q1 = """SELECT a.user_id, SUM(a.raw_score) AS pts, COUNT(*) AS n, MIN(a.created_at) AS first
           FROM national_attempts a JOIN national_tests t ON t.id=a.test_id AND t.created_by=? AND t.published=1
           WHERE a.id IN (SELECT MIN(id) FROM national_attempts GROUP BY user_id, test_id)
             AND a.created_at>=? AND a.created_at<? AND a.user_id<>?
             AND a.user_id NOT IN (SELECT user_id FROM mini_banned)
           GROUP BY a.user_id"""
    q2 = """SELECT a.user_id, SUM(a.points) AS pts, COUNT(*) AS n, MIN(a.created_at) AS first
           FROM quiz_attempts a JOIN quiz_items i ON i.id=a.item_id AND i.created_by=? AND i.published=1
           WHERE a.created_at>=? AND a.created_at<? AND a.user_id<>?
             AND a.user_id NOT IN (SELECT user_id FROM mini_banned)
           GROUP BY a.user_id"""
    agg = {}
    with db() as c:
        for q in (q1, q2):
            for r in c.execute(q, (admin_id, start, end, admin_id)):
                a = agg.setdefault(r["user_id"], {"user_id": r["user_id"], "pts": 0.0, "n": 0, "first": r["first"]})
                a["pts"] += float(r["pts"] or 0); a["n"] += r["n"]; a["first"] = min(a["first"], r["first"])
    rows = sorted(agg.values(), key=lambda x: (-x["pts"], -x["n"], x["first"]))
    for i, r in enumerate(rows, 1): r["rank"] = i; r["pts"] = round(r["pts"], 1)
    return rows

def rating_payload(kind, uid, admin_id):
    s, e, key, name = period_bounds(kind)
    rows = leaderboard(kind, admin_id, start=s, end=e)
    top = [{"rank": r["rank"], "name": user_name(r["user_id"]), "pts": r["pts"], "n": r["n"], "me": r["user_id"] == uid} for r in rows[:20]]
    me = next(({"rank": r["rank"], "pts": r["pts"], "n": r["n"]} for r in rows if r["user_id"] == uid), None)
    return {"period": kind, "label": PERIOD_NAMES[kind], "range": name, "top": top, "me": me, "total": len(rows), "prize_days": PRIZE_DAYS.get(kind, 0)}

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
        if len(_png_cache) >= 6: _png_cache.pop(next(iter(_png_cache)))
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

def send_document(token, chat_id, filename, data, caption=""):
    """Telegram'ga fayl yuboradi (baza zaxirasi uchun)."""
    b = uuid.uuid4().hex; parts = []
    for k, v in (("chat_id", str(chat_id)), ("caption", caption[:900])):
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendDocument", data=b"".join(parts), headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())

def send_document_file(token, chat_id, filename, path, caption=""):
    """Faylni Telegram'ga BO'LAKLAB yuboradi: butun fayl RAM'ga o'qilmaydi (baza zaxirasi uchun)."""
    import http.client
    b = uuid.uuid4().hex
    head = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                    for k, v in (("chat_id", str(chat_id)), ("caption", caption[:900])))
    head += f'--{b}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
    tail = f"\r\n--{b}--\r\n".encode()
    total = len(head) + os.path.getsize(path) + len(tail)
    conn = http.client.HTTPSConnection("api.telegram.org", timeout=120)
    try:
        conn.putrequest("POST", f"/bot{token}/sendDocument")
        conn.putheader("Content-Type", f"multipart/form-data; boundary={b}")
        conn.putheader("Content-Length", str(total))
        conn.endheaders(); conn.send(head)
        with open(path, "rb") as f:
            while True:
                chunk = f.read(262144)
                if not chunk: break
                conn.send(chunk)
        conn.send(tail)
        return json.loads(conn.getresponse().read().decode())
    finally:
        conn.close()

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

def award_loop(token, admin_id, log=print, on_award=None):
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
                    if on_award:
                        try: on_award(a)
                        except Exception as e: log(f"award hook error {a['user_id']}: {e}")
            except Exception as e: log(f"award loop error: {e}")
            time.sleep(600)
    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------- Eslatma: "bepul tekshiruvlaringiz yangilandi"
def reminder_candidates(free_essay, free_tool, limit=None):
    """Kecha bepul limitini tugatgan, bugun hali foydalanmagan, o'chirib qo'ymagan va yaqinda eslatma olmagan foydalanuvchilar."""
    limit = limit or REMIND_MAX_PER_DAY
    t = datetime.now(TZ)
    yday = (t - timedelta(days=1)).strftime("%Y-%m-%d"); today = t.strftime("%Y-%m-%d")
    since = (datetime.utcnow() - timedelta(days=REMIND_EVERY_DAYS)).isoformat(timespec="seconds") + "Z"
    with db() as c:
        rows = c.execute("""SELECT DISTINCT u.user_id FROM (
                SELECT user_id FROM essay_usage WHERE day=? AND n>=?
                UNION SELECT user_id FROM ai_usage WHERE day=? AND n>=?) u
            LEFT JOIN reminders r ON r.user_id=u.user_id
            WHERE COALESCE(r.optout,0)=0 AND (r.last_sent IS NULL OR r.last_sent<?)
              AND u.user_id NOT IN (SELECT user_id FROM essay_usage WHERE day=? AND n>0)
              AND u.user_id NOT IN (SELECT user_id FROM ai_usage WHERE day=? AND n>0)
            LIMIT ?""", (yday, max(1, int(free_essay)), yday, max(1, int(free_tool)), since, today, today, int(limit))).fetchall()
    return [int(r[0]) for r in rows if not is_banned(int(r[0]))]

def reminder_mark(uid, optout=None):
    with db() as c:
        c.execute("INSERT OR IGNORE INTO reminders(user_id,last_sent,optout) VALUES(?,NULL,0)", (int(uid),))
        if optout is None:
            c.execute("UPDATE reminders SET last_sent=? WHERE user_id=?", (datetime.utcnow().isoformat(timespec="seconds") + "Z", int(uid)))
        else:
            c.execute("UPDATE reminders SET optout=? WHERE user_id=?", (1 if optout else 0, int(uid)))
        c.commit()

def reminder_optout(uid):
    with db() as c:
        r = c.execute("SELECT optout FROM reminders WHERE user_id=?", (int(uid),)).fetchone()
    return bool(r and r[0])

# ---------------------------------------------------------------- Savollar (kunlik savol / topshiriq)
import re as _re
def norm_answer(x):
    x = str(x).lower()
    for ch in "ʻʼ’‘`´": x = x.replace(ch, "'")
    x = _re.sub(r"[^\w']+", " ", x, flags=_re.U)
    return _re.sub(r"\s+", " ", x).strip()

def quiz_create(uid, d):
    kind = d.get("kind")
    title = str(d.get("title", "")).strip()[:100]; question = str(d.get("question", "")).strip()[:2000]
    if kind not in ("closed", "open") or not title or not question: return None, "Sarlavha, savol va turini kiriting."
    points = max(1, min(5, int(d.get("points", 1) or 1))); expl = str(d.get("explanation", "")).strip()[:600]
    options, correct, answers = [], "", []
    if kind == "closed":
        options = [str(o).strip()[:200] for o in (d.get("options") or []) if str(o).strip()][:6]
        correct = str(d.get("correct", "")).strip().upper()
        if len(options) < 2: return None, "Kamida 2 ta variant kiriting."
        if correct not in "ABCDEF"[:len(options)] or not correct: return None, "To‘g‘ri variantni belgilang."
    else:
        answers = [str(a).strip()[:200] for a in (d.get("answers") or []) if str(a).strip()][:10]
        if not answers: return None, "To‘g‘ri javob(lar)ni kiriting."
    with db() as c:
        cur = c.execute("INSERT INTO quiz_items(title,question,kind,options_json,correct,answers_json,points,explanation,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (title, question, kind, json.dumps(options, ensure_ascii=False), correct, json.dumps(answers, ensure_ascii=False), points, expl, uid, now())); c.commit()
        return cur.lastrowid, None

def quiz_list(uid, is_admin=False):
    with db() as c:
        items = [dict(r) for r in c.execute("SELECT * FROM quiz_items WHERE published=1 ORDER BY id DESC LIMIT 100")]
        mine = {r["item_id"]: dict(r) for r in c.execute("SELECT * FROM quiz_attempts WHERE user_id=?", (uid or 0,))}
    out = []
    for it in items:
        o = {"id": it["id"], "title": it["title"], "question": it["question"], "kind": it["kind"], "options": json.loads(it["options_json"] or "[]"), "points": it["points"], "created_at": it["created_at"]}
        a = mine.get(it["id"])
        if a:
            o["my"] = {"answer": a["answer"], "correct": bool(a["is_correct"]), "points": a["points"]}
        if a or is_admin:
            o["right"] = it["correct"] if it["kind"] == "closed" else " / ".join(json.loads(it["answers_json"] or "[]"))
            o["explanation"] = it["explanation"] or ""
        out.append(o)
    return out

def quiz_answer(uid, item_id, answer):
    with db() as c:
        it = c.execute("SELECT * FROM quiz_items WHERE id=? AND published=1", (item_id,)).fetchone()
        if not it: return None, "Savol topilmadi."
        if c.execute("SELECT 1 FROM quiz_attempts WHERE item_id=? AND user_id=?", (item_id, uid)).fetchone(): return None, "Bu savolga allaqachon javob bergansiz."
        answer = str(answer).strip()[:300]
        if not answer: return None, "Javobni kiriting."
        if it["kind"] == "closed": ok = answer.strip().upper() == it["correct"]
        else: ok = norm_answer(answer) in {norm_answer(a) for a in json.loads(it["answers_json"] or "[]")}
        pts = float(it["points"]) if ok else 0.0
        try:
            c.execute("INSERT INTO quiz_attempts(item_id,user_id,answer,is_correct,points,created_at) VALUES(?,?,?,?,?,?)", (item_id, uid, answer, int(ok), pts, now())); c.commit()
        except Exception:
            return None, "Bu savolga allaqachon javob bergansiz."
        right = it["correct"] if it["kind"] == "closed" else " / ".join(json.loads(it["answers_json"] or "[]"))
    return {"correct": ok, "points": pts, "right": right, "explanation": it["explanation"] or ""}, None

def quiz_delete(item_id):
    with db() as c: c.execute("UPDATE quiz_items SET published=0 WHERE id=?", (int(item_id),)); c.commit()


# ---------------------------------------------------------------- AI limit (kunlik)
def ai_day(): return datetime.now(TZ).strftime("%Y-%m-%d")
def ai_used(uid):
    with db() as c:
        r = c.execute("SELECT n FROM ai_usage WHERE user_id=? AND day=?", (uid, ai_day())).fetchone()
    return int(r[0]) if r else 0
def ai_consume(uid, limit):
    """Kunlik limit ichida bo'lsa 1 ta ishlatadi va True qaytaradi."""
    with db() as c:
        c.execute("INSERT OR IGNORE INTO ai_usage(user_id,day,n) VALUES(?,?,0)", (uid, ai_day()))
        cur = c.execute("UPDATE ai_usage SET n=n+1 WHERE user_id=? AND day=? AND n<?", (uid, ai_day(), int(limit))); c.commit()
        return cur.rowcount == 1
def ai_refund(uid):
    with db() as c: c.execute("UPDATE ai_usage SET n=MAX(0,n-1) WHERE user_id=? AND day=?", (uid, ai_day())); c.commit()


# ---------------------------------------------------------------- Kvota: kunlik bepul + sotib olingan paketlar
# kind: 'essay' (botda esse tekshirish) | 'tool' (esse mashqi va dalil topish; Mini App va bot)
def _usage_table(kind): return "ai_usage" if kind == "tool" else "essay_usage"

def quota_status(uid, kind, free_limit):
    """{'used', 'free_left', 'credits'} — bepul limitdan qancha qolgani va pullik esselar soni."""
    uid = int(uid)
    with db() as c:
        r = c.execute(f"SELECT n FROM {_usage_table(kind)} WHERE user_id=? AND day=?", (uid, ai_day())).fetchone()
        b = c.execute("SELECT balance FROM ai_credits WHERE user_id=? AND kind=?", (uid, kind)).fetchone()
    used = int(r[0]) if r else 0
    return {"used": used, "free_left": max(0, int(free_limit) - used), "credits": int(b[0]) if b else 0}

class Src(str):
    """'free' | 'paid' (oddiy satr kabi solishtiriladi) + yechilgan KUN: yarim tunda qaytarish ham o'sha kunga tushadi."""
    day = None


def quota_consume(uid, kind, free_limit):
    """Avval kunlik bepul limitdan, u tugasa pullik paketdan 1 ta yechadi.
    'free' | 'paid' qaytaradi; hech biri qolmagan bo'lsa None."""
    uid = int(uid); tbl = _usage_table(kind); day = ai_day()
    with db() as c:
        c.execute(f"INSERT OR IGNORE INTO {tbl}(user_id,day,n) VALUES(?,?,0)", (uid, day))
        cur = c.execute(f"UPDATE {tbl} SET n=n+1 WHERE user_id=? AND day=? AND n<?", (uid, day, int(free_limit)))
        if cur.rowcount == 1:
            c.commit(); r = Src("free"); r.day = day; return r
        cur = c.execute("UPDATE ai_credits SET balance=balance-1 WHERE user_id=? AND kind=? AND balance>0", (uid, kind))
        c.commit()
        if cur.rowcount == 1:
            r = Src("paid"); r.day = day; return r
        return None

def quota_refund(uid, kind, source):
    """Tekshiruv muvaffaqiyatsiz bo'lsa, yechilgan birlikni o'sha manbaga (va o'sha kunga) qaytaradi."""
    uid = int(uid)
    with db() as c:
        if source == "free":
            c.execute(f"UPDATE {_usage_table(kind)} SET n=MAX(0,n-1) WHERE user_id=? AND day=?", (uid, getattr(source, 'day', None) or ai_day()))
        elif source == "paid":
            c.execute("INSERT INTO ai_credits(user_id,kind,balance) VALUES(?,?,1) ON CONFLICT(user_id,kind) DO UPDATE SET balance=balance+1", (uid, kind))
        c.commit()

def claim_charge(charge_id, uid, kind, stars, credits=0):
    """To'lovni (charge_id) bir marta 'band qiladi'. True: yangi; False: avval hisobga olingan."""
    with db() as c:
        try:
            c.execute("INSERT INTO star_payments(charge_id,user_id,kind,stars,credits,created_at) VALUES(?,?,?,?,?,?)",
                      (str(charge_id), int(uid), kind, int(stars), int(credits), now()))
        except sqlite3.IntegrityError:
            return False
        c.commit()
    return True

def release_charge(charge_id):
    with db() as c:
        c.execute("DELETE FROM star_payments WHERE charge_id=?", (str(charge_id),)); c.commit()

def grant_pack(uid, kind, charge_id, stars, credits):
    """To'lov muvaffaqiyatli bo'lganda paket beradi. Bir xil charge_id ikkinchi marta hisoblanmaydi.
    True: yangi berildi; False: avval berilgan."""
    uid = int(uid)
    with db() as c:
        try:
            c.execute("INSERT INTO star_payments(charge_id,user_id,kind,stars,credits,created_at) VALUES(?,?,?,?,?,?)",
                      (str(charge_id), uid, kind, int(stars), int(credits), now()))
        except sqlite3.IntegrityError:
            return False
        c.execute("INSERT INTO ai_credits(user_id,kind,balance) VALUES(?,?,?) ON CONFLICT(user_id,kind) DO UPDATE SET balance=balance+excluded.balance",
                  (uid, kind, int(credits)))
        c.commit()
    return True


# ---------------------------------------------------------------- Doimiy natija keshi (alohida fayl: zaxira nusxaga kirmaydi)
CACHE_DB_PATH = os.getenv("CACHE_DB_PATH") or os.path.join(
    os.path.dirname(os.path.abspath(os.getenv("BOT_DB_PATH", "esse_bot.sqlite3"))), "esse_cache.sqlite3")
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "45"))
CACHE_MAX_ROWS = int(os.getenv("CACHE_MAX_ROWS", "5000"))
_cache_writes = 0

def _cdb():
    return sqlite3.connect(CACHE_DB_PATH, timeout=30, check_same_thread=False)

def cache_init():
    with closing(_cdb()) as c:
        c.execute("CREATE TABLE IF NOT EXISTS result_cache(k TEXT PRIMARY KEY, v TEXT NOT NULL, created_at REAL NOT NULL)")
        c.execute("DELETE FROM result_cache WHERE created_at < ?", (time.time() - CACHE_TTL_DAYS * 86400,))
        c.commit()

def cache_load(k):
    with closing(_cdb()) as c:
        r = c.execute("SELECT v FROM result_cache WHERE k=?", (k,)).fetchone()
    return r[0] if r else None

def cache_store(k, v):
    global _cache_writes
    with closing(_cdb()) as c:
        c.execute("INSERT OR REPLACE INTO result_cache(k,v,created_at) VALUES(?,?,?)", (k, v, time.time()))
        _cache_writes += 1
        if _cache_writes % 100 == 0:
            c.execute("DELETE FROM result_cache WHERE k NOT IN (SELECT k FROM result_cache ORDER BY created_at DESC LIMIT ?)", (CACHE_MAX_ROWS,))
        c.commit()


# ---------------------------------------------------------------- ko'rishlar statistikasi
_VIEW_RE = re.compile(r"^(?:[a-zA-Z]{2,24}|book:\d{1,6})$")

def record_view(uid, section):
    """Bo'lim/asar ko'rilganini yozadi (kuniga bir foydalanuvchi uchun bitta qator: ko'rishlar soni oshadi)."""
    section = str(section or "").strip()
    if not _VIEW_RE.match(section): return False
    with db() as c:
        c.execute("INSERT INTO section_views(day,section,user_id,n) VALUES(?,?,?,1) ON CONFLICT(day,section,user_id) DO UPDATE SET n=n+1",
                  (ai_day(), section, int(uid)))
        c.commit()
    return True

def view_stats(days=None):
    """[(section, ko'rishlar, noyob_foydalanuvchilar)] — ko'rishlar bo'yicha kamayish tartibida. days=None — butun davr."""
    q = "SELECT section, SUM(n) v, COUNT(DISTINCT user_id) u FROM section_views"
    args = ()
    if days:
        since = (datetime.now(TZ) - timedelta(days=int(days) - 1)).strftime("%Y-%m-%d"); q += " WHERE day>=?"; args = (since,)
    q += " GROUP BY section ORDER BY v DESC"
    with db() as c: return [(r[0], int(r[1]), int(r[2])) for r in c.execute(q, args).fetchall()]

def view_totals(days=None):
    """(jami ko'rishlar, noyob foydalanuvchilar) — hamma bo'limlar bo'yicha."""
    q = "SELECT COALESCE(SUM(n),0), COUNT(DISTINCT user_id) FROM section_views"; args = ()
    if days:
        since = (datetime.now(TZ) - timedelta(days=int(days) - 1)).strftime("%Y-%m-%d"); q += " WHERE day>=?"; args = (since,)
    with db() as c: r = c.execute(q, args).fetchone()
    return int(r[0]), int(r[1])


# ---------------------------------------------------------------- 🎮 O'yinlar: «Ona tilini o'ynab o'rganamiz» (v41)
# O'yinlar telefonning o'zida ishlaydi (AI yo'q). Serverda faqat natija saqlanadi: ball, kunlik seriya, haftalik o'yin reytingi.
# Ball mijoz tomonidan yuboriladi (tekshirib bo'lmaydi), shuning uchun reyting alohida va sovrinsiz; kunlik chegara qo'yilgan.
GAME_MAX_Q = {"imlo": 10, "sinonim": 10, "paronim": 10, "omonim": 10, "mistakes": 15, "daily": 5, "dtm": 20, "topic": 15, "duel": 5}
GAME_DAILY_CAP = 150       # bir kunda o'yindan olinadigan maksimal ball
GAME_DAILY_BONUS = 3       # kunlik 5 savolni tugatganlik uchun
_games_ready = False

def _games_init():
    global _games_ready
    if _games_ready: return
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS game_plays(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, game TEXT, day TEXT, correct INTEGER, total INTEGER, points INTEGER, created_at TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_gp_user_day ON game_plays(user_id, day)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_gp_created ON game_plays(created_at)")
        c.commit()
    _games_ready = True

def _game_today():
    return datetime.now(TZ).strftime("%Y-%m-%d")

def _game_streak(uid):
    """(joriy seriya, eng yaxshi seriya, bugun kunlik savollar bajarilganmi). Seriya = ketma-ket kunlarda «Kunlik 5 savol» bajarilgan.
    v44: taklif qilingan har bir do'st (maks. 10) 1 ta ❄️ seriya himoyasi beradi — bir kun o'tkazib yuborilsa avtomatik ishlatiladi."""
    _gref_init()
    with db() as c:
        ds = {datetime.strptime(r[0], "%Y-%m-%d").date() for r in c.execute("SELECT day FROM game_plays WHERE user_id=? AND game='daily'", (uid,))}
        used = {datetime.strptime(r[0], "%Y-%m-%d").date() for r in c.execute("SELECT day FROM game_freeze_used WHERE user_id=?", (uid,))}
    if not ds: return 0, 0, False
    today = datetime.now(TZ).date(); done = today in ds
    left = min(_friends(uid), GAME_FREEZE_MAX) - len(used); cov = ds | used
    d = today if today in cov else today - timedelta(days=1); cur = 0; fresh = []
    while True:
        if d in ds: cur += 1; d -= timedelta(days=1)
        elif d in used or d in fresh: d -= timedelta(days=1)
        elif left > 0 and d < today and (d - timedelta(days=1)) in cov:
            fresh.append(d); cov.add(d); left -= 1; d -= timedelta(days=1)
        else: break
    if fresh:
        with db() as c:
            for x in fresh: c.execute("INSERT OR IGNORE INTO game_freeze_used(user_id,day) VALUES(?,?)", (uid, x.strftime("%Y-%m-%d")))
            c.commit()
    best = run = 0; prev = None
    for x in sorted(cov):
        if prev is not None and (x - prev).days == 1: run += 1 if x in ds else 0
        else: run = 1 if x in ds else 0
        best = max(best, run); prev = x
    return cur, max(best, cur), done

def game_state(uid, admin_id=0):
    _games_init()
    s, e, _key, name = period_bounds("week"); day = _game_today()
    cur, best, done = _game_streak(uid) if uid else (0, 0, False)
    with db() as c:
        rows = c.execute("""SELECT user_id, SUM(points) AS pts FROM game_plays WHERE created_at>=? AND created_at<? AND user_id<>?
                            AND user_id NOT IN (SELECT user_id FROM mini_banned) GROUP BY user_id HAVING SUM(points)>0
                            ORDER BY SUM(points) DESC, MIN(created_at) ASC LIMIT 1000""", (s, e, admin_id)).fetchall()
        daily = c.execute("SELECT correct,total FROM game_plays WHERE user_id=? AND game='daily' AND day=? ORDER BY id LIMIT 1", (uid, day)).fetchone() if uid else None
        today_pts = c.execute("SELECT COALESCE(SUM(points),0) FROM game_plays WHERE user_id=? AND day=?", (uid, day)).fetchone()[0] if uid else 0
    top = [{"rank": i, "name": user_name(r["user_id"]), "pts": int(r["pts"]), "me": r["user_id"] == uid} for i, r in enumerate(rows[:10], 1)]
    me = next(({"rank": i, "pts": int(r["pts"])} for i, r in enumerate(rows, 1) if r["user_id"] == uid), None)
    return {"streak": cur, "best_streak": best, "today_done": done, "daily": ({"correct": daily["correct"], "total": daily["total"]} if daily else None),
            "today_points": int(today_pts), "week": {"range": name, "top": top, "me": me, "players": len(rows)},
            "perks": (game_perks(uid) if uid else None)}

def game_submit(uid, game, correct, total, admin_id=0):
    """(natija, xato). Kunlik 5 savol kuniga bir marta hisoblanadi."""
    _games_init()
    if game not in GAME_MAX_Q: return None, "Noma'lum o‘yin."
    try: correct = int(correct); total = int(total)
    except Exception: return None, "Noto‘g‘ri natija."
    if total < 1 or total > GAME_MAX_Q[game] or correct < 0 or correct > total: return None, "Noto‘g‘ri natija."
    if game == "daily" and total != 5: return None, "Noto‘g‘ri natija."
    day = _game_today()
    with db() as c:
        if game == "daily" and c.execute("SELECT 1 FROM game_plays WHERE user_id=? AND game='daily' AND day=?", (uid, day)).fetchone():
            st = game_state(uid, admin_id); st.update({"already": True, "gained": 0}); return st, None
        used = c.execute("SELECT COALESCE(SUM(points),0) FROM game_plays WHERE user_id=? AND day=?", (uid, day)).fetchone()[0]
        pts = correct + (GAME_DAILY_BONUS if game == "daily" else 0)
        pts = max(0, min(pts, GAME_DAILY_CAP - int(used)))
        c.execute("INSERT INTO game_plays(user_id,game,day,correct,total,points,created_at) VALUES(?,?,?,?,?,?,?)", (uid, game, day, correct, total, pts, now())); c.commit()
    st = game_state(uid, admin_id); st["gained"] = pts; return st, None


# ---------------------------------------------------------------- 🤝 v44: do'st taklifi (o'yin ichidagi mukofotlar, AI xarajatsiz)
# Do'st havola orqali YANGI foydalanuvchi bo'lib kirib, birinchi o'yinini tugatsa — taklif qilgan odam mukofot oladi:
#   har do'st = 1 ta ❄️ seriya himoyasi (maks. 10) • 3 do'st = 🏅 «Elchi» + 100 XP • 5 do'st = 🃏 3 ta 50/50 joker (+ keyingi har do'stga 1 ta)
#   har 10 do'st = +1 bepul esse tekshiruvi (maks. 3 marta)
GAME_FREEZE_MAX = 10
GAME_ESSAY_EVERY = 10
GAME_ESSAY_MAX = 3
_gref_ready = False

def _gref_init():
    global _gref_ready
    if _gref_ready: return
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS game_refs(invitee_id INTEGER PRIMARY KEY, inviter_id INTEGER, seed INTEGER, vs INTEGER, created_at TEXT, played_at TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_gr_inviter ON game_refs(inviter_id)")
        c.execute("CREATE TABLE IF NOT EXISTS game_duels(invitee_id INTEGER, inviter_id INTEGER, seed INTEGER, correct INTEGER, created_at TEXT, PRIMARY KEY(invitee_id,inviter_id,seed))")
        c.execute("CREATE TABLE IF NOT EXISTS game_freeze_used(user_id INTEGER, day TEXT, PRIMARY KEY(user_id,day))")
        c.execute("CREATE TABLE IF NOT EXISTS game_perks_used(user_id INTEGER PRIMARY KEY, jokers_used INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS game_awards(user_id INTEGER, kind TEXT, created_at TEXT, PRIMARY KEY(user_id,kind))")
        c.commit()
    _gref_ready = True

def game_ref_register(invitee, inviter, is_new, seed=0, vs=-1):
    """Faqat yangi foydalanuvchi va o'zini o'zi taklif qilmagan bo'lsa yoziladi."""
    _gref_init(); invitee, inviter = int(invitee), int(inviter)
    if not is_new or invitee == inviter: return False
    with db() as c:
        cur = c.execute("INSERT OR IGNORE INTO game_refs(invitee_id,inviter_id,seed,vs,created_at) VALUES(?,?,?,?,?)", (invitee, inviter, int(seed or 0), int(vs if vs is not None else -1), now()))
        c.commit(); return cur.rowcount == 1

def _friends(uid):
    _gref_init()
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM game_refs WHERE inviter_id=? AND played_at IS NOT NULL AND invitee_id NOT IN (SELECT user_id FROM mini_banned)", (int(uid),)).fetchone()[0]

def _jokers_total(n): return 0 if n < 5 else 3 + (n - 5)

def game_perks(uid):
    _gref_init(); n = _friends(uid)
    with db() as c:
        pending = c.execute("SELECT COUNT(*) FROM game_refs WHERE inviter_id=? AND played_at IS NULL", (uid,)).fetchone()[0]
        fz_used = c.execute("SELECT COUNT(*) FROM game_freeze_used WHERE user_id=?", (uid,)).fetchone()[0]
        jr = c.execute("SELECT jokers_used FROM game_perks_used WHERE user_id=?", (uid,)).fetchone()
    steps = [(1, "❄️ Seriya himoyasi"), (3, "🏅 «Elchi» nishoni +100 XP"), (5, "🃏 3 ta 50/50 joker"), (10, "🎁 +1 bepul esse tekshiruvi")]
    nxt = next(({"need": k, "left": k - n, "reward": t} for k, t in steps if n < k), None)
    if nxt is None:
        k = (n // 10 + 1) * 10; nxt = {"need": k, "left": k - n, "reward": "🎁 +1 bepul esse tekshiruvi" if n // 10 < GAME_ESSAY_MAX else "🃏 yana joker"}
    return {"friends": n, "pending": pending, "freeze_left": max(0, min(n, GAME_FREEZE_MAX) - fz_used), "jokers_left": max(0, _jokers_total(n) - (jr[0] if jr else 0)),
            "elchi": n >= 3, "bonus_xp": 100 if n >= 3 else 0, "next": nxt, "steps": [{"need": k, "title": t, "done": n >= k} for k, t in steps]}

def game_joker_use(uid):
    """50/50 jokerini ishlatadi. (qolgan, xato)"""
    _gref_init(); p = game_perks(uid)
    if p["jokers_left"] <= 0: return None, "Jokeringiz qolmagan. Do‘stlarni taklif qilib joker oling."
    with db() as c:
        c.execute("INSERT INTO game_perks_used(user_id,jokers_used) VALUES(?,1) ON CONFLICT(user_id) DO UPDATE SET jokers_used=jokers_used+1", (uid,)); c.commit()
    return p["jokers_left"] - 1, None

def game_after_submit(uid, game, correct, total, meta=None, credit_fn=None):
    """O'yin natijasi saqlangach chaqiriladi. [(chat_id, matn), ...] — yuboriladigan xabarlar ro'yxatini qaytaradi."""
    _gref_init(); meta = meta or {}; msgs = []
    try: correct = int(correct); total = int(total)
    except Exception: return msgs
    who = user_name(uid)
    # 1) yangi do'st birinchi o'yinini tugatdi -> taklif qilganga mukofot
    if total >= 5:
        with db() as c:
            row = c.execute("SELECT inviter_id FROM game_refs WHERE invitee_id=? AND played_at IS NULL", (uid,)).fetchone()
            if row:
                c.execute("UPDATE game_refs SET played_at=? WHERE invitee_id=? AND played_at IS NULL", (now(), uid)); c.commit()
        if row:
            inv = int(row[0]); n = _friends(inv)
            t = f"🎉 {who} havolangiz orqali o‘yinni boshladi!\n❄️ +1 seriya himoyasi hisobingizda."
            if n == 3: t += "\n🏅 «Elchi» nishoni va +100 XP ochildi!"
            if n == 5: t += "\n🃏 3 ta 50/50 joker oldingiz (DTM sinovida ishlating)."
            if n > 5: t += "\n🃏 +1 joker."
            if n >= GAME_ESSAY_EVERY and n % GAME_ESSAY_EVERY == 0 and n // GAME_ESSAY_EVERY <= GAME_ESSAY_MAX:
                try:
                    with db() as c:
                        cur = c.execute("INSERT OR IGNORE INTO game_awards(user_id,kind,created_at) VALUES(?,?,?)", (inv, f"essay_{n}", now())); c.commit(); first = cur.rowcount == 1
                    if first and credit_fn:
                        credit_fn(inv, "essay", 1); t += "\n🎁 +1 bepul esse tekshiruvi qo‘shildi! (/balans)"
                except Exception: pass
            nx = game_perks(inv)["next"]
            t += f"\n\n👥 Do‘stlaringiz: {n}" + (f" • keyingi mukofotgacha yana {nx['left']} ta: {nx['reward']}" if nx else "")
            msgs.append((inv, t))
    # 2) bellashuv qabul qilindi -> chaqirgan odamga natija
    if game == "duel":
        try:
            frm = int(meta.get("from") or 0); seed = int(meta.get("seed") or 0)
        except Exception: frm = seed = 0
        if frm and frm != uid and 0 < seed < 10**9:
            with db() as c:
                cur = c.execute("INSERT OR IGNORE INTO game_duels(invitee_id,inviter_id,seed,correct,created_at) VALUES(?,?,?,?,?)", (uid, frm, seed, correct, now())); c.commit(); fresh = cur.rowcount == 1
            if fresh:
                try: vs = max(0, min(int(meta.get("vs")), total))
                except Exception: vs = None
                if vs is None: res = f"U {correct}/{total} natija oldi."
                elif correct > vs: res = f"U {correct}/{total} oldi, siz {vs}/{total} — bu safar u oldinda 😅"
                elif correct == vs: res = f"Ikkalangiz ham {vs}/{total} — durang! 🤝"
                else: res = f"Siz {vs}/{total}, u {correct}/{total} — siz yutdingiz! 🏆"
                msgs.append((frm, f"⚔️ {who} bellashuvingizni qabul qildi!\n{res}"))
    return msgs
