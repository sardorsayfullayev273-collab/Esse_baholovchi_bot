# -*- coding: utf-8 -*-
"""v128: «Videodars» — ichki guruhlar uchun.

• Video Render'da SAQLANMAYDI (na disk, na xotira): admin YouTube (ro'yxatda ko'rinmaydigan / unlisted) havolasi yoki
  tashqi saqlagichdagi to'g'ridan-to'g'ri .mp4 havolasini kiritadi. Bazada faqat havola va ma'lumot turadi.
• Kirish: admin guruh ochadi, o'quvchi qo'shadi -> har biriga login/parol beriladi. O'quvchi Mini App'da shu login bilan kiradi
  (Telegram akkaunti loginga bog'lanadi; bitta login ko'pi bilan MAX_DEV ta akkauntda ishlaydi).
• Topshiriq faqat video OXIRIGACHA ko'rilgach ochiladi. Ko'rish SERVERDA tekshiriladi (5 soniyalik bo'laklar, real vaqt bilan
  solishtiriladi) — videoni oldinga o'tkazib yuborib bo'lmaydi.
• Admin ko'radi: kim, qachon (Toshkent vaqti) kirdi, qaysi darsni ochdi, tugatdi, topshiriq topshirdi.
• v135: bo'lim nomi «Ichki guruhlar uchun». Admin o'quvchining login VA parolini ko'radi (pw_plain). «Maxsus topshiriq»:
  videoga bog'liq bo'lmagan yopiq (variantli) va ochiq (matnli) savollar; kim, qachon kirdi, qachon topshirdi, natijasi — hammasi admin ko'rinishida.
Hamma API: POST /api/vd/...   (Telegram imzosi bot-1-1.py da tekshiriladi)."""
import hashlib, hmac, json, logging, math, re, secrets, time
from datetime import datetime, timezone, timedelta
from national_certificate import db, now

log = logging.getLogger(__name__)
UZ = timezone(timedelta(hours=5))
ADMIN_ID = 0
_NOTIFY = None                     # callable(text) — adminga Telegram xabari
MAX_DEV = 2                        # bitta login nechta Telegram akkauntda ishlashi mumkin
BUCKET = 5                         # soniya: ko'rish bo'lagi
LOGIN_MAX_FAILS, LOGIN_MAX_FAILS_ACC, LOCK_MIN = 5, 25, 15
VISIT_GAP_MIN = 30                 # «bo'limni ochdi» yozuvi/xabari orasidagi eng kam vaqt
_ALPHA = 'abcdefghjkmnpqrstuvwxyz23456789'
EVENTS = {'login': '🔑 Login bilan kirdi', 'visit': '👋 Bo‘limni ochdi', 'open': '▶️ Darsni ochdi', 'done': '✅ Videoni oxirigacha ko‘rdi',
          'task': '📝 Topshiriq topshirdi', 'fail': '⛔ Noto‘g‘ri parol kiritdi',
          'topen': '📂 Maxsus topshiriqni ochdi', 'tsub': '⭐ Maxsus topshiriqni topshirdi'}
_LAST_OPEN = {}
_LAST_SUB = {}


class ApiErr(Exception):
    def __init__(self, status, msg): super().__init__(msg); self.status = status; self.msg = msg


def configure(admin_id, notify=None):
    global ADMIN_ID, _NOTIFY
    ADMIN_ID = int(admin_id or 0); _NOTIFY = notify


def _now(): return datetime.now(timezone.utc)
def _iso(dt=None): return (dt or _now()).replace(microsecond=0).isoformat()


def fmt(s):
    """UTC ISO -> «14.11.2026 15:42» (Toshkent vaqti)."""
    try:
        d = datetime.fromisoformat(str(s)[:25])
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(UZ).strftime('%d.%m.%Y %H:%M')
    except Exception: return ''


def _rows(c, sql, p=()): return [dict(r) for r in c.execute(sql, p).fetchall()]
def _row(c, sql, p=()):
    r = c.execute(sql, p).fetchone(); return dict(r) if r else None
def _clean(s, n): return ' '.join(str(s or '').split())[:n]


def _tell(text):
    if _NOTIFY is None: return
    try: _NOTIFY(text)
    except Exception: log.exception('videodars: admin xabari yuborilmadi')


def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS vd_group(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS vd_student(id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, full_name TEXT NOT NULL,
            login TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, pw_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, last_login_at TEXT, last_seen_at TEXT);
        CREATE TABLE IF NOT EXISTS vd_dev(tg_uid INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, bound_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS vd_lesson(id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, title TEXT NOT NULL,
            descr TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL, src TEXT NOT NULL, duration_sec INTEGER NOT NULL DEFAULT 0,
            min_pct INTEGER NOT NULL DEFAULT 90, task_json TEXT NOT NULL DEFAULT '{}', published INTEGER NOT NULL DEFAULT 1,
            pos INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS vd_prog(student_id INTEGER NOT NULL, lesson_id INTEGER NOT NULL, cover TEXT NOT NULL DEFAULT '',
            last_pos REAL NOT NULL DEFAULT 0, last_hb REAL NOT NULL DEFAULT 0, started_at TEXT, updated_at TEXT, completed_at TEXT,
            PRIMARY KEY(student_id, lesson_id));
        CREATE TABLE IF NOT EXISTS vd_sub(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, lesson_id INTEGER NOT NULL,
            kind TEXT NOT NULL, answers_json TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '', score INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0, passed INTEGER NOT NULL DEFAULT 0, comment TEXT NOT NULL DEFAULT '', reviewed_at TEXT,
            at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS vd_sub_i ON vd_sub(lesson_id, student_id);
        CREATE TABLE IF NOT EXISTS vd_log(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER, name TEXT NOT NULL, grp TEXT NOT NULL DEFAULT '',
            event TEXT NOT NULL, lesson_id INTEGER, lesson TEXT NOT NULL DEFAULT '', at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS vd_log_i ON vd_log(id DESC);
        CREATE TABLE IF NOT EXISTS vd_fail(k TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0, until TEXT);
        CREATE TABLE IF NOT EXISTS vd_kv(k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE IF NOT EXISTS vd_task(id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, title TEXT NOT NULL,
            descr TEXT NOT NULL DEFAULT '', items_json TEXT NOT NULL DEFAULT '[]', pass_pct INTEGER NOT NULL DEFAULT 60,
            max_attempts INTEGER NOT NULL DEFAULT 1, published INTEGER NOT NULL DEFAULT 1, pos INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS vd_tprog(student_id INTEGER NOT NULL, task_id INTEGER NOT NULL, first_open_at TEXT, last_open_at TEXT,
            attempt_start_at TEXT, opens INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(student_id, task_id));
        CREATE TABLE IF NOT EXISTS vd_tsub(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER NOT NULL, task_id INTEGER NOT NULL,
            answers_json TEXT NOT NULL DEFAULT '[]', score INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
            open_n INTEGER NOT NULL DEFAULT 0, passed INTEGER NOT NULL DEFAULT 0, comment TEXT NOT NULL DEFAULT '', reviewed_at TEXT,
            started_at TEXT, at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS vd_tsub_i ON vd_tsub(task_id, student_id);
        ''')
        # v135: parolni admin ko'rishi uchun (eski bazada ustun yo'q bo'lsa qo'shiladi; eski o'quvchilarda bo'sh qoladi)
        if 'pw_plain' not in [r[1] for r in c.execute('PRAGMA table_info(vd_student)').fetchall()]:
            c.execute("ALTER TABLE vd_student ADD COLUMN pw_plain TEXT NOT NULL DEFAULT ''")


def _kv_get(k, default=''):
    with db() as c:
        r = c.execute('SELECT v FROM vd_kv WHERE k=?', (k,)).fetchone()
    return r[0] if r else default


def _kv_set(k, v):
    with db() as c: c.execute('INSERT INTO vd_kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v', (k, str(v)))


def notify_enabled(): return _kv_get('notify', '1') != '0'


# ------------------------------------------------------------------ guruhlar
def groups(c=None):
    sql = '''SELECT g.id, g.name,
        (SELECT COUNT(*) FROM vd_student s WHERE s.group_id=g.id) AS students,
        (SELECT COUNT(*) FROM vd_lesson l WHERE l.group_id=g.id) AS lessons FROM vd_group g ORDER BY g.name COLLATE NOCASE'''
    if c is not None: return _rows(c, sql)
    with db() as c2: return _rows(c2, sql)


def group_add(name):
    name = _clean(name, 50)
    if len(name) < 2: raise ApiErr(400, 'Guruh nomini kiriting.')
    with db() as c:
        if c.execute('SELECT 1 FROM vd_group WHERE name=? COLLATE NOCASE', (name,)).fetchone(): raise ApiErr(400, 'Bunday guruh bor.')
        return c.execute('INSERT INTO vd_group(name,created_at) VALUES(?,?)', (name, _iso())).lastrowid


def group_rename(gid, name):
    name = _clean(name, 50)
    if len(name) < 2: raise ApiErr(400, 'Guruh nomini kiriting.')
    with db() as c:
        if c.execute('SELECT 1 FROM vd_group WHERE name=? COLLATE NOCASE AND id<>?', (name, int(gid))).fetchone(): raise ApiErr(400, 'Bunday guruh bor.')
        c.execute('UPDATE vd_group SET name=? WHERE id=?', (name, int(gid)))


def group_del(gid):
    with db() as c:
        g = _row(c, 'SELECT id FROM vd_group WHERE id=?', (int(gid),))
        if not g: raise ApiErr(404, 'Guruh topilmadi.')
        if c.execute('SELECT 1 FROM vd_student WHERE group_id=?', (int(gid),)).fetchone() or c.execute('SELECT 1 FROM vd_lesson WHERE group_id=?', (int(gid),)).fetchone() \
                or c.execute('SELECT 1 FROM vd_task WHERE group_id=?', (int(gid),)).fetchone():
            raise ApiErr(400, 'Guruhda o‘quvchi, dars yoki maxsus topshiriq bor. Avval ularni o‘chiring yoki boshqa guruhga ko‘chiring.')
        c.execute('DELETE FROM vd_group WHERE id=?', (int(gid),))


def _gname(c, gid):
    r = c.execute('SELECT name FROM vd_group WHERE id=?', (int(gid),)).fetchone()
    return r[0] if r else ''


# ------------------------------------------------------------------ o'quvchi hisoblari
def _hash(pw, salt): return hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), bytes.fromhex(salt), 60000).hex()
def _new_pw(): return ''.join(secrets.choice(_ALPHA) for _ in range(6))


def _norm_login(s): return re.sub(r'[^a-z0-9._-]', '', str(s or '').strip().lower())[:30]


def _free_login(c):
    for _ in range(80):
        lg = 'vd' + ''.join(secrets.choice('0123456789') for _ in range(5))
        if not c.execute('SELECT 1 FROM vd_student WHERE login=?', (lg,)).fetchone(): return lg
    raise ApiErr(500, 'Login yaratib bo‘lmadi.')


def students_add(gid, text):
    """Har qator — bitta o'quvchi ismi. -> [{id, name, login, password}] (parol FAQAT shu yerda ochiq)."""
    names = [_clean(x, 60) for x in re.split(r'[\n;]+', str(text or ''))]
    names = [n for n in names if len(n) >= 2][:100]
    if not names: raise ApiErr(400, 'Kamida bitta ism kiriting (har qatorda bittadan).')
    out = []
    with db() as c:
        if not c.execute('SELECT 1 FROM vd_group WHERE id=?', (int(gid or 0),)).fetchone(): raise ApiErr(400, 'Guruhni tanlang.')
        for n in names:
            lg, pw, salt = _free_login(c), _new_pw(), secrets.token_hex(8)
            sid = c.execute('INSERT INTO vd_student(group_id,full_name,login,salt,pw_hash,pw_plain,created_at) VALUES(?,?,?,?,?,?,?)',
                            (int(gid), n, lg, salt, _hash(pw, salt), pw, _iso())).lastrowid
            out.append({'id': sid, 'name': n, 'login': lg, 'password': pw})
    return out


def student_reset(sid):
    pw, salt = _new_pw(), secrets.token_hex(8)
    with db() as c:
        s = _row(c, 'SELECT id, login, full_name FROM vd_student WHERE id=?', (int(sid),))
        if not s: raise ApiErr(404, 'O‘quvchi topilmadi.')
        c.execute('UPDATE vd_student SET salt=?, pw_hash=?, pw_plain=? WHERE id=?', (salt, _hash(pw, salt), pw, s['id']))
        c.execute('DELETE FROM vd_dev WHERE student_id=?', (s['id'],))
        c.execute('DELETE FROM vd_fail WHERE k=?', ('acc:' + s['login'],))
    return {'id': s['id'], 'name': s['full_name'], 'login': s['login'], 'password': pw}


def student_setpw(sid, pw):
    """Admin parolni o'zi belgilaydi (kamida 4 belgi)."""
    pw = str(pw or '').strip()[:40]
    if len(pw) < 4: raise ApiErr(400, 'Parol kamida 4 belgi bo‘lsin.')
    salt = secrets.token_hex(8)
    with db() as c:
        s = _row(c, 'SELECT id, login, full_name FROM vd_student WHERE id=?', (int(sid),))
        if not s: raise ApiErr(404, 'O‘quvchi topilmadi.')
        c.execute('UPDATE vd_student SET salt=?, pw_hash=?, pw_plain=? WHERE id=?', (salt, _hash(pw, salt), pw, s['id']))
        c.execute('DELETE FROM vd_dev WHERE student_id=?', (s['id'],))
        c.execute('DELETE FROM vd_fail WHERE k=?', ('acc:' + s['login'],))
    return {'id': s['id'], 'name': s['full_name'], 'login': s['login'], 'password': pw}


def student_edit(sid, name=None, gid=None, active=None, login=None):
    sets, vals = [], []
    with db() as c:
        s = _row(c, 'SELECT * FROM vd_student WHERE id=?', (int(sid),))
        if not s: raise ApiErr(404, 'O‘quvchi topilmadi.')
        if name is not None:
            n = _clean(name, 60)
            if len(n) < 2: raise ApiErr(400, 'Ismni kiriting.')
            sets.append('full_name=?'); vals.append(n)
        if gid is not None:
            if not c.execute('SELECT 1 FROM vd_group WHERE id=?', (int(gid),)).fetchone(): raise ApiErr(400, 'Guruh topilmadi.')
            sets.append('group_id=?'); vals.append(int(gid))
        if active is not None: sets.append('active=?'); vals.append(1 if active else 0)
        if login is not None:
            lg = _norm_login(login)
            if len(lg) < 3: raise ApiErr(400, 'Login kamida 3 belgi (lotin harf, raqam, . _ -).')
            if c.execute('SELECT 1 FROM vd_student WHERE login=? AND id<>?', (lg, s['id'])).fetchone(): raise ApiErr(400, 'Bu login band.')
            sets.append('login=?'); vals.append(lg)
        if sets: c.execute('UPDATE vd_student SET ' + ','.join(sets) + ' WHERE id=?', vals + [s['id']])
        if active is not None and not active: c.execute('DELETE FROM vd_dev WHERE student_id=?', (s['id'],))


def student_del(sid):
    with db() as c:
        for t in ('vd_dev', 'vd_prog', 'vd_sub', 'vd_tprog', 'vd_tsub'): c.execute('DELETE FROM %s WHERE student_id=?' % t, (int(sid),))
        c.execute('DELETE FROM vd_student WHERE id=?', (int(sid),))


def students_list(gid=None):
    with db() as c:
        rows = _rows(c, '''SELECT s.id, s.group_id, s.full_name, s.login, s.pw_plain AS password, s.active, s.created_at, s.last_login_at, s.last_seen_at,
            (SELECT COUNT(*) FROM vd_dev d WHERE d.student_id=s.id) AS devices,
            (SELECT COUNT(*) FROM vd_prog p WHERE p.student_id=s.id AND p.completed_at IS NOT NULL) AS done
            FROM vd_student s ''' + ('WHERE s.group_id=? ' if gid else '') + 'ORDER BY s.full_name COLLATE NOCASE', (int(gid),) if gid else ())
    for r in rows:
        r['active'] = bool(r['active']); r['last_login'] = fmt(r.pop('last_login_at')); r['last_seen'] = fmt(r.pop('last_seen_at')); r.pop('created_at', None)
    return rows


def student_of(uid):
    if uid is None: return None
    with db() as c:
        return _row(c, '''SELECT s.id, s.group_id, s.full_name, s.login FROM vd_dev d JOIN vd_student s ON s.id=d.student_id
                          WHERE d.tg_uid=? AND s.active=1''', (int(uid),))


def _fail_get(c, k):
    r = c.execute('SELECT n, until FROM vd_fail WHERE k=?', (k,)).fetchone()
    return (r[0], r[1]) if r else (0, None)


def login(tg_uid, lg, pw):
    lg = _norm_login(lg); pw = str(pw or '').strip()[:60]
    if not lg or not pw: raise ApiErr(400, 'Login va parolni kiriting.')
    keys = ['acc:' + lg, 'tg:%s' % int(tg_uid)]; nowi = _iso()
    with db() as c:
        for k in keys:
            n, until = _fail_get(c, k)
            if until and until > nowi: raise ApiErr(429, 'Ko‘p marta xato kiritildi. %d daqiqadan keyin urinib ko‘ring.' % LOCK_MIN)
        s = _row(c, 'SELECT * FROM vd_student WHERE login=?', (lg,))
        ok = bool(s) and hmac.compare_digest(_hash(pw, s['salt']), s['pw_hash'])
        if not s: _hash(pw, '00' * 8)
        if not ok:
            for k in keys:
                n, until = _fail_get(c, k); n = (n if not until or until <= nowi else 0) + 1
                lock = n >= (LOGIN_MAX_FAILS if k.startswith('tg:') else LOGIN_MAX_FAILS_ACC)
                c.execute('INSERT INTO vd_fail(k,n,until) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET n=excluded.n, until=excluded.until',
                          (k, 0 if lock else n, _iso(_now() + timedelta(minutes=LOCK_MIN)) if lock else None))
            if s: _log(c, s, 'fail')
            c.commit()   # xato hisobi saqlansin (raise rollback qilmasin)
            raise ApiErr(401, 'Login yoki parol noto‘g‘ri.')
        if not s['active']: raise ApiErr(403, 'Bu hisob o‘chirilgan. Adminga murojaat qiling.')
        mine = c.execute('SELECT 1 FROM vd_dev WHERE tg_uid=? AND student_id=?', (int(tg_uid), s['id'])).fetchone()
        if not mine and c.execute('SELECT COUNT(*) FROM vd_dev WHERE student_id=?', (s['id'],)).fetchone()[0] >= MAX_DEV:
            raise ApiErr(403, 'Bu login boshqa Telegram akkauntlarda ishlatilgan. Adminga murojaat qiling (u parolni yangilaydi).')
        for k in keys: c.execute('DELETE FROM vd_fail WHERE k=?', (k,))
        c.execute('INSERT OR REPLACE INTO vd_dev(tg_uid,student_id,bound_at) VALUES(?,?,?)', (int(tg_uid), s['id'], nowi))
        c.execute('UPDATE vd_student SET last_login_at=?, last_seen_at=? WHERE id=?', (nowi, nowi, s['id']))
        g = _gname(c, s['group_id']); _log(c, s, 'login', grp=g)
    _announce(s, g, 'login')
    return {'id': s['id'], 'name': s['full_name'], 'group': g}


def logout(tg_uid):
    with db() as c: c.execute('DELETE FROM vd_dev WHERE tg_uid=?', (int(tg_uid),))


# ------------------------------------------------------------------ jurnal («kim kirdi»)
def _log(c, s, event, lesson=None, grp=None):
    if grp is None: grp = _gname(c, s['group_id'])
    c.execute('INSERT INTO vd_log(student_id,name,grp,event,lesson_id,lesson,at) VALUES(?,?,?,?,?,?,?)',
              (s['id'], s['full_name'], grp, event, (lesson or {}).get('id'), (lesson or {}).get('title', ''), _iso()))


def _announce(s, grp, event, lesson=None, extra=''):
    """Adminga Telegram xabari: ism, guruh, vaqt (Toshkent)."""
    if not notify_enabled(): return
    head = {'login': '🔑 Videodarsga kirdi', 'visit': '👋 Videodarsni ochdi', 'done': '✅ Videoni oxirigacha ko‘rdi', 'task': '📝 Topshiriq topshirdi',
            'topen': '📂 Maxsus topshiriqni ochdi', 'tsub': '⭐ Maxsus topshiriqni topshirdi'}.get(event)
    if not head: return
    t = '👥 %s\n👤 %s (%s)' % (head, s['full_name'], grp)
    if lesson: t += '\n📚 ' + lesson['title']
    if extra: t += '\n' + extra
    _tell(t + '\n🕒 ' + fmt(_iso()))


def touch_visit(s):
    """O'quvchi bo'limni ochganda: oxirgi kirishdan VISIT_GAP_MIN daqiqa o'tgan bo'lsa jurnalga yozadi va adminga xabar beradi."""
    nowi = _iso()
    with db() as c:
        r = c.execute('SELECT last_seen_at FROM vd_student WHERE id=?', (s['id'],)).fetchone()
        last = r[0] if r else None
        gap = True
        try:
            if last:
                d = datetime.fromisoformat(last[:25])
                if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
                gap = (_now() - d) > timedelta(minutes=VISIT_GAP_MIN)
        except Exception: gap = True
        c.execute('UPDATE vd_student SET last_seen_at=? WHERE id=?', (nowi, s['id']))
        g = _gname(c, s['group_id'])
        if gap: _log(c, s, 'visit', grp=g)
    if gap: _announce(s, g, 'visit')


def activity(limit=120, sid=None):
    with db() as c:
        rows = _rows(c, 'SELECT id, student_id, name, grp, event, lesson, at FROM vd_log ' + ('WHERE student_id=? ' if sid else '') + 'ORDER BY id DESC LIMIT ?',
                     ((int(sid), int(limit)) if sid else (int(limit),)))
    return [{'id': r['id'], 'student_id': r['student_id'], 'name': r['name'], 'group': r['grp'], 'event': r['event'],
             'label': EVENTS.get(r['event'], r['event']), 'lesson': r['lesson'], 'time': fmt(r['at'])} for r in rows]


# ------------------------------------------------------------------ darslar
_YT = re.compile(r'(?:youtu\.be/|youtube(?:-nocookie)?\.com/(?:watch\?(?:[^#\s]*&)?v=|embed/|shorts/|live/|v/))([A-Za-z0-9_-]{11})')
_DIRECT = re.compile(r'^https://[^\s]{4,580}\.(?:mp4|webm|m4v|mov|ogv)(?:\?[^\s]*)?$', re.I)


def parse_video(url):
    """-> (kind, src). kind: 'youtube' | 'direct'."""
    u = str(url or '').strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', u): return 'youtube', u
    m = _YT.search(u)
    if m: return 'youtube', m.group(1)
    if _DIRECT.match(u): return 'direct', u
    raise ApiErr(400, 'Havola tanilmadi. YouTube havolasi yoki https:// bilan boshlanuvchi .mp4/.webm fayl havolasini kiriting.')


def _task_clean(t):
    t = t if isinstance(t, dict) else {}
    kind = t.get('kind') if t.get('kind') in ('none', 'test', 'text') else 'none'
    text = str(t.get('text') or '').strip()[:2000]
    if kind == 'none': return {'kind': 'none'}
    if kind == 'text':
        if len(text) < 3: raise ApiErr(400, 'Topshiriq matnini yozing.')
        return {'kind': 'text', 'text': text}
    qs = []
    for q in (t.get('questions') or [])[:30]:
        if not isinstance(q, dict): continue
        qt = _clean(q.get('q'), 400); raw = [_clean(o, 200) for o in (q.get('options') or [])[:6]]
        try: cr = int(q.get('correct'))
        except Exception: cr = -1
        opts, cmap = [], {}
        for j, o in enumerate(raw):
            if o: cmap[j] = len(opts); opts.append(o)
        cr = cmap.get(cr, -1)   # bo'sh variantlar olib tashlanganda to'g'ri javob indeksi siljimasin
        if not qt and not opts: continue
        if not qt: raise ApiErr(400, 'Test: savol matni bo‘sh qolgan.')
        if len(opts) < 2: raise ApiErr(400, 'Test: har savolda kamida 2 ta variant bo‘lsin.')
        if not 0 <= cr < len(opts): raise ApiErr(400, 'Test: «%s» savolida to‘g‘ri javob belgilanmagan.' % qt[:40])
        qs.append({'q': qt, 'options': opts, 'correct': cr})
    if not qs: raise ApiErr(400, 'Testga kamida bitta savol qo‘shing.')
    try: pp = int(t.get('pass_pct'))
    except Exception: pp = 60
    return {'kind': 'test', 'text': text, 'questions': qs, 'pass_pct': min(100, max(1, pp))}


def _task(l):
    try: return json.loads(l.get('task_json') or '{}') or {'kind': 'none'}
    except Exception: return {'kind': 'none'}


def lesson_save(d, lid=None):
    title = _clean(d.get('title'), 120)
    if len(title) < 2: raise ApiErr(400, 'Dars nomini kiriting.')
    kind, src = parse_video(d.get('url'))
    try: dur = int(float(d.get('duration_sec') or 0))
    except Exception: dur = 0
    if not 10 <= dur <= 6 * 3600: raise ApiErr(400, 'Video davomiyligi noto‘g‘ri (10 soniya – 6 soat). «⏱ Aniqlash» tugmasini bosing yoki qo‘lda kiriting.')
    try: mp = int(d.get('min_pct') or 90)
    except Exception: mp = 90
    mp = min(100, max(50, mp)); task = _task_clean(d.get('task'))
    descr = str(d.get('descr') or '').strip()[:600]
    with db() as c:
        if not c.execute('SELECT 1 FROM vd_group WHERE id=?', (int(d.get('group_id') or 0),)).fetchone(): raise ApiErr(400, 'Guruhni tanlang.')
        gid = int(d['group_id']); pub = 1 if d.get('published', True) else 0; ts = _iso()
        if lid:
            old = _row(c, 'SELECT * FROM vd_lesson WHERE id=?', (int(lid),))
            if not old: raise ApiErr(404, 'Dars topilmadi.')
            if (old['kind'], old['src']) != (kind, src) or abs(old['duration_sec'] - dur) > 2:
                c.execute('DELETE FROM vd_prog WHERE lesson_id=?', (int(lid),))   # video almashdi: eski ko'rish hisobi yaroqsiz
            c.execute('UPDATE vd_lesson SET group_id=?,title=?,descr=?,kind=?,src=?,duration_sec=?,min_pct=?,task_json=?,published=?,updated_at=? WHERE id=?',
                      (gid, title, descr, kind, src, dur, mp, json.dumps(task, ensure_ascii=False), pub, ts, int(lid)))
            return int(lid)
        pos = (c.execute('SELECT COALESCE(MAX(pos),0)+1 FROM vd_lesson WHERE group_id=?', (gid,)).fetchone()[0])
        return c.execute('INSERT INTO vd_lesson(group_id,title,descr,kind,src,duration_sec,min_pct,task_json,published,pos,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                         (gid, title, descr, kind, src, dur, mp, json.dumps(task, ensure_ascii=False), pub, pos, ts, ts)).lastrowid


def lesson_publish(lid, v):
    with db() as c: c.execute('UPDATE vd_lesson SET published=? WHERE id=?', (1 if v else 0, int(lid)))


def lesson_move(lid, direction):
    with db() as c:
        l = _row(c, 'SELECT id, group_id, pos FROM vd_lesson WHERE id=?', (int(lid),))
        if not l: raise ApiErr(404, 'Dars topilmadi.')
        ids = [r[0] for r in c.execute('SELECT id FROM vd_lesson WHERE group_id=? ORDER BY pos, id', (l['group_id'],)).fetchall()]
        i = ids.index(l['id']); j = i - 1 if direction == 'up' else i + 1
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            for n, x in enumerate(ids, 1): c.execute('UPDATE vd_lesson SET pos=? WHERE id=?', (n, x))


def lesson_del(lid):
    with db() as c:
        for t in ('vd_prog', 'vd_sub'): c.execute('DELETE FROM %s WHERE lesson_id=?' % t, (int(lid),))
        c.execute('DELETE FROM vd_lesson WHERE id=?', (int(lid),))


def _pct(cover):
    return round(100.0 * cover.count('1') / len(cover)) if cover else 0


def lessons_admin(gid=None):
    with db() as c:
        rows = _rows(c, 'SELECT * FROM vd_lesson ' + ('WHERE group_id=? ' if gid else '') + 'ORDER BY group_id, pos, id', (int(gid),) if gid else ())
        for r in rows:
            r['done'] = c.execute('SELECT COUNT(*) FROM vd_prog WHERE lesson_id=? AND completed_at IS NOT NULL', (r['id'],)).fetchone()[0]
            r['students'] = c.execute('SELECT COUNT(*) FROM vd_student WHERE group_id=? AND active=1', (r['group_id'],)).fetchone()[0]
    out = []
    for r in rows:
        url = ('https://youtu.be/' + r['src']) if r['kind'] == 'youtube' else r['src']
        out.append({'id': r['id'], 'group_id': r['group_id'], 'title': r['title'], 'descr': r['descr'], 'url': url, 'kind': r['kind'],
                    'duration_sec': r['duration_sec'], 'min_pct': r['min_pct'], 'task': _task(r), 'published': bool(r['published']),
                    'done': r['done'], 'students': r['students']})
    return out


def _task_state(c, sid, lid, task):
    """-> 'none' | 'todo' | 'sent' | 'passed' | 'failed'"""
    if task.get('kind', 'none') == 'none': return 'none'
    subs = _rows(c, 'SELECT passed, kind FROM vd_sub WHERE student_id=? AND lesson_id=? ORDER BY id DESC', (sid, lid))
    if not subs: return 'todo'
    if task['kind'] == 'text': return 'sent'
    return 'passed' if any(s['passed'] for s in subs) else 'failed'


def lessons_for(s):
    with db() as c:
        rows = _rows(c, 'SELECT * FROM vd_lesson WHERE group_id=? AND published=1 ORDER BY pos, id', (s['group_id'],))
        out = []
        for r in rows:
            p = _row(c, 'SELECT cover, completed_at FROM vd_prog WHERE student_id=? AND lesson_id=?', (s['id'], r['id'])) or {'cover': '', 'completed_at': None}
            task = _task(r)
            out.append({'id': r['id'], 'title': r['title'], 'descr': r['descr'], 'duration_sec': r['duration_sec'], 'pct': _pct(p['cover']),
                        'completed': bool(p['completed_at']), 'task_kind': task.get('kind', 'none'), 'task_state': _task_state(c, s['id'], r['id'], task)})
    return out


def _lesson_get(c, lid):
    l = _row(c, 'SELECT * FROM vd_lesson WHERE id=?', (int(lid or 0),))
    if not l: raise ApiErr(404, 'Dars topilmadi.')
    return l


def _need_access(c, s, admin, l):
    if admin: return
    if not s: raise ApiErr(401, 'Avval login bilan kiring.')
    if l['group_id'] != s['group_id'] or not l['published']: raise ApiErr(403, 'Bu dars sizning guruhingiz uchun emas.')


def lesson_view(uid, s, admin, lid):
    with db() as c:
        l = _lesson_get(c, lid); _need_access(c, s, admin, l)
        p = {'cover': '', 'last_pos': 0, 'completed_at': None}
        if s and not admin:
            p = _row(c, 'SELECT cover, last_pos, completed_at FROM vd_prog WHERE student_id=? AND lesson_id=?', (s['id'], l['id'])) or p
            key = (s['id'], l['id']); t = time.time()
            if t - _LAST_OPEN.get(key, 0) > 600:
                _LAST_OPEN[key] = t; _log(c, s, 'open', l)
                if len(_LAST_OPEN) > 5000: _LAST_OPEN.clear()
        task = _task(l)
        cover = p['cover'] or ''
        last = cover.rfind('1'); allow = (last + 1) * BUCKET if last >= 0 else 0
        resume = p['last_pos'] if 0 < p['last_pos'] < l['duration_sec'] - 8 and not p['completed_at'] else 0
        return {'id': l['id'], 'title': l['title'], 'descr': l['descr'], 'kind': l['kind'], 'src': l['src'], 'duration_sec': l['duration_sec'],
                'min_pct': l['min_pct'], 'pct': _pct(cover), 'completed': bool(p['completed_at']), 'allow_to': allow, 'resume': resume,
                'task_kind': task.get('kind', 'none'), 'task_state': (_task_state(c, s['id'], l['id'], task) if s and not admin else '')}


def heartbeat(uid, s, admin, lid, pos, playing, rate, ended, dur):
    """Ko'rishni hisobga oladi. Har 5 soniyada keladi. Oldinga sakrash KREDIT BERMAYDI; vaqt serverdagi soat bilan o'lchanadi."""
    with db() as c:
        l = _lesson_get(c, lid); _need_access(c, s, admin, l)
        if admin:   # admin ko'rganda hisob yuritilmaydi, faqat video davomiyligi noto'g'ri kiritilgan bo'lsa tuzatiladi
            try: d = int(float(dur or 0))
            except Exception: d = 0
            if 10 <= d <= 6 * 3600 and abs(d - l['duration_sec']) >= 2:
                c.execute('UPDATE vd_lesson SET duration_sec=?, updated_at=? WHERE id=?', (d, _iso(), l['id']))
            return {'admin': True}
        D = l['duration_sec']; nb = max(1, math.ceil(D / BUCKET))
        p = _row(c, 'SELECT * FROM vd_prog WHERE student_id=? AND lesson_id=?', (s['id'], l['id']))
        if not p:
            c.execute('INSERT INTO vd_prog(student_id,lesson_id,cover,started_at) VALUES(?,?,?,?)', (s['id'], l['id'], '0' * nb, _iso()))
            p = _row(c, 'SELECT * FROM vd_prog WHERE student_id=? AND lesson_id=?', (s['id'], l['id']))
        cover = list((p['cover'] or '').ljust(nb, '0')[:nb])
        try: pos = min(max(float(pos), 0.0), float(D))
        except Exception: pos = 0.0
        try: rate = min(max(float(rate or 1), 0.25), 2.0)
        except Exception: rate = 1.0
        t = time.time(); last_pos, last_hb = float(p['last_pos'] or 0), float(p['last_hb'] or 0)
        if playing and last_hb and 0 < t - last_hb <= 20:
            adv = pos - last_pos
            if 0 < adv <= (t - last_hb) * rate * 1.25 + 1.5:    # oddiy ko'rish (sakrash emas)
                for b in range(int(last_pos // BUCKET), min(int(pos // BUCKET), nb - 1) + 1): cover[b] = '1'
        cs = ''.join(cover); pct = _pct(cs)
        done = bool(p['completed_at'])
        reached_end = (ended and pos >= D - 10) or (cs[nb - 1] == '1' and pos >= D - 3)   # haqiqatan oxiriga yetdi
        if not done and pct >= l['min_pct'] and reached_end:
            done = True
            c.execute('UPDATE vd_prog SET completed_at=? WHERE student_id=? AND lesson_id=?', (_iso(), s['id'], l['id']))
            _log(c, s, 'done', l); g = _gname(c, s['group_id']); newly = (s, g, l)
        else: newly = None
        c.execute('UPDATE vd_prog SET cover=?, last_pos=?, last_hb=?, updated_at=? WHERE student_id=? AND lesson_id=?', (cs, pos, t, _iso(), s['id'], l['id']))
        c.execute('UPDATE vd_student SET last_seen_at=? WHERE id=?', (_iso(), s['id']))
        last = cs.rfind('1')
        res = {'pct': pct, 'completed': done, 'allow_to': (last + 1) * BUCKET if last >= 0 else 0, 'min_pct': l['min_pct']}
    if newly: _announce(newly[0], newly[1], 'done', newly[2], 'Ko‘rilgan: %d%%' % pct)
    return res


# ------------------------------------------------------------------ topshiriq (video tugagach)
def task_get(s, admin, lid):
    with db() as c:
        l = _lesson_get(c, lid); _need_access(c, s, admin, l)
        task = _task(l); k = task.get('kind', 'none')
        if k == 'none': return {'kind': 'none', 'title': l['title']}
        last = None
        if s and not admin:
            p = _row(c, 'SELECT completed_at FROM vd_prog WHERE student_id=? AND lesson_id=?', (s['id'], l['id']))
            if not (p and p['completed_at']): raise ApiErr(403, 'Topshiriq videoni oxirigacha ko‘rgandan keyin ochiladi.')
            last = _row(c, 'SELECT * FROM vd_sub WHERE student_id=? AND lesson_id=? ORDER BY id DESC', (s['id'], l['id']))
            passed = bool(c.execute('SELECT 1 FROM vd_sub WHERE student_id=? AND lesson_id=? AND passed=1', (s['id'], l['id'])).fetchone())
        else: passed = True
        out = {'kind': k, 'title': l['title'], 'text': task.get('text', ''), 'passed': passed}
        if k == 'test':
            out['pass_pct'] = task['pass_pct']
            out['questions'] = [{'q': q['q'], 'options': q['options'], **({'correct': q['correct']} if admin else {})} for q in task['questions']]
        if last:
            out['last'] = {'score': last['score'], 'total': last['total'], 'passed': bool(last['passed']), 'text': last['text'], 'comment': last['comment'],
                           'time': fmt(last['at']), 'wrong': (json.loads(last['answers_json'] or '{}').get('wrong', []) if k == 'test' else [])}
            if k == 'test' and passed: out['answers'] = [q['correct'] for q in task['questions']]
        return out


def task_submit(s, lid, answers=None, text=None):
    with db() as c:
        l = _lesson_get(c, lid)
        if not s: raise ApiErr(401, 'Avval login bilan kiring.')
        _need_access(c, s, False, l)
        p = _row(c, 'SELECT completed_at FROM vd_prog WHERE student_id=? AND lesson_id=?', (s['id'], l['id']))
        if not (p and p['completed_at']): raise ApiErr(403, 'Topshiriq videoni oxirigacha ko‘rgandan keyin ochiladi.')
        task = _task(l); k = task.get('kind', 'none')
        if k == 'none': raise ApiErr(400, 'Bu darsda topshiriq yo‘q.')
        key = (s['id'], l['id']); tnow = time.time()
        if tnow - _LAST_SUB.get(key, 0) < 8: raise ApiErr(429, 'Biroz kuting va qayta yuboring.')
        _LAST_SUB[key] = tnow
        if len(_LAST_SUB) > 5000: _LAST_SUB.clear()
        g = _gname(c, s['group_id'])
        if k == 'text':
            tx = str(text or '').strip()[:4000]
            if len(tx) < 2: raise ApiErr(400, 'Javobingizni yozing.')
            c.execute('INSERT INTO vd_sub(student_id,lesson_id,kind,text,at) VALUES(?,?,?,?,?)', (s['id'], l['id'], 'text', tx, _iso()))
            _log(c, s, 'task', l); res = {'kind': 'text', 'sent': True}; extra = 'Matnli javob'
        else:
            qs = task['questions']
            if not isinstance(answers, list) or len(answers) != len(qs): raise ApiErr(400, 'Hamma savolga javob bering.')
            wrong, score = [], 0
            for i, q in enumerate(qs):
                try: a = int(answers[i])
                except Exception: a = -1
                if a == q['correct']: score += 1
                else: wrong.append(i)
            passed = 100.0 * score / len(qs) >= task['pass_pct']
            c.execute('INSERT INTO vd_sub(student_id,lesson_id,kind,answers_json,score,total,passed,at) VALUES(?,?,?,?,?,?,?,?)',
                      (s['id'], l['id'], 'test', json.dumps({'a': answers, 'wrong': wrong}), score, len(qs), 1 if passed else 0, _iso()))
            _log(c, s, 'task', l)
            res = {'kind': 'test', 'score': score, 'total': len(qs), 'passed': passed, 'wrong': [] if passed else wrong, 'pass_pct': task['pass_pct']}
            if passed: res['answers'] = [q['correct'] for q in qs]
            extra = 'Natija: %d/%d %s' % (score, len(qs), '✅' if passed else '❌')
    _announce(s, g, 'task', l, extra)
    return res


# ------------------------------------------------------------------ admin: natijalar va javoblar
def lesson_results(lid):
    with db() as c:
        l = _lesson_get(c, lid); task = _task(l)
        studs = _rows(c, 'SELECT id, full_name, login, active FROM vd_student WHERE group_id=? ORDER BY full_name COLLATE NOCASE', (l['group_id'],))
        out = []
        for s in studs:
            p = _row(c, 'SELECT cover, completed_at, updated_at FROM vd_prog WHERE student_id=? AND lesson_id=?', (s['id'], l['id'])) or {}
            subs = _rows(c, 'SELECT id, kind, text, score, total, passed, comment, at FROM vd_sub WHERE student_id=? AND lesson_id=? ORDER BY id DESC', (s['id'], l['id']))
            best = max(subs, key=lambda x: (x['passed'], x['score'])) if subs and task.get('kind') == 'test' else (subs[0] if subs else None)
            out.append({'student_id': s['id'], 'name': s['full_name'], 'active': bool(s['active']), 'pct': _pct(p.get('cover') or ''),
                        'completed': fmt(p['completed_at']) if p.get('completed_at') else '', 'last_watch': fmt(p['updated_at']) if p.get('updated_at') else '',
                        'attempts': len(subs), 'task_state': _task_state(c, s['id'], l['id'], task),
                        'best': ({'score': best['score'], 'total': best['total'], 'passed': bool(best['passed'])} if best and best['kind'] == 'test' else None),
                        'sub': ({'id': subs[0]['id'], 'text': subs[0]['text'], 'comment': subs[0]['comment'], 'time': fmt(subs[0]['at'])} if subs and subs[0]['kind'] == 'text' else None)})
    return {'lesson': {'id': l['id'], 'title': l['title'], 'task_kind': task.get('kind', 'none')}, 'rows': out}


def sub_review(sub_id, comment):
    with db() as c:
        r = _row(c, 'SELECT id FROM vd_sub WHERE id=?', (int(sub_id or 0),))
        if not r: raise ApiErr(404, 'Javob topilmadi.')
        c.execute('UPDATE vd_sub SET comment=?, reviewed_at=? WHERE id=?', (str(comment or '').strip()[:600], _iso(), r['id']))



# ------------------------------------------------------------------ v135: MAXSUS TOPSHIRIQ (videoga bog'liq emas; yopiq + ochiq savollar)
def _items_clean(items):
    """Yopiq savol: {type:'closed', q, options[2..6], correct}. Ochiq savol: {type:'open', q}."""
    out = []
    for it in (items or [])[:50]:
        if not isinstance(it, dict): continue
        typ = 'open' if it.get('type') == 'open' else 'closed'
        qt = _clean(it.get('q'), 500)
        if typ == 'open':
            if not qt: continue
            if len(qt) < 2: raise ApiErr(400, 'Ochiq savol matni juda qisqa.')
            out.append({'type': 'open', 'q': qt}); continue
        raw = [_clean(o, 200) for o in (it.get('options') or [])[:6]]
        try: cr = int(it.get('correct'))
        except Exception: cr = -1
        opts, cmap = [], {}
        for j, o in enumerate(raw):
            if o: cmap[j] = len(opts); opts.append(o)
        cr = cmap.get(cr, -1)
        if not qt and not opts: continue
        if not qt: raise ApiErr(400, 'Yopiq test: savol matni bo‘sh qolgan.')
        if len(opts) < 2: raise ApiErr(400, 'Yopiq test: har savolda kamida 2 ta variant bo‘lsin.')
        if not 0 <= cr < len(opts): raise ApiErr(400, 'Yopiq test: «%s» savolida to‘g‘ri javob belgilanmagan.' % qt[:40])
        out.append({'type': 'closed', 'q': qt, 'options': opts, 'correct': cr})
    if not out: raise ApiErr(400, 'Kamida bitta savol qo‘shing.')
    return out


def _items(t):
    try: return json.loads(t.get('items_json') or '[]') or []
    except Exception: return []


def task_save(d, tid=None):
    title = _clean(d.get('title'), 120)
    if len(title) < 2: raise ApiErr(400, 'Topshiriq nomini kiriting.')
    items = _items_clean(d.get('items'))
    try: pp = int(d.get('pass_pct'))
    except Exception: pp = 60
    pp = min(100, max(1, pp))
    try: ma = int(d.get('max_attempts'))
    except Exception: ma = 1
    ma = ma if ma in (0, 1, 2, 3, 5) else 1
    descr = str(d.get('descr') or '').strip()[:1000]
    with db() as c:
        if not c.execute('SELECT 1 FROM vd_group WHERE id=?', (int(d.get('group_id') or 0),)).fetchone(): raise ApiErr(400, 'Guruhni tanlang.')
        gid = int(d['group_id']); pub = 1 if d.get('published', True) else 0; ts = _iso()
        js = json.dumps(items, ensure_ascii=False)
        if tid:
            old = _row(c, 'SELECT * FROM vd_task WHERE id=?', (int(tid),))
            if not old: raise ApiErr(404, 'Topshiriq topshiriqlar ro‘yxatida topilmadi.')
            c.execute('UPDATE vd_task SET group_id=?,title=?,descr=?,items_json=?,pass_pct=?,max_attempts=?,published=?,updated_at=? WHERE id=?',
                      (gid, title, descr, js, pp, ma, pub, ts, int(tid)))
            return int(tid)
        pos = c.execute('SELECT COALESCE(MAX(pos),0)+1 FROM vd_task WHERE group_id=?', (gid,)).fetchone()[0]
        return c.execute('INSERT INTO vd_task(group_id,title,descr,items_json,pass_pct,max_attempts,published,pos,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (gid, title, descr, js, pp, ma, pub, pos, ts, ts)).lastrowid


def task_publish(tid, v):
    with db() as c: c.execute('UPDATE vd_task SET published=? WHERE id=?', (1 if v else 0, int(tid)))


def task_del(tid):
    with db() as c:
        for t in ('vd_tprog', 'vd_tsub'): c.execute('DELETE FROM %s WHERE task_id=?' % t, (int(tid),))
        c.execute('DELETE FROM vd_task WHERE id=?', (int(tid),))


def tasks_admin(gid=None):
    with db() as c:
        rows = _rows(c, 'SELECT * FROM vd_task ' + ('WHERE group_id=? ' if gid else '') + 'ORDER BY group_id, pos, id', (int(gid),) if gid else ())
        out = []
        for r in rows:
            items = _items(r)
            out.append({'id': r['id'], 'group_id': r['group_id'], 'title': r['title'], 'descr': r['descr'], 'items': items, 'pass_pct': r['pass_pct'],
                        'max_attempts': r['max_attempts'], 'published': bool(r['published']),
                        'closed_n': sum(1 for x in items if x.get('type') != 'open'), 'open_n': sum(1 for x in items if x.get('type') == 'open'),
                        'opened': c.execute('SELECT COUNT(*) FROM vd_tprog WHERE task_id=?', (r['id'],)).fetchone()[0],
                        'submitted': c.execute('SELECT COUNT(DISTINCT student_id) FROM vd_tsub WHERE task_id=?', (r['id'],)).fetchone()[0],
                        'students': c.execute('SELECT COUNT(*) FROM vd_student WHERE group_id=? AND active=1', (r['group_id'],)).fetchone()[0]})
    return out


def _t_state(c, sid, tid):
    """-> (state, attempts, best_row)  state: new | opened | sent | passed | failed"""
    subs = _rows(c, 'SELECT id, score, total, passed, open_n, at FROM vd_tsub WHERE student_id=? AND task_id=? ORDER BY id DESC', (sid, tid))
    if not subs:
        opened = c.execute('SELECT 1 FROM vd_tprog WHERE student_id=? AND task_id=?', (sid, tid)).fetchone()
        return ('opened' if opened else 'new'), 0, None
    best = max(subs, key=lambda x: (x['passed'], x['score']))
    if best['total'] == 0: return 'sent', len(subs), subs[0]
    return ('passed' if best['passed'] else 'failed'), len(subs), best


def stasks_for(s):
    with db() as c:
        rows = _rows(c, 'SELECT * FROM vd_task WHERE group_id=? AND published=1 ORDER BY pos, id', (s['group_id'],))
        out = []
        for r in rows:
            items = _items(r); st, att, best = _t_state(c, s['id'], r['id'])
            out.append({'id': r['id'], 'title': r['title'], 'descr': r['descr'], 'n': len(items),
                        'closed_n': sum(1 for x in items if x.get('type') != 'open'), 'open_n': sum(1 for x in items if x.get('type') == 'open'),
                        'state': st, 'attempts': att, 'max_attempts': r['max_attempts'],
                        'score': best['score'] if best else 0, 'total': best['total'] if best else 0})
    return out


def _t_get(c, tid):
    t = _row(c, 'SELECT * FROM vd_task WHERE id=?', (int(tid or 0),))
    if not t: raise ApiErr(404, 'Topshiriq topshiriqlar ro‘yxatida topilmadi.')
    return t


def _t_access(c, s, admin, t):
    if admin: return
    if not s: raise ApiErr(401, 'Avval login bilan kiring.')
    if t['group_id'] != s['group_id'] or not t['published']: raise ApiErr(403, 'Bu topshiriq sizning guruhingiz uchun emas.')


def _t_can_submit(t, att, state):
    if t['max_attempts'] and att >= t['max_attempts']: return False
    return state != 'passed'


def stask_begin(s, admin, tid):
    """O'quvchi topshiriqni ochadi: ochilish vaqti yoziladi (admin ko'radi). Savollarda to'g'ri javob YO'Q."""
    with db() as c:
        t = _t_get(c, tid); _t_access(c, s, admin, t)
        items = _items(t)
        if admin:
            return {'id': t['id'], 'title': t['title'], 'descr': t['descr'], 'pass_pct': t['pass_pct'], 'max_attempts': t['max_attempts'], 'admin': True,
                    'items': items}
        nowi = _iso(); first = False
        pr = _row(c, 'SELECT * FROM vd_tprog WHERE student_id=? AND task_id=?', (s['id'], t['id']))
        last_sub = c.execute('SELECT MAX(at) FROM vd_tsub WHERE student_id=? AND task_id=?', (s['id'], t['id'])).fetchone()[0]
        if not pr:
            first = True
            c.execute('INSERT INTO vd_tprog(student_id,task_id,first_open_at,last_open_at,attempt_start_at,opens) VALUES(?,?,?,?,?,1)', (s['id'], t['id'], nowi, nowi, nowi))
        else:
            start = pr['attempt_start_at']
            if not start or (last_sub and last_sub >= start): start = nowi
            c.execute('UPDATE vd_tprog SET last_open_at=?, attempt_start_at=?, opens=opens+1 WHERE student_id=? AND task_id=?', (nowi, start, s['id'], t['id']))
        key = ('t', s['id'], t['id']); tm = time.time()
        if first or tm - _LAST_OPEN.get(key, 0) > 600:
            _LAST_OPEN[key] = tm; _log(c, s, 'topen', {'id': t['id'], 'title': t['title']})
            if len(_LAST_OPEN) > 5000: _LAST_OPEN.clear()
        st, att, best = _t_state(c, s['id'], t['id'])
        last = _row(c, 'SELECT * FROM vd_tsub WHERE student_id=? AND task_id=? ORDER BY id DESC', (s['id'], t['id']))
        can = _t_can_submit(t, att, st)
        out = {'id': t['id'], 'title': t['title'], 'descr': t['descr'], 'pass_pct': t['pass_pct'], 'max_attempts': t['max_attempts'], 'attempts': att,
               'state': st, 'can_submit': can,
               'items': [({'type': 'open', 'q': x['q']} if x.get('type') == 'open' else {'type': 'closed', 'q': x['q'], 'options': x['options']}) for x in items]}
        if last:
            try: ans = json.loads(last['answers_json'] or '{}')
            except Exception: ans = {}
            out['last'] = {'score': last['score'], 'total': last['total'], 'open_n': last['open_n'], 'passed': bool(last['passed']), 'comment': last['comment'],
                           'time': fmt(last['at']), 'answers': ans.get('a', []), 'wrong': ans.get('wrong', []) if can else []}
            if not can:   # urinish tugadi yoki o'tdi: to'g'ri javoblar ochiladi
                out['correct'] = [x.get('correct') if x.get('type') != 'open' else None for x in items]
    if first: _announce(s, _gname_safe(s), 'topen', {'title': t['title']})
    return out


def _gname_safe(s):
    with db() as c: return _gname(c, s['group_id'])


def stask_submit(s, tid, answers):
    with db() as c:
        t = _t_get(c, tid)
        if not s: raise ApiErr(401, 'Avval login bilan kiring.')
        _t_access(c, s, False, t)
        items = _items(t); st, att, best = _t_state(c, s['id'], t['id'])
        if t['max_attempts'] and att >= t['max_attempts']: raise ApiErr(403, 'Urinishlar tugagan.')
        if st == 'passed': raise ApiErr(403, 'Bu topshiriqdan allaqachon o‘tgansiz.')
        if not isinstance(answers, list) or len(answers) != len(items): raise ApiErr(400, 'Hamma savolga javob bering.')
        key = ('t', s['id'], t['id']); tnow = time.time()
        if tnow - _LAST_SUB.get(key, 0) < 8: raise ApiErr(429, 'Biroz kuting va qayta yuboring.')
        score, total, open_n, wrong, clean = 0, 0, 0, [], []
        for i, it in enumerate(items):
            a = answers[i]
            if it.get('type') == 'open':
                tx = str(a or '').strip()[:3000]
                if len(tx) < 2: raise ApiErr(400, '%d-savolga javob yozing.' % (i + 1))
                clean.append(tx); open_n += 1
            else:
                try: a = int(a)
                except Exception: a = -1
                if not 0 <= a < len(it['options']): raise ApiErr(400, '%d-savolga javob bering.' % (i + 1))
                clean.append(a); total += 1
                if a == it['correct']: score += 1
                else: wrong.append(i)
        _LAST_SUB[key] = tnow
        if len(_LAST_SUB) > 5000: _LAST_SUB.clear()
        passed = (100.0 * score / total >= t['pass_pct']) if total else True
        pr = _row(c, 'SELECT attempt_start_at, first_open_at FROM vd_tprog WHERE student_id=? AND task_id=?', (s['id'], t['id'])) or {}
        started = pr.get('attempt_start_at') or pr.get('first_open_at') or _iso()
        c.execute('INSERT INTO vd_tsub(student_id,task_id,answers_json,score,total,open_n,passed,started_at,at) VALUES(?,?,?,?,?,?,?,?,?)',
                  (s['id'], t['id'], json.dumps({'a': clean, 'wrong': wrong}, ensure_ascii=False), score, total, open_n, 1 if passed else 0, started, _iso()))
        _log(c, s, 'tsub', {'id': t['id'], 'title': t['title']}); g = _gname(c, s['group_id'])
        att += 1; finished = passed or (t['max_attempts'] and att >= t['max_attempts'])
        res = {'score': score, 'total': total, 'open_n': open_n, 'passed': passed, 'attempts': att, 'max_attempts': t['max_attempts'],
               'wrong': [] if finished else wrong, 'can_retry': not finished}
        if finished: res['correct'] = [x.get('correct') if x.get('type') != 'open' else None for x in items]
    extra = ('Natija: %d/%d %s' % (score, total, '✅' if passed else '❌') if total else 'Faqat ochiq savollar') + (' • ochiq javoblar: %d' % open_n if open_n and total else '')
    _announce(s, g, 'tsub', {'title': t['title']}, extra)
    return res


def _dur(a, b):
    try:
        da = datetime.fromisoformat(str(a)[:25]); db_ = datetime.fromisoformat(str(b)[:25])
        sec = int((db_ - da).total_seconds())
        if sec < 0: return ''
        return ('%d daq %02d s' % (sec // 60, sec % 60)) if sec >= 60 else ('%d s' % sec)
    except Exception: return ''


def task_results(tid):
    """Admin: guruhdagi har bir o'quvchi — qachon kirdi, necha marta, qachon topshirdi, natija."""
    with db() as c:
        t = _t_get(c, tid); items = _items(t)
        studs = _rows(c, 'SELECT id, full_name, login, active FROM vd_student WHERE group_id=? ORDER BY full_name COLLATE NOCASE', (t['group_id'],))
        out = []
        for s in studs:
            pr = _row(c, 'SELECT first_open_at, last_open_at, opens FROM vd_tprog WHERE student_id=? AND task_id=?', (s['id'], t['id'])) or {}
            subs = _rows(c, 'SELECT id, score, total, open_n, passed, comment, started_at, at FROM vd_tsub WHERE student_id=? AND task_id=? ORDER BY id DESC', (s['id'], t['id']))
            st, att, best = _t_state(c, s['id'], t['id'])
            last = subs[0] if subs else None
            out.append({'student_id': s['id'], 'name': s['full_name'], 'login': s['login'], 'active': bool(s['active']), 'state': st, 'attempts': att,
                        'first_open': fmt(pr['first_open_at']) if pr.get('first_open_at') else '', 'last_open': fmt(pr['last_open_at']) if pr.get('last_open_at') else '',
                        'opens': pr.get('opens', 0),
                        'submitted_at': fmt(last['at']) if last else '', 'spent': _dur(last['started_at'], last['at']) if last else '',
                        'score': best['score'] if best else 0, 'total': best['total'] if best else 0,
                        'open_n': last['open_n'] if last else 0, 'reviewed': bool(last and last['comment'])})
    return {'task': {'id': t['id'], 'title': t['title'], 'closed_n': sum(1 for x in items if x.get('type') != 'open'),
                     'open_n': sum(1 for x in items if x.get('type') == 'open'), 'pass_pct': t['pass_pct'], 'max_attempts': t['max_attempts']}, 'rows': out}


def task_sub_detail(tid, sid):
    """Admin: bitta o'quvchining barcha urinishlari, har savol bo'yicha javobi (to'g'ri/noto'g'ri)."""
    with db() as c:
        t = _t_get(c, tid); items = _items(t)
        s = _row(c, 'SELECT id, full_name FROM vd_student WHERE id=?', (int(sid or 0),))
        if not s: raise ApiErr(404, 'O‘quvchi topilmadi.')
        subs = _rows(c, 'SELECT * FROM vd_tsub WHERE student_id=? AND task_id=? ORDER BY id DESC', (s['id'], t['id']))
        out = []
        for sb in subs:
            try: a = json.loads(sb['answers_json'] or '{}').get('a', [])
            except Exception: a = []
            det = []
            for i, it in enumerate(items):
                ans = a[i] if i < len(a) else None
                if it.get('type') == 'open': det.append({'type': 'open', 'q': it['q'], 'answer': ans if isinstance(ans, str) else ''})
                else:
                    det.append({'type': 'closed', 'q': it['q'], 'options': it['options'], 'correct': it['correct'], 'chosen': ans if isinstance(ans, int) else -1,
                                'ok': ans == it['correct']})
            out.append({'id': sb['id'], 'time': fmt(sb['at']), 'started': fmt(sb['started_at']) if sb['started_at'] else '', 'spent': _dur(sb['started_at'], sb['at']),
                        'score': sb['score'], 'total': sb['total'], 'open_n': sb['open_n'], 'passed': bool(sb['passed']), 'comment': sb['comment'], 'items': det})
    return {'student': {'id': s['id'], 'name': s['full_name']}, 'title': t['title'], 'subs': out}


def tsub_review(sub_id, comment):
    with db() as c:
        r = _row(c, 'SELECT id FROM vd_tsub WHERE id=?', (int(sub_id or 0),))
        if not r: raise ApiErr(404, 'Javob topilmadi.')
        c.execute('UPDATE vd_tsub SET comment=?, reviewed_at=? WHERE id=?', (str(comment or '').strip()[:600], _iso(), r['id']))


# ------------------------------------------------------------------ API
def _s_or_err(uid, admin, need_student=True):
    s = student_of(uid)
    if not s and not admin and need_student: raise ApiErr(401, 'Avval login bilan kiring.')
    return s


def _i(v):
    try: return int(v)
    except Exception: return 0


def api_post(path, body, uid, admin):
    """-> (status, dict)"""
    p = path.split('?')[0]
    if not isinstance(body, dict): return 400, {'ok': False, 'error': 'Noto‘g‘ri so‘rov.'}
    try: return 200, _route(p, body, uid, admin)
    except ApiErr as e: return e.status, {'ok': False, 'error': e.msg}
    except Exception:
        log.exception('videodars %s', p); return 500, {'ok': False, 'error': 'Xatolik. Qayta urinib ko‘ring.'}


def _route(p, b, uid, admin):
    if p == '/api/vd/me':
        s = student_of(uid)
        if admin:
            with db() as c: gs = groups(c)
            return {'ok': True, 'role': 'admin', 'groups': gs, 'notify': notify_enabled(), 'max_dev': MAX_DEV}
        if not s: return {'ok': True, 'role': 'guest'}
        touch_visit(s)
        with db() as c: g = _gname(c, s['group_id'])
        return {'ok': True, 'role': 'student', 'name': s['full_name'], 'group': g, 'lessons': lessons_for(s), 'tasks': stasks_for(s)}
    if p == '/api/vd/login':
        r = login(uid, b.get('login'), b.get('password')); return {'ok': True, **r}
    if p == '/api/vd/logout': logout(uid); return {'ok': True}
    if p == '/api/vd/lessons':
        s = _s_or_err(uid, admin)
        return {'ok': True, 'lessons': lessons_admin(_i(b.get('group_id')) or None) if admin else lessons_for(s)}
    if p == '/api/vd/lesson':
        s = _s_or_err(uid, admin); return {'ok': True, 'lesson': lesson_view(uid, s, admin, b.get('id'))}
    if p == '/api/vd/hb':
        s = _s_or_err(uid, admin)
        return {'ok': True, **heartbeat(uid, s, admin, b.get('id'), b.get('pos'), bool(b.get('playing')), b.get('rate'), bool(b.get('ended')), b.get('dur'))}
    if p == '/api/vd/task':
        s = _s_or_err(uid, admin); return {'ok': True, 'task': task_get(s, admin, b.get('id'))}
    if p == '/api/vd/submit':
        s = _s_or_err(uid, False); return {'ok': True, 'result': task_submit(s, b.get('id'), b.get('answers'), b.get('text'))}
    if p == '/api/vd/st/list':      # v135: maxsus topshiriqlar (o'quvchi: o'z guruhiniki; admin: hammasi)
        s = _s_or_err(uid, admin)
        return {'ok': True, 'tasks': tasks_admin(_i(b.get('group_id')) or None) if admin else stasks_for(s)}
    if p == '/api/vd/st/open':
        s = _s_or_err(uid, admin); return {'ok': True, 'task': stask_begin(s, admin, b.get('id'))}
    if p == '/api/vd/st/submit':
        s = _s_or_err(uid, False); return {'ok': True, 'result': stask_submit(s, b.get('id'), b.get('answers'))}
    if p == '/api/vd/parse':      # admin formasi: havolani tekshirish (video turini aniqlash)
        if not admin: raise ApiErr(403, 'Faqat admin.')
        k, src = parse_video(b.get('url')); return {'ok': True, 'kind': k, 'src': src}
    if not p.startswith('/api/vd/admin/'): raise ApiErr(404, 'Topilmadi')
    if not admin: raise ApiErr(403, 'Faqat admin.')
    a = p[len('/api/vd/admin/'):]
    if a == 'groups':
        with db() as c: return {'ok': True, 'groups': groups(c)}
    if a == 'group_add': gid = group_add(b.get('name')); return {'ok': True, 'id': gid}
    if a == 'group_rename': group_rename(_i(b.get('id')), b.get('name')); return {'ok': True}
    if a == 'group_del': group_del(_i(b.get('id'))); return {'ok': True}
    if a == 'students': return {'ok': True, 'students': students_list(_i(b.get('group_id')) or None)}
    if a == 'students_add': return {'ok': True, 'created': students_add(b.get('group_id'), b.get('names'))}
    if a == 'student_reset': return {'ok': True, 'cred': student_reset(_i(b.get('id')))}
    if a == 'student_edit':
        student_edit(_i(b.get('id')), b.get('name'), b.get('group_id'), (bool(b['active']) if 'active' in b else None), b.get('login')); return {'ok': True}
    if a == 'student_setpw': return {'ok': True, 'cred': student_setpw(_i(b.get('id')), b.get('password'))}
    if a == 'task_save': return {'ok': True, 'id': task_save(b, _i(b.get('id')) or None)}
    if a == 'task_pub': task_publish(_i(b.get('id')), bool(b.get('published'))); return {'ok': True}
    if a == 'task_del': task_del(_i(b.get('id'))); return {'ok': True}
    if a == 'task_results': return {'ok': True, **task_results(_i(b.get('id')))}
    if a == 'task_detail': return {'ok': True, **task_sub_detail(_i(b.get('id')), _i(b.get('student_id')))}
    if a == 'task_review': tsub_review(_i(b.get('id')), b.get('comment')); return {'ok': True}
    if a == 'student_del': student_del(_i(b.get('id'))); return {'ok': True}
    if a == 'lesson_save': return {'ok': True, 'id': lesson_save(b, _i(b.get('id')) or None)}
    if a == 'lesson_pub': lesson_publish(_i(b.get('id')), bool(b.get('published'))); return {'ok': True}
    if a == 'lesson_move': lesson_move(_i(b.get('id')), 'up' if b.get('dir') == 'up' else 'down'); return {'ok': True}
    if a == 'lesson_del': lesson_del(_i(b.get('id'))); return {'ok': True}
    if a == 'results': return {'ok': True, **lesson_results(_i(b.get('id')))}
    if a == 'review': sub_review(_i(b.get('id')), b.get('comment')); return {'ok': True}
    if a == 'activity': return {'ok': True, 'rows': activity(min(300, _i(b.get('limit')) or 120), _i(b.get('student_id')) or None)}
    if a == 'notify': _kv_set('notify', '1' if b.get('on') else '0'); return {'ok': True, 'notify': notify_enabled()}
    raise ApiErr(404, 'Topilmadi')
