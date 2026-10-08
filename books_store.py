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
        c.execute('CREATE INDEX IF NOT EXISTS ix_book_q ON book_questions(book_id)')
        c.execute('''CREATE TABLE IF NOT EXISTS book_attempts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, book_id INTEGER NOT NULL, correct INTEGER NOT NULL,
            total INTEGER NOT NULL, created_at TEXT NOT NULL)''')
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
        rows = c.execute('''SELECT b.id, b.title, b.author, (b.info<>'') has_info,
            (SELECT COUNT(*) FROM book_images i WHERE i.book_id=b.id) pics,
            (SELECT COUNT(*) FROM book_questions q WHERE q.book_id=b.id) qn
            FROM books b ORDER BY b.id''').fetchall()
    return [{'n': r['id'], 'title': r['title'], 'author': r['author'], 'has_info': bool(r['has_info']), 'pics': r['pics'], 'qn': r['qn']} for r in rows]


def get_image(n, thumb=False):
    with db() as c:
        r = c.execute('SELECT full,thumb FROM books WHERE id=?', (int(n),)).fetchone()
    return (r['thumb'] if thumb else r['full']) if r else None


def delete(n):
    with db() as c:
        cur = c.execute('DELETE FROM books WHERE id=?', (int(n),))
        for t in ('book_images', 'book_questions', 'book_attempts'):
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
    return {'n': r['id'], 'title': r['title'], 'author': r['author'], 'info': r['info'], 'pics': pic_ids(n), 'qn': question_count(n)}


# ------------------------------------------------------------------ test
LETTERS = 'ABCDEF'


def parse_bulk(text):
    """'1. Savol / A) ... / Javob: B / Izoh: ...' formatidagi matnni savollarga aylantiradi. (savollar, xatolar)"""
    import re
    qs, errs, cur = [], [], None
    def flush():
        nonlocal cur
        if cur: qs.append(cur); cur = None
    for raw in text.replace('\r', '').split('\n'):
        line = raw.strip()
        if not line: continue
        m = re.match(r'^(?:Javob|Жавоб|Answer)\s*[:\-]\s*([A-Fa-f])\b', line, re.I)
        if m and cur: cur['answer'] = m.group(1).upper(); continue
        m = re.match(r'^Izoh\s*[:\-]\s*(.+)$', line, re.I)
        if m and cur: cur['explanation'] = m.group(1).strip(); continue
        m = re.match(r'^([A-Fa-f])\s*[\)\.]\s*(.+)$', line)
        if m and cur: cur['options'].append(m.group(2).strip()); continue
        m = re.match(r'^\d+\s*[\.\)]\s*(.+)$', line)
        if m: flush(); cur = {'text': m.group(1).strip(), 'options': [], 'answer': '', 'explanation': ''}; continue
        if cur and not cur['options']: cur['text'] += ' ' + line
    flush()
    for i, q in enumerate(qs, 1):
        if len(q['options']) < 2: errs.append(f'{i}-savolda variantlar yetarli emas (kamida 2 ta)')
        elif len(q['options']) > 6: errs.append(f'{i}-savolda 6 tadan ortiq variant bor')
        elif not q['answer']: errs.append(f'{i}-savolda «Javob: X» yo‘q')
        elif LETTERS.index(q['answer']) >= len(q['options']): errs.append(f'{i}-savol javobi variantlardan tashqarida')
    return qs, errs


def add_questions(n, qs, replace=False):
    with db() as c:
        if replace: c.execute('DELETE FROM book_questions WHERE book_id=?', (int(n),))
        for q in qs:
            c.execute('INSERT INTO book_questions(book_id,text,options,answer,explanation) VALUES(?,?,?,?,?)',
                      (int(n), q['text'][:1500], json.dumps(q['options'], ensure_ascii=False), q['answer'], (q.get('explanation') or '')[:1000]))
        c.commit()
    return question_count(n)


def question_count(n):
    with db() as c:
        return c.execute('SELECT COUNT(*) FROM book_questions WHERE book_id=?', (int(n),)).fetchone()[0]


def clear_questions(n):
    with db() as c:
        cur = c.execute('DELETE FROM book_questions WHERE book_id=?', (int(n),)); c.commit(); return cur.rowcount


def questions(n, with_answers=False):
    with db() as c:
        rows = c.execute('SELECT id,text,options,answer,explanation FROM book_questions WHERE book_id=? ORDER BY id', (int(n),)).fetchall()
    out = []
    for i, r in enumerate(rows, 1):
        q = {'number': i, 'text': r['text'], 'options': json.loads(r['options'])}
        if with_answers: q.update({'answer': r['answer'], 'explanation': r['explanation']})
        out.append(q)
    return out


def grade(uid, n, answers):
    """answers: {'1':'B',...}. Natija va har bir savol bo'yicha tahlil; urinish bazaga yoziladi."""
    qs = questions(n, with_answers=True)
    if not qs: return None
    review, ok = [], 0
    for q in qs:
        u = str((answers or {}).get(str(q['number']), '')).strip().upper()[:1]
        good = (u == q['answer']); ok += good
        review.append({'number': q['number'], 'text': q['text'], 'user': u, 'correct': q['answer'], 'is_ok': good,
                       'correct_text': q['options'][LETTERS.index(q['answer'])], 'explanation': q['explanation']})
    with db() as c:
        c.execute('INSERT INTO book_attempts(user_id,book_id,correct,total,created_at) VALUES(?,?,?,?,?)', (int(uid), int(n), ok, len(qs), now()))
        c.commit()
    return {'correct': ok, 'total': len(qs), 'percent': round(ok * 100 / len(qs)), 'review': review}


def best_score(uid, n):
    with db() as c:
        r = c.execute('SELECT MAX(correct*100.0/total) p, COUNT(*) k FROM book_attempts WHERE user_id=? AND book_id=?', (int(uid), int(n))).fetchone()
    return {'best': (round(r['p']) if r['p'] is not None else None), 'tries': r['k']}
