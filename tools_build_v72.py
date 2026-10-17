"""v72: content_gram.py va content_matn_adab.py dan
   1) miniapp/dtm_bank.json ga (o'yinlar, mock, kunlik, duel) yangi savollarni qo'shadi (s='v72' belgisi bilan — qayta ishlatsa takrorlanmaydi);
   2) mashq_seed.json yaratadi (Mashq → Grammatika / Matn / Adabiyot mavzulari: qoida, misol, yopiq va ochiq testlar).
Ishlatish:  python3 tools_build_v72.py
"""
import json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from content_gram import TOPICS as T_GRAM
from content_matn_adab import TOPICS_MATN, TOPICS_ADAB

LETTERS = 'ABCDEF'
ID0 = 70001
ALL = T_GRAM + TOPICS_MATN + TOPICS_ADAB


def problems(item, where):
    out = []
    k = item['k']
    if not item['q'].strip(): out.append('savol matni bo‘sh')
    if k == 'mc':
        o = item['o']
        if not (2 <= len(o) <= 6): out.append('variantlar soni')
        if len({x.strip().lower() for x in o}) != len(o): out.append('variantlar takrorlanadi')
        if any(not x.strip() for x in o): out.append('bo‘sh variant')
        if not item.get('e'): out.append('izoh yo‘q')
    elif k == 'open':
        if not item['ans']: out.append('javob yo‘q')
    elif k == 'match':
        if len(item['r']) != len(item['a']): out.append('qator/javob soni')
        if any(a >= len(item['o']) or a < 0 for a in item['a']): out.append('javob indeksi')
    return [where + ': ' + x for x in out]


def build_game_items():
    items, nid = [], ID0
    for t in ALL:
        for it in t['items']:
            d = {'t': it['k'], 'c': it['c'], 'd': 3 if it['k'] == 'match' else 2, 'q': it['q'], 'e': it.get('e', ''), 'id': nid, 's': 'v72'}
            if it['k'] == 'mc':
                d['o'] = it['o']; d['a'] = 0
                if it.get('fix'): d['fix'] = True
            elif it['k'] == 'open':
                d['ans'] = it['ans']
            else:
                d['r'] = it['r']; d['o'] = it['o']; d['a'] = it['a']
            if it.get('p'): d['p'] = it['p']
            items.append(d); nid += 1
    return items


def build_seed():
    seeds = []
    for ti, t in enumerate(ALL):
        closed, opened = [], []
        for qi, it in enumerate(t['items']):
            if it['k'] == 'match':
                continue   # Mashq testlari faqat yopiq (A–D) va ochiq turda; moslashtirish o'yinlar bankida
            text = it['q']
            if it.get('p'): text = '📄 Matn:\n' + it['p'] + '\n\n❓ ' + it['q']
            if it['k'] == 'mc':
                rnd = random.Random(1000 * (ti + 1) + qi)
                idx = list(range(len(it['o']))); rnd.shuffle(idx)
                options = [it['o'][i] for i in idx]
                closed.append({'text': text, 'options': options, 'answer': LETTERS[idx.index(0)], 'explanation': it.get('e', '')})
            else:
                opened.append({'text': text, 'options': it['ans'], 'explanation': it.get('e', '')})
        intro = ('Matn:\n' + t['text']) if t.get('text') else 'Bu mavzu bo‘yicha qoidalarni o‘qing, so‘ng «Testlar» bo‘limida mashq qiling.'
        seeds.append({'sec': t['sec'], 'title': t['title'], 'sections': {'heroes': intro, 'important': t['rules'], 'plot': t.get('examples', '')},
                      'closed': closed, 'open': opened})
    return seeds


def main():
    errs = []
    for t in ALL:
        for i, it in enumerate(t['items'], 1):
            errs += problems(it, f"{t['title'][:30]} #{i}")
    if errs:
        print('XATOLAR:'); print('\n'.join(errs)); sys.exit(1)
    # --- o'yin banki
    p = os.path.join(HERE, 'miniapp', 'dtm_bank.json')
    bank = json.load(open(p, encoding='utf-8'))
    bank = [x for x in bank if x.get('s') != 'v72']
    used = {x['id'] for x in bank}
    new = build_game_items()
    assert not any(x['id'] in used for x in new), 'id to‘qnashuvi'
    bank += new
    json.dump(bank, open(p, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    # --- mashq urug'i
    seeds = build_seed()
    json.dump(seeds, open(os.path.join(HERE, 'mashq_seed.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    by = {}
    for t in ALL:
        for it in t['items']: by[(it['c'], it['k'])] = by.get((it['c'], it['k']), 0) + 1
    nc = sum(len(s['closed']) for s in seeds); no = sum(len(s['open']) for s in seeds)
    print(f'dtm_bank.json: +{len(new)} savol (jami {len(bank)}). Mashq: {len(seeds)} mavzu, {nc} yopiq + {no} ochiq test.')
    print('turkum bo‘yicha:', dict(sorted(by.items())))


if __name__ == '__main__':
    main()
