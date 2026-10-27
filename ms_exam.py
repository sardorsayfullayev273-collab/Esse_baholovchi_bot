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
