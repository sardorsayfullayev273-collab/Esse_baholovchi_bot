# v60: Mock imtihonlar (Mini App «Mock» bo'limi). Admin boshqaradi; hozircha bepul (price=0).
# To'lov admin yoqmaguncha o'chiq (mock_settings.pay_on). Foydalanuvchiga «bepul» yozuvi ko'rsatilmaydi. 1 ta mock = MOCK_UZS (10 000 so'm), karta orqali.
import os, re
from datetime import datetime, timezone

_db = None
_lock = None
_ready = False

MOCK_UZS = int(os.getenv('MOCK_UZS', '10000') or 10000)   # 1 ta mock narxi (so'm)
MOCK_EXPERT_UZS = int(os.getenv('MOCK_EXPERT_UZS', '5000') or 5000)   # v67: Mock kunlari ekspert esse tekshiruvi aksiya narxi (so'm)
# v67: Mock savollari bo'yicha mavzular xaritasi (xato savollar tahlili shu bo'yicha). Admin keyin o'zgartirishi mumkin (ustoz paneli → fan xaritasi).
MOCK_FANMAP = ("Tilshunoslik nazariyasi: 1-12\nBadiiy asar: 13-17\nIlmiy matn: 18-22\nBadiiy matn: 23-27\n"
               "G‘azal: 28-32\nLingvistik tahlil: 33-41\nMumtoz tahlil: 42-44")


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
        # v74: mock testining PDF varianti (Telegram file_id; serverda fayl saqlanmaydi)
        c.execute('CREATE TABLE IF NOT EXISTS mock_pdfs(id INTEGER PRIMARY KEY AUTOINCREMENT, mock_id INTEGER NOT NULL, title TEXT NOT NULL DEFAULT \'\', file_id TEXT NOT NULL, size INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS mock_pdf_sent(pdf_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY(pdf_id,user_id))')
        try: c.execute("ALTER TABLE mocks ADD COLUMN reg_until TEXT DEFAULT ''")
        except Exception: pass
        try: c.execute("ALTER TABLE mocks ADD COLUMN published_at TEXT DEFAULT ''")   # v68: natijalar e'lon qilingan vaqt
        except Exception: pass
        c.execute('CREATE TABLE IF NOT EXISTS mock_published_results(mock_code TEXT NOT NULL, user_id INTEGER NOT NULL, data_json TEXT NOT NULL, PRIMARY KEY(mock_code,user_id))')
        # v67: ekspert orqali esse tekshiruvi (Mock aksiyasi)
        c.execute('CREATE TABLE IF NOT EXISTS mock_expert_pending(user_id INTEGER PRIMARY KEY, mock_code TEXT NOT NULL, created_at TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS mock_expert_jobs(job_id INTEGER PRIMARY KEY, mock_code TEXT NOT NULL, user_id INTEGER NOT NULL, created_at TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS mock_expert_scores(mock_code TEXT NOT NULL, user_id INTEGER NOT NULL, score REAL NOT NULL, job_id INTEGER, created_at TEXT NOT NULL, PRIMARY KEY(mock_code,user_id))')
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
    if uid is None or not is_joined(uid, r['id']):   # v67: test faqat «Qatnashaman» degan foydalanuvchiga ochiladi
        return {'ok': False, 'need_join': True, 'mock_id': r['id'], 'error': 'Bu mock testida faqat ro‘yxatdan o‘tganlar qatnasha oladi. «Mock» bo‘limida «Qatnashaman» tugmasini bosgan bo‘lishingiz kerak.'}, 403
    if not has_access(uid, r['id']):
        return {'ok': False, 'need_pay': True, 'mock_id': r['id'], 'price': MOCK_UZS, 'error': 'Bu mock uchun to‘lov kerak.'}, 402
    return None


def _now():
    return datetime.now(timezone.utc)


def is_joined(uid, mid):
    _init()
    with _lock, _db() as c:
        return c.execute('SELECT 1 FROM mock_regs WHERE mock_id=? AND user_id=?', (int(mid), int(uid))).fetchone() is not None


def by_code(code):
    """Test kodi bo'yicha mock qatori (yo'q bo'lsa None)."""
    code = str(code or '').upper().strip()
    if not code: return None
    _init()
    with _lock, _db() as c:
        return c.execute('SELECT * FROM mocks WHERE test_code=? ORDER BY opens_at DESC LIMIT 1', (code,)).fetchone()


def is_published(code):
    """Mock natijalari admin tomonidan e'lon qilinganmi."""
    try:
        r = by_code(code)
        return bool(r) and bool((r['published_at'] or '').strip())
    except Exception:
        return False


def publish_mark(mid):
    _init()
    with _lock, _db() as c:
        c.execute('UPDATE mocks SET published_at=? WHERE id=?', (_iso(_now()), int(mid)))


def snapshot_set(code, uid, data):
    import json as _j
    _init()
    with _lock, _db() as c:
        c.execute('INSERT OR REPLACE INTO mock_published_results(mock_code,user_id,data_json) VALUES(?,?,?)', (str(code).upper(), int(uid), _j.dumps(data, ensure_ascii=False)))


def snapshot_get(code, uid):
    import json as _j
    _init()
    with _lock, _db() as c:
        r = c.execute('SELECT data_json FROM mock_published_results WHERE mock_code=? AND user_id=?', (str(code).upper(), int(uid))).fetchone()
    return _j.loads(r[0]) if r else None


def history(uid, limit=8):
    """v71: talabgorning e'lon qilingan mocklari bo'yicha ball dinamikasi (eskidan yangiga)."""
    import json as _j
    _init()
    with _lock, _db() as c:
        rows = c.execute("SELECT p.mock_code AS code, p.data_json AS dj, m.title AS title, m.opens_at AS at FROM mock_published_results p "
                         "JOIN mocks m ON UPPER(m.test_code)=p.mock_code WHERE p.user_id=? ORDER BY m.opens_at", (int(uid),)).fetchall()
    out = []
    for r in rows:
        try:
            d = _j.loads(r['dj']); sc = d.get('combined_score_75')
            if sc is None: continue
            out.append({'code': r['code'], 'title': r['title'], 'score': float(sc), 'level': d.get('level'), 'place': d.get('place'), 'total': d.get('total'), 'date': str(r['at'])[:10]})
        except Exception:
            continue
    return out[-limit:]


def class_trend(limit=8):
    """v71: e'lon qilingan mocklar bo'yicha sinf o'rtachasi, sertifikatdan o'tganlar foizi (eskidan yangiga)."""
    import json as _j
    _init()
    with _lock, _db() as c:
        rows = c.execute("SELECT p.mock_code AS code, p.data_json AS dj, m.title AS title, m.opens_at AS at FROM mock_published_results p "
                         "JOIN mocks m ON UPPER(m.test_code)=p.mock_code ORDER BY m.opens_at").fetchall()
    agg = {}
    for r in rows:
        try: sc = _j.loads(r['dj']).get('combined_score_75')
        except Exception: continue
        if sc is None: continue
        a = agg.setdefault(r['code'], {'title': r['title'], 'at': str(r['at'])[:10], 'v': []}); a['v'].append(float(sc))
    out = [{'code': k, 'title': a['title'], 'date': a['at'], 'n': len(a['v']), 'mean': round(sum(a['v']) / len(a['v']), 1),
            'pass_pct': round(100 * sum(1 for x in a['v'] if x >= 46) / len(a['v']))} for k, a in agg.items() if a['v']]
    out.sort(key=lambda x: x['date'])
    return out[-limit:]


def is_mock_code(code):
    try: return by_code(code) is not None
    except Exception: return False


def reg_deadline(r):
    """Ro'yxatga olish tugash vaqti (belgilanmagan bo'lsa — test ochilishi)."""
    try:
        ru = r['reg_until']
    except Exception:
        ru = ''
    return _parse(ru) if ru else _parse(r['opens_at'])


def promo_mock(uid, is_admin=False):
    """Ekspert aksiyasi: hozir OCHIQ (boshlangan, tugamagan) mock va foydalanuvchi unga ro'yxatdan o'tgan bo'lsa — shu mock qatori."""
    _init()
    now = _now()
    with _lock, _db() as c:
        rows = c.execute("SELECT * FROM mocks WHERE test_code<>'' ORDER BY opens_at DESC LIMIT 20").fetchall()
        for r in rows:
            if _parse(r['opens_at']) <= now < _parse(r['closes_at']):
                if is_admin or c.execute('SELECT 1 FROM mock_regs WHERE mock_id=? AND user_id=?', (r['id'], int(uid))).fetchone():
                    return r
    return None


# ---- ekspert orqali esse tekshiruvi (Mock)
def expert_pending_set(uid, code):
    _init()
    with _lock, _db() as c:
        c.execute('INSERT OR REPLACE INTO mock_expert_pending(user_id,mock_code,created_at) VALUES(?,?,?)', (int(uid), str(code).upper(), _iso(_now())))


def expert_pending_get(uid):
    _init()
    with _lock, _db() as c:
        r = c.execute('SELECT mock_code FROM mock_expert_pending WHERE user_id=?', (int(uid),)).fetchone()
    return r[0] if r else None


def expert_pending_clear(uid):
    _init()
    with _lock, _db() as c:
        c.execute('DELETE FROM mock_expert_pending WHERE user_id=?', (int(uid),))


def expert_job_link(job_id, code, uid):
    _init()
    with _lock, _db() as c:
        c.execute('INSERT OR REPLACE INTO mock_expert_jobs(job_id,mock_code,user_id,created_at) VALUES(?,?,?,?)', (int(job_id), str(code).upper(), int(uid), _iso(_now())))


def expert_job_info(job_id):
    _init()
    with _lock, _db() as c:
        r = c.execute('SELECT job_id,mock_code,user_id FROM mock_expert_jobs WHERE job_id=?', (int(job_id),)).fetchone()
    return dict(r) if r else None


def expert_job_for(uid, code):
    """Foydalanuvchining shu mock uchun ekspertga yuborgan oxirgi esse ishi (yo'q bo'lsa None)."""
    _init()
    with _lock, _db() as c:
        r = c.execute('SELECT job_id FROM mock_expert_jobs WHERE user_id=? AND mock_code=? ORDER BY job_id DESC LIMIT 1', (int(uid), str(code).upper())).fetchone()
    return int(r[0]) if r else None


def expert_score_set(code, uid, score, job_id=None):
    _init()
    with _lock, _db() as c:
        c.execute('INSERT OR REPLACE INTO mock_expert_scores(mock_code,user_id,score,job_id,created_at) VALUES(?,?,?,?,?)', (str(code).upper(), int(uid), float(score), job_id, _iso(_now())))


def expert_score_get(code, uid):
    _init()
    with _lock, _db() as c:
        r = c.execute('SELECT score FROM mock_expert_scores WHERE mock_code=? AND user_id=?', (str(code).upper(), int(uid))).fetchone()
    return float(r[0]) if r else None


MAX_PDFS = 10


def pdf_list(mid):
    _init()
    with _lock, _db() as c:
        rows = c.execute('SELECT id,title,size FROM mock_pdfs WHERE mock_id=? ORDER BY id', (int(mid),)).fetchall()
    return [{'id': r['id'], 'title': r['title'], 'size': r['size']} for r in rows]


def pdf_get(pid):
    _init()
    with _lock, _db() as c:
        r = c.execute('SELECT * FROM mock_pdfs WHERE id=?', (int(pid),)).fetchone()
    return dict(r) if r else None


def pdf_add(mid, file_id, title, size=0):
    _init()
    with _lock, _db() as c:
        if c.execute('SELECT COUNT(*) FROM mock_pdfs WHERE mock_id=?', (int(mid),)).fetchone()[0] >= MAX_PDFS: return None
        cur = c.execute('INSERT INTO mock_pdfs(mock_id,title,file_id,size,created_at) VALUES(?,?,?,?,?)', (int(mid), (title or '').strip()[:150] or 'Test (PDF)', file_id, int(size or 0), _iso(_now())))
        return cur.lastrowid


def pdf_del(mid, pid):
    _init()
    with _lock, _db() as c:
        cur = c.execute('DELETE FROM mock_pdfs WHERE id=? AND mock_id=?', (int(pid), int(mid)))
        c.execute('DELETE FROM mock_pdf_sent WHERE pdf_id=?', (int(pid),))
        return cur.rowcount > 0


def pdf_sent_mark(pid, uid):
    with _lock, _db() as c:
        c.execute('INSERT OR IGNORE INTO mock_pdf_sent(pdf_id,user_id) VALUES(?,?)', (int(pid), int(uid)))


def pdf_unsent(pid, mid):
    """Ro'yxatdan o'tgan, lekin shu PDF hali yuborilmagan foydalanuvchilar."""
    _init()
    with _lock, _db() as c:
        return [x[0] for x in c.execute('SELECT user_id FROM mock_regs WHERE mock_id=? AND user_id NOT IN (SELECT user_id FROM mock_pdf_sent WHERE pdf_id=?)', (int(mid), int(pid))).fetchall()]


def pdf_visible(uid, r, is_admin):
    """PDF ni ko'ra/ola oladimi: admin, yoki ro'yxatdan o'tgan (va to'lagan) foydalanuvchi — mock OCHIQ paytda."""
    if is_admin: return True
    if not uid or not r: return False
    now = _now()
    if not (_parse(r['opens_at']) <= now < _parse(r['closes_at'])): return False
    return is_joined(uid, r['id']) and has_access(uid, r['id'])


def regs_of(code):
    """Shu mockka ro'yxatdan o'tgan foydalanuvchi id lari."""
    r = by_code(code)
    if not r: return []
    with _lock, _db() as c:
        return [x[0] for x in c.execute('SELECT user_id FROM mock_regs WHERE mock_id=?', (r['id'],)).fetchall()]


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
            ru = reg_deadline(r)
            st = _status(o, cl, now)
            # v67: test kodi (va «Boshlash») faqat ro'yxatdan o'tganga / adminga ko'rinadi
            show_code = has_acc and (joined or is_admin)
            item = {'id': r['id'], 'title': r['title'], 'opens_at': r['opens_at'], 'closes_at': r['closes_at'],
                    'reg_until': _iso(ru), 'reg_open': now < ru, 'has_test': bool(r['test_code']),
                    'test_code': (r['test_code'] or '') if show_code else '', 'regs': regs, 'joined': joined,
                    'status': st, 'locked': not has_acc, 'published': bool((r['published_at'] or '').strip()),
                    'pdf_n': (c.execute('SELECT COUNT(*) FROM mock_pdfs WHERE mock_id=?', (r['id'],)).fetchone()[0] if (joined or is_admin) else 0)}
            if st == 'open' and (joined or is_admin) and r['test_code']:
                item['expert_promo'] = {'uzs': MOCK_EXPERT_UZS}   # aksiya narxi FAQAT mock boshlangach va faqat qatnashuvchiga ko'rinadi
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
            if _now() >= reg_deadline(r):
                return {'ok': False, 'error': 'Ro‘yxatga olish yopilgan.'}, 400
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
        ru_raw = str(body.get('reg_until', '') or '').strip()
        try: ru = _parse(ru_raw) if ru_raw else o
        except Exception: return {'ok': False, 'error': 'Ro‘yxatga olish tugash vaqtini to‘g‘ri kiriting.'}, 400
        if ru > cl: return {'ok': False, 'error': 'Ro‘yxatga olish mock yopilishidan oldin tugashi kerak.'}, 400
        if not code: return {'ok': False, 'error': 'Mockka test kerak: avval testni kiriting.'}, 400   # v69
        with _lock, _db() as c:
            if c.execute('SELECT 1 FROM mocks WHERE test_code=?', (code,)).fetchone():
                return {'ok': False, 'error': 'Bu test kodi boshqa mockka biriktirilgan.'}, 400
        with _lock, _db() as c:
            cur = c.execute('INSERT INTO mocks(title,opens_at,closes_at,test_code,price,created_at,reg_until) VALUES(?,?,?,?,?,?,?)',
                            (title, _iso(o), _iso(cl), code, 0, _iso(_now()), _iso(ru)))
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
            for t in ('mocks', 'mock_regs', 'mock_access', 'mock_pdfs'):
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
