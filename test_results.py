"""Test muddati, yakunlash va natijalar fayli (Excel .xlsx) — milliy sertifikat va oddiy testlar uchun.

kind: 'ms' (milliy sertifikat testi) yoki 'simple' (oddiy test).
Qo'shimcha kutubxona kerak emas: .xlsx fayl zipfile yordamida yig'iladi.
"""
import io, json, zipfile, logging
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
from national_certificate import db, now

UZ = timezone(timedelta(hours=5))
DEADLINE_CHOICES = {1, 6, 24, 72, 168, 720}   # soat


# ------------------------------------------------------------------ muddat / yakunlash
def init_results_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS test_deadlines(
            kind TEXT NOT NULL, code TEXT NOT NULL, closes_at TEXT, finished_at TEXT,
            PRIMARY KEY(kind, code))''')
        c.commit()


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def set_deadline(kind, code, hours):
    """hours=None/0 — muddatsiz (faqat qo'lda yakunlanadi)."""
    code = code.upper().strip()
    closes = _iso(datetime.now(timezone.utc) + timedelta(hours=int(hours))) if hours else None
    with db() as c:
        c.execute('''INSERT INTO test_deadlines(kind,code,closes_at,finished_at) VALUES(?,?,?,NULL)
                     ON CONFLICT(kind,code) DO UPDATE SET closes_at=excluded.closes_at''', (kind, code, closes))
        c.commit()
    return closes


def info(kind, code):
    with db() as c:
        r = c.execute('SELECT closes_at,finished_at FROM test_deadlines WHERE kind=? AND code=?', (kind, code.upper().strip())).fetchone()
    closes, fin = (r['closes_at'], r['finished_at']) if r else (None, None)
    closed = bool(fin) or bool(closes and closes <= _iso(datetime.now(timezone.utc)))
    return {'closes_at': closes, 'finished_at': fin, 'closed': closed}


def is_closed(kind, code):
    return info(kind, code)['closed']


def finish(kind, code):
    """Testni yakunlaydi. Yangi yakunlangan bo'lsa True, avval yakunlangan bo'lsa False."""
    code = code.upper().strip()
    with db() as c:
        r = c.execute('SELECT finished_at FROM test_deadlines WHERE kind=? AND code=?', (kind, code)).fetchone()
        if r and r['finished_at']:
            return False
        if r:
            c.execute('UPDATE test_deadlines SET finished_at=? WHERE kind=? AND code=?', (now(), kind, code))
        else:
            c.execute('INSERT INTO test_deadlines(kind,code,closes_at,finished_at) VALUES(?,?,NULL,?)', (kind, code, now()))
        c.commit()
    return True


def due():
    """Muddati o'tgan, lekin hali yakunlanmagan testlar: [(kind, code)]."""
    with db() as c:
        rows = c.execute('SELECT kind,code FROM test_deadlines WHERE finished_at IS NULL AND closes_at IS NOT NULL AND closes_at<=?',
                         (_iso(datetime.now(timezone.utc)),)).fetchall()
    return [(r['kind'], r['code']) for r in rows]


# ------------------------------------------------------------------ test va ishtirokchilar
def _table(kind):
    return 'national_tests' if kind == 'ms' else 'simple_tests'


def get_meta(kind, code):
    """{'id','title','created_by','questions'} yoki None."""
    with db() as c:
        r = c.execute(f'SELECT id,code,title,created_by,questions_json FROM {_table(kind)} WHERE code=?', (code.upper().strip(),)).fetchone()
    if not r:
        return None
    return {'id': r['id'], 'code': r['code'], 'title': r['title'], 'created_by': r['created_by'], 'questions': json.loads(r['questions_json'])}


def _split_name(uid):
    with db() as c:
        r = c.execute('SELECT name,username FROM mini_users WHERE user_id=?', (uid,)).fetchone()
    name = ((r['name'] if r else '') or '').strip()
    uname = ('@' + r['username']) if r and r['username'] else ''
    if not name:
        return f'Talabgor {uid}', '', uname
    parts = name.split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else ''), uname


def _fmt_time(iso):
    try:
        return datetime.fromisoformat(iso).astimezone(UZ).strftime('%d.%m.%Y %H:%M')
    except Exception:
        return iso or ''


def _ms_max(questions):
    return sum(float(q.get('points', 1)) for q in questions if q.get('type', 'Y1') != 'O2')


def participants(kind, code):
    m = get_meta(kind, code)
    if not m:
        return []
    out, seen = [], {}
    with db() as c:
        if kind == 'simple':
            rows = c.execute('SELECT * FROM simple_attempts WHERE test_id=? ORDER BY id', (m['id'],)).fetchall()
        else:
            rows = c.execute('SELECT * FROM national_attempts WHERE test_id=? ORDER BY id', (m['id'],)).fetchall()
    mx_pts = _ms_max(m['questions']) if kind == 'ms' else 0
    for r in rows:
        uid = r['user_id']; seen[uid] = seen.get(uid, 0) + 1
        first, last, uname = _split_name(uid)
        d = {'user_id': uid, 'first': first, 'last': last, 'username': uname, 'attempt': seen[uid], 'at': _fmt_time(r['created_at'])}
        if kind == 'simple':
            try: errs = [int(x) for x in json.loads(r['errors_json'] or '[]')]
            except Exception: errs = []
            tot = r['total']; d.update(correct=r['correct'], total=tot, percent=round(r['correct'] / tot * 100) if tot else 0,
                                        errors=[str(x) for x in errs], err_nums=errs)
        else:
            try: raw_errs = json.loads(r['errors_json'] or '[]')
            except Exception: raw_errs = []
            labels, nums = [], []
            for e in raw_errs if isinstance(raw_errs, list) else []:
                if not isinstance(e, dict): continue
                n = e.get('number'); nums.append(n)
                wp = e.get('wrong_parts')
                labels.append(f"{n}({'+'.join(wp)})" if wp else str(n))
            d.update(correct=r['raw_score'], total=mx_pts, percent=round((r['raw_score'] or 0) / mx_pts * 100) if mx_pts else 0,
                     combined=r['diagnostic_score'], level=r['level'] or '', errors=labels, err_nums=[x for x in nums if x])
        out.append(d)
    return out


# ------------------------------------------------------------------ .xlsx yozuvchi (kutubxonasiz)
def _col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


def _sheet_xml(rows, widths, styles):
    cols = ''.join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths, 1))
    body = []
    for ri, row in enumerate(rows, 1):
        cells = []
        for ci, v in enumerate(row, 1):
            ref = f'{_col(ci)}{ri}'; st = styles.get(ri, 0)
            if v is None or v == '':
                if st: cells.append(f'<c r="{ref}" s="{st}"/>')
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                cells.append(f'<c r="{ref}" s="{st}"><v>{v}</v></c>')
            else:
                cells.append(f'<c r="{ref}" s="{st}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>')
        body.append(f'<row r="{ri}">{"".join(cells)}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetViews><sheetView workbookViewId="0"/></sheetViews><cols>{cols}</cols><sheetData>{"".join(body)}</sheetData></worksheet>')


def make_xlsx(sheets):
    """sheets: [(nom, qatorlar, ustun_kengliklari, {qator_raqami: uslub})]; uslub 1=sarlavha, 2=katta matn."""
    z_io = io.BytesIO()
    with zipfile.ZipFile(z_io, 'w', zipfile.ZIP_DEFLATED) as z:
        n = len(sheets)
        z.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, n + 1)) + '</Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + ''.join(f'<sheet name="{escape(s[0])[:31]}" sheetId="{i}" r:id="rId{i}"/>' for i, s in enumerate(sheets, 1)) + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, n + 1))
                   + f'<Relationship Id="rId{n+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                   '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font><font><b/><sz val="14"/><name val="Calibri"/></font></fonts>'
                   '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0B7656"/></patternFill></fill></fills>'
                   '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
                   '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                   '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="top" wrapText="1"/></xf>'
                   '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center" wrapText="1"/></xf>'
                   '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        for i, (name, rows, widths, styles) in enumerate(sheets, 1):
            z.writestr(f'xl/worksheets/sheet{i}.xml', _sheet_xml(rows, widths, styles))
    return z_io.getvalue()


def _num(x):
    try:
        f = float(x); return int(f) if f == int(f) else round(f, 2)
    except Exception:
        return x


def build_xlsx(kind, code):
    """(fayl_nomi, bayt) yoki None."""
    m = get_meta(kind, code)
    if not m:
        return None
    ps = participants(kind, code); inf = info(kind, code)
    state = 'Yakunlangan' if inf['closed'] else 'Davom etmoqda'
    n_users = len({p['user_id'] for p in ps})
    title_rows = [[f"{m['title']} — natijalar"], [f"Test kodi: {m['code']}   |   Holat: {state}   |   Ishtirokchilar: {n_users}   |   Urinishlar: {len(ps)}   |   Fayl vaqti: {_fmt_time(now())}"], []]
    if kind == 'simple':
        head = ['№', 'Ism', 'Familiya', 'Telegram', 'Urinish', 'To‘g‘ri javoblar', 'Jami savol', 'Foiz (%)', 'Xato qilgan savollar', 'Topshirgan vaqt']
        data = [[i, p['first'], p['last'], p['username'], p['attempt'], p['correct'], p['total'], p['percent'], ', '.join(p['errors']) or '—', p['at']] for i, p in enumerate(ps, 1)]
        widths = [5, 16, 18, 16, 9, 12, 11, 10, 40, 17]
    else:
        head = ['№', 'Ism', 'Familiya', 'Telegram', 'Urinish', 'Test balli', 'Maksimal', 'Foiz (%)', 'Umumiy ball (test+esse)', 'Daraja', 'Xato qilgan topshiriqlar', 'Topshirgan vaqt']
        data = [[i, p['first'], p['last'], p['username'], p['attempt'], _num(p['correct']), _num(p['total']), p['percent'], _num(p.get('combined')), p.get('level', ''), ', '.join(p['errors']) or '—', p['at']] for i, p in enumerate(ps, 1)]
        widths = [5, 16, 18, 16, 9, 10, 10, 9, 14, 18, 40, 17]
    rows1 = title_rows + [head] + data
    sheet1 = ('Natijalar', rows1, widths, {1: 2, 4: 1})
    # 2-varaq: savollar bo'yicha xatolar
    cnt = {}
    for p in ps:
        for q in set(p['err_nums']):
            cnt[q] = cnt.get(q, 0) + 1
    total_q = len(m['questions']); att = len(ps)
    rows2 = [['Savollar tahlili'], [], ['Savol №', 'Xato qilganlar soni', 'Xato foizi (%)']]
    for q in range(1, total_q + 1):
        rows2.append([q, cnt.get(q, 0), round(cnt.get(q, 0) / att * 100) if att else 0])
    sheet2 = ('Savollar tahlili', rows2, [10, 20, 16], {1: 2, 3: 1})
    safe = ''.join(ch for ch in m['code'] if ch.isalnum() or ch in '-_')
    return f'natijalar_{safe}.xlsx', make_xlsx([sheet1, sheet2])
