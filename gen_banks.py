# -*- coding: utf-8 -*-
"""Savol banklarini YASAYDI (oflayn). Ishlatish: python3 tools/gen_banks.py
Kirish: tools/lug_parsed.json (parse_lug.py), miniapp/{paronim,omonim,sinonim,dictionary,active1000}.json, tools/mumtoz_q.json
Chiqish: miniapp/leks_omonim.json, leks_sinonim.json, leks_paronim.json, imlo_bank.json, mumtoz_bank.json
Savol formati dtm_bank.json bilan bir xil: {t:'mc', c, d, q, o:[TO'G'RI, x, y, z], a:0, e, id}  (ilova variantlarni aralashtiradi)."""
import json, re, random, os, itertools, collections
random.seed(50)
HERE = os.path.dirname(os.path.abspath(__file__)); APP = os.path.join(HERE, '..', 'miniapp')
J = lambda p: json.load(open(p, encoding='utf-8'))
def norm(w): return re.sub(r'[`\'ʻʼ’]', '‘', w.strip().lower())
def clean_word(w): return bool(re.match(r'^[a-z‘’]+$', w))
def lev(a, b):
    if abs(len(a) - len(b)) > 3: return 9
    p = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        c = [i]
        for j, cb in enumerate(b, 1): c.append(min(p[j] + 1, c[j - 1] + 1, p[j - 1] + (ca != cb)))
        p = c
    return p[-1]
def lcp(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y: break
        n += 1
    return n
def cut(s, n=70):
    s = re.sub(r'\s+', ' ', s).strip(' ;.,')
    if len(s) <= n: return s
    s = s[:n].rsplit(' ', 1)[0].rstrip(' ,;')
    return s + '…'
def Q(cat, d, q, correct, wrong, exp, qid, fix=False):
    o = [correct] + list(wrong)
    if len(set(o)) != len(o) or len(o) < 4: return None
    x = {'t': 'mc', 'c': cat, 'd': d, 'q': q, 'o': o, 'a': 0, 'e': exp, 'id': qid}
    if fix: x['fix'] = 1
    return x
def fixap(t): return re.sub(r'(?<![ogOG])‘', '’', t)
def save(name, arr):
    for x in arr:
        x['q'] = fixap(x['q']); x['e'] = fixap(x['e']); x['o'] = [fixap(o) for o in x['o']]
    json.dump(arr, open(os.path.join(APP, name), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(name, len(arr), os.path.getsize(os.path.join(APP, name)) // 1024, 'KB')

LUG = J(os.path.join(HERE, 'lug_parsed.json'))
DICT = {norm(w) for w in J(os.path.join(APP, 'dictionary.json')) if isinstance(w, str)}
POSORDER = ['ot', 'fe’l', 'sifat', 'ravish', 'son', 'olmosh', 'undov', 'yuklama', 'taqlid']
def poslabel(ps):
    ps = [p for p in POSORDER if p in ps]
    return ps[0] if len(ps) == 1 else (', '.join(ps[:-1]) + ' va ' + ps[-1])

# ============================================================= OMONIM
def gen_omonim():
    out = []; nid = 10001
    E = []
    for e in LUG['omo']:
        w = norm(e['w'])
        if not clean_word(w) or len(w) < 2: continue
        ss = [s for s in e['s'] if s['m'] or s['p']]
        if len(ss) < 2: continue
        E.append({'w': w, 's': ss, 'tag': all(s['p'] for s in ss)})
    tagged = [e for e in E if e['tag']]
    # a) so'z turkumlari
    combos = collections.Counter(poslabel({s['p'] for s in e['s']}) for e in tagged if len({s['p'] for s in e['s']}) >= 2)
    pool_lab = [l for l, _ in combos.most_common(8)]
    A = [e for e in tagged if len({s['p'] for s in e['s']}) >= 2]; random.shuffle(A)
    for e in A[:170]:
        lab = poslabel({s['p'] for s in e['s']})
        wr = [l for l in pool_lab if l != lab]; random.shuffle(wr)
        if len(wr) < 3: continue
        ex = '; '.join('%d) %s — %s' % (i, s['p'], cut(s['m'], 40) or '…') for i, s in enumerate(e['s'][:3], 1))
        out.append(Q('leks', 2, '«%s» omonimi qaysi so‘z turkumlariga oid ma’nolarga ega?' % e['w'], lab, wr[:3],
                     '«%s» lug‘atda quyidagicha berilgan: %s.' % (e['w'], ex), nid)); nid += 1
    # b) ma'no
    pm = collections.defaultdict(list)
    for e in tagged:
        for s in e['s']:
            m = cut(s['m'], 55)
            if 6 <= len(m) <= 55 and e['w'] not in m.lower(): pm[s['p']].append((e['w'], '%s — %s' % (s['p'], m)))
    B = list(tagged); random.shuffle(B); nb = 0
    for e in B:
        if nb >= 150: break
        s = random.choice([s for s in e['s'] if s['p'] in ('ot', 'fe’l', 'sifat') and 6 <= len(cut(s['m'], 55)) <= 55] or [None])
        if not s: continue
        m = '%s — %s' % (s['p'], cut(s['m'], 55)); cands = [x for w2, x in pm[s['p']] if w2 != e['w']]
        if len(cands) < 3: continue
        wr = random.sample(cands, 3)
        out.append(Q('leks', 1, '«%s» omonimining ma’nolaridan qaysi biri lug‘atda to‘g‘ri berilgan?' % e['w'], m, wr,
                     '«%s» ma’nolari: %s.' % (e['w'], '; '.join('%d) %s — %s' % (i, t['p'], cut(t['m'], 40)) for i, t in enumerate(e['s'][:3], 1))), nid)); nid += 1; nb += 1
    # c) guruhlar (ot+fe'l, ot+sifat)
    for need, nq in ((('ot', 'fe’l'), 70), (('ot', 'sifat'), 50)):
        have = [e for e in tagged if all(p in {s['p'] for s in e['s']} for p in need)]
        lack = [e for e in tagged if need[1] not in {s['p'] for s in e['s']} and need[0] in {s['p'] for s in e['s']}]
        for _ in range(nq):
            g = random.sample(have, 3)
            opts = [g]
            for k in range(3):
                bad = random.choice(lack); h = random.sample(have, 2); opts.append(h + [bad])
            ws = lambda L: ', '.join(x['w'] for x in L)
            correct = ws(opts[0]); wrong = [ws(L) for L in opts[1:]]
            if len({correct, *wrong}) < 4: continue
            if need[1] == 'fe’l': qq = 'Qaysi javobda berilgan so‘zlarning barchasi ham ot, ham fe’l ma’nosiga ega bo‘la oladi (omonim)?'
            else: qq = 'Qaysi javobda berilgan so‘zlarning barchasi ham ot, ham sifat ma’nosiga ega bo‘la oladi (omonim)?'
            exp = 'To‘g‘ri qator: ' + '; '.join('%s (%s)' % (x['w'], poslabel({s['p'] for s in x['s']})) for x in opts[0]) + '. Boshqa qatorlarda %s ma’nosi yo‘q so‘z bor: ' % need[1] + '; '.join('%s (%s)' % (L[-1]['w'], poslabel({s['p'] for s in L[-1]['s']})) for L in opts[1:]) + '.'
            out.append(Q('leks', 3, qq, correct, wrong, exp, nid)); nid += 1
    return [x for x in out if x]

# ============================================================= PARONIM
def gen_paronim():
    out = []; nid = 12001
    pj = J(os.path.join(APP, 'paronim.json'))
    pairs = []   # [(w, meaning), ...]
    for items in LUG['par']:
        its = [(norm(x['w']), x['m']) for x in items if clean_word(norm(x['w']))]
        if len(its) >= 2: pairs.append(its)
    for e in pj:
        its = [(norm(x['w']), x['m']) for x in e['w'] if clean_word(norm(x['w']))]
        if len(its) >= 2: pairs.append(its)
    seen = set(); P = []
    for its in pairs:
        key = tuple(sorted(w for w, _ in its))
        if key in seen: continue
        seen.add(key); P.append(its)
    allw = sorted({w for its in P for w, _ in its})
    # a) ma'no bo'yicha so'z
    random.shuffle(P); na = 0
    for its in P:
        for i, (w, m) in enumerate(its):
            if na >= 230: break
            mm = cut(re.sub(r'^(esk|dial|xim|fiz|med|bot|zool|mus|tib|sft)\.\s*(kt\.\s*)?', '', m, flags=re.I), 60)
            if len(mm) < 5 or w in mm.lower() or random.random() < .55: continue
            partner = [x for x, _ in its if x != w]
            near = sorted([x for x in allw if x != w and x not in partner and 1 <= lev(x, w) <= 2], key=lambda x: (lev(x, w), x))
            if not near: continue
            wr = partner[:2] + near[:3]; wr = [x for x in dict.fromkeys(wr)][:3]
            if len(wr) < 3: continue
            exp = '; '.join('«%s» — %s' % (x, cut(mx, 50)) for x, mx in its[:3] if mx) + '.'
            out.append(Q('leks', 2, '«%s» ma’nosini bildiruvchi so‘zni toping.' % mm, w, wr, exp, nid)); nid += 1; na += 1
    # b) paronim juftlik
    sets = [[norm(x) for x in e['h'] if clean_word(norm(x))] for e in J(os.path.join(APP, 'sinonim.json'))]
    sets = [s for s in sets if len(s) >= 2]
    random.shuffle(P)
    for its in P[:90]:
        a, b = its[0][0], its[1][0]
        if a == b: continue
        wr = []
        for s in random.sample(sets, 30):
            x, y = random.sample(s, 2)
            if lev(x, y) > 2 and ('%s — %s' % (x, y)) not in wr: wr.append('%s — %s' % (x, y))
            if len(wr) == 3: break
        if len(wr) < 3: continue
        out.append(Q('leks', 1, 'Qaysi juftlik paronim (shakli yaqin, ma’nosi har xil so‘zlar)?', '%s — %s' % (a, b), wr,
                     '«%s» (%s) va «%s» (%s) — paronimlar. Qolgan juftliklar ma’nodosh so‘zlar.' % (a, cut(its[0][1], 40), b, cut(its[1][1], 40)), nid)); nid += 1
    # c, d) gap: paronim noto'g'ri / to'g'ri qo'llangan
    def sentences(text, key):
        t = re.sub(r'\([^)]*\)', ' ', text); t = re.sub(r'\s+', ' ', t).strip()
        res = []
        for s in re.findall(r'[^.!?…]+[.!?…]*', t):
            s = re.sub(r'^[—–-]\s*', '', s.strip())
            if not (30 <= len(s) <= 105) or '[' in s or '“' in s or '«' in s: continue
            for m in re.finditer(r"[A-Za-zʻ‘’'`ʼ]+", s):
                tok = m.group(0)
                if len(key) <= len(tok) <= len(key) + 5 and norm(tok).startswith(key): res.append((s, m.start(), m.end(), tok[len(key):]))
        return res
    items = []   # (e_index, word index, sentence, swapped sentence)
    for ei, e in enumerate(pj):
        ws = [(norm(x['w']), x) for x in e['w'] if clean_word(norm(x['w']))]
        if len(ws) < 2: continue
        for wi, (key, x) in enumerate(ws):
            for ex in x.get('ex', []):
                for s, a, b, suf in sentences(ex, key):
                    other = ws[(wi + 1) % len(ws)][0]
                    bad = s[:a] + other + suf + s[b:]
                    items.append((ei, key, other, s, bad))
                    break
    items = list({it[3]: it for it in items}.values()); random.shuffle(items)
    byE = collections.defaultdict(list)
    for it in items: byE[it[0]].append(it)
    pool = list(items); n1 = n2 = 0
    for it in pool:
        if n1 < 130:
            others = [x for x in random.sample(pool, 12) if x[0] != it[0]][:3]
            if len(others) == 3:
                out.append(Q('leks', 3, 'Paronimlarni qo‘llashda xatolik bor gapni aniqlang.', it[4], [x[3] for x in others],
                             'Xato: «%s» o‘rniga «%s» bo‘lishi kerak (gap lug‘at misolidan olingan).' % (it[2], it[1]), nid)); nid += 1; n1 += 1
        if n2 < 100 and random.random() < .8:
            others = [x for x in random.sample(pool, 12) if x[0] != it[0]][:3]
            if len(others) == 3:
                out.append(Q('leks', 3, 'Qaysi gapda paronim to‘g‘ri qo‘llangan?', it[3], [x[4] for x in others],
                             'To‘g‘ri qator: «%s» so‘zi shu ma’noda ishlatilgan. Boshqa gaplarda paronim almashtirilgan: %s.' % (it[1], ', '.join('«%s» (to‘g‘risi «%s»)' % (x[2], x[1]) for x in others)), nid)); nid += 1; n2 += 1
    return [x for x in out if x]

# ============================================================= SINONIM
CLUSTERS = [  # (sifatlar, otlar, zid ma'noli sifat)
 (['kuchli', 'baquvvat', 'quvvatli', 'qudratli'], ['kuch', 'quvvat', 'qudrat'], 'kuchsiz'),
 (['chiroyli', 'go‘zal', 'suluv', 'ko‘rkam', 'nafis'], ['husn', 'go‘zallik', 'ko‘rk'], 'xunuk'),
 (['aqlli', 'farosatli', 'dono', 'zakovatli', 'donishmand'], ['aql', 'farosat', 'zakovat', 'donolik'], 'nodon'),
 (['baxtli', 'saodatli', 'baxtiyor'], ['baxt', 'saodat', 'iqbol'], 'baxtsiz'),
 (['mehribon', 'rahmdil', 'shafqatli', 'muruvvatli'], ['mehr', 'shafqat', 'rahm', 'muruvvat'], 'berahm'),
 (['jasur', 'botir', 'dovyurak', 'mard', 'qo‘rqmas'], ['jasorat', 'botirlik', 'mardlik', 'dovyuraklik'], 'qo‘rqoq'),
 (['katta', 'buyuk', 'ulkan', 'ulug‘', 'yirik'], ['kattalik', 'buyuklik', 'ulug‘lik'], 'kichik'),
 (['tezkor', 'chaqqon', 'epchil', 'chaqqon'], ['tezlik', 'chaqqonlik', 'epchillik'], 'sekin'),
 (['yaxshi', 'durust', 'a’lo', 'ajoyib', 'yaxshi'], ['yaxshilik', 'ezgulik', 'xayr'], 'yomon'),
 (['sodiq', 'vafodor', 'vafoli'], ['sadoqat', 'vafo', 'vafodorlik'], 'xoin'),
 (['halol', 'pok', 'diyonatli', 'insofli'], ['halollik', 'poklik', 'diyonat', 'insof'], 'nopok'),
 (['boy', 'badavlat', 'davlatmand'], ['boylik', 'davlat', 'badavlatlik'], 'kambag‘al'),
 (['kambag‘al', 'qashshoq', 'nochor', 'bechora'], ['kambag‘allik', 'qashshoqlik', 'nochorlik', 'faqirlik'], 'boy'),
 (['g‘amgin', 'mahzun', 'ma’yus', 'tushkun'], ['g‘am', 'alam', 'qayg‘u', 'mahzunlik'], 'xursand'),
 (['xursand', 'shod', 'mamnun', 'xushnud'], ['shodlik', 'quvonch', 'xursandlik', 'mamnunlik'], 'g‘amgin'),
 (['tirishqoq', 'mehnatkash', 'g‘ayratli', 'sa’y-harakatli'], ['tirishqoqlik', 'g‘ayrat', 'mehnat'], 'dangasa'),
 (['sabrli', 'bardoshli', 'chidamli', 'toqatli'], ['sabr', 'bardosh', 'chidam', 'toqat'], 'sabrsiz'),
 (['mashhur', 'taniqli', 'nomdor', 'shuhratli'], ['shuhrat', 'mashhurlik', 'nom'], 'nomaʼlum'),
 (['toza', 'ozoda', 'pokiza'], ['tozalik', 'ozodalik', 'pokizalik', 'poklik'], 'iflos'),
 (['adolatli', 'odil', 'insofli', 'haqqoniy'], ['adolat', 'odillik', 'insof'], 'adolatsiz'),
 (['hurmatli', 'muhtaram', 'e’zozli', 'e’tiborli'], ['hurmat', 'izzat', 'ehtirom', 'e’zoz'], 'hurmatsiz'),
 (['tinch', 'osoyishta', 'xotirjam', 'sokin'], ['tinchlik', 'osoyishtalik', 'xotirjamlik', 'sukunat'], 'notinch'),
 (['jahldor', 'g‘azabnok', 'asabiy', 'qahrli'], ['jahl', 'g‘azab', 'qahr', 'achchiq'], 'muloyim'),
 (['yorqin', 'nurli', 'ravshan', 'porloq'], ['nur', 'yog‘du', 'ziyo', 'yorug‘lik'], 'xira'),
 (['qorong‘i', 'tund', 'zim-ziyo'], ['zulmat', 'qorong‘ilik', 'tundlik'], 'yorug‘'),
 (['o‘tkir', 'keskin', 'tig‘li'], ['o‘tkirlik', 'keskinlik'], 'o‘tmas'),
 (['dangasa', 'ishyoqmas', 'sust'], ['dangasalik', 'sustlik'], 'tirishqoq'),
 (['kamtar', 'xokisor', 'kamsuqum'], ['kamtarlik', 'xokisorlik', 'kamsuqumlik'], 'takabbur'),
 (['saxiy', 'jomard', 'ochiq qo‘l'], ['saxovat', 'saxiylik', 'jomardlik'], 'baxil'),
 (['sog‘lom', 'baquvvat', 'bardam', 'tetik'], ['sog‘liq', 'salomatlik', 'sihat-salomatlik'], 'kasal'),
]
def gen_sinonim():
    out = []; nid = 11001
    # --- A) so'z turkumi jihatidan farqlanadigan yaqin so'zlar (qo'lda tuzilgan klasterlar)
    seen = set()
    for adj, nou, ant in CLUSTERS:
        adj = [x for x in dict.fromkeys(adj) if ' ' not in x and '-' not in x]; nou = [x for x in dict.fromkeys(nou) if ' ' not in x and '-' not in x]
        if len(adj) < 3 or len(nou) < 2: continue
        # 1) so'z turkumi jihatidan farqli
        combos = list(itertools.combinations(adj, 3)); random.shuffle(combos)
        for c, nn in zip(combos[:4], itertools.cycle(random.sample(nou, len(nou)))):
            o = [nn] + list(c)
            out.append(Q('leks', 2, 'Qaysi so‘z qolganlaridan so‘z turkumi jihatidan farq qiladi?', nn, list(c),
                         '«%s» — ot; «%s» — sifat. Ma’nodosh so‘zlar bir turkumga oid bo‘ladi.' % (nn, '», «'.join(c)), nid)); nid += 1
        nc = list(itertools.combinations(nou, 3)) if len(nou) >= 4 else []
        for c in nc[:1]:
            a = random.choice(adj)
            out.append(Q('leks', 2, 'Qaysi so‘z qolganlaridan so‘z turkumi jihatidan farq qiladi?', a, list(c),
                         '«%s» — sifat; «%s» — ot.' % (a, '», «'.join(c)), nid)); nid += 1
        # 2) sifatga ma'nodosh
        for a in adj[:5]:
            rights = [x for x in adj if x != a]
            r = random.choice(rights)
            wr = random.sample(nou, min(2, len(nou))) + [ant]
            if len(set(wr + [r])) < 4: continue
            out.append(Q('leks', 2, '«%s» so‘ziga ma’nodosh so‘zni toping.' % a, r, wr,
                         '«%s» va «%s» — sifat, o‘zaro ma’nodosh. «%s» — ot, «%s» — zid ma’noli so‘z.' % (a, r, wr[0], ant), nid)); nid += 1
        # 3) otga ma'nodosh
        for n in nou[:4]:
            rights = [x for x in nou if x != n]
            if not rights: continue
            r = random.choice(rights)
            wr = random.sample(adj, 2) + [ant]
            out.append(Q('leks', 2, '«%s» so‘ziga ma’nodosh so‘zni toping.' % n, r, wr,
                         '«%s» va «%s» — ot, o‘zaro ma’nodosh. «%s» — sifat, «%s» — zid ma’noli sifat.' % (n, r, wr[0], ant), nid)); nid += 1
    # --- B) lug'at to'plamlaridan (yaqin shakldagi chalg'ituvchilar bilan)
    S = J(os.path.join(APP, 'sinonim.json'))
    sets = []
    for e in S:
        ws = [norm(x) for x in e['h'] if clean_word(norm(x))]
        ws = list(dict.fromkeys(ws))
        if len(ws) >= 2: sets.append(ws)
    idx = collections.defaultdict(set)
    for i, ws in enumerate(sets):
        for w in ws: idx[w].add(i)
    allw = sorted(idx); random.shuffle(sets)
    def near(t, r, excl):
        sc = []
        for x in allw:
            if x in excl or x == t or x == r: continue
            if idx[x] & (idx[t] | idx[r]): continue
            s = max(lcp(x, t), lcp(x, r)); d = min(lev(x, t), lev(x, r))
            if s >= 4 or d <= 2 or (len(x) > 4 and (x in t or t in x or x in r or r in x)): sc.append((-s, d, x))
        sc.sort(); return [x for _, _, x in sc]
    na = 0
    for ws in sets:
        if na >= 220: break
        t, r = random.sample(ws, 2)
        nr = near(t, r, set())
        if len(nr) < 2: continue
        wr = nr[:3]
        if len(wr) < 3:
            extra = [x for x in random.sample(allw, 40) if x not in ws and x not in wr and not (idx[x] & (idx[t] | idx[r]))]; wr += extra[:3 - len(wr)]
        if len(wr) < 3: continue
        key = (t, r)
        if key in seen: continue
        seen.add(key)
        out.append(Q('leks', 3 if len(nr) >= 3 else 2, '«%s» so‘ziga ma’nodosh so‘zni toping.' % t, r, wr,
                     'Ma’nodosh so‘zlar: %s. Boshqa variantlar shakli yaqin bo‘lsa-da, ma’nodosh emas.' % ', '.join(ws[:5]), nid)); nid += 1; na += 1
    nb = 0
    for ws in sets:
        if nb >= 120: break
        if len(ws) < 3: continue
        g = random.sample(ws, 3); rows = []
        for k in range(3):
            two = random.sample(g, 2); nr = near(two[0], two[1], set(ws))
            if not nr: break
            rows.append(two + [random.choice(nr[:4])])
        if len(rows) < 3: continue
        fmt = lambda L: ', '.join(L)
        corr = fmt(g); wrong = [fmt(r_) for r_ in rows]
        if len({corr, *wrong}) < 4: continue
        out.append(Q('leks', 3, 'Qaysi qatordagi so‘zlarning hammasi o‘zaro ma’nodosh?', corr, wrong,
                     'Ma’nodosh qator: %s. Boshqa qatorlarda bittadan ma’nodosh bo‘lmagan so‘z bor.' % ', '.join(ws[:5]), nid)); nid += 1; nb += 1
    return [x for x in out if x]

# ============================================================= IMLO
def gen_imlo():
    out = []; nid = 20001
    act = {norm(x) for x in J(os.path.join(APP, 'active1000.json')) for x in re.split(r'[\s,;/]+', str(x)) if x}
    cand = set()
    for e in J(os.path.join(APP, 'sinonim.json')):
        for w in e['h']: cand.add(norm(w))
    for e in J(os.path.join(APP, 'paronim.json')):
        for w in e['w']: cand.add(norm(w['w']))
    for e in LUG['omo']: cand.add(norm(e['w']))
    words = sorted(w for w in (cand | act) if w in DICT and re.match(r'^[a-z‘’]{4,13}$', w))
    def rules(w):
        r = []
        if re.search(r'[og]‘|’', w): r.append('apos')
        if re.search(r'([bdfjklmnpqrstvxyz])\1', w): r.append('dbl')
        if 'x' in w or re.search(r'(^|[^sc])h', w): r.append('hx')
        if re.search(r'[qk]', w): r.append('qk')
        return r
    LAB = {'apos': 'o‘, g‘ harflari va tutuq belgisi (’) saqlanadi.', 'dbl': 'Qo‘sh undosh (ikki harf) saqlanadi.', 'hx': 'H va X harflarini adashtirmang.', 'qk': 'Q va K harflarini adashtirmang.'}
    def mut(w, rule):
        if rule == 'apos':
            ps = [i for i, ch in enumerate(w) if ch in '‘’']
            if not ps: return None
            i = random.choice(ps); return w[:i] + w[i + 1:] if random.random() < .6 else w[:i] + ('’' if w[i] == '‘' else '‘') + w[i + 1:]
        if rule == 'dbl':
            ps = [m.start() for m in re.finditer(r'([bdfjklmnpqrstvxyz])\1', w)]
            if not ps: return None
            i = random.choice(ps); return w[:i] + w[i + 1:]
        if rule == 'hx':
            ps = [i for i, ch in enumerate(w) if ch == 'x' or (ch == 'h' and not (i > 0 and w[i - 1] in 'sc'))]
            if not ps: return None
            i = random.choice(ps); return w[:i] + ('h' if w[i] == 'x' else 'x') + w[i + 1:]
        if rule == 'qk':
            ps = [i for i, ch in enumerate(w) if ch in 'qk']
            if not ps: return None
            i = random.choice(ps); return w[:i] + ('k' if w[i] == 'q' else 'q') + w[i + 1:]
    byrule = {r: [w for w in words if r in rules(w)] for r in LAB}
    print('imlo pools', {r: len(v) for r, v in byrule.items()})
    def bad_of(w, rule):
        for _ in range(8):
            m = mut(w, rule)
            if m and m != w and m not in DICT: return m
        return None
    n1 = n2 = 0; tries = 0
    while (n1 < 220 or n2 < 160) and tries < 6000:
        tries += 1
        rule = random.choices(['apos', 'dbl', 'hx', 'qk'], [.4, .25, .2, .15])[0]
        pool = byrule[rule]
        if len(pool) < 12: continue
        if n1 < 220 and random.random() < .58:
            # 4 qator x 3 so'z: bitta qatorda barcha so'zlar to'g'ri
            g = random.sample(pool, 12); rows = [g[0:3], g[3:6], g[6:9], g[9:12]]; ok = True; bads = []
            for r in rows[1:]:
                i = random.randrange(3); b = bad_of(r[i], rule)
                if not b: ok = False; break
                bads.append((r[i], b)); r[i] = b
            if not ok: continue
            fmt = lambda L: ', '.join(L)
            out.append(Q('imlo', 3, 'Qaysi qatordagi barcha so‘zlar to‘g‘ri yozilgan?', fmt(rows[0]), [fmt(r) for r in rows[1:]],
                         'Boshqa qatorlarda xato bor: ' + '; '.join('«%s» emas, «%s»' % (b, w) for w, b in bads) + '. ' + LAB[rule], nid)); nid += 1; n1 += 1
        elif n2 < 160:
            g = random.sample(pool, 4); b = bad_of(g[0], rule)
            if not b: continue
            out.append(Q('imlo', 2, 'Qaysi so‘zda imlo xatosi bor?', b, g[1:],
                         'To‘g‘ri yozilishi: «%s». %s' % (g[0], LAB[rule]), nid)); nid += 1; n2 += 1
    return [x for x in out if x]

# ============================================================= MUMTOZ (so'z ma'nolari)
def gen_mumtoz():
    out = []; nid = 30001
    src = os.path.join(HERE, 'mumtoz_q.json')
    if not os.path.exists(src): return out
    raw = J(src); P = []
    for w, m in raw:
        w = w.strip(); m = re.sub(r'^\d+\s*[\.\)]\s*', '', m.strip()); m = cut(m, 60)
        if not re.match(r'^[a-zA-Z‘’\' -]{3,16}$', w) or len(m) < 4 or w.lower() in m.lower(): continue
        if not re.match(r'^[a-zA-Zʻ‘’\' ,\-]+…?$', m) or m.endswith('-') or re.search(r'[A-Z]', m[1:]): continue
        P.append((w, m))
    random.shuffle(P); P = P[:2600]
    byl = collections.defaultdict(list)
    for w, m in P: byl[w[:2].lower()].append((w, m))
    def toks(m): return set(re.findall(r'[a-z‘’]{4,}', m.lower()))
    n1 = 0
    for w, m in P:
        if n1 >= 260: break
        pool = [x for x in byl[w[:2].lower()] if x[0] != w and not (toks(x[1]) & toks(m))]
        if len(pool) < 3: pool += [x for x in random.sample(P, 30) if x[0] != w and not (toks(x[1]) & toks(m))]
        if len(pool) < 3: continue
        wr = [x[1] for x in random.sample(pool, 3)]
        if m in wr: continue
        out.append(Q('nazar', 2, 'Mumtoz adabiyotda «%s» so‘zi qanday ma’noni bildiradi?' % w.lower(), m, wr, '«%s» — %s.' % (w.lower(), m), nid)); nid += 1; n1 += 1
    n2 = 0
    for w, m in random.sample(P, len(P)):
        if n2 >= 120: break
        pool = [x for x in random.sample(P, 40) if x[0] != w and not (toks(x[1]) & toks(m))]
        if len(pool) < 3: continue
        out.append(Q('nazar', 3, '«%s» ma’nosini bildiruvchi mumtoz so‘zni toping.' % m, w.lower(), [x[0].lower() for x in pool[:3]], '«%s» — %s.' % (w.lower(), m), nid)); nid += 1; n2 += 1
    return [x for x in out if x]

if __name__ == '__main__':
    om, pa, sn, im, mu = gen_omonim(), gen_paronim(), gen_sinonim(), gen_imlo(), gen_mumtoz()
    save('leks_omonim.json', om); save('leks_paronim.json', pa); save('leks_sinonim.json', sn); save('imlo_bank.json', im)
    if mu: save('mumtoz_bank.json', mu)
