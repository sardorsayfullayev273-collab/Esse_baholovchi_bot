"""v27: test havolasi orqali kelganlar, ustozga bonus, ustoz paneli, test reytingi, eslatmalar va kunlik seriya.

Hamma jadvallar national_certificate.db() bazasida. kind: 'ms' yoki 'simple'.
"""
import os
from datetime import datetime, timedelta, timezone
from national_certificate import db, now
import test_results as tr
import manual_pay as mp

UZ = timezone(timedelta(hours=5))
TEST_REF_BONUS = int(os.getenv("TEST_REF_BONUS", "1") or 1)      # yangi o'quvchi testni ishlasa, ustozga bepul esse tekshiruvi
TEST_REF_MAX = int(os.getenv("TEST_REF_MAX", "50") or 50)        # bitta ustoz oladigan eng ko'p mukofot
STREAK_REMIND_HOUR = int(os.getenv("STREAK_REMIND_HOUR", "20") or 20)   # Toshkent vaqti bilan


def init_growth_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS test_visits(
            kind TEXT NOT NULL, code TEXT NOT NULL, user_id INTEGER NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(kind, code, user_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS test_refs(
            invitee_id INTEGER PRIMARY KEY, creator_id INTEGER NOT NULL, kind TEXT NOT NULL, code TEXT NOT NULL,
            created_at TEXT NOT NULL, rewarded INTEGER NOT NULL DEFAULT 0)''')
        c.execute("CREATE INDEX IF NOT EXISTS ix_test_refs_creator ON test_refs(creator_id)")
        c.execute('''CREATE TABLE IF NOT EXISTS streaks(
            user_id INTEGER PRIMARY KEY, current INTEGER NOT NULL DEFAULT 0, best INTEGER NOT NULL DEFAULT 0,
            last_day TEXT, remind_day TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS streak_days(
            user_id INTEGER NOT NULL, day TEXT NOT NULL, PRIMARY KEY(user_id, day))''')
        # v28: mavjud foydalanuvchilarning joriy seriyasi kunlarini kalendarga bir marta to'ldiramiz
        for r in c.execute('SELECT user_id,current,last_day FROM streaks WHERE last_day IS NOT NULL AND current>0').fetchall():
            try:
                end = datetime.strptime(r['last_day'], '%Y-%m-%d').date()
            except Exception:
                continue
            for i in range(min(int(r['current']), 400)):
                c.execute('INSERT OR IGNORE INTO streak_days(user_id,day) VALUES(?,?)', (r['user_id'], (end - timedelta(days=i)).isoformat()))
        c.commit()


# ------------------------------------------------------------------ havola orqali kelish
def register_visit(kind, code, uid, is_new):
    """Havolani ochgan o'quvchini yozadi. Yangi foydalanuvchi bo'lsa — ustozga bonus uchun ham belgilanadi."""
    code = code.upper().strip(); uid = int(uid)
    m = tr.get_meta(kind, code)
    if not m:
        return
    with db() as c:
        c.execute('INSERT OR IGNORE INTO test_visits(kind,code,user_id,created_at) VALUES(?,?,?,?)', (kind, code, uid, now()))
        creator = m.get('created_by')
        if is_new and creator and int(creator) != uid:
            c.execute('INSERT OR IGNORE INTO test_refs(invitee_id,creator_id,kind,code,created_at) VALUES(?,?,?,?,?)',
                      (uid, int(creator), kind, code, now()))
        c.commit()


def reward_creator(uid, kind, code):
    """Havola orqali kelgan yangi o'quvchi shu testni ishlagach, ustozga bonus. Berilsa creator_id, aks holda None."""
    code = code.upper().strip(); uid = int(uid)
    with db() as c:
        r = c.execute('SELECT creator_id FROM test_refs WHERE invitee_id=? AND kind=? AND code=? AND rewarded=0', (uid, kind, code)).fetchone()
        if not r:
            return None
        creator = int(r['creator_id'])
        given = c.execute('SELECT COUNT(*) FROM test_refs WHERE creator_id=? AND rewarded=1', (creator,)).fetchone()[0]
        c.execute('UPDATE test_refs SET rewarded=? WHERE invitee_id=?', (1 if given < TEST_REF_MAX else 2, uid))
        c.commit()
    if given >= TEST_REF_MAX or TEST_REF_BONUS <= 0:
        return None
    mp.add_credits(creator, 'essay', TEST_REF_BONUS)
    return creator


# ------------------------------------------------------------------ test reytingi
def _name_short(uid):
    first, last, _u = tr._split_name(uid)
    return (first + (' ' + last[:1] + '.' if last else '')).strip()


def standings(kind, code):
    """Har bir o'quvchining eng yaxshi urinishi, tartiblangan: [{user_id,score,percent,correct,total}]."""
    best = {}
    for i, p in enumerate(tr.participants(kind, code)):
        score = p.get('combined') if (kind == 'ms' and p.get('combined') is not None) else p['percent']
        try: score = float(score)
        except Exception: score = 0.0
        cur = best.get(p['user_id'])
        if cur is None or score > cur['score']:
            best[p['user_id']] = {'user_id': p['user_id'], 'score': score, 'percent': p['percent'], 'correct': p['correct'], 'total': p['total'], 'order': i}
    rows = sorted(best.values(), key=lambda x: (-x['score'], x['order']))
    for n, r in enumerate(rows, 1):
        r['rank'] = n
    return rows


def top(kind, code, uid=None, limit=10):
    rows = standings(kind, code)
    out = [{'rank': r['rank'], 'name': _name_short(r['user_id']), 'percent': r['percent'], 'correct': r['correct'], 'total': r['total'],
            'score': (round(r['score'], 1) if kind == 'ms' else None), 'me': bool(uid and r['user_id'] == int(uid))} for r in rows[:limit]]
    me = next(({'rank': r['rank'], 'percent': r['percent']} for r in rows if uid and r['user_id'] == int(uid)), None)
    return {'top': out, 'me': me, 'participants': len(rows)}


def rank_of(kind, code, uid):
    rows = standings(kind, code)
    me = next((r for r in rows if r['user_id'] == int(uid)), None)
    return {'rank': me['rank'] if me else None, 'participants': len(rows)}


# ------------------------------------------------------------------ ustoz paneli
def panel(uid):
    uid = int(uid); tests = []
    with db() as c:
        for kind, tbl, att in (('simple', 'simple_tests', 'simple_attempts'), ('ms', 'national_tests', 'national_attempts')):
            for r in c.execute(f'SELECT id,code,title,created_at FROM {tbl} WHERE created_by=? ORDER BY id DESC LIMIT 100', (uid,)).fetchall():
                a = c.execute(f'SELECT COUNT(*) n, COUNT(DISTINCT user_id) u FROM {att} WHERE test_id=?', (r['id'],)).fetchone()
                visits = c.execute('SELECT COUNT(*) FROM test_visits WHERE kind=? AND code=? AND user_id<>?', (kind, r['code'], uid)).fetchone()[0]
                refs = c.execute('SELECT COUNT(*) FROM test_refs WHERE kind=? AND code=?', (kind, r['code'])).fetchone()[0]
                refd = c.execute('SELECT COUNT(*) FROM test_refs WHERE kind=? AND code=? AND rewarded=1', (kind, r['code'])).fetchone()[0]
                if kind == 'simple':
                    av = c.execute(f'SELECT AVG(correct*100.0/NULLIF(total,0)) FROM {att} WHERE test_id=?', (r['id'],)).fetchone()[0]
                else:
                    av = c.execute(f'SELECT AVG(diagnostic_score) FROM {att} WHERE test_id=?', (r['id'],)).fetchone()[0]
                inf = tr.info(kind, r['code'])
                tests.append({'kind': kind, 'code': r['code'], 'title': r['title'], 'created_at': r['created_at'], 'attempts': a['n'], 'users': a['u'],
                              'visits': visits, 'new_users': refs, 'rewarded': refd, 'closed': inf['closed'], 'closes_at': inf['closes_at'],
                              'avg': (round(av, 1) if av is not None else None), 'avg_label': ('o‘rtacha %' if kind == 'simple' else 'o‘rtacha ball /75')})
        bonus_given = c.execute('SELECT COUNT(*) FROM test_refs WHERE creator_id=? AND rewarded=1', (uid,)).fetchone()[0]
    tests.sort(key=lambda t: t['created_at'], reverse=True)
    return {'tests': tests,
            'totals': {'tests': len(tests), 'users': sum(t['users'] for t in tests), 'attempts': sum(t['attempts'] for t in tests),
                       'visits': sum(t['visits'] for t in tests), 'new_users': sum(t['new_users'] for t in tests),
                       'bonus': bonus_given * TEST_REF_BONUS, 'bonus_per_student': TEST_REF_BONUS}}


# ------------------------------------------------------------------ muddat tugashiga eslatma
def reminder_candidates():
    """Tugashiga ~1 soat qolgan, hali eslatilmagan testlar: [(kind, code, closes_at)]."""
    nowu = datetime.now(timezone.utc)
    lo, hi = tr._iso(nowu), tr._iso(nowu + timedelta(minutes=60))
    out = []
    with db() as c:
        rows = c.execute('SELECT kind,code,closes_at,set_at FROM test_deadlines WHERE finished_at IS NULL AND reminded=0 AND closes_at IS NOT NULL AND closes_at>? AND closes_at<=?', (lo, hi)).fetchall()
        for r in rows:
            c.execute('UPDATE test_deadlines SET reminded=1 WHERE kind=? AND code=?', (r['kind'], r['code']))
            try:
                if r['set_at'] and datetime.fromisoformat(r['closes_at']) - datetime.fromisoformat(r['set_at']) <= timedelta(minutes=90):
                    continue   # 1 soatlik testlarga eslatma yuborilmaydi
            except Exception:
                pass
            out.append((r['kind'], r['code'], r['closes_at']))
        c.commit()
    return out


def pending_visitors(kind, code):
    """Havolani ochgan, lekin testni hali ishlamagan foydalanuvchilar."""
    m = tr.get_meta(kind, code)
    if not m:
        return []
    att = 'simple_attempts' if kind == 'simple' else 'national_attempts'
    with db() as c:
        rows = c.execute(f'SELECT user_id FROM test_visits WHERE kind=? AND code=? AND user_id<>? AND user_id NOT IN (SELECT user_id FROM {att} WHERE test_id=?)',
                         (kind, code.upper(), int(m.get('created_by') or 0), m['id'])).fetchall()
    return [r['user_id'] for r in rows]


def counts(kind, code):
    m = tr.get_meta(kind, code)
    if not m:
        return {'users': 0, 'attempts': 0}
    att = 'simple_attempts' if kind == 'simple' else 'national_attempts'
    with db() as c:
        r = c.execute(f'SELECT COUNT(*) n, COUNT(DISTINCT user_id) u FROM {att} WHERE test_id=?', (m['id'],)).fetchone()
    return {'users': r['u'], 'attempts': r['n']}


# ------------------------------------------------------------------ kunlik seriya
def _today():
    return datetime.now(UZ).date()


def touch(uid):
    """Bugungi faoliyatni belgilaydi. {'current','best','new_today'}"""
    uid = int(uid); today = _today(); t = today.isoformat(); y = (today - timedelta(days=1)).isoformat()
    with db() as c:
        r = c.execute('SELECT current,best,last_day FROM streaks WHERE user_id=?', (uid,)).fetchone()
        c.execute('INSERT OR IGNORE INTO streak_days(user_id,day) VALUES(?,?)', (uid, t))
        if r and r['last_day'] == t:
            c.commit()
            return {'current': r['current'], 'best': r['best'], 'new_today': False}
        cur = (r['current'] + 1) if (r and r['last_day'] == y) else 1
        best = max(cur, r['best'] if r else 0)
        c.execute('''INSERT INTO streaks(user_id,current,best,last_day) VALUES(?,?,?,?)
                     ON CONFLICT(user_id) DO UPDATE SET current=excluded.current, best=excluded.best, last_day=excluded.last_day''', (uid, cur, best, t))
        c.commit()
    return {'current': cur, 'best': best, 'new_today': True}


def get_streak(uid):
    today = _today(); t = today.isoformat(); y = (today - timedelta(days=1)).isoformat()
    with db() as c:
        r = c.execute('SELECT current,best,last_day FROM streaks WHERE user_id=?', (int(uid),)).fetchone()
    if not r:
        return {'current': 0, 'best': 0, 'done_today': False}
    alive = r['last_day'] in (t, y)
    return {'current': r['current'] if alive else 0, 'best': r['best'], 'done_today': r['last_day'] == t}


def calendar(uid, year, month):
    """Oy kalendari uchun: shu oyda mashq qilingan kunlar (oy kunlari raqami) + joriy holat."""
    year = int(year); month = int(month)
    if not (2020 <= year <= 2100 and 1 <= month <= 12):
        today = _today(); year, month = today.year, today.month
    pref = '%04d-%02d-' % (year, month)
    with db() as c:
        rows = c.execute('SELECT day FROM streak_days WHERE user_id=? AND day LIKE ?', (int(uid), pref + '%')).fetchall()
    days = sorted({int(r['day'][8:10]) for r in rows})
    st = get_streak(uid); today = _today()
    return {'year': year, 'month': month, 'days': days, 'today': today.isoformat(),
            'current': st['current'], 'best': st['best'], 'done_today': st['done_today']}


def streak_reminders():
    """Bugun hali mashq qilmagan, seriyasi >=2 kun bo'lgan foydalanuvchilar (kuniga bir marta, belgilanadi): [(uid, current)]."""
    if datetime.now(UZ).hour < STREAK_REMIND_HOUR:
        return []
    today = _today(); t = today.isoformat(); y = (today - timedelta(days=1)).isoformat()
    with db() as c:
        rows = c.execute('SELECT user_id,current FROM streaks WHERE last_day=? AND current>=2 AND COALESCE(remind_day,"")<>?', (y, t)).fetchall()
        c.executemany('UPDATE streaks SET remind_day=? WHERE user_id=?', [(t, r['user_id']) for r in rows])
        c.commit()
    return [(r['user_id'], r['current']) for r in rows]
