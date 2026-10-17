"""v72: o'quv markazi — xatolar daftari (intervalli takrorlash), kunlik reja holati, zaif mavzular, ball bashorati.

Hamma jadval national_certificate.db() bazasida. Hech qanday AI chaqirilmaydi — xarajat yo'q.
Mini app bilan aloqa: bot-1-1.py ichida /api/hub/* yo'llari handle_get / handle_post ga uzatiladi
(mock_mod bilan bir xil usul: (payload, status) yoki None qaytaradi).
"""
import json
import time
from datetime import datetime, timedelta, timezone

from national_certificate import db, now

UZ = timezone(timedelta(hours=5))
INTERVALS = (1, 3, 7, 14)            # kun: xato qilingan savol shu oraliqlarda qaytadi
MAX_ITEMS_PER_SYNC = 30              # bitta so'rovdagi eng ko'p savol
MAX_PAYLOAD = 2500                   # bitta savol ma'lumoti (belgilar)
MAX_TOTAL_MISTAKES = 400             # bitta foydalanuvchida saqlanadigan eng ko'p xato
DUE_BATCH = 10                       # bir takrorlash seansidagi savollar
PLAN_TASKS = ('daily', 'mistakes', 'topic', 'essay')
LEVELS = ((46, 'C'), (50, 'C+'), (55, 'B'), (60, 'B+'), (65, 'A'), (70, 'A+'))   # national_certificate.level_for bilan bir xil

_rl = {}


def _allow(key, limit, per):
    t = time.time()
    arr = [x for x in _rl.get(key, []) if t - x < per]
    if len(arr) >= limit:
        _rl[key] = arr
        return False
    arr.append(t)
    _rl[key] = arr
    if len(_rl) > 5000:
        for k in list(_rl)[:1000]:
            _rl.pop(k, None)
    return True


def today(offset=0):
    return (datetime.now(UZ) + timedelta(days=offset)).strftime('%Y-%m-%d')


def init():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS lh_mistakes(
            user_id INTEGER NOT NULL, qkey TEXT NOT NULL, payload TEXT NOT NULL, topic TEXT NOT NULL DEFAULT '',
            wrong_n INTEGER NOT NULL DEFAULT 1, stage INTEGER NOT NULL DEFAULT 0,
            due_day TEXT NOT NULL, last_day TEXT NOT NULL, PRIMARY KEY(user_id, qkey))''')
        c.execute('CREATE INDEX IF NOT EXISTS ix_lh_mistakes_due ON lh_mistakes(user_id, due_day)')
        c.execute('''CREATE TABLE IF NOT EXISTS lh_plan(
            user_id INTEGER NOT NULL, day TEXT NOT NULL, task TEXT NOT NULL, PRIMARY KEY(user_id, day, task))''')
        c.execute('''CREATE TABLE IF NOT EXISTS lh_topic(
            user_id INTEGER NOT NULL, topic TEXT NOT NULL, correct INTEGER NOT NULL DEFAULT 0,
            total INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id, topic))''')
        c.execute('''CREATE TABLE IF NOT EXISTS lh_reports(
            user_id INTEGER NOT NULL, qkey TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, PRIMARY KEY(user_id, qkey))''')
        c.execute('''CREATE TABLE IF NOT EXISTS lh_qstats(
            qkey TEXT PRIMARY KEY, shown INTEGER NOT NULL DEFAULT 0, correct INTEGER NOT NULL DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS lh_digest(user_id INTEGER PRIMARY KEY, day TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS lh_override(
            qid INTEGER PRIMARY KEY, hide INTEGER NOT NULL, created TEXT NOT NULL)''')
        c.commit()


# ------------------------------------------------------------------ xatolar daftari
def _clean_topic(t):
    t = str(t or '')[:16]
    return ''.join(ch for ch in t if ch.isalnum() or ch in '_-')


def sync(uid, items):
    """items: [{key, payload(dict), topic, ok(bool)}].
    ok=False  -> daftarga qo'shiladi (yoki 1-bosqichga qaytadi), ertaga takrorlanadi.
    ok=True   -> faqat daftarda bor va muddati kelgan savol bo'lsa keyingi bosqichga o'tadi; 14 kundan keyin to'g'ri bo'lsa o'chadi.
    Mavzu statistikasi har bir javobdan yangilanadi (qurilmalararo saqlanadi)."""
    uid = int(uid)
    td, tm = today(), today(1)
    changed = 0
    with db() as c:
        total = c.execute('SELECT COUNT(*) FROM lh_mistakes WHERE user_id=?', (uid,)).fetchone()[0]
        for it in items[:MAX_ITEMS_PER_SYNC]:
            if not isinstance(it, dict):
                continue
            key = str(it.get('key') or '')[:300]
            if not key:
                continue
            ok = bool(it.get('ok'))
            topic = _clean_topic(it.get('topic'))
            if key[:1] == 'b' and key[1:].isdigit():   # bank savoli: umumiy statistika (qiyinlik va noto'g'ri kalitni aniqlash uchun)
                c.execute('INSERT OR IGNORE INTO lh_qstats(qkey,shown,correct) VALUES(?,0,0)', (key,))
                c.execute('UPDATE lh_qstats SET shown=shown+1, correct=correct+? WHERE qkey=?', (1 if ok else 0, key))
            if topic:
                c.execute('INSERT OR IGNORE INTO lh_topic(user_id,topic,correct,total) VALUES(?,?,0,0)', (uid, topic))
                c.execute('UPDATE lh_topic SET correct=correct+?, total=total+1 WHERE user_id=? AND topic=?', (1 if ok else 0, uid, topic))
            row = c.execute('SELECT stage, due_day FROM lh_mistakes WHERE user_id=? AND qkey=?', (uid, key)).fetchone()
            if not ok:
                payload = it.get('payload')
                pj = json.dumps(payload, ensure_ascii=False) if payload is not None else ''
                if row is None:
                    if not pj or len(pj) > MAX_PAYLOAD or total >= MAX_TOTAL_MISTAKES:
                        continue
                    c.execute('INSERT INTO lh_mistakes(user_id,qkey,payload,topic,wrong_n,stage,due_day,last_day) VALUES(?,?,?,?,1,0,?,?)',
                              (uid, key, pj, topic, tm, td))
                    total += 1
                else:
                    c.execute('UPDATE lh_mistakes SET wrong_n=wrong_n+1, stage=0, due_day=?, last_day=? WHERE user_id=? AND qkey=?',
                              (tm, td, uid, key))
                changed += 1
            elif row is not None and row['due_day'] <= td:
                nxt = int(row['stage']) + 1
                if nxt >= len(INTERVALS):
                    c.execute('DELETE FROM lh_mistakes WHERE user_id=? AND qkey=?', (uid, key))   # o'zlashtirildi
                else:
                    c.execute('UPDATE lh_mistakes SET stage=?, due_day=?, last_day=? WHERE user_id=? AND qkey=?',
                              (nxt, today(INTERVALS[nxt]), td, uid, key))
                changed += 1
        c.commit()
    return changed


def due_items(uid, limit=DUE_BATCH):
    with db() as c:
        rows = c.execute('SELECT qkey,payload,topic,stage,wrong_n FROM lh_mistakes WHERE user_id=? AND due_day<=? '
                         'ORDER BY stage ASC, wrong_n DESC LIMIT ?', (int(uid), today(), int(limit))).fetchall()
    out = []
    for r in rows:
        try:
            p = json.loads(r['payload'])
        except Exception:
            continue
        out.append({'key': r['qkey'], 'payload': p, 'topic': r['topic'], 'stage': r['stage'], 'wrong_n': r['wrong_n']})
    return out


def counts(uid):
    with db() as c:
        r = c.execute('SELECT COUNT(*) n, SUM(CASE WHEN due_day<=? THEN 1 ELSE 0 END) d FROM lh_mistakes WHERE user_id=?',
                      (today(), int(uid))).fetchone()
    return int(r['n'] or 0), int(r['d'] or 0)


# ------------------------------------------------------------------ kunlik reja
def mark_done(uid, task):
    if task not in PLAN_TASKS:
        return False
    with db() as c:
        c.execute('INSERT OR IGNORE INTO lh_plan(user_id,day,task) VALUES(?,?,?)', (int(uid), today(), task))
        c.execute('DELETE FROM lh_plan WHERE user_id=? AND day<?', (int(uid), today(-7)))
        c.commit()
    return True


def done_today(uid):
    with db() as c:
        return [r['task'] for r in c.execute('SELECT task FROM lh_plan WHERE user_id=? AND day=?', (int(uid), today())).fetchall()]


# ------------------------------------------------------------------ zaif mavzular
def topics(uid):
    with db() as c:
        rows = c.execute('SELECT topic,correct,total FROM lh_topic WHERE user_id=?', (int(uid),)).fetchall()
    out = [{'c': r['topic'], 'ok': int(r['correct']), 't': int(r['total'])} for r in rows if int(r['total']) > 0]
    for x in out:
        x['p'] = round(x['ok'] * 100.0 / x['t'])
    return out


# ------------------------------------------------------------------ ball bashorati
def forecast(uid):
    """So'nggi diagnostik urinishlardan taxminiy ball. Rasmiy natija emas (bot hisobi). Urinish bo'lmasa None."""
    try:
        with db() as c:
            rows = c.execute('SELECT diagnostic_score FROM national_attempts WHERE user_id=? AND diagnostic_score IS NOT NULL '
                             'ORDER BY id DESC LIMIT 3', (int(uid),)).fetchall()
    except Exception:
        return None
    sc = [float(r[0]) for r in rows if r[0] is not None]
    if not sc:
        return None
    # eng yangisiga ko'proq og'irlik
    w = [3, 2, 1][:len(sc)]
    est = sum(s * k for s, k in zip(sc, w)) / sum(w)
    est = round(est, 1)
    level, nxt = None, None
    for th, name in LEVELS:
        if est >= th:
            level = name
        elif nxt is None:
            nxt = (name, th, round(th - est, 1))
    return {'score': est, 'max': 75, 'level': level or 'Sertifikat berilmadi', 'next_level': nxt[0] if nxt else None,
            'next_gap': nxt[2] if nxt else 0, 'attempts': len(sc)}


# ------------------------------------------------------------------ savol sifati: shikoyat, yashirish, hisobot
HIDE_AFTER = 3                                   # shuncha FOYDALANUVCHI shikoyat qilsa savol o'zi yashiriladi
REASONS = {'xato': 'javob noto‘g‘ri', 'matn': 'matn tushunarsiz', 'oson': 'juda oson', 'boshqa': 'boshqa'}


def report(uid, qkey, reason):
    qkey = str(qkey or '')[:300]
    if not qkey:
        return None
    reason = reason if reason in REASONS else 'boshqa'
    with db() as c:
        c.execute('INSERT OR REPLACE INTO lh_reports(user_id,qkey,reason,created) VALUES(?,?,?,?)', (int(uid), qkey, reason, now()))
        n = c.execute('SELECT COUNT(*) FROM lh_reports WHERE qkey=?', (qkey,)).fetchone()[0]
        c.commit()
    return n


def hidden_ids():
    """O'yinlarda ko'rsatilmaydigan bank savollarining id lari (shikoyat >= HIDE_AFTER yoki admin yashirgan; admin «och» degan bo'lsa ko'rsatiladi)."""
    with db() as c:
        rows = c.execute("SELECT qkey FROM lh_reports WHERE qkey GLOB 'b[0-9]*' GROUP BY qkey HAVING COUNT(*) >= ?", (HIDE_AFTER,)).fetchall()
        ov = {r['qid']: r['hide'] for r in c.execute('SELECT qid,hide FROM lh_override').fetchall()}
    ids = {int(r['qkey'][1:]) for r in rows if r['qkey'][1:].isdigit()}
    for qid, h in ov.items():
        (ids.add if h else ids.discard)(qid)
    return sorted(ids)


def set_override(qid, hide):
    with db() as c:
        c.execute('INSERT INTO lh_override(qid,hide,created) VALUES(?,?,?) ON CONFLICT(qid) DO UPDATE SET hide=excluded.hide, created=excluded.created',
                  (int(qid), 1 if hide else 0, now()))
        c.commit()


_BANK_CACHE = {}


def _bank_text(qid):
    """Hisobotda savol matnini ko'rsatish uchun (miniapp/*.json banklaridan)."""
    if not _BANK_CACHE:
        import glob, os
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miniapp')
        for fp in glob.glob(os.path.join(base, '*_bank.json')) + glob.glob(os.path.join(base, 'leks_*.json')) + glob.glob(os.path.join(base, 'dtm19_*.json')):
            try:
                for x in json.load(open(fp, encoding='utf-8')):
                    if isinstance(x, dict) and 'id' in x:
                        _BANK_CACHE[int(x['id'])] = ((x.get('q') or '').replace('\n', ' ')[:90], os.path.basename(fp))
            except Exception:
                pass
    return _BANK_CACHE.get(int(qid), ('', ''))


def report_text(limit=12):
    hid = set(hidden_ids())
    with db() as c:
        rep = c.execute('SELECT qkey, COUNT(*) n, GROUP_CONCAT(reason) rs FROM lh_reports GROUP BY qkey ORDER BY n DESC, MAX(created) DESC LIMIT ?', (limit,)).fetchall()
        sus = c.execute('SELECT qkey, shown, correct FROM lh_qstats WHERE shown>=20 AND (correct*1.0/shown<0.15 OR correct*1.0/shown>0.97) ORDER BY shown DESC LIMIT ?', (limit,)).fetchall()
    out = ['🧪 SAVOL SIFATI HISOBOTI', '']
    out.append('📣 Shikoyat qilingan savollar:' if rep else '📣 Shikoyatlar hozircha yo‘q.')
    for r in rep:
        k = r['qkey']; qid = int(k[1:]) if k[:1] == 'b' and k[1:].isdigit() else None
        cnt = {}
        for x in (r['rs'] or '').split(','):
            cnt[x] = cnt.get(x, 0) + 1
        why = ', '.join(f"{REASONS.get(a, a)}×{b}" for a, b in cnt.items())
        txt = _bank_text(qid)[0] if qid else k[:70]
        out.append(f"• {k} — {r['n']} ta ({why}){' 🙈 yashirilgan' if qid in hid else ''}\n   {txt}")
    if sus:
        out += ['', '📊 Shubhali savollar (javoblar statistikasi):']
        for r in sus:
            k = r['qkey']; qid = int(k[1:]); pct = round(r['correct'] * 100 / r['shown'])
            out.append(f"• {k} — {r['shown']} marta berilgan, to‘g‘ri javob {pct}% ({'kalit xato bo‘lishi mumkin' if pct < 50 else 'juda oson'})\n   {_bank_text(qid)[0]}")
    out += ['', 'Yashirish: /savol_yashir <id>   Qaytarish: /savol_och <id>']
    return '\n'.join(out)


# ------------------------------------------------------------------ haftalik shaxsiy hisobot (botdan yuboriladi)
CAT_NAMES = {'imlo': 'Imlo', 'soz': 'So‘z yasalishi', 'morf': 'Morfologiya', 'sint': 'Sintaksis', 'punk': 'Punktuatsiya', 'leks': 'Leksikologiya',
             'usl': 'Uslubiyat', 'nazar': 'Mumtoz adabiyot', 'tarix': 'Badiiy asarlar', 'matn': 'Matn bilan ishlash'}
DIGEST_WEEKDAY, DIGEST_HOUR = 6, 18          # yakshanba, 18:00 (Toshkent) dan keyin


def _iso_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec='seconds')


def _week_stats(c, uid, start, end):
    r = c.execute('SELECT COUNT(*) n, COALESCE(SUM(correct),0) ok, COALESCE(SUM(total),0) t FROM game_plays WHERE user_id=? AND created_at>=? AND created_at<?',
                  (int(uid), start, end)).fetchone()
    return int(r['n']), int(r['ok']), int(r['t'])


def digest_message(uid):
    """(matn | None). So'nggi 7 kunda o'ynamagan bo'lsa None."""
    with db() as c:
        n, ok, t = _week_stats(c, uid, _iso_ago(7), _iso_ago(-1))
        if not n or not t:
            return None
        _n0, ok0, t0 = _week_stats(c, uid, _iso_ago(14), _iso_ago(7))
    acc = round(ok * 100 / t)
    lines = ['📊 Haftalik hisobotingiz', '', f'✅ {t} ta savolga javob berdingiz, to‘g‘ri javoblar: {acc}%']
    if t0:
        d = acc - round(ok0 * 100 / t0)
        if d:
            lines[-1] += f' ({"+" if d > 0 else ""}{d}% o‘tgan haftaga nisbatan)'
    try:
        from growth_tests import get_streak
        st = get_streak(uid)
        if st.get('current'):
            lines.append(f'🔥 Seriya: {st["current"]} kun')
    except Exception:
        pass
    weak = sorted([x for x in topics(uid) if x['t'] >= 5 and x['p'] < 75], key=lambda x: x['p'])[:1]
    if weak:
        lines.append(f'🎯 Eng zaif mavzu: {CAT_NAMES.get(weak[0]["c"], weak[0]["c"])} ({weak[0]["p"]}%) — shuni mashq qiling')
    _total, due = counts(uid)
    if due:
        lines.append(f'📒 Xatolar daftarida {due} ta savol sizni kutmoqda')
    f = forecast(uid)
    if f:
        lines.append(f'📈 Taxminiy ball: {f["score"]}/{f["max"]}' + (f' — {f["next_level"]} darajagacha {f["next_gap"]} ball qoldi' if f.get('next_level') else ''))
    lines += ['', 'Yangi hafta — yangi imkoniyat. Bugun 5 daqiqa mashq qilib ko‘ring! 💪']
    return '\n'.join(lines)


def digest_candidates(limit=400):
    """Yakshanba kechqurun: oxirgi 7 kunda o'ynagan, bu hafta hisobot olmagan foydalanuvchilar. Yuborilgan deb belgilanadi (qayta chiqmaydi)."""
    n = datetime.now(UZ)
    if n.weekday() != DIGEST_WEEKDAY or n.hour < DIGEST_HOUR:
        return []
    td = today()
    try:
        with db() as c:
            rows = c.execute('SELECT DISTINCT user_id FROM game_plays WHERE created_at>=? AND user_id NOT IN (SELECT user_id FROM lh_digest WHERE day=?) LIMIT ?',
                             (_iso_ago(7), td, int(limit))).fetchall()
            ids = [int(r['user_id']) for r in rows]
            c.executemany('INSERT INTO lh_digest(user_id,day) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET day=excluded.day', [(i, td) for i in ids])
            c.commit()
    except Exception:
        return []
    return ids


# ------------------------------------------------------------------ HTTP
def handle_get(path, uid):
    if not path.startswith('/api/hub/'):
        return None
    if not uid:
        return {'ok': False, 'error': 'Foydalanuvchi aniqlanmadi.'}, 400
    if not _allow('g%s' % uid, 60, 60):
        return {'ok': False, 'error': 'Juda ko‘p so‘rov.'}, 429
    if path == '/api/hub/home':
        total, due = counts(uid)
        return {'ok': True, 'day': today(), 'done': done_today(uid), 'mistakes_total': total, 'mistakes_due': due,
                'topics': topics(uid), 'forecast': forecast(uid)}, 200
    if path == '/api/hub/hidden':
        return {'ok': True, 'ids': hidden_ids()}, 200
    if path == '/api/hub/mistakes':
        total, due = counts(uid)
        return {'ok': True, 'items': due_items(uid), 'due': due, 'total': total}, 200
    return {'ok': False, 'error': 'Not found'}, 404


def handle_post(path, uid, body):
    if not path.startswith('/api/hub/'):
        return None
    if not uid:
        return {'ok': False, 'error': 'Foydalanuvchi aniqlanmadi.'}, 400
    if not _allow('p%s' % uid, 40, 60):
        return {'ok': False, 'error': 'Juda ko‘p so‘rov.'}, 429
    body = body if isinstance(body, dict) else {}
    if path == '/api/hub/sync':
        items = body.get('items')
        if not isinstance(items, list):
            return {'ok': False, 'error': 'items kerak'}, 400
        sync(uid, items)
        total, due = counts(uid)
        return {'ok': True, 'mistakes_total': total, 'mistakes_due': due}, 200
    if path == '/api/hub/report':
        n = report(uid, body.get('key'), str(body.get('reason') or ''))
        if n is None:
            return {'ok': False, 'error': 'key kerak'}, 400
        return {'ok': True, 'count': n}, 200
    if path == '/api/hub/done':
        if not mark_done(uid, str(body.get('task') or '')):
            return {'ok': False, 'error': 'Noma’lum topshiriq'}, 400
        return {'ok': True, 'done': done_today(uid)}, 200
    return {'ok': False, 'error': 'Not found'}, 404
