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
import random
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, BadRequestError
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ============================================================
# CONFIG
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
SCORING_VERSION = "strict-v5-criterion-routing"
PORT = int(os.getenv("PORT", "10000"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "1953416343"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Sardor_Sayfullayev777").lstrip("@").strip()
ADMIN_CONTACT_URL = os.getenv("ADMIN_CONTACT_URL", "https://t.me/Sardor_Sayfullayev777")
DB_PATH = os.getenv("BOT_DB_PATH", "esse_bot.sqlite3")
EMBLEM_PATH = os.getenv("EMBLEM_PATH", "emblem.png")

# PDF himoyasi: Telegram Bot API orqali yuklab olish chegarasi 20 MB.
# Biz biroz zaxira qoldirib, 19 MB dan katta PDFni qabul qilmaymiz.
MAX_PDF_SIZE_MB = float(os.getenv("MAX_PDF_SIZE_MB", "10"))
MAX_PDF_SIZE_BYTES = int(MAX_PDF_SIZE_MB * 1024 * 1024)
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "5"))
MAX_PDF_RENDER_DIM = int(os.getenv("MAX_PDF_RENDER_DIM", "1600"))
MAX_PDF_JPEG_QUALITY = int(os.getenv("MAX_PDF_JPEG_QUALITY", "78"))
PDF_PROCESS_TIMEOUT = int(os.getenv("PDF_PROCESS_TIMEOUT", "150"))
# Majburiy kanal obunasi
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@milliysertifikat_ona_tili1")
REQUIRED_CHANNEL_URL = os.getenv("REQUIRED_CHANNEL_URL", "https://t.me/milliysertifikat_ona_tili1")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN Render Environment Variables orqali berilishi kerak.")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY Render Environment Variables orqali berilishi kerak.")

client = OpenAI(api_key=OPENAI_API_KEY, timeout=120.0, max_retries=2)

async def openai_json(input_payload, max_output_tokens=12000):
    """OpenAI Responses API chaqiruvi va JSON javobini xavfsiz olish.

    Muhim: bu funksiya matn va rasm tekshiruvlari uchun bir xil kirish formatini
    qabul qiladi. JSON formatini prompt orqali talab qiladi va model qaytargan
    JSONni clean_json/json.loads orqali tekshiradi. Vaqtinchalik API/429 xatolarida
    bir necha marta qayta urinadi; foydalanuvchiga texnik tafsilot chiqarmaydi.
    """
    last_error = None
    for attempt in range(3):
        try:
            kwargs = {
                "model": MODEL,
                "input": input_payload,
                "max_output_tokens": max_output_tokens,
            }
            response = await asyncio.to_thread(client.responses.create, **kwargs)
            raw = clean_json(response.output_text)
            if not raw:
                raise ValueError("OpenAI javobi bo'sh.")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("OpenAI JSON obyekti qaytarmadi.")
            return data
        except RateLimitError as e:
            last_error = e
            logger.warning("OpenAI rate limit, retry %s/3", attempt + 1)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt * 2)
        except (AuthenticationError, BadRequestError) as e:
            logger.exception("OpenAI request rejected")
            raise
        except (APIError, json.JSONDecodeError, ValueError) as e:
            last_error = e
            logger.warning("OpenAI response problem, retry %s/3: %s", attempt + 1, type(e).__name__)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
        except Exception as e:
            last_error = e
            logger.exception("OpenAI JSON call failed, retry %s/3", attempt + 1)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
    raise RuntimeError("OpenAI tekshiruvini yakunlab bo'lmadi.") from last_error

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
            status TEXT,
            result_json TEXT
        )''')
        # Existing SQLite databases may have been created before result_json was added.
        cols = {r[1] for r in c.execute("PRAGMA table_info(checks)").fetchall()}
        if "result_json" not in cols:
            c.execute("ALTER TABLE checks ADD COLUMN result_json TEXT")
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

def save_check(user_id, mode, topic, total, words, status, result=None):
    result_json = None
    if result is not None:
        try:
            result_json = json.dumps(result, ensure_ascii=False)
        except Exception:
            result_json = None
    with DB_LOCK, db() as c:
        c.execute("INSERT INTO checks(user_id,mode,topic,total,words,created_at,status,result_json) VALUES(?,?,?,?,?,?,?,?)",
                  (user_id, mode, topic[:1000], float(total), int(words), now_iso(), status, result_json))
        c.commit()

def admin_users_page(limit=20):
    with DB_LOCK, db() as c:
        rows = c.execute('''SELECT u.user_id,u.username,u.first_name,u.last_name,
                                   COUNT(ch.id) AS checks_count, MAX(ch.created_at) AS last_check
                            FROM users u LEFT JOIN checks ch ON ch.user_id=u.user_id
                            GROUP BY u.user_id
                            ORDER BY COALESCE(last_check,u.last_seen) DESC, u.user_id DESC
                            LIMIT ?''', (limit,)).fetchall()
    return [dict(r) for r in rows]

def admin_user_checks(user_id, limit=15):
    with DB_LOCK, db() as c:
        rows = c.execute('''SELECT id,mode,topic,total,words,created_at,status,result_json
                            FROM checks WHERE user_id=? ORDER BY id DESC LIMIT ?''', (user_id,limit)).fetchall()
    return [dict(r) for r in rows]

def admin_check_detail(check_id):
    with DB_LOCK, db() as c:
        row = c.execute('''SELECT ch.*,u.username,u.first_name,u.last_name
                           FROM checks ch LEFT JOIN users u ON u.user_id=ch.user_id
                           WHERE ch.id=?''', (check_id,)).fetchone()
    return dict(row) if row else None

def admin_user_keyboard(rows):
    buttons=[]
    for r in rows:
        name = ' '.join(x for x in [r.get('first_name',''), r.get('last_name','')] if x).strip() or (('@'+r.get('username')) if r.get('username') else str(r.get('user_id')))
        label=f"{name[:28]} — {int(r.get('checks_count') or 0)} ta"
        buttons.append([InlineKeyboardButton(label, callback_data=f"admin_user_{r['user_id']}")])
    buttons.append([InlineKeyboardButton("🔄 Yangilash", callback_data="admin_users")])
    return InlineKeyboardMarkup(buttons)

def admin_checks_keyboard(rows):
    buttons=[]
    for r in rows:
        mode = {'text':'📝','image':'🖼️','pdf':'📄'}.get(r.get('mode'),'📌')
        label=f"{mode} {float(r.get('total') or 0):g}/24 • {str(r.get('created_at',''))[:10]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"admin_check_{r['id']}")])
    return InlineKeyboardMarkup(buttons)

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

# ============================================================
# GLOBAL EVALUATION QUEUE
# 10-20 users can submit essays at once without freezing the bot.
# Users do not see queue numbers or internal concurrency details.
# Only a small number of expensive AI evaluations run simultaneously;
# the rest wait silently while Telegram remains responsive.
# ============================================================
MAX_PARALLEL_EVALUATIONS = max(1, int(os.getenv("MAX_PARALLEL_EVALUATIONS", "2")))
EVALUATION_SEMAPHORE = asyncio.Semaphore(MAX_PARALLEL_EVALUATIONS)
EVALUATION_WAIT_TIMEOUT = max(60, int(os.getenv("EVALUATION_WAIT_TIMEOUT", "900")))

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

async def run_evaluation_silently(coro_factory):
    """Global silent queue for expensive AI checks.

    The caller already sends a normal 'tekshirilmoqda' status message.
    This function deliberately does not expose queue position, user count,
    semaphore state, or rate-limit details to the user.
    """
    try:
        await asyncio.wait_for(EVALUATION_SEMAPHORE.acquire(), timeout=EVALUATION_WAIT_TIMEOUT)
    except asyncio.TimeoutError as e:
        raise RuntimeError("Tekshiruv navbati juda uzoq davom etdi.") from e
    try:
        return await coro_factory()
    finally:
        EVALUATION_SEMAPHORE.release()

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

async def evaluation_method_callback(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id != ADMIN_ID and not await is_subscribed(user_id, context.bot):
        await query.answer("❌ Avval kanalga a’zo bo‘ling.", show_alert=True)
        return
    await query.answer()

    if query.data == "eval_ai":
        context.user_data["method"] = "ai"
        context.user_data["stage"] = "essay_ai"
        await query.message.reply_text(
            "🤖 Sun’iy intellekt yordamida baholash tanlandi.\n\n"
            "✅ Bu xizmat bepul.\n\n"
            "📌 Endi esseingizni yuboring:\n"
            "• matn ko‘rinishida; yoki\n"
            "• rasm(lar) ko‘rinishida; yoki\n"
            "• PDF ko‘rinishida.\n\n"
            "⚠️ Juda ko‘p talabgorlar foydalanayotgan paytda saytda uzilishlar kuzatilishi mumkin. "
            "Bunday holatda biroz kutib, qayta urinib ko‘ring.\n\n"
            f"📄 PDF uchun: maksimal {MAX_PDF_SIZE_MB:g} MB va {MAX_PDF_PAGES} sahifa.",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if query.data == "eval_expert":
        context.user_data["method"] = "expert"
        context.user_data["stage"] = "expert_confirm"
        await query.message.reply_text(
            "⚠️ DIQQAT\n\n"
            "👨‍🏫 Haqiqiy ekspert yordamida baholash — pullik xizmat.\n\n"
            "💰 Bitta esse tekshirish narxi: 10 000 so‘m.\n"
            "⏱ Esse 24 soat ichida tekshiriladi va natija sizga yuboriladi.\n\n"
            "Davom etishga rozimisiz?",
            reply_markup=EXPERT_CONFIRM_KEYBOARD
        )
        return

    if query.data == "expert_back":
        context.user_data["stage"] = "method"
        await query.message.reply_text("⬅️ Baholash usulini tanlang:", reply_markup=EVALUATION_METHOD_KEYBOARD)
        return

    if query.data == "expert_agree":
        context.user_data["stage"] = "expert_contact"
        await query.message.reply_text(
            "✅ Roziligingiz qabul qilindi.\n\n"
            "👨‍🏫 EKSPERT\n"
            f"{ADMIN_CONTACT_URL}\n\n"
            "Telegram orqali ekspertga faqat «Esse tekshirish» deb yozing.\n"
            "Ekspert sizga to‘lov uchun karta ma’lumotlarini yuboradi. "
            "To‘lovdan so‘ng esseingizni ekspertga yuborasiz va u 24 soat ichida tekshirib, natijani sizga yuboradi.",
            reply_markup=EXPERT_CONTACT_KEYBOARD
        )
        return

async def result_format_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.data not in ("result_image", "result_text") or context.user_data.get("stage") != "result_mode":
        return
    result = context.user_data.get("pending_result")
    if not result:
        await query.message.reply_text("⚠️ Natija ma’lumoti topilmadi. Esseni qayta tekshiring.", reply_markup=MAIN_KEYBOARD)
        context.user_data.clear()
        return
    mode = "image" if query.data == "result_image" else "text"
    set_result_mode(query.from_user.id, mode)
    await query.message.reply_text("⏳ Natija tayyorlanmoqda...", reply_markup=MAIN_KEYBOARD)
    try:
        await send_result(query.message, result, mode)
    except Exception:
        logger.exception("result format send error")
        await query.message.reply_text("⚠️ Natijani yuborishda texnik muammo yuz berdi. Qayta urinib ko‘ring.", reply_markup=MAIN_KEYBOARD)
    finally:
        context.user_data.clear()

# ============================================================
# 🌱 ESSENI O‘STIRISH — BEPUL O‘QUV BO‘LIMI
# ============================================================
async def show_growth_gate(message, user_id):
    await message.reply_text(
        "🌱 ESSENI O‘STIRISH\n\n"
        "Esseni yozish va takomillashtirish uchun kerakli vositalarni tanlang.",
        reply_markup=GROWTH_KEYBOARD
    )

# ============================================================
# KEYBOARDS
# ============================================================
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["✍️ Esse tekshirish", "📊 Statistika"],
    ["🌱 Esseni o‘stirish"],
], resize_keyboard=True)

GROWTH_KEYBOARD = ReplyKeyboardMarkup([
    ["📚 Xatolar ustida ishlash", "🔄 Esseni yaxshilash"],
    ["✍️ Esse yozish mashqi", "💡 Dalil topib berish"],
    ["⬅️ Asosiy menyu"],
], resize_keyboard=True)

STATISTICS_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("📊 Statistikam", callback_data="stats_personal")],
    [InlineKeyboardButton("📈 Rivojlanishim", callback_data="stats_progress")],
    [InlineKeyboardButton("📊 Chuqur statistika", callback_data="stats_deep")],
])

EVALUATION_METHOD_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🤖 Sun’iy intellekt yordamida baholash", callback_data="eval_ai")],
    [InlineKeyboardButton("👨‍🏫 Haqiqiy ekspert yordamida baholash", callback_data="eval_expert")],
])

EXPERT_CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ Roziman", callback_data="expert_agree"),
     InlineKeyboardButton("⬅️ Ortga", callback_data="expert_back")],
])

RESULT_FORMAT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🖼 Rasmli", callback_data="result_image")],
    [InlineKeyboardButton("📝 Matnli", callback_data="result_text")],
])

EXPERT_CONTACT_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton(f"👨‍🏫 Ekspert: @{ADMIN_USERNAME}", url=ADMIN_CONTACT_URL)],
])

ADMIN_KEYBOARD = ReplyKeyboardMarkup([
    ["📈 Umumiy statistika", "👥 Foydalanuvchilar"],
    ["👥 Foydalanuvchilar CSV", "📢 Reklama yuborish"],
    ["🧪 Test holati"],
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


def authoritative_total24(data):
    """Barcha natija ko'rinishlari uchun yagona, hisoblangan 24 ballik jami."""
    scores = data.get("scores") or []
    status = str(data.get("status", ""))
    if scores and status != "special_case":
        total = round(sum(float(item.get("score", 0) or 0) for item in scores), 1)
    else:
        total = round(float(data.get("total", 0) or 0), 1)
    data["total"] = total
    return total


def normalize_summary_score(data):
    """AI xulosasida qolib ketgan eski/stale ballni yagona jami ball bilan almashtiradi."""
    total = authoritative_total24(data)
    summary = str(data.get("summary", "") or "")
    if not summary:
        return summary
    import re
    total_txt = f"{total:g}/24"
    summary = re.sub(
        r"((?:jami|umumiy)\s+ball\s*[:：]?\s*)\d+(?:\.\d+)?\s*/\s*24",
        lambda m: m.group(1) + total_txt,
        summary,
        flags=re.IGNORECASE,
    )
    summary = re.sub(
        r"((?:yakuniy|final)\s+ball\s*[:：]?\s*)\d+(?:\.\d+)?\s*/\s*24",
        lambda m: m.group(1) + total_txt,
        summary,
        flags=re.IGNORECASE,
    )
    data["summary"] = summary
    return summary

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

AUDIT_SCHEMA_PROMPT = r"""
Siz MUSTAQIL XATO AUDITORISIZ. Esse matnini BBA baholashidan alohida ravishda tekshiring.

ASOSIY MAQSAD: imlo, punktuatsiya/ishoraviy, qo'shimcha qo'llash va so'z qo'llashdagi
ANIQ xatolarni imkon qadar to'liq topish. Har bir xatoni alohida ko'rsating.

QAT'IY QOIDALAR:
1) Xato faqat matndagi real birlikka asoslangan bo'lsin. Taxmin, did yoki "yaxshiroq bo'lardi" xato emas.
2) Bir xil xato bir xil joyda bir marta sanaladi.
3) Bir xil so'zning boshqa-boshqa joylardagi mustaqil xatosi bo'lsa, har bir joy alohida xato.
4) Imlo: so'zning yozilish normasi buzilgan bo'lsa.
5) Punktuatsiya: vergul, nuqta, ikki nuqta, nuqtali vergul, tire, qo'shtirnoq va boshqa belgilar noto'g'ri qo'yilgan yoki zarur joyda tushirilgan bo'lsa.
6) Qo'shimcha: kelishik, egalik, ko'plik, fe'l shakli va boshqa grammatik qo'shimcha noto'g'ri qo'llangan bo'lsa.
7) So'z qo'llash: so'z/konstruksiya mazmunga yoki o'zbek adabiy tilidagi me'yoriy qo'llanishga mos kelmasa.
8) "xo'sh"/"xo‘sh" kirish qismida takrorlangan bo'lsa ham, faqat mavjudligi yoki takrori uchun xato emas.
9) Har bir xatoda XATO, TO'G'RISI, IZOH va KONTEKST bo'lsin.
10) Ko'rinmagan yoki noaniq so'zni o'ylab topmang.
11) Barcha aniq xatolarni tekshirib bo'lgachgina JSON qaytaring.

JSON:
{"errors":{"7":[],"8":[],"9":[],"10":[]}}
Har bir obyekt: {"wrong":"...","correct":"...","explanation":"...","context":"..."}
"""

ADJUDICATOR_PROMPT = r"""
Siz FINAL XATO NAZORATCHISISIZ. Quyida esse va ikki bosqichli auditorlar topgan xatolar beriladi.
Sizning vazifangiz:
A) Har bir nomzod xatoni original matn bilan tekshirish.
B) Haqiqiy bo'lmagan, taxminiy yoki faqat uslubiy afzallik bo'lgan xatolarni olib tashlash.
C) Auditorlar o'tkazib yuborgan ANIQ imlo, punktuatsiya, qo'shimcha va so'z qo'llash xatolarini original matndan topib qo'shish.
D) Bir xil joydagi bir xil xatoni bir marta qoldirish.
E) "xo'sh"/"xo‘sh"ni uning mavjudligi yoki takrori sababli xato qilmaslik.
F) Har bir qolgan xato uchun original matndan aniq KONTEKST berish.

Faqat JSON qaytaring:
{"errors":{"7":[],"8":[],"9":[],"10":[]}}
Har bir obyekt: {"wrong":"...","correct":"...","explanation":"...","context":"..."}
"""

async def _call_error_auditor(system_prompt, essay):
    try:
        r = await asyncio.to_thread(client.responses.create, model=MODEL, input=[
            {"role":"system","content":system_prompt},
            {"role":"user","content":str(essay or "")}
        ])
        raw = clean_json(r.output_text)
        obj = json.loads(raw)
        errs = obj.get("errors") or {}
        return {str(k): (v if isinstance(v, list) else []) for k,v in errs.items()}
    except Exception:
        logger.exception("Error audit failed")
        return {}

async def audit_text_errors(essay):
    # Two independent passes reduce the chance that one reviewer misses a small error.
    a, b = await asyncio.gather(
        _call_error_auditor(AUDIT_SCHEMA_PROMPT, essay),
        _call_error_auditor(AUDIT_SCHEMA_PROMPT + "\\nSiz boshqa auditorning natijasini ko'rmaysiz. Mustaqil qayta tekshiring.", essay),
    )
    candidates = {"7": [], "8": [], "9": [], "10": []}
    for c in candidates:
        candidates[c].extend(a.get(c, []))
        candidates[c].extend(b.get(c, []))
    return await adjudicate_errors(essay, candidates)

async def audit_image_errors(images):
    import base64
    content = [{"type":"input_text","text":AUDIT_SCHEMA_PROMPT + "\\nBu rasmlar bitta esse. Qo'lda yozilgan matnni bevosita ko'rib, xatolarni aniqlang. Transkripsiya xatosiga emas, rasmdagi haqiqiy yozuvga tayaning."}]
    for b in images:
        b64 = base64.b64encode(b).decode()
        content.append({"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"})
    try:
        r = await asyncio.to_thread(client.responses.create, model=MODEL, input=[{"role":"system","content":AUDIT_SCHEMA_PROMPT},{"role":"user","content":content}])
        raw = clean_json(r.output_text)
        obj = json.loads(raw)
        errs = obj.get("errors") or {}
        return {str(k): (v if isinstance(v, list) else []) for k,v in errs.items()}
    except Exception:
        logger.exception("Image error audit failed")
        return {}

async def adjudicate_errors(essay, candidates):
    payload = {
        "essay": str(essay or ""),
        "candidate_errors": candidates,
    }
    try:
        r = await asyncio.to_thread(client.responses.create, model=MODEL, input=[
            {"role":"system","content":ADJUDICATOR_PROMPT},
            {"role":"user","content":json.dumps(payload, ensure_ascii=False)}
        ])
        raw = clean_json(r.output_text)
        obj = json.loads(raw)
        errs = obj.get("errors") or {}
        return {str(k): (v if isinstance(v, list) else []) for k,v in errs.items()}
    except Exception:
        logger.exception("Final error adjudication failed")
        return candidates

def _route_error_to_criterion(original_criterion, err):
    """Xatoni faqat uning haqiqiy tabiatiga mos mezonda qoldiradi.

    Asosiy muammo: AI ba'zan vergul/nuqta xatosini 9 yoki 10-mezonga,
    so'z qo'llash xatosini 7-mezonga yozib yuboradi. Bu funksiya bunday
    aralashuvni birinchi navbatda aniq til belgilariga qarab tuzatadi.
    """
    c = int(original_criterion)
    wrong = str(err.get("wrong") or "").strip()
    correct = str(err.get("correct") or "").strip()
    explanation = str(err.get("explanation") or "").strip().lower()
    context = str(err.get("context") or "").strip().lower()
    blob = f"{explanation} {context}"

    # Tinish belgisi bilan bog'liq aniq signal.
    punct_terms = (
        "vergul", "nuqta", "ikki nuqta", "nuqtali vergul", "tire",
        "qo'shtirnoq", "qo‘sh tirnoq", "tinish", "ishoraviy", "punktuats",
        "vergul qo'y", "vergul qo‘y", "vergul tush", "belgi qo'y", "belgi qo‘y"
    )
    has_punct_signal = any(t in blob for t in punct_terms)

    # Qo'shimcha/grammatik shakl bilan bog'liq aniq signal.
    suffix_terms = (
        "qo'shimcha", "qo‘shimcha", "kelishik", "egalik", "ko'plik",
        "ko‘plik", "affiks", "fe'l shakli", "grammatik shakl", "qo'shimchasi",
        "qo‘shimchasi"
    )
    has_suffix_signal = any(t in blob for t in suffix_terms)

    # Imlo/yozilish bilan bog'liq signal.
    spelling_terms = (
        "imlo", "imloviy", "yozilishi", "yozilgan", "harf xato",
        "harfning", "apostrof", "o'zbek imlo", "o‘zbek imlo", "imlo lug'at",
        "imlo lug‘at"
    )
    has_spelling_signal = any(t in blob for t in spelling_terms)

    # Faqat tinish belgilaridan farq qilsa, bu shubhasiz 8-mezon.
    def strip_punct(v):
        return re.sub(r"[^\w\s]", "", str(v or "").lower(), flags=re.UNICODE).split()
    punctuation_only = bool(wrong and correct and strip_punct(wrong) == strip_punct(correct) and wrong != correct)

    if punctuation_only or has_punct_signal:
        return 8
    if has_suffix_signal:
        return 9
    if has_spelling_signal:
        return 7

    # So'zning ma'nosi, tanlovi yoki uslubiy qo'llanishi 10-mezon.
    word_terms = (
        "so'z qo'llash", "so‘z qo‘llash", "so'z tanlash", "so‘z tanlash",
        "ma'nosi", "ma’nosi", "mazmunga mos", "mazmunga mos emas",
        "uslubiy", "leksik", "noto'g'ri so'z", "noto‘g‘ri so‘z"
    )
    if any(t in blob for t in word_terms):
        return 10

    # 7-mezondagi xato agar so'zning yozilishi emas, boshqa so'z bilan
    # almashtirilishi bo'lsa, u 10-mezonga tegishli. Masalan,
    # "tajribasini oshiradi" -> "tajribasini orttiradi" imlo emas.
    if c == 7 and wrong and correct:
        def lev(a, b):
            a, b = str(a), str(b)
            prev = list(range(len(b) + 1))
            for i, ca in enumerate(a, 1):
                cur = [i]
                for j, cb in enumerate(b, 1):
                    cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j-1] + (ca != cb)))
                prev = cur
            return prev[-1]
        wt = re.findall(r"[\wʻ’']+", wrong.lower(), flags=re.UNICODE)
        ct = re.findall(r"[\wʻ’']+", correct.lower(), flags=re.UNICODE)
        if len(wt) == len(ct) and wt:
            changed = [(a, b) for a, b in zip(wt, ct) if a != b]
            if len(changed) == 1 and lev(*changed[0]) >= 3:
                return 10

    return c


def _reclassify_errors(errors_by_criterion):
    """Bitta xatoni yagona to'g'ri mezonga o'tkazadi va dublikatlarni yo'qotadi."""
    routed = {"7": [], "8": [], "9": [], "10": []}
    for key, items in (errors_by_criterion or {}).items():
        try:
            source_c = int(key)
        except Exception:
            continue
        if source_c not in (7, 8, 9, 10):
            continue
        for err in items or []:
            if not isinstance(err, dict):
                continue
            target = _route_error_to_criterion(source_c, err)
            if target not in (7, 8, 9, 10):
                target = source_c
            e = dict(err)
            e["criterion"] = target
            routed[str(target)].append(e)

    # Bir xil joydagi bir xil xatoni bir marta qoldiramiz.
    final = {k: [] for k in routed}
    seen = set()
    for key in ("7", "8", "9", "10"):
        for e in routed[key]:
            def norm(v):
                return re.sub(r"\s+", " ", str(v or "").strip().lower().replace("’", "'").replace("ʻ", "'").replace("`", "'"))
            sig = (int(key), norm(e.get("wrong")), norm(e.get("correct")), norm(e.get("context")))
            if sig in seen:
                continue
            seen.add(sig)
            e.pop("criterion", None)
            final[key].append(e)
    return final

def merge_audit_errors(data, *audits):
    by = {int(x["criterion"]): x for x in data.get("scores", [])}

    # Avval barcha nomzod xatolarni yig'amiz, so'ng ularni faqat to'g'ri
    # mezonga yo'naltiramiz. Shunday qilib, masalan, vergul xatosi 9 yoki
    # 10-mezonga o'tib ketmaydi.
    combined_by = {"7": [], "8": [], "9": [], "10": []}
    for c in (7, 8, 9, 10):
        combined_by[str(c)].extend(list(by.get(c, {}).get("errors") or []))
    for audit in audits:
        for c in combined_by:
            combined_by[c].extend(list((audit or {}).get(c, []) or []))
    routed_all = _reclassify_errors(combined_by)

    def norm(v):
        return str(v or "").strip().lower().replace("’","'").replace("ʻ","'").replace("`","'")
    for c in (7, 8, 9, 10):
        item = by.get(c)
        if not item:
            continue
        cleaned = []
        for e in routed_all.get(str(c), []):
            if not isinstance(e, dict):
                continue
            wrong = str(e.get("wrong") or "").strip()
            correct = str(e.get("correct") or "").strip()
            explanation = str(e.get("explanation") or "").strip()
            context = str(e.get("context") or "").strip()
            if not wrong or not explanation:
                continue
            if c == 10 and norm(wrong) in {"xo'sh", "xosh"}:
                continue
            cleaned.append({"wrong": wrong, "correct": correct, "explanation": explanation, "context": context})
        item["errors"] = cleaned
        item["error_count"] = len(cleaned)
        if cleaned:
            item["reason"] = f"Aniqlangan xatolar: {len(cleaned)} ta. Faqat shu mezonga tegishli xatolar sanaldi."
        else:
            item["reason"] = "Aniq xato topilmadi."
    return data

def enforce_strict_high_score_gate(data):
    """20+ ball faqat barcha asosiy talablar real dalil bilan bajarilganda mumkin."""
    scores = {int(x["criterion"]): x for x in data.get("scores", [])}
    total = round(sum(float(x.get("score", 0)) for x in scores.values()), 1)
    flags = data.get("flags") or {}
    error_free = all(int(scores.get(c, {}).get("error_count", 0) or 0) == 0 for c in (7,8,9,10,12))
    core_strong = all(float(scores.get(c, {}).get("score", 0)) >= 1.5 for c in (1,2,3,4,5,6,11))
    evidence_ok = (
        str(flags.get("evidence_status", "none")) == "both"
        and bool(flags.get("evidence_strong", False))
        and int(flags.get("strong_evidence_view1_count", 0) or 0) >= 2
        and int(flags.get("strong_evidence_view2_count", 0) or 0) >= 2
    )
    conclusion_ok = str(flags.get("conclusion_position", "unknown")) in {"view1", "view2"}
    lexical_ok = float(scores.get(11, {}).get("score", 0)) >= 1.5
    if total > 20 and not (error_free and core_strong and evidence_ok and conclusion_ok and lexical_ok):
        # Ballni sun'iy ravishda pasaytirmaymiz; yuqori ball uchun yetishmagan asoslarni
        # natijada ochiq ko'rsatamiz va 20 ball chegarasini qat'iy nazorat qilamiz.
        data["high_score_blocked"] = True
        data["high_score_block_reason"] = (
            "20 balldan yuqori natija uchun barcha asosiy mezonlar kamida 1,5, "
            "7/8/9/10/12 mezonlarda aniq xato yo‘qligi, ikkala qarashga kuchli dalil "
            "va xulosada bitta qarashni aniq qo‘llab-quvvatlash talab qilinadi."
        )
        # The score remains rubric-derived; we do not invent a deduction solely to make it rare.
    return data

async def evaluate_text(topic, essay):
    k = cache_key("text", topic, essay, MODEL, SCORING_VERSION)
    old = cache_get(k)
    if old: return old
    data = await openai_json([{"role":"system","content":RUBRIC},{"role":"user","content":eval_schema_prompt(topic,essay)}])
    audit = await audit_text_errors(essay)
    data = merge_audit_errors(data, audit)
    data = apply_deterministic_rules(data, essay, topic)
    data = enforce_strict_high_score_gate(data)
    cache_put(k, data)
    return data

async def evaluate_image(topic, image_bytes):
    k = cache_key("image", topic, hashlib.sha256(image_bytes).hexdigest(), MODEL, SCORING_VERSION)
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
    audit_text, audit_image = await asyncio.gather(audit_text_errors(transcription), audit_image_errors([image_bytes]))
    data = merge_audit_errors(data, audit_text, audit_image)
    data = apply_deterministic_rules(data, transcription, topic)
    data = enforce_strict_high_score_gate(data)
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
    k = cache_key("images", topic, digest.hexdigest(), MODEL, SCORING_VERSION)
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
    audit_text, audit_image = await asyncio.gather(audit_text_errors(transcription), audit_image_errors(images))
    data = merge_audit_errors(data, audit_text, audit_image)
    data = apply_deterministic_rules(data, transcription, topic)
    data = enforce_strict_high_score_gate(data)
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
    total = authoritative_total24(data)
    normalize_summary_score(data)
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
    footer_h = 175

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
    warning = "⚠️ Bu sun’iy intellekt yordamida tayyorlangan natija. Haqiqiy ekspert natijasidan biroz farq qilishi mumkin."
    warning2 = "Agar haqiqiy natijangizni yanada aniqroq bilmoqchi bo‘lsangiz, «Haqiqiy ekspert yordamida baholash» bo‘limini tanlang."
    wy = y + 72
    for ln in _fit_lines(d, warning, small, W - 2 * M, 2) + _fit_lines(d, warning2, small, W - 2 * M, 2):
        d.text((M, wy), ln, font=small, fill=gray)
        wy += 24

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
def _prepare_pdf_sync(pdf_bytes):
    """PDFni bloklamaydigan yordamchi oqim uchun tayyorlaydi.
    Matnli PDF -> matn; skaner/qo'l yozuvi -> siqilgan JPEG sahifalar.
    """
    if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
        raise ValueError(f"PDF hajmi {MAX_PDF_SIZE_MB:g} MB dan katta")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)
    if page_count <= 0:
        raise ValueError("PDFda sahifa topilmadi")
    if page_count > MAX_PDF_PAGES:
        raise ValueError(f"PDF {MAX_PDF_PAGES} sahifadan oshmasligi kerak")

    texts = []
    for page in reader.pages:
        try:
            texts.append((page.extract_text() or "").strip())
        except Exception:
            texts.append("")
    joined = "\n\n".join(x for x in texts if x).strip()

    # Yetarli matn bo'lsa OCR/visionga o'tmaymiz.
    if len(joined) >= 80:
        return {"kind": "text", "payload": joined, "pages": page_count}

    # Skaner/qo'l yozuvi PDF. Har bir sahifani ketma-ket render qilamiz.
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    try:
        for page in doc:
            rect = page.rect
            longest = max(float(rect.width), float(rect.height)) or 1.0
            scale = min(1.5, MAX_PDF_RENDER_DIM / longest)
            scale = max(0.6, scale)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            raw = pix.tobytes("jpeg", jpg_quality=MAX_PDF_JPEG_QUALITY)

            # Yana bir marta PIL orqali qat'iy o'lcham/hajm nazorati.
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            im.thumbnail((MAX_PDF_RENDER_DIM, MAX_PDF_RENDER_DIM), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            im.save(out, "JPEG", quality=MAX_PDF_JPEG_QUALITY, optimize=True)
            images.append(out.getvalue())
    finally:
        doc.close()

    if not images:
        raise ValueError("PDF sahifalarini o'qib bo'lmadi")
    return {"kind": "images", "payload": images, "pages": page_count}


async def evaluate_pdf(topic, pdf_bytes):
    """PDFni xavfsiz limitlar bilan, bloklamasdan va navbat orqali tekshiradi."""
    if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
        raise ValueError(f"PDF hajmi {MAX_PDF_SIZE_MB:g} MB dan katta")

    k = cache_key("pdf", topic, hashlib.sha256(pdf_bytes).hexdigest(), MODEL)
    old = cache_get(k)
    if old:
        return old

    prepared = await asyncio.wait_for(
        asyncio.to_thread(_prepare_pdf_sync, pdf_bytes),
        timeout=PDF_PROCESS_TIMEOUT,
    )

    if prepared["kind"] == "text":
        data = await evaluate_text(topic, prepared["payload"])
    else:
        data = await evaluate_images(topic, prepared["payload"])

    data["_pdf_mode"] = True
    data["_pdf_pages"] = prepared["pages"]
    cache_put(k, data)
    return data


def make_text_result(data):
    total = authoritative_total24(data)
    normalize_summary_score(data)
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
    if data.get("high_score_blocked"):
        lines += ["", "⚠️ YUQORI BALL NAZORATI:", str(data.get("high_score_block_reason"))]
    if data.get("summary"):
        lines += ["", "UMUMIY XULOSA:", str(data.get("summary"))]
    improvements = data.get("improvements") or []
    if improvements:
        lines += ["", "YAXSHILASH UCHUN:"] + [f"• {x}" for x in improvements]
    return "\n".join(lines)

async def send_result(message, data, mode="image"):
    total = authoritative_total24(data)
    normalize_summary_score(data)
    disclaimer = (
        "\n\n⚠️ Bu sun’iy intellekt yordamida tayyorlangan natija. "
        "Haqiqiy ekspert natijasidan biroz farq qilishi mumkin.\n"
        "Agar haqiqiy natijangizni yanada aniqroq bilmoqchi bo‘lsangiz, "
        "«Haqiqiy ekspert yordamida baholash» bo‘limini tanlang."
    )
    if mode == "text":
        text = make_text_result(data) + disclaimer
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
    caption=(
        f"📊 {total:g}/24  •  75 ballik ekvivalent: {to_75(total)}/75"
        + disclaimer
    )
    await message.reply_photo(photo=InputFile(img,filename="esse_natijasi.jpg"),caption=caption[:1024])

async def send_user_stats(message,user_id):
    img=await asyncio.to_thread(make_stats_image,user_id)
    await message.reply_photo(photo=InputFile(img,filename="statistika.jpg"),caption="📊 Statistikangiz")

async def statistics_menu_callback(update, context):
    query=update.callback_query
    await query.answer()
    uid=update.effective_user.id
    if query.data=="stats_personal":
        await send_user_stats(query.message, uid)
    elif query.data=="stats_progress":
        await send_user_stats(query.message, uid)
        await query.message.reply_text(
            "📈 Rivojlanishim\n\nBu bo‘lim shaxsiy natijalaringiz dinamikasini ko‘rsatadi.",
            reply_markup=MAIN_KEYBOARD
        )
    elif query.data=="stats_deep":
        await send_deep_stats(query.message, uid)

def get_user_error_profile(user_id):
    criterion_scores = {}
    error_items = []
    with DB_LOCK, db() as c:
        rows = c.execute("SELECT result_json FROM checks WHERE user_id=? AND result_json IS NOT NULL ORDER BY id DESC LIMIT 30", (user_id,)).fetchall()
    for row in rows:
        try:
            data=json.loads(row[0])
        except Exception:
            continue
        for item in data.get("scores",[]) or []:
            try:
                criterion=int(item.get("criterion",0)); score=float(item.get("score",0))
            except Exception:
                continue
            if criterion:
                criterion_scores.setdefault(criterion,[]).append(score)
            for err in item.get("errors",[]) or []:
                if isinstance(err,dict):
                    wrong=str(err.get("wrong","")).strip(); correct=str(err.get("correct","")).strip()
                    if wrong:
                        error_items.append((criterion,wrong,correct))
    weak=[]
    for criterion,scores in criterion_scores.items():
        avg=sum(scores)/len(scores)
        if avg < 2:
            weak.append((avg,criterion,len(scores)))
    weak.sort()
    return weak,error_items

async def send_deep_stats(message,user_id):
    with DB_LOCK, db() as c:
        rows=c.execute("SELECT result_json,total,created_at FROM checks WHERE user_id=? AND result_json IS NOT NULL ORDER BY id DESC LIMIT 30",(user_id,)).fetchall()
    if not rows:
        await message.reply_text("📊 Chuqur statistika uchun kamida bitta esse tekshirtiring.",reply_markup=MAIN_KEYBOARD); return
    buckets={i:[] for i in range(1,13)}
    totals=[]
    for r in rows:
        try: d=json.loads(r[0]); totals.append(float(r[1] or 0))
        except Exception: continue
        for x in d.get("scores",[]) or []:
            try: buckets[int(x.get("criterion"))].append(float(x.get("score",0)))
            except Exception: pass
    avgs=[(sum(v)/len(v),cid,len(v)) for cid,v in buckets.items() if v]
    avgs.sort()
    first=min(totals[-1],24) if totals else 0; latest=max(totals[0],0) if totals else 0
    lines=["📊 CHUQUR STATISTIKA","",f"Tahlil bazasi: so‘nggi {len(rows)} ta esse",f"O‘rtacha ball: {sum(totals)/len(totals):.1f}/24",f"Eng yuqori: {max(totals):g}/24",f"Eng past: {min(totals):g}/24"]
    if len(totals)>=2: lines.append(f"Oxirgi natija: {totals[0]:g}/24  |  Oldingi: {totals[1]:g}/24  |  Farq: {totals[0]-totals[1]:+.1f}")
    if avgs:
        lines += ["","🔻 KO‘PROQ ISHLASH KERAK:"]
        for avg,cid,n in avgs[:5]: lines.append(f"• {cid}. {CRITERION_NAMES.get(cid)} — {avg:.2f}/2 ({n} ta)")
        lines += ["","🔺 YAXSHI NATIJA:"]
        for avg,cid,n in sorted(avgs,reverse=True)[:3]: lines.append(f"• {cid}. {CRITERION_NAMES.get(cid)} — {avg:.2f}/2")
    await message.reply_text("\n".join(lines)[:3900],reply_markup=MAIN_KEYBOARD)

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

async def admin_users_callback(update, context):
    query=update.callback_query
    if not await is_admin(update):
        await query.answer("⛔ Faqat admin uchun.", show_alert=True); return
    await query.answer()
    rows=admin_users_page()
    if not rows:
        await query.edit_message_text("👥 Hozircha foydalanuvchilar yo‘q.")
        return
    await query.edit_message_text("👥 Foydalanuvchilar\n\nKerakli foydalanuvchini tanlang:", reply_markup=admin_user_keyboard(rows))

async def admin_user_callback(update, context):
    query=update.callback_query
    if not await is_admin(update):
        await query.answer("⛔ Faqat admin uchun.", show_alert=True); return
    await query.answer()
    try: uid=int(query.data.split("_",2)[2])
    except Exception:
        await query.edit_message_text("⚠️ Foydalanuvchi IDsi noto‘g‘ri."); return
    with DB_LOCK, db() as c:
        u=c.execute("SELECT user_id,username,first_name,last_name,joined_at,last_seen FROM users WHERE user_id=?",(uid,)).fetchone()
    if not u:
        await query.edit_message_text("⚠️ Foydalanuvchi topilmadi."); return
    rows=admin_user_checks(uid)
    name=' '.join(x for x in [u['first_name'],u['last_name']] if x).strip() or 'Noma’lum'
    text=f"👤 {name}\n🆔 {uid}"
    if u['username']: text += f"\n🔗 @{u['username']}"
    text += f"\n\n📝 Tekshiruvlar: {len(rows)} ta\n\nKerakli natijani tanlang:"
    markup=admin_checks_keyboard(rows) if rows else None
    if rows:
        await query.edit_message_text(text, reply_markup=markup)
    else:
        await query.edit_message_text(text.replace("\n\nKerakli natijani tanlang:","\n\nHali tekshiruv yo‘q."))

async def admin_check_callback(update, context):
    query=update.callback_query
    if not await is_admin(update):
        await query.answer("⛔ Faqat admin uchun.", show_alert=True); return
    await query.answer()
    try: cid=int(query.data.split("_",2)[2])
    except Exception:
        await query.edit_message_text("⚠️ Natija IDsi noto‘g‘ri."); return
    row=admin_check_detail(cid)
    if not row:
        await query.edit_message_text("⚠️ Natija topilmadi."); return
    name=' '.join(x for x in [row.get('first_name',''),row.get('last_name','')] if x).strip() or 'Noma’lum'
    header=(f"📋 ESSE NATIJASI\n\n👤 {name}\n🆔 {row.get('user_id')}\n"
            f"📅 {row.get('created_at','')}\n📚 Usul: {row.get('mode','')}\n"
            f"📝 So‘zlar: {row.get('words',0)}\n🎯 Ball: {float(row.get('total') or 0):g}/24\n"
            f"📌 Mavzu: {str(row.get('topic','')).strip()[:500]}")
    detail=None
    if row.get('result_json'):
        try: detail=json.loads(row['result_json'])
        except Exception: detail=None
    if detail:
        header += f"\n\n📊 75 ballik: {to_75(float(row.get('total') or 0))}/75"
        for item in sorted(detail.get('scores',[]) or [], key=lambda x:int(x.get('criterion',0))):
            c=int(item.get('criterion',0)); score=float(item.get('score',0)); reason=str(item.get('reason','')).strip()
            header += f"\n\n{c}. {CRITERION_NAMES.get(c,item.get('name',f'Mezon {c}'))}: {score:g}/2"
            if reason: header += f"\n{reason[:700]}"
            for err in (item.get('errors') or [])[:2]:
                if isinstance(err,dict): header += f"\n❌ {err.get('wrong','—')} → {err.get('correct','—')}\n   {err.get('explanation','')[:300]}"
        if detail.get('summary'): header += "\n\n🧾 XULOSA\n"+str(detail['summary'])[:1200]
        if detail.get('improvements'):
            header += "\n\n🎯 TAVSIYALAR\n"+"\n".join('• '+str(x) for x in detail['improvements'][:5])
    else:
        header += "\n\nℹ️ Bu tekshiruv eski yozuv bo‘lgani uchun to‘liq AI tahlili bazada saqlanmagan. Yangi tekshiruvlarda to‘liq natija saqlanadi."
    # Telegram message limit: split into safe chunks.
    chunks=[header[i:i+3800] for i in range(0,len(header),3800)]
    for i,ch in enumerate(chunks):
        if i==0:
            await query.edit_message_text(ch, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Natijalar ro‘yxati", callback_data=f"admin_user_{row.get('user_id')}")]]))
        else:
            await context.bot.send_message(ADMIN_ID,ch)

# ============================================================
# COMMANDS / HANDLERS
# ============================================================




async def start(update,context):
    upsert_user(update.effective_user)
    context.user_data.clear()
    if not await require_subscription(update, context): return
    await update.message.reply_text(
        "Assalomu alaykum!\n\n"
        "Esse tekshirish uchun «✍️ Esse tekshirish» tugmasini bosing.\n"
        "Avval esse mavzusini yuborasiz, keyin baholash usulini tanlaysiz.",
        reply_markup=MAIN_KEYBOARD
    )

async def new_cmd(update,context):
    upsert_user(update.effective_user)
    if not await require_subscription(update, context): return
    context.user_data.clear(); context.user_data["stage"]="topic"
    await update.message.reply_text("📝 Esse mavzusi/vaziyatini yuboring.", reply_markup=MAIN_KEYBOARD)

async def help_cmd(update,context):
    upsert_user(update.effective_user)
    if not await require_subscription(update, context): return
    await update.message.reply_text(
        "✍️ Esse tekshirish tugmasini bosing.\n"
        "1. Mavzuni yuboring.\n"
        "2. Sun’iy intellekt yoki haqiqiy ekspert usulini tanlang.\n"
        "3. AI usulida esse matni, rasm yoki PDF yuboriladi.\n"
        "4. Tekshiruvdan so‘ng natija rasmli yoki matnli shaklda olinadi.",
        reply_markup=MAIN_KEYBOARD
    )

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
        if context.user_data.get("stage") != "essay_ai":
            await message.reply_text("Avval «✍️ Esse tekshirish» tugmasini bosing.", reply_markup=MAIN_KEYBOARD)
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
            result=await run_evaluation_silently(lambda: evaluate_images(topic, images))
            save_check(user_id,"image",topic,result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
            context.user_data["pending_result"] = result
            context.user_data["stage"] = "result_mode"
            await status.edit_text(f"✅ {len(file_ids)} ta rasmli esse tekshirildi.")
            await message.reply_text("📬 Natijani qanday usulda qabul qilasiz?", reply_markup=RESULT_FORMAT_KEYBOARD)
    except Exception:
        logger.exception("photo album error")
        try:
            await message.reply_text("⚠️ Rasmlar bilan tekshiruvni yakunlashda texnik muammo yuz berdi. Birozdan so‘ng qayta urinib ko‘ring.")
        except Exception:
            pass
        context.user_data.clear()

async def handle_pdf(update, context):
    upsert_user(update.effective_user)
    if not await require_subscription(update, context):
        return
    if context.user_data.get("growth_practice"):
        document=update.message.document
        size=int(document.file_size or 0)
        if size and size>MAX_PDF_SIZE_BYTES:
            await update.message.reply_text(f"⚠️ PDF juda katta. Maksimal hajm: {MAX_PDF_SIZE_MB:g} MB.",reply_markup=GROWTH_KEYBOARD); return
        status=await update.message.reply_text("⏳ Mashq PDF fayli tekshirilmoqda...",reply_markup=GROWTH_KEYBOARD)
        try:
            f=await context.bot.get_file(document.file_id); b=io.BytesIO(); await asyncio.wait_for(f.download_to_memory(b),timeout=60)
            session=context.user_data.pop("growth_practice")
            result=await run_evaluation_silently(lambda: evaluate_pdf(session["topic"],b.getvalue()))
            save_check(update.effective_user.id,"growth_pdf",session["topic"],result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
            await send_result(update.message,result,"image")
            tips=result.get("improvements") or []
            if tips:
                await send_learning_card(update.message,"🎯 MASHQ UCHUN TAVSIYALAR","Keyingi esse uchun aniq tavsiyalar",[("Amaliy tavsiyalar",[str(x) for x in tips[:8]])])
            await status.edit_text("✅ Mashq PDF essesi tekshirildi.")
        except Exception:
            logger.exception("growth practice pdf error"); await status.edit_text("⚠️ Mashq PDFni tekshirishda texnik muammo yuz berdi.")
        return
    if context.user_data.get("stage") != "essay_ai":
        await update.message.reply_text(
            "Avval «✍️ Esse tekshirish» tugmasini bosing.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    document = update.message.document
    size = int(document.file_size or 0)
    if size and size > MAX_PDF_SIZE_BYTES:
        await update.message.reply_text(
            f"📄 PDF juda katta. Maksimal hajm: {MAX_PDF_SIZE_MB:g} MB.\n"
            f"Iltimos, PDFni kichraytirib qayta yuboring.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    name = (document.file_name or "").lower()
    mime = (document.mime_type or "").lower()
    if not (name.endswith(".pdf") or mime == "application/pdf"):
        await update.message.reply_text(
            "📄 Faqat PDF fayl qabul qilinadi.", reply_markup=MAIN_KEYBOARD
        )
        return

    lock = await user_lock(update.effective_user.id)
    if lock.locked():
        await update.message.reply_text("⏳ Oldingi tekshiruv tugamadi.")
        return

    async with lock:
        status = await update.message.reply_text(
            f"⏳ PDF qabul qilindi. Maksimal {MAX_PDF_PAGES} sahifagacha tekshiriladi..."
        )
        try:
            f = await context.bot.get_file(document.file_id)
            b = io.BytesIO()
            await asyncio.wait_for(f.download_to_memory(b), timeout=60)
            pdf_bytes = b.getvalue()

            if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
                raise ValueError(f"PDF hajmi {MAX_PDF_SIZE_MB:g} MB dan katta")

            topic = context.user_data.get("topic", "")
            result = await run_evaluation_silently(
                lambda: evaluate_pdf(topic, pdf_bytes)
            )
            save_check(
                update.effective_user.id,
                "pdf",
                topic,
                result.get("total", 0),
                result.get("word_count", 0),
                result.get("status", "normal"),
                result
            )
            context.user_data["pending_result"] = result
            context.user_data["stage"] = "result_mode"
            pages = int(result.get("_pdf_pages", 0) or 0)
            await status.edit_text(f"✅ PDFdagi {pages} sahifalik esse tekshirildi.")
            await update.message.reply_text("📬 Natijani qanday usulda qabul qilasiz?", reply_markup=RESULT_FORMAT_KEYBOARD)
        except ValueError as e:
            logger.warning("pdf rejected: %s", e)
            await status.edit_text(
                f"⚠️ PDF qabul qilinmadi: {e}.\n"
                f"Maksimal hajm {MAX_PDF_SIZE_MB:g} MB, maksimal {MAX_PDF_PAGES} sahifa."
            )
            context.user_data.clear()
        except asyncio.TimeoutError:
            logger.warning("pdf processing timeout")
            await status.edit_text(
                "⚠️ PDFni qayta ishlash juda uzoq davom etdi. Faylni kichraytirib "
                "yoki sahifalar sonini kamaytirib qayta yuboring."
            )
            context.user_data.clear()
        except Exception:
            logger.exception("pdf error")
            await status.edit_text(
                "⚠️ PDFni tekshirishda texnik muammo yuz berdi. "
                "Fayl hajmi va sahifalar soni me'yorida bo‘lsa, qayta urinib ko‘ring."
            )
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
    if context.user_data.get("growth_practice"):
        lock=await user_lock(update.effective_user.id)
        if lock.locked(): await update.message.reply_text("⏳ Oldingi tekshiruv tugamadi."); return
        async with lock:
            status=await update.message.reply_text("⏳ Mashq rasmi o‘qilmoqda va tekshirilmoqda...",reply_markup=GROWTH_KEYBOARD)
            try:
                file_id=update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
                f=await context.bot.get_file(file_id); b=io.BytesIO(); await f.download_to_memory(b)
                session=context.user_data.pop("growth_practice")
                result=await run_evaluation_silently(lambda: evaluate_image(session["topic"],b.getvalue()))
                save_check(update.effective_user.id,"growth_image",session["topic"],result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
                await send_result(update.message,result,"image")
                tips=result.get("improvements") or []
                if tips:
                    await send_learning_card(update.message,"🎯 MASHQ UCHUN TAVSIYALAR","Keyingi esse uchun aniq tavsiyalar",[("Amaliy tavsiyalar",[str(x) for x in tips[:8]])])
                await status.edit_text("✅ Mashq essesi tekshirildi.")
            except Exception:
                logger.exception("growth practice image error")
                await status.edit_text("⚠️ Mashq rasmini tekshirishda texnik muammo yuz berdi.")
        return
    if context.user_data.get("stage")!="essay_ai":
        await update.message.reply_text("Avval «✍️ Esse tekshirish» tugmasini bosing.",reply_markup=MAIN_KEYBOARD); return

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
            result=await run_evaluation_silently(lambda: evaluate_image(topic,b.getvalue()))
            save_check(update.effective_user.id,"image",topic,result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
            context.user_data["pending_result"] = result
            context.user_data["stage"] = "result_mode"
            await status.edit_text("✅ Tekshiruv tugadi.")
            await update.message.reply_text("📬 Natijani qanday usulda qabul qilasiz?", reply_markup=RESULT_FORMAT_KEYBOARD)
        except Exception:
            logger.exception("image error")
            await status.edit_text("⚠️ Tekshiruvni yakunlashda texnik muammo yuz berdi. Birozdan so‘ng qayta urinib ko‘ring.")
            context.user_data.clear()


# ============================================================
# ESSENI O‘STIRISH — YORDAMCHI FUNKSIYALAR
# ============================================================
LESSONS = {
    1: ("Publitsistik uslub", "Fikrni xolis, aniq va ommabop tarzda bayon qiling. Badiiy bezakni dalil o‘rniga ishlatmang."),
    2: ("Ikkala qarash va shaxsiy qarash", "Har ikki tomonning fikrini aniq ko‘rsating va xulosada o‘z pozitsiyangizni ravshan belgilang."),
    3: ("Dalillash", "Har ikki qarash uchun kamida ikkita aniq, mavzuga bevosita aloqador sabab yoki dalil keltiring."),
    4: ("Kirish, asosiy qism, xulosa", "Kirishda muammoni oching, asosiy qismda qarashlarni tahlil qiling, xulosada pozitsiyangizni yakunlang."),
    5: ("Mantiqiy qurilish va xatboshilar", "Har bir asosiy xatboshida bitta asosiy fikrni rivojlantiring va fikrlar orasida mantiqiy bog‘lanish yarating."),
    6: ("Izchillik va fikrlar takrori", "Har bir yangi gap oldingi fikrni rivojlantirsin. Bir xil mazmunni ortiqcha takrorlashdan saqlaning."),
    7: ("Imlo", "So‘zlarning adabiy me’yor bo‘yicha yozilishini tekshiring. Shubhali shaklni normativ manba bilan solishtiring."),
    8: ("Punktuatsiya", "Tinish belgilarini gapning grammatik va mazmuniy tuzilishiga qarab qo‘llang; vergulni faqat pauza uchun qo‘ymang."),
    9: ("Qo‘shimcha qo‘llash", "Qo‘shimchalarning shakli va grammatik mosligini tekshiring: kelishik, egalik, ko‘plik va boshqa shakllar."),
    10: ("So‘z qo‘llash uslubiyati", "So‘zning ma’nosi va kontekstga mosligini tekshiring. Faqat g‘alati tuyulgani uchun so‘zni xato deb hisoblamang."),
    11: ("Leksik xilma-xillik", "Bir xil so‘zlarni keraksiz takrorlamasdan, mazmunga mos sinonim va turli ifoda vositalaridan foydalaning."),
    12: ("Sheva, vulgarizm, varvarizm, parazit so‘zlar", "Argumentli esseda adabiy til me’yorini saqlang va parazit, shevaga xos yoki nomaqbul birliklarni cheklang."),
}

def latest_result(user_id):
    with DB_LOCK, db() as c:
        row = c.execute("SELECT result_json FROM checks WHERE user_id=? AND result_json IS NOT NULL ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        logger.exception("latest_result json decode error")
        return None

def build_learning_plan(data, limit=5):
    """Eng past ball olgan mezonlarni aniqlaydi. Tenglikda mezon raqami saqlanadi."""
    rows=[]
    for item in data.get("scores",[]) or []:
        try:
            cid=int(item.get("criterion",0)); score=float(item.get("score",0))
        except Exception:
            continue
        if cid in CRITERION_NAMES:
            rows.append((score,cid))
    rows.sort(key=lambda x:(x[0],x[1]))
    return rows[:max(1,int(limit))]

async def send_improvement(message,user_id):
    data=await asyncio.to_thread(latest_result,user_id)
    if not data:
        await message.reply_text("🔄 Esseni yaxshilash uchun avval esse tekshirtiring.",reply_markup=GROWTH_KEYBOARD)
        return
    total=authoritative_total24(data)
    weak=build_learning_plan(data,limit=5)
    sections=[]
    if weak:
        items=[]
        for score,cid in weak:
            name=CRITERION_NAMES.get(cid,f"Mezon {cid}")
            items.append(f"{name}: {score:g}/2")
        sections.append(("📉 ENG KO‘P E’TIBOR TALAB QILADIGAN MEZONLAR",items))
        tasks=[]
        for _,cid in weak[:3]:
            name,lesson=LESSONS.get(cid,(CRITERION_NAMES.get(cid,f"Mezon {cid}"),""))
            tasks.append(f"{name}: {lesson}")
        sections.append(("🎯 KEYINGI ESSE UCHUN VAZIFALAR",tasks))
    sections.append(("📋 TOPSHIRISHDAN OLDINGI TEKSHIRUV",[
        "Har ikki qarash aniq berildimi?",
        "Har ikki qarash kamida ikki aniq sabab/dalil bilan asoslandimi?",
        "Shaxsiy pozitsiya xulosada ravshanmi?",
        "Imlo va punktuatsiya xatolari qayta tekshirildimi?",
        "Xulosa mavzuga bevosita javob beradimi?",
    ]))
    await send_learning_card(message,"🔄 ESSENI YAXSHILASH",f"Oxirgi natija: {total:g}/24  •  {to_75(total)}/75",sections,caption="📈 Keyingi esseda shu vazifalarni bajarishga e’tibor bering.")

# ============================================================
# ESSENI O‘STIRISH — YANGI O‘QUV FUNKSIYALARI
# ============================================================
DAILY_ESSAY_TOPICS = [
    "Ayrimlar sun’iy intellekt ta’limni yaxshilaydi desa, boshqalar uning salbiy oqibatlaridan xavotirda.",
    "Ba’zilar onlayn ta’limni qulay deb hisoblaydi, boshqalar esa an’anaviy ta’lim samaraliroq deb o‘ylaydi.",
    "Ayrimlar yoshlar bo‘sh vaqtini ijtimoiy tarmoqlarda o‘tkazishini tabiiy hol deb biladi, boshqalar esa buning zararli tomonlarini ta’kidlaydi.",
    "Ba’zilar kitob o‘qishning elektron shakli qulayligini aytadi, boshqalar qog‘oz kitobni afzal ko‘radi.",
    "Ayrimlar shaharlarda jamoat transportini rivojlantirish zarur deb hisoblaydi, boshqalar shaxsiy avtomobil qulayroq deydi.",
    "Ba’zilar maktablarda uy vazifasini kamaytirish kerak deb hisoblaydi, boshqalar muntazam mashq bilimni mustahkamlaydi deydi.",
    "Ayrimlar imtihon natijasi o‘quvchining bilimini to‘liq ko‘rsatadi deb hisoblaydi, boshqalar baholashning boshqa shakllarini ham qo‘llash kerak deydi.",
    "Ba’zilar chet tilini erta yoshdan o‘rganish kerak deb hisoblaydi, boshqalar ona tilini mukammal egallashni birinchi o‘ringa qo‘yadi.",
    "Ayrimlar yoshlar uchun sport bilan shug‘ullanish majburiy bo‘lishi kerak deb hisoblaydi, boshqalar buni shaxsiy tanlov deb biladi.",
    "Ba’zilar masofadan ishlash vaqtni tejaydi deb hisoblaydi, boshqalar jamoa bilan bir joyda ishlash samaraliroq deydi.",
]

def daily_essay_topic():
    from datetime import date
    return DAILY_ESSAY_TOPICS[date.today().toordinal() % len(DAILY_ESSAY_TOPICS)]

async def send_daily_essay_practice(message, user_id, context):
    topic=daily_essay_topic()
    context.user_data["growth_practice"]={"topic":topic,"started_at":datetime.utcnow().isoformat()}
    await message.reply_text("✍️ ESSE YOZISH MASHQI\n\n📝 Bugungi mavzu:\n"+topic+"\n\nEsseni shu chatga yuboring. Matn, rasm yoki PDF yuborishingiz mumkin.\nBot uni BBA 24 ballik mezonlar asosida tekshiradi. Natija, xatolar va tavsiyalar rasmli natija kartasida chiqadi.",reply_markup=GROWTH_KEYBOARD)

async def finish_growth_practice_text(message,user_id,essay_text,context):
    session=context.user_data.pop("growth_practice",None)
    if not session: return False
    await message.reply_text("⏳ Mashq essesi tekshirilmoqda...",reply_markup=GROWTH_KEYBOARD)
    try:
        result=await run_evaluation_silently(lambda: evaluate_text(session["topic"],essay_text))
        save_check(user_id,"growth_text",session["topic"],result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
        await send_result(message,result,"image")
        tips=result.get("improvements") or []
        if tips:
            await send_learning_card(message,"🎯 MASHQ UCHUN TAVSIYALAR","Keyingi esse uchun aniq tavsiyalar",[("Amaliy tavsiyalar",[str(x) for x in tips[:8]])])
    except Exception:
        logger.exception("growth essay practice error")
        await message.reply_text("⚠️ Mashq esseni tekshirishda texnik muammo yuz berdi. Qayta urinib ko‘ring.",reply_markup=GROWTH_KEYBOARD)
    return True

async def send_evidence_helper(message,user_id,context,topic=None):
    if not topic:
        context.user_data["growth_evidence_waiting"]=True
        await message.reply_text("💡 DALIL TOPIB BERISH\n\nMavzuni yuboring.\n\nMasalan:\n«Ayrimlar onlayn ta’limni ma’qul ko‘rishadi, boshqalar offlayn ta’lim tarafdori.»",reply_markup=GROWTH_KEYBOARD); return
    await message.reply_text("🔎 Mavzu uchun dalil turlari tayyorlanmoqda...",reply_markup=GROWTH_KEYBOARD)
    prompt=f'''Sen argumentli esse uchun dalil tayyorlovchi yordamchisan.
Mavzu: {topic}
5 tur ber: statistik dalil, hayotiy misol, tarixiy misol, mutaxassis fikri, mantiqiy dalil.
Muhim: manbasi tekshirilmagan raqam, ism yoki iqtibosni fakt sifatida UYDIMA. Ishonchli aniq manba bo‘lmasa, raqam o‘rniga qanday statistikani izlash kerakligini ayt. Mutaxassis fikrida tasdiqlanmagan iqtibosni qo‘shtirnoqqa olma.
JSON: {{"statistical":{{"claim":"...","source":"..."}},"life":"...","historical":"...","expert":{{"claim":"...","source":"..."}},"logical":"..."}}'''
    try:
        data=await openai_json(prompt,max_output_tokens=6000); st=data.get("statistical") or {}; ex=data.get("expert") or {}
        await send_learning_card(message,"💡 DALILLAR BANKI",f"📝 {topic}",[
            ("📊 STATISTIK DALIL",[str(st.get("claim","—")), f"Manba: {st.get('source','Tekshirish kerak')}"]),
            ("👤 HAYOTIY MISOL",[str(data.get("life","—"))]),
            ("🏛️ TARIXIY MISOL",[str(data.get("historical","—"))]),
            ("🎓 MUTAXASSIS FIKRI",[str(ex.get("claim","—")), f"Manba: {ex.get('source','Tekshirish kerak')}"]),
            ("🧠 MANTIQIY DALIL",[str(data.get("logical","—"))]),
            ("⚠️ TEKSHIRUV",["Statistik raqam va iqtibosni ishlatishdan oldin manbasini tekshiring."])
        ])
    except Exception:
        logger.exception("evidence helper error"); await message.reply_text("⚠️ Dalillarni tayyorlashda texnik muammo yuz berdi. Mavzuni qayta yuboring.",reply_markup=GROWTH_KEYBOARD)

def _learning_card_bytes(title, subtitle, sections):
    """O‘quv bo‘limlari uchun matnni Telegramga rasm-card ko‘rinishida tayyorlaydi."""
    W=1200; M=55; gap=22
    title_f=font(46,True); sub_f=font(23); section_f=font(28,True); body_f=font(21); small_f=font(18)
    # First pass: calculate dynamic height.
    dummy=Image.new("RGB",(W,100),"white"); d=ImageDraw.Draw(dummy)
    content_w=W-2*M
    blocks=[]
    total_h=145
    for heading, body in sections:
        h_lines=_fit_lines(d, heading, section_f, content_w, 2)
        b_lines=[]
        if isinstance(body,(list,tuple)):
            for item in body:
                b_lines.extend(_fit_lines(d, "• "+str(item), body_f, content_w, 3))
        else:
            b_lines=_fit_lines(d, str(body), body_f, content_w, 8)
        bh=max(90, 35+len(h_lines)*34+len(b_lines)*29)
        blocks.append((h_lines,b_lines,bh))
        total_h += bh+gap
    total_h += 70
    img=Image.new("RGB",(W,total_h),(246,251,248)); d=ImageDraw.Draw(img)
    d.rounded_rectangle((22,22,W-22,total_h-22),radius=30,fill=(255,255,255),outline=(216,232,222),width=2)
    emb=load_emblem(82)
    tx=M
    if emb:
        img.paste(emb,(M,42),emb); tx=M+105
    d.text((tx,42),title,font=title_f,fill=(27,116,76))
    for i,line in enumerate(_fit_lines(d,subtitle,sub_f,W-tx-M,2)):
        d.text((tx,98+i*29),line,font=sub_f,fill=(80,95,87))
    y=150
    for h_lines,b_lines,bh in blocks:
        d.rounded_rectangle((M,y,W-M,y+bh),radius=22,fill=(242,249,244),outline=(218,233,222),width=1)
        ty=y+18
        for ln in h_lines:
            d.text((M+22,ty),ln,font=section_f,fill=(42,57,50)); ty+=34
        ty+=4
        for ln in b_lines:
            d.text((M+22,ty),ln,font=body_f,fill=(70,84,77)); ty+=29
        y+=bh+gap
    out=io.BytesIO(); out.name="esse_ostirish.jpg"
    img.save(out,"JPEG",quality=90,optimize=True); out.seek(0)
    return out

async def send_learning_card(message,title,subtitle,sections,caption=None):
    bio=_learning_card_bytes(title,subtitle,sections)
    await message.reply_photo(photo=InputFile(bio,filename="esse_ostirish.jpg"),caption=caption,reply_markup=GROWTH_KEYBOARD)

async def send_error_lesson(message,user_id):
    data=await asyncio.to_thread(latest_result,user_id)
    if not data:
        await message.reply_text("📚 Xatolar ustida ishlash uchun avval esse tekshirtiring.",reply_markup=MAIN_KEYBOARD); return
    weak=build_learning_plan(data); cid=weak[0][1] if weak else 7
    name,lesson=LESSONS.get(cid,(CRITERION_NAMES.get(cid,f"Mezon {cid}"),""))
    errors=[]
    for item in data.get("scores",[]) or []:
        if int(item.get("criterion",0) or 0)==cid:
            errors=[e for e in item.get("errors",[]) or [] if isinstance(e,dict)]
    score=dict((int(x.get("criterion",0)),x.get("score",0)) for x in data.get("scores",[]) or []).get(cid,0)
    examples=[]
    for e in errors[:5]:
        examples.append(f"{e.get('wrong','—')} → {e.get('correct','—')}" + (f" — {e.get('explanation')}" if e.get('explanation') else ""))
    if not examples: examples=["Hozircha aniq xato namunasi saqlanmagan. Keyingi esseda shu mezonni alohida nazorat qiling."]
    await send_learning_card(message,"📚 XATOLAR USTIDA ISHLASH",f"Eng ko‘p ishlash kerak bo‘lgan yo‘nalish: {name}",[
        (f"🎯 {name} — {score}/2",lesson),
        ("🔎 SIZDA ANIQLANGAN MISOLLAR",examples),
        ("✍️ AMALIY VAZIFA",["Shu mezonga oid 3 ta to‘g‘ri gap yozing.","Keyingi esseda shu mezonni topshirishdan oldin alohida tekshiring."])
    ])


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
            if text=="👥 Foydalanuvchilar":
                rows=admin_users_page()
                if not rows:
                    await update.message.reply_text("👥 Hozircha foydalanuvchilar yo‘q.",reply_markup=ADMIN_KEYBOARD); return
                await update.message.reply_text("👥 Foydalanuvchilar\n\nKerakli foydalanuvchini tanlang:",reply_markup=admin_user_keyboard(rows)); return
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
    if text=="✍️ Esse tekshirish":
        context.user_data.clear()
        context.user_data["stage"]="topic"
        await update.message.reply_text("📝 Esse mavzusi/vaziyatini yuboring.", reply_markup=MAIN_KEYBOARD)
        return
    if text=="📊 Statistika":
        await update.message.reply_text(
            "📊 STATISTIKA BO‘LIMI\n\nKerakli bo‘limni tanlang:",
            reply_markup=STATISTICS_MENU
        )
        return
    if text=="🌱 Esseni o‘stirish":
        await show_growth_gate(update.message,update.effective_user.id)
        return
    if text=="✍️ Esse yozish mashqi":
        await send_daily_essay_practice(update.message,update.effective_user.id,context); return
    if text=="💡 Dalil topib berish":
        await send_evidence_helper(update.message,update.effective_user.id,context); return
    if text=="⬅️ Asosiy menyu":
        await update.message.reply_text("🏠 Asosiy menyu", reply_markup=MAIN_KEYBOARD)
        return
    if text=="📚 Xatolar ustida ishlash":
        await send_error_lesson(update.message,update.effective_user.id)
        return
    if text=="🔄 Esseni yaxshilash":
        await send_improvement(update.message,update.effective_user.id)
        return

    if context.user_data.get("growth_practice") and text != "⬅️ Asosiy menyu":
        if await finish_growth_practice_text(update.message,update.effective_user.id,text,context): return
    if context.user_data.pop("growth_evidence_waiting",False):
        await send_evidence_helper(update.message,update.effective_user.id,context,text); return

    stage=context.user_data.get("stage")
    if stage in (None,"topic"):
        context.user_data["topic"] = text
        context.user_data["stage"] = "method"
        await update.message.reply_text(
            "✅ Esse mavzusi qabul qilindi.\n\nEndi baholash usulini tanlang:",
            reply_markup=EVALUATION_METHOD_KEYBOARD
        )
        return
    if stage!="essay_ai": return
    lock=await user_lock(update.effective_user.id)
    if lock.locked(): await update.message.reply_text("⏳ Oldingi tekshiruv tugamadi."); return
    async with lock:
        status=await update.message.reply_text("⏳ Esse tekshirilmoqda...")
        try:
            topic=context.user_data.get("topic","")
            result=await run_evaluation_silently(lambda: evaluate_text(topic,text))
            save_check(update.effective_user.id,"text",topic,result.get("total",0),result.get("word_count",word_count(text)),result.get("status","normal"),result)
            context.user_data["pending_result"] = result
            context.user_data["stage"] = "result_mode"
            await status.edit_text("✅ Tekshiruv tugadi.")
            await update.message.reply_text("📬 Natijani qanday usulda qabul qilasiz?", reply_markup=RESULT_FORMAT_KEYBOARD)
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
    app.add_handler(CommandHandler(["admin", "panel"], admin_cmd))
    app.add_handler(CallbackQueryHandler(subscription_callback, pattern="^check_subscription$"))
    app.add_handler(CallbackQueryHandler(evaluation_method_callback, pattern="^(eval_ai|eval_expert|expert_agree|expert_back)$"))
    app.add_handler(CallbackQueryHandler(result_format_callback, pattern="^result_(image|text)$"))
    app.add_handler(CallbackQueryHandler(statistics_menu_callback, pattern="^stats_(personal|progress|deep)$"))
    app.add_handler(CallbackQueryHandler(admin_users_callback, pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_user_callback, pattern="^admin_user_[0-9]+$"))
    app.add_handler(CallbackQueryHandler(admin_check_callback, pattern="^admin_check_[0-9]+$"))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE,handle_photo))
    app.add_handler(MessageHandler(filters.Document.PDF,handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_text))
    app.add_error_handler(telegram_error_handler)
    logger.info("BOT STARTED | model=%s | admin=%s | max_parallel_evaluations=%s", MODEL, ADMIN_ID, MAX_PARALLEL_EVALUATIONS)
    app.run_polling(drop_pending_updates=True,close_loop=False)

if __name__=="__main__":
    main()
