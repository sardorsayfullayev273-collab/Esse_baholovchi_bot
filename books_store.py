"""Badiiy asarlar rasmlari — bazada (SQLite) saqlanadi: bot orqali qo'shiladi, zaxira nusxaga ham kiradi."""
import io, os, json
from national_certificate import db, now

FULL_MAX = 1280   # to'liq rasm: eng katta tomoni
THUMB_W = 360


def init_books_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS books(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, full BLOB NOT NULL, thumb BLOB NOT NULL, created_at TEXT NOT NULL)''')
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
        rows = c.execute('SELECT id,title FROM books ORDER BY id').fetchall()
    return [{'n': r['id'], 'title': r['title']} for r in rows]


def get_image(n, thumb=False):
    with db() as c:
        r = c.execute('SELECT full,thumb FROM books WHERE id=?', (int(n),)).fetchone()
    return (r['thumb'] if thumb else r['full']) if r else None


def delete(n):
    with db() as c:
        cur = c.execute('DELETE FROM books WHERE id=?', (int(n),)); c.commit(); return cur.rowcount > 0


def rename(n, title):
    with db() as c:
        cur = c.execute('UPDATE books SET title=? WHERE id=?', (title.strip()[:120], int(n))); c.commit(); return cur.rowcount > 0


def seed_from_dir(folder):
    """Baza bo'sh bo'lsa va books/ papkasi bo'lsa — undagi asarlarni bazaga ko'chiradi (bir marta)."""
    try:
        with db() as c:
            if c.execute('SELECT COUNT(*) FROM books').fetchone()[0]:
                return 0
        man = json.load(open(os.path.join(folder, 'books.json'), encoding='utf-8'))
    except Exception:
        return 0
    n = 0
    for it in man:
        try:
            raw = open(os.path.join(folder, '%02d.jpg' % it['n']), 'rb').read()
            add(it['title'], raw); n += 1
        except Exception:
            pass
    return n
