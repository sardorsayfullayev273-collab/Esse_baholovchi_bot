"""v72: «Mashq» bo'limlariga (Grammatika, Matn, Adabiyot) tayyor mavzular, qoidalar va testlarni bir marta joylaydi.
Faqat bir marta ishlaydi (national_settings: mashq_seed_v72). Admin keyin mavzularni tahrirlashi yoki o'chirishi mumkin —
bot qayta ishga tushganda ular qaytib kelmaydi. Majburan qayta joylash: seed(bk, force=True) (bir xil nomli mavzular o'tkazib yuboriladi).
"""
import json, os, logging
from national_certificate import setting, set_setting

log = logging.getLogger(__name__)
SEED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mashq_seed.json')
FLAG = 'mashq_seed_v72'


def seed(bk, force=False):
    """Qaytaradi: (qo'shilgan_mavzular, qo'shilgan_savollar). Hech narsa qo'shilmasa (0, 0)."""
    if not force and setting(FLAG, '') == '1':
        return 0, 0
    if not os.path.exists(SEED_PATH):
        log.warning('mashq_seed.json topilmadi')
        return 0, 0
    data = json.load(open(SEED_PATH, encoding='utf-8'))
    have = {}
    for sec in {t['sec'] for t in data}:
        have[sec] = {bk._norm_title(b['title']) for b in bk.list_books(sec)}
    topics = qn = 0
    for t in data:
        key = bk._norm_title(t['title'])
        if key in have[t['sec']]:
            continue
        try:
            n = bk.add(t['title'], None, t['sec'])
            bk.set_sections(n, {k: v for k, v in t['sections'].items() if v})
            qs = [dict(q, kind='closed') for q in t['closed']] + [dict(q, kind='open') for q in t['open']]
            if qs:
                bk.add_questions(n, qs)
                qn += len(qs)
            have[t['sec']].add(key); topics += 1
        except Exception:
            log.exception('Mashq mavzusini joylashda xato: %s', t.get('title'))
    set_setting(FLAG, '1')
    log.info('Mashq urug‘i joylandi: %d mavzu, %d savol', topics, qn)
    return topics, qn
