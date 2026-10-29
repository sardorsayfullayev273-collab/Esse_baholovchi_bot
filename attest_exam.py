# -*- coding: utf-8 -*-
"""v107 — Attestatsiya (o'zbek tili va adabiyoti o'qituvchilari) test moduli.

Rasmiy tuzilma (Maktabgacha va maktab ta'limi vazirligi spetsifikatsiyasi, VM 572-son qarori):
  • jami 50 ta test topshirig'i, 90 daqiqa
  • 1–35  — mutaxassislik fani («Asosiy fan»)
  • 36–40 — kasb standarti      («Kasbiy standart»)
  • 41–50 — pedagogik mahorat   («Pedagogik mahorat»)
  • har bir to'g'ri javob — 2 ball, maksimal 100 ball
  • toifa chegaralari: 80 / 70 / 60 / 55 ball (pastda DECISION_RULES)

Test kiritish — faqat admin. Foydalanuvchilarga ochish — admin sozlamasi (att_public), standart: yopiq.
Server javoblarni test tugamaguncha MIJOZGA YUBORMAYDI.
"""
import json, re, secrets, time
from datetime import datetime, timezone, timedelta

from national_certificate import db

N_FAN, N_KASB, N_PED = 35, 5, 10
N_TOTAL = N_FAN + N_KASB + N_PED          # 50
POINTS = 2                                 # har bir to'g'ri javob
MAX_SCORE = N_TOTAL * POINTS               # 100
DURATION_MIN = 90
GRACE_SEC = 90                             # tarmoq kechikishi uchun zaxira
MAX_OBJECTIONS = 5                         # bitta urinishda e'tirozlar soni
TZ = timezone(timedelta(hours=5))          # Toshkent

# (toifa kodi, nomi, [(minimal ball, natija matni, yangi toifa)...]) — yuqoridan pastga
CATS = ["mutaxassis", "ikkinchi", "birinchi", "oliy"]
CAT_NAMES = {"mutaxassis": "Mutaxassis (toifasiz)", "ikkinchi": "Ikkinchi toifa",
             "birinchi": "Birinchi toifa", "oliy": "Oliy toifa"}
DECISION_RULES = {
    "oliy":       [(80, "Attestatsiyadan o‘tdi, oliy malaka toifasi saqlanadi.", "oliy"),
                   (70, "Attestatsiyadan o‘tmadi, birinchi malaka toifasiga tushiriladi.", "birinchi"),
                   (0,  "Attestatsiyadan o‘tmadi, ikkinchi malaka toifasiga tushiriladi.", "ikkinchi")],
    "birinchi":   [(80, "Attestatsiyadan o‘tdi, oliy malaka toifasi beriladi.", "oliy"),
                   (70, "Attestatsiyadan o‘tdi, birinchi malaka toifasi saqlanadi.", "birinchi"),
                   (0,  "Attestatsiyadan o‘tmadi, ikkinchi malaka toifasiga tushiriladi.", "ikkinchi")],
    "ikkinchi":   [(70, "Attestatsiyadan o‘tdi, birinchi malaka toifasi beriladi.", "birinchi"),
                   (60, "Attestatsiyadan o‘tdi, ikkinchi malaka toifasi saqlanadi.", "ikkinchi"),
                   (0,  "Attestatsiyadan o‘tmadi, mutaxassis lavozimiga tushiriladi.", "mutaxassis")],
    "mutaxassis": [(60, "Attestatsiyadan o‘tdi, ikkinchi malaka toifasi beriladi.", "ikkinchi"),
                   (55, "Attestatsiyadan o‘tdi, mutaxassis lavozimi saqlanadi.", "mutaxassis"),
                   (0,  "Attestatsiyadan o‘tmadi, mutaxassis lavozimiga muvofiq emas deb topiladi.", "mutaxassis")],
}
EXTRA_NOTE_86 = "86 va undan yuqori ball — 70 foizlik ustama uchun asos bo‘ladi (VM 130-son qarori)."


def section_of(n):
    return "fan" if n <= N_FAN else ("kasb" if n <= N_FAN + N_KASB else "ped")


def decision(total, cur):
    """(matn, yangi toifa) — joriy toifa `cur` bo'yicha. cur noma'lum bo'lsa None."""
    rules = DECISION_RULES.get(cur)
    if not rules:
        return None
    for lim, text, new in rules:
        if total >= lim:
            return {"text": text, "new": new, "new_name": CAT_NAMES[new], "passed": text.startswith("Attestatsiyadan o‘tdi")}
    return None


def cat_by_score(total):
    """Joriy toifa ko'rsatilmaganda — ball bo'yicha erishilgan toifa."""
    if total >= 80: return "oliy"
    if total >= 70: return "birinchi"
    if total >= 60: return "ikkinchi"
    if total >= 55: return "mutaxassis"
    return None


# ------------------------------------------------------------------ baza
def init():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS att_tests(
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT 'Ona tili va adabiyot', duration_min INTEGER NOT NULL DEFAULT 90,
            questions_json TEXT NOT NULL, created_by INTEGER, created_at TEXT NOT NULL,
            published INTEGER NOT NULL DEFAULT 1)''')
        c.execute('''CREATE TABLE IF NOT EXISTS att_attempts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, test_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            started_at INTEGER NOT NULL, finished_at INTEGER, answers_json TEXT NOT NULL DEFAULT '{}')''')
        c.execute('CREATE INDEX IF NOT EXISTS att_attempts_u ON att_attempts(user_id, test_id)')
        c.execute('''CREATE TABLE IF NOT EXISTS att_objections(
            id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id INTEGER NOT NULL, qn INTEGER NOT NULL,
            user_id INTEGER NOT NULL, reason TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL, decided_at INTEGER, UNIQUE(attempt_id, qn))''')
        c.execute('CREATE TABLE IF NOT EXISTS att_settings(key TEXT PRIMARY KEY, value TEXT)')
        c.commit()


def _setting(k, d=''):
    with db() as c:
        r = c.execute('SELECT value FROM att_settings WHERE key=?', (k,)).fetchone()
    return r['value'] if r else d


def _set_setting(k, v):
    with db() as c:
        c.execute('INSERT INTO att_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (k, str(v)))
        c.commit()


def is_public():
    return _setting('att_public', '0') == '1'


# ------------------------------------------------------------------ matnni tahlil qilish
_OPT_RE = re.compile(r'^\s*([*+✅✔]?)\s*\(?([A-Da-d])\)?\s*[.)]\s*(.*)$')
_Q_RE = re.compile(r'^\s*(\d{1,3})\s*[.)]\s*(.*)$')
_ANS_RE = re.compile(r"^\s*(?:javob|to['‘’`ʻ]?g['‘’`ʻ]?ri\s+javob|kalit|answer|ans)\s*[:=\-–]\s*\(?([A-Da-d])\)?\s*\.?\s*$", re.I)
_TOP_RE = re.compile(r'^\s*(?:mavzu|topic)\s*[:=]\s*(.+?)\s*$', re.I)
_EXP_RE = re.compile(r'^\s*(?:izoh|tushuntirish|explanation)\s*[:=]\s*(.*)$', re.I)
_KEYHDR_RE = re.compile(r'^\s*(?:javoblar(?:\s+kaliti)?|kalitlar|kalit|javoblar)\s*[:\-–]?\s*(.*)$', re.I)
_PAIR_RE = re.compile(r'(\d{1,3})\s*[-–.:)=]*\s*([A-Da-d])(?![A-Za-z0-9])')


def parse_text(text):
    """Matndan savollarni ajratadi. Qaytaradi: (questions, errors).
    Format: «1. Savol / A) ... / B) ... / C) ... / D) ... / Javob: B». To'g'ri variantni
    «*B) ...» yoki «✅B) ...» deb ham belgilash mumkin; oxirida «Javoblar: 1-A 2-B ...» kalit bloki ham bo'ladi."""
    qs, cur, last, key_text, in_key = [], None, None, [], False
    for raw in str(text or '').replace('\r', '').split('\n'):
        line = raw.rstrip()
        if not line.strip():
            continue
        if in_key:
            key_text.append(line); continue
        mk = _KEYHDR_RE.match(line)
        if mk and qs and not _OPT_RE.match(line) and not _Q_RE.match(line):
            in_key = True
            if mk.group(1): key_text.append(mk.group(1))
            continue
        mt = _TOP_RE.match(line)
        if mt and cur is not None: cur['t'] = mt.group(1)[:120]; last = None; continue
        me = _EXP_RE.match(line)
        if me and cur is not None: cur['e'] = me.group(1).strip()[:2000]; last = 'exp'; continue
        ma = _ANS_RE.match(line)
        if ma and cur is not None:
            cur['a'] = 'ABCD'.index(ma.group(1).upper()); last = None; continue
        mo = _OPT_RE.match(line)
        if mo and cur is not None:
            mark, letter, body = mo.group(1), mo.group(2).upper(), mo.group(3).strip()
            cur['opts'].append((letter, body))
            if mark: cur['a'] = 'ABCD'.index(letter)
            last = 'opt'; continue
        mq = _Q_RE.match(line)
        if mq and (cur is None or len(cur['opts']) >= 2):
            cur = {'q': mq.group(2).strip(), 'opts': [], 'a': None}
            qs.append(cur); last = 'q'; continue
        if cur is not None:   # davomi (uzun savol/variant/izoh matni)
            if last == 'exp':
                cur['e'] = (cur.get('e', '') + ' ' + line.strip()).strip()[:2000]
            elif last == 'opt' and cur['opts']:
                l, b = cur['opts'][-1]; cur['opts'][-1] = (l, (b + ' ' + line.strip()).strip())
            else:
                cur['q'] = (cur['q'] + ' ' + line.strip()).strip()
    keymap = {}
    for n, l in _PAIR_RE.findall(' '.join(key_text)):
        keymap[int(n)] = 'ABCD'.index(l.upper())
    errors, out = [], []
    for i, q in enumerate(qs, 1):
        letters = [l for l, _ in q['opts']]
        if letters != ['A', 'B', 'C', 'D']:
            errors.append('%d-savol: variantlar A, B, C, D tartibida 4 ta bo‘lishi kerak (topildi: %s)' % (i, ''.join(letters) or 'yo‘q')); continue
        if not q['q']:
            errors.append('%d-savol: savol matni bo‘sh' % i); continue
        a = q['a'] if q['a'] is not None else keymap.get(i)
        if a is None:
            errors.append('%d-savol: to‘g‘ri javob ko‘rsatilmagan' % i); continue
        bodies = [b for _, b in q['opts']]
        if any(not b for b in bodies):
            errors.append('%d-savol: bo‘sh variant bor' % i); continue
        item = {'q': q['q'][:1500], 'o': [b[:500] for b in bodies], 'a': a}
        if q.get('t'): item['t'] = q['t']
        if q.get('e'): item['e'] = q['e']
        out.append(item)
    if not errors and len(out) != N_TOTAL:
        errors.append('Savollar soni %d ta, lekin rasmiy tuzilma — %d ta (35 fan + 5 kasbiy standart + 10 pedagogik mahorat)' % (len(out), N_TOTAL))
    return out, errors


# ------------------------------------------------------------------ test boshqaruvi (admin)
def _gen_code():
    while True:
        code = 'AT-' + secrets.token_hex(3).upper()
        with db() as c:
            if not c.execute('SELECT 1 FROM att_tests WHERE code=?', (code,)).fetchone():
                return code


def create_test(title, subject, text, uid, dry_run=False):
    title = str(title or '').strip()[:120]
    subject = (str(subject or '').strip() or 'Ona tili va adabiyot')[:80]
    qs, errors = parse_text(text)
    if dry_run:
        return {'ok': not errors, 'count': len(qs), 'errors': errors[:12],
                'split': {'fan': min(len(qs), N_FAN), 'kasb': max(0, min(len(qs) - N_FAN, N_KASB)), 'ped': max(0, min(len(qs) - N_FAN - N_KASB, N_PED))}}
    if not title:
        raise ValueError('Test nomini kiriting.')
    if errors:
        raise ValueError('; '.join(errors[:5]))
    code = _gen_code()
    with db() as c:
        c.execute('INSERT INTO att_tests(code,title,subject,duration_min,questions_json,created_by,created_at,published) VALUES(?,?,?,?,?,?,?,1)',
                  (code, title, subject, DURATION_MIN, json.dumps(qs, ensure_ascii=False), int(uid), datetime.now(timezone.utc).isoformat(timespec='seconds')))
        c.commit()
    return {'ok': True, 'code': code, 'count': len(qs)}


def _get_test(code):
    with db() as c:
        r = c.execute('SELECT * FROM att_tests WHERE code=?', (str(code or '').upper().strip(),)).fetchone()
    return dict(r) if r else None


def _test_by_id(tid):
    with db() as c:
        r = c.execute('SELECT * FROM att_tests WHERE id=?', (int(tid),)).fetchone()
    return dict(r) if r else None


def delete_test(code):
    t = _get_test(code)
    if not t: raise ValueError('Test topilmadi.')
    with db() as c:
        ids = [r[0] for r in c.execute('SELECT id FROM att_attempts WHERE test_id=?', (t['id'],)).fetchall()]
        for i in ids: c.execute('DELETE FROM att_objections WHERE attempt_id=?', (i,))
        c.execute('DELETE FROM att_attempts WHERE test_id=?', (t['id'],))
        c.execute('DELETE FROM att_tests WHERE id=?', (t['id'],))
        c.commit()
    return {'ok': True}


def admin_test(code):
    """Admin tahrirlash oynasi uchun: savollar, to'g'ri javoblar, mavzu va izoh."""
    t = _get_test(code)
    if not t: raise ValueError('Test topilmadi.')
    qs = json.loads(t['questions_json'])
    return {'ok': True, 'code': t['code'], 'title': t['title'],
            'items': [{'n': i + 1, 'section': section_of(i + 1), 'q': q['q'], 'correct': q['a'], 'topic': q.get('t', ''), 'explanation': q.get('e', '')} for i, q in enumerate(qs)]}


def edit_test(code, edits):
    """edits: [{'n':7,'topic':'..','explanation':'..'}]. Xato bo'lsa hech narsa yozilmaydi. Qaytaradi: o'zgargan savollar soni."""
    t = _get_test(code)
    if not t: raise ValueError('Test topilmadi.')
    qs = json.loads(t['questions_json']); changed = 0
    if not isinstance(edits, list) or not edits or len(edits) > N_TOTAL: raise ValueError('O‘zgarish yo‘q.')
    for e in edits:
        try: n = int(e.get('n'))
        except Exception: raise ValueError('Savol raqami noto‘g‘ri.')
        if not 1 <= n <= N_TOTAL: raise ValueError('%d-savol topilmadi.' % n)
        q = qs[n - 1]; before = json.dumps(q, sort_keys=True, ensure_ascii=False)
        if 'topic' in e:
            tp = re.sub(r'\s+', ' ', str(e.get('topic') or '')).strip()[:120]
            if tp: q['t'] = tp
            else: q.pop('t', None)
        if 'explanation' in e:
            ex = str(e.get('explanation') or '').strip()[:2000]
            if ex: q['e'] = ex
            else: q.pop('e', None)
        if json.dumps(q, sort_keys=True, ensure_ascii=False) != before: changed += 1
    if changed:
        with db() as c:
            c.execute('UPDATE att_tests SET questions_json=? WHERE id=?', (json.dumps(qs, ensure_ascii=False), t['id'])); c.commit()
    return {'ok': True, 'changed': changed}


def set_topics(code, text):
    import ms_exam
    mp, errs = ms_exam.parse_topic_lines(text, N_TOTAL)
    if errs: raise ValueError('; '.join(errs[:4]))
    if not mp: raise ValueError('Mavzu topilmadi. Namuna: 1-35: Ona tili qoidalari')
    return edit_test(code, [{'n': n, 'topic': tp} for n, tp in sorted(mp.items())])


def set_published(code, on):
    t = _get_test(code)
    if not t: raise ValueError('Test topilmadi.')
    with db() as c:
        c.execute('UPDATE att_tests SET published=? WHERE id=?', (1 if on else 0, t['id'])); c.commit()
    return {'ok': True, 'published': bool(on)}


# ------------------------------------------------------------------ ball hisoblash
def _clean_answers(d):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            try:
                n, a = int(k), int(v)
            except (TypeError, ValueError):
                continue
            if 1 <= n <= N_TOTAL and 0 <= a <= 3: out[str(n)] = a
    return out


def grade(questions, answers, accepted=()):
    """answers: {'1': 0..3}; accepted: qabul qilingan e'tirozli savol raqamlari (to'g'ri deb hisoblanadi)."""
    accepted = set(int(x) for x in accepted)
    per, flipped = [], 0
    for n in range(1, N_TOTAL + 1):
        q = questions[n - 1]; given = answers.get(str(n))
        ok = (given == q['a'])
        if not ok and n in accepted: ok = True; flipped += 1
        per.append({'n': n, 'section': section_of(n), 'ok': ok, 'skipped': given is None})
    main_ok = sum(1 for p in per if p['n'] <= N_FAN + N_KASB and p['ok'])
    ped_ok = sum(1 for p in per if p['n'] > N_FAN + N_KASB and p['ok'])
    fan_ok = sum(1 for p in per if p['section'] == 'fan' and p['ok'])
    kasb_ok = sum(1 for p in per if p['section'] == 'kasb' and p['ok'])
    total = (main_ok + ped_ok) * POINTS
    return {'per': per, 'main_ok': main_ok, 'main_total': N_FAN + N_KASB, 'main_ball': main_ok * POINTS,
            'ped_ok': ped_ok, 'ped_total': N_PED, 'ped_ball': ped_ok * POINTS,
            'fan_ok': fan_ok, 'kasb_ok': kasb_ok, 'total': total, 'percent': round(total * 100.0 / MAX_SCORE),
            'objection_flipped': flipped, 'objection_ball': flipped * POINTS}


# ------------------------------------------------------------------ urinish
def _attempt(aid):
    with db() as c:
        r = c.execute('SELECT * FROM att_attempts WHERE id=?', (int(aid),)).fetchone()
    return dict(r) if r else None


def _deadline(att, test):
    return int(att['started_at']) + int(test['duration_min']) * 60


def _finalize(att, test, answers=None):
    """Urinishni yakunlaydi (agar yakunlanmagan bo'lsa). Yakun vaqti muddatdan oshmaydi."""
    if att['finished_at']: return att
    ans = _clean_answers(answers if answers is not None else json.loads(att['answers_json'] or '{}'))
    fin = min(int(time.time()), _deadline(att, test))
    with db() as c:
        c.execute('UPDATE att_attempts SET finished_at=?, answers_json=? WHERE id=? AND finished_at IS NULL',
                  (fin, json.dumps(ans), att['id'])); c.commit()
    return _attempt(att['id'])


def start(uid, code, admin):
    t = _get_test(code)
    if not t or (not t['published'] and not admin): raise ValueError('Test topilmadi.')
    with db() as c:
        r = c.execute('SELECT * FROM att_attempts WHERE user_id=? AND test_id=? AND finished_at IS NULL ORDER BY id DESC LIMIT 1', (int(uid), t['id'])).fetchone()
    att = dict(r) if r else None
    if att and time.time() > _deadline(att, t) + GRACE_SEC:
        _finalize(att, t); att = None
    if not att:
        with db() as c:
            n_today = c.execute('SELECT COUNT(*) FROM att_attempts WHERE user_id=? AND started_at>?', (int(uid), int(time.time()) - 86400)).fetchone()[0]
            if n_today >= 10 and not admin: raise ValueError('Bir kunda ko‘pi bilan 10 ta urinish. Ertaga davom eting.')
            cur = c.execute('INSERT INTO att_attempts(test_id,user_id,started_at,answers_json) VALUES(?,?,?,?)', (t['id'], int(uid), int(time.time()), '{}'))
            c.commit(); att = _attempt(cur.lastrowid)
    qs = json.loads(t['questions_json'])
    return {'ok': True, 'attempt_id': att['id'], 'title': t['title'], 'subject': t['subject'],
            'duration_min': t['duration_min'], 'started_ts': int(att['started_at']), 'deadline_ts': _deadline(att, t),
            'server_ts': int(time.time()), 'answers': json.loads(att['answers_json'] or '{}'),
            'sections': [{'key': 'fan', 'name': 'Asosiy fan', 'from': 1, 'to': N_FAN},
                         {'key': 'kasb', 'name': 'Kasbiy standart', 'from': N_FAN + 1, 'to': N_FAN + N_KASB},
                         {'key': 'ped', 'name': 'Pedagogik mahorat', 'from': N_FAN + N_KASB + 1, 'to': N_TOTAL}],
            'questions': [{'n': i + 1, 'q': q['q'], 'o': q['o'], 'section': section_of(i + 1)} for i, q in enumerate(qs)]}


def save(uid, attempt_id, answers):
    att = _attempt(attempt_id)
    if not att or int(att['user_id']) != int(uid): raise ValueError('Urinish topilmadi.')
    t = _test_by_id(att['test_id'])
    if att['finished_at'] or time.time() > _deadline(att, t) + GRACE_SEC: return {'ok': True, 'finished': True}
    with db() as c:
        c.execute('UPDATE att_attempts SET answers_json=? WHERE id=? AND finished_at IS NULL', (json.dumps(_clean_answers(answers)), att['id'])); c.commit()
    return {'ok': True, 'finished': False}


def submit(uid, attempt_id, answers):
    att = _attempt(attempt_id)
    if not att or int(att['user_id']) != int(uid): raise ValueError('Urinish topilmadi.')
    t = _test_by_id(att['test_id'])
    if not att['finished_at']:
        late = time.time() > _deadline(att, t) + GRACE_SEC
        _finalize(att, t, None if late else answers)   # muddatdan keyin — faqat serverga saqlangan javoblar
    return {'ok': True, 'attempt_id': int(attempt_id)}


# ------------------------------------------------------------------ natija
def _accepted(aid):
    with db() as c:
        return {r['qn'] for r in c.execute("SELECT qn FROM att_objections WHERE attempt_id=? AND status='accepted'", (int(aid),)).fetchall()}


def _objections(aid):
    with db() as c:
        return {r['qn']: r['status'] for r in c.execute('SELECT qn,status FROM att_objections WHERE attempt_id=?', (int(aid),)).fetchall()}


def _fmt_dt(ts):
    d = datetime.fromtimestamp(int(ts), TZ)
    return d.strftime('%d.%m.%Y'), d.strftime('%H:%M')


def _load_finished(uid, attempt_id, admin):
    att = _attempt(attempt_id)
    if not att or (int(att['user_id']) != int(uid) and not admin): raise ValueError('Natija topilmadi.')
    t = _test_by_id(att['test_id'])
    if not t: raise ValueError('Test topilmadi.')
    if not att['finished_at']:
        if time.time() > _deadline(att, t) + GRACE_SEC: att = _finalize(att, t)
        else: raise ValueError('Test hali yakunlanmagan.')
    return att, t


def result(uid, attempt_id, admin):
    att, t = _load_finished(uid, attempt_id, admin)
    qs = json.loads(t['questions_json'])
    g = grade(qs, json.loads(att['answers_json'] or '{}'), _accepted(att['id']))
    obj = _objections(att['id'])
    d, s = _fmt_dt(att['started_at']); _, e = _fmt_dt(att['finished_at'])
    tiles = [{'n': p['n'], 'section': p['section'], 'ok': p['ok'],
              'obj': obj.get(p['n']), 'topic': qs[p['n'] - 1].get('t', '')} for p in g['per']]
    return {'ok': True, 'attempt_id': att['id'], 'title': t['title'], 'subject': t['subject'], 'date': d, 'start': s, 'end': e,
            'total': g['total'], 'max': MAX_SCORE, 'percent': g['percent'],
            'main': {'total': g['main_total'], 'ok': g['main_ok'], 'ball': g['main_ball'], 'fan_ok': g['fan_ok'], 'kasb_ok': g['kasb_ok']},
            'ped': {'total': g['ped_total'], 'ok': g['ped_ok'], 'ball': g['ped_ball']},
            'objections': {'count': len(obj), 'accepted': g['objection_flipped'], 'ball': g['objection_ball'],
                           'pending': sum(1 for v in obj.values() if v == 'pending'), 'left': max(0, MAX_OBJECTIONS - len(obj))},
            'tiles': tiles, 'cat_by_score': cat_by_score(g['total']),
            'rules': {k: [{'min': a, 'text': b, 'new': c} for a, b, c in v] for k, v in DECISION_RULES.items()},
            'cat_names': CAT_NAMES, 'note86': EXTRA_NOTE_86 if g['total'] >= 86 else ''}


def review(uid, attempt_id, admin):
    att, t = _load_finished(uid, attempt_id, admin)
    qs = json.loads(t['questions_json']); ans = json.loads(att['answers_json'] or '{}'); acc = _accepted(att['id']); obj = _objections(att['id'])
    items = []
    for i, q in enumerate(qs, 1):
        given = ans.get(str(i))
        items.append({'n': i, 'section': section_of(i), 'q': q['q'], 'o': q['o'], 'given': given, 'correct': q['a'],
                      'ok': given == q['a'] or i in acc, 'obj': obj.get(i), 'topic': q.get('t', ''), 'explanation': q.get('e', '')})
    return {'ok': True, 'items': items}


def my_attempts(uid):
    with db() as c:
        rows = c.execute('''SELECT a.id, a.started_at, a.finished_at, t.title FROM att_attempts a JOIN att_tests t ON t.id=a.test_id
                            WHERE a.user_id=? AND a.finished_at IS NOT NULL ORDER BY a.id DESC LIMIT 40''', (int(uid),)).fetchall()
    out = []
    for r in rows:
        try: tot = result(uid, r['id'], False)['total']
        except ValueError: continue
        out.append({'id': r['id'], 'title': r['title'], 'date': _fmt_dt(r['started_at'])[0], 'total': tot, 'max': MAX_SCORE})
    return {'ok': True, 'items': out}


def list_tests(uid, admin):
    pub = is_public()
    base = {'ok': True, 'is_admin': bool(admin), 'public': pub,
            'structure': {'total': N_TOTAL, 'fan': N_FAN, 'kasb': N_KASB, 'ped': N_PED, 'points': POINTS, 'max': MAX_SCORE, 'minutes': DURATION_MIN}}
    if not admin and not pub:
        base.update({'locked': True, 'items': []}); return base
    with db() as c:
        rows = c.execute('SELECT id,code,title,subject,duration_min,created_at,published FROM att_tests ORDER BY id DESC LIMIT 100').fetchall()
        items = []
        for r in rows:
            if not admin and not r['published']: continue
            cnt = c.execute('SELECT COUNT(*) FROM att_attempts WHERE test_id=? AND finished_at IS NOT NULL', (r['id'],)).fetchone()[0]
            prog = c.execute('SELECT id FROM att_attempts WHERE test_id=? AND user_id=? AND finished_at IS NULL ORDER BY id DESC LIMIT 1', (r['id'], int(uid))).fetchone()
            items.append({'code': r['code'], 'title': r['title'], 'subject': r['subject'], 'minutes': r['duration_min'],
                          'published': bool(r['published']), 'attempts': cnt if admin else None, 'in_progress': bool(prog)})
    base.update({'locked': False, 'items': items}); return base


# ------------------------------------------------------------------ e'tirozlar
def add_objection(uid, attempt_id, qn, reason):
    att, t = _load_finished(uid, attempt_id, False)
    qn = int(qn)
    if not 1 <= qn <= N_TOTAL: raise ValueError('Savol raqami noto‘g‘ri.')
    qs = json.loads(t['questions_json']); ans = json.loads(att['answers_json'] or '{}')
    if ans.get(str(qn)) == qs[qn - 1]['a']: raise ValueError('Bu savolga to‘g‘ri javob bergansiz — e’tiroz kerak emas.')
    reason = str(reason or '').strip()[:500]
    if len(reason) < 5: raise ValueError('E’tiroz sababini yozing (kamida 5 belgi).')
    with db() as c:
        if c.execute('SELECT 1 FROM att_objections WHERE attempt_id=? AND qn=?', (att['id'], qn)).fetchone(): raise ValueError('Bu savol bo‘yicha e’tiroz allaqachon yuborilgan.')
        if c.execute('SELECT COUNT(*) FROM att_objections WHERE attempt_id=?', (att['id'],)).fetchone()[0] >= MAX_OBJECTIONS:
            raise ValueError('Bitta urinishda ko‘pi bilan %d ta e’tiroz yuborish mumkin.' % MAX_OBJECTIONS)
        c.execute('INSERT INTO att_objections(attempt_id,qn,user_id,reason,created_at) VALUES(?,?,?,?,?)', (att['id'], qn, int(uid), reason, int(time.time()))); c.commit()
    return {'ok': True}


def list_objections():
    with db() as c:
        rows = c.execute("SELECT * FROM att_objections WHERE status='pending' ORDER BY id LIMIT 100").fetchall()
        out = []
        for r in rows:
            a = c.execute('SELECT * FROM att_attempts WHERE id=?', (r['attempt_id'],)).fetchone()
            t = c.execute('SELECT * FROM att_tests WHERE id=?', (a['test_id'],)).fetchone() if a else None
            if not a or not t: continue
            q = json.loads(t['questions_json'])[r['qn'] - 1]; given = json.loads(a['answers_json'] or '{}').get(str(r['qn']))
            out.append({'id': r['id'], 'user_id': r['user_id'], 'test': t['title'], 'qn': r['qn'], 'q': q['q'], 'o': q['o'],
                        'correct': q['a'], 'given': given, 'reason': r['reason']})
    return {'ok': True, 'items': out}


def decide_objection(oid, accept):
    with db() as c:
        r = c.execute('SELECT id FROM att_objections WHERE id=? AND status=?', (int(oid), 'pending')).fetchone()
        if not r: raise ValueError('E’tiroz topilmadi yoki ko‘rib chiqilgan.')
        c.execute('UPDATE att_objections SET status=?, decided_at=? WHERE id=?', ('accepted' if accept else 'rejected', int(time.time()), int(oid))); c.commit()
    return {'ok': True}


# ------------------------------------------------------------------ HTTP marshrutlari (cert_center bilan bir xil shakl)
def _can_use(admin):
    return bool(admin) or is_public()


def api_get(path, uid, admin):
    p = path.split('?')[0]
    try:
        if p == '/api/att/list': return 200, list_tests(uid, admin)
        if not _can_use(admin): return 403, {'ok': False, 'error': 'Bu bo‘lim hozircha yopiq.'}
        if p == '/api/att/admin_test':
            if not admin: return 403, {'ok': False, 'error': 'Faqat admin.'}
            from urllib.parse import parse_qs, urlparse
            return 200, admin_test((parse_qs(urlparse(path).query).get('code') or [''])[0])
        if p == '/api/att/mine': return 200, my_attempts(uid)
        if p.startswith('/api/att/result/'): return 200, result(uid, p.rsplit('/', 1)[-1], admin)
        if p.startswith('/api/att/review/'): return 200, review(uid, p.rsplit('/', 1)[-1], admin)
        if p == '/api/att/objections':
            if not admin: return 403, {'ok': False, 'error': 'Faqat admin.'}
            return 200, list_objections()
    except ValueError as e:
        return 400, {'ok': False, 'error': str(e)}
    return 404, {'ok': False, 'error': 'Topilmadi'}


def api_post(path, body, uid, admin):
    p = path.split('?')[0]
    if not isinstance(body, dict): return 400, {'ok': False, 'error': 'Noto‘g‘ri so‘rov.'}
    try:
        if p in ('/api/att/create', '/api/att/delete', '/api/att/publish', '/api/att/public', '/api/att/objection/decide', '/api/att/edit', '/api/att/topics') and not admin:
            return 403, {'ok': False, 'error': 'Faqat admin.'}
        if p == '/api/att/create':
            return 200, create_test(body.get('title'), body.get('subject'), body.get('text'), uid, dry_run=bool(body.get('dry_run')))
        if p == '/api/att/delete': return 200, delete_test(body.get('code'))
        if p == '/api/att/edit': return 200, edit_test(body.get('code'), body.get('edits'))
        if p == '/api/att/topics': return 200, set_topics(body.get('code'), body.get('text'))
        if p == '/api/att/publish': return 200, set_published(body.get('code'), bool(body.get('on')))
        if p == '/api/att/public':
            _set_setting('att_public', '1' if body.get('on') else '0'); return 200, {'ok': True, 'public': is_public()}
        if p == '/api/att/objection/decide': return 200, decide_objection(body.get('id'), bool(body.get('accept')))
        if not _can_use(admin): return 403, {'ok': False, 'error': 'Bu bo‘lim hozircha yopiq.'}
        if p == '/api/att/start': return 200, start(uid, body.get('code'), admin)
        if p == '/api/att/save': return 200, save(uid, body.get('attempt_id'), body.get('answers'))
        if p == '/api/att/submit': return 200, submit(uid, body.get('attempt_id'), body.get('answers'))
        if p == '/api/att/objection': return 200, add_objection(uid, body.get('attempt_id'), body.get('qn'), body.get('reason'))
    except ValueError as e:
        return 400, {'ok': False, 'error': str(e)}
    return 404, {'ok': False, 'error': 'Topilmadi'}
