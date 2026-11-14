"""v126: «Natijalarimiz» — sertifikatlar (rasm + ism + daraja) va «Maxsus fikrlar». Hammasini admin Mini App ichida kiritadi.
Ko'rinish: har yozuvda `visible` (0/1) — faqat admin «Hammaga ko'rsatish» bossa foydalanuvchiga chiqadi."""
import io, os
from national_certificate import db, now
import books_store as bk

LEVELS = ('A+', 'A', 'B+', 'B', 'C+')
KINDS = {'kurs': 'Kurs', 'bot': 'Bot', 'esse': 'Esse tekshiruvi', 'ustoz': 'Ustoz haqida',
         'natija': 'Natija hikoyasi', 'maslahat': 'Maslahat', 'boshqa': 'Boshqa'}
THUMB_W = 560


def init():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS res_cert(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, level TEXT NOT NULL, score TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT '', full BLOB NOT NULL, thumb BLOB NOT NULL, visible INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS res_op(
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, who TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'boshqa',
            text TEXT NOT NULL, gain TEXT NOT NULL DEFAULT '', visible INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)''')


def _thumb(raw):
    from PIL import Image
    im = bk._open(raw); w, h = im.size
    out = io.BytesIO(); im.resize((THUMB_W, max(1, round(h * THUMB_W / w))), Image.LANCZOS).save(out, 'JPEG', quality=84, optimize=True)
    return out.getvalue()


def _clean(s, n): return ' '.join(str(s or '').split())[:n]


def norm_level(v):
    v = str(v or '').strip().upper().replace(' ', '')
    return v if v in LEVELS else ''


def list_certs(admin=False):
    with db() as c:
        rows = c.execute('SELECT id,name,level,score,note,visible,created_at FROM res_cert' + ('' if admin else ' WHERE visible=1') + ' ORDER BY id DESC').fetchall()
    out = []
    for r in rows:
        d = {'id': r['id'], 'name': r['name'], 'level': r['level'], 'score': r['score'], 'note': r['note']}
        if admin: d['visible'] = bool(r['visible'])
        out.append(d)
    return out


def list_ops(admin=False):
    with db() as c:
        rows = c.execute('SELECT id,name,who,kind,text,gain,visible FROM res_op' + ('' if admin else ' WHERE visible=1') + ' ORDER BY id DESC').fetchall()
    out = []
    for r in rows:
        d = {'id': r['id'], 'name': r['name'], 'who': r['who'], 'kind': r['kind'], 'kind_label': KINDS.get(r['kind'], 'Boshqa'), 'text': r['text'], 'gain': r['gain']}
        if admin: d['visible'] = bool(r['visible'])
        out.append(d)
    return out


def get_img(cid, thumb=False, admin=False):
    with db() as c:
        r = c.execute('SELECT %s AS b, visible FROM res_cert WHERE id=?' % ('thumb' if thumb else 'full'), (int(cid),)).fetchone()
    if not r or not (admin or r['visible']): return None
    return bytes(r['b'])


def add_cert(name, level, score, note, raw, visible=False):
    name = _clean(name, 80); lv = norm_level(level)
    if not name: return None, 'Ism familiyani kiriting.'
    if not lv: return None, 'Daraja: ' + ', '.join(LEVELS)
    if not raw: return None, 'Sertifikat rasmini tanlang.'
    try: full, _t = bk._make(raw); th = _thumb(raw)
    except Exception: return None, 'Rasm o‘qilmadi (JPG yoki PNG yuboring).'
    with db() as c:
        cur = c.execute('INSERT INTO res_cert(name,level,score,note,full,thumb,visible,created_at) VALUES(?,?,?,?,?,?,?,?)',
                        (name, lv, _clean(score, 20), _clean(note, 120), full, th, 1 if visible else 0, now()))
        return cur.lastrowid, ''


def edit_cert(cid, name=None, level=None, score=None, note=None, raw=None):
    sets, vals = [], []
    if name is not None:
        n = _clean(name, 80)
        if not n: return 'Ism familiyani kiriting.'
        sets.append('name=?'); vals.append(n)
    if level is not None:
        lv = norm_level(level)
        if not lv: return 'Daraja: ' + ', '.join(LEVELS)
        sets.append('level=?'); vals.append(lv)
    if score is not None: sets.append('score=?'); vals.append(_clean(score, 20))
    if note is not None: sets.append('note=?'); vals.append(_clean(note, 120))
    if raw:
        try: full, _t = bk._make(raw); th = _thumb(raw)
        except Exception: return 'Rasm o‘qilmadi.'
        sets += ['full=?', 'thumb=?']; vals += [full, th]
    if not sets: return ''
    with db() as c: c.execute('UPDATE res_cert SET ' + ','.join(sets) + ' WHERE id=?', vals + [int(cid)])
    return ''


def set_cert_visible(cid, v):
    with db() as c: c.execute('UPDATE res_cert SET visible=? WHERE id=?', (1 if v else 0, int(cid)))


def del_cert(cid):
    with db() as c: c.execute('DELETE FROM res_cert WHERE id=?', (int(cid),))


def add_op(name, who, kind, text, gain, visible=False):
    name = _clean(name, 60); text = ' '.join(str(text or '').split())[:600]
    if not name: return None, 'Kim nomidan ekanini yozing.'
    if len(text) < 5: return None, 'Fikr matnini kiriting.'
    kind = kind if kind in KINDS else 'boshqa'
    with db() as c:
        cur = c.execute('INSERT INTO res_op(name,who,kind,text,gain,visible,created_at) VALUES(?,?,?,?,?,?,?)',
                        (name, _clean(who, 60), kind, text, _clean(gain, 40), 1 if visible else 0, now()))
        return cur.lastrowid, ''


def edit_op(oid, name=None, who=None, kind=None, text=None, gain=None):
    sets, vals = [], []
    if name is not None:
        n = _clean(name, 60)
        if not n: return 'Kim nomidan ekanini yozing.'
        sets.append('name=?'); vals.append(n)
    if who is not None: sets.append('who=?'); vals.append(_clean(who, 60))
    if kind is not None: sets.append('kind=?'); vals.append(kind if kind in KINDS else 'boshqa')
    if text is not None:
        t = ' '.join(str(text).split())[:600]
        if len(t) < 5: return 'Fikr matnini kiriting.'
        sets.append('text=?'); vals.append(t)
    if gain is not None: sets.append('gain=?'); vals.append(_clean(gain, 40))
    if not sets: return ''
    with db() as c: c.execute('UPDATE res_op SET ' + ','.join(sets) + ' WHERE id=?', vals + [int(oid)])
    return ''


def set_op_visible(oid, v):
    with db() as c: c.execute('UPDATE res_op SET visible=? WHERE id=?', (1 if v else 0, int(oid)))


def del_op(oid):
    with db() as c: c.execute('DELETE FROM res_op WHERE id=?', (int(oid),))
