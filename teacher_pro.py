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
_ASCII_ONLY = False   # v71: TTF shrift topilmasa True bo'ladi (— • kabi belgilar ASCII ga almashtiriladi, □ chiqmaydi)
LEVEL_BANDS = [('NC', 0, 46), ('C', 46, 50), ('C+', 50, 55), ('B', 55, 60), ('B+', 60, 65), ('A', 65, 70), ('A+', 70, 75.0001)]


def level_bands():
    return [{'level': n, 'from': a, 'to': min(b, 75)} for n, a, b in LEVEL_BANDS]


def next_level(score):
    """Keyingi daraja: {'level','at','need'} yoki None (eng yuqori darajada)."""
    for n, a, b in LEVEL_BANDS:
        if a <= float(score) < b:
            if n == 'A+': return None
            i = [x[0] for x in LEVEL_BANDS].index(n); nn, na, _ = LEVEL_BANDS[i + 1]
            return {'level': nn, 'at': na, 'need': round(na - float(score), 1)}
    return None


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


def _pearson(xs, ys):
    n = len(xs)
    if n < 4: return None
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx < 1e-9 or sy < 1e-9: return None
    return round(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sx * sy), 2)


GROUPS = [('A', 'A+/A'), ('B', 'B+/B'), ('C', 'C+/C'), ('NC', 'NC')]
_GRP = {'A+': 'A', 'A': 'A', 'B+': 'B', 'B': 'B', 'C+': 'C', 'C': 'C', 'NC': 'NC'}


def _mock_insights(items, qs, vec, ans, essay, tT, final, lvl, fm, item_pct, D, N):
    """v71: Mock natijalarining chuqur tahlili: ishonchlilik (KR-20), chegaraga yaqinlar, mavzu x daraja, esse-test farqi,
    shubhali kalitlar, xulosa va ustozga amaliy qadamlar. Hammasi JSON-xavfsiz."""
    out = {}; heads = []; acts = []
    num = lambda i: int(re.match(r'\d+', i).group())
    # --- 1. ishonchlilik (KR-20) va o'lchov xatosi
    used = [i for i in items if 0 < sum(1 for v in vec.values() if i in v) < N]
    rel = None
    if N >= 8 and len(used) >= 5:
        tot = [sum(1 for i in used if i in v) for v in vec.values()]
        try: var = statistics.variance(tot)
        except Exception: var = 0
        if var > 1e-9:
            pq = sum((item_pct[i][0] / 100) * (1 - item_pct[i][0] / 100) for i in used); k = len(used)
            a = max(-1.0, min(1.0, round(k / (k - 1) * (1 - pq / var), 2)))
            rel = {'alpha': a, 'sem': round(math.sqrt(var) * math.sqrt(max(0, 1 - a)), 1), 'k': k, 'n': N,
                   'label': 'yuqori' if a >= 0.8 else ('qoniqarli' if a >= 0.7 else ('past' if a >= 0.5 else 'juda past')), 'small_n': N < 15}
    out['reliability'] = rel
    if rel:
        heads.append(f"Test ishonchliligi (KR-20) = {rel['alpha']} ({rel['label']}); o'lchov xatosi ±{rel['sem']} ta savol." + (' Ishtirokchilar kam (<15), natija taxminiy.' if rel['small_n'] else ''))
        if rel['alpha'] < 0.7: acts.append("Ishonchlilik past: shubhali va farqlamaydigan savollarni almashtiring yoki kalitlarini tekshiring.")
    # --- 2. sertifikat chegarasi (46) va keyingi darajaga yaqinlar
    pass_n = sum(1 for v in final.values() if v >= 46)
    near = []
    for u, v in final.items():
        nl = next_level(v)
        if nl and nl['need'] <= 3 and lvl[u] != 'A+':
            near.append({'name': _short_name(u), 'final': v, 'level': lvl[u], 'next': nl['level'], 'need': nl['need']})
    near.sort(key=lambda x: x['need'])
    cert_edge = [x for x in near if x['next'] == 'C']
    out['cert'] = {'pass_n': pass_n, 'fail_n': N - pass_n, 'pass_pct': round(100 * pass_n / N), 'edge': cert_edge[:12], 'near_next': near[:12]}
    if cert_edge:
        heads.append(f"{len(cert_edge)} ta talabgor sertifikat chegarasidan (46 ball) 3 ball ichida pastda: ular bilan alohida ishlasangiz, o'tish soni oshadi.")
        acts.append("Chegaraga yaqin talabgorlarga (ro'yxat pastda) eng zaif mavzu bo'yicha qisqa qo'shimcha mashq bering.")
    # --- 3. mavzu x daraja kesimi
    fl = []
    members = {g: [u for u in vec if _GRP[lvl[u]] == g] for g, _ in GROUPS}
    order = sorted(final, key=lambda u: -final[u]); half = max(1, N // 2); upper, lower = order[:half], order[-half:]
    for name, nums in fm.items():
        its = [i for i in items if num(i) in nums]
        if not its: continue
        pc = lambda us: (round(100 * statistics.mean(sum(1 for i in its if i in vec[u]) / len(its) for u in us)) if us else None)
        row = {'name': name, 'items': len(its), 'groups': {g: pc(members[g]) for g, _ in GROUPS}, 'upper': pc(upper), 'lower': pc(lower), 'all': pc(list(vec))}
        row['gap'] = (row['upper'] - row['lower']) if row['upper'] is not None and row['lower'] is not None else None
        fl.append(row)
    fl.sort(key=lambda r: (r['all'] if r['all'] is not None else 999))
    out['fan_levels'] = {'groups': [lb for _, lb in GROUPS], 'keys': [g for g, _ in GROUPS], 'rows': fl, 'counts': {g: len(members[g]) for g, _ in GROUPS}}
    if fl:
        w = fl[0]; heads.append(f"Eng zaif mavzu: {w['name']} ({w['all']}%).")
        acts.append(f"«{w['name']}» mavzusini keyingi darsda qayta tushuntiring.")
        gp = [r for r in fl if r['gap'] is not None]
        if gp:
            b = max(gp, key=lambda r: r['gap']); heads.append(f"Eng ajratuvchi mavzu: {b['name']} (yuqori yarim {b['upper']}%, quyi yarim {b['lower']}%): kuchli va kuchsizlar aynan shu yerda ajraladi.")
    # --- 4. esse va test
    es_pairs = [(tT[u], nc.essay_to_75(essay[u])) for u in vec if essay[u] is not None]
    gap = []
    for u in vec:
        if essay[u] is None: continue
        e75 = nc.essay_to_75(essay[u]); d = round(e75 - tT[u], 1)
        if abs(d) >= 12: gap.append({'name': _short_name(u), 'test': tT[u], 'essay': e75, 'diff': d})
    gap.sort(key=lambda x: -abs(x['diff']))
    missing = [_short_name(u) for u in vec if essay[u] is None]
    out['essay'] = {'with': len(es_pairs), 'missing': len(missing), 'missing_names': missing[:12], 'corr': _pearson([a for a, _ in es_pairs], [b for _, b in es_pairs]),
                    'mean_test': (round(statistics.mean(a for a, _ in es_pairs), 1) if es_pairs else None), 'mean_essay': (round(statistics.mean(b for _, b in es_pairs), 1) if es_pairs else None), 'gap': gap[:8]}
    ee = out['essay']
    if ee['with'] and ee['mean_test'] is not None and ee['mean_essay'] is not None:
        d = round(ee['mean_essay'] - ee['mean_test'], 1)
        if abs(d) >= 5:
            heads.append(f"Esse o'rtacha ball ({ee['mean_essay']}) testdan ({ee['mean_test']}) {'yuqori' if d > 0 else 'past'}: farq {abs(d)} ball.")
            if d < 0: acts.append("Esse testdan past: esse yozish (mezonlar, hajm, tuzilma) bo'yicha alohida mashg'ulot kerak.")
    if ee['missing']: acts.append(f"{ee['missing']} ta talabgorda esse hali yo'q: yakuniy ball esse kelgach o'zgaradi.")
    if gap: acts.append(f"{len(gap)} ta talabgorda esse va test o'rtasida katta farq bor: esse yoki testni qayta ko'rib chiqing.")
    # --- 5. shubhali savollar (kalit, qiyin/oson, farqlamaydigan)
    flags = []
    up_n = max(3, round(0.27 * N)); up_set = set(order[:up_n]); up_n = len(up_set)
    for i in items:
        pct = item_pct[i][0]; d = D.get(i); reasons = []
        m = re.match(r'(\d+)([ab]?)$', i); q = qs[int(m.group(1)) - 1] if m and 0 < int(m.group(1)) <= len(qs) else {}
        top = None
        if q.get('type', 'Y1') in ('Y1', 'Y2') and q.get('answer'):
            cnt, ucnt, ucor = {}, {}, 0; corr = str(q['answer']).strip().upper()
            for u, a in ans.items():
                x = str(a.get(str(num(i)), '')).strip().upper()
                if x and x != corr: cnt[x] = cnt.get(x, 0) + 1
                if u in up_set:
                    if x and x != corr: ucnt[x] = ucnt.get(x, 0) + 1
                    elif x == corr: ucor += 1
            if cnt:
                o, c = max(cnt.items(), key=lambda kv: kv[1]); top = {'option': o, 'share': round(100 * c / N), 'correct': corr}
                if ucnt and up_n >= 5:
                    uo, uc = max(ucnt.items(), key=lambda kv: kv[1]); top['upper_option'] = uo; top['upper_share'] = round(100 * uc / up_n); top['upper_correct'] = round(100 * ucor / up_n)
        # kalit shubhali: kuchli (yuqori 27%) guruhning o'zi ko'pchilik bo'lib boshqa variantni tanlagan
        suspect = bool(top and top.get('upper_share') is not None and top['upper_share'] >= 60 and top['upper_share'] > top['upper_correct'])
        if suspect: reasons.append(f"kalit shubhali: kuchli talabgorlarning {top['upper_share']}% i {top['upper_option']} ni tanlagan, to'g'ri javobni {top['upper_correct']}%")
        if d is not None and d < 0: reasons.append(f"teskari farqlash ({d})")
        elif d is not None and d < 0.1 and 15 <= pct <= 90: reasons.append(f"farqlamaydi ({d})")
        if pct < 15: reasons.append('juda qiyin (<15%)')
        elif pct > 92: reasons.append('juda oson (>92%)')
        if reasons: flags.append({'item': i, 'pct': round(pct, 1), 'd': d, 'reasons': reasons, 'key': suspect, 'top_wrong': top})
    flags.sort(key=lambda f: (not f['key'], -len(f['reasons']), f['pct']))
    out['flags'] = flags[:15]; ks = [f for f in flags if f['key']]
    out['flag_counts'] = {'key': len(ks), 'hard': sum(1 for f in flags if f['pct'] < 15), 'easy': sum(1 for f in flags if f['pct'] > 92), 'flat': sum(1 for f in flags if f['d'] is not None and f['d'] < 0.1)}
    if ks:
        heads.append(f"{len(ks)} ta savolning kaliti shubhali: " + ', '.join('#' + f['item'] for f in ks[:6]) + '.')
        acts.append("Shubhali kalitli savollarni tekshiring: noto'g'ri bo'lsa, bu savollar natijani buzgan bo'lishi mumkin.")
    out['headlines'] = heads[:6]; out['actions'] = acts[:6]
    return out


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
            'weak': weak_rows, 'strong': strong_rows, 'bad_disc': bad_disc, 'people': people, 'advice': advice, 'essay_stats': essay_stats,
            'insights': _safe_insights(items, qs, vec, ans, essay, tT, final, lvl, fm, item_pct, D, N)}


def _safe_insights(*a):
    try: return _mock_insights(*a)
    except Exception:
        import logging; logging.getLogger(__name__).exception('mock insights'); return None


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
    if _ASCII_ONLY:
        for a, b in (('—', '-'), ('–', '-'), ('•', '-'), ('−', '-'), ('…', '...'), ('→', '>'), ('≥', '>='), ('«', '"'), ('»', '"')): s = s.replace(a, b)
    out = []
    for ch in s:
        low = ch.lower()
        if low in _CYR:
            t = _CYR[low]; out.append(t.capitalize() if ch != low and t else t)
        elif ord(ch) < (0x80 if _ASCII_ONLY else 0x250) or (not _ASCII_ONLY and ch in '–—•−…→≥«»'):
            out.append(ch)
    return ''.join(out).strip()


class _Pdf:
    W, H, M = 1240, 1754, 70
    GREEN, GOLD, RED, AMBER, INK, MUTED, LINE, SOFT = '#0b6e4f', '#b8902f', '#c0392b', '#d9a21b', '#1d2b27', '#6b7a75', '#dfe6e3', '#f2f6f4'

    def __init__(self, title, subtitle, header='SINF HISOBOTI'):
        from PIL import Image, ImageDraw, ImageFont
        self.Image, self.ImageDraw, self.ImageFont = Image, ImageDraw, ImageFont
        self.title, self.subtitle, self.header = title, subtitle, header
        self.pages = []; self._fonts = {}; self.new_page()

    def f(self, size, bold=False):
        k = (size, bold)
        global _ASCII_ONLY
        if k not in self._fonts:
            names = (['Poppins-Bold.ttf', 'DejaVuSans-Bold.ttf', 'LiberationSans-Bold.ttf'] if bold else ['Poppins-Regular.ttf', 'DejaVuSans.ttf', 'LiberationSans-Regular.ttf'])
            dirs = [FONT_DIR, '/usr/share/fonts/truetype/dejavu', '/usr/share/fonts/truetype/liberation2', '/usr/share/fonts/truetype/liberation', '/usr/share/fonts/dejavu']
            f = None
            for nm in names:
                for d in dirs:
                    try: f = self.ImageFont.truetype(os.path.join(d, nm), size); break
                    except Exception: continue
                if f: break
            if f is None:
                _ASCII_ONLY = True
                try: f = self.ImageFont.load_default(size)
                except Exception: f = self.ImageFont.load_default()
            self._fonts[k] = f
        return self._fonts[k]

    def new_page(self):
        im = self.Image.new('RGB', (self.W, self.H), 'white'); self.pages.append(im); self.d = self.ImageDraw.Draw(im); self.y = self.M
        self.d.rectangle([0, 0, self.W, 14], fill=self.GREEN)
        self.text(self.M, 34, self.header, 22, bold=True, fill=self.GREEN)
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

    def h2(self, s, sub='', keep=0):
        self.need(80 + keep); self.text(self.M, self.y, s, 30, bold=True); self.y += 42
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
        self.need(row_h * 5); draw_head()
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
    p.need(560)
    p.h2('4. Har savol bo\'yicha foiz', 'Yashil: 70% dan yuqori, sariq: 40–70%, qizil: 40% dan past.', keep=420)
    p.grid(a['items'], 10); p.y += 16
    p.h2('5. Sust savollar — qayta o\'rgatish kerak', keep=200)
    rows = []
    for w in a['weak']:
        wr = w.get('wrong'); rows.append(['#' + w['item'], f"{w['pct']}%", w['fan'] or '—', (f"{wr['option']} ({wr['share']}%)" if wr else '—'), ('—' if w.get('d') is None else w['d'])])
    if rows: p.table(['Savol', "To'g'ri", 'Fan/mavzu', "Ko'p tanlangan xato", 'Farqlash'], rows, [90, 100, 260, 230, 110], ['l', 'r', 'l', 'l', 'r'])
    else: p.para("Sust savollar yo'q — sinf yaxshi ishlagan.")
    p.h2('6. Kuchli savollar', keep=200)
    p.table(['Savol', "To'g'ri", 'Fan/mavzu'], [['#' + w['item'], f"{w['pct']}%", w['fan'] or '—'] for w in a['strong']], [90, 100, 400], ['l', 'r', 'l'])
    if a['bad_disc']:
        p.h2('7. Yomon farqlovchi savollar', "Kuchli va kuchsiz o'quvchilar bir xil javob bergan: kalit yoki savol shartini tekshiring.")
        p.table(['Savol', "To'g'ri", 'Farqlash'], [['#' + b['item'], f"{b['pct']}%", b['d']] for b in a['bad_disc']], [90, 100, 100], ['l', 'r', 'r'])
    ins = a.get('insights') if ms else None
    if ins:
        p.need(300); p.h2('Chuqur tahlil', 'Ishonchlilik, sertifikat chegarasi, mavzu va daraja kesimi, shubhali savollar.', keep=200)
        for t in ins.get('headlines') or []: p.para('- ' + t, 19, indent=8)
        if ins.get('actions'):
            p.h2('Ustoz uchun amaliy qadamlar', keep=100)
            for i, t in enumerate(ins['actions'], 1): p.para(f'{i}. ' + t, 19, indent=8)
        fl = ins.get('fan_levels') or {}
        if fl.get('rows'):
            p.h2('Mavzu va daraja kesimi', "Har daraja guruhi shu mavzuda necha foiz to'g'ri yechgan. Farq = yuqori yarim - quyi yarim.", keep=200)
            p.table(['Mavzu'] + fl['groups'] + ['Farq'], [[r['name']] + [('-' if r['groups'][k] is None else f"{r['groups'][k]}%") for k in fl['keys']] + [('-' if r['gap'] is None else f"+{r['gap']}")] for r in fl['rows']],
                    [300, 100, 100, 100, 100, 100], ['l', 'r', 'r', 'r', 'r', 'r'])
        ct = ins.get('cert') or {}
        if ct.get('edge'):
            p.h2("Sertifikat chegarasiga yaqinlar (46 ball)", f"O'tganlar: {ct['pass_n']} ({ct['pass_pct']}%), o'tmaganlar: {ct['fail_n']}.", keep=200)
            p.table(['Ism', 'Ball', 'Daraja', 'Yetishmaydi'], [[x['name'] if safe_text(x['name']) else '-', x['final'], x['level'], x['need']] for x in ct['edge']], [320, 110, 110, 160], ['l', 'r', 'r', 'r'])
        es = ins.get('essay') or {}
        if es.get('with'):
            p.h2('Esse va test', f"Test o'rtachasi {es.get('mean_test')}, esse o'rtachasi {es.get('mean_essay')}" + (f", bog'liqlik r = {es['corr']}" if es.get('corr') is not None else '') + '.', keep=60)
            if es.get('gap'): p.table(['Ism', 'Test', 'Esse', 'Farq'], [[x['name'] if safe_text(x['name']) else '-', x['test'], x['essay'], x['diff']] for x in es['gap']], [320, 120, 120, 120], ['l', 'r', 'r', 'r'])
        if ins.get('flags'):
            fc = ins.get('flag_counts') or {}
            p.h2('Tekshirish kerak bo\'lgan savollar', f"Kalit shubhali: {fc.get('key', 0)}, juda qiyin: {fc.get('hard', 0)}, juda oson: {fc.get('easy', 0)}, farqlamaydi: {fc.get('flat', 0)}.", keep=200)
            p.table(['Savol', "To'g'ri", 'Sabab'], [['#' + f['item'], f"{f['pct']}%", '; '.join(f['reasons'])[:70]] for f in ins['flags']], [90, 110, 640], ['l', 'r', 'l'])
    p.need(420); p.h2('8. Ishtirokchilar jadvali', keep=180)
    if ms:
        lvc = lambda v: {'NC': p.RED}.get(v)
        rows = [[x['rank'], (x['name'] if safe_text(x['name']) else f"Ishtirokchi {x['rank']}"), x['correct'], x['rasch'], ('—' if x['essay'] is None else x['essay']), x['final'], x['level']] for x in a['people']]
        p.table(['#', 'Ism', "To'g'ri", 'Rasch', 'Esse', 'Yakuniy', 'Daraja'], rows, [50, 330, 100, 100, 100, 110, 100], ['l', 'l', 'r', 'r', 'r', 'r', 'r'], color_cols={6: lvc})
    else:
        gc = lambda v: p.RED if str(v) == '2' else None
        rows = [[x['rank'], (x['name'] if safe_text(x['name']) else f"Ishtirokchi {x['rank']}"), f"{x['correct']}/{x['total']}", f"{x['pct']}%", x['grade']] for x in a['people']]
        p.table(['#', 'Ism', "To'g'ri", 'Foiz', 'Baho'], rows, [50, 380, 130, 120, 100], ['l', 'l', 'r', 'r', 'r'], color_cols={4: gc})
    if ms and prog:
        p.h2("9. O'quvchilar rivoji", "Sizning Milliy sertifikat testlaringiz bo'yicha (kamida 2 ta test).")
        p.table(['Ism', 'Testlar', 'Ball dinamikasi', 'Farq'], [[x['name'], x['n'], '  >  '.join(str(v) for v in x['scores'][-6:]), ('+' if x['delta'] > 0 else '') + str(x['delta'])] for x in prog],
                [220, 90, 520, 90], ['l', 'r', 'l', 'r'], color_cols={3: lambda v: p.RED if str(v).startswith('-') else p.GREEN})
    return p.finish()


# ------------------------------------------------------------------ v71: MOCK — talabgorning shaxsiy natija hisoboti (PDF)
def _pdf_scale(p, score):
    """Daraja shkalasi (NC ... A+) va talabgor o'rni."""
    p.need(150); n = len(LEVEL_BANDS); w = (p.W - 2 * p.M) / n; y = p.y + 34
    cols = {'NC': p.RED, 'C': p.AMBER, 'C+': p.AMBER, 'B': '#5fb88a', 'B+': '#3a9a6b', 'A': '#1f8a5b', 'A+': '#0e6e4a'}
    mark = None
    for i, (nm, a, b) in enumerate(LEVEL_BANDS):
        x0 = p.M + i * w
        p.d.rectangle([x0 + 2, y, x0 + w - 2, y + 26], fill=cols[nm])
        p.text(x0 + w / 2, y + 36, nm, 20, bold=True, anchor='ma')
        p.text(x0 + 4, y + 66, str(a), 14, fill=p.MUTED)
        if a <= float(score) < b: mark = x0 + w * (float(score) - a) / (min(b, 75) - a)
    if mark is None: mark = p.W - p.M - 4 if float(score) >= 75 else p.M + 4
    p.d.polygon([(mark, y - 4), (mark - 12, y - 24), (mark + 12, y - 24)], fill=p.GOLD)
    p.text(mark, y - 52, f'{score}', 22, bold=True, fill=p.GOLD, anchor='ma')
    p.y = y + 96


def _pdf_line(p, labels, values):
    """Mocklar bo'yicha ball dinamikasi chizig'i."""
    p.need(300); h = 190; x0, x1 = p.M + 40, p.W - p.M - 40; base = p.y + h + 20
    lo, hi = min(values + [40]), max(values + [60]); span = max(hi - lo, 1)
    pts = []
    for i, v in enumerate(values):
        x = x0 + (x1 - x0) * (i / max(len(values) - 1, 1)); y = base - (h * (v - lo) / span); pts.append((x, y))
    p.d.line([p.M, base, p.W - p.M, base], fill=p.LINE, width=2)
    if len(pts) > 1: p.d.line(pts, fill=p.GREEN, width=5)
    for (x, y), v, lb in zip(pts, values, labels):
        p.d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=p.GOLD)
        p.text(x, y - 38, f'{v}', 20, bold=True, anchor='ma'); p.text(x, base + 10, p.fit(lb, 15, 160), 15, fill=p.MUTED, anchor='ma')
    p.y = base + 50


def build_mock_personal_pdf(snap, history=None, name=''):
    """snap — mock_published_results snapshot (class_stats, fan_report, priority, next_level bilan). Qaytaradi: PDF baytlari."""
    history = history or []
    final = snap.get('combined_score_75'); lvl = snap.get('level') or '-'
    p = _Pdf(snap.get('title', 'Mock'), f"Mock natijasi • kod {snap.get('code', '')}", header='MOCK NATIJASI')
    p.text(p.M, p.y, snap.get('title', 'Mock'), 36, bold=True); p.y += 52
    p.text(p.M, p.y, (name + ' • ' if safe_text(name) else '') + datetime.now(timezone(timedelta(hours=5))).strftime('%d.%m.%Y'), 18, fill=p.MUTED); p.y += 44
    cs = snap.get('class_stats') or {}
    p.kpis([('Yakuniy ball', f'{final}/75'), ('Daraja', lvl), ("Sinfdagi o'rin", f"{snap.get('place', '-')}/{snap.get('total', '-')}"), ("Sinf o'rtachasi", cs.get('mean', '-'))])
    p.h2('1. Daraja shkalasi', keep=140)
    _pdf_scale(p, final)
    nl = snap.get('next_level')
    p.para(f"{nl['level']} darajaga yana {nl['need']} ball yetishmaydi ({nl['at']} ball kerak)." if nl else 'Siz eng yuqori darajadasiz. Natijani saqlab qoling.', 20)
    if cs.get('n'): p.para(f"Siz ishtirokchilarning {cs.get('percentile', 0)}% idan yuqori natija ko'rsatdingiz. Eng yaxshi ball: {cs.get('best', '-')}.", 19, fill=p.MUTED)
    p.h2('2. Test va esse', keep=160)
    es = snap.get('essay_score')
    p.table(['Qism', 'Natija', '75 ballik'], [['Test (Rasch)', f"{snap.get('raw_score')}/{snap.get('max_score')} to'g'ri", snap.get('score_75')],
            ['Esse', (f'{es}/24' if es is not None else 'tekshirilmagan'), (snap.get('essay_75') if es is not None else '-')], ['Yakuniy (test + esse) / 2', '', final]],
            [300, 260, 160], ['l', 'r', 'r'])
    fr = snap.get('fan_report') or []
    if fr:
        p.h2("3. Mavzular bo'yicha", "Qavs ichida sinf o'rtachasi. Eng pastdan boshlab takrorlang.", keep=200)
        rows = sorted(fr, key=lambda f: f['correct_pct'])
        p.bars([(f['name'], f['correct_pct'], f"{f['correct_pct']}%" + (f"  (sinf: {int(round(f['class_pct']))}%)" if f.get('class_pct') is not None else '')) for f in rows], lambda lab, v: p.pct_color(v), 100, label_w=330)
    pr = snap.get('priority') or []
    if pr:
        p.h2("4. Avval shularni qayta o'rganing", "Sinf ko'pchiligi topgan, siz xato qilgan savollar eng muhim.", keep=200)
        p.table(['Savol', 'Mavzu', 'Sinfda topganlar'], [['#' + str(x['item']), x['fan'], ('-' if x.get('class_pct') is None else f"{int(round(x['class_pct']))}%")] for x in pr], [100, 420, 200], ['l', 'l', 'r'])
    if len(history) >= 2:
        p.h2('5. Mocklar dinamikasi', keep=320)
        _pdf_line(p, [h['title'] for h in history[-6:]], [float(h['score']) for h in history[-6:]])
        d = round(float(history[-1]['score']) - float(history[-2]['score']), 1)
        p.para(f"Oldingi mockka nisbatan: {'+' if d > 0 else ''}{d} ball.", 20)
    er = snap.get('errors') or []
    if er:
        p.h2(f'6. Xatolar tafsiloti ({len(er)} ta)', keep=200)
        p.table(['Savol', 'Sizning javob', "To'g'ri javob"], [[str(x.get('number')), str(x.get('user_text') if x.get('user_text') is not None else x.get('user')), str(x.get('correct_text') if x.get('correct_text') is not None else x.get('correct'))] for x in er[:60]], [90, 330, 330], ['l', 'l', 'l'])
    p.h2('Keyingi mockgacha reja', keep=160)
    plan = []
    if fr and any(f['wrong'] for f in fr):
        w = sorted([f for f in fr if f['wrong']], key=lambda f: f['correct_pct'])[0]; plan.append(f"{w['name']} mavzusini takrorlang ({w['correct_pct']}% to'g'ri).")
    if pr: plan.append("Xato qilingan oson savollar: " + ', '.join('#' + str(x['item']) for x in pr[:5]) + ' ni qayta yeching.')
    if nl: plan.append(f"Maqsad: {nl['level']} daraja uchun {nl['at']} ball.")
    if es is None: plan.append('Esse tekshiruvini oling, yakuniy ballga 50% hissa qo\'shadi.')
    for t in plan or ['Natijani saqlab qolish uchun mashqni davom ettiring.']: p.para('- ' + t, 20, indent=8)
    return p.finish()


def build_mock_admin_pdf(title, code, rows, qstats, status='', stamp=''):
    """v79 NAMUNA: mock natijalari bo'yicha admin/ustoz hisoboti.
    rows: [{'name','tg','raw','max','pct','final','level','wrong'}], qstats: [(savol_no, xato_soni, xato_foiz)]."""
    import unicodedata
    for r in rows:   # chiroyli (matematik) shriftdagi ismlarni oddiy harfga o'tkazamiz; ism o'qilmasa - telegram
        nm = safe_text(unicodedata.normalize('NFKC', str(r.get('name') or ''))).strip()
        r['name'] = nm if nm.strip(" -'") else (r.get('tg') or '-')
    n = len(rows)
    p = _Pdf(title, f'Mock natijalari - kod {code}', header='MOCK HISOBOTI')
    p.text(p.M, p.y, title, 36, bold=True); p.y += 52
    p.text(p.M, p.y, f"Kod: {code}" + (f"  •  {status}" if status else '') + (f"  •  {stamp}" if stamp else ''), 18, fill=p.MUTED); p.y += 44
    finals = [float(r['final']) for r in rows if r.get('final') is not None]
    mean = round(sum(finals) / len(finals), 1) if finals else 0
    best = max(finals) if finals else 0
    CERT = ('B+', 'A', 'A+')   # mockda sertifikat faqat shu darajalarga
    passed = sum(1 for r in rows if r['level'] in CERT)
    p.kpis([('Ishtirokchilar', n), ("O'rtacha ball /75", mean), ('Eng yuqori ball', best), ('Sertifikat (B+ va yuqori)', f"{passed} ({round(passed * 100 / n) if n else 0}%)")])
    lv_order = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'Sertifikat berilmadi']
    cnt = {k: 0 for k in lv_order}
    for r in rows: cnt[r['level'] if r['level'] in cnt else 'Sertifikat berilmadi'] += 1
    p.h2('1. Darajalar taqsimoti', "Har bir daraja bo'yicha ishtirokchilar soni.", keep=330)
    p.vbars(['A+', 'A', 'B+', 'B', 'C+', 'C', 'Yo‘q'], [cnt[k] for k in lv_order], p.GREEN)
    top = sorted(rows, key=lambda r: -float(r.get('final') or 0))
    p.h2('2. Reyting - eng yaxshi 10 ta', keep=300)
    medal = {0: '1', 1: '2', 2: '3'}
    p.table(['#', 'Ishtirokchi', 'Test', '%', 'Umumiy /75', 'Daraja'],
            [[medal.get(i, str(i + 1)), r['name'], f"{r['raw']}/{r['max']}", f"{int(round(r['pct']))}%", r['final'], r['level'].replace('Sertifikat berilmadi', '-')] for i, r in enumerate(top[:10])],
            [60, 380, 140, 100, 160, 140], ['l', 'l', 'r', 'r', 'r', 'r'],
            color_cols={3: lambda v: p.pct_color(float(str(v).rstrip('%') or 0))})
    p.h2('3. Savollar xaritasi', "To'g'ri topganlar foizi: yashil - yaxshi, sariq - o'rta, qizil - qiyin.", keep=240)
    items = [{'item': str(q[0]), 'pct': 100 - float(q[2])} for q in qstats if q[1] is not None]
    p.grid(items, per_row=10); p.y += 24
    hard = sorted(qstats, key=lambda q: -float(q[2]))[:8]
    p.h2('4. Eng qiyin 8 ta savol', 'Darsda birinchi navbatda shularni tahlil qiling.', keep=360)
    p.bars([(f'#{q[0]}', float(q[2]), f'{int(round(float(q[2])))}% xato ({q[1]} kishi)') for q in hard], lambda lab, v: p.RED if v >= 60 else p.AMBER, maxv=100, label_w=110)
    easy = sorted([q for q in qstats if q[1] is not None], key=lambda q: float(q[2]))[:5]
    p.h2('5. Xulosa va tavsiyalar', keep=240)
    low = [r for r in rows if r['level'] not in CERT]
    p.para(f"• Ishtirokchilarning {round(passed * 100 / n) if n else 0}% i sertifikat darajasiga (B+ va yuqori) yetdi, o'rtacha ball {mean}/75.", 20)
    p.para(f"• Eng qiyin savollar: {', '.join('#' + str(q[0]) for q in hard[:5])}. Ularni sinfda alohida tushuntiring.", 20)
    if easy: p.para(f"• Eng yaxshi o'zlashtirilgan: {', '.join('#' + str(q[0]) for q in easy[:3])}.", 20)
    if low: p.para(f"• {len(low)} ta ishtirokchi B+ chegarasidan past (sertifikat berilmaydi). Ularga shaxsiy takrorlash rejasini bering.", 20)
    p.para("• Esse balli test balli bilan birga hisoblanadi - esse tekshiruvini o'tkazib yubormang.", 20, fill=p.MUTED)
    return p.finish()
