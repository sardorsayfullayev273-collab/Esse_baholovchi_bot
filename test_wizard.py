# -*- coding: utf-8 -*-
"""v117 — botda «📝 Test kiritish» ustasi: Telegramga bog'liq bo'lmagan toza yordamchi funksiyalar.

Mini App'dagi «Diagnostik test» bilan bir xil ma'lumot tuzilmasi:
  • MS testi (45 topshiriq): Y1 (1–32, A–D), Y2 (33–35, A–F), O1 (ochiq), O1AB (a/b ochiq), O2 (esse, ona tili)
  • Mavzulashtirilgan (oddiy) test: istalgan sondagi savollar, A–F variantlar; «javoblar kaliti» yoki «savollar bilan»
Telegram qismi (tugmalar, xabarlar) bot-1-1.py ichida; bu yerda faqat tahlil (parse) va tekshiruv.
"""
import re

import ms_exam as se_
from national_certificate import split_alts

LETTERS = 'ABCDEF'
DEADLINES = [(1, '1 soat'), (6, '6 soat'), (24, '1 kun'), (72, '3 kun'), (168, '7 kun'), (720, '30 kun')]

ESSAY_MODE_TEXT = {
    'bot': '🤖 Botda tekshiriladi (talabgor esseni botga yuboradi, sun’iy intellekt ball qo‘yadi)',
    'manual': '✍️ Talabgor esse ballini o‘zi qo‘lda kiritadi (0–24)',
    'creator': '👤 Esse ballini men (test kirituvchi) qo‘yaman',
}
ESSAY_MODE_SHORT = {'any': 'talabgor tanlaydi', 'bot': 'botda (AI) tekshiriladi', 'manual': 'qo‘lda kiritiladi', 'creator': 'test kirituvchi qo‘yadi'}

_PAIR = re.compile(r'(?:^|[\s,;])(\d{1,4})\s*[-–.:)=]*\s*([A-Fa-f])(?![A-Za-z0-9])')
_OPEN = re.compile(r'^\s*(\d{1,2})\s*([abAB])?\s*[=:]\s*(.+?)\s*$')
_AB = re.compile(r'^\s*a\)?\s*(.*?)\s*[;|]\s*b\)?\s*(.*?)\s*$', re.I)
_PIPE = re.compile(r'^\s*(.+?)\s*\|\s*(.+?)\s*$')


# =====================================================================  MS (45 topshiriq)
def ms_new_state():
    return {'closed': {}, 'open': {}, 'ab': {}}


def _ms_type(skey, n):
    return se_.expected_type(skey, n)


def _closed_numbers(skey):
    return [n for n in range(1, 46) if _ms_type(skey, n) in ('Y1', 'Y2')]


def _letter_ok(typ, L):
    return L in ('ABCD' if typ == 'Y1' else 'ABCDEF')


def ms_feed(st, text, skey, answers=False):
    """Bitta xabarni kalitga (answers=True — talabgor javoblariga) qo'shadi. Qaytaradi: (qo'shilgan_soni, ogohlantirishlar).
    Kalitda ochiq javobda «/» bilan bir nechta to'g'ri javob bo'ladi; talabgor esa BITTA javob yozadi (bo'linmaydi)."""
    alts_of = (lambda x: [x.strip()] if x.strip() else []) if answers else split_alts
    added = 0
    warns = []
    rest = []
    for raw in str(text or '').replace('\r', '').split('\n'):
        ln = raw.strip()
        if not ln:
            continue
        m = _OPEN.match(ln)
        if m and 36 <= int(m.group(1)) <= 45:
            n = int(m.group(1))
            part = (m.group(2) or '').lower()
            body = m.group(3).strip()
            typ = _ms_type(skey, n)
            if typ == 'O1':
                alts = alts_of(body)
                if not alts:
                    warns.append(f'{n}-savol: javob bo‘sh.')
                else:
                    st['open'][n] = alts
                    added += 1
            elif typ == 'O1AB':
                if part in ('a', 'b'):
                    alts = alts_of(body)
                    if alts:
                        st['ab'].setdefault(n, {})[part] = alts
                        added += 1
                    else:
                        warns.append(f'{n}{part}) javob bo‘sh.')
                else:
                    mm = _AB.match(body) or (_PIPE.match(body) if answers else None)
                    if mm and mm.group(1) and mm.group(2):
                        st['ab'][n] = {'a': alts_of(mm.group(1)), 'b': alts_of(mm.group(2))}
                        added += 1
                    else:
                        warns.append(f'{n}-savol a/b: «{n}a = …» va «{n}b = …» deb alohida yozing.')
            elif typ == 'O2':
                warns.append(f'{n}-topshiriq esse — unga bu yerda javob kerak emas.')
            else:
                warns.append(f'{n}-savol uchun bunday javob mumkin emas.')
            continue
        rest.append(ln)
    if rest:
        a2, w2 = _feed_closed(st['closed'], ' '.join(rest), _closed_numbers(skey), lambda n: _ms_type(skey, n))
        added += a2
        warns += w2
    return added, warns


def _allowed_ms(typ):
    return 'ABCD' if typ == 'Y1' else 'ABCDEF'


def _feed_letters(store, text, numbers, allowed_of):
    """Yopiq javoblarni qo'shadi: ketma-ket harflar (birinchi bo'sh raqamdan) yoki «1A 2B» juftliklari.
    allowed_of(n) — n-savolda mumkin bo'lgan harflar («ABCD»). Qaytadan (qo'shilgan, ogohlantirishlar)."""
    warns = []
    compact = re.sub(r'[\s,;.]+', '', str(text or '')).upper()
    if compact and re.fullmatch(r'[A-F]+', compact):
        free = [n for n in numbers if n not in store]
        if len(compact) > len(free):
            return 0, [f'{len(compact)} ta harf yubordingiz, lekin bo‘sh joy faqat {len(free)} ta. Hech narsa qabul qilinmadi — tekshirib qayta yuboring.']
        for L, n in zip(compact, free):
            ok = allowed_of(n)
            if L not in ok:
                return 0, [f'{n}-savolga «{L}» mumkin emas (A–{ok[-1]}). Hech narsa qabul qilinmadi — tekshirib qayta yuboring.']
        for L, n in zip(compact, free):
            store[n] = L
        return len(compact), warns
    added = 0
    for m in _PAIR.finditer(' ' + str(text or '')):
        n = int(m.group(1))
        L = m.group(2).upper()
        if n not in numbers:
            warns.append(f'{n}-raqam bu testda yopiq savol emas (o‘tkazib yuborildi).')
            continue
        if L not in allowed_of(n):
            warns.append(f'{n}-savolga «{L}» mumkin emas.')
            continue
        store[n] = L
        added += 1
    if not added and not warns:
        warns.append('Javob topilmadi. Namuna: ABCDABCD…  yoki  1A 2B 3C')
    return added, warns


def _feed_closed(store, text, numbers, type_of):
    return _feed_letters(store, text, numbers, lambda n: _allowed_ms(type_of(n)))


def ms_missing(st, skey):
    out = []
    for n in range(1, 46):
        typ = _ms_type(skey, n)
        if typ in ('Y1', 'Y2'):
            if n not in st['closed']:
                out.append(n)
        elif typ == 'O1':
            if not st['open'].get(n):
                out.append(n)
        elif typ == 'O1AB':
            d = st['ab'].get(n) or {}
            if not (d.get('a') and d.get('b')):
                out.append(n)
    return out


def _compress(nums):
    """[1,2,3,7,9,10] -> '1–3, 7, 9–10'"""
    nums = sorted(nums)
    out = []
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else f'{nums[i]}–{nums[j]}')
        i = j + 1
    return ', '.join(out)


def ms_progress(st, skey):
    """Kalit holati: bo'limlar bo'yicha nechta kiritilgan va nima yetishmaydi."""
    miss = set(ms_missing(st, skey))
    lines = []
    total = done = 0
    for name, a, b in se_.SUBJECTS[skey]['sections']:
        nums = [n for n in range(a, b + 1) if _ms_type(skey, n) != 'O2']
        if not nums:
            continue
        d = len([n for n in nums if n not in miss])
        total += len(nums)
        done += d
        mark = '✅' if d == len(nums) else '⏳'
        lines.append(f'{mark} {a}–{b} {name}: {d}/{len(nums)}')
    head = f'📊 Kalit: {done}/{total} ta kiritildi'
    tail = ''
    if miss:
        tail = '\n\nYetishmaydi: ' + _compress(list(miss))
    return head + '\n' + '\n'.join(lines) + tail, not miss


def ms_build_questions(st, skey):
    """API kutadigan 45 elementli ro'yxat (Mini App bilan bir xil)."""
    qs = []
    for n in range(1, 46):
        typ = _ms_type(skey, n)
        q = {'type': typ, 'points': 1}
        if typ == 'Y1':
            q['options'] = list('ABCD')
            q['answer'] = st['closed'][n]
        elif typ == 'Y2':
            q['options'] = list('ABCDEF')
            q['answer'] = st['closed'][n]
        elif typ == 'O1':
            q['answers'] = list(st['open'][n])
        elif typ == 'O1AB':
            q['a_answers'] = list(st['ab'][n]['a'])
            q['b_answers'] = list(st['ab'][n]['b'])
        else:
            q['essay_from_bot'] = True
        qs.append(q)
    return qs


def ms_key_help(skey):
    cfg = se_.SUBJECTS[skey]
    secs = {t: (a, b) for a, b, t in cfg['layout']}
    y1 = secs.get('Y1', (1, 32))
    y2 = secs.get('Y2', (33, 35))
    parts = [
        '🔑 JAVOBLAR KALITINI YUBORING',
        'Bir necha xabar bilan ham yuborsangiz bo‘ladi — bot qayerga yetganingizni ko‘rsatib turadi.',
        '',
        f'1️⃣ Yopiq testlar {y1[0]}–{y1[1]} (A–D) va moslashtirish {y2[0]}–{y2[1]} (A–F):',
        '• ketma-ket harflar (1-savoldan boshlab):  ABCDABCD…',
        '• yoki raqami bilan:  1A 2B 3C 4D',
        '',
        '2️⃣ Ochiq javoblar:',
    ]
    if 'O1' in secs:
        a, b = secs['O1']
        parts += [f'• {a}–{b}-savollar, har biri alohida qatorda:', '   36 = KITOB/KITOBLAR', '   (bir nechta to‘g‘ri javob «/» bilan ajratiladi)']
    if 'O1AB' in secs:
        a, b = secs['O1AB']
        parts += [f'• {a}–{b}-savollar (a va b bandlari):', f'   {a}a = NEGAKI/CHUNKI', f'   {a}b = ERGASHGAN QO‘SHMA GAP']
    parts += ['', 'ℹ️ Katta-kichik harf va apostrof turlari farqlanmaydi.']
    if cfg['essay']:
        parts += ['45-topshiriq — esse: unga javob kaliti kiritilmaydi.']
    return '\n'.join(parts)


# =====================================================================  Oddiy (mavzulashtirilgan) test
def simple_key_feed(st, text, n, nopts):
    """st: {'ans': {raqam: harf}}. Ketma-ket harflar yoki «1A 2B» juftliklari. Qaytaradi: (qo'shilgan, ogohlantirishlar)."""
    ok = LETTERS[:nopts]
    return _feed_letters(st['ans'], text, list(range(1, n + 1)), lambda i: ok)


def simple_answer_feed(st, text, qs):
    """Talabgor javoblari (oddiy test): har savolning o'z variantlar soni bor."""
    return _feed_letters(st['ans'], text, list(range(1, len(qs) + 1)), lambda i: LETTERS[:max(2, len(qs[i - 1]['options']))])


def simple_key_missing(st, n):
    return [i for i in range(1, n + 1) if i not in st['ans']]


def simple_key_progress(st, n):
    miss = simple_key_missing(st, n)
    done = n - len(miss)
    txt = f'📊 Javoblar kaliti: {done}/{n} ta kiritildi'
    if miss:
        txt += '\nYetishmaydi: ' + _compress(miss)
    return txt, not miss


def simple_key_questions(st, n, nopts):
    opts = list(LETTERS[:nopts])
    return [{'text': '', 'options': list(opts), 'answer': st['ans'][i]} for i in range(1, n + 1)]


def parse_simple_bulk(text):
    """Mini App'dagi parseSimple bilan bir xil: «1. Savol / A) variant / Javob: B / Izoh: …». Qaytaradi: (savollar, xatolar)."""
    qs = []
    errs = []
    cur = None

    def flush():
        nonlocal cur
        if cur:
            qs.append(cur)
            cur = None

    for raw in str(text or '').replace('\r', '').split('\n'):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r'^(?:Javob|Жавоб|Answer)\s*[:\-]\s*([A-Fa-f])\b', line, re.I)
        if m and cur:
            cur['answer'] = m.group(1).upper()
            continue
        m = re.match(r'^Izoh\s*[:\-]\s*(.+)$', line, re.I)
        if m and cur:
            cur['explanation'] = m.group(1)
            continue
        m = re.match(r'^([A-Fa-f])\s*[\)\.]\s*(.+)$', line)
        if m and cur:
            cur['options'].append(m.group(2).strip())
            continue
        m = re.match(r'^\d+\s*[\.\)]\s*(.+)$', line)
        if m:
            flush()
            cur = {'text': m.group(1).strip(), 'options': [], 'answer': '', 'explanation': ''}
            continue
        if cur and not cur['options']:
            cur['text'] += ' ' + line
    flush()
    for i, q in enumerate(qs, 1):
        if len(q['options']) < 2:
            errs.append(f'{i}-savolda variantlar yetarli emas')
        elif not q['answer']:
            errs.append(f'{i}-savolda «Javob: X» yo‘q')
        elif LETTERS.index(q['answer']) >= len(q['options']):
            errs.append(f'{i}-savolning javobi variantlar orasida yo‘q')
    return qs, errs


SIMPLE_BULK_SAMPLE = (
    '1. Savol matni?\nA) birinchi variant\nB) ikkinchi variant\nC) uchinchi variant\nD) to‘rtinchi variant\nJavob: B\nIzoh: ixtiyoriy izoh\n\n'
    '2. Keyingi savol…'
)


# =====================================================================  Talabgor javoblari (botda «✅ Javob yuborish»)
def ms_answers_dict(st, skey):
    """API/baholash kutadigan {'1':'A', ..., '36':'KITOB', '40':['x','y']} (45-esse kirmaydi)."""
    out = {}
    for n in range(1, 46):
        typ = _ms_type(skey, n)
        if typ in ('Y1', 'Y2') and n in st['closed']:
            out[str(n)] = st['closed'][n]
        elif typ == 'O1' and st['open'].get(n):
            out[str(n)] = st['open'][n][0]
        elif typ == 'O1AB':
            d = st['ab'].get(n) or {}
            if d.get('a') or d.get('b'):
                out[str(n)] = [(d.get('a') or [''])[0], (d.get('b') or [''])[0]]
    return out


def ms_answers_count(st):
    return len(st['closed']) + len(st['open']) + sum(len([1 for k in ('a', 'b') if (d.get(k))]) for d in st['ab'].values())


def ms_answer_help(skey):
    cfg = se_.SUBJECTS[skey]
    secs = {t: (a, b) for a, b, t in cfg['layout']}
    y1 = secs.get('Y1', (1, 32)); y2 = secs.get('Y2', (33, 35))
    parts = [
        'JAVOBLARINGIZNI YUBORING (bir necha xabar bilan ham bo‘ladi):',
        '',
        f'1️⃣ {y1[0]}–{y1[1]} (A–D) va {y2[0]}–{y2[1]} (A–F) — harflar:',
        '   ABCDABCD…  (1-savoldan boshlab, ketma-ket)',
        '   yoki raqami bilan:  1A 2B 3C',
        '',
        '2️⃣ Ochiq javoblar — har biri alohida qatorda, faqat BITTA javob:',
    ]
    if 'O1' in secs:
        a, b = secs['O1']; parts.append(f'   {a} = kitob      ({a}–{b}-savollar)')
    if 'O1AB' in secs:
        a, b = secs['O1AB']; parts += [f'   {a}a = birinchi javob', f'   {a}b = ikkinchi javob     ({a}–{b}-savollar, a va b)']
    parts += ['', 'ℹ️ Katta-kichik harf va apostrof turlari farqlanmaydi.']
    if cfg['essay']:
        parts.append('📝 Esse (45-topshiriq) — javoblardan keyingi qadamda.')
    return '\n'.join(parts)


def simple_answers_progress(st, n):
    miss = simple_key_missing(st, n)
    txt = f'📊 Javoblar: {n - len(miss)}/{n} ta kiritildi'
    if miss:
        txt += '\nYetishmaydi: ' + _compress(miss)
    return txt, not miss
