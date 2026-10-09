"""Oddiy testlar (milliy sertifikat formatidan tashqari): ixtiyoriy sondagi yopiq savollar (A-F variantlar).

Savol matni ixtiyoriy: faqat javoblar kaliti (A, B, C...) bilan ham, savollar bilan birga ham kiritish mumkin.

Alohida jadvallar; Rasch/esse/sertifikat tizimiga aralashmaydi. Natija: to'g'ri javoblar soni va foiz.
"""
import json, secrets
from datetime import datetime, timedelta, timezone
from national_certificate import db, now

MAX_Q = 1000   # texnik chegara (so'rov hajmi uchun); amalda cheklanmagan
LETTERS = "ABCDEF"


def init_simple_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS simple_tests(
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '', questions_json TEXT NOT NULL, created_by INTEGER, created_at TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS simple_attempts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, test_id INTEGER NOT NULL,
            correct INTEGER NOT NULL, total INTEGER NOT NULL, created_at TEXT NOT NULL)''')
        cols = {r[1] for r in c.execute('PRAGMA table_info(simple_attempts)').fetchall()}
        if 'errors_json' not in cols:
            c.execute("ALTER TABLE simple_attempts ADD COLUMN errors_json TEXT NOT NULL DEFAULT '[]'")
        c.execute("CREATE INDEX IF NOT EXISTS ix_simple_att ON simple_attempts(test_id, user_id)")
        c.commit()


def _gen_code():
    while True:
        code = 'T-' + secrets.token_hex(3).upper()
        with db() as c:
            if not c.execute('SELECT 1 FROM simple_tests WHERE code=?', (code,)).fetchone():
                return code


def validate(questions):
    """(tozalangan_savollar | None, xato matni)."""
    if not isinstance(questions, list) or not questions:
        return None, "Kamida 1 ta savol kiriting."
    if len(questions) > MAX_Q:
        return None, f"Bitta testda {MAX_Q} tadan ortiq savol bo‘lmasin."
    out = []
    for i, q in enumerate(questions, 1):
        if not isinstance(q, dict):
            return None, f"{i}-savol noto‘g‘ri."
        text = str(q.get('text', '')).strip()[:6000]
        opts = [str(o).strip()[:1500] for o in (q.get('options') or [])]
        # savol matni ixtiyoriy (faqat javoblar kaliti bo'lishi mumkin); variant matni bo'sh bo'lsa harfning o'zi olinadi
        if opts and len(opts) <= 6 and any(not o for o in opts):
            opts = [o or LETTERS[k] for k, o in enumerate(opts)]
        if not (2 <= len(opts) <= 6) or any(not o for o in opts):
            return None, f"{i}-savolda 2 tadan 6 tagacha to‘ldirilgan variant bo‘lishi kerak."
        ans = str(q.get('answer', '')).strip().upper()
        if ans not in LETTERS[:len(opts)]:
            return None, f"{i}-savolning to‘g‘ri javobi ({ans or '—'}) variantlar orasida yo‘q."
        out.append({'text': text, 'options': opts, 'answer': ans, 'explanation': str(q.get('explanation', '')).strip()[:600]})
    return out, None


def create(title, subject, questions, created_by):
    code = _gen_code()
    with db() as c:
        c.execute('INSERT INTO simple_tests(code,title,subject,questions_json,created_by,created_at) VALUES(?,?,?,?,?,?)',
                  (code, title, subject, json.dumps(questions, ensure_ascii=False), created_by, now()))
        c.commit()
    return code


def get(code):
    with db() as c:
        r = c.execute('SELECT * FROM simple_tests WHERE code=?', ((code or '').upper().strip(),)).fetchone()
    if not r:
        return None
    d = dict(r); d['questions'] = json.loads(d.pop('questions_json')); return d


def count_recent(uid, hours):
    """Foydalanuvchi oxirgi N soatda yaratgan testlar soni."""
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM simple_tests WHERE created_by=? AND created_at>=?", (int(uid), since)).fetchone()[0]


def list_all():
    with db() as c:
        rows = c.execute('''SELECT t.code,t.title,t.subject,t.created_at,t.created_by,
            (SELECT COUNT(*) FROM simple_attempts a WHERE a.test_id=t.id) AS attempts,
            json_array_length(t.questions_json) AS n FROM simple_tests t ORDER BY t.id DESC LIMIT 200''').fetchall()
    return [dict(r) for r in rows]


def delete(code, by=None, admin=False):
    """Admin hammasini, muallif faqat o'z testini o'chiradi."""
    with db() as c:
        r = c.execute('SELECT id,created_by FROM simple_tests WHERE code=?', ((code or '').upper().strip(),)).fetchone()
        if not r:
            return False
        if not admin and (by is None or r['created_by'] != int(by)):
            return False
        c.execute('DELETE FROM simple_attempts WHERE test_id=?', (r['id'],))
        c.execute('DELETE FROM simple_tests WHERE id=?', (r['id'],)); c.commit()
    return True


def grade(test, answers, uid):
    qs = test['questions']; errors = []; correct = 0
    for i, q in enumerate(qs, 1):
        u = str((answers or {}).get(str(i), '')).strip().upper()
        if u == q['answer']:
            correct += 1
        else:
            errors.append({'number': i, 'text': q['text'], 'user': u or '—', 'correct': q['answer'],
                           'correct_text': q['options'][LETTERS.index(q['answer'])], 'explanation': q.get('explanation', '')})
    total = len(qs)
    with db() as c:
        c.execute('INSERT INTO simple_attempts(user_id,test_id,correct,total,created_at,errors_json) VALUES(?,?,?,?,?,?)', (int(uid), test['id'], correct, total, now(), json.dumps([e['number'] for e in errors])))
        c.commit()
    return {'correct': correct, 'total': total, 'percent': round(correct / total * 100) if total else 0, 'errors': errors}
