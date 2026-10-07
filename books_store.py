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
