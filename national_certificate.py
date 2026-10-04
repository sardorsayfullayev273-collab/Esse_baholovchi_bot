import os, sqlite3, json, re, hashlib, secrets, math
from datetime import datetime, timezone

DB_PATH = os.getenv('BOT_DB_PATH','esse_bot.sqlite3')
NATIONAL_ADMIN_ID = int(os.getenv('ADMIN_ID','1953416343'))
NATIONAL_APP_URL = os.getenv('MINIAPP_URL','')

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def db():
    c=sqlite3.connect(DB_PATH,timeout=30,check_same_thread=False); c.row_factory=sqlite3.Row; return c

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

def normalize_answer(s):
    s=(s or '').strip().casefold()
    s=s.replace('’',"'").replace('‘',"'").replace('`',"'")
    s=re.sub(r'\s+',' ',s)
    return s

def accepted_answer(q):
    a=q.get('answers',[])
    if isinstance(a,str): a=[a]
    return [normalize_answer(x) for x in a]

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
        return normalize_answer(vals[0]) in [normalize_answer(x) for x in aa] and normalize_answer(vals[1]) in [normalize_answer(x) for x in bb]
    return False

def check_parts(q, user):
    """O1AB: (a to'g'rimi, b to'g'rimi)."""
    vals=user if isinstance(user,list) else [user,'']
    vals=list(vals)+['','']
    aa=q.get('a_answers',q.get('answers_a',[])); bb=q.get('b_answers',q.get('answers_b',[]))
    if isinstance(aa,str): aa=[aa]
    if isinstance(bb,str): bb=[bb]
    return (normalize_answer(vals[0]) in [normalize_answer(x) for x in aa],
            normalize_answer(vals[1]) in [normalize_answer(x) for x in bb])

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
            errors.append({**part_info,'number':i,'type':typ,'user':user,'correct':q.get('answer') if typ in ('Y1','Y2') else (q.get('answers') if typ=='O1' else [q.get('a_answers'),q.get('b_answers')]),'explanation':q.get('explanation','')})
    raw=round(correct,2)
    pct=(raw/maxp*75) if maxp else 0
    return raw,round(pct,2),errors,maxp

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

def get_test(code):
    with db() as c:r=c.execute('SELECT * FROM national_tests WHERE code=? AND published=1',(code.upper().strip(),)).fetchone()
    if not r:return None
    d=dict(r); d['questions']=json.loads(d.pop('questions_json')); return d

def list_tests():
    with db() as c: rows=c.execute('SELECT id,code,title,subject,duration_min,created_at,published FROM national_tests ORDER BY id DESC').fetchall()
    return [dict(x) for x in rows]

def save_attempt(user_id,test_id,essay_check_id,answers,raw,score,level,errors):
    with db() as c:
        c.execute('INSERT INTO national_attempts(user_id,test_id,essay_check_id,answers_json,raw_score,diagnostic_score,level,errors_json,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(user_id,test_id,essay_check_id,json.dumps(answers,ensure_ascii=False),raw,score,level,json.dumps(errors,ensure_ascii=False),now())); c.commit()

def latest_essay_check(user_id):
    with db() as c:r=c.execute("SELECT id,total,result_json FROM checks WHERE user_id=? AND mode IN ('text','photo','pdf','image') ORDER BY id DESC LIMIT 1",(user_id,)).fetchone()
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
        rows=c.execute("SELECT id,total,topic,result_json FROM checks WHERE user_id=? AND mode IN ('text','photo','pdf','image') ORDER BY id DESC LIMIT 300",(user_id,)).fetchall()
    for r in rows:
        if norm_topic(r['topic'])==topic: return {'id':r['id'],'total':r['total'],'result_json':r['result_json']}
    return None


# =====================================================================
# RASCH / T-SHKALA (UZBMB "Baholash mezonlari va tabaqalashtirilgan ball berish")
#   Test:  Rasch qobiliyati θ -> Z=(θ-μ)/σ -> T=50+10Z, eng ko'pi 75
#   Esse:  24 ballik mezon -> 75 ballik jadval (24->75, 23.5->74, ... 12->51 ... 8.5->44; qadam: 0.5 ball = 1)
#   Umumiy ball = (test T + esse T) / 2
# =====================================================================
RASCH_MIN_N = int(os.getenv('RASCH_MIN_N', '30'))   # Rasch uchun kamida shuncha talabgor (har testning 1-urinishi)

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
        return round(raw_pct * 75, 1), False, N, f"Rasch uchun kamida {RASCH_MIN_N} ta talabgor kerak (hozir {N}). Ball vaqtincha foiz bo'yicha hisoblandi."
    # ma'lumot bermaydigan savollar (hamma to'g'ri yoki hech kim to'g'ri emas) Rasch'da hisobga olinmaydi
    informative = [n for n in nums if 0 < sum(1 for v in cohort.values() if n in v) < N]
    L = len(informative)
    if L < 5:
        return round(raw_pct * 75, 1), False, N, "Savollar yetarlicha farqlamaydi (Rasch uchun)."
    thetas = [_logit_measure(sum(1 for n in informative if n in v), L) for v in cohort.values()]
    mu = sum(thetas) / N
    sd = math.sqrt(sum((t - mu) ** 2 for t in thetas) / max(1, N - 1))
    if sd < 1e-9:
        return 50.0, False, N, "Talabgorlar natijalari bir xil."
    my_theta = _logit_measure(sum(1 for n in informative if n in mine), L)   # qayta urinishda ham joriy natija baholanadi
    z = (my_theta - mu) / sd
    return round(max(0.0, min(75.0, 50 + 10 * z)), 1), True, N, ''

def diagnostic_result(test, user_id, errors, essay):  # noqa
    """Ikkala joyda (Mini App va bot) bir xil ball: umumiy = (test T + esse T) / 2.
    essay: essay_for_test() natijasi yoki None. Esse topilmasa esse bo'limi 0 ball."""
    scored = rasch_items(test)
    wrong = wrong_item_ids(errors)
    correct = {n for n in scored if n not in wrong}
    test_t, is_rasch, n, note = rasch_test_t(test, user_id, correct, scored)
    essay24 = float(essay['total']) if essay else None
    essay_t = essay_to_75(essay24) if essay24 is not None else 0.0
    combined = round((test_t + essay_t) / 2.0, 1)
    return {'test_t': test_t, 'essay24': essay24, 'essay_t': essay_t, 'combined': combined,
            'level': level_for(combined), 'rasch': is_rasch, 'cohort': n, 'note': note}
