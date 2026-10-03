import os, sqlite3, json, re, hashlib, secrets
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

def grade(test, answers):
    qs=test['questions']; errors=[]; correct=0; maxp=0
    for i,q in enumerate(qs,1):
        typ=q.get('type','Y1'); pts=float(q.get('points',1)); maxp+=pts
        user=answers.get(str(i),'')
        ok=check_answer(q,user)
        if ok: correct+=pts
        else:
            errors.append({'number':i,'type':typ,'user':user,'correct':q.get('answer') if typ in ('Y1','Y2') else (q.get('answers') if typ=='O1' else [q.get('a_answers'),q.get('b_answers')]),'explanation':q.get('explanation','')})
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

def create_test(title, questions, created_by, subject='Ona tili va adabiyot', duration=180, publish=1):
    if len(questions)!=45: raise ValueError('To‘liq milliy format testi 45 ta topshiriqdan iborat bo‘lishi kerak.')
    code=gen_code()
    with db() as c:
        c.execute('INSERT INTO national_tests(code,title,subject,duration_min,questions_json,created_by,created_at,published) VALUES(?,?,?,?,?,?,?,?)',(code,title,subject,int(duration),json.dumps(questions,ensure_ascii=False),created_by,now(),publish)); c.commit()
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
