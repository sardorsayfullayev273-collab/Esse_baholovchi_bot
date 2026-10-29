import os, sqlite3, json, re, hashlib, secrets, math
from datetime import datetime, timezone

DB_PATH = os.getenv('BOT_DB_PATH','esse_bot.sqlite3')
NATIONAL_ADMIN_ID = int(os.getenv('ADMIN_ID','1953416343'))
NATIONAL_APP_URL = os.getenv('MINIAPP_URL','')

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
class _ClosingConn(sqlite3.Connection):
    """`with db() as c:` oxirida commit/rollback qiladi va ulanishni YOPADI (xotira oqishi oldini oladi)."""
    def __exit__(self, et, ev, tb):
        try:
            return super().__exit__(et, ev, tb)
        finally:
            try: self.close()
            except Exception: pass

def db():
    c=sqlite3.connect(DB_PATH,timeout=30,check_same_thread=False,factory=_ClosingConn); c.row_factory=sqlite3.Row
    try: c.execute('PRAGMA busy_timeout=30000')
    except Exception: pass
    try: c.execute('PRAGMA cache_size=-1500')
    except Exception: pass
    return c

def init_national_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS national_tests(
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, title TEXT NOT NULL,
            subject TEXT NOT NULL DEFAULT 'Ona tili va adabiyot', duration_min INTEGER NOT NULL DEFAULT 180,
            questions_json TEXT NOT NULL, created_by INTEGER, created_at TEXT NOT NULL,
            published INTEGER NOT NULL DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS national_attempts(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, test_id INTEGER NOT NULL,
            essay_check_id INTEGER, answers_json TEXT, raw_score REAL, diagnostic_score REAL,
            level TEXT, errors_json TEXT, created_at TEXT NOT NULL)''')
        cols={r[1] for r in c.execute('PRAGMA table_info(national_tests)').fetchall()}
        if 'essay_topic' not in cols:
            c.execute("ALTER TABLE national_tests ADD COLUMN essay_topic TEXT NOT NULL DEFAULT ''")
        c.execute('''CREATE TABLE IF NOT EXISTS national_settings(
            key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        for k,v in [('national_paid','0'),('national_price_stars','50')]:
            c.execute('INSERT OR IGNORE INTO national_settings(key,value) VALUES(?,?)',(k,v))
        c.commit()



def init_prep_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS national_prep_resources(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, kind TEXT NOT NULL,
            content TEXT, file_path TEXT, created_by INTEGER, created_at TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 1)""")
        c.commit()

def create_prep_resource(title, kind, content='', file_path='', created_by=0, published=1):
    with db() as c:
        cur=c.execute('INSERT INTO national_prep_resources(title,kind,content,file_path,created_by,created_at,published) VALUES(?,?,?,?,?,?,?)',
            (str(title).strip(),str(kind).strip(),str(content or ''),str(file_path or ''),int(created_by or 0),now(),int(published)))
        c.commit(); return cur.lastrowid

def list_prep_resources():
    with db() as c:
        rows=c.execute('SELECT id,title,kind,content,file_path,created_at,published FROM national_prep_resources WHERE published=1 ORDER BY id DESC').fetchall()
    return [dict(x) for x in rows]

def list_all_prep_resources():
    with db() as c:
        rows=c.execute('SELECT id,title,kind,content,file_path,created_at,published FROM national_prep_resources ORDER BY id DESC').fetchall()
    return [dict(x) for x in rows]

def setting(k, default=''):
    with db() as c:
        r=c.execute('SELECT value FROM national_settings WHERE key=?',(k,)).fetchone()
    return r['value'] if r else default

def set_setting(k,v):
    with db() as c:
        c.execute('INSERT INTO national_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v))); c.commit()

def gen_code():
    while True:
        code='MS-'+secrets.token_hex(3).upper()
        with db() as c:
            if not c.execute('SELECT 1 FROM national_tests WHERE code=?',(code,)).fetchone(): return code

_APOS=dict.fromkeys(map(ord,"\u2018\u2019\u201b\u02bb\u02bc\u02b9\u02c8\u2032\u00b4`\u0060\u02ca\u02cb"),"'")
_DASH=dict.fromkeys(map(ord,"\u2010\u2011\u2012\u2013\u2014\u2212"),"-")
def normalize_answer(s):
    """Katta-kichik harf, ortiqcha bo'sh joy va barcha turdagi apostrof (‘ ’ ʻ ʼ ` ´ ') farqlanmaydi."""
    import unicodedata
    s=unicodedata.normalize('NFKC',str(s or '')).strip().casefold()
    s=s.translate(_APOS).translate(_DASH)
    s=re.sub(r'\s+',' ',s).strip(' .,;:!?')
    return s

def split_alts(x):
    """'KITOB/KITOBLAR; BOOK' -> ['KITOB','KITOBLAR','BOOK']  (bir nechta to'g'ri javob '/' bilan ajratiladi; eski ';' ham ishlaydi)."""
    if isinstance(x,(list,tuple)):
        out=[]
        for i in x: out+=split_alts(i)
        return out
    return [t.strip() for t in re.split(r'[/;]',str(x or '')) if t.strip()]

def accepted_answer(q):
    return [normalize_answer(x) for x in split_alts(q.get('answers',[]))]

def _alts(v):
    return [normalize_answer(x) for x in split_alts(v)]

def fmt_alts(v):
    return ' / '.join(split_alts(v))

def fmt_user(v):
    if isinstance(v,list): return ' | '.join(str(x) for x in v)
    return str(v or '')

def check_answer(q, user):
    typ=q.get('type','Y1')
    if typ in ('Y1','Y2'):
        return normalize_answer(user)==normalize_answer(q.get('answer',''))
    if typ=='O1':
        vals=user if isinstance(user,list) else [user]
        ok=accepted_answer(q)
        return normalize_answer(vals[0] if vals else '') in ok
    if typ=='O1AB':
        vals=user if isinstance(user,list) else [user,'']
        aa=q.get('a_answers',q.get('answers_a',[])); bb=q.get('b_answers',q.get('answers_b',[]))
        if isinstance(aa,str): aa=[aa]
        if isinstance(bb,str): bb=[bb]
        return normalize_answer(vals[0]) in _alts(aa) and normalize_answer(vals[1]) in _alts(bb)
    return False

def check_parts(q, user):
    """O1AB: (a to'g'rimi, b to'g'rimi)."""
    vals=user if isinstance(user,list) else [user,'']
    vals=list(vals)+['','']
    aa=q.get('a_answers',q.get('answers_a',[])); bb=q.get('b_answers',q.get('answers_b',[]))
    if isinstance(aa,str): aa=[aa]
    if isinstance(bb,str): bb=[bb]
    return (normalize_answer(vals[0]) in _alts(aa),
            normalize_answer(vals[1]) in _alts(bb))

def grade(test, answers):
    qs=test['questions']; errors=[]; correct=0; maxp=0
    for i,q in enumerate(qs,1):
        typ=q.get('type','Y1')
        if typ=='O2': continue  # esse (45-topshiriq) test balliga kirmaydi: bali botdagi esse natijasidan olinadi
        pts=float(q.get('points',1)); maxp+=pts
        user=answers.get(str(i),'')
        if typ=='O1AB':
            # a) va b) dan har biri alohida baholanadi: har biri uchun savol ballining yarmi
            a_ok,b_ok=check_parts(q,user)
            earned=pts/2*(int(a_ok)+int(b_ok)); correct+=earned
            ok=a_ok and b_ok
            part_info={'wrong_parts':[p for p,v in (('a',a_ok),('b',b_ok)) if not v],'earned':round(earned,2),'points':pts}
        else:
            ok=check_answer(q,user)
            if ok: correct+=pts
            part_info={}
        if not ok:
            errors.append({**part_info,'number':i,'type':typ,'user':user,'correct':q.get('answer') if typ in ('Y1','Y2') else (q.get('answers') if typ=='O1' else [q.get('a_answers'),q.get('b_answers')]),'user_text':(('a) '+fmt_user(user[0] if isinstance(user,list) and user else '')+'  b) '+fmt_user(user[1] if isinstance(user,list) and len(user)>1 else '')) if typ=='O1AB' else fmt_user(user)),'correct_text':(('a) '+fmt_alts(q.get('a_answers',q.get('answers_a',[])))+'  b) '+fmt_alts(q.get('b_answers',q.get('answers_b',[])))) if typ=='O1AB' else (fmt_alts(q.get('answers')) if typ=='O1' else str(q.get('answer','')))),'explanation':q.get('explanation','')})
    raw=round(correct,2)
    pct=(raw/maxp*75) if maxp else 0
    return raw,round(pct,2),errors,maxp

def answer_key(test, answers=None):
    """v101: testning TO'LIQ javoblar ro'yxati (to'g'ri javob + foydalanuvchi javobi + holat). answers=None -> faqat kalit (admin).
    status: 'ok' | 'bad' | 'partial' (a/b dan bittasi) | 'key' (foydalanuvchi javobi yo'q) | 'essay' (45-topshiriq: test javobi yo'q)."""
    out=[]
    for i,q in enumerate(test['questions'],1):
        typ=q.get('type','Y1'); txt=str(q.get('text') or '')[:200]; pts=float(q.get('points',1))
        if typ=='O2':
            out.append({'number':i,'type':typ,'status':'essay','text':txt,'points':0,'user_text':'','correct_text':'Esse — test javoblariga kirmaydi','explanation':'','topic':str(q.get('topic') or '')}); continue
        has=answers is not None; user=(answers or {}).get(str(i),'')
        if typ=='O1AB':
            ua=user[0] if isinstance(user,list) and user else ''; ub=user[1] if isinstance(user,list) and len(user)>1 else ''
            correct='a) '+fmt_alts(q.get('a_answers',q.get('answers_a',[])))+'   b) '+fmt_alts(q.get('b_answers',q.get('answers_b',[])))
            utext='a) '+(fmt_user(ua) or '—')+'   b) '+(fmt_user(ub) or '—')
            a_ok,b_ok=check_parts(q,user); st='ok' if (a_ok and b_ok) else ('partial' if (a_ok or b_ok) else 'bad')
        elif typ=='O1':
            correct=fmt_alts(q.get('answers')); utext=fmt_user(user) or '—'; st='ok' if check_answer(q,user) else 'bad'
        else:
            correct=str(q.get('answer','')); utext=fmt_user(user) or '—'; st='ok' if check_answer(q,user) else 'bad'
        if not has: st='key'; utext=''
        out.append({'number':i,'type':typ,'status':st,'text':txt,'points':pts,'user_text':utext,'correct_text':correct,'explanation':str(q.get('explanation') or ''),'topic':str(q.get('topic') or '')})
    return out

def level_for(score):
    if score>=70:return 'A+'
    if score>=65:return 'A'
    if score>=60:return 'B+'
    if score>=55:return 'B'
    if score>=50:return 'C+'
    if score>=46:return 'C'
    return 'Sertifikat berilmadi'

def combined_diagnostic_score(test_score_75, essay_score_24):
    """Botning diagnostik hisob-kitobi: test 50 ball + esse 25 ball.
    Bu rasmiy UZBMB Rasch formulasi emas; rasmiy natijani almashtirmaydi.
    """
    t = max(0.0, min(75.0, float(test_score_75 or 0)))
    e = max(0.0, min(24.0, float(essay_score_24 or 0)))
    return round((t / 75.0) * 50.0 + (e / 24.0) * 25.0, 2)

def create_test(title, questions, created_by, subject='Ona tili va adabiyot', duration=180, publish=1, essay_topic=''):
    if len(questions)!=45: raise ValueError('To‘liq milliy format testi 45 ta topshiriqdan iborat bo‘lishi kerak.')
    code=gen_code()
    with db() as c:
        c.execute('INSERT INTO national_tests(code,title,subject,duration_min,questions_json,created_by,created_at,published,essay_topic) VALUES(?,?,?,?,?,?,?,?,?)',(code,title,subject,int(duration),json.dumps(questions,ensure_ascii=False),created_by,now(),publish,str(essay_topic or '').strip()[:300])); c.commit()
    return code

_GT_CACHE={}
def get_test(code):
    """v82: 8 soniya kesh — mock boshlanganda yuzlab so'rov har safar bazadan 45 savollik JSON o'qimasin."""
    import time as _t
    k=code.upper().strip(); h=_GT_CACHE.get(k)
    if h and _t.time()-h[0]<8: return dict(h[1])
    with db() as c:r=c.execute('SELECT * FROM national_tests WHERE code=? AND published=1',(k,)).fetchone()
    if not r:
        _GT_CACHE.pop(k,None); return None
    d=dict(r); d['questions']=json.loads(d.pop('questions_json'))
    if len(_GT_CACHE)>200: _GT_CACHE.clear()
    _GT_CACHE[k]=(_t.time(),d); return dict(d)

def list_tests():
    with db() as c: rows=c.execute('SELECT id,code,title,subject,duration_min,created_at,published FROM national_tests ORDER BY id DESC').fetchall()
    return [dict(x) for x in rows]

def has_attempt(user_id,test_id):
    with db() as c:
        return c.execute('SELECT 1 FROM national_attempts WHERE user_id=? AND test_id=? LIMIT 1',(int(user_id),int(test_id))).fetchone() is not None

def save_attempt(user_id,test_id,essay_check_id,answers,raw,score,level,errors,allow_repeat=False):
    """Bir foydalanuvchi bir testni FAQAT BIR MARTA topshiradi (admin: allow_repeat=True). Saqlangan bo'lsa True, rad etilsa False.
    Tekshiruv va yozish bitta SQL'da (bir vaqtda ikki marta yuborilsa ham ikkinchisi o'tmaydi)."""
    vals=(user_id,test_id,essay_check_id,json.dumps(answers,ensure_ascii=False),raw,score,level,json.dumps(errors,ensure_ascii=False),now())
    with db() as c:
        if allow_repeat:
            cur=c.execute('INSERT INTO national_attempts(user_id,test_id,essay_check_id,answers_json,raw_score,diagnostic_score,level,errors_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)',vals)
        else:
            cur=c.execute('INSERT INTO national_attempts(user_id,test_id,essay_check_id,answers_json,raw_score,diagnostic_score,level,errors_json,created_at) SELECT ?,?,?,?,?,?,?,?,? WHERE NOT EXISTS (SELECT 1 FROM national_attempts WHERE user_id=? AND test_id=?)',vals+(int(user_id),int(test_id)))
        c.commit(); return cur.rowcount>0

def latest_essay_check(user_id):
    with db() as c:r=c.execute("SELECT id,total,result_json FROM checks WHERE user_id=? AND mode IN ('text','photo','pdf','image','expert') ORDER BY id DESC LIMIT 1",(user_id,)).fetchone()
    return dict(r) if r else None

def norm_topic(s):
    """Mavzularni solishtirish uchun: katta-kichik harf, apostrof turlari va bo'shliqlar farq qilmaydi."""
    s=(s or '').strip().casefold()
    for ch in ('’','‘','`','ʻ','ʼ'): s=s.replace(ch,"'")
    s=re.sub(r'[\s]+',' ',s).strip(' .!?:;,\u00ab\u00bb"')
    return s

def essay_for_test(user_id, test):
    """Testning esse mavzusida yozilgan foydalanuvchining OXIRGI esse tekshiruvini qaytaradi.
    Mavzusiz (eski) testlar uchun avvalgidek oxirgi esse olinadi."""
    topic=norm_topic((test or {}).get('essay_topic',''))
    if not topic: return latest_essay_check(user_id)
    with db() as c:
        rows=c.execute("SELECT id,total,topic,result_json FROM checks WHERE user_id=? AND mode IN ('text','photo','pdf','image','expert') ORDER BY id DESC LIMIT 300",(user_id,)).fetchall()
    for r in rows:
        if norm_topic(r['topic'])==topic: return {'id':r['id'],'total':r['total'],'result_json':r['result_json']}
    return None


# =====================================================================
# RASCH / T-SHKALA (UZBMB "Baholash mezonlari va tabaqalashtirilgan ball berish")
#   Test:  Rasch qobiliyati θ -> Z=(θ-μ)/σ -> T=50+10Z, eng ko'pi 75
#   Esse:  24 ballik mezon -> 75 ballik jadval (24->75, 23.5->74, ... 12->51 ... 8.5->44; qadam: 0.5 ball = 1)
#   Umumiy ball = (test T + esse T) / 2
# =====================================================================
ESSAY_MISSING_ZERO = True   # v105: umumiy = (test T + esse T) ÷ 2 DOIM; esse topilmasa esse bo'limi 0/75 (faqat testga qarab yuqori ball QO'YILMAYDI)
RASCH_MIN_N = int(os.getenv('RASCH_MIN_N', '31'))   # Rasch uchun kamida shuncha talabgor (har testning 1-urinishi)

FALLBACK_T60 = float(os.getenv('FALLBACK_T60', '55'))   # talabgor kam bo'lganda: 60% to'g'ri javob ≈ shu T-ball (100% = 75, 0% = 15)

def fallback_t(raw_pct):
    """Rasch uchun talabgor yetarli bo'lmaganda taxminiy T-ball (bo'lakli-chiziqli): 0%->15, 60%->FALLBACK_T60, 100%->75."""
    p = max(0.0, min(1.0, float(raw_pct)))
    if p <= 0.6:
        return round(15 + (FALLBACK_T60 - 15) * (p / 0.6), 1)
    return round(FALLBACK_T60 + (75 - FALLBACK_T60) * ((p - 0.6) / 0.4), 1)

def essay_to_75(total24):
    """UZBMB jadvali: 24 ballik esse bahosini 75 ballik shkalaga o'tkazish (T = 27 + 2*ball)."""
    t = max(0.0, min(24.0, float(total24 or 0)))
    return round(max(0.0, min(75.0, 27 + 2 * t)), 1)

def rasch_items(test):
    """Rasch bandlari: oddiy savol -> '7'; O1AB -> '40a' va '40b' (har biri alohida to'g'ri/noto'g'ri). Esse (O2) kirmaydi."""
    items=[]
    for i,q in enumerate(test['questions'],1):
        t=q.get('type','Y1')
        if t=='O2': continue
        items += [f'{i}a',f'{i}b'] if t=='O1AB' else [str(i)]
    return items

def wrong_item_ids(errors):
    """Xatolar ro'yxatidan noto'g'ri bandlar to'plami. Eski yozuvlarda (wrong_parts yo'q) O1AB uchun ikkala qism xato deb olinadi."""
    out=set()
    for e in errors or []:
        n=int(e['number'])
        if e.get('type')=='O1AB':
            for p in (e.get('wrong_parts') or ['a','b']): out.add(f'{n}{p}')
        else: out.add(str(n))
    return out

def _first_attempt_vectors(test_id):
    """Testning har bir foydalanuvchisi uchun FAQAT birinchi urinishi: {user_id: set(xato savol raqamlari)}."""
    out = {}
    with db() as c:
        rows = c.execute('SELECT user_id, errors_json FROM national_attempts WHERE test_id=? ORDER BY id ASC', (test_id,)).fetchall()
    for r in rows:
        if r['user_id'] in out: continue
        try: errs = wrong_item_ids(json.loads(r['errors_json'] or '[]'))
        except Exception: errs = set()
        out[r['user_id']] = errs
    return out

def _logit_measure(r, L):
    """Rasch (PROX) bo'yicha qobiliyat: to'liq/nol ballar 0.5 ga tuzatiladi."""
    r = min(max(float(r), 0.5), L - 0.5)
    return math.log(r / (L - r))

def rasch_test_t(test, user_id, correct_items, scored_numbers):
    """Test bo'limi uchun 75 ballik T-bahoni hisoblaydi.
    correct_items: joriy urinishda to'g'ri javob berilgan savol raqamlari (set)
    scored_numbers: ballanadigan savollar raqamlari (esse bundan tashqari)
    Qaytaradi: (T, rasch_ishladimi, kohorta_soni, izoh)
    Rasch shartlari: bir xil og'irlikdagi dixotomik savollar; hech kim/hamma to'g'ri yechgan savollar tashlanadi;
    θ ning standartlash (Z) uchun μ va σ shu test bo'yicha talabgorlar kohortasidan olinadi."""
    nums = list(scored_numbers)
    # kohorta: oldingi birinchi urinishlar + joriy foydalanuvchi (agar hali yo'q bo'lsa — bu uning birinchi urinishi)
    prev = _first_attempt_vectors(test['id'])
    cohort = {u: {n for n in nums if n not in errs} for u, errs in prev.items()}   # har kimning 1-urinishi
    mine = set(correct_items) & set(nums)                                          # joriy urinish
    cohort.setdefault(user_id, mine)                                               # birinchi urinish bo'lsa kohortaga qo'shiladi
    N = len(cohort)
    raw_pct = (len(mine) / len(nums)) if nums else 0.0
    if N < RASCH_MIN_N or not nums:
        return fallback_t(raw_pct), False, N, f"Rasch uchun kamida {RASCH_MIN_N} ta talabgor kerak (hozir {N}). Ball vaqtincha taxminiy shkala bo'yicha hisoblandi."
    # ma'lumot bermaydigan savollar (hamma to'g'ri yoki hech kim to'g'ri emas) Rasch'da hisobga olinmaydi
    informative = [n for n in nums if 0 < sum(1 for v in cohort.values() if n in v) < N]
    L = len(informative)
    if L < 5:
        return fallback_t(raw_pct), False, N, "Savollar yetarlicha farqlamaydi (Rasch uchun); ball taxminiy shkala bo'yicha hisoblandi."
    thetas = [_logit_measure(sum(1 for n in informative if n in v), L) for v in cohort.values()]
    mu = sum(thetas) / N
    sd = math.sqrt(sum((t - mu) ** 2 for t in thetas) / max(1, N - 1))
    if sd < 1e-9:
        return 50.0, False, N, "Talabgorlar natijalari bir xil."
    my_theta = _logit_measure(sum(1 for n in informative if n in mine), L)   # qayta urinishda ham joriy natija baholanadi
    z = (my_theta - mu) / sd
    return round(max(0.0, min(75.0, 50 + 10 * z)), 1), True, N, ''

def test_has_essay(test):
    """v108: testda esse (O2) topshirig'i bormi (matematika/tarix testlarida esse yo'q)."""
    import ms_exam
    return ms_exam.has_essay(test)

def diagnostic_result(test, user_id, errors, essay):  # noqa
    """Ikkala joyda (Mini App va bot) bir xil ball: umumiy = (test T + esse T) / 2.
    essay: essay_for_test() natijasi yoki None. Esse topilmasa esse bo'limi 0 ball."""
    scored = rasch_items(test)
    wrong = wrong_item_ids(errors)
    correct = {n for n in scored if n not in wrong}
    test_t, is_rasch, n, note = rasch_test_t(test, user_id, correct, scored)
    if not test_has_essay(test):   # v108: matematika/tarix — esse yo'q: umumiy ball = test T-bali
        c0 = round(test_t, 1)
        return {'test_t': test_t, 'essay24': None, 'essay_t': 0.0, 'combined': c0, 'essay_missing': False, 'no_essay': True, 'essay_source': 'none',
                'level': level_for(c0), 'rasch': is_rasch, 'cohort': n, 'note': note}
    essay24 = float(essay['total']) if essay else None
    essay_t = essay_to_75(essay24) if essay24 is not None else 0.0
    essay_skipped = False   # v105: esse yo'q bo'lsa ham umumiy = (test + 0) ÷ 2
    combined = round(test_t, 1) if essay_skipped else round((test_t + essay_t) / 2.0, 1)
    return {'test_t': test_t, 'essay24': essay24, 'essay_t': essay_t, 'combined': combined, 'essay_missing': essay_skipped, 'essay_source': ('manual' if (essay and essay.get('manual')) else ('bot' if essay else 'none')),
            'level': level_for(combined), 'rasch': is_rasch, 'cohort': n, 'note': note}


# ---------------------------------------------------------------- Kutilayotgan diagnostik test (esse bahosi tanlanguncha)
def _pending_table(c):
    c.execute("CREATE TABLE IF NOT EXISTS national_pending(user_id INTEGER PRIMARY KEY, code TEXT NOT NULL, answers_json TEXT NOT NULL, created_at TEXT)")

def pending_set(user_id, code, answers):
    with db() as c:
        _pending_table(c)
        c.execute("INSERT INTO national_pending(user_id,code,answers_json,created_at) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET code=excluded.code, answers_json=excluded.answers_json, created_at=excluded.created_at",
                  (int(user_id), str(code), json.dumps(answers, ensure_ascii=False), now())); c.commit()

def pending_get(user_id):
    """{'code', 'answers'} yoki None."""
    with db() as c:
        _pending_table(c)
        r = c.execute("SELECT code, answers_json FROM national_pending WHERE user_id=?", (int(user_id),)).fetchone()
    if not r: return None
    try: return {'code': r['code'], 'answers': json.loads(r['answers_json'])}
    except Exception: return None

def pending_clear(user_id):
    with db() as c:
        _pending_table(c)
        c.execute("DELETE FROM national_pending WHERE user_id=?", (int(user_id),)); c.commit()

def parse_manual_essay(text):
    """Foydalanuvchi kiritgan esse balli (0–24) -> 0.5 qadamga yaxlitlangan float yoki None."""
    try:
        v = float(str(text).strip().replace(',', '.'))
    except Exception:
        return None
    if v < 0 or v > 24: return None
    return round(v * 2) / 2.0


# ---------------------------------------------------------------- Sertifikat test YAKUNLANGANDAN keyin beriladi
def _hold_table(c):
    c.execute("CREATE TABLE IF NOT EXISTS national_cert_hold(id INTEGER PRIMARY KEY AUTOINCREMENT, test_code TEXT NOT NULL, user_id INTEGER NOT NULL, data_json TEXT NOT NULL, level TEXT, created_at TEXT, issued_at TEXT, cert_code TEXT, UNIQUE(test_code,user_id))")

def cert_hold(test_code,user_id,data,level):
    with db() as c:
        _hold_table(c)
        c.execute("INSERT INTO national_cert_hold(test_code,user_id,data_json,level,created_at) VALUES(?,?,?,?,?) ON CONFLICT(test_code,user_id) DO UPDATE SET data_json=excluded.data_json, level=excluded.level WHERE issued_at IS NULL",
                  (str(test_code).upper(),int(user_id),json.dumps(data,ensure_ascii=False),level,now())); c.commit()

def cert_pending_list(test_code):
    with db() as c:
        _hold_table(c)
        rows=c.execute("SELECT id,user_id,data_json,level FROM national_cert_hold WHERE test_code=? AND issued_at IS NULL ORDER BY id",(str(test_code).upper(),)).fetchall()
    return [{'id':r['id'],'user_id':r['user_id'],'data':json.loads(r['data_json']),'level':r['level']} for r in rows]

def cert_mark_issued(hold_id,cert_code=None):
    with db() as c:
        _hold_table(c)
        c.execute("UPDATE national_cert_hold SET issued_at=?, cert_code=? WHERE id=?",(now(),cert_code,int(hold_id))); c.commit()


# ===== v103: admin mavjud testning savol matni / to'g'ri javobi / izohini tuzatadi + ishtirokchilar ballini qayta hisoblaydi =====
def _test_row(code):
    k=str(code or '').upper().strip()
    with db() as c: r=c.execute('SELECT * FROM national_tests WHERE code=?',(k,)).fetchone()
    if not r: return None
    d=dict(r); d['questions']=json.loads(d.pop('questions_json')); return d

def edit_questions(code, edits):
    """edits: [{'number':7,'answer':'B'} | {'number':37,'answers':'kitob/kitoblar'} | {'number':41,'a_answers':..,'b_answers':..} | {'number':3,'text':..,'explanation':..}].
    Hammasi tekshiriladi, xato bo'lsa HECH NARSA yozilmaydi (ValueError). Qaytaradi: o'zgargan savollar soni."""
    k=str(code or '').upper().strip()
    with db() as c:
        r=c.execute('SELECT id,questions_json FROM national_tests WHERE code=?',(k,)).fetchone()
        if not r: raise ValueError('Test topilmadi.')
        qs=json.loads(r['questions_json']); changed=0
        for e in (edits or []):
            if not isinstance(e,dict): raise ValueError('Tahrir ma’lumoti noto‘g‘ri.')
            try: n=int(e.get('number') or 0)
            except Exception: n=0
            if not (1<=n<=len(qs)): raise ValueError(f'{n}-savol topilmadi.')
            q=qs[n-1]; typ=q.get('type','Y1'); before=json.dumps(q,sort_keys=True,ensure_ascii=False)
            if 'text' in e:
                tx=str(e.get('text') or '').strip()[:6000]
                if tx: q['text']=tx
                else: q.pop('text',None)
            if 'topic' in e:   # v111: mavzu nomi (xatolar tahlili uchun)
                tp=re.sub(r'\s+',' ',str(e.get('topic') or '')).strip()[:120]
                if tp: q['topic']=tp
                else: q.pop('topic',None)
            if 'explanation' in e:
                ex=str(e.get('explanation') or '').strip()[:2000]
                if ex: q['explanation']=ex
                else: q.pop('explanation',None)
            if typ in ('Y1','Y2') and 'answer' in e:
                a=str(e.get('answer') or '').strip().upper(); opts=q.get('options') or (list('ABCD') if typ=='Y1' else list('ABCDEF'))
                if a not in opts: raise ValueError(f'{n}-savol: to‘g‘ri javob {"/".join(opts)} dan biri bo‘lishi kerak.')
                q['answer']=a
            if typ=='O1' and 'answers' in e:
                al=split_alts(e.get('answers'))
                if not al: raise ValueError(f'{n}-savolning to‘g‘ri javobi bo‘sh bo‘lishi mumkin emas.')
                q['answers']=al
            if typ=='O1AB':
                for key in ('a_answers','b_answers'):
                    if key in e:
                        al=split_alts(e.get(key))
                        if not al: raise ValueError(f'{n}-savolning {key[0]}) javobi bo‘sh bo‘lishi mumkin emas.')
                        q[key]=al
            if json.dumps(q,sort_keys=True,ensure_ascii=False)!=before: changed+=1
        if changed:
            c.execute('UPDATE national_tests SET questions_json=? WHERE id=?',(json.dumps(qs,ensure_ascii=False),r['id'])); c.commit()
    _GT_CACHE.pop(k,None)
    return changed

def set_topics(code, text):
    """v111: admin mavzularni ommaviy kiritadi («1-12: Mavzu»). Xato bo'lsa HECH NARSA yozilmaydi (ValueError). Qaytaradi: o'zgargan savollar soni."""
    import ms_exam
    t=_test_row(code)
    if not t: raise ValueError('Test topilmadi.')
    mp,errs=ms_exam.parse_topic_lines(text,len(t['questions']))
    if errs: raise ValueError('; '.join(errs[:4]))
    if not mp: raise ValueError('Mavzu topilmadi. Namuna: 1-12: Imlo qoidalari')
    return edit_questions(code,[{'number':n,'topic':tp} for n,tp in sorted(mp.items())])

def regrade_attempts(code):
    """Yangi kalit bo'yicha barcha ishtirokchilarning test balli (raw) va xatolar ro'yxatini qayta hisoblaydi.
    Umumiy ball/daraja: MOCK'da e'lon paytida hisoblanadi (e'londan oldin shu yetarli). Qaytaradi: {'attempts':n,'changed':m}."""
    t=_test_row(code)
    if not t: return {'attempts':0,'changed':0}
    n=ch=0
    with db() as c:
        rows=c.execute('SELECT id,answers_json,raw_score,errors_json FROM national_attempts WHERE test_id=?',(t['id'],)).fetchall()
        for r in rows:
            n+=1
            try: ans=json.loads(r['answers_json'] or '{}')
            except Exception: ans={}
            raw,_pct,errors,_mx=grade(t,ans); ej=json.dumps(errors,ensure_ascii=False)
            if abs(float(raw)-float(r['raw_score'] or 0))>1e-9 or ej!=(r['errors_json'] or ''):
                c.execute('UPDATE national_attempts SET raw_score=?, errors_json=? WHERE id=?',(raw,ej,r['id'])); ch+=1
        c.commit()
    _GT_CACHE.pop(str(code or '').upper().strip(),None)
    return {'attempts':n,'changed':ch}
