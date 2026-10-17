"""v72: savol banklarini tekshirib, buzilgan (PDFdan ko'chirishda shikastlangan) savollarni karantin ro'yxatiga yozadi.
Natija: miniapp/banks_blocked.json  (o'yinlar shu id larni ko'rsatmaydi)  va  banks_blocked_report.txt  (ustoz tekshirishi uchun).
Ishlatish: python3 tools_quarantine_v72.py
"""
import glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
MA = os.path.join(HERE, 'miniapp')


def truncated(q):
    """PDFdan ko'chirishda savol oxiri kesilgan yoki «? a», «? lab, g‘ini imda» kabi axlat qo'shilgan."""
    s = (q or '').strip()
    if not s: return False
    last = s.split('\n')[-1].strip()
    if re.match(r'^(I{1,3}|IV|V|VI)\.\s', last): return False            # rim raqamli ro'yxat (I. ..., II. ...)
    if re.match(r'^\d\)\s', last): return bool(re.search(r'\.\.\.', last)) and not re.search(r'[;.)]$', last)
    m = re.search(r'[?.!]\s+([^\s?.!]{1,14}(?:[\s,.\-]+[^\s?.!]{1,14}){0,3})$', s)
    if m and len(m.group(1)) <= 26 and not m.group(1)[0].isupper(): return True
    return not re.search(r'[?.!:…»)\]]\s*$', s)


def reasons(x):
    f = []
    q = x.get('q') or ''; o = x.get('o') if isinstance(x.get('o'), list) else []
    if x.get('t') == 'mc':
        if q.count('«') != q.count('»'): f.append('«» juftsiz (matn buzilgan)')
        if re.search(r'(^|[\s(«])[JKQXHGSDFBLMNPRTVYZjkqxhgsdfblmnprtvyz]\s[o‘ua]', q): f.append('buzilgan bo‘g‘in (masalan «K o‘p»)')
        if truncated(q): f.append('savol matni kesilgan yoki oxirida axlat bor')
        if any(isinstance(s, str) and re.match(r'^\s*[-–—]\s+\S', s) for s in o): f.append('variant «- » bilan boshlanadi (shikastlangan)')
        if any(isinstance(s, str) and re.search(r'(^|[\s(«])[JKQXHGSDFBLMNPRTVYZjkqxhgsdfblmnprtvyz]\s[o‘]', s) and len(s) > 6 for s in o): f.append('variant ichida buzilgan bo‘g‘in')
    return f


def main():
    files = sorted(set(glob.glob(os.path.join(MA, '*_bank.json')) + glob.glob(os.path.join(MA, 'leks_*.json')) + glob.glob(os.path.join(MA, 'dtm19_*.json'))))
    ids, lines, per = [], [], {}
    for fp in files:
        d = json.load(open(fp, encoding='utf-8'))
        if not isinstance(d, list): continue
        for x in d:
            if x.get('s') == 'v72': continue   # yangi (o'zim yozgan) savollar tekshiruvdan o'tgan
            r = reasons(x)
            if r:
                ids.append(x['id']); per[os.path.basename(fp)] = per.get(os.path.basename(fp), 0) + 1
                lines.append(f"[{x['id']}] {os.path.basename(fp)} — {'; '.join(r)}\n    S: {(x.get('q') or '')[:160]!r}\n    V: {' / '.join(map(str, x.get('o') or []))[:140]}")
    json.dump({'ids': sorted(set(ids)), 'note': 'v72 avtomatik karantin: tekshirilgach ro‘yxatdan o‘chirish mumkin'}, open(os.path.join(MA, 'banks_blocked.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    open(os.path.join(HERE, 'banks_blocked_report.txt'), 'w', encoding='utf-8').write(
        f'KARANTINGA OLINGAN SAVOLLAR: {len(set(ids))} ta\nFayllar bo‘yicha: {per}\n\n' + '\n\n'.join(lines) + '\n')
    print('karantin:', len(set(ids)), per)


if __name__ == '__main__':
    main()
