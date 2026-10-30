# -*- coding: utf-8 -*-
"""v108 — Milliy sertifikat imtihonlari: fanlar konfiguratsiyasi va natija tahlili.

Rasmiy format (uzbmb.uz fan spetsifikatsiyalari): 45 topshiriq.
  • Y-1 (1–32)  — bitta to'g'ri javobli yopiq test
  • Y-2 (33–35) — moslashtirish (A–F)
  • O   (36–44/45) — qisqa javobli ochiq topshiriq (a/b bandli)
  • Ona tili va adabiyot: №45 — yozma ish (esse), 24 ballik mezon
Vaqt: ona tili — 180 daq., matematika — 150 daq., tarix — 90 daq. (admin o'zgartira oladi).
Natija: Rash/T-shkala (national_certificate), esse bo'lsa umumiy = (test T + esse T) / 2, bo'lmasa = test T.
"""
import re

SUBJECTS = {
    'ona_tili': {
        'name': 'Ona tili va adabiyot', 'minutes': 180, 'essay': True,
        'layout': [(1, 32, 'Y1'), (33, 35, 'Y2'), (36, 39, 'O1'), (40, 44, 'O1AB'), (45, 45, 'O2')],
        'sections': [('Yopiq testlar', 1, 32), ('Moslashtirish', 33, 35), ('Ochiq javobli', 36, 44), ('Yozma ish (esse)', 45, 45)],
    },
    'matematika': {
        'name': 'Matematika', 'minutes': 150, 'essay': False,
        'layout': [(1, 32, 'Y1'), (33, 35, 'Y2'), (36, 45, 'O1AB')],
        'sections': [('Yopiq testlar', 1, 32), ('Moslashtirish', 33, 35), ('Ochiq javobli', 36, 45)],
    },
    'tarix': {
        'name': 'O‘zbekiston tarixi', 'minutes': 90, 'essay': False,
        'layout': [(1, 32, 'Y1'), (33, 35, 'Y2'), (36, 45, 'O1AB')],
        'sections': [('Yopiq testlar', 1, 32), ('Moslashtirish', 33, 35), ('Ochiq javobli', 36, 45)],
    },
}
DEFAULT_KEY = 'ona_tili'
N_TASKS = 45
MIN_MINUTES, MAX_MINUTES = 10, 240


def key_of(subject):
    """Fan nomidan (yoki kalitidan) konfiguratsiya kaliti. Noma'lum/eski testlar — ona tili."""
    s = str(subject or '').strip().casefold()
    if s in SUBJECTS: return s
    if 'matem' in s: return 'matematika'
    if 'tarix' in s or 'history' in s: return 'tarix'
    return DEFAULT_KEY


def config(subject):
    return SUBJECTS[key_of(subject)]


def expected_type(subject, i):
    for a, b, t in config(subject)['layout']:
        if a <= i <= b: return t
    return None


def minutes_for(subject, requested=None):
    try: m = int(requested)
    except (TypeError, ValueError): m = 0
    if m <= 0: m = config(subject)['minutes']
    return max(MIN_MINUTES, min(MAX_MINUTES, m))


def has_essay(test):
    """Testda esse bormi: O2 topshirig'i bo'lsa — ha; aks holda fanning o'ziga qarab (ona tili — ha, matematika/tarix — yo'q).
    Fani noma'lum/eski testlar ona tili deb olinadi (esse kutiladi)."""
    qs = (test or {}).get('questions') or []
    if any((q or {}).get('type') == 'O2' for q in qs): return True
    return bool(config((test or {}).get('subject'))['essay'])


def layout_error(subject, questions):
    """Savollar fan tuzilmasiga mos kelmasa — xabar, aks holda None."""
    if not isinstance(questions, list) or len(questions) != N_TASKS:
        return 'Milliy sertifikat testi 45 ta topshiriqdan iborat bo‘lishi kerak.'
    for i, q in enumerate(questions, 1):
        exp = expected_type(subject, i)
        if not isinstance(q, dict): return f'{i}-savol ma’lumoti noto‘g‘ri.'
        if q.get('type', 'Y1') != exp: return f'{i}-savol turi {exp} bo‘lishi kerak.'
    return None


# ---------------------------------------------------------------- natija tahlili
def question_status(q, user, check_answer, check_parts):
    typ = q.get('type', 'Y1')
    if typ == 'O2': return 'essay'
    blank = (user is None or user == '' or (isinstance(user, list) and not any(str(x).strip() for x in user)))
    if typ == 'O1AB':
        a_ok, b_ok = check_parts(q, user)
        if a_ok and b_ok: return 'ok'
        if a_ok or b_ok: return 'partial'
        return 'skip' if blank else 'bad'
    if check_answer(q, user): return 'ok'
    return 'skip' if blank else 'bad'


def breakdown(test, answers, check_answer, check_parts):
    """Natija ekrani uchun: har savol holati (xarita) va bo'limlar kesimi.
    status: ok | partial | bad | skip | essay.  kind: yopiq | moslashtirish | ochiq | esse."""
    cfg = config((test or {}).get('subject'))
    qs = test['questions']; answers = answers or {}
    tiles = []
    for i, q in enumerate(qs, 1):
        st = question_status(q, answers.get(str(i)), check_answer, check_parts)
        typ = q.get('type', 'Y1')
        tiles.append({'n': i, 'type': typ, 'status': st})
    sections = []
    for name, a, b in cfg['sections']:
        part = [t for t in tiles if a <= t['n'] <= b]
        if not part: continue
        ok = sum(1 for t in part if t['status'] == 'ok')
        half = sum(1 for t in part if t['status'] == 'partial')
        sections.append({'name': name, 'from': a, 'to': b, 'total': len(part), 'ok': ok, 'partial': half,
                         'essay': all(t['status'] == 'essay' for t in part)})
    return {'tiles': tiles, 'sections': sections}


def count_words(text):
    return len(re.findall(r'[^\W_]+(?:[\'‘’`ʻʼ-][^\W_]+)*', str(text or ''), flags=re.UNICODE))


# ---------------------------------------------------------------- uzun matnlar (v108+)
MAX_PASSAGE = 12000


def clean_passages(questions):
    """Savollardagi 'passage' (uzun matn) va 'passage_from' (shu matnli oldingi savol raqami) maydonlarini tozalaydi.
    Matn faqat bir marta (guruhning birinchi savolida) saqlanadi, qolganlari unga ishora qiladi."""
    for q in questions:
        if not isinstance(q, dict): continue
        ps = str(q.get('passage') or '').replace('\r', '').strip()[:MAX_PASSAGE]
        if ps: q['passage'] = ps
        else: q.pop('passage', None)
    for i, q in enumerate(questions, 1):
        if not isinstance(q, dict): continue
        try: pf = int(q.get('passage_from') or 0)
        except (TypeError, ValueError): pf = 0
        src = questions[pf - 1] if 1 <= pf < i and isinstance(questions[pf - 1], dict) else None
        if src is not None and src.get('passage') and not q.get('passage'): q['passage_from'] = pf
        else: q.pop('passage_from', None)
    return questions


def parse_topic_lines(text, n_max):
    """Admin ommaviy mavzu kiritishi. Qator: «1-12: Mavzu nomi» yoki «1,3,7-9: Mavzu». Ajratgich: «:» yoki «=» (yoki « - »).
    Qaytaradi: ({savol_raqami: mavzu}, [xatolar]). Bo'sh qatorlar o'tkazib yuboriladi; mavzu bo'sh bo'lsa — shu savollarning mavzusi o'chiriladi."""
    out, errs = {}, []
    for ln, raw in enumerate(str(text or '').replace('\r', '').split('\n'), 1):
        line = raw.strip()
        if not line: continue
        m = re.match(r'^([\d,\s\-–]+?)\s*[:=]\s*(.*)$', line) or re.match(r'^(\d[\d,\s\-–]*?)\s+[-–—]\s+(.+)$', line)
        if not m: errs.append('%d-qator: «raqam: mavzu» ko‘rinishida yozing' % ln); continue
        topic = re.sub(r'\s+', ' ', m.group(2)).strip()[:120]
        nums = set(); bad = False
        for part in re.split(r'[,\s]+', m.group(1).strip().replace('–', '-')):
            if not part: continue
            r = re.match(r'^(\d+)(?:-(\d+))?$', part)
            if not r: bad = True; break
            a = int(r.group(1)); b = int(r.group(2) or a)
            if a < 1 or b < a or b > n_max: bad = True; break
            nums.update(range(a, b + 1))
        if bad or not nums: errs.append('%d-qator: savol raqamlari 1–%d oralig‘ida bo‘lishi kerak' % (ln, n_max)); continue
        for n in nums: out[n] = topic
    return out, errs
