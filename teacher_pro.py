# -*- coding: utf-8 -*-
"""v56: USTOZ PRO — obuna (30 kun), sinf tahlili (Milliy sertifikat: Rasch bilan; Oddiy test: oddiy hisob) va PDF hisobot.
Hech qanday tashqi kutubxona yo'q (PIL bot'da bor). AI chaqirilmaydi — xarajat 0."""
import io
import json
import math
import os
import re
import statistics
from datetime import datetime, timedelta, timezone

import national_certificate as nc
import test_results as tr

FREE_REPORT_MAX_N = 30          # bepul 1 ta hisobot: ko'pi bilan shuncha ishtirokchi
LEVELS = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'NC']
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')


def _iso(dt): return dt.replace(tzinfo=None).isoformat(timespec='seconds') + 'Z'
def _parse(s): return datetime.fromisoformat(str(s).rstrip('Z'))


# ------------------------------------------------------------------ obuna
def init_teacher_db():
    with nc.db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS teacher_pro(user_id INTEGER PRIMARY KEY, until TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS teacher_pro_orders(okey TEXT PRIMARY KEY, user_id INTEGER, at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS teacher_free(user_id INTEGER, kind TEXT, code TEXT, at TEXT, PRIMARY KEY(user_id,kind,code))")
        c.commit()


def pro_until(uid):
    with nc.db() as c:
        r = c.execute("SELECT until FROM teacher_pro WHERE user_id=?", (int(uid),)).fetchone()
    if not r: return None
    try:
        d = _parse(r[0])
    except Exception:
        return None
    return d if d > datetime.utcnow() else None


def grant_pro(uid, days, okey):
    """Obunani uzaytiradi (qayta bosilsa ham bir buyurtma ikki marta hisoblanmaydi). Qaytaradi: tugash sanasi."""
    uid = int(uid)
    with nc.db() as c:
        if c.execute("SELECT 1 FROM teacher_pro_orders WHERE okey=?", (okey,)).fetchone():
            return pro_until(uid)
        cur = pro_until(uid)
        base = max(datetime.utcnow(), cur) if cur else datetime.utcnow()
        until = (base + timedelta(days=int(days))).replace(microsecond=0)
        c.execute("INSERT INTO teacher_pro(user_id,until) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET until=excluded.until", (uid, _iso(until)))
        c.execute("INSERT INTO teacher_pro_orders(okey,user_id,at) VALUES(?,?,?)", (okey, uid, _iso(datetime.utcnow())))
        c.commit()
    return until


def access(uid, kind, code, n_participants, admin=False):
    """(ruxsat, sabab). Pro/admin — har doim. Aks holda 1 ta bepul hisobot (<= FREE_REPORT_MAX_N ishtirokchi)."""
    if admin or pro_until(uid): return True, 'pro'
    with nc.db() as c:
        if c.execute("SELECT 1 FROM teacher_free WHERE user_id=? AND kind=? AND code=?", (int(uid), kind, code)).fetchone(): return True, 'free'
        used = c.execute("SELECT COUNT(*) FROM teacher_free WHERE user_id=?", (int(uid),)).fetchone()[0]
        if used == 0 and n_participants <= FREE_REPORT_MAX_N:
            c.execute("INSERT OR IGNORE INTO teacher_free(user_id,kind,code,at) VALUES(?,?,?,?)", (int(uid), kind, code, _iso(datetime.utcnow()))); c.commit()
            return True, 'free_new'
    return False, ('limit_n' if used == 0 else 'need_pro')


def free_left(uid):
    with nc.db() as c:
        return 0 if c.execute("SELECT COUNT(*) FROM teacher_free WHERE user_id=?", (int(uid),)).fetchone()[0] else 1


# ------------------------------------------------------------------ fan / mavzu xaritasi
def parse_fanmap(text):
    """"Grammatika: 1-23, 36-39\nG'azal: 24-28"  ->  {'Grammatika':[1..23,36..39], ...}"""
    out = {}
    for line in re.split(r'[\n;]+', text or ''):
        if ':' not in line: continue
        name, rng = line.split(':', 1); name = name.strip()[:40]
        nums = []
        for part in re.split(r'[,\s]+', rng.strip()):
            m = re.fullmatch(r'(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?', part)
            if not m: continue
            a = int(m.group(1)); b = int(m.group(2) or a)
            if 0 < a <= b <= 1000: nums += list(range(a, b + 1))
        if name and nums: out[name] = sorted(set(nums))
    return out


def _mock_default_fanmap(kind, code):
    """v67: Mock testi uchun admin xarita kiritmagan bo'lsa — standart mavzular xaritasi (44 savol)."""
    if kind != 'ms': return ''
    try:
        import mock_mod as _mk
        return _mk.MOCK_FANMAP if _mk.is_mock_code(code) else ''
    except Exception:
        return ''


def fanmap_text(kind, code):
    try: return nc.setting(f'fanmap_{kind}_{code}', '') or _mock_default_fanmap(kind, code)
    except Exception: return ''


def get_fanmap(kind, code):
    try: return parse_fanmap(nc.setting(f'fanmap_{kind}_{code}', '') or _mock_default_fanmap(kind, code))
    except Exception: return {}


def set_fanmap(kind, code, text):
    fm = parse_fanmap(text)
    nc.set_setting(f'fanmap_{kind}_{code}', '\n'.join(f"{k}: {','.join(str(x) for x in v)}" for k, v in fm.items()))
    return fm


# ------------------------------------------------------------------ umumiy yordamchilar
def _label_level(score):
    lv = nc.level_for(score)
    return 'NC' if lv.startswith('Sertifikat') else lv


def _short_name(uid):
    first, last, uname = tr._split_name(uid)
    n = (first + ' ' + (last[:1] + '.' if last else '')).strip()
    return n or (uname or f'ID {uid}')


def _item_rows(item_pct, fanmap, n_items_meta):
    """item_pct: {item_id: (pct, n)}; qaytaradi sust/kuchli ro'yxatlar uchun tayyor qatorlar."""
    def fan_of(q):
        num = int(re.match(r'\d+', q).group())
        for name, nums in fanmap.items():
            if num in nums: return name
        return ''
    rows = [{'item': k, 'pct': v[0], 'fan': fan_of(k)} for k, v in item_pct.items()]
    return rows


def _discrimination(vectors, items):
    """27% yuqori va past guruhlar farqi: {item: D}. Kamida 10 ishtirokchi kerak."""
    N = len(vectors)
    if N < 10: return {}
    order = sorted(vectors.values(), key=lambda s: -len(s))
    k = max(2, round(0.27 * N)); up, lo = order[:k], order[-k:]
    return {it: round(sum(1 for v in up if it in v) / k - sum(1 for v in lo if it in v) / k, 2) for it in items}


def _hist(values, edges):
    out = [0] * (len(edges) - 1)
    for v in values:
        for i in range(len(edges) - 1):
            if edges[i] <= v < edges[i + 1] or (i == len(edges) - 2 and v == edges[-1]):
                out[i] += 1; break
    return out


def _spread(vals):
    if not vals: return {'mean': 0, 'median': 0, 'sd': 0, 'min': 0, 'max': 0}
    return {'mean': round(statistics.mean(vals), 1), 'median': round(statistics.median(vals), 1),
            'sd': round(statistics.pstdev(vals), 1) if len(vals) > 1 else 0, 'min': round(min(vals), 1), 'max': round(max(vals), 1)}


# ------------------------------------------------------------------ MILLIY SERTIFIKAT (Rasch)
def _first_attempts(table, test_id, cols):
    with nc.db() as c:
        rows = c.execute(f"SELECT {cols} FROM {table} WHERE test_id=? ORDER BY id", (test_id,)).fetchall()
    seen, out = set(), []
    for r in rows:
        if r['user_id'] in seen: continue
        seen.add(r['user_id']); out.append(r)
    return out


def _essay_total(check_id):
    if not check_id: return None
    try:
        with nc.db() as c:
            r = c.execute("SELECT total FROM checks WHERE id=?", (int(check_id),)).fetchone()
        return float(r[0]) if r and r[0] is not None else None
    except Exception:
        return None


def _rasch_cohort(items, vectors):
    """To'liq kohorta bo'yicha Rasch T (nc.rasch_test_t bilan bir xil qoida). -> ({uid:T}, rasch_ishladimi, izoh)."""
    N = len(vectors)
    def fb(): return {u: nc.fallback_t(len(v) / len(items) if items else 0) for u, v in vectors.items()}
    if N < nc.RASCH_MIN_N or not items:
        return fb(), False, f"Rasch uchun kamida {nc.RASCH_MIN_N} ta talabgor kerak (hozir {N}); ballar taxminiy shkala bo'yicha."
    inf = [n for n in items if 0 < sum(1 for v in vectors.values() if n in v) < N]
    if len(inf) < 5:
        return fb(), False, "Savollar yetarlicha farqlamaydi; ballar taxminiy shkala bo'yicha."
    th = {u: nc._logit_measure(sum(1 for n in inf if n in v), len(inf)) for u, v in vectors.items()}
    mu = sum(th.values()) / N; sd = math.sqrt(sum((t - mu) ** 2 for t in th.values()) / max(1, N - 1))
    if sd < 1e-9: return {u: 50.0 for u in vectors}, False, "Natijalar bir xil."
    return {u: round(max(0.0, min(75.0, 50 + 10 * (t - mu) / sd)), 1) for u, t in th.items()}, True, f"Rasch modeli: {N} talabgor, {len(inf)} ta farqlovchi band."


def ms_analytics(code):
    t = nc.get_test(code)
    if not t: return None
    items = nc.rasch_items(t); qs = t['questions']
    atts = _first_attempts('national_attempts', t['id'], 'user_id,essay_check_id,answers_json,raw_score,diagnostic_score,errors_json,created_at')
    N = len(atts)
    base = {'kind': 'ms', 'code': code, 'title': t.get('title', code), 'n': N, 'items_total': len(items)}
    if N == 0: return {**base, 'empty': True}
    vec, ans, raw, essay = {}, {}, {}, {}
    for a in atts:
        u = a['user_id']
        try: wrong = nc.wrong_item_ids(json.loads(a['errors_json'] or '[]'))
        except Exception: wrong = set()
        vec[u] = {i for i in items if i not in wrong}
        try: ans[u] = json.loads(a['answers_json'] or '{}')
        except Exception: ans[u] = {}
        raw[u] = float(a['raw_score'] or 0); essay[u] = _essay_total(a['essay_check_id'])
    tT, is_rasch, note = _rasch_cohort(items, vec)
    final = {}
    for u in vec:
        e = essay[u]
        if e is None: final[u] = tT[u] if not nc.ESSAY_MISSING_ZERO else round(tT[u] / 2, 1)
        else: final[u] = round((tT[u] + nc.essay_to_75(e)) / 2, 1)
    lvl = {u: _label_level(final[u]) for u in final}
    dist = {k: sum(1 for v in lvl.values() if v == k) for k in LEVELS}
    # savol tahlili
    item_pct = {i: (round(sum(1 for v in vec.values() if i in v) / N * 100, 1), N) for i in items}
    D = _discrimination(vec, items)
    fm = get_fanmap('ms', code)
    # xato variantlar (yopiq savollar uchun)
    weak = sorted(item_pct.items(), key=lambda kv: kv[1][0])[:10]
    def wrong_opt(item):
        m = re.match(r'(\d+)([ab]?)$', item); num = int(m.group(1))
        q = qs[num - 1] if 0 < num <= len(qs) else {}
        if q.get('type', 'Y1') not in ('Y1', 'Y2') or not q.get('answer'): return None
        cnt = {}
        for u, a in ans.items():
            x = str(a.get(str(num), '')).strip().upper()
            if x and x != str(q['answer']).strip().upper(): cnt[x] = cnt.get(x, 0) + 1
        if not cnt: return None
        o, c = max(cnt.items(), key=lambda kv: kv[1]); return {'option': o, 'share': round(c / N * 100), 'correct': str(q['answer']).upper()}
    def fan_of(item):
        num = int(re.match(r'\d+', item).group())
        for name, nums in fm.items():
            if num in nums: return name
        return ''
    weak_rows = [{'item': k, 'pct': v[0], 'fan': fan_of(k), 'wrong': wrong_opt(k), 'd': D.get(k)} for k, v in weak if v[0] < 60][:8]
    strong_rows = [{'item': k, 'pct': v[0], 'fan': fan_of(k)} for k, v in sorted(item_pct.items(), key=lambda kv: -kv[1][0])[:8]]
    bad_disc = [{'item': k, 'd': d, 'pct': item_pct[k][0]} for k, d in sorted(D.items(), key=lambda kv: kv[1])[:6] if d < 0.1]
    fans = []
    for name, nums in fm.items():
        its = [i for i in items if int(re.match(r'\d+', i).group()) in nums]
        ps = [item_pct[i][0] for i in its]
        if ps:
            m = statistics.mean(ps)
            worst = sorted(its, key=lambda i: item_pct[i][0])[:3]
            fans.append({'name': name, 'pct': round(m, 1), 'items': len(ps), 'wrong_pct': round(100 - m, 1),
                         'worst': [{'item': i, 'pct': item_pct[i][0], 'wrong': wrong_opt(i)} for i in worst if item_pct[i][0] < 80]})
    fans.sort(key=lambda f: f['pct'])
    vals = list(final.values())
    ranked = sorted(final, key=lambda u: -final[u])
    people = [{'rank': i + 1, 'user_id': u, 'name': _short_name(u), 'correct': round(raw[u], 1), 'rasch': tT[u],
               'essay': (nc.essay_to_75(essay[u]) if essay[u] is not None else None), 'essay24': (round(essay[u], 1) if essay[u] is not None else None),
               'final': final[u], 'level': lvl[u]} for i, u in enumerate(ranked)]
    _es = [e for e in essay.values() if e is not None]
    essay_stats = {'with': len(_es), 'missing': N - len(_es), 'mean24': (round(statistics.mean(_es), 1) if _es else None)}
    advice = []
    if fans: advice.append(f"Eng sust fan: {fans[0]['name']} ({fans[0]['pct']}%) — shu mavzuga urg'u bering.")
    if weak_rows: advice.append("Qayta o'tish kerak: " + ', '.join('#' + w['item'] for w in weak_rows[:5]) + '.')
    if bad_disc: advice.append("Yomon farqlovchi savollar (kalit yoki shartni tekshiring): " + ', '.join('#' + b['item'] for b in bad_disc[:4]) + '.')
    nonpass = dist.get('NC', 0)
    if nonpass: advice.append(f"{nonpass} ta o'quvchi sertifikat chegarasidan past — ular bilan alohida ishlang.")
    return {**base, 'empty': False, 'rasch': is_rasch, 'note': note, 'summary': {**_spread(vals), 'pass_pct': round(100 * (N - dist.get('NC', 0)) / N), 'raw_max': tr._ms_max(qs)},
            'levels': [{'name': k, 'n': dist[k], 'pct': round(100 * dist[k] / N)} for k in LEVELS],
            'hist': {'edges': [0, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75], 'counts': _hist(vals, [0, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75.01])},
            'items': [{'item': i, 'pct': item_pct[i][0], 'd': D.get(i)} for i in items], 'fans': fans, 'fanmap_set': bool(fm),
            'weak': weak_rows, 'strong': strong_rows, 'bad_disc': bad_disc, 'people': people, 'advice': advice, 'essay_stats': essay_stats}


# ------------------------------------------------------------------ ODDIY TEST (oddiy hisob)
def _grade5(pct):
    return 5 if pct >= 86 else 4 if pct >= 71 else 3 if pct >= 56 else 2


def simple_analytics(code):
    m = tr.get_meta('simple', code)
    if not m: return None
    qs = m['questions']; nq = len(qs)
    atts = _first_attempts('simple_attempts', m['id'], 'user_id,correct,total,errors_json,created_at')
    N = len(atts); base = {'kind': 'simple', 'code': code, 'title': m['title'], 'n': N, 'items_total': nq}
    if N == 0: return {**base, 'empty': True}
    items = [str(i) for i in range(1, nq + 1)]
    vec, pct, cor = {}, {}, {}
    for a in atts:
        u = a['user_id']
        try: errs = {str(int(x)) for x in json.loads(a['errors_json'] or '[]')}
        except Exception: errs = set()
        vec[u] = {i for i in items if i not in errs}
        cor[u] = a['correct']; pct[u] = round(a['correct'] / a['total'] * 100, 1) if a['total'] else 0.0
    vals = list(pct.values())
    gcount = {g: sum(1 for p in vals if _grade5(p) == g) for g in (5, 4, 3, 2)}
    item_pct = {i: (round(sum(1 for v in vec.values() if i in v) / N * 100, 1), N) for i in items}
    D = _discrimination(vec, items); fm = get_fanmap('simple', code)
    def fan_of(item):
        for name, nums in fm.items():
            if int(item) in nums: return name
        return ''
    weak_rows = [{'item': k, 'pct': v[0], 'fan': fan_of(k), 'wrong': None, 'd': D.get(k)} for k, v in sorted(item_pct.items(), key=lambda kv: kv[1][0])[:10] if v[0] < 60][:8]
    strong_rows = [{'item': k, 'pct': v[0], 'fan': fan_of(k)} for k, v in sorted(item_pct.items(), key=lambda kv: -kv[1][0])[:8]]
    bad_disc = [{'item': k, 'd': d, 'pct': item_pct[k][0]} for k, d in sorted(D.items(), key=lambda kv: kv[1])[:6] if d < 0.1]
    fans = []
    for name, nums in fm.items():
        ps = [item_pct[i][0] for i in items if int(i) in nums]
        if ps: fans.append({'name': name, 'pct': round(statistics.mean(ps), 1), 'items': len(ps)})
    fans.sort(key=lambda f: f['pct'])
    ranked = sorted(pct, key=lambda u: (-cor[u], u))
    people = [{'rank': i + 1, 'user_id': u, 'name': _short_name(u), 'correct': cor[u], 'total': nq, 'pct': pct[u], 'grade': _grade5(pct[u])} for i, u in enumerate(ranked)]
    advice = []
    if fans: advice.append(f"Eng sust mavzu: {fans[0]['name']} ({fans[0]['pct']}%).")
    if weak_rows: advice.append("Qayta o'tish kerak: " + ', '.join('#' + w['item'] for w in weak_rows[:5]) + '.')
    if bad_disc: advice.append("Yomon farqlovchi savollar (kalitni tekshiring): " + ', '.join('#' + b['item'] for b in bad_disc[:4]) + '.')
    if gcount[2]: advice.append(f"{gcount[2]} ta o'quvchi «2» baho oldi — takroriy dars kerak.")
    return {**base, 'empty': False, 'rasch': False, 'note': "Oddiy hisob: foiz = to'g'ri javoblar / jami savollar. Baho: 86%+ → 5, 71–85% → 4, 56–70% → 3, 56% dan past → 2.",
            'summary': {**_spread(vals), 'pass_pct': round(100 * (N - gcount[2]) / N)},
            'grades': [{'name': str(g), 'n': gcount[g], 'pct': round(100 * gcount[g] / N)} for g in (5, 4, 3, 2)],
            'hist': {'edges': list(range(0, 101, 10)), 'counts': _hist(vals, list(range(0, 100, 10)) + [100.01])},
            'items': [{'item': i, 'pct': item_pct[i][0], 'd': D.get(i)} for i in items], 'fans': fans, 'fanmap_set': bool(fm),
            'weak': weak_rows, 'strong': strong_rows, 'bad_disc': bad_disc, 'people': people, 'advice': advice}


def fan_report(code, uid):
    """v67: bitta o'quvchining mavzular bo'yicha xato savollari: [{'name','total','wrong':[...],'correct_pct'}]."""
    try:
        t = nc.get_test(code)
        fm = get_fanmap('ms', code)
        if not t or not fm: return []
        items = nc.rasch_items(t)
        atts = [a for a in _first_attempts('national_attempts', t['id'], 'user_id,errors_json') if int(a['user_id']) == int(uid)]
        if not atts: return []
        wrong = nc.wrong_item_ids(json.loads(atts[0]['errors_json'] or '[]'))
        out = []
        for name, nums in fm.items():
            its = [i for i in items if int(re.match(r'\d+', i).group()) in nums]
            if not its: continue
            w = sorted([i for i in its if i in wrong], key=lambda x: (int(re.match(r'\d+', x).group()), x))
            out.append({'name': name, 'total': len(its), 'wrong': w, 'correct_pct': round(100 * (len(its) - len(w)) / len(its))})
        return out
    except Exception:
        return []


def analytics(kind, code):
    return ms_analytics(code) if kind == 'ms' else simple_analytics(code)


def progress(uid, limit=40):
    """Ustozning Milliy sertifikat testlari bo'yicha o'quvchi rivoji (kamida 2 ta test): [{name, scores, delta}]."""
    with nc.db() as c:
        rows = c.execute("SELECT a.user_id, a.diagnostic_score s, a.id FROM national_attempts a JOIN national_tests t ON t.id=a.test_id WHERE t.created_by=? ORDER BY a.id", (int(uid),)).fetchall()
    seq = {}
    for r in rows: seq.setdefault(r['user_id'], []).append(round(float(r['s'] or 0), 1))
    out = [{'name': _short_name(u), 'scores': s[-10:], 'delta': round(s[-1] - s[0], 1), 'n': len(s)} for u, s in seq.items() if len(s) >= 2]
    out.sort(key=lambda x: (-x['n'], -x['delta']))
    return out[:limit]


# ------------------------------------------------------------------ PDF (PIL, ko'p sahifali)
_CYR = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя', ['a', 'b', 'v', 'g', 'd', 'e', 'yo', 'j', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't', 'u', 'f', 'x', 'ts', 'ch', 'sh', 'sh', '', 'i', '', 'e', 'yu', 'ya']))
_CYR.update({'қ': 'q', 'ғ': 'g', 'ў': "o'", 'ҳ': 'h'})


def safe_text(s):
    s = str(s or '')
    for a in ('ʻ', 'ʼ', '‘', '’', '`', '´'): s = s.replace(a, "'")
    out = []
    for ch in s:
        low = ch.lower()
        if low in _CYR:
            t = _CYR[low]; out.append(t.capitalize() if ch != low and t else t)
        elif ord(ch) < 0x250 or ch in '–—•−…':
            out.append(ch)
    return ''.join(out).strip()


class _Pdf:
    W, H, M = 1240, 1754, 70
    GREEN, GOLD, RED, AMBER, INK, MUTED, LINE, SOFT = '#0b6e4f', '#b8902f', '#c0392b', '#d9a21b', '#1d2b27', '#6b7a75', '#dfe6e3', '#f2f6f4'

    def __init__(self, title, subtitle):
        from PIL import Image, ImageDraw, ImageFont
        self.Image, self.ImageDraw, self.ImageFont = Image, ImageDraw, ImageFont
        self.title, self.subtitle = title, subtitle
        self.pages = []; self._fonts = {}; self.new_page()

    def f(self, size, bold=False):
        k = (size, bold)
        if k not in self._fonts:
            try: self._fonts[k] = self.ImageFont.truetype(os.path.join(FONT_DIR, 'Poppins-Bold.ttf' if bold else 'Poppins-Regular.ttf'), size)
            except Exception: self._fonts[k] = self.ImageFont.load_default()
        return self._fonts[k]

    def new_page(self):
        im = self.Image.new('RGB', (self.W, self.H), 'white'); self.pages.append(im); self.d = self.ImageDraw.Draw(im); self.y = self.M
        self.d.rectangle([0, 0, self.W, 14], fill=self.GREEN)
        self.text(self.M, 34, 'SINF HISOBOTI', 22, bold=True, fill=self.GREEN)
        self.text(self.W - self.M, 38, safe_text(self.title)[:60], 18, fill=self.MUTED, anchor='ra')
        self.y = 90

    def text(self, x, y, s, size=20, bold=False, fill=None, anchor='la'):
        self.d.text((x, y), safe_text(s), font=self.f(size, bold), fill=fill or self.INK, anchor=anchor)

    def fit(self, s, size, maxw, bold=False):
        s = safe_text(s); f = self.f(size, bold)
        while s and self.d.textlength(s, font=f) > maxw: s = s[:-2].rstrip() + '…' if len(s) > 2 else ''
        return s

    def need(self, h):
        if self.y + h > self.H - 90: self.new_page()

    def h2(self, s, sub=''):
        self.need(80); self.text(self.M, self.y, s, 30, bold=True); self.y += 42
        if sub: self.text(self.M, self.y, sub, 17, fill=self.MUTED); self.y += 30
        self.y += 6

    def kpis(self, items):
        w = (self.W - 2 * self.M - 20 * (len(items) - 1)) / len(items); x = self.M
        for lab, val in items:
            self.d.rounded_rectangle([x, self.y, x + w, self.y + 110], 16, fill=self.SOFT)
            self.text(x + 18, self.y + 14, lab, 16, fill=self.MUTED); self.text(x + 18, self.y + 44, str(val), 38, bold=True, fill=self.GREEN); x += w + 20
        self.y += 130

    def bars(self, rows, color_fn, maxv=None, label_w=150):
        mx = maxv or max([r[1] for r in rows] + [1]); bw = self.W - 2 * self.M - label_w - 190
        for lab, v, cap in rows:
            self.need(46); self.text(self.M, self.y + 3, self.fit(lab, 21, label_w - 12, True), 21, bold=True)
            w = max(2, int(bw * v / mx)) if v else 2
            self.d.rounded_rectangle([self.M + label_w, self.y + 4, self.M + label_w + w, self.y + 30], 6, fill=color_fn(lab, v))
            self.text(self.M + label_w + w + 12, self.y + 5, cap, 20, fill=self.INK); self.y += 44

    def vbars(self, labels, counts, color):
        self.need(330); h = 220; base = self.y + h + 40; mx = max(counts + [1]); n = len(counts)
        w = (self.W - 2 * self.M) / n
        for i, (lb, c) in enumerate(zip(labels, counts)):
            bh = int(h * c / mx); x0 = self.M + i * w + 8
            self.d.rounded_rectangle([x0, base - bh, x0 + w - 16, base], 6, fill=color)
            self.text(x0 + (w - 16) / 2, base - bh - 28, str(c), 19, bold=True, anchor='ma')
            self.text(x0 + (w - 16) / 2, base + 8, lb, 16, fill=self.MUTED, anchor='ma')
        self.y = base + 44

    def pct_color(self, p): return self.GREEN if p >= 70 else (self.AMBER if p >= 40 else self.RED)

    def grid(self, items, per_row=10):
        cw = (self.W - 2 * self.M) / per_row; ch = 78
        for i, it in enumerate(items):
            if i % per_row == 0: self.need(ch + 8)
            x = self.M + (i % per_row) * cw; 
            self.d.rounded_rectangle([x + 3, self.y + 3, x + cw - 3, self.y + ch - 3], 10, fill=self.pct_color(it['pct']))
            self.text(x + cw / 2, self.y + 12, '#' + it['item'], 17, fill='#ffffff', anchor='ma')
            self.text(x + cw / 2, self.y + 38, f"{int(round(it['pct']))}%", 23, bold=True, fill='#ffffff', anchor='ma')
            if i % per_row == per_row - 1 or i == len(items) - 1: self.y += ch

    def table(self, head, rows, widths, align=None, row_h=36, color_cols=None):
        total = sum(widths); sc = (self.W - 2 * self.M) / total; ws = [w * sc for w in widths]; align = align or ['l'] * len(head)
        def draw_head():
            self.d.rectangle([self.M, self.y, self.W - self.M, self.y + row_h], fill=self.GREEN); x = self.M
            for h, w, a in zip(head, ws, align): self.text(x + (6 if a == 'l' else w - 6), self.y + 6, h, 16, bold=True, fill='#fff', anchor='la' if a == 'l' else 'ra'); x += w
            self.y += row_h
        self.need(row_h * 3); draw_head()
        for i, r in enumerate(rows):
            if self.y + row_h > self.H - 90: self.new_page(); draw_head()
            if i % 2: self.d.rectangle([self.M, self.y, self.W - self.M, self.y + row_h], fill=self.SOFT)
            x = self.M
            for j, (c, w, a) in enumerate(zip(r, ws, align)):
                col = (color_cols or {}).get(j, lambda v: None)(c) or self.INK
                self.text(x + (6 if a == 'l' else w - 6), self.y + 6, self.fit(c, 17, w - 12), 17, fill=col, anchor='la' if a == 'l' else 'ra'); x += w
            self.y += row_h
        self.y += 20

    def para(self, s, size=19, fill=None, indent=0):
        words = safe_text(s).split(); line = ''
        for w in words:
            t = (line + ' ' + w).strip()
            if self.d.textlength(t, font=self.f(size)) > self.W - 2 * self.M - indent: self.need(32); self.text(self.M + indent, self.y, line, size, fill=fill); self.y += size + 10; line = w
            else: line = t
        if line: self.need(32); self.text(self.M + indent, self.y, line, size, fill=fill); self.y += size + 14

    def finish(self):
        n = len(self.pages)
        for i, im in enumerate(self.pages, 1):
            d = self.ImageDraw.Draw(im); d.line([self.M, self.H - 60, self.W - self.M, self.H - 60], fill=self.LINE, width=2)
            d.text((self.M, self.H - 48), safe_text(self.subtitle), font=self.f(16), fill=self.MUTED)
            d.text((self.W - self.M, self.H - 48), f'{i} / {n}', font=self.f(16), fill=self.MUTED, anchor='ra')
        buf = io.BytesIO()
        self.pages[0].save(buf, 'PDF', save_all=True, append_images=self.pages[1:], resolution=150.0, quality=85)
        return buf.getvalue()


def build_pdf(a, teacher_name='', prog=None):
    """a — analytics() natijasi. Qaytaradi: PDF baytlari."""
    ms = a['kind'] == 'ms'
    p = _Pdf(a['title'], f"Ustoz Pro • {'Milliy sertifikat testi' if ms else 'Oddiy test'} • kod {a['code']}")
    p.text(p.M, p.y, a['title'], 36, bold=True); p.y += 52
    p.text(p.M, p.y, f"{'Milliy sertifikat testi' if ms else 'Oddiy test'} • kod {a['code']} • " + datetime.now(timezone(timedelta(hours=5))).strftime('%d.%m.%Y') + (f' • {teacher_name}' if teacher_name else ''), 18, fill=p.MUTED); p.y += 46
    if a.get('empty'):
        p.para("Bu testni hali hech kim topshirmagan. Havolani ulashing, natijalar kelgach hisobot to'ladi."); return p.finish()
    s = a['summary']
    p.kpis([('Ishtirokchilar', a['n']), ("O'rtacha " + ('ball' if ms else '%'), s['mean']), ('Mediana', s['median']), ("O'tganlar", f"{s['pass_pct']}%")])
    p.h2('1. Toifa taqsimoti' if ms else '1. Baholar taqsimoti', a['note'] if len(a['note']) < 130 else '')
    if ms:
        col = lambda lab, v: {'A+': p.GREEN, 'A': p.GREEN, 'B+': '#3b9a6d', 'B': '#3b9a6d', 'C+': p.AMBER, 'C': p.AMBER, 'NC': p.RED}[lab]
        p.bars([(l['name'], l['n'], f"{l['n']}  ({l['pct']}%)") for l in a['levels']], col)
    else:
        col = lambda lab, v: {'5': p.GREEN, '4': '#3b9a6d', '3': p.AMBER, '2': p.RED}[lab]
        p.bars([(f"«{g['name']}»", g['n'], f"{g['n']}  ({g['pct']}%)") for g in a['grades']], lambda lab, v: col(lab[1:-1], v))
    if a['fans']:
        p.h2("2. Fanlar/mavzular bo'yicha o'rtacha", "Eng pastdan boshlab — avval shularni takrorlang."); p.bars([(f['name'], f['pct'], f"{f['pct']}%  ({f['items']} savol)") for f in a['fans']], lambda lab, v: p.pct_color(v), 100, 250)
    p.h2('3. Ball taqsimoti' if ms else '3. Foiz taqsimoti')
    e = a['hist']['edges']; labels = [f'{e[i]}-{e[i + 1]}' for i in range(len(e) - 1)] if ms else [f'{e[i]}-{e[i + 1]}' for i in range(len(e) - 1)]
    p.vbars(labels, a['hist']['counts'], p.GREEN)
    if a['advice']:
        p.h2('Ustoz uchun xulosa')
        for t in a['advice']: p.para('• ' + t, 20, indent=8)
    p.new_page()
    p.h2('4. Har savol bo\'yicha foiz', 'Yashil: 70% dan yuqori, sariq: 40–70%, qizil: 40% dan past.')
    p.grid(a['items'], 10); p.y += 16
    p.h2('5. Sust savollar — qayta o\'rgatish kerak')
    rows = []
    for w in a['weak']:
        wr = w.get('wrong'); rows.append(['#' + w['item'], f"{w['pct']}%", w['fan'] or '—', (f"{wr['option']} ({wr['share']}%)" if wr else '—'), ('—' if w.get('d') is None else w['d'])])
    if rows: p.table(['Savol', "To'g'ri", 'Fan/mavzu', "Ko'p tanlangan xato", 'Farqlash'], rows, [90, 100, 260, 230, 110], ['l', 'r', 'l', 'l', 'r'])
    else: p.para("Sust savollar yo'q — sinf yaxshi ishlagan.")
    p.h2('6. Kuchli savollar')
    p.table(['Savol', "To'g'ri", 'Fan/mavzu'], [['#' + w['item'], f"{w['pct']}%", w['fan'] or '—'] for w in a['strong']], [90, 100, 400], ['l', 'r', 'l'])
    if a['bad_disc']:
        p.h2('7. Yomon farqlovchi savollar', "Kuchli va kuchsiz o'quvchilar bir xil javob bergan: kalit yoki savol shartini tekshiring.")
        p.table(['Savol', "To'g'ri", 'Farqlash'], [['#' + b['item'], f"{b['pct']}%", b['d']] for b in a['bad_disc']], [90, 100, 100], ['l', 'r', 'r'])
    p.new_page(); p.h2('8. Ishtirokchilar jadvali')
    if ms:
        lvc = lambda v: {'NC': p.RED}.get(v)
        rows = [[x['rank'], x['name'], x['correct'], x['rasch'], ('—' if x['essay'] is None else x['essay']), x['final'], x['level']] for x in a['people']]
        p.table(['#', 'Ism', "To'g'ri", 'Rasch', 'Esse', 'Yakuniy', 'Daraja'], rows, [50, 330, 100, 100, 100, 110, 100], ['l', 'l', 'r', 'r', 'r', 'r', 'r'], color_cols={6: lvc})
    else:
        gc = lambda v: p.RED if str(v) == '2' else None
        rows = [[x['rank'], x['name'], f"{x['correct']}/{x['total']}", f"{x['pct']}%", x['grade']] for x in a['people']]
        p.table(['#', 'Ism', "To'g'ri", 'Foiz', 'Baho'], rows, [50, 380, 130, 120, 100], ['l', 'l', 'r', 'r', 'r'], color_cols={4: gc})
    if ms and prog:
        p.h2("9. O'quvchilar rivoji", "Sizning Milliy sertifikat testlaringiz bo'yicha (kamida 2 ta test).")
        p.table(['Ism', 'Testlar', 'Ball dinamikasi', 'Farq'], [[x['name'], x['n'], '  >  '.join(str(v) for v in x['scores'][-6:]), ('+' if x['delta'] > 0 else '') + str(x['delta'])] for x in prog],
                [220, 90, 520, 90], ['l', 'r', 'l', 'r'], color_cols={3: lambda v: p.RED if str(v).startswith('-') else p.GREEN})
    return p.finish()
