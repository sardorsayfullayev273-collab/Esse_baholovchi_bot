# -*- coding: utf-8 -*-
"""lug_parsed.json dagi paronim/sinonim/omonim ma'lumotlarini ilova lug'atlariga qo'shadi (takroriylarsiz).
Ishlatish: python3 tools/merge_lug.py   (avval parse_lug.py)"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); APP = os.path.join(HERE, '..', 'miniapp')
L = json.load(open(os.path.join(HERE, 'lug_parsed.json'), encoding='utf-8'))
def norm(w): return re.sub(r'[`\'ʻʼ’]', '‘', w.strip().lower())
def cap(w): return w[:1].upper() + w[1:]
# paronim
pj = json.load(open(os.path.join(APP, 'paronim.json'), encoding='utf-8'))
have = {tuple(sorted(norm(x['w']) for x in e['w'])) for e in pj}; add = 0
for its in L['par']:
    its = [x for x in its if x['w']]
    if len(its) < 2: continue
    key = tuple(sorted(norm(x['w']) for x in its))
    if key in have: continue
    have.add(key); add += 1
    pj.append({'n': ' — '.join(x['w'].upper() for x in its),
               'w': [{'w': cap(x['w']), 'm': (x['m'].rstrip('.') + '.') if x['m'] else '', 'ex': []} for x in its]})
pj.sort(key=lambda e: e['n'].lower())
json.dump(pj, open(os.path.join(APP, 'paronim.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('paronim +%d => %d' % (add, len(pj)))
# sinonim
sj = json.load(open(os.path.join(APP, 'sinonim.json'), encoding='utf-8'))
have = {tuple(sorted(norm(x) for x in e['h'])) for e in sj}; add = 0
for ws in L['sin']:
    key = tuple(sorted(norm(x) for x in ws))
    if key in have: continue
    have.add(key); add += 1
    sj.append({'h': [cap(x) if i else cap(x.lower()) for i, x in enumerate(ws)], 't': 'A. Hojiyevning «O‘zbek tili sinonimlarining izohli lug‘ati» dan (izohsiz qator).'})
json.dump(sj, open(os.path.join(APP, 'sinonim.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('sinonim +%d => %d' % (add, len(sj)))
# omonim lug'ati (qidiruv sahifasi uchun)
om = [{'w': e['w'], 's': [[s['p'] or '', s['m']] for s in e['s']]} for e in L['omo']]
om.sort(key=lambda e: e['w'].lower())
json.dump(om, open(os.path.join(APP, 'omonim_lug.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('omonim_lug', len(om))
