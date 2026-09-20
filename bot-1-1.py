import os
import re
import csv
import io
import json
import sqlite3
import asyncio
import hashlib
import logging
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, BadRequestError
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ============================================================
# CONFIG
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
PORT = int(os.getenv("PORT", "10000"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1953416343"))
ADMIN_CONTACT_URL = os.getenv("ADMIN_CONTACT_URL", "https://t.me/Sardor_Sayfullayev777")
DB_PATH = os.getenv("BOT_DB_PATH", "esse_bot.sqlite3")
EMBLEM_PATH = os.getenv("EMBLEM_PATH", "emblem.png")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN Render Environment Variables orqali berilishi kerak.")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY Render Environment Variables orqali berilishi kerak.")

client = OpenAI(api_key=OPENAI_API_KEY, timeout=120.0, max_retries=2)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("esse_baholovchi_bot")

# ============================================================
# BBA / BASIRAT NIZOMI + USER-SUPPLIED SUPPLEMENTARY RULES
# ============================================================
RUBRIC = r'''
Siz O'zbekiston ona tili va adabiyot fanidan esse tekshiruvchi qat'iy ekspert bo'lasiz.
Asosiy manba: "ESSE BAHOLASH NIZOMI - BASIRAT.pdf". Jami 24 ball, 12 mezon.
Har bir mezon faqat 0 / 0.5 / 1 / 1.5 / 2 ball.

MAXSUS HOLATLAR:
1) Esse yozilmagan -> 0.
2) Mavzuga mos emas -> 2.
3) 100 so'zdan kam -> 2.
4) Boshqa manbadan ko'chirilgani ishonchli dalil bilan aniqlansa -> 2.
5) Faqat kirish qismi yozilib, qolgan qismlar yo'q -> 0.
6) To'liq kirill alifbosida -> 0.
Ko'chirilganlikni dalilsiz taxmin qilmang. Vaziyat matnini qayta ishlatish internetdan ko'chirish dalili emas.
Reja va epigraf talab qilinmaydi.

12 MEZON:
1. Publitsistik uslub.
2. Ikkala qarash + shaxsiy qarash.
3. Har ikkala qarashni dalillash.
4. Kirish + asosiy qism + xulosa.
5. Mantiqiy qurilish va xatboshilar.
6. Mantiqiy-mazmuniy izchillik va fikr takrori.
7. Imlo.
8. Punktuatsiya.
9. Qo'shimcha qo'llash.
10. So'z qo'llash bilan bog'liq uslubiy xatolar.
11. Leksik xilma-xillik.
12. Sheva/vulgarizm/varvarizm/parazit so'zlar.

5,7,8,9,10,12 uchun xato soni bo'yicha rasmiy shkala:
0=2; 1-2=1.5; 3-4=1; 5-6=0.5; 7+=0.
6 uchun rasmiy shkala takror + izchillik holatiga bog'liq.

QO'SHIMCHA QAT'IY QOIDALAR (foydalanuvchi bergan):
A) Esse qismlari 2 ball bo'lishi uchun kirish, asosiy qism va xulosa to'liq bo'lishi kerak.
   Biror qism yo'q bo'lsa, 4-mezon va matn qurilishida xato qayd etiladi.
B) Mavzuga aloqasiz har bir gap 6-mezon (IZCHILLIK)ga salbiy ta'sir qiladi.
C) Leksik xilma-xillik 2 ball juda kam holatda beriladi; real dalil bo'lmasa 1-1.5 atrofida.
D) Noto'g'ri ishlatilgan maqol/ibora 6 va 11-mezonlarda sabab bilan qayd etiladi, bir xil xato bir joyda qayta sanalmaydi.
E) Badiiy/poetik uslubga o'tib ketish bo'lsa: "publitsistik uslubdan chetlashilgan" deb yoziladi va 1-mezon 1 ball bilan cheklanadi.
F) Sheva elementi bo'lsa: 12-mezon va 1-mezonga salbiy ta'sir qiladi; aynan bir so'zni dalil sifatida ko'rsating.
G) Har ikki asosiy qarash uchun kamida 2 ta aniq sabab/argument bo'lishi kerak. Bir qarashda 2 tadan kam sabab bo'lsa, 2-mezon 1 ballga tushiriladi va yuzakilik izohlanadi.
H) Dalil faqat aniq, mustahkam va mavzuga mos bo'lsa hisoblanadi. Ikki qarash ham dalillangan -> 3-mezon 2. Faqat biri -> 1.5. Dalil vaziyatga mos kelmasa -> 3 va 6 mezonlarda salbiy ta'sir qayd etiladi.
I) Har bir asosiy qism alohida xatboshida bo'lishi kerak; aks holda 5-mezon pasayadi.
J) Kirish/asosiy qism/xulosadan biri to'liq bo'lmasa: 4 va 5 mezonlarda 1 ballgacha pasayish qayd etiladi.
K) Kirish mavzuni so'zma-so'z ko'chirsa, 4 va 5 mezonlarda 1 ballgacha pasayish.
L) Shaxsiy fikr asosan xulosada aniq berilishi kerak. Kirish yoki 1/2 qarashlarda "menimcha bunisi to'g'ri", "sizningcha qaysi biri to'g'ri", "keling, fikrlashaylik" kabi iboralar uslub va izchillik nuqtayi nazaridan salbiy qayd qilinadi. Lekin 2-mezon shaxsiy qarash mavjudligini ham tekshiradi.
M) Xulosada ikki qarashdan BIRINI qo'llab-quvvatlash shart. Ikkalasini ham to'g'ri deb yakunlash yoki mavzu mohiyatidan chetga chiqish -> 4 va 6 mezonlarda pasayish.
N) Imlo, ishoraviy/punktuatsiya, so'z qo'llash va qo'shimcha qo'llash xatolari foydalanuvchi bergan amaldagi imlo me'yorlariga asoslanadi. So'zni faqat "g'alati ko'rindi" deb xato qilmang; norma bilan asoslang.
O) Har bir aniqlangan xato so'zma-so'z ko'rsatilishi kerak: XATO -> TO'G'RISI -> IZOH.
P) Bir xil xatoni ikki marta sanamang, agar u ikki xil mezonning mustaqil talabi bo'lmasa.
Q) 2/2 faqat to'liq va aniq dalil bo'lsa beriladi. Umumiy maqtov yoki mavzuga yaqinlik 2/2 uchun yetarli emas.

MUHIM: Qo'shimcha qoidalar rasmiy mezonlarning ball diapazonini buzmasdan qo'llanadi. Ball faqat 0,0.5,1,1.5,2 bo'lishi mumkin.
'''

CRITERION_NAMES = {
    1: "Publitsistik uslub",
    2: "Ikkala qarash va shaxsiy qarash",
    3: "Har ikkala qarashning dalillar bilan asoslanishi",
    4: "Kirish, asosiy qism, xulosa",
    5: "Mantiqiy qurilish va xatboshilar",
    6: "Izchillik va fikrlar takrori",
    7: "Imlo",
    8: "Punktuatsiya",
    9: "Qo'shimcha qo'llash",
    10: "So'z qo'llash uslubiyati",
    11: "Leksik xilma-xillik",
    12: "Sheva, vulgarizm, varvarizm, parazit so'zlar",
}

# ============================================================
# SQLITE PERSISTENT STORAGE
# ============================================================
DB_LOCK = threading.Lock()

def db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with DB_LOCK, db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            joined_at TEXT NOT NULL,
            last_seen TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS checks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mode TEXT,
            topic TEXT,
            total REAL,
            words INTEGER,
            created_at TEXT NOT NULL,
            status TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            message TEXT,
            created_at TEXT NOT NULL
        )''')
        c.commit()

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def upsert_user(user):
    if not user:
        return
    t = now_iso()
    with DB_LOCK, db() as c:
        c.execute('''INSERT INTO users(user_id,username,first_name,last_name,joined_at,last_seen)
                     VALUES(?,?,?,?,?,?)
                     ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,
                     first_name=excluded.first_name,last_name=excluded.last_name,last_seen=excluded.last_seen''',
                  (user.id, user.username or "", user.first_name or "", user.last_name or "", t, t))
        c.commit()

def save_check(user_id, mode, topic, total, words, status):
    with DB_LOCK, db() as c:
        c.execute("INSERT INTO checks(user_id,mode,topic,total,words,created_at,status) VALUES(?,?,?,?,?,?,?)",
                  (user_id, mode, topic[:1000], float(total), int(words), now_iso(), status))
        c.commit()

def stats_for_user(user_id):
    with DB_LOCK, db() as c:
        row = c.execute('''SELECT COUNT(*) n, AVG(total) avg, MAX(total) hi, MIN(total) lo,
                           SUM(CASE WHEN mode='text' THEN 1 ELSE 0 END) text_n,
                           SUM(CASE WHEN mode='image' THEN 1 ELSE 0 END) image_n
                           FROM checks WHERE user_id=?''', (user_id,)).fetchone()
        last = c.execute("SELECT total,created_at FROM checks WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        prev = c.execute("SELECT total FROM checks WHERE user_id=? ORDER BY id DESC LIMIT 1 OFFSET 1", (user_id,)).fetchone()
    return dict(row or {}), (dict(last) if last else None), (dict(prev) if prev else None)

def global_stats():
    with DB_LOCK, db() as c:
        total = c.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
        text_n = c.execute("SELECT COUNT(*) FROM checks WHERE mode='text'").fetchone()[0]
        image_n = c.execute("SELECT COUNT(*) FROM checks WHERE mode='image'").fetchone()[0]
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        avg = c.execute("SELECT AVG(total) FROM checks").fetchone()[0]
    return total, text_n, image_n, users, avg or 0

def users_csv_bytes():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["user_id","username","first_name","last_name","joined_at","last_seen"])
    with DB_LOCK, db() as c:
        for r in c.execute("SELECT user_id,username,first_name,last_name,joined_at,last_seen FROM users ORDER BY user_id"):
            w.writerow(list(r))
    return out.getvalue().encode("utf-8-sig")

# ============================================================
# CACHE / LOCKS
# ============================================================
CACHE = {}
CACHE_LOCK = threading.Lock()
CACHE_MAX = 100
USER_LOCKS = {}
USER_LOCKS_GUARD = asyncio.Lock()

def cache_key(*parts):
    return hashlib.sha256("\n---\n".join(str(x or "") for x in parts).encode()).hexdigest()

def cache_get(k):
    with CACHE_LOCK:
        return CACHE.get(k)

def cache_put(k, v):
    with CACHE_LOCK:
        if len(CACHE) >= CACHE_MAX:
            CACHE.pop(next(iter(CACHE)))
        CACHE[k] = v

async def user_lock(user_id):
    async with USER_LOCKS_GUARD:
        if user_id not in USER_LOCKS:
            USER_LOCKS[user_id] = asyncio.Lock()
        return USER_LOCKS[user_id]

# ============================================================
# KEYBOARDS
# ============================================================
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["✍️ Keyingi esseni tekshirish", "📊 Statistikam"],
    ["👨‍💼 Admin bilan bog‘lanish", "⚠️ Bot kamchiliklari haqida xabar berish"],
    ["📚 Esse qanday yoziladi?"],
], resize_keyboard=True)

ADMIN_KEYBOARD = ReplyKeyboardMarkup([
    ["📈 Umumiy statistika", "📢 Reklama yuborish"],
    ["👥 Foydalanuvchilar CSV", "🧪 Test holati"],
    ["⬅️ Oddiy menyu"],
], resize_keyboard=True)

# ============================================================
# BASIC / SCORING HELPERS
# ============================================================
def word_count(text):
    return len(re.findall(r"\S+", text or "", flags=re.UNICODE))

def full_cyrillic(text):
    letters = re.findall(r"[A-Za-zА-Яа-яЁёҚқҒғҲҳЎў]", text or "")
    if not letters:
        return False
    cyr = re.findall(r"[А-Яа-яЁёҚқҒғҲҳЎў]", text or "")
    return len(cyr) / len(letters) >= 0.98

def score_errors(n):
    n = max(0, int(n))
    return 2.0 if n == 0 else 1.5 if n <= 2 else 1.0 if n <= 4 else 0.5 if n <= 6 else 0.0

def clamp_half(x):
    x = max(0.0, min(2.0, float(x)))
    return round(x * 2) / 2

def set_score(item, score):
    item["score"] = clamp_half(score)

def clean_json(raw):
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()

def validate_ai(data):
    scores = data.get("scores")
    if not isinstance(scores, list) or len(scores) != 12:
        raise ValueError("12 mezon qaytmadi")
    ids = {int(x.get("criterion")) for x in scores}
    if ids != set(range(1,13)):
        raise ValueError("Mezonlar 1-12 bo'lishi kerak")
    for x in scores:
        if float(x.get("score",0)) not in {0,0.5,1,1.5,2}:
            raise ValueError("Noto'g'ri ball")

def apply_deterministic_rules(data, essay, topic):
    data.setdefault("status", "normal")
    data["word_count"] = word_count(essay)
    by = {int(x["criterion"]): x for x in data["scores"]}

    # Error-count criteria are always deterministic.
    for c in (5,7,8,9,10,12):
        n = max(0, int(by[c].get("error_count", 0)))
        by[c]["error_count"] = n
        set_score(by[c], score_errors(n))

    rep = max(0, int(by[6].get("repetition_count", 0)))
    coherent = bool(by[6].get("coherence_intact", True))
    by[6]["repetition_count"] = rep
    by[6]["coherence_intact"] = coherent
    if rep == 0 and coherent: set_score(by[6], 2)
    elif rep <= 2 and coherent: set_score(by[6], 1.5)
    elif 3 <= rep <= 4 and not coherent: set_score(by[6], 1)
    elif 5 <= rep <= 6 and not coherent: set_score(by[6], 0.5)
    elif rep >= 7 and not coherent: set_score(by[6], 0)
    else: set_score(by[6], 1.0 if rep >= 3 else 1.5)

    # Extra rule flags are explicitly requested from the model.
    flags = data.get("flags") or {}
    data["flags"] = flags

    # Missing conclusion / incomplete parts -> criteria 4 and 5 down by 1.
    if flags.get("missing_conclusion") or flags.get("incomplete_section"):
        set_score(by[4], by[4]["score"] - 1)
        set_score(by[5], by[5]["score"] - 1)
        by[4].setdefault("examples", []).append("XULOSA TO'LIQ EMAS")

    # Intro copies the topic verbatim.
    if flags.get("intro_copies_topic"):
        set_score(by[4], by[4]["score"] - 1)
        set_score(by[5], by[5]["score"] - 1)
        by[4].setdefault("examples", []).append("KIRISH MAVZUNI SO'ZMA-SO'Z TAKRORLAGAN")

    # Paragraph structure.
    if flags.get("paragraph_structure_problem"):
        set_score(by[5], by[5]["score"] - 0.5)

    # Style deviation.
    if flags.get("artistic_poetic_style"):
        set_score(by[1], 1)
        by[1].setdefault("reason", "")
        by[1]["reason"] += " Publitsistik uslubdan chetlashilgan."

    # Dialect: requested effect on criteria 1 and 12.
    dialect_count = int(flags.get("dialect_count", 0) or 0)
    if dialect_count > 0:
        set_score(by[12], by[12]["score"] - 1)
        set_score(by[1], by[1]["score"] - 1)

    # Fewer than 2 reasons for either view -> criterion 2 = 1.
    left_args = int(flags.get("view1_reason_count", 0) or 0)
    right_args = int(flags.get("view2_reason_count", 0) or 0)
    if left_args < 2 or right_args < 2:
        set_score(by[2], 1)
        by[2]["reason"] = (by[2].get("reason", "") + " Asosiy qarashlardan kamida birida 2 ta aniq sabab/argument yetarli emas.").strip()

    # Evidence rule.
    evidence = str(flags.get("evidence_status", "none"))
    if evidence == "both": set_score(by[3], 2)
    elif evidence == "one": set_score(by[3], 1.5)
    elif evidence == "irrelevant":
        set_score(by[3], by[3]["score"] - 1)
        set_score(by[6], by[6]["score"] - 0.5)

    # Off-topic sentences -> criterion 6. One sentence = 0.5 deduction.
    off_sent = int(flags.get("off_topic_sentence_count", 0) or 0)
    if off_sent > 0:
        set_score(by[6], by[6]["score"] - 0.5 * off_sent)

    # Bad proverb/idiom: affects 6 and 11.
    bad_idiom = int(flags.get("bad_proverb_idiom_count", 0) or 0)
    if bad_idiom > 0:
        set_score(by[6], by[6]["score"] - 0.5 * bad_idiom)
        set_score(by[11], by[11]["score"] - 0.5 * bad_idiom)

    # Lexical variety: 2 is exceptional. Model must show qualifying examples.
    lexical_examples = data.get("lexical_examples") or []
    if by[11]["score"] == 2 and len(lexical_examples) < 2:
        set_score(by[11], 1.5)
        by[11]["reason"] = "Leksik xilma-xillik yetarli darajada aniq dalillanmadi; 2 ball uchun yetarli asos yo'q."

    # Conclusion must support one of two views.
    conclusion = str(flags.get("conclusion_position", "unknown"))
    if conclusion in {"both_correct", "off_topic", "unknown"} and flags.get("conclusion_present", True):
        set_score(by[4], by[4]["score"] - 1)
        set_score(by[6], by[6]["score"] - 1)
        by[4]["reason"] = (by[4].get("reason", "") + " Xulosada ikki qarashdan birini aniq qo'llab-quvvatlash talabi bajarilmagan.").strip()

    # Personal opinion in wrong sections: only a documented penalty, not removal of criterion 2.
    if flags.get("personal_opinion_in_intro_or_body"):
        set_score(by[1], by[1]["score"] - 0.5)
        set_score(by[6], by[6]["score"] - 0.5)

    # Special cases from the source rubric. Empty essay must be checked first.
    if not essay.strip():
        data["status"] = "special_case"; data["special_reason"] = "Esse yozilmagan."; data["total"] = 0.0; return data
    if full_cyrillic(essay):
        data["status"] = "special_case"; data["special_reason"] = "Esse matni to'liq kirill alifbosida yozilgan."; data["total"] = 0.0; return data
    if data.get("only_introduction"):
        data["status"] = "special_case"; data["special_reason"] = "Faqat kirish qismi yozilgan."; data["total"] = 0.0; return data
    if data.get("off_topic"):
        data["status"] = "special_case"; data["special_reason"] = "Esse mavzuga mos emas."; data["total"] = 2.0; return data
    if data.get("copied_with_evidence"):
        data["status"] = "special_case"; data["special_reason"] = "Esse boshqa manbadan ko'chirilganligi ishonchli aniqlandi."; data["total"] = 2.0; return data
    if data["word_count"] < 100:
        data["status"] = "special_case"
        data["special_reason"] = "Esse hajmi 100 ta so'zdan kam."
        data["total"] = 2.0
        return data
    data["scores"] = sorted(by.values(), key=lambda x: int(x["criterion"]))
    data["total"] = round(sum(float(x["score"]) for x in data["scores"]), 1)
    return data

# ============================================================
# 75-BALL MAPPING: 24 -> 75, 23.5 -> 74, ...
# ============================================================
def to_75(total24):
    return int(round(27 + 2 * float(total24)))

# ============================================================
# OPENAI EVALUATION
# ============================================================
def eval_schema_prompt(topic, essay):
    return f'''
MAVZU/VAZIYAT:
{topic}

ESSE:
{essay}

So'z soni dastur bo'yicha: {word_count(essay)}

Faqat JSON qaytaring. Har bir xatoni so'zma-so'z ko'rsating.
Xato obyektlari: {{"wrong":"...", "correct":"...", "explanation":"...", "type":"imlo|punktuatsiya|qo'shimcha|so'z|12-mezon"}}

JSON SHAKLI:
{{
 "off_topic": false,
 "copied_with_evidence": false,
 "only_introduction": false,
 "flags": {{
   "missing_conclusion": false,
   "incomplete_section": false,
   "intro_copies_topic": false,
   "paragraph_structure_problem": false,
   "artistic_poetic_style": false,
   "dialect_count": 0,
   "view1_reason_count": 0,
   "view2_reason_count": 0,
   "evidence_status": "both|one|irrelevant|none",
   "off_topic_sentence_count": 0,
   "bad_proverb_idiom_count": 0,
   "conclusion_present": true,
   "conclusion_position": "view1|view2|both_correct|off_topic|unknown",
   "personal_opinion_in_intro_or_body": false
 }},
 "lexical_examples": [],
 "scores": [
  {{"criterion":1,"name":"Publitsistik uslub","score":0,"reason":"","examples":[],"errors":[]}},
  {{"criterion":2,"name":"Ikkala qarash va shaxsiy qarash","score":0,"reason":"","examples":[],"errors":[]}},
  {{"criterion":3,"name":"Dalillash","score":0,"reason":"","examples":[],"errors":[]}},
  {{"criterion":4,"name":"Kirish, asosiy qism, xulosa","score":0,"reason":"","examples":[],"errors":[]}},
  {{"criterion":5,"name":"Mantiqiy qurilish","score":0,"reason":"","error_count":0,"examples":[],"errors":[]}},
  {{"criterion":6,"name":"Izchillik","score":0,"reason":"","repetition_count":0,"coherence_intact":true,"examples":[],"errors":[]}},
  {{"criterion":7,"name":"Imlo","score":0,"reason":"","error_count":0,"examples":[],"errors":[]}},
  {{"criterion":8,"name":"Punktuatsiya","score":0,"reason":"","error_count":0,"examples":[],"errors":[]}},
  {{"criterion":9,"name":"Qo'shimcha qo'llash","score":0,"reason":"","error_count":0,"examples":[],"errors":[]}},
  {{"criterion":10,"name":"So'z qo'llash","score":0,"reason":"","error_count":0,"examples":[],"errors":[]}},
  {{"criterion":11,"name":"Leksik xilma-xillik","score":0,"reason":"","examples":[],"errors":[]}},
  {{"criterion":12,"name":"Sheva/vulgarizm/varvarizm/parazit","score":0,"reason":"","error_count":0,"examples":[],"errors":[]}}
 ],
 "summary":"",
 "improvements":[]
}}

QAT'IY:
- 12 mezon to'liq bo'lsin.
- 5,7,8,9,10,12 uchun faqat real xatolarni sanang.
- 6 uchun repetition_count va coherence_intact ni belgilang.
- Imlo/qo'shimcha/so'z xatosini norma bilan asoslang; taxmin qilmang.
- Bir xatoni ikki marta sanamang.
- 2/2 faqat to'liq dalil bilan.
- Leksik 2 ball juda kam; kamida 2 ta aniq, yaxshi ishlatilgan birlik ko'rsatilmasa 1.5 yoki past.
- Xulosa ikki qarashdan birini tanlab qo'llab-quvvatlaydimi — albatta tekshiring.
'''

async def openai_json(input_payload):
    try:
        r = await asyncio.to_thread(client.responses.create, model=MODEL, input=input_payload)
    except AuthenticationError as e:
        raise RuntimeError("OPENAI_API_KEY noto'g'ri yoki faol emas.") from e
    except RateLimitError as e:
        raise RuntimeError("OpenAI API limiti/krediti bilan muammo bor.") from e
    except BadRequestError as e:
        raise RuntimeError(f"OpenAI so'rovi rad etildi: {e}") from e
    except APIError as e:
        raise RuntimeError("OpenAI API texnik xatosi yuz berdi.") from e
    raw = clean_json(r.output_text)
    if not raw:
        raise RuntimeError("OpenAI bo'sh javob qaytardi.")
    try:
        data = json.loads(raw)
        validate_ai(data)
        return data
    except Exception as e:
        logger.exception("JSON parse/validation failed: %s", raw[:2000])
        raise RuntimeError("AI javobi noto'g'ri formatda qaytdi.") from e

async def evaluate_text(topic, essay):
    k = cache_key("text", topic, essay, MODEL)
    old = cache_get(k)
    if old: return old
    data = await openai_json([{"role":"system","content":RUBRIC},{"role":"user","content":eval_schema_prompt(topic,essay)}])
    data = apply_deterministic_rules(data, essay, topic)
    cache_put(k, data)
    return data

async def evaluate_image(topic, image_bytes):
    k = cache_key("image", topic, hashlib.sha256(image_bytes).hexdigest(), MODEL)
    old = cache_get(k)
    if old: return old
    import base64
    b64 = base64.b64encode(image_bytes).decode()
    prompt = eval_schema_prompt(topic, "[ESSENING MATNI RASMDAN O'QILADI]") + "\nRasmdagi qo'lda yozilgan matnni avval transcription maydonida to'liq yozing. Ko'rinmagan so'zni o'ylab topmang."
    payload = [{"role":"system","content":RUBRIC},{"role":"user","content":[
        {"type":"input_text","text":prompt},
        {"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"}
    ]}]
    data = await openai_json(payload)
    transcription = str(data.get("transcription") or data.get("essay_text") or "")
    if not transcription:
        # Ask for transcription in the same response is preferred; if absent, use the available text field.
        transcription = str(data.get("text") or "")
    data["transcription"] = transcription
    data = apply_deterministic_rules(data, transcription, topic)
    data["_image_mode"] = True
    cache_put(k, data)
    return data

# ============================================================
# IMAGE HELPERS / BBA STYLE RESULT
# ============================================================
def font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for p in paths:
        if os.path.exists(p): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def wrap(draw, text, f, width):
    text = str(text or "")
    out=[]; cur=""
    for w in text.split():
        test = w if not cur else cur+" "+w
        if draw.textbbox((0,0),test,font=f)[2] <= width: cur=test
        else:
            if cur: out.append(cur)
            cur=w
    if cur: out.append(cur)
    return out or [""]

def load_emblem(size=90):
    if not os.path.exists(EMBLEM_PATH): return None
    try:
        im=Image.open(EMBLEM_PATH).convert("RGBA")
        im.thumbnail((size,size),Image.LANCZOS)
        return im
    except Exception:
        return None

def draw_rounded_text(draw, xy, text, f, fill, max_width):
    return wrap(draw,text,f,max_width)

def make_result_image(data):
    W=1400; M=70
    green=(27,126,83); dark=(35,55,47); pale=(235,248,241); mint=(246,252,248); gray=(96,110,104); white=(255,255,255)
    title=font(46,True); sub=font(25); big=font(76,True); crit=font(25,True); body=font(21); small=font(18)
    d0=Image.new("RGB",(W,500),white); dd=ImageDraw.Draw(d0)
    y=35
    emb=load_emblem(88)
    if emb:
        d0.paste(emb,(M,y),emb); title_x=M+105
    else: title_x=M
    dd.text((title_x,y+5),"Esse baholovchi bot",font=title,fill=green)
    y=118
    for line in wrap(dd,"Sizning essyeingiz BBA nizomi bo‘yicha tekshirildi va quyidagi natija aniqlandi:",sub,W-2*M):
        dd.text((M,y),line,font=sub,fill=dark); y+=35
    # score card
    y+=20
    dd.rounded_rectangle((M,y,W-M,y+170),radius=30,fill=pale)
    total=float(data.get("total",0)); eq=to_75(total)
    dd.text((M+35,y+25),f"{total:g} /24",font=big,fill=green)
    dd.text((M+40,y+112),"YAKUNIY BALL",font=crit,fill=dark)
    dd.text((W-360,y+45),f"{eq} /75",font=font(54,True),fill=green)
    dd.text((W-360,y+112),"75 ballik ekvivalent",font=small,fill=gray)
    # meta
    meta=f"So‘zlar soni: {int(data.get('word_count',0))}   •   Holat: {'maxsus' if data.get('status')=='special_case' else 'oddiy'}"
    dd.text((M,y+195),meta,font=small,fill=gray)

    rows=[]
    for item in sorted(data.get("scores",[]), key=lambda x:int(x["criterion"])):
        c=int(item["criterion"]); sc=float(item.get("score",0)); name=CRITERION_NAMES.get(c,item.get("name",f"Mezon {c}"))
        rows.append((c,name,sc,item))
    # two-column criterion cards
    card_w=(W-2*M-30)//2
    row_h=145
    y+=240
    cards_h=((len(rows)+1)//2)*row_h
    total_h=y+cards_h+520
    img=Image.new("RGB",(W,total_h),mint); d=ImageDraw.Draw(img)
    # header copy
    if emb: img.paste(emb,(M,35),emb); d.text((M+105,48),"Esse baholovchi bot",font=title,fill=green)
    else: d.text((M,48),"Esse baholovchi bot",font=title,fill=green)
    yy=135
    for line in wrap(d,"Sizning essyeingiz BBA nizomi bo‘yicha tekshirildi va quyidagi natija aniqlandi:",sub,W-2*M):
        d.text((M,yy),line,font=sub,fill=dark); yy+=35
    yy+=15
    d.rounded_rectangle((M,yy,W-M,yy+165),radius=30,fill=pale)
    d.text((M+35,yy+22),f"{total:g} /24",font=big,fill=green)
    d.text((M+40,yy+108),"YAKUNIY BALL",font=crit,fill=dark)
    d.text((W-360,yy+40),f"{eq} /75",font=font(54,True),fill=green)
    d.text((W-360,yy+108),"75 ballik ekvivalent",font=small,fill=gray)
    yy+=195
    d.text((M,yy),f"So‘zlar soni: {int(data.get('word_count',0))}",font=small,fill=gray); yy+=40
    for idx,(c,name,sc,item) in enumerate(rows):
        col=idx%2; r=idx//2
        x=M+col*(card_w+30); cy=yy+r*row_h
        d.rounded_rectangle((x,cy,x+card_w,cy+row_h-15),radius=20,fill=white,outline=(213,229,220),width=2)
        d.text((x+18,cy+15),f"{c}. {name}",font=crit,fill=dark)
        d.text((x+card_w-90,cy+15),f"{sc:g}/2",font=crit,fill=green)
        reason=str(item.get("reason","")).strip()
        if reason:
            lines=wrap(d,reason,body,card_w-36)[:3]
            ty=cy+55
            for line in lines:
                d.text((x+18,ty),line,font=body,fill=gray); ty+=28
        if c in (5,7,8,9,10,12):
            d.text((x+18,cy+row_h-48),f"Xatolar: {int(item.get('error_count',0))}",font=small,fill=gray)
        if c==6:
            d.text((x+card_w-230,cy+row_h-48),f"Takror: {int(item.get('repetition_count',0))}",font=small,fill=gray)
    yy=yy+cards_h+20
    # Error list
    d.rounded_rectangle((M,yy,W-M,yy+350),radius=25,fill=white)
    d.text((M+25,yy+22),"ANIQLANGAN XATOLAR",font=crit,fill=green)
    errors=[]
    for item in rows:
        for e in item[3].get("errors",[]) or []:
            if isinstance(e,dict): errors.append((item[0],e))
    if errors:
        ty=yy+65
        for c,e in errors[:18]:
            line=f"{c}-mezon: XATO: {e.get('wrong','—')} → TO‘G‘RISI: {e.get('correct','—')}"
            for ln in wrap(d,line,small,W-2*M-50)[:2]:
                d.text((M+25,ty),ln,font=small,fill=dark); ty+=25
            if ty>yy+320: break
    else:
        d.text((M+25,yy+75),"Aniq xatolar ro‘yxati qayd etilmadi.",font=body,fill=gray)
    yy+=380
    d.rounded_rectangle((M,yy,W-M,yy+190),radius=25,fill=pale)
    d.text((M+25,yy+20),"UMUMIY XULOSA",font=crit,fill=green)
    ty=yy+62
    for ln in wrap(d,data.get("summary",""),body,W-2*M-50)[:4]:
        d.text((M+25,ty),ln,font=body,fill=dark); ty+=27
    yy+=220
    d.rounded_rectangle((M,yy,W-M,yy+190),radius=25,fill=white)
    d.text((M+25,yy+20),"YAXSHILASH UCHUN",font=crit,fill=green)
    ty=yy+62
    for imp in (data.get("improvements") or [])[:4]:
        for ln in wrap(d,"• "+str(imp),body,W-2*M-50)[:2]:
            d.text((M+25,ty),ln,font=body,fill=dark); ty+=27
    yy+=220
    d.text((M,yy),"BILIMNI BAHOLASH AGENTLIGI",font=font(24,True),fill=green)
    d.text((M,yy+35),"SIFAT • ADOLAT • NATIJA",font=small,fill=gray)
    out=io.BytesIO(); out.name="esse_natijasi.jpg"; img.save(out,"JPEG",quality=92,optimize=True); out.seek(0); return out

# ============================================================
# STATISTICS IMAGE — OLD PROFESSIONAL STYLE
# ============================================================
def make_stats_image(user_id):
    s,last,prev=stats_for_user(user_id)
    n=int(s.get("n") or 0); avg=float(s.get("avg") or 0); hi=s.get("hi"); lo=s.get("lo"); text_n=int(s.get("text_n") or 0); image_n=int(s.get("image_n") or 0)
    last_v=float(last["total"]) if last else None; prev_v=float(prev["total"]) if prev else None
    if last_v is None or prev_v is None: trend="→ O‘zgarmagan"
    elif last_v>prev_v: trend=f"↑ +{last_v-prev_v:g} ball"
    elif last_v<prev_v: trend=f"↓ {last_v-prev_v:g} ball"
    else: trend="→ O‘zgarmagan"
    W,H=1200,900
    bg=(248,252,249); green=(27,116,76); dark=(42,57,50); light=(226,244,235); grid=(205,225,214); gray=(105,120,112)
    img=Image.new("RGB",(W,H),bg); d=ImageDraw.Draw(img)
    d.rounded_rectangle((35,30,W-35,H-35),radius=36,fill=(255,255,255),outline=(220,234,225),width=2)
    d.text((80,70),"Esse natijalari statistikasi",font=font(44,True),fill=dark)
    d.text((80,130),f"Tekshirilgan esse: {n} ta",font=font(27),fill=green)
    d.text((80,180),f"O‘rtacha: {avg:.1f}/24",font=font(25,True),fill=dark)
    d.text((420,180),f"Oxirgi: {last_v:g}/24" if last_v is not None else "Oxirgi: —",font=font(25,True),fill=dark)
    d.text((850,180),trend,font=font(23,True),fill=green if trend.startswith(("↑","→")) else (180,80,70))
    # Graph panel
    gx,gy,gw,gh=80,250,1040,500
    d.rounded_rectangle((gx,gy,gx+gw,gy+gh),radius=28,fill=light)
    left=gx+90; right=gx+gw-50; top=gy+45; bottom=gy+gh-70
    for val in [0,6,12,18,24]:
        y=bottom-(val/24)*(bottom-top)
        d.line((left,y,right,y),fill=grid,width=2)
        d.text((gx+35,y-12),str(val),font=font(18),fill=gray)
    if n:
        # Plot last 20 user results in chronological order.
        with DB_LOCK, db() as c:
            rows=list(c.execute("SELECT total FROM checks WHERE user_id=? ORDER BY id DESC LIMIT 20",(user_id,)))
        vals=[float(r[0]) for r in reversed(rows)]
        step=(right-left)/max(1,len(vals)-1)
        pts=[]
        for i,v in enumerate(vals):
            x=left+i*step; y=bottom-(v/24)*(bottom-top); pts.append((x,y))
        if len(pts)>1: d.line(pts,fill=green,width=5)
        for i,(x,y) in enumerate(pts):
            d.ellipse((x-9,y-9,x+9,y+9),fill=green)
            d.text((x-7,y-38),str(i+1),font=font(16,True),fill=dark)
    d.text((80,785),f"Eng yuqori: {hi:g}/24" if hi is not None else "Eng yuqori: —",font=font(22),fill=dark)
    d.text((350,785),f"Eng past: {lo:g}/24" if lo is not None else "Eng past: —",font=font(22),fill=dark)
    d.text((80,830),"BBA uslubidagi rasmiy kuzatuv grafigi",font=font(18),fill=gray)
    out=io.BytesIO(); out.name="statistika.jpg"; img.save(out,"JPEG",quality=92,optimize=True); out.seek(0); return out

def make_admin_stats_image():
    total,text_n,image_n,users,avg=global_stats()
    W,H=1100,650; bg=(248,252,249); green=(27,116,76); dark=(42,57,50); light=(226,244,235)
    img=Image.new("RGB",(W,H),bg); d=ImageDraw.Draw(img)
    d.rounded_rectangle((30,25,W-30,H-25),radius=35,fill="white",outline=(220,234,225),width=2)
    d.text((70,65),"Admin — Esse natijalari statistikasi",font=font(38,True),fill=dark)
    vals=[("Jami tekshiruv",total),("Matnli",text_n),("Rasmli",image_n),("Foydalanuvchi",users),("O‘rtacha",f"{avg:.1f}/24")]
    y=145
    for label,val in vals:
        d.rounded_rectangle((70,y,W-70,y+75),radius=18,fill=light)
        d.text((95,y+20),label,font=font(24,True),fill=dark)
        d.text((W-300,y+18),str(val),font=font(27,True),fill=green); y+=90
    out=io.BytesIO(); out.name="admin_statistika.jpg"; img.save(out,"JPEG",quality=92); out.seek(0); return out

# ============================================================
# TELEGRAM SENDERS
# ============================================================
async def send_result(message, data):
    img=await asyncio.to_thread(make_result_image,data)
    caption=f"📊 {float(data.get('total',0)):g}/24  •  75 ballik ekvivalent: {to_75(data.get('total',0))}/75"
    await message.reply_photo(photo=InputFile(img,filename="esse_natijasi.jpg"),caption=caption)

async def send_user_stats(message,user_id):
    img=await asyncio.to_thread(make_stats_image,user_id)
    await message.reply_photo(photo=InputFile(img,filename="statistika.jpg"),caption="📊 Statistikangiz")

# ============================================================
# ADMIN
# ============================================================
async def is_admin(update):
    return bool(update.effective_user and update.effective_user.id==ADMIN_ID)

async def admin_cmd(update,context):
    if not await is_admin(update):
        await update.message.reply_text("⛔ Bu bo‘lim faqat admin uchun.",reply_markup=MAIN_KEYBOARD); return
    context.user_data.clear(); context.user_data["admin_mode"]=True
    await update.message.reply_text("👨‍💼 Admin paneli\nKerakli amalni tanlang.",reply_markup=ADMIN_KEYBOARD)

async def admin_broadcast_text(bot, text):
    with DB_LOCK, db() as c:
        ids=[r[0] for r in c.execute("SELECT user_id FROM users")]
    ok=bad=0
    for uid in ids:
        try:
            await bot.send_message(uid,text)
            ok+=1
        except Exception:
            bad+=1
    return ok,bad

async def admin_broadcast_photo(bot, photo_bytes, caption):
    with DB_LOCK, db() as c:
        ids=[r[0] for r in c.execute("SELECT user_id FROM users")]
    ok=bad=0
    for uid in ids:
        try:
            await bot.send_photo(uid,photo=InputFile(io.BytesIO(photo_bytes),filename="reklama.jpg"),caption=caption[:1024])
            ok+=1
        except Exception:
            bad+=1
    return ok,bad

# ============================================================
# COMMANDS / HANDLERS
# ============================================================
async def start(update,context):
    upsert_user(update.effective_user)
    context.user_data.clear()
    await update.message.reply_text("Assalomu alaykum! 👋\n\nMen ONA TILI VA ADABIYOT esse tekshiruvchi botman.\nBaholash 24 ballik Basirat nizomi va qo‘shimcha qat’iy qoidalar asosida amalga oshiriladi.",reply_markup=MAIN_KEYBOARD)

async def new_cmd(update,context):
    upsert_user(update.effective_user); context.user_data.clear(); context.user_data["stage"]="topic"
    await update.message.reply_text("📝 Mavzu/vaziyatni yuboring.",reply_markup=MAIN_KEYBOARD)

async def help_cmd(update,context):
    await update.message.reply_text("📚 1) Mavzu/vaziyat.\n2) Esse matni yoki rasm.\n3) Natija bitta BBA uslubidagi rasmda.\n\n12 mezon • 24 ball • 75 ballik ekvivalent.",reply_markup=MAIN_KEYBOARD)

async def handle_photo(update,context):
    upsert_user(update.effective_user)
    if context.user_data.get("admin_mode") and await is_admin(update):
        if context.user_data.get("admin_action")=="broadcast_photo":
            try:
                p=update.message.photo[-1]
                f=await context.bot.get_file(p.file_id); b=io.BytesIO(); await f.download_to_memory(b)
                context.user_data["broadcast_photo_bytes"]=b.getvalue(); context.user_data["admin_action"]="broadcast_caption"
                await update.message.reply_text("Rasm qabul qilindi. Endi reklama matnini yuboring.",reply_markup=ADMIN_KEYBOARD)
            except Exception as e: await update.message.reply_text(f"Xatolik: {e}",reply_markup=ADMIN_KEYBOARD)
            return
    if context.user_data.get("stage")!="essay":
        await update.message.reply_text("Avval «✍️ Keyingi esseni tekshirish» tugmasini bosing.",reply_markup=MAIN_KEYBOARD); return
    lock=await user_lock(update.effective_user.id)
    if lock.locked(): await update.message.reply_text("⏳ Oldingi tekshiruv tugamadi."); return
    async with lock:
        status=await update.message.reply_text("⏳ Rasm o‘qilmoqda va tekshirilmoqda...")
        try:
            file_id=update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
            f=await context.bot.get_file(file_id); b=io.BytesIO(); await f.download_to_memory(b)
            topic=context.user_data.get("topic","")
            result=await evaluate_image(topic,b.getvalue())
            save_check(update.effective_user.id,"image",topic,result.get("total",0),result.get("word_count",0),result.get("status","normal"))
            await send_result(update.message,result)
            context.user_data.clear(); await status.edit_text("✅ Tekshiruv tugadi.")
        except Exception as e:
            logger.exception("image error"); await status.edit_text(f"⚠️ {e}"); context.user_data.clear()

async def handle_text(update,context):
    upsert_user(update.effective_user)
    text=(update.message.text or "").strip()
    if not text: return

    # Admin panel
    if await is_admin(update):
        if text=="/admin":
            await admin_cmd(update,context); return
        if context.user_data.get("admin_mode"):
            action=context.user_data.get("admin_action")
            if text=="⬅️ Oddiy menyu":
                context.user_data.clear(); await update.message.reply_text("Oddiy menyu.",reply_markup=MAIN_KEYBOARD); return
            if text=="📈 Umumiy statistika":
                img=await asyncio.to_thread(make_admin_stats_image); await update.message.reply_photo(InputFile(img,filename="admin_statistika.jpg"),reply_markup=ADMIN_KEYBOARD); return
            if text=="👥 Foydalanuvchilar CSV":
                await update.message.reply_document(InputFile(io.BytesIO(users_csv_bytes()),filename="users.csv"),caption="Foydalanuvchilar ro‘yxati",reply_markup=ADMIN_KEYBOARD); return
            if text=="🧪 Test holati":
                await update.message.reply_text(f"✅ Bot ishlayapti.\nModel: {MODEL}\nAdmin ID: {ADMIN_ID}\nDB: {DB_PATH}",reply_markup=ADMIN_KEYBOARD); return
            if text=="📢 Reklama yuborish":
                context.user_data["admin_action"]="broadcast_choose"
                await update.message.reply_text("Reklama turi: «matn» yoki «rasm» deb yozing.",reply_markup=ADMIN_KEYBOARD); return
            if action=="broadcast_choose":
                if text.lower() in ("matn","text"):
                    context.user_data["admin_action"]="broadcast_text"
                    await update.message.reply_text("Barcha foydalanuvchilarga yuboriladigan matnni yozing.",reply_markup=ADMIN_KEYBOARD); return
                if text.lower() in ("rasm","photo"):
                    context.user_data["admin_action"]="broadcast_photo"
                    await update.message.reply_text("Reklama rasmini yuboring.",reply_markup=ADMIN_KEYBOARD); return
            if action=="broadcast_text":
                ok,bad=await admin_broadcast_text(context.bot,text); context.user_data["admin_action"]=None
                await update.message.reply_text(f"📢 Reklama yuborildi.\nYetib borgan: {ok}\nXato: {bad}",reply_markup=ADMIN_KEYBOARD); return
            if action=="broadcast_caption":
                b=context.user_data.pop("broadcast_photo_bytes",None); ok,bad=await admin_broadcast_photo(context.bot,b,text) if b else (0,0)
                context.user_data["admin_action"]=None
                await update.message.reply_text(f"📢 Rasmli reklama yuborildi.\nYetib borgan: {ok}\nXato: {bad}",reply_markup=ADMIN_KEYBOARD); return

    # Normal menu
    if text=="✍️ Keyingi esseni tekshirish":
        context.user_data.clear(); context.user_data["stage"]="topic"; await update.message.reply_text("📝 Mavzu/vaziyatni yuboring.",reply_markup=MAIN_KEYBOARD); return
    if text=="📊 Statistikam": await send_user_stats(update.message,update.effective_user.id); return
    if text=="👨‍💼 Admin bilan bog‘lanish":
        await update.message.reply_text(f"👨‍💼 Admin bilan bog‘lanish:\n{ADMIN_CONTACT_URL}",reply_markup=MAIN_KEYBOARD); return
    if text=="⚠️ Bot kamchiliklari haqida xabar berish":
        context.user_data["feedback_mode"]=True; await update.message.reply_text("Kamchilikni yozib yuboring.",reply_markup=MAIN_KEYBOARD); return
    if text=="📚 Esse qanday yoziladi?":
        await update.message.reply_text("📚 Kirish + asosiy qism + xulosa.\n• Ikki asosiy qarash\n• Har ikki qarashga kamida 2 ta aniq sabab\n• Har ikki qarashga mos dalil\n• Shaxsiy pozitsiya xulosada\n• Publitsistik uslub\n• Kamida 100 so‘z\n• Reja va epigraf yo‘q",reply_markup=MAIN_KEYBOARD); return
    if context.user_data.get("feedback_mode"):
        with DB_LOCK, db() as c:
            c.execute("INSERT INTO feedback(user_id,username,message,created_at) VALUES(?,?,?,?)",(update.effective_user.id,update.effective_user.username or "",text[:4000],now_iso())); c.commit()
        context.user_data.clear(); await update.message.reply_text("✅ Xabaringiz qabul qilindi.",reply_markup=MAIN_KEYBOARD); return

    stage=context.user_data.get("stage")
    if stage in (None,"topic"):
        context.user_data["topic"]=text; context.user_data["stage"]="essay"
        await update.message.reply_text("Mavzu qabul qilindi ✅\n\nEndi essening o‘zini matn yoki rasm ko‘rinishida yuboring.",reply_markup=MAIN_KEYBOARD); return
    if stage!="essay": return
    lock=await user_lock(update.effective_user.id)
    if lock.locked(): await update.message.reply_text("⏳ Oldingi tekshiruv tugamadi."); return
    async with lock:
        status=await update.message.reply_text("⏳ Esse tekshirilmoqda...")
        try:
            topic=context.user_data.get("topic","")
            result=await evaluate_text(topic,text)
            save_check(update.effective_user.id,"text",topic,result.get("total",0),result.get("word_count",word_count(text)),result.get("status","normal"))
            await send_result(update.message,result)
            context.user_data.clear(); await status.edit_text("✅ Tekshiruv tugadi.")
        except Exception as e:
            logger.exception("text error"); await status.edit_text(f"⚠️ Tekshiruvda xatolik: {e}"); context.user_data.clear()

# ============================================================
# HEALTH / MAIN
# ============================================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/plain; charset=utf-8"); self.end_headers(); self.wfile.write(b"Esse baholovchi bot ishlayapti.")
    def log_message(self,*args): pass

def start_health():
    ThreadingHTTPServer(("0.0.0.0",PORT),HealthHandler).serve_forever()

def main():
    init_db()
    threading.Thread(target=start_health,daemon=True).start()
    app=Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("new",new_cmd))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CommandHandler("admin",admin_cmd))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE,handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_text))
    logger.info("BOT STARTED | model=%s | admin=%s",MODEL,ADMIN_ID)
    app.run_polling(drop_pending_updates=True,close_loop=False)

if __name__=="__main__":
    main()
