"""Test savollari uchun boy matn (qalin / qiya / tagiga chiziq / jadval / rasm) va Word (.docx) import.

Belgilash (matn ichida oddiy teglar):
  [b]qalin[/b]  [i]qiya[/i]  [u]tagiga chiziq[/u]  [sup]yuqori indeks[/sup]  [sub]quyi indeks[/sub]
  [img:12]                       — yuklangan rasm (ID bo'yicha)
  [tbl]A|B|C¶1|2|3[/tbl]         — jadval (katak: |, qator: ¶)
Qo'shimcha kutubxona kerak emas (faqat zipfile + xml + PIL).
"""
import io, re, zipfile
import xml.etree.ElementTree as ET
from national_certificate import db, now

MAX_IMG_SIDE = 1400
MAX_DOCX = 8 * 1024 * 1024
MAX_DOCX_IMAGES = 60
MAX_TEXT = 6000

TAG_RE = re.compile(r'\[/?(?:b|i|u|sup|sub)\]')
ANY_RE = re.compile(r'\[/?(?:b|i|u|sup|sub)\]|\[img:\d+\]|\[/?tbl\]')
_ready = False


def strip(text):
    """Teglarni olib tashlaydi (Telegram xabari, CSV, ochiq javob uchun)."""
    s = str(text or '')
    s = re.sub(r'\[img:\d+\]', '🖼', s)
    s = re.sub(r'\[tbl\](.*?)\[/tbl\]', lambda m: '\n' + m.group(1).replace('¶', '\n').replace('|', '  |  ') + '\n', s, flags=re.S)
    return TAG_RE.sub('', s)


# ---------------------------------------------------------------- rasmlar
def _init():
    global _ready
    if _ready: return
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS q_images(
            id INTEGER PRIMARY KEY AUTOINCREMENT, data BLOB NOT NULL, owner INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)''')
        c.commit()
    _ready = True


def add_image(raw, owner=0):
    """Rasmni kichraytirib (JPEG) saqlaydi, ID qaytaradi. Yaroqsiz bo'lsa ValueError."""
    from PIL import Image
    _init()
    try:
        im = Image.open(io.BytesIO(raw)); im.load()
    except Exception:
        raise ValueError('Rasm o‘qilmadi.')
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA'); bg = Image.new('RGB', im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[-1]); im = bg
    else:
        im = im.convert('RGB')
    im.thumbnail((MAX_IMG_SIDE, MAX_IMG_SIDE))
    out = io.BytesIO(); im.save(out, 'JPEG', quality=84, optimize=True)
    with db() as c:
        cur = c.execute('INSERT INTO q_images(data,owner,created_at) VALUES(?,?,?)', (out.getvalue(), int(owner), now()))
        c.commit(); return cur.lastrowid


def get_image(i):
    _init()
    with db() as c:
        r = c.execute('SELECT data FROM q_images WHERE id=?', (int(i),)).fetchone()
    return bytes(r['data']) if r else None


# ---------------------------------------------------------------- Word (.docx)
NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'v': 'urn:schemas-microsoft-com:vml',
}
W = '{%s}' % NS['w']
R = '{%s}' % NS['r']
A = '{%s}' % NS['a']
V = '{%s}' % NS['v']


def _on(el):
    """<w:b/> yoki <w:b w:val="1"/> — yoqilgan; val=0/false/none — o'chiq."""
    if el is None: return False
    v = el.get(W + 'val')
    return v is None or v.lower() not in ('0', 'false', 'none', 'off')


class _Docx:
    def __init__(self, raw, owner, allow_images=True):
        self.z = zipfile.ZipFile(io.BytesIO(raw))
        self.owner = owner
        self.allow_images = allow_images
        self.rels = {}
        self.imgs = {}          # rId -> saqlangan rasm ID
        self.img_count = 0
        self.num = {}           # (numId, ilvl) -> hisoblagich
        self.numfmt = {}        # (numId, ilvl) -> format
        self.warn = []
        try:
            rr = ET.fromstring(self.z.read('word/_rels/document.xml.rels'))
            for e in rr: self.rels[e.get('Id')] = e.get('Target')
        except KeyError: pass
        self._load_numbering()

    def _load_numbering(self):
        try: root = ET.fromstring(self.z.read('word/numbering.xml'))
        except KeyError: return
        absf = {}
        for an in root.findall('w:abstractNum', NS):
            aid = an.get(W + 'abstractNumId')
            for lv in an.findall('w:lvl', NS):
                f = lv.find('w:numFmt', NS)
                absf[(aid, lv.get(W + 'ilvl'))] = f.get(W + 'val') if f is not None else 'decimal'
        for n in root.findall('w:num', NS):
            nid = n.get(W + 'numId'); a = n.find('w:abstractNumId', NS)
            if a is None: continue
            for (aid, lvl), f in absf.items():
                if aid == a.get(W + 'val'): self.numfmt[(nid, lvl)] = f

    def _image(self, rid):
        if not self.allow_images:
            if 'img_denied' not in self.warn: self.warn.append('img_denied')
            return None
        if rid in self.imgs: return self.imgs[rid]
        t = self.rels.get(rid)
        if not t: return None
        path = t.lstrip('/') if t.startswith('/') else 'word/' + t
        path = re.sub(r'(^|/)\./', r'\1', path)
        try: raw = self.z.read(path)
        except KeyError: return None
        if self.img_count >= MAX_DOCX_IMAGES:
            if 'img_limit' not in self.warn: self.warn.append('img_limit')
            return None
        try: iid = add_image(raw, self.owner)
        except ValueError:     # masalan .emf/.wmf — brauzer ko'rsata olmaydi
            if 'img_fmt' not in self.warn: self.warn.append('img_fmt')
            return None
        self.img_count += 1; self.imgs[rid] = iid
        return iid

    # --- paragraf
    def _runs(self, p):
        """[(format, matn)] — formatlangan bo'laklar."""
        segs = []
        for r in p.iter(W + 'r'):
            pr = r.find('w:rPr', NS)
            fmt = ()
            if pr is not None:
                f = []
                if _on(pr.find('w:b', NS)): f.append('b')
                if _on(pr.find('w:i', NS)): f.append('i')
                u = pr.find('w:u', NS)
                if u is not None and u.get(W + 'val', 'single') != 'none': f.append('u')
                va = pr.find('w:vertAlign', NS)
                if va is not None and va.get(W + 'val') in ('superscript', 'subscript'):
                    f.append('sup' if va.get(W + 'val') == 'superscript' else 'sub')
                fmt = tuple(f)
            for ch in r:
                tag = ch.tag
                if tag == W + 't': segs.append((fmt, ch.text or ''))
                elif tag in (W + 'tab', W + 'br', W + 'cr'): segs.append((fmt, ' '))
                elif tag == W + 'noBreakHyphen': segs.append((fmt, '-'))
                elif tag in (W + 'drawing', W + 'pict'):
                    for bl in ch.iter(A + 'blip'):
                        i = self._image(bl.get(R + 'embed'))
                        if i: segs.append(((), '[img:%d]' % i))
                    for im in ch.iter(V + 'imagedata'):
                        i = self._image(im.get(R + 'id'))
                        if i: segs.append(((), '[img:%d]' % i))
        # bir xil formatdagi qo'shni bo'laklarni birlashtirish
        merged = []
        for f, t in segs:
            if merged and merged[-1][0] == f: merged[-1] = (f, merged[-1][1] + t)
            else: merged.append((f, t))
        return merged

    @staticmethod
    def _wrap(segs):
        out = []
        for f, t in segs:
            if not f or not t.strip(): out.append(t); continue
            lead = t[:len(t) - len(t.lstrip())]; trail = t[len(t.rstrip()):]; core = t.strip()
            for tg in f: core = '[%s]%s[/%s]' % (tg, core, tg)
            out.append(lead + core + trail)
        return ''.join(out)

    def _label(self, p):
        ppr = p.find('w:pPr', NS)
        if ppr is None: return ''
        np_ = ppr.find('w:numPr', NS)
        if np_ is None: return ''
        n = np_.find('w:numId', NS); l = np_.find('w:ilvl', NS)
        nid = n.get(W + 'val') if n is not None else None
        lvl = l.get(W + 'val') if l is not None else '0'
        if not nid or nid == '0': return ''
        fmt = self.numfmt.get((nid, lvl), 'decimal')
        if fmt == 'bullet': return ''
        k = (nid, lvl); self.num[k] = self.num.get(k, 0) + 1; c = self.num[k]
        if fmt in ('upperLetter', 'lowerLetter'):
            return ('ABCDEFGHIJKLMNOPQRSTUVWXYZ'[(c - 1) % 26]) + ') '
        if fmt in ('upperRoman', 'lowerRoman', 'decimal', 'decimalZero'): return '%d. ' % c
        return '%d. ' % c

    def paragraph(self, p):
        txt = self._wrap(self._runs(p))
        vis = TAG_RE.sub('', txt).strip()
        if not vis: return ''
        label = self._label(p)
        if label and not re.match(r'^\s*(?:\d+\s*[\.\)]|[A-Fa-f]\s*[\)\.])', vis): txt = label + txt
        return re.sub(r'\s+', ' ', txt).strip()

    def table(self, tbl):
        rows = []
        for tr in tbl.findall('w:tr', NS):
            cells = []
            for tc in tr.findall('w:tc', NS):
                parts = [self.paragraph(p) for p in tc.findall('w:p', NS)]
                cell = ' '.join(x for x in parts if x).replace('|', '/').replace('¶', ' ')
                cells.append(cell)
                span = tc.find('w:tcPr/w:gridSpan', NS)
                if span is not None:
                    try: cells.extend([''] * (int(span.get(W + 'val')) - 1))
                    except Exception: pass
            if cells: rows.append('|'.join(cells))
        if not rows or all(not r.replace('|', '').strip() for r in rows): return ''
        return '[tbl]' + '¶'.join(rows) + '[/tbl]'

    def lines(self):
        root = ET.fromstring(self.z.read('word/document.xml'))
        body = root.find('w:body', NS)
        out = []
        for el in body:
            if el.tag == W + 'p':
                s = self.paragraph(el)
                if s: out.append(s)
            elif el.tag == W + 'tbl':
                s = self.table(el)
                if s: out.append(s)
        return out


def docx_to_text(raw, owner=0, allow_images=True):
    """Word faylni (.docx) matn qatorlariga aylantiradi (teglar bilan). (matn, ogohlantirishlar) qaytaradi."""
    if len(raw) > MAX_DOCX: raise ValueError('Fayl juda katta (8 MB gacha).')
    if raw[:2] != b'PK': raise ValueError('Bu .docx fayl emas. Word’da «Saqlash → .docx» qiling (eski .doc ishlamaydi).')
    try: d = _Docx(raw, owner, allow_images)
    except zipfile.BadZipFile: raise ValueError('Fayl buzilgan yoki .docx emas.')
    try: lines = d.lines()
    except KeyError: raise ValueError('Word fayl ichida matn topilmadi.')
    except ET.ParseError: raise ValueError('Word fayl o‘qilmadi.')
    warns = []
    if 'img_denied' in d.warn: warns.append('Rasmlar qo‘shilmadi: rasm yuklash faqat admin uchun.')
    if 'img_limit' in d.warn: warns.append(f'Rasmlar {MAX_DOCX_IMAGES} tadan oshdi — qolganlari qo‘shilmadi.')
    if 'img_fmt' in d.warn: warns.append('Ba’zi rasmlar (masalan .emf/.wmf) o‘qilmadi — ularni JPG/PNG qilib qo‘ying.')
    return '\n'.join(lines), warns
