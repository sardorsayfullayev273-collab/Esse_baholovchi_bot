# -*- coding: utf-8 -*-
"""Word (docx) lug'atidan (paronim, omonim, sinonim) tuzilgan ma'lumot chiqaradi.
Ishlatish:  python3 tools/parse_lug.py LUGAT.docx  ->  tools/lug_parsed.json
"""
import re, sys, json, subprocess, os

def fix(s):
    s = s.replace('`', '’').replace('ʻ', '’').replace('ʼ', '’').replace("'", '’').replace('‘', '’')
    s = re.sub(r'(?<=[oOgG])’', '‘', s)          # o‘ va g‘ harflari
    return s

def txt(path):
    out = subprocess.run(['pandoc', '-t', 'plain', '--wrap=none', path], capture_output=True, text=True).stdout
    return [l.strip() for l in out.split('\n')]

POS = {'ot': 'ot', 'fe’l': 'fe’l', 'fe‘l': 'fe’l', 'sft': 'sifat', 'sifat': 'sifat', 'ravish': 'ravish', 'son': 'son', 'olmosh': 'olmosh',
       'undov': 'undov', 'yuklama': 'yuklama', 'bog‘lovchi': 'bog‘lovchi', 'bog’lovchi': 'bog‘lovchi', 'ko‘makchi': 'ko‘makchi', 'ko’makchi': 'ko‘makchi',
       'modal': 'modal', 'taqlid': 'taqlid'}

def parse(path):
    L = txt(path)
    i_par = next(i for i, l in enumerate(L) if l.startswith('I. Paronim'))
    i_omo = next(i for i, l in enumerate(L) if l.startswith('II. Omonim'))
    i_sin = next(i for i, l in enumerate(L) if l.startswith('III QISM'))
    par, omo, sin = [], [], []
    # ---- paronim: "12. alam (..) – a’lam (..)"
    buf = ''
    for l in L[i_par + 3:i_omo]:
        if not l: continue
        if re.match(r'^\d+\.\s', l):
            if buf: par.append(buf)
            buf = l
        elif buf and not l.startswith('II.'):
            buf += ' ' + l
    if buf: par.append(buf)
    P = []
    for raw in par:
        raw = re.sub(r'^\d+\.\s*', '', fix(raw))
        parts = re.split(r'\s+[–—-]\s+(?=[A-Za-zʻ‘’\']+[a-zʻ‘’\']*\s*(?:\(|$|–|-))', raw)
        items = []
        for p in parts:
            m = re.match(r'^([^\(]+?)\s*(?:\((.*)\))?\s*$', p.strip())
            if not m: continue
            w = m.group(1).strip(' .,;'); mean = (m.group(2) or '').strip()
            if w and re.match(r'^[A-Za-z‘’\- ]+$', w): items.append({'w': w, 'm': mean})
        if len(items) >= 2: P.append(items)
    # ---- omonim
    cur = None; O = []; bad = []
    for l in L[i_omo + 4:i_sin]:
        if not l: continue
        l = fix(l)
        m = re.match(r'^([A-Za-z‘’\-]+(?: [a-z‘’\-]+)?)\s+(1\).*)$', l)
        if m:
            if cur: O.append(cur)
            cur = [m.group(1), m.group(2)]
        elif cur and not re.match(r'^[A-Za-z‘’\-]+\s+1\)', l):
            cur[1] += ' ' + l
        else: bad.append(l)
    if cur: O.append(cur)
    OM = []
    for w, rest in O:
        ms = re.split(r'(?:(?<=\s)|^)\d+\)\s*', rest)
        ms = [x.strip() for x in ms if x.strip()]
        out = []
        for x in ms:
            m = re.match(r'^([A-Za-z‘’]+)[\.,]?\s*(.*)$', x)
            pos = None; mean = x
            if m and m.group(1).lower() in POS:
                pos = POS[m.group(1).lower()]; mean = m.group(2)
            mean = re.sub(r'\s+', ' ', mean).strip(' ;.,')
            out.append({'p': pos, 'm': mean})
        if len(out) >= 2: OM.append({'w': w, 's': out})
    # ---- sinonim: "4. ASIL, sara, ..."
    S = []
    for l in L[i_sin:]:
        l = fix(l)
        m = re.match(r'^\s*\d+\.\s+(.+)$', l)
        if m:
            ws = [x.strip(' .') for x in m.group(1).split(',') if x.strip(' .')]
            if len(ws) >= 3: S.append(ws)
    return {'par': P, 'omo': OM, 'sin': S, 'omo_bad': bad[:20]}

if __name__ == '__main__':
    d = parse(sys.argv[1])
    json.dump(d, open(os.path.join(os.path.dirname(__file__), 'lug_parsed.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print({k: len(v) for k, v in d.items()})
