# -*- coding: utf-8 -*-
"""v109: SINF NAZORATI — ustoz paneli kengaytmasi.

Sinflar va o'quvchilar ro'yxati, guruhda vazifa nazorati, davomat, test qatnashuvi,
ota-ona nazorati (alohida login/parol), reyting va o'zlashtirish.
Bu modul Telegramga bog'liq EMAS (class_bot.py yuboradi): hamma xabar cc_outbox navbatiga yoziladi.
Tashqi kutubxona yo'q. AI chaqirilmaydi.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

import national_certificate as nc

log = logging.getLogger('class_ctl')
UZ = timezone(timedelta(hours=5))
ADMIN_ID = int(os.getenv('ADMIN_ID', '1953416343'))
LATE_AFTER_MIN = 10            # davomat ochilgandan shuncha daqiqadan keyin belgilansa — «kechikdi»
QUIET_FROM, QUIET_TO = 21, 7   # ota-onaga xabar yuborilmaydigan soatlar (Toshkent vaqti)
W_ATT, W_HW, W_TEST = 0.3, 0.3, 0.4
MS_MAX = 75.0
LOGIN_MAX_FAILS = 5            # bitta Telegram akkaunt uchun
LOGIN_MAX_FAILS_ACC = 25       # bitta login uchun (hamma urinishlar jami) — haqiqiy ota-onani bloklab qo'ymaslik uchun yuqoriroq
LOGIN_LOCK_MIN = 15
STATUS_UZ = {'p': 'Keldi', 'l': 'Kechikdi', 'a': 'Kelmadi', 'e': 'Sababli'}


class ApiErr(Exception):
    def __init__(self, code, msg): self.code, self.msg = code, msg


# ------------------------------------------------------------------ vaqt
def _now(): return datetime.now(timezone.utc).replace(tzinfo=None)
def _iso(dt): return dt.replace(microsecond=0).isoformat()
def _parse(s): return datetime.fromisoformat(str(s)[:19])
def _loc(s): return _parse(s).replace(tzinfo=timezone.utc).astimezone(UZ)
def fmt(s):
    try: return _loc(s).strftime('%d.%m %H:%M')
    except Exception: return '—'
def fmt_day(s):
    try: return _loc(s).strftime('%d.%m.%Y')
    except Exception: return '—'
def _to_utc(local_dt): return _iso(local_dt.astimezone(timezone.utc).replace(tzinfo=None))


# ------------------------------------------------------------------ ota-onaga xabar vaqti (ADMIN boshqaradi)
CFG_KEY = 'cfg:parent_msg'
CFG_DEFAULT = {'enabled': True, 'from': QUIET_TO, 'to': QUIET_FROM, 'weekly_day': 6, 'weekly_hour': 18, 'fee_hour': 9}
_cfg_cache = {'t': 0.0, 'v': None}


def _cfg_clean(d, base=None):
    """Tekshiradi va to'liq sozlama qaytaradi (xato bo'lsa ValueError)."""
    out = dict(base or CFG_DEFAULT); d = d if isinstance(d, dict) else {}
    def _int(k, lo, hi, nm):
        if k not in d: return
        try: v = int(d[k])
        except (TypeError, ValueError): raise ValueError('%s: son kiriting.' % nm)
        if not (lo <= v <= hi): raise ValueError('%s: %d dan %d gacha bo‘lsin.' % (nm, lo, hi))
        out[k] = v
    if 'enabled' in d: out['enabled'] = bool(d['enabled']) if not isinstance(d['enabled'], str) else d['enabled'].lower() in ('1', 'true', 'on', 'ha')
    _int('from', 0, 23, 'Boshlanish soati'); _int('to', 1, 24, 'Tugash soati')
    _int('weekly_day', 0, 6, 'Haftalik hisobot kuni'); _int('weekly_hour', 0, 23, 'Haftalik hisobot soati'); _int('fee_hour', 0, 23, 'To‘lov eslatmasi soati')
    if out['from'] >= out['to']: raise ValueError('Boshlanish soati tugash soatidan oldin bo‘lsin (masalan 07 → 21).')
    return out


def get_cfg():
    if _cfg_cache['v'] is not None and time.time() - _cfg_cache['t'] < 10: return dict(_cfg_cache['v'])
    cfg = dict(CFG_DEFAULT)
    try:
        with nc.db() as c: r = c.execute("SELECT v FROM cc_kv WHERE k=?", (CFG_KEY,)).fetchone()
        if r and r[0]: cfg = _cfg_clean(json.loads(r[0]))
    except Exception: log.exception('cfg o‘qish'); cfg = dict(CFG_DEFAULT)
    _cfg_cache.update(t=time.time(), v=cfg); return dict(cfg)


def set_cfg(d):
    cfg = _cfg_clean(d, get_cfg())
    with nc.db() as c:
        c.execute("INSERT OR REPLACE INTO cc_kv(k,v) VALUES(?,?)", (CFG_KEY, json.dumps(cfg))); c.commit()
    _cfg_cache.update(t=0.0, v=None)
    reschedule_pending()
    return get_cfg()


def quiet_after(dt=None):
    """Ruxsat etilgan oynadan tashqarida yubormaslik: UTC iso qaytaradi (oyna — admin sozlamasi, Toshkent vaqti)."""
    cfg = get_cfg(); lo, hi = cfg['from'], cfg['to']
    n = dt or _now()
    l = n.replace(tzinfo=timezone.utc).astimezone(UZ)
    if lo <= l.hour < hi: return _iso(n)
    if l.hour >= hi: l = l + timedelta(days=1)
    l = l.replace(hour=lo, minute=0, second=0, microsecond=0)
    return _to_utc(l)


def reschedule_pending():
    """Sozlama o'zgargach navbatdagi ota-ona xabarlarining vaqtini yangi oynaga qarab qayta hisoblaydi."""
    after = quiet_after()
    with nc.db() as c:
        c.execute("UPDATE cc_outbox SET send_after=? WHERE sent_at IS NULL AND roster_id IS NOT NULL AND tries<5", (after,)); c.commit()


def outbox_stats():
    iso = _iso(_now()); en = get_cfg()['enabled']
    with nc.db() as c:
        tot = c.execute("SELECT COUNT(*) FROM cc_outbox WHERE sent_at IS NULL AND roster_id IS NOT NULL AND tries<5").fetchone()[0]
        due = c.execute("SELECT COUNT(*) FROM cc_outbox WHERE sent_at IS NULL AND roster_id IS NOT NULL AND tries<5 AND send_after<=?", (iso,)).fetchone()[0]
    ready = due if en else 0
    return {'pending': tot, 'ready': ready, 'waiting': tot - ready}


def parse_due(text, now=None):
    """Matn boshidagi muddatni ajratadi: '24s', '2k', 'ertaga 18:00', 'bugun 20:00', '15.11 18:00', '18:30'.
    -> (due_utc_iso | None, qolgan_matn)"""
    now = now or datetime.now(UZ)
    t = (text or '').strip()
    def _at(base, hm):
        h, m = 20, 0
        if hm:
            h, m = [int(x) for x in re.split(r'[:.]', hm)]
            if h > 23 or m > 59: return None
        return base.replace(hour=h, minute=m, second=0, microsecond=0)
    m = re.match(r'^(\d{1,3})\s*(soat|s|kun|k)\b\s*(.*)$', t, re.I | re.S)
    if m:
        n = int(m.group(1)); hrs = n if m.group(2).lower() in ('s', 'soat') else n * 24
        if 0 < hrs <= 24 * 90: return _to_utc(now + timedelta(hours=hrs)), m.group(3).strip()
    m = re.match(r'^(bugun|ertaga|indinga)\b\s*(\d{1,2}[:.]\d{2})?\s*(.*)$', t, re.I | re.S)
    if m:
        add = {'bugun': 0, 'ertaga': 1, 'indinga': 2}[m.group(1).lower()]
        d = _at(now + timedelta(days=add), m.group(2))
        if d: return _to_utc(d), m.group(3).strip()
    m = re.match(r'^(\d{1,2})[.\-/](\d{1,2})(?:[.\-/](\d{2,4}))?\s+(?:(\d{1,2}[:.]\d{2})\s*)?(.*)$', t, re.S)
    if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(1)) <= 31:
        try:
            y = int(m.group(3)) if m.group(3) else now.year
            if y < 100: y += 2000
            d = _at(now.replace(year=y, month=int(m.group(2)), day=int(m.group(1))), m.group(4))
            if d and d <= now and not m.group(3): d = d.replace(year=y + 1)
            if d: return _to_utc(d), m.group(5).strip()
        except ValueError: pass
    m = re.match(r'^(\d{1,2}):(\d{2})\s*(.*)$', t, re.S)
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        d = _at(now, m.group(1) + ':' + m.group(2))
        if d <= now: d += timedelta(days=1)
        return _to_utc(d), m.group(3).strip()
    return None, t


def default_due():
    n = datetime.now(UZ) + timedelta(days=1)
    return _to_utc(n.replace(hour=20, minute=0, second=0, microsecond=0))


# ------------------------------------------------------------------ baza
def _rows(c, sql, p=()): return [dict(r) for r in c.execute(sql, p).fetchall()]
def _row(c, sql, p=()):
    r = c.execute(sql, p).fetchone()
    return dict(r) if r else None


def init():
    with nc.db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS cc_classes(id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id INTEGER NOT NULL, name TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT '', chat_id INTEGER, chat_title TEXT NOT NULL DEFAULT '', notify_mode TEXT NOT NULL DEFAULT 'auto',
            rating_names TEXT NOT NULL DEFAULT 'short', fee_day INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS cc_assist(class_id INTEGER NOT NULL, user_id INTEGER NOT NULL, PRIMARY KEY(class_id,user_id));
        CREATE TABLE IF NOT EXISTS cc_roster(id INTEGER PRIMARY KEY AUTOINCREMENT, class_id INTEGER NOT NULL, full_name TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '', parent_phone TEXT NOT NULL DEFAULT '', student_uid INTEGER, fee INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS ix_cc_roster_c ON cc_roster(class_id);
        CREATE INDEX IF NOT EXISTS ix_cc_roster_u ON cc_roster(student_uid);
        CREATE TABLE IF NOT EXISTS cc_parent_acc(id INTEGER PRIMARY KEY AUTOINCREMENT, roster_id INTEGER UNIQUE NOT NULL, login TEXT UNIQUE NOT NULL,
            salt TEXT NOT NULL, pw_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cc_parent_dev(tg_uid INTEGER NOT NULL, acc_id INTEGER NOT NULL, bound_at TEXT NOT NULL, PRIMARY KEY(tg_uid,acc_id));
        CREATE TABLE IF NOT EXISTS cc_login_fail(k TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0, until TEXT);
        CREATE TABLE IF NOT EXISTS cc_hw(id INTEGER PRIMARY KEY AUTOINCREMENT, class_id INTEGER NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL DEFAULT '',
            due_at TEXT NOT NULL, created_at TEXT NOT NULL, created_by INTEGER, chat_id INTEGER, msg_id INTEGER, finalized INTEGER NOT NULL DEFAULT 0,
            reminded INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS ix_cc_hw_c ON cc_hw(class_id);
        CREATE TABLE IF NOT EXISTS cc_hw_sub(hw_id INTEGER NOT NULL, roster_id INTEGER NOT NULL, kind TEXT NOT NULL DEFAULT 'button', at TEXT NOT NULL,
            grade INTEGER, PRIMARY KEY(hw_id,roster_id));
        CREATE TABLE IF NOT EXISTS cc_att_s(id INTEGER PRIMARY KEY AUTOINCREMENT, class_id INTEGER NOT NULL, day TEXT NOT NULL, title TEXT NOT NULL DEFAULT '',
            code TEXT NOT NULL DEFAULT '', mode TEXT NOT NULL DEFAULT 'code', open_until TEXT NOT NULL, created_at TEXT NOT NULL, chat_id INTEGER, msg_id INTEGER,
            closed INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS ix_cc_atts_c ON cc_att_s(class_id);
        CREATE TABLE IF NOT EXISTS cc_att(session_id INTEGER NOT NULL, roster_id INTEGER NOT NULL, status TEXT NOT NULL, via TEXT NOT NULL DEFAULT 'teacher',
            at TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', PRIMARY KEY(session_id,roster_id));
        CREATE TABLE IF NOT EXISTS cc_tests(id INTEGER PRIMARY KEY AUTOINCREMENT, class_id INTEGER NOT NULL, kind TEXT NOT NULL, code TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '', due_at TEXT NOT NULL, created_at TEXT NOT NULL, finalized INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS ix_cc_tests_c ON cc_tests(class_id);
        CREATE TABLE IF NOT EXISTS cc_outbox(id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, text TEXT NOT NULL, send_after TEXT NOT NULL,
            sent_at TEXT, tries INTEGER NOT NULL DEFAULT 0, kind TEXT NOT NULL DEFAULT '', ref INTEGER, roster_id INTEGER, markup_json TEXT, err TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS ix_cc_outbox ON cc_outbox(sent_at, send_after);
        CREATE TABLE IF NOT EXISTS cc_notif(kind TEXT NOT NULL, ref INTEGER NOT NULL, roster_id INTEGER NOT NULL, at TEXT NOT NULL, PRIMARY KEY(kind,ref,roster_id));
        CREATE TABLE IF NOT EXISTS cc_pay(roster_id INTEGER NOT NULL, ym TEXT NOT NULL, paid_at TEXT NOT NULL, PRIMARY KEY(roster_id,ym));
        CREATE TABLE IF NOT EXISTS cc_kv(k TEXT PRIMARY KEY, v TEXT);
        ''')
        c.commit()


def _kv_once(key):
    """True: birinchi marta (belgilandi); False: avval bajarilgan."""
    with nc.db() as c:
        cur = c.execute("INSERT OR IGNORE INTO cc_kv(k,v) VALUES(?,?)", (key, _iso(_now())))
        c.commit(); return cur.rowcount > 0


# ------------------------------------------------------------------ huquqlar
def is_teacher_user(uid):
    if uid is None: return False
    if int(uid) == ADMIN_ID: return True
    try:
        with nc.db() as c:
            return c.execute("SELECT 1 FROM teachers WHERE user_id=? AND active=1", (int(uid),)).fetchone() is not None
    except Exception:
        return False


def class_get(cid):
    with nc.db() as c: return _row(c, "SELECT * FROM cc_classes WHERE id=? AND active=1", (int(cid or 0),))


def class_by_chat(chat_id):
    with nc.db() as c: return _row(c, "SELECT * FROM cc_classes WHERE chat_id=? AND active=1", (int(chat_id),))


def is_owner(k, uid, admin=False): return bool(k) and uid is not None and (admin or int(uid) == int(k['teacher_id']) or int(uid) == ADMIN_ID)


def can_manage(k, uid, admin=False):
    if not k or uid is None: return False
    if is_owner(k, uid, admin): return True
    with nc.db() as c:
        return c.execute("SELECT 1 FROM cc_assist WHERE class_id=? AND user_id=?", (k['id'], int(uid))).fetchone() is not None


def teacher_classes(uid, admin=False):
    with nc.db() as c:
        if admin or (uid is not None and int(uid) == ADMIN_ID):
            return _rows(c, "SELECT * FROM cc_classes WHERE active=1 ORDER BY id DESC")
        return _rows(c, "SELECT * FROM cc_classes WHERE active=1 AND (teacher_id=? OR id IN (SELECT class_id FROM cc_assist WHERE user_id=?)) ORDER BY id DESC",
                     (int(uid), int(uid)))


def me_flags(uid, admin=False):
    if uid is None: return {'class_teacher': False, 'parent_mode': False}
    return {'class_teacher': bool(is_teacher_user(uid) or admin or teacher_classes(uid)), 'parent_mode': bool(parent_children(uid))}


# ------------------------------------------------------------------ sinf
def class_create(teacher_id, name, subject='', chat_id=None, chat_title=''):
    name = re.sub(r'\s+', ' ', str(name or '')).strip()[:60]
    if len(name) < 2: raise ApiErr(400, 'Sinf nomi juda qisqa.')
    with nc.db() as c:
        if chat_id:
            c.execute("UPDATE cc_classes SET chat_id=NULL WHERE chat_id=?", (int(chat_id),))
        cur = c.execute("INSERT INTO cc_classes(teacher_id,name,subject,chat_id,chat_title,created_at) VALUES(?,?,?,?,?,?)",
                        (int(teacher_id), name, str(subject or '')[:40], chat_id, str(chat_title or '')[:80], _iso(_now())))
        c.commit(); return cur.lastrowid


def class_link_chat(cid, chat_id, title=''):
    with nc.db() as c:
        c.execute("UPDATE cc_classes SET chat_id=NULL WHERE chat_id=? AND id<>?", (int(chat_id), int(cid)))
        c.execute("UPDATE cc_classes SET chat_id=?, chat_title=? WHERE id=?", (int(chat_id), str(title or '')[:80], int(cid)))
        c.commit()


def class_unlink_chat(chat_id):
    with nc.db() as c:
        c.execute("UPDATE cc_classes SET chat_id=NULL WHERE chat_id=?", (int(chat_id),)); c.commit()


def class_update(cid, **kw):
    sets, p = [], []
    if 'name' in kw:
        nm = re.sub(r'\s+', ' ', str(kw['name'] or '')).strip()[:60]
        if len(nm) < 2: raise ApiErr(400, 'Sinf nomi juda qisqa.')
        sets.append('name=?'); p.append(nm)
    if 'subject' in kw: sets.append('subject=?'); p.append(str(kw['subject'] or '')[:40])
    if kw.get('notify_mode') in ('auto', 'approve'): sets.append('notify_mode=?'); p.append(kw['notify_mode'])
    if kw.get('rating_names') in ('short', 'full'): sets.append('rating_names=?'); p.append(kw['rating_names'])
    if 'fee_day' in kw:
        try: fd = max(0, min(28, int(kw['fee_day'])))
        except Exception: fd = 0
        sets.append('fee_day=?'); p.append(fd)
    if not sets: return
    with nc.db() as c:
        c.execute(f"UPDATE cc_classes SET {','.join(sets)} WHERE id=?", (*p, int(cid))); c.commit()


def class_delete(cid):
    with nc.db() as c:
        c.execute("UPDATE cc_classes SET active=0, chat_id=NULL WHERE id=?", (int(cid),)); c.commit()


def assist_add(cid, uid):
    with nc.db() as c:
        c.execute("INSERT OR IGNORE INTO cc_assist(class_id,user_id) VALUES(?,?)", (int(cid), int(uid))); c.commit()


def assist_del(cid, uid):
    with nc.db() as c:
        c.execute("DELETE FROM cc_assist WHERE class_id=? AND user_id=?", (int(cid), int(uid))); c.commit()


# ------------------------------------------------------------------ o'quvchilar ro'yxati
def _digits(s): return re.sub(r'\D', '', str(s or ''))


def parse_roster(text):
    """Qator: «Ism Familiya; o'quvchi tel; ota-ona tel». Bitta raqam bo'lsa — ota-ona raqami. Excel'dan nusxa (tab) ham bo'ladi."""
    out = []
    for ln in str(text or '').replace('\r', '').split('\n'):
        ln = re.sub(r'^\s*(\d{1,3}\s*[.)]|[-•*])\s*', '', ln).strip()
        if not ln: continue
        parts = [x.strip() for x in re.split(r'\s*[;,\t|]\s*', ln) if x.strip()]
        name = re.sub(r'\s+', ' ', parts[0])[:60]
        if len(name) < 2 or not re.search(r'[^\W\d_]', name): continue
        ph = [p for p in (_digits(x) for x in parts[1:]) if len(p) >= 9][:2]
        stu, par = ('', ph[0]) if len(ph) == 1 else ((ph[0], ph[1]) if len(ph) == 2 else ('', ''))
        out.append({'name': name, 'phone': stu[-12:], 'parent_phone': par[-12:]})
    return out


def roster_add_many(cid, text):
    items = parse_roster(text); added = skipped = 0
    with nc.db() as c:
        have = {re.sub(r'\s+', ' ', r[0]).lower() for r in c.execute("SELECT full_name FROM cc_roster WHERE class_id=? AND active=1", (int(cid),))}
        for it in items:
            key = it['name'].lower()
            if key in have: skipped += 1; continue
            c.execute("INSERT INTO cc_roster(class_id,full_name,phone,parent_phone,created_at) VALUES(?,?,?,?,?)",
                      (int(cid), it['name'], it['phone'], it['parent_phone'], _iso(_now())))
            have.add(key); added += 1
        c.commit()
    return {'added': added, 'skipped': skipped, 'total': len(items)}


def roster_get(rid):
    with nc.db() as c: return _row(c, "SELECT * FROM cc_roster WHERE id=? AND active=1", (int(rid or 0),))


def roster_list(cid):
    with nc.db() as c:
        rows = _rows(c, """SELECT r.*, a.login AS login, a.id AS acc_id,
            (SELECT COUNT(*) FROM cc_parent_dev d WHERE d.acc_id=a.id) AS parent_devs
            FROM cc_roster r LEFT JOIN cc_parent_acc a ON a.roster_id=r.id WHERE r.class_id=? AND r.active=1 ORDER BY r.full_name COLLATE NOCASE""", (int(cid),))
        ym = datetime.now(UZ).strftime('%Y-%m')
        paid = {r[0] for r in c.execute("SELECT roster_id FROM cc_pay WHERE ym=?", (ym,))}
    for r in rows:
        r['linked'] = bool(r['student_uid']); r['parent_linked'] = (r['parent_devs'] or 0) > 0; r['paid'] = r['id'] in paid
    return rows


def roster_edit(rid, **kw):
    sets, p = [], []
    if 'full_name' in kw:
        nm = re.sub(r'\s+', ' ', str(kw['full_name'] or '')).strip()[:60]
        if len(nm) < 2: raise ApiErr(400, 'Ism juda qisqa.')
        sets.append('full_name=?'); p.append(nm)
    if 'phone' in kw: sets.append('phone=?'); p.append(_digits(kw['phone'])[-12:])
    if 'parent_phone' in kw: sets.append('parent_phone=?'); p.append(_digits(kw['parent_phone'])[-12:])
    if 'fee' in kw:
        try: fee = max(0, min(100000000, int(kw['fee'])))
        except Exception: fee = 0
        sets.append('fee=?'); p.append(fee)
    if sets:
        with nc.db() as c:
            c.execute(f"UPDATE cc_roster SET {','.join(sets)} WHERE id=?", (*p, int(rid))); c.commit()


def roster_del(rid):
    with nc.db() as c:
        c.execute("UPDATE cc_roster SET active=0, student_uid=NULL WHERE id=?", (int(rid),))
        acc = c.execute("SELECT id FROM cc_parent_acc WHERE roster_id=?", (int(rid),)).fetchone()
        if acc:
            c.execute("DELETE FROM cc_parent_dev WHERE acc_id=?", (acc[0],)); c.execute("DELETE FROM cc_parent_acc WHERE id=?", (acc[0],))
        c.commit()


def roster_unlinked(cid):
    with nc.db() as c:
        return _rows(c, "SELECT id, full_name FROM cc_roster WHERE class_id=? AND active=1 AND student_uid IS NULL ORDER BY full_name COLLATE NOCASE", (int(cid),))


def link_student(rid, uid):
    """O'quvchi Telegram akkauntini ro'yxatdagi ismga bog'laydi. Bitta akkaunt sinfda faqat bitta ismga."""
    r = roster_get(rid)
    if not r: return False, 'Ro‘yxatdagi ism topilmadi.'
    with nc.db() as c:
        if r['student_uid'] and int(r['student_uid']) != int(uid): return False, 'Bu ism allaqachon boshqa akkauntga ulangan. Ustozga murojaat qiling.'
        ex = c.execute("SELECT full_name FROM cc_roster WHERE class_id=? AND student_uid=? AND active=1 AND id<>?", (r['class_id'], int(uid), int(rid))).fetchone()
        if ex: return False, f'Siz bu sinfda allaqachon «{ex[0]}» sifatida ulangansiz.'
        c.execute("UPDATE cc_roster SET student_uid=? WHERE id=?", (int(uid), int(rid))); c.commit()
    return True, r['full_name']


def unlink_student(rid):
    with nc.db() as c:
        c.execute("UPDATE cc_roster SET student_uid=NULL WHERE id=?", (int(rid),)); c.commit()


def student_rosters(uid):
    with nc.db() as c:
        return _rows(c, "SELECT r.*, k.name AS class_name, k.chat_id AS chat_id FROM cc_roster r JOIN cc_classes k ON k.id=r.class_id "
                        "WHERE r.student_uid=? AND r.active=1 AND k.active=1", (int(uid),))


# ------------------------------------------------------------------ ota-ona login/parol
_ALPHA = 'abcdefghjkmnpqrstuvwxyz23456789'


def _hash(pw, salt): return hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), bytes.fromhex(salt), 60000).hex()


def acc_create_or_reset(rid):
    """Login/parol yaratadi (yoki parolni yangilaydi). Parol FAQAT shu yerda ochiq qaytadi, bazada xesh turadi.
    Parol yangilansa — eski qurilmalar chiqarib yuboriladi."""
    pw = ''.join(secrets.choice(_ALPHA) for _ in range(6)); salt = secrets.token_hex(8)
    with nc.db() as c:
        a = c.execute("SELECT id, login FROM cc_parent_acc WHERE roster_id=?", (int(rid),)).fetchone()
        if a:
            c.execute("UPDATE cc_parent_acc SET salt=?, pw_hash=? WHERE id=?", (salt, _hash(pw, salt), a[0]))
            c.execute("DELETE FROM cc_parent_dev WHERE acc_id=?", (a[0],)); login = a[1]
        else:
            for _ in range(50):
                login = 'ota' + ''.join(secrets.choice('0123456789') for _ in range(5))
                if not c.execute("SELECT 1 FROM cc_parent_acc WHERE login=?", (login,)).fetchone(): break
            c.execute("INSERT INTO cc_parent_acc(roster_id,login,salt,pw_hash,created_at) VALUES(?,?,?,?,?)", (int(rid), login, salt, _hash(pw, salt), _iso(_now())))
        c.commit()
    return login, pw


def creds_for_class(cid):
    """Login-paroli yo'q o'quvchilar uchun yaratadi. [(ism, login, parol|None)]"""
    out = []
    for r in roster_list(cid):
        if r['login']: out.append((r['full_name'], r['login'], None))
        else:
            lg, pw = acc_create_or_reset(r['id']); out.append((r['full_name'], lg, pw))
    return out


def _fail_get(c, key):
    r = c.execute("SELECT n, until FROM cc_login_fail WHERE k=?", (key,)).fetchone()
    return (r[0], r[1]) if r else (0, None)


def parent_login(tg_uid, login, password):
    """-> (ok, xabar, roster_id|None)"""
    login = re.sub(r'\s+', '', str(login or '')).lower()[:30]; password = str(password or '').strip()[:60]
    if not login or not password: return False, 'Login va parolni kiriting.', None
    keys = ['acc:' + login, 'tg:%s' % int(tg_uid)]; now = _iso(_now())
    with nc.db() as c:
        for k in keys:
            n, until = _fail_get(c, k)
            if until and until > now: return False, f'Ko‘p marta xato kiritildi. {LOGIN_LOCK_MIN} daqiqadan keyin urinib ko‘ring.', None
        a = _row(c, "SELECT * FROM cc_parent_acc WHERE login=?", (login,))
        ok = bool(a) and hmac.compare_digest(_hash(password, a['salt']) if a else '', a['pw_hash'] if a else 'x')
        if not a: _hash(password, '00' * 8)   # vaqt farqini kamaytirish
        if not ok:
            for k in keys:
                n, until = _fail_get(c, k); n = (n if not until or until <= now else 0) + 1
                until2 = _iso(_now() + timedelta(minutes=LOGIN_LOCK_MIN)) if n >= (LOGIN_MAX_FAILS if k.startswith('tg:') else LOGIN_MAX_FAILS_ACC) else None
                c.execute("INSERT INTO cc_login_fail(k,n,until) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET n=excluded.n, until=excluded.until", (k, 0 if until2 else n, until2))
            c.commit(); return False, 'Login yoki parol noto‘g‘ri.', None
        r = _row(c, "SELECT * FROM cc_roster WHERE id=? AND active=1", (a['roster_id'],))
        if not r: return False, 'Bu hisob faol emas. Ustozga murojaat qiling.', None
        for k in keys: c.execute("DELETE FROM cc_login_fail WHERE k=?", (k,))
        c.execute("INSERT OR REPLACE INTO cc_parent_dev(tg_uid,acc_id,bound_at) VALUES(?,?,?)", (int(tg_uid), a['id'], _iso(_now()))); c.commit()
    return True, r['full_name'], r['id']


def parent_logout(tg_uid):
    with nc.db() as c:
        c.execute("DELETE FROM cc_parent_dev WHERE tg_uid=?", (int(tg_uid),)); c.commit()


def parent_children(tg_uid):
    """Shu Telegram akkaunt ulangan farzandlar: [{rid, name, class_id, class_name}]"""
    if tg_uid is None: return []
    with nc.db() as c:
        return _rows(c, """SELECT r.id AS rid, r.full_name AS name, r.class_id AS class_id, k.name AS class_name FROM cc_parent_dev d
            JOIN cc_parent_acc a ON a.id=d.acc_id JOIN cc_roster r ON r.id=a.roster_id AND r.active=1 JOIN cc_classes k ON k.id=r.class_id AND k.active=1
            WHERE d.tg_uid=? ORDER BY r.full_name COLLATE NOCASE""", (int(tg_uid),))


def parent_tg_ids(rid):
    with nc.db() as c:
        return [r[0] for r in c.execute("SELECT d.tg_uid FROM cc_parent_dev d JOIN cc_parent_acc a ON a.id=d.acc_id WHERE a.roster_id=?", (int(rid),))]


# ------------------------------------------------------------------ xabar navbati
def queue(chat_id, text, kind='', ref=None, rid=None, quiet=False, markup=None):
    after = quiet_after() if quiet else _iso(_now())
    with nc.db() as c:
        c.execute("INSERT INTO cc_outbox(chat_id,text,send_after,kind,ref,roster_id,markup_json) VALUES(?,?,?,?,?,?,?)",
                  (int(chat_id), str(text)[:4000], after, kind, ref, rid, json.dumps(markup) if markup else None)); c.commit()


def outbox_due(limit=30):
    hold = "" if get_cfg()['enabled'] else " AND roster_id IS NULL"   # admin «to‘xtatish»ni yoqqan bo‘lsa: ota-ona/o‘quvchi xabarlari ushlab turiladi, ustozga xabarlar ketaveradi
    with nc.db() as c:
        return _rows(c, "SELECT * FROM cc_outbox WHERE sent_at IS NULL AND send_after<=? AND tries<5" + hold + " ORDER BY id LIMIT ?", (_iso(_now()), int(limit)))


def outbox_done(oid, ok, err=''):
    with nc.db() as c:
        if ok or err == 'blocked':
            c.execute("UPDATE cc_outbox SET sent_at=?, err=? WHERE id=?", (_iso(_now()), err, int(oid)))
        else:
            # qayta urinish: ota-ona xabari ruxsat etilgan oynadan tashqariga (kechasi) tushmasin; Telegram tezlik cheklovi (429) urinish hisobiga kirmasin
            row = c.execute("SELECT roster_id FROM cc_outbox WHERE id=?", (int(oid),)).fetchone()
            nxt = _now() + timedelta(minutes=(1 if err == 'http429' else 2))
            after = quiet_after(nxt) if (row and row[0] is not None) else _iso(nxt)
            c.execute("UPDATE cc_outbox SET tries=tries+?, send_after=?, err=? WHERE id=?", (0 if err == 'http429' else 1, after, err[:60], int(oid)))
        c.commit()


def tell_teacher(k, text, markup=None, kind='t', ref=None):
    queue(k['teacher_id'], text, kind, ref, None, False, markup)


def notify_parent(rid, text, kind, ref):
    """1 — navbatga qo'yildi, 0 — ota-ona ulanmagan, -1 — avval yuborilgan."""
    with nc.db() as c:
        if c.execute("SELECT 1 FROM cc_notif WHERE kind=? AND ref=? AND roster_id=?", (kind, int(ref), int(rid))).fetchone(): return -1
    ids = parent_tg_ids(rid)
    if not ids: return 0
    with nc.db() as c:
        c.execute("INSERT OR IGNORE INTO cc_notif(kind,ref,roster_id,at) VALUES(?,?,?,?)", (kind, int(ref), int(rid), _iso(_now()))); c.commit()
    for t in ids: queue(t, text, kind, int(ref), rid, True)
    return 1


def _notify_many(items, kind, ref):
    """items: [(rid, name, text)] -> (yuborildi, ota-onasi ulanmagan ismlar)"""
    sent, nop = 0, []
    for rid, name, text in items:
        r = notify_parent(rid, text, kind, ref)
        if r == 1: sent += 1
        elif r == 0: nop.append(name)
    return sent, nop


def msg_parents(cid, text, rid=None):
    text = str(text or '').strip()[:1500]
    if not text: raise ApiErr(400, 'Xabar matni bo‘sh.')
    k = class_get(cid); n = 0; nop = []
    for r in roster_list(cid):
        if rid and int(r['id']) != int(rid): continue
        ids = parent_tg_ids(r['id'])
        if not ids: nop.append(r['full_name']); continue
        for t in ids: queue(t, f"📩 Ustoz xabari ({k['name']}):\n\n{text}", 'msg', None, r['id'], True); n += 1
    return {'sent': n, 'no_parent': nop}


def _names(rows, key='full_name', lim=15):
    ns = [r[key] for r in rows]
    return ', '.join(ns[:lim]) + (f' va yana {len(ns) - lim} ta' if len(ns) > lim else '')


def _markup_np(kind, ref):
    return {'inline_keyboard': [[{'text': '📨 Ota-onalarga yuborish', 'callback_data': f'cc_np:{kind}:{ref}'}]]}


# ------------------------------------------------------------------ davomat
def att_start(cid, minutes=20, title='', mode='code', chat_id=None, msg_id=None):
    k = class_get(cid)
    with nc.db() as c:
        open_ids = [r[0] for r in c.execute("SELECT id FROM cc_att_s WHERE class_id=? AND closed=0", (int(cid),))]
    for sid in open_ids: att_finalize(sid)
    try: minutes = max(2, min(180, int(minutes)))
    except Exception: minutes = 20
    code = ''.join(secrets.choice('0123456789') for _ in range(4)) if mode == 'code' else ''
    n = datetime.now(UZ); title = (str(title or '').strip() or f"Dars {n.strftime('%d.%m')}")[:60]
    with nc.db() as c:
        cur = c.execute("INSERT INTO cc_att_s(class_id,day,title,code,mode,open_until,created_at,chat_id,msg_id) VALUES(?,?,?,?,?,?,?,?,?)",
                        (int(cid), n.date().isoformat(), title, code, 'code' if mode == 'code' else 'button', _iso(_now() + timedelta(minutes=minutes)), _iso(_now()), chat_id, msg_id))
        c.commit(); sid = cur.lastrowid
    return att_get(sid)


def att_get(sid):
    with nc.db() as c: return _row(c, "SELECT * FROM cc_att_s WHERE id=?", (int(sid or 0),))


def att_set_msg(sid, chat_id, msg_id):
    with nc.db() as c:
        c.execute("UPDATE cc_att_s SET chat_id=?, msg_id=? WHERE id=?", (chat_id, msg_id, int(sid))); c.commit()


def att_mark(sid, rid, status, via='teacher', note=None):
    if status not in STATUS_UZ: raise ApiErr(400, 'Noto‘g‘ri holat.')
    s = att_get(sid)
    if not s: raise ApiErr(404, 'Davomat topilmadi.')
    with nc.db() as c:
        if note is None:
            old = c.execute("SELECT note FROM cc_att WHERE session_id=? AND roster_id=?", (int(sid), int(rid))).fetchone(); note = old[0] if old else ''
        c.execute("INSERT INTO cc_att(session_id,roster_id,status,via,at,note) VALUES(?,?,?,?,?,?) ON CONFLICT(session_id,roster_id) DO UPDATE SET status=excluded.status, via=excluded.via, at=excluded.at",
                  (int(sid), int(rid), status, via, _iso(_now()), note)); c.commit()
    if s['closed'] and status in ('a', 'l'):   # yakunlangandan keyin ustoz tuzatsa — avto rejimda ota-onaga xabar
        k = class_get(s['class_id'])
        if k and k['notify_mode'] == 'auto':
            r = roster_get(rid)
            if r: notify_parent(rid, _msg_att(r['full_name'], k['name'], s, status), 'att', sid)


def att_self(uid, code=None):
    """O'quvchi o'zi belgilanadi. -> (ok, matn)"""
    code = re.sub(r'\D', '', str(code or ''))
    rows = student_rosters(uid)
    if not rows: return False, 'Siz hech bir sinf ro‘yxatiga ulanmagansiz. Ustozdan havola so‘rang.'
    now = _iso(_now()); wrong = False; found = False
    for r in rows:
        with nc.db() as c:
            for s in _rows(c, "SELECT * FROM cc_att_s WHERE class_id=? AND closed=0 AND open_until>? ORDER BY id DESC", (r['class_id'], now)):
                found = True
                if s['mode'] == 'code' and code != s['code']: wrong = True; continue
                late = _parse(now) > _parse(s['created_at']) + timedelta(minutes=LATE_AFTER_MIN)
                old = c.execute("SELECT status FROM cc_att WHERE session_id=? AND roster_id=?", (s['id'], r['id'])).fetchone()
                if old and old[0] in ('p', 'l'): return True, f"Siz allaqachon belgilangansiz ({STATUS_UZ[old[0]]})."
                att_mark(s['id'], r['id'], 'l' if late else 'p', 'self')
                return True, f"✅ {r['full_name']}, davomat belgilandi" + (' (kechikdingiz).' if late else '.')
    if wrong: return False, '❌ Kod noto‘g‘ri. Darsda e’lon qilingan kodni tekshiring.'
    return False, 'Hozir ochiq davomat yo‘q.' if not found else 'Davomatni belgilab bo‘lmadi.'


def _msg_att(name, cname, s, st):
    if st == 'a': return f"⚠️ {name} bugun ({fmt_day(s['created_at'])}) «{cname}» — «{s['title']}» darsiga KELMADI.\nSababi bo‘lsa, ustozga Mini App → Ustoz paneli orqali xabar bering."
    if st == 'l': return f"⏰ {name} bugun «{cname}» — «{s['title']}» darsiga kechikib keldi."
    return ''


def att_finalize(sid):
    s = att_get(sid)
    if not s or s['closed']: return None
    k = class_get(s['class_id'])
    if not k:
        with nc.db() as c: c.execute("UPDATE cc_att_s SET closed=1 WHERE id=?", (int(sid),)); c.commit()
        return None
    ros = roster_list(k['id'])
    with nc.db() as c:
        have = {r[0] for r in c.execute("SELECT roster_id FROM cc_att WHERE session_id=?", (int(sid),))}
        for r in ros:
            if r['id'] not in have:
                c.execute("INSERT INTO cc_att(session_id,roster_id,status,via,at) VALUES(?,?,'a','auto',?)", (int(sid), r['id'], _iso(_now())))
        c.execute("UPDATE cc_att_s SET closed=1 WHERE id=?", (int(sid),)); c.commit()
        marks = {r[0]: r[1] for r in c.execute("SELECT roster_id,status FROM cc_att WHERE session_id=?", (int(sid),))}
    pres = [r for r in ros if marks.get(r['id']) == 'p']; late = [r for r in ros if marks.get(r['id']) == 'l']
    absn = [r for r in ros if marks.get(r['id']) == 'a']; exc = [r for r in ros if marks.get(r['id']) == 'e']
    L = [f"📋 Davomat yakunlandi — {k['name']} • {s['title']}", f"✅ Keldi: {len(pres)} • ⏰ Kechikdi: {len(late)} • ❌ Kelmadi: {len(absn)}" + (f" • 📝 Sababli: {len(exc)}" if exc else '')]
    if absn: L.append('❌ Kelmaganlar: ' + _names(absn))
    if late: L.append('⏰ Kechikkanlar: ' + _names(late))
    markup = None
    if absn or late:
        if k['notify_mode'] == 'auto':
            items = [(r['id'], r['full_name'], _msg_att(r['full_name'], k['name'], s, marks[r['id']])) for r in absn + late]
            sent, nop = _notify_many(items, 'att', sid)
            L.append(f"📨 Ota-onalarga xabar: {sent} ta")
            if nop: L.append('⚠️ Ota-onasi ulanmagan (login/parol bering): ' + ', '.join(nop[:15]))
        else:
            L.append('Ota-onalarga yuborish uchun tugmani bosing.'); markup = _markup_np('att', sid)
    risky = []
    with nc.db() as c:
        last = [r[0] for r in c.execute("SELECT id FROM cc_att_s WHERE class_id=? AND closed=1 ORDER BY id DESC LIMIT 3", (k['id'],))]
        if len(last) == 3:
            for r in absn:
                n = c.execute(f"SELECT COUNT(*) FROM cc_att WHERE roster_id=? AND status='a' AND session_id IN ({','.join('?' * 3)})", (r['id'], *last)).fetchone()[0]
                if n == 3: risky.append(r)
    if risky: L.append('🚨 Ketma-ket 3 ta darsga kelmadi: ' + _names(risky))
    tell_teacher(k, '\n'.join(L), markup, 'attsum', sid)
    return {'present': len(pres), 'late': len(late), 'absent': len(absn), 'excused': len(exc)}


def att_notify(sid):
    s = att_get(sid)
    if not s: raise ApiErr(404, 'Davomat topilmadi.')
    k = class_get(s['class_id'])
    with nc.db() as c:
        rows = _rows(c, "SELECT a.roster_id rid, a.status st, r.full_name nm FROM cc_att a JOIN cc_roster r ON r.id=a.roster_id WHERE a.session_id=? AND a.status IN ('a','l')", (int(sid),))
    sent, nop = _notify_many([(r['rid'], r['nm'], _msg_att(r['nm'], k['name'], s, r['st'])) for r in rows], 'att', sid)
    return {'sent': sent, 'no_parent': nop}


def att_detail(sid):
    s = att_get(sid)
    if not s: return None
    with nc.db() as c:
        marks = {r[0]: {'status': r[1], 'via': r[2], 'note': r[3]} for r in c.execute("SELECT roster_id,status,via,note FROM cc_att WHERE session_id=?", (int(sid),))}
    ros = roster_list(s['class_id'])
    return {'session': s, 'rows': [{'rid': r['id'], 'name': r['full_name'], 'status': (marks.get(r['id']) or {}).get('status', ''), 'via': (marks.get(r['id']) or {}).get('via', ''),
                                    'note': (marks.get(r['id']) or {}).get('note', '')} for r in ros]}


def att_excuse(tg_uid, sid, rid, note):
    if int(rid) not in [c['rid'] for c in parent_children(tg_uid)]: raise ApiErr(403, 'Bu farzand sizga ulanmagan.')
    note = re.sub(r'\s+', ' ', str(note or '')).strip()[:300]
    if len(note) < 3: raise ApiErr(400, 'Sababni yozing.')
    s = att_get(sid); r = roster_get(rid)
    if not s or not r or s['class_id'] != r['class_id']: raise ApiErr(404, 'Dars topilmadi.')
    with nc.db() as c:
        cur = c.execute("UPDATE cc_att SET note=? WHERE session_id=? AND roster_id=? AND status IN ('a','l')", (note, int(sid), int(rid))); c.commit()
        if cur.rowcount == 0: raise ApiErr(400, 'Bu darsga sabab yozib bo‘lmaydi.')
    k = class_get(s['class_id'])
    tell_teacher(k, f"📝 {r['full_name']} ota-onasi sababli deb xabar berdi ({s['title']}, {fmt_day(s['created_at'])}):\n«{note}»",
                 {'inline_keyboard': [[{'text': '✅ Sababli deb belgilash', 'callback_data': f'cc_ex:{sid}:{rid}'}]]}, 'excuse', sid)
    return True


# ------------------------------------------------------------------ vazifa
def hw_create(cid, by, title, text='', due_at=None, chat_id=None, msg_id=None):
    title = re.sub(r'\s+', ' ', str(title or '')).strip()[:100]
    if len(title) < 2: raise ApiErr(400, 'Vazifa nomi juda qisqa.')
    with nc.db() as c:
        cur = c.execute("INSERT INTO cc_hw(class_id,title,text,due_at,created_at,created_by,chat_id,msg_id) VALUES(?,?,?,?,?,?,?,?)",
                        (int(cid), title, str(text or '')[:3000], due_at or default_due(), _iso(_now()), by, chat_id, msg_id)); c.commit()
        return cur.lastrowid


def hw_get(hid):
    with nc.db() as c: return _row(c, "SELECT * FROM cc_hw WHERE id=?", (int(hid or 0),))


def hw_by_msg(chat_id, msg_id):
    with nc.db() as c: return _row(c, "SELECT * FROM cc_hw WHERE chat_id=? AND msg_id=?", (int(chat_id), int(msg_id)))


def hw_set_msg(hid, chat_id, msg_id):
    with nc.db() as c:
        c.execute("UPDATE cc_hw SET chat_id=?, msg_id=? WHERE id=?", (chat_id, msg_id, int(hid))); c.commit()


def hw_submit(hid, rid, kind='button'):
    """-> 'new' | 'again'"""
    with nc.db() as c:
        if c.execute("SELECT 1 FROM cc_hw_sub WHERE hw_id=? AND roster_id=?", (int(hid), int(rid))).fetchone():
            if kind == 'reply': c.execute("UPDATE cc_hw_sub SET kind=? WHERE hw_id=? AND roster_id=? AND kind='button'", (kind, int(hid), int(rid))); c.commit()
            return 'again'
        c.execute("INSERT INTO cc_hw_sub(hw_id,roster_id,kind,at) VALUES(?,?,?,?)", (int(hid), int(rid), kind, _iso(_now()))); c.commit()
    return 'new'


def hw_mark(hid, rid, on):
    with nc.db() as c:
        if on: c.execute("INSERT OR IGNORE INTO cc_hw_sub(hw_id,roster_id,kind,at) VALUES(?,?,'teacher',?)", (int(hid), int(rid), _iso(_now())))
        else: c.execute("DELETE FROM cc_hw_sub WHERE hw_id=? AND roster_id=?", (int(hid), int(rid)))
        c.commit()


def hw_grade(hid, rid, grade):
    try: g = None if grade in (None, '') else max(0, min(100, int(grade)))
    except Exception: raise ApiErr(400, 'Ball 0–100 oralig‘ida bo‘lsin.')
    with nc.db() as c:
        c.execute("INSERT OR IGNORE INTO cc_hw_sub(hw_id,roster_id,kind,at) VALUES(?,?,'teacher',?)", (int(hid), int(rid), _iso(_now())))
        c.execute("UPDATE cc_hw_sub SET grade=? WHERE hw_id=? AND roster_id=?", (g, int(hid), int(rid))); c.commit()


def hw_delete(hid):
    with nc.db() as c:
        c.execute("DELETE FROM cc_hw_sub WHERE hw_id=?", (int(hid),)); c.execute("DELETE FROM cc_hw WHERE id=?", (int(hid),)); c.commit()


def hw_detail(hid):
    h = hw_get(hid)
    if not h: return None
    with nc.db() as c:
        subs = {r['roster_id']: dict(r) for r in c.execute("SELECT * FROM cc_hw_sub WHERE hw_id=?", (int(hid),)).fetchall()}
    rows = []
    for r in roster_list(h['class_id']):
        s = subs.get(r['id'])
        st = 'miss'
        if s: st = 'done' if (s['kind'] == 'teacher' or s['at'][:19] <= h['due_at'][:19]) else 'late'
        rows.append({'rid': r['id'], 'name': r['full_name'], 'status': st, 'kind': s['kind'] if s else '', 'grade': s['grade'] if s else None, 'at': fmt(s['at']) if s else ''})
    return {'hw': h, 'rows': rows, 'due_text': fmt(h['due_at']), 'is_due': h['due_at'][:19] <= _iso(_now())}


def hw_counts(hid):
    h = hw_get(hid)
    with nc.db() as c:
        done = c.execute("SELECT COUNT(*) FROM cc_hw_sub s JOIN cc_roster r ON r.id=s.roster_id AND r.active=1 WHERE s.hw_id=?", (int(hid),)).fetchone()[0]
        tot = c.execute("SELECT COUNT(*) FROM cc_roster WHERE class_id=? AND active=1", (h['class_id'],)).fetchone()[0]
    return done, tot


def _hw_missers(h):
    ros = roster_list(h['class_id'])
    with nc.db() as c: ok = {r[0] for r in c.execute("SELECT roster_id FROM cc_hw_sub WHERE hw_id=?", (h['id'],))}
    return [r for r in ros if r['id'] not in ok], len(ros)


def _msg_hw(name, h): return f"📚 {name} «{h['title']}» vazifasini muddatida (≤ {fmt(h['due_at'])}) topshirmadi."


def hw_finalize(hid):
    h = hw_get(hid)
    if not h or h['finalized']: return None
    with nc.db() as c: c.execute("UPDATE cc_hw SET finalized=1 WHERE id=?", (int(hid),)); c.commit()
    k = class_get(h['class_id'])
    if not k: return None
    miss, total = _hw_missers(h)
    L = [f"📚 Vazifa muddati tugadi — {k['name']}", f"«{h['title']}»", f"✅ Topshirdi: {total - len(miss)}/{total}"]
    markup = None
    if miss:
        L.append('❌ Topshirmaganlar: ' + _names(miss))
        if k['notify_mode'] == 'auto':
            sent, nop = _notify_many([(r['id'], r['full_name'], _msg_hw(r['full_name'], h)) for r in miss], 'hw', hid)
            L.append(f'📨 Ota-onalarga xabar: {sent} ta')
            if nop: L.append('⚠️ Ota-onasi ulanmagan: ' + ', '.join(nop[:15]))
        else:
            L.append('Ota-onalarga yuborish uchun tugmani bosing.'); markup = _markup_np('hw', hid)
    tell_teacher(k, '\n'.join(L), markup, 'hwsum', hid)
    return {'missed': len(miss), 'total': total}


def hw_notify(hid):
    h = hw_get(hid)
    if not h: raise ApiErr(404, 'Vazifa topilmadi.')
    miss, _ = _hw_missers(h)
    sent, nop = _notify_many([(r['id'], r['full_name'], _msg_hw(r['full_name'], h)) for r in miss], 'hw', hid)
    return {'sent': sent, 'no_parent': nop}


def hw_remind(hid):
    h = hw_get(hid)
    with nc.db() as c: c.execute("UPDATE cc_hw SET reminded=1 WHERE id=?", (int(hid),)); c.commit()
    if not h: return 0
    miss, _ = _hw_missers(h); n = 0
    for r in miss:
        if r['student_uid']:
            queue(r['student_uid'], f"⏰ Eslatma: «{h['title']}» vazifasi muddati — {fmt(h['due_at'])}. Ulgurib topshiring!", 'hwrem', hid, r['id'], True); n += 1
    return n


# ------------------------------------------------------------------ test qatnashuvi
def _test_meta(kind, code):
    code = str(code or '').upper().strip()
    tbl = {'ms': 'national_tests', 'simple': 'simple_tests'}.get(kind)
    if not tbl or not code: return None
    with nc.db() as c: return _row(c, f"SELECT id, code, title FROM {tbl} WHERE code=?", (code,))


def test_assign(cid, kind, code, hours=48):
    m = _test_meta(kind, code)
    if not m: raise ApiErr(404, 'Bunday kodli test topilmadi.')
    try: hours = max(1, min(24 * 60, int(hours)))
    except Exception: hours = 48
    with nc.db() as c:
        cur = c.execute("INSERT INTO cc_tests(class_id,kind,code,title,due_at,created_at) VALUES(?,?,?,?,?,?)",
                        (int(cid), kind, m['code'], m['title'] or '', _iso(_now() + timedelta(hours=hours)), _iso(_now()))); c.commit()
        return cur.lastrowid


def test_get(tid):
    with nc.db() as c: return _row(c, "SELECT * FROM cc_tests WHERE id=?", (int(tid or 0),))


def _test_scores(t, uids):
    """{uid: foiz} — test biriktirilgandan keyingi BIRINCHI urinish."""
    uids = [int(u) for u in uids if u]
    if not uids: return {}
    m = _test_meta(t['kind'], t['code'])
    if not m: return {}
    out = {}
    with nc.db() as c:
        q = ','.join('?' * len(uids))
        if t['kind'] == 'ms':
            rows = c.execute(f"SELECT user_id, diagnostic_score, raw_score, created_at FROM national_attempts WHERE test_id=? AND user_id IN ({q}) ORDER BY id", (m['id'], *uids)).fetchall()
            for r in rows:
                if r['created_at'][:19] < t['created_at'][:19] or r['user_id'] in out: continue
                sc = r['diagnostic_score'] if r['diagnostic_score'] is not None else r['raw_score']
                out[r['user_id']] = round(max(0.0, min(100.0, float(sc or 0) / MS_MAX * 100)), 1)
        else:
            rows = c.execute(f"SELECT user_id, correct, total, created_at FROM simple_attempts WHERE test_id=? AND user_id IN ({q}) ORDER BY id", (m['id'], *uids)).fetchall()
            for r in rows:
                if r['created_at'][:19] < t['created_at'][:19] or r['user_id'] in out: continue
                out[r['user_id']] = round((r['correct'] or 0) / r['total'] * 100, 1) if r['total'] else 0.0
    return out


def test_detail(tid):
    t = test_get(tid)
    if not t: return None
    ros = roster_list(t['class_id']); sc = _test_scores(t, [r['student_uid'] for r in ros])
    rows = [{'rid': r['id'], 'name': r['full_name'], 'linked': r['linked'], 'took': bool(r['student_uid'] and int(r['student_uid']) in sc),
             'pct': sc.get(int(r['student_uid'])) if r['student_uid'] else None} for r in ros]
    return {'test': t, 'rows': rows, 'due_text': fmt(t['due_at']), 'is_due': t['due_at'][:19] <= _iso(_now())}


def _msg_test(r, t):
    if r['took']: return f"📝 {r['name']} «{t['title'] or t['code']}» testida qatnashdi. Natija: {r['pct']}%."
    return f"📝 {r['name']} «{t['title'] or t['code']}» testida (≤ {fmt(t['due_at'])}) QATNASHMADI."


def test_finalize(tid):
    t = test_get(tid)
    if not t or t['finalized']: return None
    with nc.db() as c: c.execute("UPDATE cc_tests SET finalized=1 WHERE id=?", (int(tid),)); c.commit()
    k = class_get(t['class_id'])
    if not k: return None
    d = test_detail(tid); took = [r for r in d['rows'] if r['took']]; miss = [r for r in d['rows'] if not r['took']]
    avg = round(sum(r['pct'] for r in took) / len(took), 1) if took else None
    L = [f"📝 Test muddati tugadi — {k['name']}", f"«{t['title'] or t['code']}» ({t['code']})", f"✅ Qatnashdi: {len(took)}/{len(d['rows'])}" + (f" • o‘rtacha {avg}%" if avg is not None else '')]
    if miss: L.append('❌ Qatnashmaganlar: ' + ', '.join(r['name'] for r in miss[:15]) + (f' va yana {len(miss) - 15} ta' if len(miss) > 15 else ''))
    markup = None
    if k['notify_mode'] == 'auto':
        sent, nop = _notify_many([(r['rid'], r['name'], _msg_test(r, t)) for r in d['rows']], 'tst', tid)
        L.append(f'📨 Ota-onalarga xabar: {sent} ta')
        if nop: L.append('⚠️ Ota-onasi ulanmagan: ' + ', '.join(nop[:15]))
    else:
        L.append('Ota-onalarga yuborish uchun tugmani bosing.'); markup = _markup_np('tst', tid)
    tell_teacher(k, '\n'.join(L), markup, 'tstsum', tid)
    return {'took': len(took), 'missed': len(miss)}


def test_notify(tid):
    t = test_get(tid)
    if not t: raise ApiErr(404, 'Test topilmadi.')
    d = test_detail(tid)
    sent, nop = _notify_many([(r['rid'], r['name'], _msg_test(r, t)) for r in d['rows']], 'tst', tid)
    return {'sent': sent, 'no_parent': nop}


def test_delete(tid):
    with nc.db() as c: c.execute("DELETE FROM cc_tests WHERE id=?", (int(tid),)); c.commit()


# ------------------------------------------------------------------ o'zlashtirish va reyting
def _pct(x): return None if x is None else round(x, 1)


def _comp(att, hw, tst):
    parts = [(v, w) for v, w in ((att, W_ATT), (hw, W_HW), (tst, W_TEST)) if v is not None]
    if not parts: return None
    return round(sum(v * w for v, w in parts) / sum(w for _, w in parts), 1)


def class_stats(cid):
    """{rid: {att, hw, test, comp, grade, ...}} — bitta sinf bo'yicha."""
    now = _iso(_now())
    with nc.db() as c:
        ros = _rows(c, "SELECT * FROM cc_roster WHERE class_id=? AND active=1", (int(cid),))
        att = {}
        for r in c.execute("SELECT a.roster_id rid, a.status st, COUNT(*) n FROM cc_att a JOIN cc_att_s s ON s.id=a.session_id WHERE s.class_id=? AND s.closed=1 GROUP BY a.roster_id, a.status", (int(cid),)):
            att.setdefault(r['rid'], {})[r['st']] = r['n']
        hws = _rows(c, "SELECT * FROM cc_hw WHERE class_id=? AND due_at<=?", (int(cid), now))
        subs = {(r['hw_id'], r['roster_id']): dict(r) for r in c.execute("SELECT s.* FROM cc_hw_sub s JOIN cc_hw h ON h.id=s.hw_id WHERE h.class_id=?", (int(cid),)).fetchall()}
        tests = _rows(c, "SELECT * FROM cc_tests WHERE class_id=?", (int(cid),))
    uids = [r['student_uid'] for r in ros if r['student_uid']]
    tsc = {t['id']: _test_scores(t, uids) for t in tests}
    out = {}
    for r in ros:
        a = att.get(r['id'], {}); n = sum(a.get(x, 0) for x in 'pla')
        att_pct = None if n == 0 else round((a.get('p', 0) + 0.5 * a.get('l', 0)) / n * 100, 1)
        done = 0.0; grades = []
        for h in hws:
            s = subs.get((h['id'], r['id']))
            if s:
                done += 1 if (s['kind'] == 'teacher' or s['at'][:19] <= h['due_at'][:19]) else 0.5
        for (hid, rid), s in subs.items():
            if rid == r['id'] and s['grade'] is not None: grades.append(s['grade'])
        hw_pct = None if not hws else round(done / len(hws) * 100, 1)
        vals = []
        for t in tests:
            v = tsc[t['id']].get(int(r['student_uid'])) if r['student_uid'] else None
            if v is not None: vals.append(v)
            elif t['due_at'] <= now: vals.append(0.0)
        test_pct = None if not vals else round(sum(vals) / len(vals), 1)
        out[r['id']] = {'rid': r['id'], 'name': r['full_name'], 'att': att_pct, 'hw': hw_pct, 'test': test_pct, 'comp': _comp(att_pct, hw_pct, test_pct),
                        'grade': round(sum(grades) / len(grades), 1) if grades else None, 'absent': a.get('a', 0), 'late': a.get('l', 0), 'present': a.get('p', 0),
                        'excused': a.get('e', 0), 'linked': bool(r['student_uid'])}
    return out


def _disp(name, mode):
    if mode == 'full': return name
    p = name.split()
    return p[0] + (' ' + p[-1][0] + '.' if len(p) > 1 else '')


def class_rating(cid, hl=None, names=None, top=None):
    k = class_get(cid); st = class_stats(cid); mode = names or (k['rating_names'] if k else 'short')
    arr = sorted(st.values(), key=lambda x: (x['comp'] is None, -(x['comp'] or 0), x['name'].lower()))
    rows = []
    for i, x in enumerate(arr, 1):
        rows.append({'rank': i, 'rid': x['rid'], 'name': _disp(x['name'], mode), 'comp': x['comp'], 'att': x['att'], 'hw': x['hw'], 'test': x['test'], 'me': hl is not None and int(hl) == x['rid']})
    comps = [x['comp'] for x in arr if x['comp'] is not None]
    res = {'n': len(arr), 'avg': round(sum(comps) / len(comps), 1) if comps else None,
           'avg_att': _avg([x['att'] for x in arr]), 'avg_hw': _avg([x['hw'] for x in arr]), 'avg_test': _avg([x['test'] for x in arr])}
    if top:
        sel = rows[:top]
        mine = next((r for r in rows if r['me']), None)
        if mine and mine not in sel: sel.append(mine)
        rows = sel
    res['rows'] = rows
    return res


def _avg(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 1) if v else None


def _verdict(comp):
    if comp is None: return 'Ma’lumot yetarli emas'
    return 'A’lo' if comp >= 85 else 'Yaxshi' if comp >= 70 else 'Qoniqarli' if comp >= 50 else 'Past — e’tibor kerak'


def child_profile(rid, full=True):
    r = roster_get(rid)
    if not r: return None
    k = class_get(r['class_id'])
    if not k: return None
    st = class_stats(k['id']); me = st.get(int(rid)) or {}
    rating = class_rating(k['id'], hl=rid, top=10)
    me_row = next((x for x in class_rating(k['id'], hl=rid)['rows'] if x['me']), None)
    out = {'rid': int(rid), 'name': r['full_name'], 'class_id': k['id'], 'class_name': k['name'], 'subject': k['subject'], 'stats': me, 'verdict': _verdict(me.get('comp')),
           'rank': me_row['rank'] if me_row and me_row['comp'] is not None else None, 'n': rating['n'], 'class_avg': rating['avg'],
           'class_avg_att': rating['avg_att'], 'class_avg_hw': rating['avg_hw'], 'class_avg_test': rating['avg_test'], 'rating': rating['rows']}
    if not full: return out
    now = _iso(_now()); ym = datetime.now(UZ).strftime('%Y-%m')
    with nc.db() as c:
        out['att'] = _rows(c, """SELECT s.id AS sid, s.title, s.created_at AS at, a.status, a.note FROM cc_att a JOIN cc_att_s s ON s.id=a.session_id
                                 WHERE a.roster_id=? AND s.closed=1 ORDER BY s.id DESC LIMIT 25""", (int(rid),))
        hws = _rows(c, "SELECT h.id, h.title, h.due_at, s.at AS sat, s.kind, s.grade FROM cc_hw h LEFT JOIN cc_hw_sub s ON s.hw_id=h.id AND s.roster_id=? WHERE h.class_id=? ORDER BY h.id DESC LIMIT 20", (int(rid), k['id']))
        tests = _rows(c, "SELECT * FROM cc_tests WHERE class_id=? ORDER BY id DESC LIMIT 15", (k['id'],))
        out['paid'] = c.execute("SELECT 1 FROM cc_pay WHERE roster_id=? AND ym=?", (int(rid), ym)).fetchone() is not None
        wk = []
        for w in range(4):
            a, b = _iso(_now() - timedelta(days=7 * (w + 1))), _iso(_now() - timedelta(days=7 * w))
            rr = c.execute("SELECT a.status, COUNT(*) FROM cc_att a JOIN cc_att_s s ON s.id=a.session_id WHERE a.roster_id=? AND s.closed=1 AND s.created_at>? AND s.created_at<=? GROUP BY a.status", (int(rid), a, b)).fetchall()
            d = {x[0]: x[1] for x in rr}; n = sum(d.get(q, 0) for q in 'pla')
            wk.append({'week': w, 'pct': None if n == 0 else round((d.get('p', 0) + 0.5 * d.get('l', 0)) / n * 100, 1), 'n': n})
        out['weeks'] = list(reversed(wk))
        pts = None
        if r['student_uid']:
            try:
                cut = (datetime.now(UZ).date() - timedelta(days=7)).isoformat()
                g = c.execute("SELECT COALESCE(SUM(points),0), COUNT(DISTINCT day) FROM game_plays WHERE user_id=? AND day>=?", (int(r['student_uid']), cut)).fetchone()
                pts = {'points': int(g[0]), 'days': int(g[1])}
            except Exception: pts = None
        out['activity'] = pts
    out['hw'] = []
    for h in hws:
        if h['sat']: s = 'done' if (h['kind'] == 'teacher' or h['sat'][:19] <= h['due_at'][:19]) else 'late'
        else: s = 'miss' if h['due_at'] <= now else 'open'
        out['hw'].append({'id': h['id'], 'title': h['title'], 'due': fmt(h['due_at']), 'status': s, 'grade': h['grade']})
    sc = {t['id']: _test_scores(t, [r['student_uid']]) for t in tests}
    out['tests'] = []
    for t in tests:
        v = sc[t['id']].get(int(r['student_uid'])) if r['student_uid'] else None
        out['tests'].append({'id': t['id'], 'title': t['title'] or t['code'], 'code': t['code'], 'due': fmt(t['due_at']), 'pct': v,
                             'status': 'took' if v is not None else ('miss' if t['due_at'] <= now else 'open')})
    for a in out['att']: a['date'] = fmt_day(a['at']); a['status_uz'] = STATUS_UZ.get(a['status'], '')
    out['linked'] = bool(r['student_uid']); out['fee'] = r['fee']
    return out


def parent_weekly_text(rid):
    p = child_profile(rid, full=False)
    if not p: return ''
    s = p['stats']
    def f(v): return '—' if v is None else f'{v}%'
    L = [f"📊 {p['name']} — haftalik hisobot ({p['class_name']})", f"• Davomat: {f(s.get('att'))} (kelmagan: {s.get('absent', 0)}, kechikkan: {s.get('late', 0)})",
         f"• Vazifa: {f(s.get('hw'))}", f"• Testlar: {f(s.get('test'))}", f"• Umumiy o‘zlashtirish: {f(s.get('comp'))} — {p['verdict']}"]
    if p['rank']: L.append(f"• Sinf reytingi: {p['rank']}/{p['n']} (sinf o‘rtachasi {f(p['class_avg'])})")
    return '\n'.join(L)


def class_status_text(cid):
    k = class_get(cid)
    st = class_stats(cid); comps = [x['comp'] for x in st.values() if x['comp'] is not None]
    with nc.db() as c:
        s = _row(c, "SELECT * FROM cc_att_s WHERE class_id=? ORDER BY id DESC LIMIT 1", (int(cid),))
        h = _row(c, "SELECT * FROM cc_hw WHERE class_id=? ORDER BY id DESC LIMIT 1", (int(cid),))
    L = [f"📌 {k['name']} — holat", f"👥 O‘quvchilar: {len(st)} • ulangan: {sum(1 for x in st.values() if x['linked'])}"]
    if comps: L.append(f"📈 O‘rtacha o‘zlashtirish: {round(sum(comps) / len(comps), 1)}%")
    if s:
        d = att_detail(s['id']); cnt = {}
        for r in d['rows']: cnt[r['status']] = cnt.get(r['status'], 0) + 1
        L.append(f"📋 Oxirgi davomat ({s['title']}): keldi {cnt.get('p', 0)}, kechikdi {cnt.get('l', 0)}, kelmadi {cnt.get('a', 0)}")
    if h:
        done, tot = hw_counts(h['id']); L.append(f"📚 Oxirgi vazifa «{h['title']}»: {done}/{tot} topshirdi (muddat {fmt(h['due_at'])})")
    return '\n'.join(L)


def rating_text(cid, top=10):
    k = class_get(cid); r = class_rating(cid, top=top)
    L = [f"🏆 {k['name']} — o‘zlashtirish reytingi"]
    for x in r['rows']:
        if x['comp'] is None: continue
        L.append(f"{x['rank']}. {x['name']} — {x['comp']}%")
    if len(L) == 1: L.append('Hali ma’lumot yetarli emas.')
    if r['avg'] is not None: L.append(f"\nSinf o‘rtachasi: {r['avg']}%")
    L.append('Hisob: davomat 30% • vazifa 30% • testlar 40%.')
    return '\n'.join(L)


# ------------------------------------------------------------------ to'lov
def pay_set(rid, ym, paid):
    ym = str(ym or datetime.now(UZ).strftime('%Y-%m'))[:7]
    if not re.match(r'^\d{4}-\d{2}$', ym): raise ApiErr(400, 'Oy noto‘g‘ri.')
    with nc.db() as c:
        if paid: c.execute("INSERT OR IGNORE INTO cc_pay(roster_id,ym,paid_at) VALUES(?,?,?)", (int(rid), ym, _iso(_now())))
        else: c.execute("DELETE FROM cc_pay WHERE roster_id=? AND ym=?", (int(rid), ym))
        c.commit()


# ------------------------------------------------------------------ rejalashtirilgan ishlar
def tick(now=None):
    """Har ~30 soniyada: davomatni yopish, vazifa/test yakunlash, eslatmalar, haftalik va kunlik hisobotlar."""
    n = now or _now(); iso = _iso(n); loc = n.replace(tzinfo=timezone.utc).astimezone(UZ); done = {}
    def _safe(name, fn):
        try: done[name] = fn()
        except Exception: log.exception('tick %s', name)
    with nc.db() as c:
        sess = [r[0] for r in c.execute("SELECT id FROM cc_att_s WHERE closed=0 AND open_until<=?", (iso,))]
        hws = [r[0] for r in c.execute("SELECT id FROM cc_hw WHERE finalized=0 AND due_at<=?", (iso,))]
        rem = [r[0] for r in c.execute("SELECT id FROM cc_hw WHERE finalized=0 AND reminded=0 AND due_at>? AND due_at<=?", (iso, _iso(n + timedelta(hours=3))))]
        tsts = [r[0] for r in c.execute("SELECT id FROM cc_tests WHERE finalized=0 AND due_at<=?", (iso,))]
    for s in sess: _safe('att%s' % s, lambda s=s: att_finalize(s))
    for h in hws: _safe('hw%s' % h, lambda h=h: hw_finalize(h))
    for h in rem: _safe('rem%s' % h, lambda h=h: hw_remind(h))
    for t in tsts: _safe('tst%s' % t, lambda t=t: test_finalize(t))
    cfg = get_cfg()
    if loc.hour >= cfg['fee_hour']: _safe('fee', lambda: _fee_reminders(loc))
    if loc.weekday() == cfg['weekly_day'] and loc.hour >= cfg['weekly_hour']: _safe('weekly', lambda: _weekly(loc))
    if loc.hour >= 20: _safe('daily', lambda: _daily(loc))
    return done


def _fee_reminders(loc):
    ym = loc.strftime('%Y-%m'); n = 0
    with nc.db() as c: ks = _rows(c, "SELECT * FROM cc_classes WHERE active=1 AND fee_day>0")
    for k in ks:
        if loc.day not in (k['fee_day'], min(28, k['fee_day'] + 3)): continue
        if not _kv_once(f"fee:{k['id']}:{ym}:{loc.day}"): continue
        for r in roster_list(k['id']):
            if r['fee'] > 0 and not r['paid']:
                for t in parent_tg_ids(r['id']):
                    queue(t, f"💳 {r['full_name']} — «{k['name']}» uchun {ym} oyi to‘lovi ({r['fee']:,} so‘m) hali qilinmagan. Iltimos, to‘lovni amalga oshiring.".replace(',', ' '), 'fee', None, r['id'], True); n += 1
    return n


def _weekly(loc):
    key = loc.strftime('%G%V'); n = 0
    if not _kv_once('weekly:' + key): return 0
    with nc.db() as c: ks = _rows(c, "SELECT id FROM cc_classes WHERE active=1")
    for k in ks:
        for r in roster_list(k['id']):
            for t in parent_tg_ids(r['id']):
                txt = parent_weekly_text(r['id'])
                if txt: queue(t, txt, 'weekly', int(key), r['id'], True); n += 1
    return n


def _daily(loc):
    today = loc.date().isoformat(); n = 0
    with nc.db() as c: ks = _rows(c, "SELECT * FROM cc_classes WHERE active=1")
    for k in ks:
        with nc.db() as c:
            has = c.execute("SELECT 1 FROM cc_att_s WHERE class_id=? AND day=?", (k['id'], today)).fetchone() or \
                  c.execute("SELECT 1 FROM cc_hw WHERE class_id=? AND substr(due_at,1,10)=?", (k['id'], today)).fetchone()
        if not has or not _kv_once(f"daily:{today}:{k['id']}"): continue
        tell_teacher(k, '🗓 Kunlik xulosa\n' + class_status_text(k['id']), None, 'daily'); n += 1
    return n


# ------------------------------------------------------------------ API
def _need_class(cid, uid, admin, owner=False):
    k = class_get(cid)
    if not k: raise ApiErr(404, 'Sinf topilmadi.')
    if not (is_owner(k, uid, admin) if owner else can_manage(k, uid, admin)): raise ApiErr(403, 'Bu sinf sizniki emas.')
    return k


def _i(v, name='id'):
    try: return int(v)
    except Exception: raise ApiErr(400, f'{name} noto‘g‘ri.')


def _class_row(k):
    with nc.db() as c:
        n = c.execute("SELECT COUNT(*) FROM cc_roster WHERE class_id=? AND active=1", (k['id'],)).fetchone()[0]
        l = c.execute("SELECT COUNT(*) FROM cc_roster WHERE class_id=? AND active=1 AND student_uid IS NOT NULL", (k['id'],)).fetchone()[0]
    return {'id': k['id'], 'name': k['name'], 'subject': k['subject'], 'students': n, 'linked': l, 'group': bool(k['chat_id']), 'group_title': k['chat_title'], 'owner_id': k['teacher_id']}


def _g_me(q, uid, admin):
    kids = parent_children(uid)
    _c = get_cfg()
    return {'ok': True, 'teacher': bool(is_teacher_user(uid) or admin or teacher_classes(uid, admin)), 'parent': bool(kids), 'children': kids, 'admin': bool(admin),
            'send_window': ('%02d:00–%02d:00' % (_c['from'], _c['to'])) if _c['enabled'] else ''}


def _g_list(q, uid, admin):
    return {'ok': True, 'classes': [_class_row(k) for k in teacher_classes(uid, admin)], 'can_create': bool(is_teacher_user(uid) or admin)}


def _g_detail(q, uid, admin):
    k = _need_class(_i(q.get('id')), uid, admin)
    with nc.db() as c:
        sess = _rows(c, "SELECT * FROM cc_att_s WHERE class_id=? ORDER BY id DESC LIMIT 15", (k['id'],))
        hws = _rows(c, "SELECT id,title,due_at,finalized FROM cc_hw WHERE class_id=? ORDER BY id DESC LIMIT 15", (k['id'],))
        tests = _rows(c, "SELECT * FROM cc_tests WHERE class_id=? ORDER BY id DESC LIMIT 15", (k['id'],))
        asst = [r[0] for r in c.execute("SELECT user_id FROM cc_assist WHERE class_id=?", (k['id'],))]
    for s in sess:
        s['when'] = fmt(s['created_at']); s['open'] = (not s['closed']) and s['open_until'] > _iso(_now())
    for h in hws:
        h['due_text'] = fmt(h['due_at']); h['done'], h['total'] = hw_counts(h['id'])
    for t in tests: t['due_text'] = fmt(t['due_at'])
    st = class_stats(k['id'])
    ros = roster_list(k['id'])
    for r in ros:
        r['stats'] = st.get(r['id'], {}); r.pop('student_uid', None)
    rating = class_rating(k['id'], names='full')
    return {'ok': True, 'cls': {**_class_row(k), 'notify_mode': k['notify_mode'], 'rating_names': k['rating_names'], 'fee_day': k['fee_day'], 'is_owner': is_owner(k, uid, admin)},
            'roster': ros, 'sessions': sess, 'hw': hws, 'tests': tests, 'assistants': asst, 'rating': rating}


def _g_att(q, uid, admin):
    s = att_get(_i(q.get('sid'), 'sid'))
    if not s: raise ApiErr(404, 'Davomat topilmadi.')
    _need_class(s['class_id'], uid, admin)
    return {'ok': True, **att_detail(s['id'])}


def _g_hw(q, uid, admin):
    d = hw_detail(_i(q.get('hw'), 'hw'))
    if not d: raise ApiErr(404, 'Vazifa topilmadi.')
    _need_class(d['hw']['class_id'], uid, admin)
    return {'ok': True, **d}


def _g_test(q, uid, admin):
    d = test_detail(_i(q.get('tid'), 'tid'))
    if not d: raise ApiErr(404, 'Test topilmadi.')
    _need_class(d['test']['class_id'], uid, admin)
    return {'ok': True, **d}


def _g_parent_me(q, uid, admin):
    kids = parent_children(uid)
    if not kids: raise ApiErr(403, 'Ota-ona sifatida kirilmagan.')
    out = []
    for kd in kids:
        p = child_profile(kd['rid'], full=False)
        if p: out.append({'rid': p['rid'], 'name': p['name'], 'class_name': p['class_name'], 'comp': p['stats'].get('comp'), 'verdict': p['verdict'], 'rank': p['rank'], 'n': p['n']})
    return {'ok': True, 'children': out}


def _g_parent_child(q, uid, admin):
    rid = _i(q.get('rid'), 'rid')
    if rid not in [c['rid'] for c in parent_children(uid)]: raise ApiErr(403, 'Bu farzand sizga ulanmagan.')
    return {'ok': True, **child_profile(rid)}


def _need_rid(rid, uid, admin):
    r = roster_get(_i(rid, 'rid'))
    if not r: raise ApiErr(404, 'O‘quvchi topilmadi.')
    return r, _need_class(r['class_id'], uid, admin)


def _p_create(b, uid, admin):
    if not (is_teacher_user(uid) or admin): raise ApiErr(403, 'Sinf ochish faqat ustoz va admin uchun.')
    return {'ok': True, 'id': class_create(uid, b.get('name'), b.get('subject'))}


def _p_update(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin)
    class_update(k['id'], **{x: b[x] for x in ('name', 'subject', 'notify_mode', 'rating_names', 'fee_day') if x in b}); return {'ok': True}


def _p_delete(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin, owner=True); class_delete(k['id']); return {'ok': True}


def _p_assist(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin, owner=True); u = _i(b.get('user_id'), 'user_id')
    (assist_del if b.get('remove') else assist_add)(k['id'], u); return {'ok': True}


def _p_group_unlink(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin)
    if k['chat_id']: class_unlink_chat(k['chat_id'])
    return {'ok': True}


def _p_roster_add(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin); res = roster_add_many(k['id'], str(b.get('text', ''))[:60000])
    if not res['total']: raise ApiErr(400, 'Ism topilmadi. Har qatorga bittadan: Ism Familiya; telefon; ota-ona telefoni')
    return {'ok': True, **res}


def _p_roster_del(b, uid, admin):
    r, k = _need_rid(b.get('rid'), uid, admin); roster_del(r['id']); return {'ok': True}


def _p_roster_edit(b, uid, admin):
    r, k = _need_rid(b.get('rid'), uid, admin)
    roster_edit(r['id'], **{x: b[x] for x in ('full_name', 'phone', 'parent_phone', 'fee') if x in b}); return {'ok': True}


def _p_roster_unlink(b, uid, admin):
    r, k = _need_rid(b.get('rid'), uid, admin); unlink_student(r['id']); return {'ok': True}


def _p_creds(b, uid, admin):
    r, k = _need_rid(b.get('rid'), uid, admin); lg, pw = acc_create_or_reset(r['id'])
    return {'ok': True, 'name': r['full_name'], 'login': lg, 'password': pw}


def _p_creds_all(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin)
    return {'ok': True, 'items': [{'name': n, 'login': lg, 'password': pw} for n, lg, pw in creds_for_class(k['id'])]}


def _p_att_start(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin)
    s = att_start(k['id'], b.get('minutes', 20), b.get('title', ''), 'button' if b.get('mode') == 'button' else 'code')
    if k['chat_id']:
        queue(k['chat_id'], f"🕘 DAVOMAT boshlandi — {s['title']}\n" + (f"Belgilanish: darsda e’lon qilingan kod bilan /keldim KOD" if s['mode'] == 'code' else 'Belgilanish uchun /keldim yozing') + f"\n{b.get('minutes', 20)} daqiqa ochiq.", 'attgrp', s['id'])
    return {'ok': True, 'sid': s['id'], 'code': s['code']}


def _p_att_mark(b, uid, admin):
    s = att_get(_i(b.get('sid'), 'sid'))
    if not s: raise ApiErr(404, 'Davomat topilmadi.')
    _need_class(s['class_id'], uid, admin); r = roster_get(_i(b.get('rid'), 'rid'))
    if not r or r['class_id'] != s['class_id']: raise ApiErr(404, 'O‘quvchi topilmadi.')
    att_mark(s['id'], r['id'], str(b.get('status', '')), 'teacher'); return {'ok': True}


def _p_att_close(b, uid, admin):
    s = att_get(_i(b.get('sid'), 'sid'))
    if not s: raise ApiErr(404, 'Davomat topilmadi.')
    _need_class(s['class_id'], uid, admin); return {'ok': True, 'result': att_finalize(s['id'])}


def _p_att_notify(b, uid, admin):
    s = att_get(_i(b.get('sid'), 'sid'))
    if not s: raise ApiErr(404, 'Davomat topilmadi.')
    _need_class(s['class_id'], uid, admin); return {'ok': True, **att_notify(s['id'])}


def _p_hw_create(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin)
    try: hrs = max(1, min(24 * 90, int(b.get('hours', 24))))
    except Exception: hrs = 24
    hid = hw_create(k['id'], uid, b.get('title'), b.get('text', ''), _iso(_now() + timedelta(hours=hrs)))
    h = hw_get(hid)
    if k['chat_id']:
        queue(k['chat_id'], f"📚 YANGI VAZIFA — {h['title']}\n{h['text']}\n⏰ Muddat: {fmt(h['due_at'])}\n\nTopshirish: /vazifalar yoki ustoz yuborgan xabarga javob bering.", 'hwgrp', hid)
    return {'ok': True, 'id': hid}


def _hw_check(b, uid, admin):
    h = hw_get(_i(b.get('hw'), 'hw'))
    if not h: raise ApiErr(404, 'Vazifa topilmadi.')
    _need_class(h['class_id'], uid, admin); return h


def _p_hw_mark(b, uid, admin):
    h = _hw_check(b, uid, admin); r = roster_get(_i(b.get('rid'), 'rid'))
    if not r or r['class_id'] != h['class_id']: raise ApiErr(404, 'O‘quvchi topilmadi.')
    hw_mark(h['id'], r['id'], bool(b.get('on'))); return {'ok': True}


def _p_hw_grade(b, uid, admin):
    h = _hw_check(b, uid, admin); r = roster_get(_i(b.get('rid'), 'rid'))
    if not r or r['class_id'] != h['class_id']: raise ApiErr(404, 'O‘quvchi topilmadi.')
    hw_grade(h['id'], r['id'], b.get('grade')); return {'ok': True}


def _p_hw_delete(b, uid, admin):
    h = _hw_check(b, uid, admin); hw_delete(h['id']); return {'ok': True}


def _p_hw_notify(b, uid, admin):
    h = _hw_check(b, uid, admin); return {'ok': True, **hw_notify(h['id'])}


def _p_test_assign(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin)
    kind = b.get('kind') if b.get('kind') in ('ms', 'simple') else None
    if not kind: raise ApiErr(400, 'Test turini tanlang.')
    return {'ok': True, 'id': test_assign(k['id'], kind, b.get('code'), b.get('hours', 48))}


def _test_check(b, uid, admin):
    t = test_get(_i(b.get('tid'), 'tid'))
    if not t: raise ApiErr(404, 'Test topilmadi.')
    _need_class(t['class_id'], uid, admin); return t


def _p_test_check(b, uid, admin):
    t = _test_check(b, uid, admin); return {'ok': True, 'result': test_finalize(t['id'])}


def _p_test_notify(b, uid, admin):
    t = _test_check(b, uid, admin); return {'ok': True, **test_notify(t['id'])}


def _p_test_delete(b, uid, admin):
    t = _test_check(b, uid, admin); test_delete(t['id']); return {'ok': True}


def _p_pay(b, uid, admin):
    r, k = _need_rid(b.get('rid'), uid, admin); pay_set(r['id'], b.get('ym'), bool(b.get('paid'))); return {'ok': True}


def _p_msg(b, uid, admin):
    k = _need_class(_i(b.get('id')), uid, admin); return {'ok': True, **msg_parents(k['id'], b.get('text'), b.get('rid'))}


def _p_parent_login(b, uid, admin):
    ok, msg, rid = parent_login(uid, b.get('login'), b.get('password'))
    if not ok: raise ApiErr(401, msg)
    return {'ok': True, 'name': msg, 'rid': rid}


def _p_parent_logout(b, uid, admin):
    parent_logout(uid); return {'ok': True}


def _p_parent_excuse(b, uid, admin):
    att_excuse(uid, _i(b.get('sid'), 'sid'), _i(b.get('rid'), 'rid'), b.get('note')); return {'ok': True}


def _need_admin(uid, admin):
    if not (admin or (uid is not None and int(uid) == ADMIN_ID)): raise ApiErr(403, 'Faqat admin.')


def _cfg_payload():
    loc = _now().replace(tzinfo=timezone.utc).astimezone(UZ); cfg = get_cfg()
    return {'ok': True, 'cfg': cfg, 'defaults': CFG_DEFAULT, 'now': loc.strftime('%H:%M'), 'open': bool(cfg['from'] <= loc.hour < cfg['to']), 'stats': outbox_stats()}


def _g_admin_cfg(q, uid, admin):
    _need_admin(uid, admin); return _cfg_payload()


def _p_admin_cfg(b, uid, admin):
    _need_admin(uid, admin)
    try: set_cfg(b)
    except ValueError as e: raise ApiErr(400, str(e))
    return _cfg_payload()


GET = {'/api/class/admin/cfg': _g_admin_cfg, '/api/class/me': _g_me, '/api/class/list': _g_list, '/api/class/detail': _g_detail, '/api/class/att': _g_att, '/api/class/hw': _g_hw,
       '/api/class/test': _g_test, '/api/parent/me': _g_parent_me, '/api/parent/child': _g_parent_child}
POST = {'/api/class/admin/cfg': _p_admin_cfg, '/api/class/create': _p_create, '/api/class/update': _p_update, '/api/class/delete': _p_delete, '/api/class/assist': _p_assist,
        '/api/class/group_unlink': _p_group_unlink, '/api/class/roster/add': _p_roster_add, '/api/class/roster/del': _p_roster_del,
        '/api/class/roster/edit': _p_roster_edit, '/api/class/roster/unlink': _p_roster_unlink, '/api/class/creds': _p_creds, '/api/class/creds_all': _p_creds_all,
        '/api/class/att/start': _p_att_start, '/api/class/att/mark': _p_att_mark, '/api/class/att/close': _p_att_close, '/api/class/att/notify': _p_att_notify,
        '/api/class/hw/create': _p_hw_create, '/api/class/hw/mark': _p_hw_mark, '/api/class/hw/grade': _p_hw_grade, '/api/class/hw/delete': _p_hw_delete,
        '/api/class/hw/notify': _p_hw_notify, '/api/class/test/assign': _p_test_assign, '/api/class/test/check': _p_test_check,
        '/api/class/test/notify': _p_test_notify, '/api/class/test/delete': _p_test_delete, '/api/class/pay': _p_pay, '/api/class/msg': _p_msg,
        '/api/parent/login': _p_parent_login, '/api/parent/logout': _p_parent_logout, '/api/parent/excuse': _p_parent_excuse}


def handles(path): return path in GET or path in POST


def api_get(path, query, uid, admin=False):
    """query: {kalit: qiymat} (bitta qiymatli). -> (status, dict)"""
    fn = GET.get(path)
    if not fn: return 404, {'ok': False, 'error': 'Topilmadi.'}
    try: return 200, fn(query or {}, uid, admin)
    except ApiErr as e: return e.code, {'ok': False, 'error': e.msg}
    except Exception:
        log.exception('api_get %s', path); return 500, {'ok': False, 'error': 'Server xatosi.'}


def api_post(path, body, uid, admin=False):
    fn = POST.get(path)
    if not fn: return 404, {'ok': False, 'error': 'Topilmadi.'}
    try: return 200, fn(body if isinstance(body, dict) else {}, uid, admin)
    except ApiErr as e: return e.code, {'ok': False, 'error': e.msg}
    except Exception:
        log.exception('api_post %s', path); return 500, {'ok': False, 'error': 'Server xatosi.'}
