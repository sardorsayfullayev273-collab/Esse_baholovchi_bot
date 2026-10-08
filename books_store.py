"""Badiiy asarlar rasmlari — bazada (SQLite) saqlanadi: bot orqali qo'shiladi, zaxira nusxaga ham kiradi."""
import io, os, json
from national_certificate import db, now

FULL_MAX = 1280   # to'liq rasm: eng katta tomoni
THUMB_W = 360


def init_books_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS books(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, full BLOB NOT NULL, thumb BLOB NOT NULL, created_at TEXT NOT NULL)''')
        cols = {r[1] for r in c.execute('PRAGMA table_info(books)').fetchall()}
        if 'author' not in cols: c.execute("ALTER TABLE books ADD COLUMN author TEXT NOT NULL DEFAULT ''")
        if 'info' not in cols: c.execute("ALTER TABLE books ADD COLUMN info TEXT NOT NULL DEFAULT ''")
        c.execute('''CREATE TABLE IF NOT EXISTS book_images(
            id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL, full BLOB NOT NULL, thumb BLOB NOT NULL, created_at TEXT NOT NULL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS book_questions(
            id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL, text TEXT NOT NULL, options TEXT NOT NULL,
            answer TEXT NOT NULL, explanation TEXT NOT NULL DEFAULT '')''')
        qcols = {r[1] for r in c.execute('PRAGMA table_info(book_questions)').fetchall()}
        if 'kind' not in qcols: c.execute("ALTER TABLE book_questions ADD COLUMN kind TEXT NOT NULL DEFAULT 'closed'")
        c.execute('CREATE INDEX IF NOT EXISTS ix_book_q ON book_questions(book_id)')
        c.execute('''CREATE TABLE IF NOT EXISTS book_sections(
            book_id INTEGER NOT NULL, key TEXT NOT NULL, text TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(book_id, key))''')
        c.execute('''CREATE TABLE IF NOT EXISTS book_attempts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, book_id INTEGER NOT NULL, correct INTEGER NOT NULL,
            total INTEGER NOT NULL, created_at TEXT NOT NULL)''')
        acols = {r[1] for r in c.execute('PRAGMA table_info(book_attempts)').fetchall()}
        if 'kind' not in acols: c.execute("ALTER TABLE book_attempts ADD COLUMN kind TEXT NOT NULL DEFAULT 'closed'")
        c.commit()


def _make(raw):
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    w, h = im.size; s = min(1.0, FULL_MAX / max(w, h))
    full = io.BytesIO(); im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS).save(full, 'JPEG', quality=85, optimize=True, progressive=True)
    th = io.BytesIO(); im.resize((THUMB_W, max(1, round(h * THUMB_W / w))), Image.LANCZOS).save(th, 'JPEG', quality=70, optimize=True)
    return full.getvalue(), th.getvalue()


def add(title, raw):
    full, thumb = _make(raw)
    with db() as c:
        cur = c.execute('INSERT INTO books(title,full,thumb,created_at) VALUES(?,?,?,?)', (title.strip()[:120], full, thumb, now()))
        c.commit(); return cur.lastrowid


def list_books():
    with db() as c:
        rows = c.execute('''SELECT b.id, b.title, b.author,
            ((b.info<>'') OR EXISTS(SELECT 1 FROM book_sections s WHERE s.book_id=b.id AND s.text<>'')) has_info,
            (SELECT COUNT(*) FROM book_images i WHERE i.book_id=b.id) pics,
            (SELECT COUNT(*) FROM book_questions q WHERE q.book_id=b.id) qn,
            (SELECT COUNT(*) FROM book_questions q WHERE q.book_id=b.id AND q.kind='open') qo
            FROM books b ORDER BY b.id''').fetchall()
    return [{'n': r['id'], 'title': r['title'], 'author': r['author'], 'has_info': bool(r['has_info']), 'pics': r['pics'],
             'qn': r['qn'], 'qo': r['qo'], 'qc': r['qn'] - r['qo']} for r in rows]


def get_image(n, thumb=False):
    with db() as c:
        r = c.execute('SELECT full,thumb FROM books WHERE id=?', (int(n),)).fetchone()
    return (r['thumb'] if thumb else r['full']) if r else None


def delete(n):
    with db() as c:
        cur = c.execute('DELETE FROM books WHERE id=?', (int(n),))
        for t in ('book_images', 'book_questions', 'book_attempts', 'book_sections'):
            c.execute(f'DELETE FROM {t} WHERE book_id=?', (int(n),))
        c.commit(); return cur.rowcount > 0


def rename(n, title):
    with db() as c:
        cur = c.execute('UPDATE books SET title=? WHERE id=?', (title.strip()[:120], int(n))); c.commit(); return cur.rowcount > 0


def find_dir(base):
    """books papkasini topadi: books, Books, Books/books ... (katta-kichik harf va ichma-ich papkalar farqi qilmaydi)."""
    best = None
    for root, dirs, files in os.walk(base):
        if root[len(base):].count(os.sep) > 3:
            dirs[:] = []; continue
        dirs[:] = [d for d in dirs if d not in ('miniapp', 'fonts', '.git', '__pycache__', 'node_modules')]
        imgs = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not f.lower().endswith('_t.jpg')]
        if 'books.json' in [f.lower() for f in files] or len(imgs) >= 3:
            if best is None or len(imgs) > best[0]:
                best = (len(imgs), root)
    return best[1] if best else os.path.join(base, 'books')


def _items(folder):
    """[(sarlavha, fayl_yo'li)] — books.json bo'lsa undan, bo'lmasa fayl nomlaridan."""
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not f.lower().endswith('_t.jpg'))
    man = None
    for f in os.listdir(folder):
        if f.lower() == 'books.json':
            try: man = json.load(open(os.path.join(folder, f), encoding='utf-8'))
            except Exception: man = None
    out = []
    if man:
        for it in man:
            for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                fp = os.path.join(folder, '%02d%s' % (it['n'], ext))
                if os.path.isfile(fp):
                    out.append((it['title'], fp)); break
        return out
    for f in files:
        stem = os.path.splitext(f)[0]
        out.append((('Asar ' + stem) if stem.isdigit() else stem.replace('_', ' ').strip(), os.path.join(folder, f)))
    return out


def seed_from_dir(folder, force=False):
    """Papkadagi asarlarni bazaga ko'chiradi. force=False: faqat baza bo'sh bo'lsa. force=True: nomi bor asarlarni o'tkazib yuboradi."""
    try:
        have = {x['title'] for x in list_books()}
        if have and not force:
            return 0
        items = _items(folder)
    except Exception:
        return 0
    n = 0
    for title, fp in items:
        try:
            if title in have:
                continue
            add(title, open(fp, 'rb').read()); n += 1
        except Exception:
            pass
    return n


def folder_report(folder):
    """Diagnostika: papka topildimi, nechta rasm bor."""
    if not os.path.isdir(folder):
        return f"❌ Rasmlar papkasi topilmadi.\nQidirilgan joy: {folder}"
    try: items = _items(folder)
    except Exception: items = []
    return f"📁 Papka topildi: {folder}\n🖼 Rasmlar: {len(items)} ta" + (f" ({', '.join(t for t, _ in items[:3])}…)" if items else "")


# ------------------------------------------------------------------ qo'shimcha rasmlar
def exists(n):
    with db() as c:
        return c.execute('SELECT 1 FROM books WHERE id=?', (int(n),)).fetchone() is not None


def add_pic(n, raw):
    """Mavjud asarga qo'shimcha rasm. Rasm id sini qaytaradi."""
    full, thumb = _make(raw)
    with db() as c:
        cur = c.execute('INSERT INTO book_images(book_id,full,thumb,created_at) VALUES(?,?,?,?)', (int(n), full, thumb, now()))
        c.commit(); return cur.lastrowid


def pic_ids(n):
    with db() as c:
        return [r['id'] for r in c.execute('SELECT id FROM book_images WHERE book_id=? ORDER BY id', (int(n),)).fetchall()]


def get_pic(pid, thumb=False):
    with db() as c:
        r = c.execute('SELECT full,thumb FROM book_images WHERE id=?', (int(pid),)).fetchone()
    return (r['thumb'] if thumb else r['full']) if r else None


def delete_pics(n):
    with db() as c:
        cur = c.execute('DELETE FROM book_images WHERE book_id=?', (int(n),)); c.commit(); return cur.rowcount


# ------------------------------------------------------------------ ma'lumot
def set_info(n, text, author=None, append=False):
    with db() as c:
        r = c.execute('SELECT info FROM books WHERE id=?', (int(n),)).fetchone()
        if not r: return False
        new = ((r['info'] + '\n\n' + text) if (append and r['info']) else text).strip()[:20000]
        c.execute('UPDATE books SET info=? WHERE id=?', (new, int(n)))
        if author is not None: c.execute('UPDATE books SET author=? WHERE id=?', (author.strip()[:120], int(n)))
        c.commit(); return True


def get_detail(n):
    with db() as c:
        r = c.execute('SELECT id,title,author,info FROM books WHERE id=?', (int(n),)).fetchone()
    if not r: return None
    return {'n': r['id'], 'title': r['title'], 'author': r['author'], 'info': r['info'], 'pics': pic_ids(n), 'qn': question_count(n),
            'counts': question_counts(n)}


# ------------------------------------------------------------------ ma'lumotlar (3 bo'lim)
SECTIONS = (('heroes', 'Asar qahramonlari'), ('important', 'Muhim ma‘lumotlar'), ('plot', 'Voqealar rivoji'))
SECTION_KEYS = tuple(k for k, _ in SECTIONS)
SECTION_MAX = 8000


def get_sections(n):
    """{'heroes':..., 'important':..., 'plot':...}. Eski (botdagi /asar_malumot) matni bo'lsa va bo'limlar bo'sh bo'lsa,
    u «Muhim ma'lumotlar» sifatida ko'rsatiladi."""
    with db() as c:
        rows = {r['key']: r['text'] for r in c.execute('SELECT key,text FROM book_sections WHERE book_id=?', (int(n),)).fetchall()}
        legacy = c.execute('SELECT info FROM books WHERE id=?', (int(n),)).fetchone()
    out = {k: rows.get(k, '') for k in SECTION_KEYS}
    if not any(out.values()) and legacy and legacy['info']: out['important'] = legacy['info']
    return out


def set_sections(n, sections, author=None):
    """Berilgan kalitlarni saqlaydi (bo'sh matn — o'chiradi). Muallifni ham yangilashi mumkin."""
    if not exists(n): return False
    with db() as c:
        for k in SECTION_KEYS:
            if k not in (sections or {}): continue
            t = str(sections[k] or '').strip()[:SECTION_MAX]
            if t: c.execute('INSERT INTO book_sections(book_id,key,text,updated_at) VALUES(?,?,?,?) ON CONFLICT(book_id,key) DO UPDATE SET text=excluded.text, updated_at=excluded.updated_at',
                            (int(n), k, t, now()))
            else: c.execute('DELETE FROM book_sections WHERE book_id=? AND key=?', (int(n), k))
        if author is not None: c.execute('UPDATE books SET author=? WHERE id=?', (str(author).strip()[:120], int(n)))
        c.commit()
    return True


# ------------------------------------------------------------------ test (yopiq: variantli; ochiq: javobni o'zi yozadi)
LETTERS = 'ABCDEF'
KINDS = ('closed', 'open')
MAX_Q_PER_KIND = 300


def _norm_ans(s):
    """Ochiq javobni solishtirish: kichik harf, barcha apostroflar bir xil, tinish belgilari va ortiqcha bo'shliqlar yo'q."""
    import re
    s = str(s or '').lower()
    for ch in '‘’ʻʼ`´': s = s.replace(ch, "'")
    s = re.sub(r"[^\w\s']", ' ', s.replace('_', ' '), flags=re.U)
    return re.sub(r'\s+', ' ', s).strip()


def parse_bulk(text, kind='closed'):
    """Yopiq: '1. Savol / A) ... / Javob: B / Izoh: ...'.  Ochiq: '1. Savol / Javob: javob1 | javob2 / Izoh: ...'.
    Qaytaradi: (savollar, xatolar)."""
    import re
    qs, errs, cur = [], [], None
    def flush():
        nonlocal cur
        if cur: qs.append(cur); cur = None
    for raw in text.replace('\r', '').split('\n'):
        line = raw.strip()
        if not line: continue
        if kind == 'open':
            m = re.match(r'^(?:Javob|Жавоб|Answer)\s*[:\-]\s*(.+)$', line, re.I)
            if m and cur: cur['options'] = [x.strip() for x in m.group(1).split('|') if x.strip()]; cur['answer'] = (cur['options'] or [''])[0]; continue
        else:
            m = re.match(r'^(?:Javob|Жавоб|Answer)\s*[:\-]\s*([A-Fa-f])\b', line, re.I)
            if m and cur: cur['answer'] = m.group(1).upper(); continue
        m = re.match(r'^Izoh\s*[:\-]\s*(.+)$', line, re.I)
        if m and cur: cur['explanation'] = m.group(1).strip(); continue
        if kind != 'open':
            m = re.match(r'^([A-Fa-f])\s*[\)\.]\s*(.+)$', line)
            if m and cur: cur['options'].append(m.group(2).strip()); continue
        m = re.match(r'^\d+\s*[\.\)]\s*(.+)$', line)
        if m: flush(); cur = {'kind': kind, 'text': m.group(1).strip(), 'options': [], 'answer': '', 'explanation': ''}; continue
        if cur and not cur['options'] and not cur['answer']: cur['text'] += ' ' + line
    flush()
    for i, q in enumerate(qs, 1):
        if kind == 'open':
            if not q['options']: errs.append(f'{i}-savolda «Javob: ...» yo‘q')
        elif len(q['options']) < 2: errs.append(f'{i}-savolda variantlar yetarli emas (kamida 2 ta)')
        elif len(q['options']) > 6: errs.append(f'{i}-savolda 6 tadan ortiq variant bor')
        elif not q['answer']: errs.append(f'{i}-savolda «Javob: X» yo‘q')
        elif LETTERS.index(q['answer']) >= len(q['options']): errs.append(f'{i}-savol javobi variantlardan tashqarida')
    return qs, errs


def validate_question(kind, text, options, answer):
    """Xato matnini qaytaradi, to'g'ri bo'lsa ''."""
    if kind not in KINDS: return 'Test turi noto‘g‘ri.'
    if not str(text or '').strip(): return 'Savol matnini kiriting.'
    opts = [str(o).strip() for o in (options or []) if str(o).strip()]
    if kind == 'open':
        if not opts: return 'Kamida bitta to‘g‘ri javob kiriting.'
        if len(opts) > 10: return 'To‘g‘ri javob variantlari 10 tadan oshmasin.'
        if any(len(o) > 200 for o in opts): return 'Javob juda uzun (200 belgigacha).'
        return ''
    if len(opts) < 2: return 'Kamida 2 ta variant kiriting.'
    if len(opts) > 6: return 'Variantlar 6 tadan oshmasin.'
    a = str(answer or '').strip().upper()
    if len(a) != 1 or a not in LETTERS or LETTERS.index(a) >= len(opts): return 'To‘g‘ri javobni belgilang.'
    return ''


def add_questions(n, qs, replace=False, kind=None):
    """qs: [{'kind','text','options','answer','explanation'}]. kind berilmasa har bir savolning o'z turi (standart: yopiq)."""
    with db() as c:
        if replace: c.execute('DELETE FROM book_questions WHERE book_id=?' + (' AND kind=?' if kind else ''), (int(n),) + ((kind,) if kind else ()))
        for q in qs:
            k = kind or q.get('kind') or 'closed'
            opts = [str(o).strip() for o in q['options'] if str(o).strip()]
            ans = opts[0] if k == 'open' else str(q['answer']).upper()
            c.execute('INSERT INTO book_questions(book_id,text,options,answer,explanation,kind) VALUES(?,?,?,?,?,?)',
                      (int(n), q['text'].strip()[:1500], json.dumps(opts, ensure_ascii=False), ans[:200], (q.get('explanation') or '').strip()[:1000], k))
        c.commit()
    return question_count(n)


def add_question(n, kind, text, options, answer='', explanation=''):
    """Bitta savol. (True, jami_soni) yoki (False, xato)."""
    err = validate_question(kind, text, options, answer)
    if err: return False, err
    if question_counts(n).get(kind, 0) >= MAX_Q_PER_KIND: return False, f'Bitta testda {MAX_Q_PER_KIND} tadan ko‘p savol bo‘lmasin.'
    add_questions(n, [{'kind': kind, 'text': text, 'options': options, 'answer': answer, 'explanation': explanation}])
    return True, question_counts(n).get(kind, 0)


def delete_question(n, qid):
    with db() as c:
        cur = c.execute('DELETE FROM book_questions WHERE id=? AND book_id=?', (int(qid), int(n))); c.commit(); return cur.rowcount > 0


def question_count(n, kind=None):
    with db() as c:
        if kind: return c.execute('SELECT COUNT(*) FROM book_questions WHERE book_id=? AND kind=?', (int(n), kind)).fetchone()[0]
        return c.execute('SELECT COUNT(*) FROM book_questions WHERE book_id=?', (int(n),)).fetchone()[0]


def question_counts(n):
    return {'closed': question_count(n, 'closed'), 'open': question_count(n, 'open')}


def clear_questions(n, kind=None):
    with db() as c:
        cur = c.execute('DELETE FROM book_questions WHERE book_id=?' + (' AND kind=?' if kind else ''), (int(n),) + ((kind,) if kind else ()))
        c.commit(); return cur.rowcount


def questions(n, with_answers=False, kind=None):
    """Savollar (tur ichida 1 dan raqamlanadi). with_answers=True — faqat admin tahriri uchun."""
    with db() as c:
        rows = c.execute('SELECT id,kind,text,options,answer,explanation FROM book_questions WHERE book_id=?' + (' AND kind=?' if kind else '') + ' ORDER BY id',
                         (int(n),) + ((kind,) if kind else ())).fetchall()
    out, cnt = [], {}
    for r in rows:
        cnt[r['kind']] = cnt.get(r['kind'], 0) + 1
        opts = json.loads(r['options'])
        q = {'number': cnt[r['kind']], 'kind': r['kind'], 'text': r['text'], 'options': opts if r['kind'] == 'closed' else []}
        if with_answers:
            q.update({'id': r['id'], 'answer': r['answer'], 'explanation': r['explanation'], 'accepted': opts if r['kind'] == 'open' else []})
            if r['kind'] == 'open': q['options'] = []
        out.append(q)
    return out


def grade(uid, n, answers, kind='closed'):
    """answers: {'1':'B'} (yopiq) yoki {'1':'matn'} (ochiq). Javoblar serverda tekshiriladi; urinish bazaga yoziladi."""
    if kind not in KINDS: kind = 'closed'
    qs = questions(n, with_answers=True, kind=kind)
    if not qs: return None
    review, ok = [], 0
    for q in qs:
        raw = str((answers or {}).get(str(q['number']), '')).strip()
        if kind == 'open':
            u = raw[:200]; nu = _norm_ans(u)
            good = bool(nu) and any(nu == _norm_ans(a) for a in q['accepted'])
            ctext = ' / '.join(q['accepted'])
        else:
            u = raw.upper()[:1]; good = (u == q['answer'])
            ctext = q['options'][LETTERS.index(q['answer'])] if q['answer'] in LETTERS and LETTERS.index(q['answer']) < len(q['options']) else ''
        ok += good
        review.append({'number': q['number'], 'text': q['text'], 'user': u, 'correct': q['answer'], 'is_ok': good,
                       'correct_text': ctext, 'explanation': q['explanation']})
    with db() as c:
        c.execute('INSERT INTO book_attempts(user_id,book_id,correct,total,created_at,kind) VALUES(?,?,?,?,?,?)', (int(uid), int(n), ok, len(qs), now(), kind))
        c.commit()
    return {'kind': kind, 'correct': ok, 'total': len(qs), 'percent': round(ok * 100 / len(qs)), 'review': review}


def best_score(uid, n, kind=None):
    with db() as c:
        r = c.execute('SELECT MAX(correct*100.0/total) p, COUNT(*) k FROM book_attempts WHERE user_id=? AND book_id=?' + (' AND kind=?' if kind else ''),
                      (int(uid), int(n)) + ((kind,) if kind else ())).fetchone()
    return {'best': (round(r['p']) if r['p'] is not None else None), 'tries': r['k']}
