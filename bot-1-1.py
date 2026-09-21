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
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ============================================================
# CONFIG
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
PORT = int(os.getenv("PORT", "10000"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1953416343"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Sardor_Sayfullayev777").lstrip("@").strip()
ADMIN_CONTACT_URL = os.getenv("ADMIN_CONTACT_URL", "https://t.me/Sardor_Sayfullayev777")
DB_PATH = os.getenv("BOT_DB_PATH", "esse_bot.sqlite3")
EMBLEM_PATH = os.getenv("EMBLEM_PATH", "emblem.png")
# Majburiy kanal obunasi
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@milliysertifikat_ona_tili1")
REQUIRED_CHANNEL_URL = os.getenv("REQUIRED_CHANNEL_URL", "https://t.me/milliysertifikat_ona_tili1")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN Render Environment Variables orqali berilishi kerak.")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY Render Environment Variables orqali berilishi kerak.")

client = OpenAI(api_key=OPENAI_API_KEY, timeout=120.0, max_retries=2)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("esse_baholovchi_bot")

# Telegram album (media group) yig‘ish
ALBUM_BUFFERS = {}
ALBUM_TASKS = {}
ALBUM_LOCK = asyncio.Lock()
ALBUM_WAIT_SECONDS = 1.2

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
N1) MUHIM: "xo‘sh" (shuningdek "xo'sh" yozilishi) kirish qismida ishlatilgani, hatto bir necha marta takrorlangani uchun ham o‘z-o‘zidan uslubiy yoki so‘z qo‘llash xatosi hisoblanmaydi. Uni 10-mezon yoki 12-mezon xatosi sifatida sanamang. Faqat boshqa mustaqil, aniq va kontekstga asoslangan sabab mavjud bo‘lsa alohida izoh bering; "xo‘sh" so‘zining mavjudligi yoki takrori buning o‘zi bilan ball kamaytirish uchun sabab emas.
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
        c.execute('''CREATE TABLE IF NOT EXISTS user_preferences(
            user_id INTEGER PRIMARY KEY,
            result_mode TEXT NOT NULL DEFAULT 'image',
            updated_at TEXT NOT NULL
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

def get_result_mode(user_id):
    with DB_LOCK, db() as c:
        row = c.execute("SELECT result_mode FROM user_preferences WHERE user_id=?", (user_id,)).fetchone()
    return (row[0] if row and row[0] in ("image", "text") else "image")

def set_result_mode(user_id, mode):
    mode = "text" if mode == "text" else "image"
    with DB_LOCK, db() as c:
        c.execute(
            "INSERT INTO user_preferences(user_id,result_mode,updated_at) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET result_mode=excluded.result_mode, updated_at=excluded.updated_at",
            (user_id, mode, now_iso())
        )
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
# MAJBURIY KANAL OBUNASI
# ============================================================
SUBSCRIPTION_TEXT = (
    "🔒 Botdan foydalanish uchun avval majburiy kanalga a’zo bo‘ling.\n\n"
    "📢 Kanalga a’zo bo‘lgach, «✅ A’zolikni tekshirish» tugmasini bosing."
)

def subscription_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanalga a’zo bo‘lish", url=REQUIRED_CHANNEL_URL)],
        [InlineKeyboardButton("✅ A’zolikni tekshirish", callback_data="check_subscription")],
    ])

async def is_subscribed(user_id, bot):
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        status = getattr(member, "status", "")
        if status in ("member", "administrator", "creator"):
            return True
        if status == "restricted":
            return bool(getattr(member, "is_member", False))
        return False
    except Exception:
        logger.exception("Subscription check failed for user=%s channel=%s", user_id, REQUIRED_CHANNEL)
        return False

async def require_subscription(update, context):
    user = update.effective_user
    if not user:
        return False
    if user.id == ADMIN_ID:
        return True
    if await is_subscribed(user.id, context.bot):
        return True
    message = update.effective_message
    if message:
        await message.reply_text(SUBSCRIPTION_TEXT, reply_markup=subscription_keyboard())
    return False

async def subscription_callback(update, context):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if user.id == ADMIN_ID or await is_subscribed(user.id, context.bot):
        try:
            await query.edit_message_text("✅ A’zolik tasdiqlandi! Endi botdan foydalanishingiz mumkin.")
        except Exception:
            pass
        await query.message.reply_text("Asosiy menyu ochildi.", reply_markup=MAIN_KEYBOARD)
    else:
        await query.answer("❌ Siz hali kanalga a’zo bo‘lmagansiz.", show_alert=True)

# ============================================================
# KEYBOARDS
# ============================================================
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["✍️ Keyingi esseni tekshirish", "📊 Statistikam"],
    ["🖼 Rasmli natija", "📝 Matnli natija"],
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

    # "xo‘sh" is a valid discourse marker in an introduction and must not
    # be counted as a stylistic/word-choice error merely because it occurs
    # repeatedly. Remove any AI-generated error entry that targets this word.
    def _norm_apostrophe(v):
        return str(v or "").strip().lower().replace("’", "'").replace("ʻ", "'").replace("`", "'")

    for item in data.get("scores", []) or []:
        c = int(item.get("criterion", 0) or 0)
        errs = item.get("errors") or []
        if c in (10, 12):
            kept = []
            removed = 0
            for err in errs:
                if isinstance(err, dict) and _norm_apostrophe(err.get("wrong")) in {"xo'sh", "xosh"}:
                    removed += 1
                    continue
                kept.append(err)
            item["errors"] = kept
            if removed:
                item["error_count"] = max(0, int(item.get("error_count", 0) or 0) - removed)
                item["reason"] = str(item.get("reason", "")).replace("xo‘sh", "").replace("xo'sh", "").strip()

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

    # STRICT EVIDENCE GATE: 2/2 requires two strong, topic-relevant evidence units
    # for EACH viewpoint. Merely giving reasons or generic claims is not evidence.
    evidence = str(flags.get("evidence_status", "none"))
    strong_v1 = int(flags.get("strong_evidence_view1_count", 0) or 0)
    strong_v2 = int(flags.get("strong_evidence_view2_count", 0) or 0)
    evidence_strong = bool(flags.get("evidence_strong", False))
    if evidence == "both" and evidence_strong and strong_v1 >= 2 and strong_v2 >= 2:
        set_score(by[3], 2)
    elif evidence in {"both", "one"}:
        set_score(by[3], 1.5)
        by[3]["reason"] = (by[3].get("reason", "") +
            " Har ikki qarash uchun 2 balga yetadigan aniq va mustahkam dalillar to‘liq tasdiqlanmadi.").strip()
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

    # Lexical variety: 2 is exceptional. Require at least 3 qualifying units
    # and an explicit strong-variety flag. Ordinary vocabulary/synonyms do not qualify.
    lexical_examples = data.get("lexical_examples") or []
    lexical_strong = bool(flags.get("lexical_strong", False))
    if not (by[11]["score"] == 2 and lexical_strong and len(lexical_examples) >= 3):
        if by[11]["score"] >= 2:
            set_score(by[11], 1.5)
        by[11]["reason"] = "Leksik xilma-xillik yetarli emas; 2 ball uchun kamida 3 ta aniq va o‘rinli leksik birlik dalillanishi kerak."

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
   "evidence_strong": false,
   "strong_evidence_view1_count": 0,
   "strong_evidence_view2_count": 0,
   "off_topic_sentence_count": 0,
   "bad_proverb_idiom_count": 0,
   "conclusion_present": true,
   "conclusion_position": "view1|view2|both_correct|off_topic|unknown",
   "personal_opinion_in_intro_or_body": false,
   "lexical_strong": false
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
- 3-mezon uchun 2/2 faqat har bir qarashga kamida 2 ta aniq, mustahkam, mavzuga bevosita mos dalil bo'lsa. Umumiy gap, sabab yoki taxmin dalil hisoblanmaydi.
- 11-mezon uchun 2/2 juda kam beriladi: kamida 3 ta aniq, o'rinli, sifatli leksik birlik (majoziy/termin/stabil ibora va h.k.) ko'rsatilishi va ular matnda to'g'ri ishlatilgani isbotlanishi shart.
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


async def evaluate_images(topic, images):
    """Bir nechta Telegram albom rasmini bitta esse sifatida tekshiradi."""
    import base64
    if not images:
        raise ValueError("Rasmlar topilmadi.")
    digest = hashlib.sha256()
    for b in images:
        digest.update(hashlib.sha256(b).digest())
    k = cache_key("images", topic, digest.hexdigest(), MODEL)
    old = cache_get(k)
    if old:
        return old
    content = [{"type":"input_text","text": eval_schema_prompt(topic, "[ESSE BIR NECHTA RASMDA BERILGAN]") + "\nRasmlar ketma-ket bitta essega tegishli. Barcha rasmlardagi matnni tartib bilan to‘liq transcription qiling. Rasmlar orasidagi gaplarni o‘zingizcha qo‘shmang."}]
    for b in images:
        b64 = base64.b64encode(b).decode()
        content.append({"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"})
    data = await openai_json([{"role":"system","content":RUBRIC},{"role":"user","content":content}])
    transcription = str(data.get("transcription") or data.get("essay_text") or data.get("text") or "")
    data["transcription"] = transcription
    data = apply_deterministic_rules(data, transcription, topic)
    data["_image_mode"] = True
    data["_image_count"] = len(images)
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

def _fit_lines(draw, text, f, width, max_lines=None):
    """Pixel-aware wrapping. Never draws text outside its card width."""
    lines = wrap(draw, str(text or ""), f, max(50, width))
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            last = lines[-1]
            while draw.textbbox((0, 0), last + "…", font=f)[2] > width and len(last) > 4:
                last = last[:-1].rstrip()
            lines[-1] = last + "…"
    return lines


def _error_lines(draw, error, f, width):
    wrong = str(error.get("wrong", "—"))
    correct = str(error.get("correct", "—"))
    explanation = str(error.get("explanation", "")).strip()
    return (
        _fit_lines(draw, f"XATO: {wrong}", f, width),
        _fit_lines(draw, f"TO‘G‘RISI: {correct}", f, width),
        _fit_lines(draw, f"IZOH: {explanation}", f, width) if explanation else []
    )


def make_result_image(data):
    """Detailed BBA-style result card with dynamic heights; text never overlaps."""
    W = 1400
    M = 64
    GAP = 28
    green = (27, 126, 83)
    dark = (35, 55, 47)
    pale = (232, 247, 239)
    mint = (246, 252, 248)
    gray = (92, 108, 101)
    red = (165, 73, 67)
    white = (255, 255, 255)
    border = (210, 229, 220)

    title = font(48, True)
    sub = font(25)
    score_f = font(76, True)
    eq_f = font(54, True)
    card_title = font(24, True)
    body = font(20)
    small = font(17)
    section_f = font(28, True)

    rows = sorted(data.get("scores", []), key=lambda x: int(x.get("criterion", 0)))
    total = float(data.get("total", 0))
    eq = to_75(total)
    words = int(data.get("word_count", 0))

    # ----- Build a clean header first -----
    header_h = 390
    header = Image.new("RGB", (W, header_h), mint)
    hd = ImageDraw.Draw(header)
    emb = load_emblem(100)
    if emb:
        header.paste(emb, (M, 34), emb)
        tx = M + 120
    else:
        tx = M
    hd.text((tx, 42), "Esse baholovchi bot", font=title, fill=green)
    intro = "Sizning essyeingiz BBA nizomi bo‘yicha tekshirildi va quyidagi natija aniqlandi:"
    iy = 112
    for ln in _fit_lines(hd, intro, sub, W - tx - M, 2):
        hd.text((tx, iy), ln, font=sub, fill=dark)
        iy += 34

    card_y = 205
    hd.rounded_rectangle((M, card_y, W - M, card_y + 150), radius=28, fill=pale)
    hd.text((M + 34, card_y + 18), f"{total:g} /24", font=score_f, fill=green)
    hd.text((M + 38, card_y + 103), "YAKUNIY BALL", font=card_title, fill=dark)
    hd.text((W - M - 300, card_y + 28), f"{eq} /75", font=eq_f, fill=green)
    hd.text((W - M - 300, card_y + 99), "75 ballik ekvivalent", font=small, fill=gray)
    hd.text((M, 365), f"So‘zlar soni: {words}", font=small, fill=gray)

    # ----- Prepare card content and heights -----
    card_w = (W - 2 * M - GAP) // 2
    card_specs = []
    for item in rows:
        c = int(item.get("criterion", 0))
        name = CRITERION_NAMES.get(c, item.get("name", f"Mezon {c}"))
        score = float(item.get("score", 0))
        reason = str(item.get("reason", "")).strip()
        examples = [str(x) for x in (item.get("examples") or []) if str(x).strip()]
        errs = [e for e in (item.get("errors") or []) if isinstance(e, dict)]

        # Content lines determine height; no fixed-height card is used.
        reason_lines = _fit_lines(hd, reason, body, card_w - 44, 7) if reason else []
        example_lines = []
        for ex in examples[:3]:
            example_lines.extend(_fit_lines(hd, "• " + ex, small, card_w - 44, 2))
        error_blocks = []
        for e in errs[:8]:
            a, b, c3 = _error_lines(hd, e, small, card_w - 44)
            error_blocks.append((a, b, c3))

        content_h = 68
        content_h += max(1, len(reason_lines)) * 27 if reason_lines else 0
        content_h += len(example_lines) * 23
        if error_blocks:
            content_h += 18
            for a, b, c3 in error_blocks:
                content_h += len(a) * 22 + len(b) * 22 + len(c3) * 22 + 8
        content_h += 42  # footer metadata
        card_h = max(145, min(620, content_h + 26))
        card_specs.append((c, name, score, item, reason_lines, example_lines, error_blocks, card_h))

    # Pair cards row-by-row, with row height equal to the taller card.
    pairs = []
    for i in range(0, len(card_specs), 2):
        left = card_specs[i]
        right = card_specs[i + 1] if i + 1 < len(card_specs) else None
        rh = max(left[-1], right[-1] if right else 0)
        pairs.append((left, right, rh))

    criteria_h = sum(rh + 24 for _, _, rh in pairs)

    # ----- Error summary section: all errors, word-for-word -----
    all_errors = []
    for spec in card_specs:
        c, _, _, item, _, _, _, _ = spec
        for e in item.get("errors", []) or []:
            if isinstance(e, dict):
                all_errors.append((c, e))
    error_h = 125
    if all_errors:
        for c, e in all_errors:
            a, b, c3 = _error_lines(hd, e, small, W - 2 * M - 60)
            error_h += (1 + len(a) + len(b) + len(c3)) * 22 + 18
        error_h = max(error_h, 180)

    # ----- Summary / improvements -----
    summary = str(data.get("summary", "")).strip()
    improvements = [str(x) for x in (data.get("improvements") or []) if str(x).strip()]
    summary_lines = _fit_lines(hd, summary, body, W - 2 * M - 50, 7) if summary else ["—"]
    improvement_lines = []
    for x in improvements[:8]:
        improvement_lines.extend(_fit_lines(hd, "• " + x, body, W - 2 * M - 50, 2))

    summary_h = 92 + max(1, len(summary_lines)) * 28
    improve_h = 92 + max(1, len(improvement_lines)) * 28
    footer_h = 100

    total_h = header_h + 20 + criteria_h + error_h + summary_h + improve_h + footer_h + 80
    img = Image.new("RGB", (W, total_h), mint)
    d = ImageDraw.Draw(img)
    img.paste(header, (0, 0))

    y = header_h + 20

    # ----- Criteria cards -----
    for left, right, rh in pairs:
        for col, spec in enumerate((left, right)):
            if not spec:
                continue
            c, name, score, item, reason_lines, example_lines, error_blocks, card_h = spec
            x = M + col * (card_w + GAP)
            cy = y
            d.rounded_rectangle((x, cy, x + card_w, cy + rh), radius=22, fill=white, outline=border, width=2)
            d.ellipse((x + 18, cy + 18, x + 42, cy + 42), fill=green)
            title_x = x + 54
            # Criterion title gets its own width; score gets a reserved area.
            title_w = card_w - 54 - 95
            title_lines = _fit_lines(d, f"{c}. {name}", card_title, title_w, 2)
            ty = cy + 14
            for ln in title_lines:
                d.text((title_x, ty), ln, font=card_title, fill=dark)
                ty += 28
            score_txt = f"{score:g}/2"
            sb = d.textbbox((0, 0), score_txt, font=card_title)
            d.text((x + card_w - 18 - (sb[2] - sb[0]), cy + 18), score_txt, font=card_title, fill=green)

            ty = cy + 58 + max(0, len(title_lines) - 1) * 25
            for ln in reason_lines:
                d.text((x + 18, ty), ln, font=body, fill=gray)
                ty += 27
            for ln in example_lines:
                d.text((x + 18, ty), ln, font=small, fill=gray)
                ty += 23

            if error_blocks:
                d.line((x + 18, ty + 2, x + card_w - 18, ty + 2), fill=border, width=1)
                ty += 12
                for a, b, c3 in error_blocks:
                    for ln in a:
                        d.text((x + 18, ty), ln, font=small, fill=red); ty += 22
                    for ln in b:
                        d.text((x + 18, ty), ln, font=small, fill=green); ty += 22
                    for ln in c3:
                        d.text((x + 18, ty), ln, font=small, fill=gray); ty += 22
                    ty += 6

            if c in (5, 7, 8, 9, 10, 12):
                meta = f"Xatolar soni: {int(item.get('error_count', 0) or 0)}"
            elif c == 6:
                meta = f"Fikr takrori: {int(item.get('repetition_count', 0) or 0)}"
            else:
                meta = ""
            if meta:
                d.text((x + 18, cy + rh - 34), meta, font=small, fill=gray)
        y += rh + 24

    # ----- Detailed error register -----
    d.rounded_rectangle((M, y, W - M, y + error_h), radius=25, fill=white)
    d.text((M + 25, y + 20), "ANIQLANGAN XATOLAR", font=section_f, fill=green)
    ty = y + 68
    if all_errors:
        for c, e in all_errors:
            if ty > y + error_h - 70:
                break
            a, b, c3 = _error_lines(d, e, small, W - 2 * M - 60)
            d.text((M + 25, ty), f"{c}-mezon", font=small, fill=dark); ty += 22
            for ln in a:
                if ty <= y + error_h - 35:
                    d.text((M + 45, ty), ln, font=small, fill=red); ty += 22
            for ln in b:
                if ty <= y + error_h - 35:
                    d.text((M + 45, ty), ln, font=small, fill=green); ty += 22
            for ln in c3:
                if ty <= y + error_h - 35:
                    d.text((M + 45, ty), ln, font=small, fill=gray); ty += 22
            ty += 8
    else:
        d.text((M + 25, y + 70), "Aniq xatolar ro‘yxati qayd etilmadi.", font=body, fill=gray)
    y += error_h + 24

    # ----- Summary -----
    d.rounded_rectangle((M, y, W - M, y + summary_h), radius=25, fill=white)
    d.text((M + 25, y + 20), "UMUMIY XULOSA", font=section_f, fill=green)
    ty = y + 62
    for ln in summary_lines:
        d.text((M + 25, ty), ln, font=body, fill=dark); ty += 28
    y += summary_h + 24

    # ----- Improvements -----
    d.rounded_rectangle((M, y, W - M, y + improve_h), radius=25, fill=pale)
    d.text((M + 25, y + 20), "YAXSHILASH UCHUN", font=section_f, fill=green)
    ty = y + 62
    for ln in improvement_lines or ["• Keyingi esseda har bir kamchilikni tuzatishga e’tibor bering."]:
        d.text((M + 25, ty), ln, font=body, fill=dark); ty += 28
    y += improve_h + 25

    # ----- Footer -----
    d.text((M, y), "BILIMNI BAHOLASH AGENTLIGI", font=font(25, True), fill=green)
    d.text((M, y + 36), "SIFAT • ADOLAT • NATIJA", font=small, fill=gray)

    out = io.BytesIO()
    out.name = "esse_natijasi.jpg"
    # Keep the detailed image readable while avoiding unnecessarily large Telegram uploads.
    for quality in (92, 88, 84, 80):
        out.seek(0); out.truncate(0)
        img.save(out, "JPEG", quality=quality, optimize=True)
        if out.tell() <= 9_500_000:
            break
    out.seek(0)
    return out

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
def make_text_result(data):
    total = float(data.get("total", 0))
    eq = to_75(total)
    lines = [
        "📊 ESSE NATIJASI",
        f"Yakuniy ball: {total:g}/24",
        f"75 ballik ekvivalent: {eq}/75",
        f"So‘zlar soni: {int(data.get('word_count', 0) or 0)}",
        "",
        "MEZONLAR:"
    ]
    rows = sorted(data.get("scores", []), key=lambda x: int(x.get("criterion", 0)))
    for item in rows:
        c = int(item.get("criterion", 0))
        name = CRITERION_NAMES.get(c, item.get("name", f"Mezon {c}"))
        score = float(item.get("score", 0))
        reason = str(item.get("reason", "")).strip()
        lines.append(f"{c}. {name}: {score:g}/2")
        if reason:
            lines.append(f"   {reason}")
        for ex in (item.get("examples") or [])[:3]:
            lines.append(f"   • {ex}")
        for err in (item.get("errors") or []):
            if isinstance(err, dict):
                lines.append(f"   XATO: {err.get('wrong','—')}")
                lines.append(f"   TO‘G‘RISI: {err.get('correct','—')}")
                if err.get("explanation"):
                    lines.append(f"   IZOH: {err.get('explanation')}")
    if data.get("summary"):
        lines += ["", "UMUMIY XULOSA:", str(data.get("summary"))]
    improvements = data.get("improvements") or []
    if improvements:
        lines += ["", "YAXSHILASH UCHUN:"] + [f"• {x}" for x in improvements]
    return "\n".join(lines)

async def send_result(message, data, mode="image"):
    if mode == "text":
        text = make_text_result(data)
        # Telegram text limit safety. Split without cutting words.
        chunks=[]; cur=""
        for line in text.splitlines(True):
            if len(cur) + len(line) > 3900:
                if cur: chunks.append(cur); cur=""
            cur += line
        if cur: chunks.append(cur)
        for chunk in chunks:
            await message.reply_text(chunk)
        return
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
    user = update.effective_user
    if not user:
        return False
    # Primary authorization: Telegram numeric ID. Username is a safe fallback for
    # this bot's configured owner so an accidentally stale Render ADMIN_ID does not
    # make /admin appear frozen.
    if int(user.id) == int(ADMIN_ID):
        return True
    username = (user.username or "").lstrip("@").strip()
    return bool(ADMIN_USERNAME and username.lower() == ADMIN_USERNAME.lower())

async def admin_cmd(update, context):
    try:
        if not await is_admin(update):
            logger.warning("Unauthorized /admin attempt: user_id=%s username=%s",
                           getattr(update.effective_user, "id", None),
                           getattr(update.effective_user, "username", None))
            await update.message.reply_text(
                "⛔ Bu bo‘lim faqat admin uchun.", reply_markup=MAIN_KEYBOARD
            )
            return

        context.user_data.clear()
        context.user_data["admin_mode"] = True
        context.user_data["admin_action"] = None
        # Send the panel immediately; no OpenAI/database-heavy work is performed here.
        await update.message.reply_text(
            "👨‍💼 ADMIN PANELI\n\nKerakli amalni tanlang:",
            reply_markup=ADMIN_KEYBOARD
        )
        logger.info("ADMIN PANEL OPENED | user_id=%s username=%s",
                    update.effective_user.id, update.effective_user.username)
    except Exception as exc:
        logger.exception("/admin handler failed")
        try:
            await update.message.reply_text(
                "⚠️ Admin panelini ochishda xatolik yuz berdi. /admin ni qayta yuboring."
            )
        except Exception:
            pass

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
async def result_image_cmd(update, context):
    upsert_user(update.effective_user)
    if not await require_subscription(update, context): return
    set_result_mode(update.effective_user.id, "image")
    await update.message.reply_text("🖼 Natijalar endi rasmli shaklda yuboriladi.", reply_markup=MAIN_KEYBOARD)

async def result_text_cmd(update, context):
    upsert_user(update.effective_user)
    if not await require_subscription(update, context): return
    set_result_mode(update.effective_user.id, "text")
    await update.message.reply_text("📝 Natijalar endi matnli shaklda yuboriladi.", reply_markup=MAIN_KEYBOARD)

async def start(update,context):
    upsert_user(update.effective_user)
    context.user_data.clear()
    if not await require_subscription(update, context): return
    await update.message.reply_text("Assalomu alaykum!\n\nMen ona tili va adabiyot fanidan milliy sertifikat testlaridan 45-savol — esse bo‘yicha BBA nizomi asosida baholaydigan esse tekshiruvchi botman.\n\nMenga yozma ravishda avval esse mavzusini, so‘ngra rasmli yoki yozma shaklda yozgan esseyingizni yuboring.\n\nMen amaldagi esse nizomi bo‘yicha esselarni tekshiraman!",reply_markup=MAIN_KEYBOARD)

async def new_cmd(update,context):
    upsert_user(update.effective_user)
    if not await require_subscription(update, context): return
    context.user_data.clear(); context.user_data["stage"]="topic"
    await update.message.reply_text("📝 Mavzu/vaziyatni yuboring.",reply_markup=MAIN_KEYBOARD)

async def help_cmd(update,context):
    if not await require_subscription(update, context): return
    await update.message.reply_text("📚 1) Mavzu/vaziyat.\n2) Esse matni yoki rasm.\n3) Natija rasmli yoki matnli shaklda — tanlov sizniki.\n   /rasm — rasmli natija\n   /matn — matnli natija\n\n12 mezon • 24 ball • 75 ballik ekvivalent.",reply_markup=MAIN_KEYBOARD)

async def _process_photo_album(update, context, media_group_id):
    """Albomidagi barcha rasmlarni yig‘ib, bitta esse sifatida tekshiradi."""
    await asyncio.sleep(ALBUM_WAIT_SECONDS)
    async with ALBUM_LOCK:
        item = ALBUM_BUFFERS.pop(media_group_id, None)
        ALBUM_TASKS.pop(media_group_id, None)
    if not item:
        return
    chat_id = item["chat_id"]
    user_id = item["user_id"]
    message = item["message"]
    file_ids = list(dict.fromkeys(item["file_ids"]))
    if not file_ids:
        return
    try:
        if context.user_data.get("stage") != "essay":
            await message.reply_text("Avval «✍️ Keyingi esseni tekshirish» tugmasini bosing.", reply_markup=MAIN_KEYBOARD)
            return
        lock = await user_lock(user_id)
        if lock.locked():
            await message.reply_text("⏳ Oldingi tekshiruv tugamadi. Biroz kuting.")
            return
        async with lock:
            status = await message.reply_text(f"⏳ {len(file_ids)} ta rasm qabul qilindi. Bitta esse sifatida o‘qilmoqda va tekshirilmoqda...")
            images=[]
            for fid in file_ids:
                f=await context.bot.get_file(fid)
                b=io.BytesIO()
                await f.download_to_memory(b)
                images.append(b.getvalue())
            topic=context.user_data.get("topic","")
            result=await evaluate_images(topic, images)
            save_check(user_id,"image",topic,result.get("total",0),result.get("word_count",0),result.get("status","normal"))
            await send_result(message,result,get_result_mode(user_id))
            context.user_data.clear()
            await status.edit_text(f"✅ {len(file_ids)} ta rasmli esse tekshirildi.")
    except Exception:
        logger.exception("photo album error")
        try:
            await message.reply_text("⚠️ Rasmlar bilan tekshiruvni yakunlashda texnik muammo yuz berdi. Birozdan so‘ng qayta urinib ko‘ring.")
        except Exception:
            pass
        context.user_data.clear()

async def handle_photo(update,context):
    upsert_user(update.effective_user)
    # Admin reklama rasmi
    if context.user_data.get("admin_mode") and await is_admin(update):
        if context.user_data.get("admin_action")=="broadcast_photo":
            try:
                p=update.message.photo[-1]
                f=await context.bot.get_file(p.file_id); b=io.BytesIO(); await f.download_to_memory(b)
                context.user_data["broadcast_photo_bytes"]=b.getvalue(); context.user_data["admin_action"]="broadcast_caption"
                await update.message.reply_text("Rasm qabul qilindi. Endi reklama matnini yuboring.",reply_markup=ADMIN_KEYBOARD)
            except Exception as e:
                await update.message.reply_text(f"Xatolik: {e}",reply_markup=ADMIN_KEYBOARD)
            return
    if not await require_subscription(update, context): return
    if context.user_data.get("stage")!="essay":
        await update.message.reply_text("Avval «✍️ Keyingi esseni tekshirish» tugmasini bosing.",reply_markup=MAIN_KEYBOARD); return

    mgid = update.message.media_group_id
    if mgid:
        async with ALBUM_LOCK:
            item=ALBUM_BUFFERS.setdefault(mgid,{"chat_id":update.effective_chat.id,"user_id":update.effective_user.id,"message":update.message,"file_ids":[]})
            fid=update.message.photo[-1].file_id if update.message.photo else None
            if fid and fid not in item["file_ids"]:
                item["file_ids"].append(fid)
            task=ALBUM_TASKS.get(mgid)
            if task is None or task.done():
                ALBUM_TASKS[mgid]=asyncio.create_task(_process_photo_album(update, context, mgid))
        return

    # Bitta rasm yuborilgan holat
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
            await send_result(update.message,result,get_result_mode(update.effective_user.id))
            context.user_data.clear(); await status.edit_text("✅ Tekshiruv tugadi.")
        except Exception:
            logger.exception("image error")
            await status.edit_text("⚠️ Tekshiruvni yakunlashda texnik muammo yuz berdi. Birozdan so‘ng qayta urinib ko‘ring.")
            context.user_data.clear()

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
                await update.message.reply_text(f"✅ Bot ishlayapti.\nModel: {MODEL}\nAdmin ID: {ADMIN_ID}\nAdmin username: @{ADMIN_USERNAME}\nDB: {DB_PATH}",reply_markup=ADMIN_KEYBOARD); return
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

    if not await require_subscription(update, context): return

    # Normal menu
    if text=="✍️ Keyingi esseni tekshirish":
        context.user_data.clear(); context.user_data["stage"]="topic"; await update.message.reply_text("📝 Mavzu/vaziyatni yuboring.",reply_markup=MAIN_KEYBOARD); return
    if text=="📊 Statistikam": await send_user_stats(update.message,update.effective_user.id); return
    if text=="🖼 Rasmli natija":
        set_result_mode(update.effective_user.id, "image")
        await update.message.reply_text("🖼 Tanlandi: keyingi natijalar rasmli shaklda yuboriladi.", reply_markup=MAIN_KEYBOARD); return
    if text=="📝 Matnli natija":
        set_result_mode(update.effective_user.id, "text")
        await update.message.reply_text("📝 Tanlandi: keyingi natijalar matnli shaklda yuboriladi.", reply_markup=MAIN_KEYBOARD); return
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
            await send_result(update.message,result,get_result_mode(update.effective_user.id))
            context.user_data.clear(); await status.edit_text("✅ Tekshiruv tugadi.")
        except Exception as e:
            logger.exception("text error"); await status.edit_text("⚠️ Tekshiruvni yakunlashda texnik muammo yuz berdi. Birozdan so‘ng qayta urinib ko‘ring."); context.user_data.clear()

# ============================================================
# HEALTH / MAIN
# ============================================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/plain; charset=utf-8"); self.end_headers(); self.wfile.write(b"Esse baholovchi bot ishlayapti.")
    def log_message(self,*args): pass

def start_health():
    ThreadingHTTPServer(("0.0.0.0",PORT),HealthHandler).serve_forever()

async def telegram_error_handler(update, context):
    logger.exception("Telegram update error", exc_info=context.error)
    # Do not let one failed update stop the polling loop.
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Texnik xatolik yuz berdi. Iltimos, buyruqni qayta yuboring."
            )
    except Exception:
        pass


def main():
    init_db()
    threading.Thread(target=start_health,daemon=True).start()
    app=Application.builder().token(TELEGRAM_BOT_TOKEN).concurrent_updates(20).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("new",new_cmd))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CommandHandler("rasm",result_image_cmd))
    app.add_handler(CommandHandler("matn",result_text_cmd))
    app.add_handler(CommandHandler(["admin", "panel"], admin_cmd))
    app.add_handler(CallbackQueryHandler(subscription_callback, pattern="^check_subscription$"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE,handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_text))
    app.add_error_handler(telegram_error_handler)
    logger.info("BOT STARTED | model=%s | admin=%s",MODEL,ADMIN_ID)
    app.run_polling(drop_pending_updates=True,close_loop=False)

if __name__=="__main__":
    main()
