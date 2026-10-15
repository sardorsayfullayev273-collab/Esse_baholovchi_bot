# v60: Mock imtihonlar (Mini App «Mock» bo'limi). Admin boshqaradi; hozircha bepul (price=0).
# To'lov admin yoqmaguncha o'chiq (mock_settings.pay_on). Foydalanuvchiga «bepul» yozuvi ko'rsatilmaydi. 1 ta mock = MOCK_UZS (10 000 so'm), karta orqali.
import os, re
from datetime import datetime, timezone

_db = None
_lock = None
_ready = False

MOCK_UZS = int(os.getenv('MOCK_UZS', '10000') or 10000)   # 1 ta mock narxi (so'm)


def configure(db_fn, lock):
    global _db, _lock
    _db, _lock = db_fn, lock


def _init():
    global _ready
    if _ready:
        return
    with _lock, _db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS mocks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            opens_at TEXT NOT NULL,
            closes_at TEXT NOT NULL,
            test_code TEXT DEFAULT '',
            price INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS mock_regs(
            mock_id INTEGER NOT NULL, user_id INTEGER NOT NULL, joined_at TEXT NOT NULL,
            PRIMARY KEY(mock_id,user_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS mock_access(
            mock_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            PRIMARY KEY(mock_id,user_id))''')
        c.execute('CREATE TABLE IF NOT EXISTS mock_settings(k TEXT PRIMARY KEY, v TEXT)')
    _ready = True


def pay_on():
    _init()
    with _lock, _db() as c:
        r = c.execute("SELECT v FROM mock_settings WHERE k='pay_on'").fetchone()
    return bool(r) and r[0] == '1'


def set_pay(on):
    _init()
    with _lock, _db() as c:
        c.execute("INSERT OR REPLACE INTO mock_settings(k,v) VALUES('pay_on',?)", ('1' if on else '0',))


def price():
    return MOCK_UZS


def get(mid):
    _init()
    with _lock, _db() as c:
        return c.execute('SELECT * FROM mocks WHERE id=?', (int(mid),)).fetchone()


def exists(mid):
    try:
        return get(mid) is not None
    except Exception:
        return False


def title_of(mid):
    r = get(mid)
    return r['title'] if r else 'Mock'


def has_access(uid, mid):
    if not pay_on():
        return True
    _init()
    with _lock, _db() as c:
        return c.execute('SELECT 1 FROM mock_access WHERE mock_id=? AND user_id=?', (int(mid), int(uid))).fetchone() is not None


def grant(uid, mid):
    _init()
    with _lock, _db() as c:
        c.execute('INSERT OR IGNORE INTO mock_access(mock_id,user_id) VALUES(?,?)', (int(mid), int(uid)))
        c.execute('INSERT OR IGNORE INTO mock_regs(mock_id,user_id,joined_at) VALUES(?,?,?)', (int(mid), int(uid), _iso(_now())))


def mock_codes():
    _init()
    with _lock, _db() as c:
        return {r[0] for r in c.execute("SELECT test_code FROM mocks WHERE test_code<>''").fetchall()}


def test_gate(code, uid, is_admin, submit=False):
    """Test kodi mockka tegishli bo'lsa: vaqt oynasi va to'lov tekshiriladi. None = ruxsat."""
    if is_admin:
        return None
    _init()
    code = str(code or '').upper().strip()
    with _lock, _db() as c:
        r = c.execute('SELECT * FROM mocks WHERE test_code=? ORDER BY opens_at DESC LIMIT 1', (code,)).fetchone()
    if not r:
        return None
    now = _now()
    if now < _parse(r['opens_at']):
        return {'ok': False, 'error': 'Mock hali boshlanmagan.'}, 403
    if not submit and now >= _parse(r['closes_at']):
        return {'ok': False, 'error': 'Bu mock yakunlangan.'}, 410
    if uid is None or not has_access(uid, r['id']):
        return {'ok': False, 'need_pay': True, 'mock_id': r['id'], 'price': MOCK_UZS, 'error': 'Bu mock uchun to‘lov kerak.'}, 402
    return None


def _now():
    return datetime.now(timezone.utc)


def _parse(s):
    s = str(s or '').strip().replace('Z', '+00:00')
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _iso(d):
    return d.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _status(o, c, now):
    if now < o:
        return 'upcoming'
    if now < c:
        return 'open'
    return 'closed'


def listing(uid, is_admin):
    _init()
    now = _now()
    on = pay_on()
    out = []
    with _lock, _db() as c:
        rows = c.execute('SELECT * FROM mocks ORDER BY opens_at DESC LIMIT 60').fetchall()
        for r in rows:
            regs = c.execute('SELECT COUNT(*) FROM mock_regs WHERE mock_id=?', (r['id'],)).fetchone()[0]
            joined = bool(uid) and c.execute('SELECT 1 FROM mock_regs WHERE mock_id=? AND user_id=?', (r['id'], uid)).fetchone() is not None
            has_acc = (not on) or is_admin or (bool(uid) and c.execute('SELECT 1 FROM mock_access WHERE mock_id=? AND user_id=?', (r['id'], uid)).fetchone() is not None)
            o, cl = _parse(r['opens_at']), _parse(r['closes_at'])
            item = {'id': r['id'], 'title': r['title'], 'opens_at': r['opens_at'], 'closes_at': r['closes_at'],
                    'test_code': (r['test_code'] or '') if has_acc else '', 'regs': regs, 'joined': joined,
                    'status': _status(o, cl, now), 'locked': not has_acc}
            if not has_acc:
                item['price'] = MOCK_UZS
            out.append(item)
    res = {'ok': True, 'mocks': out, 'server_time': _iso(now)}
    if is_admin:
        res['pay_on'] = on
        res['price'] = MOCK_UZS
    return res


def handle_get(path, uid, is_admin, query=None):
    if path == '/api/mock/list':
        return listing(uid, is_admin), 200
    return None


def handle_post(path, uid, is_admin, body):
    if not path.startswith('/api/mock/'):
        return None
    _init()
    if path == '/api/mock/join':
        try:
            mid = int(body.get('id'))
        except Exception:
            return {'ok': False, 'error': 'Mock topilmadi.'}, 400
        on = pay_on()
        with _lock, _db() as c:
            r = c.execute('SELECT * FROM mocks WHERE id=?', (mid,)).fetchone()
            if not r:
                return {'ok': False, 'error': 'Mock topilmadi.'}, 404
            if _now() >= _parse(r['closes_at']):
                return {'ok': False, 'error': 'Bu mock yakunlangan.'}, 400
            if on and not is_admin and not c.execute('SELECT 1 FROM mock_access WHERE mock_id=? AND user_id=?', (mid, uid)).fetchone():
                return {'ok': False, 'need_pay': True, 'mock_id': mid, 'price': MOCK_UZS, 'error': 'Bu mock uchun to‘lov kerak.'}, 402
            c.execute('INSERT OR IGNORE INTO mock_regs(mock_id,user_id,joined_at) VALUES(?,?,?)', (mid, uid, _iso(_now())))
        return {'ok': True}, 200
    if not is_admin:
        return {'ok': False, 'error': 'Faqat admin.'}, 403
    if path == '/api/mock/create':
        title = re.sub(r'\s+', ' ', str(body.get('title', '')).strip())[:120]
        try:
            o, cl = _parse(body.get('opens_at')), _parse(body.get('closes_at'))
        except Exception:
            return {'ok': False, 'error': 'Sana va vaqtni to‘g‘ri kiriting.'}, 400
        if not title:
            return {'ok': False, 'error': 'Mock nomini kiriting.'}, 400
        if cl <= o:
            return {'ok': False, 'error': 'Yopilish vaqti ochilishdan keyin bo‘lishi kerak.'}, 400
        code = re.sub(r'[^A-Za-z0-9\-]', '', str(body.get('test_code', '')))[:32].upper()
        with _lock, _db() as c:
            cur = c.execute('INSERT INTO mocks(title,opens_at,closes_at,test_code,price,created_at) VALUES(?,?,?,?,?,?)',
                            (title, _iso(o), _iso(cl), code, 0, _iso(_now())))
        return {'ok': True, 'id': cur.lastrowid}, 200
    if path == '/api/mock/payon':
        set_pay(bool(body.get('on')))
        return {'ok': True, 'pay_on': pay_on()}, 200
    try:
        mid = int(body.get('id'))
    except Exception:
        return {'ok': False, 'error': 'Mock topilmadi.'}, 400
    if path == '/api/mock/delete':
        with _lock, _db() as c:
            for t in ('mocks', 'mock_regs', 'mock_access'):
                c.execute('DELETE FROM %s WHERE %s=?' % (t, 'id' if t == 'mocks' else 'mock_id'), (mid,))
        return {'ok': True}, 200
    if path == '/api/mock/grant':
        try:
            u = int(body.get('user_id'))
        except Exception:
            return {'ok': False, 'error': 'Foydalanuvchi ID noto‘g‘ri.'}, 400
        with _lock, _db() as c:
            c.execute('INSERT OR IGNORE INTO mock_access(mock_id,user_id) VALUES(?,?)', (mid, u))
        return {'ok': True}, 200
    return {'ok': False, 'error': 'Noma’lum so‘rov.'}, 404
