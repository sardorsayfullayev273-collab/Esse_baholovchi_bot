from urllib.parse import quote, urlparse, unquote, parse_qsl, parse_qs
import os
import re
import csv
import io
import json
import sqlite3
import asyncio
import hashlib
import hmac
import time
import urllib.request
import logging
import threading
import random
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, BadRequestError
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, MenuButtonWebApp, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler, ContextTypes, filters, TypeHandler, ApplicationHandlerStop
import mini_extra as mx

# Milliy sertifikat testi — mavjud esse/dictionary/growth manbalariga tegmaydigan qo'shimcha modul
from national_certificate import (init_national_db, init_prep_db, get_test, list_tests, create_test, grade as grade_national, level_for, save_attempt, latest_essay_check, essay_for_test, diagnostic_result, set_setting, setting, NATIONAL_ADMIN_ID, combined_diagnostic_score, create_prep_resource, list_prep_resources, list_all_prep_resources)

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
GROWTH_PRICE_STARS = int(os.getenv("GROWTH_PRICE_STARS", "50"))
GROWTH_DAYS = 30
REQUIRED_CHANNEL_URL = os.getenv("REQUIRED_CHANNEL_URL", "https://t.me/milliysertifikat_ona_tili1")
MINIAPP_URL = os.getenv("MINIAPP_URL", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@").strip()  # post_init da avtomatik aniqlanadi
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")

def miniapp_web_url():
    base = MINIAPP_URL or (f"{RENDER_EXTERNAL_URL}/miniapp/" if RENDER_EXTERNAL_URL else "")
    if not base or not RENDER_EXTERNAL_URL:
        return base
    # If Mini App is hosted separately (e.g. GitHub Pages), pass the Render API
    # origin in the URL so the static app can call the bot backend.
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}api={quote(RENDER_EXTERNAL_URL, safe='')}"

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
        c.execute('''CREATE TABLE IF NOT EXISTS growth_premium(
            user_id INTEGER PRIMARY KEY,
            expires_at TEXT NOT NULL,
            payment_charge_id TEXT,
            stars INTEGER NOT NULL DEFAULT 0,
            purchased_at TEXT NOT NULL
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
        if miniapp_web_url():
            await query.message.reply_text("🎓 Milliy sertifikat testini ham ishlashingiz mumkin:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎓 Milliy sertifikat", web_app=WebAppInfo(url=miniapp_web_url()))]]))
    except Exception:
        logger.exception("result format send error")
        await query.message.reply_text("⚠️ Natijani yuborishda texnik muammo yuz berdi. Qayta urinib ko‘ring.", reply_markup=MAIN_KEYBOARD)
    finally:
        context.user_data.clear()

# ============================================================
# 🌱 ESSENI O‘STIRISH PREMIUM
# ============================================================
def growth_premium_until(user_id):
    with DB_LOCK, db() as c:
        row=c.execute("SELECT expires_at FROM growth_premium WHERE user_id=?",(user_id,)).fetchone()
    if not row: return None
    try: return datetime.fromisoformat(row[0].replace("Z","+00:00"))
    except Exception: return None

def growth_premium_active(user_id):
    exp=growth_premium_until(user_id)
    if not exp: return False
    from datetime import timezone
    return exp > datetime.now(timezone.utc)

def growth_premium_text(user_id):
    exp=growth_premium_until(user_id)
    if not exp or not growth_premium_active(user_id): return "🔒 Premium faol emas"
    return f"✅ Premium faol\n⏳ Amal qilish muddati: {exp.strftime('%d.%m.%Y %H:%M')} UTC"

GROWTH_GATE_KEYBOARD=InlineKeyboardMarkup([
    [InlineKeyboardButton(f"💳 Premiumni faollashtirish — {GROWTH_PRICE_STARS} ⭐",callback_data="buy_growth")],
    [InlineKeyboardButton("📄 Shartlar",callback_data="growth_terms")],
])

async def show_growth_gate(message,user_id):
    await message.reply_text(
        "🌱 ESSENI O‘STIRISH\n\n"
        "Essedagi kamchiliklaringiz ustida tizimli ishlang.\n\n"
        "🧠 Xatolarim\n📚 Xatolar ustida ishlash\n🧪 5 savollik mini test\n"
        "🎯 Shaxsiy rejam\n🔄 Esseni yaxshilash\n✍️ Esse yozish mashqi\n"
        "🗂️ Esse rejasini tuzish\n💡 Dalil topib berish",
        reply_markup=GROWTH_KEYBOARD
    )

async def buy_growth_callback(update,context):
    query=update.callback_query; await query.answer(); uid=query.from_user.id
    if growth_premium_active(uid):
        await query.message.reply_text("✅ Sizda Premium allaqachon faol.",reply_markup=GROWTH_KEYBOARD); return
    try:
        await context.bot.send_invoice(chat_id=uid,title="Esseni o‘stirish — 30 kun",description="Xatolar tahlili, xato darsi, 5 savollik mini test, shaxsiy reja va esseni yaxshilash vositalari.",payload=f"growth_premium_30d:{uid}",provider_token="",currency="XTR",prices=[LabeledPrice("Esseni o‘stirish — 30 kun",GROWTH_PRICE_STARS)],start_parameter="growth-premium-30d")
    except Exception:
        logger.exception("growth invoice error"); await query.message.reply_text("⚠️ To‘lov oynasini ochishda xatolik yuz berdi. Keyinroq qayta urinib ko‘ring.",reply_markup=MAIN_KEYBOARD)

async def growth_terms_callback(update,context):
    query=update.callback_query; await query.answer()
    await query.message.reply_text("📄 PREMIUM SHARTLARI\n\n• Premium 30 kun amal qiladi.\n"+f"• Narx: {GROWTH_PRICE_STARS} Telegram Stars.\n• Premium faqat ushbu botdagi Esseni o‘stirish raqamli xizmatlarini ochadi.\n• To‘lov va xarid bo‘yicha yordam: /paysupport\n• Xarid qilishdan oldin ushbu shartlarni o‘qib chiqing.",reply_markup=GROWTH_GATE_KEYBOARD)

async def precheckout_growth(update,context):
    q=update.pre_checkout_query; payload=q.invoice_payload or ""
    if not payload.startswith("growth_premium_30d:"):
        await q.answer(ok=False,error_message="Buyurtma ma’lumoti noto‘g‘ri."); return
    try: uid=int(payload.split(":",1)[1])
    except Exception: await q.answer(ok=False,error_message="Buyurtma ma’lumoti noto‘g‘ri."); return
    if uid!=q.from_user.id or q.currency!="XTR" or q.total_amount!=GROWTH_PRICE_STARS:
        await q.answer(ok=False,error_message="To‘lov ma’lumoti mos kelmaydi."); return
    await q.answer(ok=True)

async def successful_payment_growth(update,context):
    payment=update.message.successful_payment; payload=payment.invoice_payload or ""
    if not payload.startswith("growth_premium_30d:"): return
    try: uid=int(payload.split(":",1)[1])
    except Exception: uid=update.effective_user.id
    if uid!=update.effective_user.id: return
    from datetime import timezone,timedelta
    now=datetime.now(timezone.utc); old=growth_premium_until(uid); start=max(now,old) if old and old>now else now; exp=start+timedelta(days=GROWTH_DAYS)
    with DB_LOCK, db() as c:
        c.execute("""INSERT INTO growth_premium(user_id,expires_at,payment_charge_id,stars,purchased_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET expires_at=excluded.expires_at,payment_charge_id=excluded.payment_charge_id,stars=excluded.stars,purchased_at=excluded.purchased_at""",(uid,exp.isoformat().replace("+00:00","Z"),payment.telegram_payment_charge_id,payment.total_amount,now.isoformat().replace("+00:00","Z"))); c.commit()
    await update.message.reply_text("🎉 PREMIUM FAOLLASHDI!\n\n🌱 Esseni o‘stirish bo‘limi 30 kunga ochildi.\n"+f"⏳ Amal qilish muddati: {exp.strftime('%d.%m.%Y %H:%M')} UTC\n\nEndi xatolar, mini test, shaxsiy reja va esseni yaxshilash vositalaridan foydalanishingiz mumkin.",reply_markup=GROWTH_KEYBOARD)

async def terms_cmd(update,context):
    await update.message.reply_text("📄 PREMIUM SHARTLARI\n\n"+f"30 kunlik Esseni o‘stirish Premium: {GROWTH_PRICE_STARS} Telegram Stars.\nPremium raqamli xizmatlar uchun mo‘ljallangan.\nXarid bo‘yicha yordam: /paysupport")

async def paysupport_cmd(update,context):
    await update.message.reply_text("🆘 TO‘LOV YORDAMI\n\n"+f"Premium: {GROWTH_PRICE_STARS} ⭐ / 30 kun.\nTo‘lov amalga oshgan bo‘lsa-yu Premium ochilmagan bo‘lsa, admin bilan bog‘laning.\n👨‍💼 @{ADMIN_USERNAME}")

# ============================================================
# KEYBOARDS
# ============================================================
APP_BUTTON_TEXT = "🎓 Milliy sertifikat"
LEGACY_MOVED = {"📊 Statistika","🌱 Esseni o‘stirish","🧠 Xatolarim","📚 Xatolar ustida ishlash","📚 Xato darsi","🧪 Mini test","🎯 Shaxsiy rejam",
                "🔄 Esseni yaxshilash","✍️ Esse yozish mashqi","🗂️ Esse rejasini tuzish","💡 Dalil topib berish","📊 Chuqur statistika","⬅️ Asosiy menyu","🎓 Milliy sertifikat"}
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["✍️ Esse tekshirish", APP_BUTTON_TEXT],
], resize_keyboard=True)

GROWTH_KEYBOARD = ReplyKeyboardMarkup([
    ["🧠 Xatolarim", "📚 Xatolar ustida ishlash"],
    ["🧪 Mini test", "🎯 Shaxsiy rejam"],
    ["🔄 Esseni yaxshilash", "✍️ Esse yozish mashqi"],
    ["🗂️ Esse rejasini tuzish", "💡 Dalil topib berish"],
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
    ["🎓 Milliy sertifikat", "🧪 Test holati"],
    ["💾 Zaxira nusxa"],
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

async def send_user_errors(message,user_id):
    weak, errors = await asyncio.to_thread(get_user_error_profile,user_id)
    if not weak and not errors:
        await message.reply_text("🧠 Hozircha yetarli saqlangan tahlil yo‘q. Yangi esse tekshirtiring — xatolaringiz shu yerda yig‘iladi.", reply_markup=MAIN_KEYBOARD)
        return
    lines=["🧠 XATOLARIM", "", "So‘nggi saqlangan tahlillar asosida:"]
    if weak:
        lines += ["", "🎯 Ko‘proq ishlash kerak bo‘lgan mezonlar:"]
        for avg,cnt,n in weak[:5]:
            lines.append(f"• {CRITERION_NAMES.get(cnt, f'Mezon {cnt}')} — o‘rtacha {avg:g}/2 ({n} ta tahlil)")
    if errors:
        lines += ["", "✍️ Aniqlangan xatolardan namunalar:"]
        seen=set()
        shown=0
        for criterion,wrong,correct in errors:
            key=(wrong.lower(),correct.lower())
            if key in seen: continue
            seen.add(key); shown+=1
            line=f"• {wrong}"
            if correct: line += f" → {correct}"
            lines.append(line[:500])
            if shown>=8: break
    lines += ["", "💡 Maslahat: har bir keyingi esseda eng past ball olgan 2–3 mezonga alohida e’tibor bering."]
    await message.reply_text("\n".join(lines)[:3900], reply_markup=MAIN_KEYBOARD)


# ============================================================
# PERSONAL LEARNING HELPERS
# ============================================================
def latest_result(user_id):
    """Return the user's latest saved full essay-analysis JSON.
    Older checks without result_json are skipped safely.
    """
    with DB_LOCK, db() as c:
        row = c.execute(
            "SELECT result_json FROM checks WHERE user_id=? AND result_json IS NOT NULL ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
    if not row or not row[0]:
        return None
    try:
        data = json.loads(row[0])
        return data if isinstance(data, dict) else None
    except Exception:
        logger.exception("latest_result JSON parse error for user=%s", user_id)
        return None

def build_learning_plan(data, limit=5):
    """Build a deterministic list of weakest criteria from one saved result.
    Returns tuples: (average/latest score, criterion_id).
    """
    scores = {}
    for item in (data or {}).get("scores", []) or []:
        try:
            cid = int(item.get("criterion", 0))
            score = float(item.get("score", 0))
        except Exception:
            continue
        if 1 <= cid <= 12:
            scores[cid] = max(0.0, min(2.0, score))
    weak = [(score, cid) for cid, score in scores.items() if score < 2.0]
    weak.sort(key=lambda x: (x[0], x[1]))
    if not weak and scores:
        weak = sorted(((score, cid) for cid, score in scores.items()), key=lambda x: (x[0], x[1]))[:limit]
    return weak[:limit]

# ============================================================
# O'QUVCHI UCHUN QO'SHIMCHA TA'LIM FUNKSIYALARI
# Mavjud baholash algoritmiga tegmaydi.
# ============================================================
LESSONS = {
    1: ("Publitsistik uslub", "Fikrni xolis, aniq va ommabop bayon qiling. Ortiqcha badiiy bezaklardan qoching."),
    2: ("Ikkala qarash + shaxsiy qarash", "Avval ikki tomonning fikrini yoritib, keyin o‘z pozitsiyangizni aniq belgilang."),
    3: ("Dalillash", "Har bir asosiy qarash uchun aniq sabab, hayotiy misol yoki ishonchli dalil keltiring."),
    4: ("Esse tuzilishi", "Kirish → asosiy qism → xulosa tartibini saqlang. Har bir asosiy fikrni alohida xatboshida yozing."),
    5: ("Mantiqiy qurilish", "Har bir xatboshi bitta asosiy fikrni rivojlantirsin. Fikrlar orasida mantiqiy o‘tish bo‘lsin."),
    6: ("Izchillik", "Bir fikrni takrorlamang. Har bir keyingi gap oldingi fikrni rivojlantirsin yoki yangi dalil bersin."),
    7: ("Imlo", "So‘zlarning lug‘aviy va imloviy me’yorini tekshiring. Shubhali so‘zlarni qayta ko‘rib chiqing."),
    8: ("Punktuatsiya", "Gap bo‘laklari, qo‘shma gaplar va kirish birliklarida tinish belgilarini tekshiring."),
    9: ("Qo‘shimcha qo‘llash", "So‘zlarga qo‘shimchalarni grammatik me’yor asosida qo‘shing; shakl va ma’no mosligini tekshiring."),
    10: ("So‘z qo‘llash", "So‘zni aynan kerakli ma’noda ishlating. Ma’nodoshlarni o‘rinsiz almashtirishdan saqlaning."),
    11: ("Leksik xilma-xillik", "Bir so‘zni ketma-ket takrorlamasdan, kontekstga mos turli ifodalarni qo‘llang."),
    12: ("Sheva va parazit so‘zlar", "Adabiy tilga mos bo‘lmagan sheva, vulgarizm, varvarizm va parazit so‘zlarni olib tashlang."),
}

MINI_TESTS = {
    1: [
        ('Argumentli esseda qaysi bayon usuli maqsadga muvofiq?', ['Aniq, xolis va ommabop bayon', 'Faqat badiiy tasvir', 'Faqat og‘zaki suhbat uslubi'], 0, 'Publitsistik bayonda fikr aniq va ommabop ifodalanadi.'),
        ('Publitsistik uslubda muallif fikri qanday bo‘lishi kerak?', ['Aniq va asoslangan', 'Faqat hissiyotga boy', 'Mavzudan uzilgan'], 0, 'Publitsistik uslubda fikr dalil va mantiq bilan ifodalanadi.'),
        ('Qaysi jumla esse uslubiga ko‘proq mos?', ['Onlayn ta’lim vaqtni tejashi mumkin.', 'Voy, bu juda zo‘r-ku!', 'Men shunaqa deb o‘ylayman-da.'], 0, 'Esse uchun me’yoriy va xolis bayon afzal.'),
        ('Publitsistik uslubning muhim belgisi qaysi?', ['Ijtimoiy masalani tushunarli yoritish', 'Faqat obrazli tasvir', 'Shevaga tayangan bayon'], 0, 'Publitsistik uslub ijtimoiy masalalarni ommaga tushunarli tarzda yoritadi.'),
        ('Esseda hissiylik qanday qo‘llanishi kerak?', ['Me’yorida, asosiy fikrni bosib ketmasdan', 'Har bir gapda undov bilan', 'Faqat hayqiriqlar orqali'], 0, 'Hissiylik mantiqiy va xolis bayonni buzmasligi kerak.'),
        ('Qaysi variant publitsistik bayonga mos emas?', ['Bu masala jamiyat uchun muhim.', 'Bu masala, voy, rosa ajoyib-da!', 'Masalaning bir necha jihati mavjud.'], 1, 'Juda og‘zaki va parazit birliklar publitsistik bayonga mos kelmaydi.'),
        ('Publitsistik esseda termin ishlatilsa, u qanday bo‘lishi kerak?', ['Mavzuga mos va to‘g‘ri qo‘llangan', 'Imkon qadar ko‘p', 'Ma’nosi tushunarsiz'], 0, 'Termin faqat mazmunga xizmat qilsa va to‘g‘ri ishlatilsa foydali.'),
        ('Qaysi usul fikrni ishonchliroq ko‘rsatadi?', ['Dalil bilan xolis izohlash', 'Faqat balandparvoz so‘zlar', 'Faqat undov gaplar'], 0, 'Ishonchlilik dalil va xolis izoh orqali kuchayadi.'),
        ('Esse uchun qaysi til me’yoriga amal qilish kerak?', ['Adabiy til me’yoriga', 'Faqat mahalliy shevaga', 'Faqat so‘zlashuv tiliga'], 0, 'Argumentli esse adabiy til va me’yoriy bayonga tayanadi.'),
        ('Publitsistik uslubda savol-javoblar qanday qo‘llanishi mumkin?', ['Fikrni ochishga xizmat qilsa', 'Har gapda majburiy', 'Mavzuni almashtirish uchun'], 0, 'Savol-javob usuli faqat mazmunni ochishga xizmat qilganda foydali.'),
    ],
    2: [
        ('Argumentli esseda ikki qarash bilan birga nima bo‘lishi kerak?', ['Muallifning shaxsiy pozitsiyasi', 'Faqat sarlavha', 'Faqat maqol'], 0, 'Muallif yakunda o‘z pozitsiyasini aniq bildirishi kerak.'),
        ('Ikki qarashni yoritishda nima muhim?', ['Har ikki tomon fikrini adolatli ko‘rsatish', 'Faqat bir tomon haqida yozish', 'Ikkinchi tomonni inkor qilish'], 0, 'Ikki qarash alohida va tushunarli yoritilishi kerak.'),
        ('Shaxsiy qarashni qayerda aniq belgilash ma’qul?', ['Xulosada', 'Faqat sarlavhada', 'Faqat birinchi so‘zda'], 0, 'Xulosa muallif pozitsiyasini aniq ko‘rsatish uchun qulay qism.'),
        ('Qaysi holatda 2-mezon talabi to‘liqroq bajariladi?', ['Ikki qarash va aniq shaxsiy xulosa berilganda', 'Faqat bir qarash berilganda', 'Faqat savol berilganda'], 0, 'Mezon ikki qarash va shaxsiy pozitsiyani talab qiladi.'),
        ('Ikkinchi qarashni butunlay tashlab ketish nimaga olib keladi?', ['2-mezon talabining to‘liq bajarilmasligiga', 'Avtomatik 24 ballga', 'Faqat so‘z sonining oshishiga'], 0, 'Ikki qarashdan biri yo‘q bo‘lsa, mezon to‘liq bajarilmaydi.'),
        ('Shaxsiy fikr qanday ifodalangani ma’qul?', ['Aniq va mavzuga asoslangan holda', 'Noaniq va mavzudan tashqari', 'Faqat savol shaklida'], 0, 'Pozitsiya aniq va mavzuga bog‘langan bo‘lishi kerak.'),
        ('Qaysi xulosa shaxsiy pozitsiyani bildiradi?', ['Shu sababli men onlayn ta’limni qulayroq deb hisoblayman.', 'Demak, ikki qarash mavjud.', 'Yuqorida fikrlar keltirildi.'], 0, 'Birinchi jumla muallifning aniq tanlovini bildiradi.'),
        ('Ikki qarashni sanab o‘tishning o‘zi yetarlimi?', ['Yo‘q, ular mazmunan yoritilishi kerak', 'Ha, faqat nomlari yetadi', 'Faqat sarlavha yetadi'], 0, 'Ikki qarash mazmunan ochilishi va keyin shaxsiy pozitsiya berilishi kerak.'),
        ('Shaxsiy qarash ikki tomonning qaysi qismidan keyin tabiiyroq keladi?', ['Ularning tahlilidan keyin', 'Mavzudan oldin', 'Har bir so‘zdan keyin'], 0, 'Avval tomonlar tahlil qilinib, so‘ng xulosa chiqariladi.'),
        ('Qaysi xulosa talabga mos emas?', ['Men ikkinchi qarashni ma’qul deb bilaman.', 'Har ikki qarash ham mavjud.', 'Qaysi biri to‘g‘ri ekanini aytmayman.'], 2, 'Xulosa ikki qarashdan birini qo‘llab-quvvatlashi kerak.'),
    ],
    3: [
        ('Kuchli dalilning asosiy belgisi nima?', ['Aniq sabab yoki misol bilan asoslanganlik', 'Juda uzunlik', 'Ko‘p undov belgisi'], 0, 'Dalil fikrni aniq sabab, misol yoki ishonchli fakt bilan asoslaydi.'),
        ('Har ikki qarashni dalillashda nima talab qilinadi?', ['Har bir tomon uchun asosli dalillar', 'Faqat bir tomon uchun dalil', 'Faqat maqol'], 0, 'Mezon har ikki qarashning dalillar bilan asoslanishini ko‘zda tutadi.'),
        ('Qaysi dalil kuchliroq?', ['Aniq hayotiy vaziyatga asoslangan misol', 'Shunchaki ‘hamma biladi’ deyish', '‘Menimcha shunday’ deyish'], 0, 'Aniq va mavzuga mos misol fikrni kuchliroq asoslaydi.'),
        ('Dalil mavzuga aloqasiz bo‘lsa, nima yuz beradi?', ['Fikrni yetarlicha asoslamaydi', 'Dalil avtomatik kuchli bo‘ladi', 'Ball albatta 2 bo‘ladi'], 0, 'Aloqasiz dalil asosiy fikrni isbotlamaydi.'),
        ('‘Ko‘pchilik shunday deydi’ jumlasi qachon yetarli dalil bo‘lmaydi?', ['Aniq asos yoki misol berilmaganda', 'Mavzuda ishlatilganda', 'Xulosada kelganda'], 0, 'Umumiy da’vo o‘zi mustahkam dalil bo‘la olmaydi.'),
        ('Dalil va fikr o‘rtasida qanday aloqa bo‘lishi kerak?', ['Dalil fikrni bevosita asoslasin', 'Dalil boshqa mavzuga o‘tsin', 'Aloqa bo‘lmasin'], 0, 'Dalil aynan ilgari surilgan fikrni asoslashga xizmat qiladi.'),
        ('Qaysi biri aniqroq dalil?', ['Masalan, masofaviy ta’limda yo‘lga ketadigan vaqt qisqaradi.', 'Bu juda yaxshi.', 'Hamma buni biladi.'], 0, 'Birinchi variant tekshiriladigan va mavzuga bog‘liq sabab beradi.'),
        ('Dalil keltirishdan oldin nima aniq bo‘lishi kerak?', ['Qaysi fikrni asoslayotganingiz', 'Qancha so‘z yozishingiz', 'Necha marta undov qo‘yishingiz'], 0, 'Dalilning vazifasi qaysi fikrni asoslashini bilishdan boshlanadi.'),
        ('Bir tomonning dalili juda kuchli, ikkinchisiniki yo‘q. Natija qanday?', ['Har ikki qarash to‘liq dalillangan hisoblanmaydi', 'Avtomatik 2 ball', 'Dalil kerak emas'], 0, '3-mezon har ikki qarashning asoslanishini tekshiradi.'),
        ('Dalil sifatida raqam keltirilsa, u qanday bo‘lishi ma’qul?', ['Mavzuga aloqador va ishonchli kontekstda', 'Tasodifiy raqam', 'Manosi tushunarsiz raqam'], 0, 'Raqam faqat mavzuga aloqador va ishonchli bo‘lsa foydali.'),
    ],
    4: [
        ('Essening asosiy tuzilishi qaysi?', ['Kirish → asosiy qism → xulosa', 'Xulosa → kirish → sarlavha', 'Faqat asosiy qism'], 0, 'Argumentli esse uch asosiy qismdan tashkil topadi.'),
        ('Kirishning vazifasi nima?', ['Mavzuni tanishtirish va muammoni qo‘yish', 'Faqat xulosani aytish', 'Faqat dalillar ro‘yxatini berish'], 0, 'Kirish o‘quvchini mavzu va muammo bilan tanishtiradi.'),
        ('Asosiy qismda nima qilinadi?', ['Qarashlar va dalillar tahlil qilinadi', 'Faqat ism-sharif yoziladi', 'Faqat sarlavha takrorlanadi'], 0, 'Asosiy qismda qarashlar asoslanib tahlil qilinadi.'),
        ('Xulosaning vazifasi nima?', ['Tahlilni yakunlab, shaxsiy pozitsiyani bildirish', 'Yangi mavzu ochish', 'Faqat savol berish'], 0, 'Xulosa asosiy fikrlarni yakunlaydi va pozitsiyani belgilaydi.'),
        ('Qaysi tuzilish mantiqan to‘g‘ri?', ['Muammo → qarashlar → dalillar → xulosa', 'Xulosa → dalilsiz fikr → kirish', 'Dalil → sarlavha → mavzu'], 0, 'Fikrlar muammodan tahlilga va xulosaga qarab rivojlanadi.'),
        ('Kirish mavzuni so‘zma-so‘z ko‘chirish bilan cheklanib qolsa, nima muammo?', ['Mustaqil kirish yetarli ochilmaydi', 'Esse avtomatik mukammal bo‘ladi', 'Dalil kuchayadi'], 0, 'Kirish mavzuni shunchaki ko‘chirmasdan muammoni ochishi kerak.'),
        ('Xulosa qaysi holatda to‘liqroq?', ['Asosiy tahlilni jamlab, bir qarashni qo‘llab-quvvatlaganda', 'Yangi mavzu boshlaganda', 'Faqat ‘tamom’ deb tugaganda'], 0, 'Xulosa avvalgi tahlilga tayangan holda yakunlanadi.'),
        ('Asosiy qismning ikki qarashi qanday berilgani ma’qul?', ['Alohida xatboshilarda', 'Bitta so‘z bilan', 'Faqat xulosada'], 0, 'Har bir asosiy qarash alohida va tushunarli xatboshida berilishi ma’qul.'),
        ('Kirishda shaxsiy pozitsiyani juda erta keskin aytish nimaga olib kelishi mumkin?', ['Tahlil uchun joy qisqarishi mumkin', 'Dalillar ko‘payadi', 'Xulosa kuchayadi'], 0, 'Shaxsiy pozitsiya xulosada aniq yakunlanishi tahlilni izchil saqlaydi.'),
        ('Esseda xulosa bo‘lmasa, qaysi qism tugallanmay qoladi?', ['Tuzilmaning yakuniy qismi', 'Sarlavha', 'Faqat kirish'], 0, 'Xulosa essening yakunlovchi qismidir.'),
    ],
    5: [
        ('Yaxshi xatboshi odatda nimani rivojlantiradi?', ['Bitta asosiy fikrni', 'Bir nechta aloqasiz mavzuni', 'Faqat bitta so‘zni'], 0, 'Xatboshi ichidagi gaplar bitta asosiy fikrga xizmat qilishi kerak.'),
        ('Xatboshilar orasidagi mantiqiy o‘tish nimaga xizmat qiladi?', ['Fikrlar bog‘lanishiga', 'So‘z sonini kamaytirishga', 'Imlo xatosini ko‘paytirishga'], 0, 'Mantiqiy o‘tish o‘quvchiga fikr rivojini kuzatishga yordam beradi.'),
        ('Bir xatboshida mutlaqo aloqasiz fikrlar aralashsa, nima buziladi?', ['Mantiqiy qurilish', 'So‘zlarning alifbo tartibi', 'Sarlavha'], 0, 'Aloqasiz fikrlar xatboshi mantiqini zaiflashtiradi.'),
        ('Qaysi bog‘lovchi qarama-qarshi fikrni ko‘rsatadi?', ['Biroq', 'Masalan', 'Shuningdek'], 0, '‘Biroq’ qarama-qarshilik munosabatini bildiradi.'),
        ('Qaysi birlik sabab-natijani ko‘rsatadi?', ['Shu sababli', 'Aksincha', 'Masalan'], 0, '‘Shu sababli’ natija yoki sabab-natija aloqasini bildiradi.'),
        ('Xatboshi boshlanishida yangi fikrga o‘tish qanday bo‘lishi kerak?', ['Oldingi fikr bilan mantiqan bog‘langan', 'Tasodifiy', 'Mavzudan butunlay uzilgan'], 0, 'Yangi fikr oldingi tahlil bilan bog‘lanishi kerak.'),
        ('Qaysi holat mantiqiy qurilishni zaiflashtiradi?', ['Dalilsiz xulosaga sakrash', 'Fikrni dalil bilan rivojlantirish', 'Xatboshilarni mavzuga mos ajratish'], 0, 'Dalilsiz sakrash fikrlar orasidagi mantiqni uzadi.'),
        ('Xatboshi juda uzun bo‘lsa, nima qilish mumkin?', ['Mustaqil fikrlarga ko‘ra ajratish', 'Barcha fikrni olib tashlash', 'Har gapga nuqta qo‘ymaslik'], 0, 'Turli asosiy fikrlar alohida xatboshilarda berilishi mumkin.'),
        ('‘Birinchidan’, ‘ikkinchidan’ birliklari nima uchun ishlatiladi?', ['Fikrlar ketma-ketligini ko‘rsatish uchun', 'Faqat so‘z sonini oshirish uchun', 'Xulosa o‘rniga'], 0, 'Ular fikrlarning tartibini aniq ko‘rsatishi mumkin.'),
        ('Mantiqiy xulosa qanday kelib chiqishi kerak?', ['Avvalgi tahlil va dalillardan', 'Tasodifiy yangi fikrdan', 'Mavzuga aloqasiz misoldan'], 0, 'Xulosa oldingi tahlilga tayangan bo‘lishi kerak.'),
    ],
    6: [
        ('Izchil matnda yangi gap qanday bo‘lishi kerak?', ['Oldingi fikrni rivojlantirsin yoki yangi dalil bersin', 'Oldingi fikrni aynan takrorlasin', 'Mavzuni almashtirsin'], 0, 'Izchillik fikrlarning o‘zaro bog‘liqligini talab qiladi.'),
        ('Bir fikrni keragidan ortiq takrorlash nimani buzadi?', ['Izchillik va mazmuniy samaradorlikni', 'Alifbo tartibini', 'Sarlavhani'], 0, 'Ortiqcha takror mazmun rivojini sekinlashtiradi.'),
        ('Qaysi variant fikrlar izchilligini ko‘rsatadi?', ['Fikr → sabab → misol → xulosa', 'Fikr → boshqa mavzu → tasodifiy gap', 'Misol → yangi mavzu → fikr'], 0, 'Mantiqiy ketma-ketlik mazmunni tushunarli qiladi.'),
        ('Bir paragrafdan ikkinchisiga o‘tishda nima kerak?', ['Mazmuniy bog‘lanish', 'Tasodifiy sakrash', 'Faqat uzun gap'], 0, 'Paragraflar umumiy mavzu doirasida bog‘langan bo‘lishi kerak.'),
        ('Qaysi gap takroriy fikrga misol?', ['Ta’lim qulay. Ta’lim qulay bo‘lishi mumkin.', 'Ta’lim qulay, chunki vaqt tejaladi.', 'Bundan tashqari, transport xarajati kamayadi.'], 0, 'Birinchi variant bir xil fikrni deyarli takrorlaydi.'),
        ('‘Bundan tashqari’ birligi qanday vazifa bajaradi?', ['Qo‘shimcha fikrni bog‘laydi', 'Qarama-qarshilikni bildiradi', 'Xulosani inkor qiladi'], 0, 'U oldingi fikrga qo‘shimcha dalil yoki fikrni bog‘laydi.'),
        ('Qaysi holat izchillikni kuchaytiradi?', ['Bog‘lovchi va mantiqiy ketma-ketlikdan foydalanish', 'Har gapda mavzuni o‘zgartirish', 'Fikrlarni aralashtirish'], 0, 'Mantiqiy bog‘lovchilar va ketma-ketlik izchillikni oshiradi.'),
        ('Xulosada asosiy fikr butunlay boshqa mavzuga o‘tsa, nima buziladi?', ['Mazmuniy izchillik', 'Faqat imlo', 'Faqat so‘z soni'], 0, 'Xulosa butun esse mavzusiga bog‘langan bo‘lishi kerak.'),
        ('Dalil fikrga mos kelmasa, qaysi sifat zaiflashadi?', ['Izchillik va mantiq', 'Alifbo tartibi', 'Sarlavha hajmi'], 0, 'Mos kelmagan dalil fikr rivojini buzadi.'),
        ('Takrorni kamaytirishning foydali usuli qaysi?', ['Bir fikrni yangi mazmun bilan rivojlantirish yoki ortiqchasini qisqartirish', 'Har safar aynan bir gapni yozish', 'Faqat so‘zlarni ko‘paytirish'], 0, 'Takror o‘rniga yangi mazmun yoki dalil berish kerak.'),
    ],
    7: [
        ('Imlo xatosi nima?', ['So‘zning me’yoriy yozilishi buzilishi', 'Tinish belgisining noto‘g‘ri qo‘yilishi', 'Fikrning takrorlanishi'], 0, 'Imlo so‘zlarning to‘g‘ri yozilish me’yorini qamrab oladi.'),
        ('Qaysi yozuv me’yoriy?', ['ma’lumot', 'malumot', "ma'lumott"], 0, '‘Ma’lumot’ so‘zi adabiy imloda shu shaklda yoziladi.'),
        ('Qaysi juftlikda xato yozilgan so‘z bor?', ["ta’lim — ta'lim", 'e’tibor — etibor', 'muammo — muammo'], 1, '‘E’tibor’ so‘zida tutuq belgisi kerak.'),
        ('Imlo tekshirishda nima asos bo‘ladi?', ['Amaldagi adabiy imlo me’yori', 'So‘zning quloqqa g‘alati eshitilishi', 'Faqat muallif xohishi'], 0, 'Imlo xatosi norma bilan asoslanishi kerak.'),
        ('Qaysi so‘z to‘g‘ri yozilgan?', ['mas’ul', 'masul', 'ma’sul'], 0, 'Me’yoriy shakl ‘mas’ul’.'),
        ('Qaysi so‘zda qo‘shib yozish to‘g‘ri?', ['bugun', 'bu kun (har doim bitta ma’noda)', 'har doim bug un'], 0, '‘Bugun’ leksik birlik sifatida qo‘shib yoziladi.'),
        ('Imlo xatosini faqat nimaga qarab belgilash noto‘g‘ri?', ['So‘z g‘alati ko‘ringaniga', 'Me’yoriy qoida va lug‘atga', 'Adabiy norma asosiga'], 0, 'Faqat shaxsiy sezgi xatoni isbotlamaydi.'),
        ('Qaysi variantda apostrof to‘g‘ri qo‘llangan?', ['san’at', 'sanat’', 'sana’t'], 0, '‘San’at’ so‘zida tutuq belgisi to‘g‘ri joylashgan.'),
        ('‘Mas’uliyat’ so‘zining to‘g‘ri yozilishi qaysi?', ['mas’uliyat', 'masuliyat', 'ma’suliyat'], 0, 'Me’yoriy yozilish ‘mas’uliyat’.'),
        ('Imlo xatosi aniqlansa, tahlilda nima ko‘rsatilishi kerak?', ['XATO → TO‘G‘RISI → IZOH', 'Faqat xatoning o‘zi', 'Faqat ball'], 0, 'Xato aniq ko‘rsatilsa, o‘quvchi uni tuzata oladi.'),
    ],
    8: [
        ('Punktuatsiya nimani tartibga soladi?', ['Tinish belgilarining qo‘llanishini', 'So‘zlarning yozilishini', 'Xatboshi uzunligini'], 0, 'Punktuatsiya tinish belgilarini qo‘llash me’yorlarini belgilaydi.'),
        ('Qaysi belgi gap oxirida darak mazmunida odatda qo‘yiladi?', ['Nuqta', 'Vergul', 'Ikki nuqta'], 0, 'Darak gap odatda nuqta bilan yakunlanadi.'),
        ('‘Biroq’ bilan boshlangan qarama-qarshi qismda tinish belgisi nimaga bog‘liq?', ['Gapning sintaktik tuzilishiga', 'Faqat so‘z soniga', 'Faqat gap uzunligiga'], 0, 'Tinish belgisi sintaktik munosabatga ko‘ra belgilanadi.'),
        ('Uyushiq bo‘laklar orasida qachon vergul qo‘yilishi mumkin?', ['Tegishli sintaktik sharoitda', 'Har doim birinchi so‘zdan keyin', 'Hech qachon'], 0, 'Vergul uyushiq bo‘laklarning bog‘lanishiga ko‘ra qo‘yiladi.'),
        ('Qaysi tinish belgisi savol gap oxirida ishlatiladi?', ['So‘roq belgisi', 'Nuqtali vergul', 'Ikki nuqta'], 0, 'Savol mazmunidagi gap so‘roq belgisi bilan tugaydi.'),
        ('Tire qo‘llashda asosiy mezon nima?', ['Gapning sintaktik va mazmuniy tuzilishi', 'Gapdagi so‘zlar soni', 'Muallifning xohishi'], 0, 'Tire ham sintaktik va mazmuniy munosabatga bog‘liq.'),
        ('Qaysi holatda vergulni shunchaki pauzaga qarab qo‘yish noto‘g‘ri?', ['Sintaktik asos bo‘lmaganda', 'Gap qisqa bo‘lganda', 'Gapda ikki so‘z bo‘lganda'], 0, 'Punktuatsiya faqat og‘zaki pauzaga emas, grammatik tuzilishga asoslanadi.'),
        ('Kirish so‘zi gapda ajratilganda qanday belgi ishlatilishi mumkin?', ['Vergul', 'Faqat nuqta', 'Faqat so‘roq belgisi'], 0, 'Kirish birliklari ko‘pincha vergul bilan ajratiladi.'),
        ('Qaysi gap punktuatsiya nuqtayi nazaridan yakunlangan?', ['Bugun imtihon boshlandi.', 'Bugun imtihon boshlandi,', 'Bugun imtihon boshlandi:'], 0, 'Darak gap mazmuniga ko‘ra nuqta bilan tugallangan.'),
        ('Punktuatsiya xatosini tahlil qilishda nima ko‘rsatiladi?', ['XATO → TO‘G‘RISI → IZOH', 'Faqat vergul soni', 'Faqat umumiy ball'], 0, 'Aniq xato va uning sababi o‘quvchiga tushunarli bo‘ladi.'),
    ],
    9: [
        ('Qo‘shimcha qo‘llashda eng muhim jihat nima?', ['Grammatik moslik', 'So‘zning uzunligi', 'Gapning rang-barangligi'], 0, 'Qo‘shimcha so‘zning grammatik shakliga mos kelishi kerak.'),
        ('Kelishik qo‘shimchasi nimani ifodalashga xizmat qiladi?', ['So‘zlar orasidagi grammatik munosabatni', 'Faqat so‘z uzunligini', 'Faqat urg‘uni'], 0, 'Kelishiklar so‘zning gapdagi munosabatini ko‘rsatadi.'),
        ('‘Kitob o‘quvchi uchun foydali’ gapida qo‘shimcha qo‘llash nimaga bog‘liq?', ['So‘zlarning grammatik munosabatiga', 'Faqat talaffuzga', 'Faqat sarlavhaga'], 0, 'Qo‘shimcha va shakllar gapdagi munosabatga mos bo‘lishi kerak.'),
        ('Qaysi variant grammatik jihatdan to‘g‘ri?', ['O‘quvchilarning fikrlari', 'O‘quvchilarni fikrlari', 'O‘quvchilar fikrlarining'], 0, '‘O‘quvchilarning fikrlari’ egalik munosabatini to‘g‘ri ifodalaydi.'),
        ('Fe’l qo‘shimchasi nimaga moslashadi?', ['Shaxs-son va zamon kabi grammatik belgilarga', 'Faqat so‘z uzunligiga', 'Faqat xatboshi hajmiga'], 0, 'Fe’l shakli grammatik ma’noga mos bo‘lishi kerak.'),
        ('Ko‘plik qo‘shimchasi qachon noo‘rin bo‘lishi mumkin?', ['Yakka ma’noli birlikni noto‘g‘ri ko‘plikka aylantirganda', 'Har doim', 'Faqat xulosada'], 0, 'Ko‘plik qo‘shimchasi mazmun va grammatik talabga mos ishlatiladi.'),
        ('Qo‘shimcha xatosini tekshirishda nima muhim?', ['So‘z shakli va gapdagi vazifani birga ko‘rish', 'Faqat so‘zni alohida ko‘rish', 'Faqat talaffuz'], 0, 'Qo‘shimcha kontekst bilan tekshiriladi.'),
        ('Qaysi birikmada kelishik mosligi to‘g‘ri?', ['Maktabga borish', 'Maktabni borish', 'Maktabdan borish'], 0, '‘Bormoq’ yo‘nalish ma’nosida ‘-ga’ bilan mos keladi.'),
        ('‘Men do‘stim bilan suhbatlashdim’ gapida ‘bilan’ nimani bildiradi?', ['Birgalik munosabatini', 'Ko‘plikni', 'Zamonni'], 0, '‘Bilan’ birgalik vositasini bildiradi.'),
        ('Qo‘shimcha xatosini ko‘rsatishda nima kerak?', ['Xato shakl, to‘g‘ri shakl va izoh', 'Faqat noto‘g‘ri so‘z', 'Faqat ball'], 0, 'Aniq tahlil o‘quvchiga xatoni tushunishga yordam beradi.'),
    ],
    10: [
        ('So‘z qo‘llash xatosi qachon yuz beradi?', ['So‘z ma’no yoki kontekstga mos kelmaganda', 'So‘z qisqa bo‘lganda', 'So‘z gap boshida kelganda'], 0, 'So‘z tanlovi mazmun va adabiy qo‘llanishga mos bo‘lishi kerak.'),
        ('Qaysi so‘z tanlovi ma’noga mosroq?', ['Muammoni hal qilmoq', 'Muammoni pishirmoq', 'Muammoni ichmoq'], 0, '‘Muammoni hal qilmoq’ me’yoriy birikmadir.'),
        ('Sinonimlardan foydalanishda nima muhim?', ['Kontekst va ma’no mosligi', 'Faqat so‘zning uzunligi', 'Faqat kam uchrashi'], 0, 'Sinonim kontekst ma’nosiga mos kelishi kerak.'),
        ('‘Vaqtni tejamoq’ birikmasida ‘tejamoq’ qanday ma’noda?', ['Vaqtni behuda sarflamaslik', 'Vaqtni sotish', 'Vaqtni yozish'], 0, '‘Tejamoq’ resursni behuda sarflamaslik ma’nosida ishlatiladi.'),
        ('Qaysi holat so‘z qo‘llash xatosiga misol bo‘lishi mumkin?', ['Kontekstga mos bo‘lmagan sinonimni tanlash', 'So‘zni to‘g‘ri ma’noda ishlatish', 'Aniq termin ishlatish'], 0, 'Noto‘g‘ri sinonim ma’noni buzishi mumkin.'),
        ('So‘zni faqat ‘g‘alati’ ko‘ringani uchun xato deyish mumkinmi?', ['Yo‘q, norma va kontekst bilan asoslash kerak', 'Ha, har doim', 'Faqat xulosada'], 0, 'Xato aniq me’yor yoki kontekst asosida ko‘rsatilishi kerak.'),
        ('Qaysi birikma ma’no jihatdan tabiiy?', ['Qaror qabul qilmoq', 'Qarorni ichmoq', 'Qarorni uxlatmoq'], 0, '‘Qaror qabul qilmoq’ me’yoriy so‘z birikmasidir.'),
        ('So‘z qo‘llashda terminning asosiy talabi nima?', ['Tegishli ma’noda va mavzuga mos ishlatilishi', 'Imkon qadar ko‘p ishlatilishi', 'Har gapda takrorlanishi'], 0, 'Termin mavzuga mos va o‘z ma’nosida qo‘llanishi kerak.'),
        ('‘Masalani ko‘rib chiqmoq’ birikmasi qanday?', ['Me’yoriy va tabiiy birikma', 'Ma’nosiz birikma', 'Faqat shevaga xos'], 0, 'Bu adabiy tilda keng qo‘llanadigan me’yoriy birikma.'),
        ('So‘z qo‘llash xatosi tahlilida nima ko‘rsatiladi?', ['Xato so‘z, to‘g‘ri variant va kontekstli izoh', 'Faqat so‘zning uzunligi', 'Faqat ball'], 0, 'Xatoning konteksti uning nima uchun noto‘g‘ri ekanini ko‘rsatadi.'),
    ],
    11: [
        ('Leksik xilma-xillik nimani anglatadi?', ['Mazmunga mos turli ifodalarni qo‘llash', 'Bir so‘zni qayta-qayta yozish', 'Har gapda chet so‘z ishlatish'], 0, 'Leksik xilma-xillik mazmunni boy va takrorsiz ifodalashga yordam beradi.'),
        ('Bir xil so‘zni ketma-ket takrorlash nimani kamaytirishi mumkin?', ['Leksik xilma-xillikni', 'Imlo me’yorini', 'Sarlavha uzunligini'], 0, 'Ortiqcha takror lug‘aviy xilma-xillikni pasaytiradi.'),
        ('Sinonimlardan qachon foydalanish foydali?', ['Ma’no va uslub mos bo‘lganda', 'Faqat uzunroq so‘z topilganda', 'Har bir gapda majburan'], 0, 'Sinonim mazmunga mos bo‘lsa matnni rang-barang qiladi.'),
        ('Qaysi juftlik sinonimga yaqin?', ['Muhim — ahamiyatli', 'Kitob — qalam', 'Maktab — dars'], 0, '‘Muhim’ va ‘ahamiyatli’ yaqin ma’noli birliklardir.'),
        ('Leksik xilma-xillik uchun nima qilish noto‘g‘ri?', ['Ma’nosi noma’lum so‘zlarni majburan ishlatish', 'Mos sinonim tanlash', 'Takrorni kamaytirish'], 0, 'Xilma-xillik ma’no aniqligidan ustun qo‘yilmaydi.'),
        ('Qaysi usul takrorni kamaytirishi mumkin?', ['Mos olmosh yoki sinonimdan foydalanish', 'Har gapni aynan takrorlash', 'Mavzuni almashtirish'], 0, 'Kontekstga mos olmosh yoki sinonim takrorni kamaytirishi mumkin.'),
        ('Bir so‘zni almashtirganda eng muhim talab nima?', ['Yangi so‘zning ma’nosi mos bo‘lishi', 'Yangi so‘z juda uzun bo‘lishi', 'Yangi so‘z chet tilidan bo‘lishi'], 0, 'Sinonim ma’no va uslub jihatdan mos kelishi kerak.'),
        ('Leksik xilma-xillik nimaga xizmat qiladi?', ['Fikrni boyroq va takrorsiz ifodalashga', 'Faqat so‘z sonini oshirishga', 'Faqat xulosani uzaytirishga'], 0, 'U mazmunni aniq va rang-barang ifodalashga xizmat qiladi.'),
        ('Qaysi variantda keraksiz takror bor?', ['Ta’lim muhim. Ta’lim jamiyat uchun muhim.', 'Ta’lim muhim, chunki bilim beradi.', 'Bundan tashqari, u imkoniyat yaratadi.'], 0, 'Birinchi variantda ‘ta’lim’ keragidan ortiq takrorlangan.'),
        ('Leksik xilma-xillikda qaysi tamoyil ustun?', ['Aniqlik va ma’no mosligi', 'Noyob so‘z ishlatish', 'Chet so‘zlarni ko‘paytirish'], 0, 'Rang-baranglik aniqlik va ma’no hisobiga bo‘lmasligi kerak.'),
    ],
    12: [
        ('Qaysi birlik akademik esseda nomaqbul?', ['Parazit so‘z', 'Aniq dalil', 'Adabiy termin'], 0, 'Parazit so‘zlar rasmiy va akademik bayonni zaiflashtiradi.'),
        ('Sheva so‘zlari qachon muammo bo‘lishi mumkin?', ['Adabiy til talab qilinadigan esseda noo‘rin ishlatilganda', 'Har doim xato emas', 'Faqat sarlavhada'], 0, 'Esse adabiy tilga tayanadi, noo‘rin sheva birliklari salbiy baholanishi mumkin.'),
        ('Vulgarizm nima?', ['Qo‘pol va haqoratli yoki nomaqbul birlik', 'Ilmiy termin', 'Rasmiy ibora'], 0, 'Vulgarizmlar adabiy va akademik bayonga mos kelmaydi.'),
        ('Varvarizmga eng yaqin ta’rif qaysi?', ['O‘zbekcha matnda noo‘rin o‘zlashma yoki begona birlik', 'Adabiy me’yoriy so‘z', 'Tinish belgisi'], 0, 'Varvarizm o‘zga tilga oid birlikning noo‘rin qo‘llanishi sifatida qaraladi.'),
        ('Parazit so‘zga misol bo‘la oladigan birlik qanday?', ['Mazmunga xizmat qilmaydigan takroriy og‘zaki birlik', 'Aniq termin', 'Dalil'], 0, 'Mazmunsiz takrorlanadigan og‘zaki birliklar bayonni susaytiradi.'),
        ('Qaysi variant adabiy bayonga mosroq?', ['Menimcha, bu usul samarali.', 'Bu usul rosa zo‘r-da.', 'Bu usul, anaqa, yaxshi.'], 0, 'Birinchi variant me’yoriy va xolisroq bayon qilingan.'),
        ('Sheva birliklarini ishlatish qachon alohida asos talab qiladi?', ['Adabiy esse talabida ularni qo‘llash zarur bo‘lmasa', 'Har doim majburiy', 'Faqat xulosada'], 0, 'Esse uchun adabiy til talab qilinadi; sheva zarur bo‘lmasa ishlatilmaydi.'),
        ('‘Xo‘sh’ so‘zining kirish qismida ishlatilishi o‘z-o‘zidan xatomi?', ['Yo‘q', 'Ha, har doim', 'Faqat uch marta ishlatilsa'], 0, '‘Xo‘sh’ning mavjudligi yoki takrori o‘z-o‘zidan 10 yoki 12-mezon xatosi emas.'),
        ('Qaysi birlik rasmiy essega ko‘proq mos?', ['Shu sababli', 'Rosa zo‘r', 'Anaqa gap'], 0, '‘Shu sababli’ adabiy va mantiqiy bog‘lovchi birlikdir.'),
        ('12-mezon xatosini belgilashda nima muhim?', ['Matndagi aniq noo‘rin birlik va uning konteksti', 'Faqat muallifning shevasi', 'So‘zning uzunligi'], 0, 'Xato aniq matn birligi va kontekst asosida ko‘rsatilishi kerak.'),
    ],
}

async def send_personal_plan(message, user_id):
    data=await asyncio.to_thread(latest_result,user_id)
    if not data:
        await message.reply_text("🎯 Shaxsiy reja tuzish uchun avval kamida bitta esse tekshirtiring.",reply_markup=MAIN_KEYBOARD); return
    total=authoritative_total24(data); weak=build_learning_plan(data)
    lines=["🎯 SHAXSIY RIVOJLANISH REJASI","",f"Hozirgi natija: {total:g}/24  •  {to_75(total)}/75",""]
    for i,(score,cid) in enumerate(weak,1):
        name,lesson=LESSONS.get(cid,(CRITERION_NAMES.get(cid,f"Mezon {cid}"),"Shu mezon bo‘yicha ko‘proq mashq qiling."))
        gap=2-score
        lines += [f"{i}. {name} — {score:g}/2",f"   📌 {lesson}",f"   🎯 Potensial: +{gap:g} ball",f"   📝 Vazifa: keyingi esseda aynan shu jihatni nazorat qiling.",""]
    lines.append("💡 Har bir keyingi tekshiruvdan so‘ng reja yangi natijaga mos yangilanadi.")
    await message.reply_text("\n".join(lines)[:3900],reply_markup=MAIN_KEYBOARD)

async def send_error_lesson(message,user_id):
    data=await asyncio.to_thread(latest_result,user_id)
    if not data:
        await message.reply_text("📚 Xato darsi uchun avval esse tekshirtiring.",reply_markup=MAIN_KEYBOARD); return
    weak=build_learning_plan(data); cid=weak[0][1] if weak else 7
    name,lesson=LESSONS.get(cid,(CRITERION_NAMES.get(cid,f"Mezon {cid}"),""))
    errors=[]
    for item in data.get("scores",[]) or []:
        if int(item.get("criterion",0) or 0)==cid:
            errors=[e for e in item.get("errors",[]) or [] if isinstance(e,dict)]
    lines=[f"📚 XATO DARSIGI — {name}","",f"Natija: {dict((int(x.get('criterion',0)),x.get('score',0)) for x in data.get('scores',[]) or []).get(cid,0)}/2","",f"📌 QOIDA:\n{lesson}"]
    if errors:
        lines += ["","🔎 SIZDA ANIQLANGAN MISOLLAR:"]
        for e in errors[:5]:
            lines.append(f"• {e.get('wrong','—')} → {e.get('correct','—')}")
            if e.get('explanation'): lines.append(f"  {e.get('explanation')}")
    lines += ["","✍️ AMALIY VAZIFA:","Shu mezonga oid 3 ta gap yozing va keyingi esseda ularni qo‘llashga harakat qiling."]
    await message.reply_text("\n".join(lines)[:3900],reply_markup=MAIN_KEYBOARD)

async def send_mini_test(message,user_id,context):
    """Start a 5-question adaptive mini test based on the latest essay."""
    data=await asyncio.to_thread(latest_result,user_id)
    if not data:
        await message.reply_text("🧪 Mini test uchun avval esse tekshirtiring.",reply_markup=MAIN_KEYBOARD)
        return

    weak=build_learning_plan(data, limit=5)
    criteria=[cid for score,cid in weak]
    # Fill remaining questions with different criteria, then repeat only if necessary.
    for cid in sorted(MINI_TESTS):
        if len(criteria) >= 5:
            break
        if cid not in criteria:
            criteria.append(cid)
    if not criteria:
        criteria=[7,8,9,10,11]

    questions=[]
    for cid in criteria[:5]:
        bank=MINI_TESTS.get(cid) or MINI_TESTS[7]
        q=random.choice(bank)
        questions.append((cid,q))

    context.user_data["mini_test"]={
        "questions": questions,
        "index": 0,
        "correct": 0,
        "answered": 0,
    }
    await _send_mini_question(message, context.user_data["mini_test"])

async def _send_mini_question(target, session):
    idx=int(session.get("index",0))
    questions=session.get("questions") or []
    if idx >= len(questions):
        return
    cid,q=questions[idx]
    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{chr(65+i)}) {opt}",callback_data=f"minians_{idx}_{i}")]
        for i,opt in enumerate(q[1])
    ])
    name=LESSONS.get(cid,(f"Mezon {cid}",""))[0]
    await target.reply_text(
        f"🧪 MINI TEST — {idx+1}/{len(questions)}\n\n"
        f"🎯 Yo‘nalish: {name}\n\n{q[0]}",
        reply_markup=kb
    )

async def mini_test_callback(update, context):
    query=update.callback_query
    await query.answer()
    try:
        _,idx_s,ans_s=query.data.split("_")
        idx=int(idx_s); ans=int(ans_s)
    except Exception:
        await query.message.reply_text("⚠️ Test javobi noto‘g‘ri yuborildi. Mini testni qayta boshlang.",reply_markup=MAIN_KEYBOARD)
        return

    session=context.user_data.get("mini_test")
    if not session:
        await query.message.reply_text("⚠️ Mini test sessiyasi topilmadi. 🧪 Mini testni qayta boshlang.",reply_markup=MAIN_KEYBOARD)
        return

    questions=session.get("questions") or []
    if idx != int(session.get("index",0)) or idx >= len(questions):
        await query.answer("Bu savol allaqachon javoblangan.",show_alert=True)
        return

    cid,q=questions[idx]
    correct=int(q[2])
    ok=ans==correct
    session["answered"]=int(session.get("answered",0))+1
    if ok:
        session["correct"]=int(session.get("correct",0))+1

    result="✅ TO‘G‘RI!" if ok else f"❌ NOTO‘G‘RI. To‘g‘ri javob: {chr(65+correct)}) {q[1][correct]}"
    await query.message.reply_text(f"{result}\n\n📚 {q[3]}")

    session["index"]=idx+1
    if session["index"] >= len(questions):
        correct_n=int(session.get("correct",0))
        total_n=len(questions)
        percent=round(correct_n/total_n*100) if total_n else 0
        if correct_n == total_n:
            level="🏆 A’lo natija!"
        elif correct_n >= 4:
            level="👏 Juda yaxshi!"
        elif correct_n >= 3:
            level="📈 Yaxshi, yana mashq qiling."
        else:
            level="📚 Zaif mezonlarni yana bir bor o‘rganing."
        await query.message.reply_text(
            f"🎓 MINI TEST YAKUNI\n\n"
            f"Natija: {correct_n}/{total_n} ta to‘g‘ri\n"
            f"Foiz: {percent}%\n\n{level}",
            reply_markup=MAIN_KEYBOARD
        )
        context.user_data.pop("mini_test",None)
        return

    await _send_mini_question(query.message, session)

async def send_improvement(message,user_id):
    data=await asyncio.to_thread(latest_result,user_id)
    if not data:
        await message.reply_text("🔄 Esseni yaxshilash uchun avval esse tekshirtiring.",reply_markup=MAIN_KEYBOARD); return
    total=authoritative_total24(data); weak=build_learning_plan(data)
    lines=["🔄 ESSENI YAXSHILASH", "", f"Joriy natija: {total:g}/24 • {to_75(total)}/75", "", "Keyingi esse uchun aniq nazorat rejasi:"]
    actions={
      1:"Badiiy bezakni kamaytirib, fikrni xolis va ommabop shaklda bayon qiling.",
      2:"Ikki qarashni ham ko‘rsating va xulosada bittasini aniq qo‘llab-quvvatlang.",
      3:"Har ikki qarashga kamida 2 tadan aniq sabab yoki dalil tayyorlang.",
      4:"Kirish, asosiy qism va xulosani alohida va to‘liq yozing.",
      5:"Har bir asosiy fikrni alohida xatboshiga ajrating.",
      6:"Takroriy gaplarni olib tashlab, har bir yangi gapga yangi mazmun bering.",
      7:"Topshirishdan oldin imlo bo‘yicha alohida qayta o‘qish qiling.",
      8:"Murakkab gaplarda tinish belgilarini sintaktik qurilma asosida tekshiring.",
      9:"Qo‘shimchalarni so‘z va gapdagi grammatik munosabat bilan tekshiring.",
      10:"Har bir shubhali so‘zning aynan shu kontekstdagi ma’nosini tekshiring.",
      11:"Bir xil so‘zlarni ortiqcha takrorlamang; mazmunga mos xilma-xil ifodalar tanlang.",
      12:"Sheva, vulgarizm, varvarizm va parazit birliklarni olib tashlang.",
    }
    for i,(score,cid) in enumerate(weak,1):
        lines += [f"{i}. {CRITERION_NAMES.get(cid,f'Mezon {cid}')} — {score:g}/2",f"   → {actions.get(cid,'Shu mezonni alohida nazorat qiling.')}",""]
    lines += ["📌 Topshirishdan oldingi 30 soniyalik tekshiruv:","1) Ikki qarash bormi?  2) Har ikkisi dalillanganmi?  3) Xulosa aniqmi?  4) Imlo va punktuatsiya tekshirildimi?"]
    await message.reply_text("\n".join(lines)[:3900],reply_markup=MAIN_KEYBOARD)

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
    arg=(context.args[0] if getattr(context,"args",None) else "")
    if arg.startswith("essay_"):
        t=get_test(arg[6:])
        if t and (t.get("essay_topic") or "").strip():
            context.user_data["topic"]=t["essay_topic"].strip(); context.user_data["stage"]="method"
            await update.message.reply_text(f"📝 Diagnostik test ({t['code']}) esse mavzusi:\n\n«{t['essay_topic']}»\n\nShu mavzuda esse yozing. Baholash usulini tanlang:",reply_markup=EVALUATION_METHOD_KEYBOARD)
            return
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n\n"
        "✍️ Esse tekshirish — esseni baho va tavsiyalar bilan tekshirtiring.\n"
        "🎓 Esse Akademiyasi — lug‘atlar, testlar, reyting, esse mashqi, dalil topish, statistika va muallif haqida ma’lumot.",
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
    if context.user_data.get("prep_file_mode") and await is_admin(update):
        try:
            os.makedirs("prep_resources", exist_ok=True)
            doc=update.message.document
            f=await context.bot.get_file(doc.file_id)
            b=io.BytesIO(); await f.download_to_memory(b)
            safe=re.sub(r"[^A-Za-z0-9_.-]+","_",doc.file_name or "material.pdf")
            path=os.path.join("prep_resources",safe)
            open(path,"wb").write(b.getvalue())
            context.user_data["prep_pending_file"]=path
            context.user_data.pop("prep_file_mode",None)
            context.user_data["prep_wizard"]={"step":"file_title","path":path}
            await update.message.reply_text("📄 Fayl qabul qilindi. Endi unga nom bering.",reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD)
        except Exception as e:
            await update.message.reply_text(f"❌ Faylni saqlashda xato: {e}",reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD)
        return
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
            await send_result(update.message,result,"text")
            tips=result.get("improvements") or []
            if tips: await update.message.reply_text("🎯 MASHQ UCHUN TAVSIYALAR\n\n"+"\n".join("• "+str(x) for x in tips[:8]),reply_markup=GROWTH_KEYBOARD)
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
    if context.user_data.get("prep_file_mode") and await is_admin(update):
        try:
            os.makedirs("prep_resources", exist_ok=True)
            p=update.message.photo[-1]
            f=await context.bot.get_file(p.file_id); b=io.BytesIO(); await f.download_to_memory(b)
            path=os.path.join("prep_resources",f"material_{update.message.message_id}.jpg")
            open(path,"wb").write(b.getvalue())
            context.user_data.pop("prep_file_mode",None)
            context.user_data["prep_wizard"]={"step":"file_title","path":path}
            await update.message.reply_text("🖼 Rasm qabul qilindi. Endi unga nom bering.",reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD)
        except Exception as e:
            await update.message.reply_text(f"❌ Rasmni saqlashda xato: {e}",reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD)
        return
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
                await send_result(update.message,result,"text")
                tips=result.get("improvements") or []
                if tips: await update.message.reply_text("🎯 MASHQ UCHUN TAVSIYALAR\n\n"+"\n".join("• "+str(x) for x in tips[:8]),reply_markup=GROWTH_KEYBOARD)
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
    await message.reply_text("✍️ ESSE YOZISH MASHQI\n\n📝 Bugungi mavzu:\n"+topic+"\n\nEsseni shu chatga yuboring. Matn, rasm yoki PDF yuborishingiz mumkin.\nBot uni BBA 24 ballik mezonlar asosida tekshiradi va xatolar hamda tavsiyalarni ko‘rsatadi.",reply_markup=GROWTH_KEYBOARD)

async def finish_growth_practice_text(message,user_id,essay_text,context):
    session=context.user_data.pop("growth_practice",None)
    if not session: return False
    await message.reply_text("⏳ Mashq essesi tekshirilmoqda...",reply_markup=GROWTH_KEYBOARD)
    try:
        result=await evaluate_text(session["topic"],essay_text)
        save_check(user_id,"growth_text",session["topic"],result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
        await send_result(message,result,"text")
        tips=result.get("improvements") or []
        if tips: await message.reply_text("🎯 MASHQ UCHUN TAVSIYALAR\n\n"+"\n".join("• "+str(x) for x in tips[:8]),reply_markup=GROWTH_KEYBOARD)
    except Exception:
        logger.exception("growth essay practice error")
        await message.reply_text("⚠️ Mashq esseni tekshirishda texnik muammo yuz berdi. Qayta urinib ko‘ring.",reply_markup=GROWTH_KEYBOARD)
    return True

async def send_essay_plan_builder(message,user_id,context,topic=None):
    if not topic:
        context.user_data["growth_plan_waiting"]=True
        await message.reply_text("🗂️ ESSE REJASINI TUZISH\n\nMavzuni yuboring.\n\nMasalan:\n«Ayrimlar onlayn ta’limni ma’qul ko‘rishadi, boshqalar esa offlayn ta’lim tarafdori.»",reply_markup=GROWTH_KEYBOARD); return
    await message.reply_text("⏳ Mavzu asosida individual reja tuzilmoqda...",reply_markup=GROWTH_KEYBOARD)
    prompt=f'''Sen O‘zbekistondagi argumentli esse yozishni o‘rgatuvchi ustozsan.
Mavzu: {topic}

Shu mavzu uchun individual reja tuz. Majburiy bo‘limlar: Kirish; 1-qarash; 1-qarash dalili; 2-qarash; 2-qarash dalili; shaxsiy pozitsiya; xulosa.
Har bir bo‘lim uchun shu mavzuga mos 1-2 aniq yo‘nalish ber. O‘ylab topilgan statistikani fakt sifatida yozma.
JSON: {{"plan":[{{"section":"...","points":["...","..."]}}]}}'''
    try:
        data=await openai_json(prompt,max_output_tokens=5000); lines=["🗂️ INDIVIDUAL ESSE REJASI","",f"📝 Mavzu: {topic}",""]
        for i,item in enumerate(data.get("plan") or [],1):
            lines.append(f"{i}. {item.get('section','')}")
            for point in (item.get("points") or [])[:3]: lines.append("   • "+str(point))
        await message.reply_text("\n".join(lines)[:3900],reply_markup=GROWTH_KEYBOARD)
    except Exception:
        logger.exception("essay plan builder error"); await message.reply_text("⚠️ Reja tuzishda texnik muammo yuz berdi. Mavzuni qayta yuboring.",reply_markup=GROWTH_KEYBOARD)

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
        lines=["💡 DALILLAR BANKI","",f"📝 Mavzu: {topic}","","📊 STATISTIK DALIL",str(st.get("claim","—")),f"Manba: {st.get('source','Tekshirish kerak')}","","👤 HAYOTIY MISOL",str(data.get("life","—")),"","🏛️ TARIXIY MISOL",str(data.get("historical","—")),"","🎓 MUTAXASSIS FIKRI",str(ex.get("claim","—")),f"Manba: {ex.get('source','Tekshirish kerak')}","","🧠 MANTIQIY DALIL",str(data.get("logical","—")),"","⚠️ Statistik raqam va iqtibosni ishlatishdan oldin manbasini tekshiring."]
        await message.reply_text("\n".join(lines)[:3900],reply_markup=GROWTH_KEYBOARD)
    except Exception:
        logger.exception("evidence helper error"); await message.reply_text("⚠️ Dalillarni tayyorlashda texnik muammo yuz berdi. Mavzuni qayta yuboring.",reply_markup=GROWTH_KEYBOARD)

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
            if text=="🎓 Milliy sertifikat":
                context.user_data["national_admin"]=True
                await national_admin_menu(update.message); return
            if context.user_data.get("national_admin"):
                if text=="⬅️ Admin panel":
                    context.user_data.pop("national_admin",None); await update.message.reply_text("Admin panel",reply_markup=ADMIN_KEYBOARD); return
                if text=="📋 Testlar": await national_test_list(update.message); return
                if text=="📚 Tayyorlov materiallari":
                    context.user_data["national_prep_admin"]=True
                    await prep_admin_menu(update.message); return
                if context.user_data.get("national_prep_admin"):
                    if text=="⬅️ Milliy sertifikat admin":
                        context.user_data.pop("national_prep_admin",None); await national_admin_menu(update.message); return
                    if text=="📋 Materiallar": await prep_list_admin(update.message); return
                    if text=="➕ Manba qo‘shish":
                        context.user_data["prep_wizard"]={"step":"title"}
                        await update.message.reply_text("Manba nomini yuboring."); return
                    if text=="📄 Fayl yuklash":
                        context.user_data["prep_file_mode"]=True
                        await update.message.reply_text("PDF, DOC, DOCX yoki boshqa tayyorlov faylini yuboring. Keyin nomini so‘rayman.",reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD); return
                    pw=context.user_data.get("prep_wizard")
                    if pw:
                        if pw.get("step")=="file_title":
                            create_prep_resource(text.strip(),"fayl",file_path=pw.get("path",""),created_by=update.effective_user.id)
                            context.user_data.pop("prep_wizard",None)
                            await update.message.reply_text("✅ Fayl tayyorlov bo‘limiga qo‘shildi.",reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD); return
                        if pw["step"]=="title":
                            pw["title"]=text.strip(); pw["step"]="kind"
                            await update.message.reply_text("Turini yuboring: manba / savol / topshiriq") ; return
                        if pw["step"]=="kind":
                            kind=text.strip().lower()
                            if kind not in ("manba","savol","topshiriq"):
                                await update.message.reply_text("❌ Faqat: manba, savol yoki topshiriq deb yozing."); return
                            pw["kind"]=kind; pw["step"]="content"
                            await update.message.reply_text("Endi matnni, savolni, topshiriqni yoki URL manzilini yuboring."); return
                        if pw["step"]=="content":
                            create_prep_resource(pw["title"],pw.get("kind","manba"),content=text,created_by=update.effective_user.id)
                            context.user_data.pop("prep_wizard",None)
                            await update.message.reply_text("✅ Tayyorlov materiali qo‘shildi.",reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD); return
                if text=="💳 Pullik bo‘lim sozlamasi":
                    cur=setting('national_paid','0'); new='0' if cur=='1' else '1'; set_setting('national_paid',new)
                    await update.message.reply_text(f"🎓 Milliy sertifikat bo‘limi: {'PULLIK' if new=='1' else 'BEPUL'}",reply_markup=NATIONAL_ADMIN_KEYBOARD); return
                if text=="➕ Test yaratish":
                    context.user_data["national_wizard"]={"step":"title","questions":[]}
                    await update.message.reply_text("1/3 Test nomini yuboring."); return
                wiz=context.user_data.get('national_wizard')
                if wiz:
                    if wiz['step']=='title':
                        wiz['title']=text; wiz['step']='questions'
                        await update.message.reply_text("""2/3 Endi 45 ta topshiriqni bittadan yuboring.

Format:
Y1|Savol matni|A|1|Izoh
O1|Savol matni|to‘g‘ri javob;muqobil javob|1|Izoh
O1AB|Savol|a javob;;b javob|1|Izoh

Y-1/Y-2 uchun javob harfi, O-1 uchun so‘z/jumla, O-1 a/b uchun `A javob;;B javob`.""" ); return
                    q=_parse_test_wizard_line(text)
                    if not q:
                        await update.message.reply_text("❌ Format xato. Qaytadan yuboring."); return
                    wiz['questions'].append(q); n=len(wiz['questions'])
                    if n<45:
                        await update.message.reply_text(f"✅ {n}/45 qabul qilindi. Keyingi topshiriqni yuboring."); return
                    try:
                        code=create_test(wiz['title'],wiz['questions'],update.effective_user.id)
                        context.user_data.pop('national_wizard',None)
                        await update.message.reply_text(f"""✅ Test tayyor!
🔑 Kod: {code}
📚 45 topshiriq
⏱ 180 daqiqa""",reply_markup=NATIONAL_ADMIN_KEYBOARD)
                    except Exception as e:
                        logger.exception('national create'); await update.message.reply_text(f"❌ Testni saqlashda xato: {e}")
                    return
            if text=="📈 Umumiy statistika":
                img=await asyncio.to_thread(make_admin_stats_image); await update.message.reply_photo(InputFile(img,filename="admin_statistika.jpg"),reply_markup=ADMIN_KEYBOARD); return
            if text=="👥 Foydalanuvchilar":
                rows=admin_users_page()
                if not rows:
                    await update.message.reply_text("👥 Hozircha foydalanuvchilar yo‘q.",reply_markup=ADMIN_KEYBOARD); return
                await update.message.reply_text("👥 Foydalanuvchilar\n\nKerakli foydalanuvchini tanlang:",reply_markup=admin_user_keyboard(rows)); return
            if text=="👥 Foydalanuvchilar CSV":
                await update.message.reply_document(InputFile(io.BytesIO(users_csv_bytes()),filename="users.csv"),caption="Foydalanuvchilar ro‘yxati",reply_markup=ADMIN_KEYBOARD); return
            if text=="💾 Zaxira nusxa":
                await backup_cmd(update,context); return
            if text=="🧪 Test holati":
                await update.message.reply_text(f"✅ Bot ishlayapti.\nModel: {MODEL}\nAdmin ID: {ADMIN_ID}\nAdmin username: @{ADMIN_USERNAME}\nDB: {DB_PATH} ({(os.path.getsize(DB_PATH)//1024) if os.path.exists(DB_PATH) else 0} KB)"+("\n⚠️ Baza yo‘li nisbiy: Render'da Disk ulanmagan bo‘lsa, har deployda baza o‘chib ketadi. /backup bilan zaxira oling." if not os.path.isabs(DB_PATH) else ""),reply_markup=ADMIN_KEYBOARD); return
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
    if text==APP_BUTTON_TEXT or text in LEGACY_MOVED:
        if text!=APP_BUTTON_TEXT:
            await update.message.reply_text("📱 Bu bo‘lim endi Mini ilova ichida.",reply_markup=MAIN_KEYBOARD)
        await send_app_open(update.message); return
    if text=="📊 Statistika":
        await update.message.reply_text(
            "📊 STATISTIKA BO‘LIMI\n\nKerakli bo‘limni tanlang:",
            reply_markup=STATISTICS_MENU
        )
        return
    if text=="🌱 Esseni o‘stirish":
        await show_growth_gate(update.message,update.effective_user.id)
        return
    if text=="🎓 Milliy sertifikat":
        await national_start_user(update.message,update.effective_user.id); return
    if context.user_data.get("national_session"):
        if await national_submit_answer_text(update,context,text): return
    if text=="✍️ Esse yozish mashqi":
        await send_daily_essay_practice(update.message,update.effective_user.id,context); return
    if text=="🗂️ Esse rejasini tuzish":
        await send_essay_plan_builder(update.message,update.effective_user.id,context); return
    if text=="💡 Dalil topib berish":
        await send_evidence_helper(update.message,update.effective_user.id,context); return
    if text=="⬅️ Asosiy menyu":
        await update.message.reply_text("🏠 Asosiy menyu", reply_markup=MAIN_KEYBOARD)
        return
    if text=="🧠 Xatolarim":
        await send_user_errors(update.message,update.effective_user.id)
        return
    if text=="🎯 Shaxsiy rejam":
        await send_personal_plan(update.message,update.effective_user.id)
        return
    if text in ("📚 Xato darsi", "📚 Xatolar ustida ishlash"):
        await send_error_lesson(update.message,update.effective_user.id)
        return
    if text=="🧪 Mini test":
        await send_mini_test(update.message,update.effective_user.id,context)
        return
    if text=="🔄 Esseni yaxshilash":
        await send_improvement(update.message,update.effective_user.id)
        return
    if text=="📊 Chuqur statistika":
        await send_deep_stats(update.message,update.effective_user.id)
        return

    if context.user_data.get("growth_practice") and text != "⬅️ Asosiy menyu":
        if await finish_growth_practice_text(update.message,update.effective_user.id,text,context): return
    if context.user_data.pop("growth_plan_waiting",False):
        await send_essay_plan_builder(update.message,update.effective_user.id,context,text); return
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
# 🎓 MILLIY SERTIFIKAT TEST TIZIMI — qo‘shimcha modul
# ============================================================
NATIONAL_ADMIN_KEYBOARD = ReplyKeyboardMarkup([
    ["➕ Test yaratish", "📋 Testlar"],
    ["📚 Tayyorlov materiallari", "💳 Pullik bo‘lim sozlamasi"],
    ["⬅️ Admin panel"],
], resize_keyboard=True)

async def prep_admin_menu(message):
    rows=list_all_prep_resources()
    await message.reply_text(
        "📚 MILLIY SERTIFIKATGA TAYYORLOV — ADMIN\n\n"
        "Bu yerga muhim manbalar, savollar va topshiriqlarni qo‘shishingiz mumkin.\n"
        f"Hozirgi materiallar: {len(rows)} ta\n\n"
        "➕ Manba qo‘shish — nomi va matni/URL\n"
        "📄 Fayl yuklash — PDF/DOC/DOCX va boshqa materiallar (keyingi qadamda Telegramdan yuboriladi).",
        reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD)

NATIONAL_PREP_ADMIN_KEYBOARD = ReplyKeyboardMarkup([
    ["➕ Manba qo‘shish", "📋 Materiallar"],
    ["📄 Fayl yuklash", "⬅️ Milliy sertifikat admin"],
], resize_keyboard=True)

async def prep_list_admin(message):
    rows=list_all_prep_resources()
    if not rows:
        await message.reply_text("📚 Hozircha material kiritilmagan.", reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD); return
    lines=["📚 TAYYORLOV MATERIALlari\n"]
    for r in rows[:40]:
        lines.append(f"#{r['id']} • {r['title']} • {r['kind']}")
    await message.reply_text("\n".join(lines)[:3900], reply_markup=NATIONAL_PREP_ADMIN_KEYBOARD)

async def national_admin_menu(message):
    await message.reply_text(
        "🎓 MILLIY SERTIFIKAT — ADMIN\n\n"
        "45 topshiriqli testlarni boshqarish.\n"
        "Y-1: yopiq | Y-2: moslashtirish | O-1: ochiq a/b | O-2: esse.\n\n"
        f"Pullik holati: {'YOQILGAN' if setting('national_paid','0')=='1' else 'BEPUL'}",
        reply_markup=NATIONAL_ADMIN_KEYBOARD)

async def national_test_list(message):
    rows=list_tests()
    if not rows:
        await message.reply_text("📋 Hozircha testlar kiritilmagan.",reply_markup=NATIONAL_ADMIN_KEYBOARD); return
    lines=["📋 TESTLAR\n"]
    for r in rows[:30]:
        lines.append(f"🔑 {r['code']} — {r['title']}\n📚 {r['subject']} | {r['duration_min']} daqiqa | {'Nashr qilingan' if r['published'] else 'Yashirin'}")
    await message.reply_text("\n\n".join(lines)[:3900],reply_markup=NATIONAL_ADMIN_KEYBOARD)

async def national_start_user(message, user_id):
    await message.reply_text(
        "🎓 MILLIY SERTIFIKATGA TAYYORGARLIK\n\n"
        "45 topshiriqli testni maxsus kod orqali boshlang.\n"
        "Javoblar yopiq topshiriqlarda harf, ochiq topshiriqlarda esa javobning o‘zi bilan kiritiladi.\n\n"
        "🔑 Test kodini yuboring:")

def _parse_test_wizard_line(text):
    # Format: TYPE|QUESTION|ANSWER(S)|POINTS|EXPLANATION
    parts=[x.strip() for x in text.split('|',4)]
    if len(parts)<3:return None
    typ=parts[0].upper()
    if typ not in ('Y1','Y2','O1','O1AB'): return None
    q={'type':typ,'text':parts[1],'points':float(parts[3]) if len(parts)>3 and parts[3] else 1.0,'explanation':parts[4] if len(parts)>4 else ''}
    if typ in ('Y1','Y2'): q['answer']=parts[2].upper()
    elif typ=='O1': q['answers']=[x.strip() for x in parts[2].split(';') if x.strip()]
    else:
        ab=parts[2].split(';;',1)
        if len(ab)!=2:return None
        q['a_answers']=[x.strip() for x in ab[0].split(';') if x.strip()]
        q['b_answers']=[x.strip() for x in ab[1].split(';') if x.strip()]
    return q

async def national_submit_answer_text(update,context,text):
    session=context.user_data.get('national_session')
    if not session:return False
    test=get_test(session['code'])
    if not test:
        context.user_data.pop('national_session',None); return False
    idx=int(session.get('index',1))
    q=test['questions'][idx-1]
    typ=q.get('type','Y1')
    if typ in ('Y1','Y2'):
        val=text.strip().upper()
        if not re.fullmatch(r'[A-Z]+',val):
            await update.message.reply_text('❌ Faqat javob harfini kiriting: A, B, C yoki D.'); return True
    elif typ=='O1':
        val=text.strip()
        if not val: await update.message.reply_text('❌ Javobni yozing.'); return True
    else:
        # O1AB: a va b javoblarini | bilan ajratish
        parts=[x.strip() for x in text.split('|',1)]
        if len(parts)!=2 or not parts[0] or not parts[1]:
            await update.message.reply_text('❌ A va B javoblarini quyidagicha yozing:\nJavob A | Javob B'); return True
        val=parts
    session.setdefault('answers',{})[str(idx)]=val
    session['index']=idx+1
    if session['index']<=45:
        nq=test['questions'][session['index']-1]
        hint='A/B/C/D harfini kiriting' if nq.get('type') in ('Y1','Y2') else ('Javobni yozing' if nq.get('type')=='O1' else 'A javob | B javob ko‘rinishida yozing')
        await update.message.reply_text(f"🧪 {session['index']}/45\n{nq.get('text','')}\n\n✏️ {hint}")
    else:
        raw,score,errors,maxp=grade_national(test,session['answers'])
        essay=essay_for_test(update.effective_user.id,test)
        dr=diagnostic_result(test,update.effective_user.id,errors,essay)
        score=dr['test_t']; combined=dr['combined']; lvl=dr['level']
        essay_total=dr['essay24']
        save_attempt(update.effective_user.id,test['id'],essay['id'] if essay else None,session['answers'],raw,combined,lvl,errors)
        context.user_data.pop('national_session',None)
        await update.message.reply_text(
            f"❌ TESTDAGI XATOLAR\n\n"
            + ("\n".join([f"{e['number']}-savol: siz — {e['user']} | to‘g‘ri — {e['correct']}" + (f"  (qisman: {e['earned']:g}/{e['points']:g} ball)" if e.get('wrong_parts') is not None and e.get('earned') else "") for e in errors[:35]]) if errors else '🎉 Barcha javoblar to‘g‘ri!')
            + f"\n\n📊 To‘g‘ri javob: {raw:g}/{maxp:g}"
            + f"\n🧪 Test ({'Rasch T-ball' if dr['rasch'] else 'taxminiy, foiz'}): {score:.1f}/75"
            + (f"\n📝 Esse: {essay_total:g}/24 → {dr['essay_t']:g}/75" if essay_total is not None else (f"\n📝 Esse: «{test['essay_topic']}» mavzusida topilmadi → 0/75" if test.get('essay_topic') else "\n📝 Esse topilmadi → 0/75"))
            + f"\n\n📈 UMUMIY: ({score:.1f} + {dr['essay_t']:g}) ÷ 2 = {combined:.1f}/75\n🏅 Daraja: {lvl}"
            + (f"\n\nℹ️ {dr['note']}" if dr['note'] else "")
            + "\n\nBu rasmiy davlat sertifikati emas, tayyorlov diagnostikasi.",
            reply_markup=MAIN_KEYBOARD)
    return True

# ============================================================
# HEALTH / MAIN
# ============================================================

# ============================================================
# MINI APP: Telegram initData tekshiruvi va admin huquqi
# ============================================================
# Test kiritish (yaratish/o'chirish) va tayyorlov materiali qo'shish faqat ADMIN_ID uchun.
# Hamma uchun ochiq qilish kerak bo'lsa Render'da TEST_CREATE_ADMIN_ONLY=0 qo'ying.
TEST_CREATE_ADMIN_ONLY = os.getenv("TEST_CREATE_ADMIN_ONLY", "0") != "0"

def verify_init_data(init_data, max_age=172800):
    """Telegram WebApp initData imzosini tekshiradi. To'g'ri bo'lsa user dict, aks holda None."""
    try:
        if not init_data: return None
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        got = pairs.pop("hash", "")
        check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got): return None
        if time.time() - int(pairs.get("auth_date", "0")) > max_age: return None
        return json.loads(pairs.get("user", "{}"))
    except Exception:
        return None

def tg_api(method, payload):
    req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read().decode())

GROWTH_LABELS = {"errors": "📚 Xatolar ustida ishlash", "improve": "🔄 Esseni yaxshilash",
                 "practice": "✍️ Esse yozish mashqi", "evidence": "💡 Dalil topib berish"}

def delete_test_by_code(code):
    from national_certificate import db as _ndb
    with _ndb() as c:
        c.execute("UPDATE national_tests SET published=0 WHERE code=?", (code.upper().strip(),)); c.commit()

async def send_app_open(message):
    url=miniapp_web_url()
    if not url:
        await message.reply_text("Mini ilova hozircha sozlanmagan."); return
    await message.reply_text("🎓 Esse Akademiyasi — lug‘atlar, testlar, reyting, esse mashqi, dalil topish, statistika va muallif haqida ma’lumot 👇",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Mini ilovani ochish",web_app=WebAppInfo(url=url))]]))

# ---- Mini App ichidagi AI vositalari (esse mashqi va dalil topish): kunlik limit + fon ishlari
AI_FREE_DAILY=int(os.getenv("AI_FREE_DAILY","2")); AI_PREMIUM_DAILY=int(os.getenv("AI_PREMIUM_DAILY","10"))
_JOBS={}; _JOBS_LOCK=threading.Lock(); _AI_SEM=threading.BoundedSemaphore(2)

def ai_limit_for(uid):
    if int(uid)==int(ADMIN_ID): return 1000
    try: return AI_PREMIUM_DAILY if growth_premium_active(uid) else AI_FREE_DAILY
    except Exception: return AI_FREE_DAILY

async def _practice_job(uid,topic,text):
    result=await evaluate_text(topic,text)
    total=authoritative_total24(result); normalize_summary_score(result)
    try: save_check(uid,"growth_text",topic,total,word_count(text),result.get("status","normal"),result)
    except Exception: logger.exception("practice save_check")
    crit=[{"name":str(x.get("name","")),"score":x.get("score"),"reason":str(x.get("reason",""))[:220]} for x in (result.get("scores") or [])]
    return {"kind":"practice","topic":topic,"total":total,"to75":to_75(total),"words":word_count(text),"criteria":crit,
            "summary":str(result.get("summary",""))[:700],"improvements":[str(i)[:220] for i in (result.get("improvements") or [])[:8]]}

async def _evidence_job(uid,topic):
    prompt=f'''Sen argumentli esse uchun dalil tayyorlovchi yordamchisan.
Mavzu: {topic}
5 tur ber: statistik dalil, hayotiy misol, tarixiy misol, mutaxassis fikri, mantiqiy dalil.
Muhim: manbasi tekshirilmagan raqam, ism yoki iqtibosni fakt sifatida UYDIMA. Ishonchli aniq manba bo‘lmasa, raqam o‘rniga qanday statistikani izlash kerakligini ayt. Mutaxassis fikrida tasdiqlanmagan iqtibosni qo‘shtirnoqqa olma.
JSON: {{"statistical":{{"claim":"...","source":"..."}},"life":"...","historical":"...","expert":{{"claim":"...","source":"..."}},"logical":"..."}}'''
    d=await openai_json(prompt,max_output_tokens=6000); st=d.get("statistical") or {}; ex=d.get("expert") or {}
    return {"kind":"evidence","topic":topic,"statistical":{"claim":str(st.get("claim","—")),"source":str(st.get("source","Tekshirish kerak"))},
            "life":str(d.get("life","—")),"historical":str(d.get("historical","—")),"expert":{"claim":str(ex.get("claim","—")),"source":str(ex.get("source","Tekshirish kerak"))},"logical":str(d.get("logical","—"))}

def start_ai_job(uid,make_coro):
    import secrets
    jid=secrets.token_hex(8)
    with _JOBS_LOCK:
        for k in [k for k,v in _JOBS.items() if time.time()-v["t"]>3600]: _JOBS.pop(k,None)
        _JOBS[jid]={"uid":uid,"status":"running","t":time.time()}
    def run():
        try:
            with _AI_SEM: data=asyncio.run(make_coro())
            _JOBS[jid].update(status="done",data=data)
        except Exception:
            logger.exception("ai job error"); mx.ai_refund(uid)
            _JOBS[jid].update(status="error",error="Texnik muammo yuz berdi. Limitingiz qaytarildi, birozdan so‘ng qayta urinib ko‘ring.")
    threading.Thread(target=run,daemon=True).start(); return jid

class HealthHandler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        raw=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Headers','Content-Type, X-Init-Data'); self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS'); self.end_headers(); self.wfile.write(raw)
    def do_OPTIONS(self): self._json({'ok':True})
    def _user(self):
        u=verify_init_data(self.headers.get('X-Init-Data',''))
        if u and u.get('id'): mx.touch_user(u)
        return int(u['id']) if u and u.get('id') else None
    def _ip(self):
        xf=self.headers.get('X-Forwarded-For','')
        return (xf.split(',')[-1].strip() if xf else self.client_address[0]) or '?'
    def _png(self, data):
        self.send_response(200); self.send_header('Content-Type','image/png'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(data)
    def _guard(self, uid, per_min=90):
        """Spam/blok himoyasi: IP va foydalanuvchi bo'yicha tezlik cheklovi + ban. True: davom etish mumkin."""
        if not mx.allow('ip:'+self._ip(), 300, 60): self._json({'ok':False,'error':'Juda ko‘p so‘rov. Bir daqiqadan keyin urinib ko‘ring.'},429); return False
        if uid is not None:
            if mx.is_banned(uid): self._json({'ok':False,'error':'Hisobingiz bloklangan.'},403); return False
            if not self._is_admin(uid) and not mx.allow('u:%s'%uid, per_min, 60): self._json({'ok':False,'error':'Juda tez-tez so‘rov yuboryapsiz. Biroz kuting.'},429); return False
        return True
    def _is_admin(self,uid): return uid is not None and int(uid)==int(ADMIN_ID)
    MIME={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'application/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.ico':'image/x-icon'}
    def _static(self, rel):
        """miniapp/ papkasidagi fayllarni (index.html, style.css, app.js, *.json) beradi."""
        base=os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'miniapp'))
        rel=unquote(rel).lstrip('/') or 'index.html'
        full=os.path.realpath(os.path.join(base,rel))
        if not full.startswith(base+os.sep) or not os.path.isfile(full): return False
        ext=os.path.splitext(full)[1].lower()
        data=open(full,'rb').read()
        self.send_response(200)
        self.send_header('Content-Type',self.MIME.get(ext,'application/octet-stream'))
        # Trafikni tejash: katta lug'at fayllari 1 kunga keshlanadi va siqiladi (gzip)
        self.send_header('Cache-Control','public, max-age=86400' if ext=='.json' else 'no-cache')
        if ext in ('.json','.js','.css','.html') and len(data)>1024 and 'gzip' in self.headers.get('Accept-Encoding',''):
            import gzip
            data=gzip.compress(data,compresslevel=6); self.send_header('Content-Encoding','gzip'); self.send_header('Vary','Accept-Encoding')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers(); self.wfile.write(data); return True
    def do_GET(self):
        try:
            # ?api=... kabi query qismi route'ni buzmasligi uchun faqat path olinadi
            _u=urlparse(self.path); self.path=_u.path; self.query=parse_qs(_u.query)
            if self.path=='/miniapp':
                self.send_response(301); self.send_header('Location','/miniapp/'); self.end_headers(); return
            if self.path.startswith('/miniapp/'):
                if self._static(self.path[len('/miniapp/'):]): return
                self._json({'ok':False,'error':'Fayl topilmadi'},404); return
            if self.path.startswith('/api/') and not self.path.startswith('/api/cert/'):
                if not self._guard(self._user() if self.headers.get('X-Init-Data') else None): return
            if self.path.startswith('/api/cert/verify/'):
                c=mx.get_cert(self.path.rsplit('/',1)[-1])
                self._json({'ok':bool(c),'kind':c['kind'] if c else None,'name':c['data'].get('name') if c else None,'score':c['data'].get('score') if c else None,'level':c['data'].get('level') if c else None,'date':c['created_at'][:10] if c else None}); return
            if self.path.startswith('/api/cert/') and self.path.endswith('.png'):
                if not mx.allow('cert:'+self._ip(), 20, 60): self._json({'ok':False,'error':'Juda ko‘p so‘rov.'},429); return
                code=self.path[len('/api/cert/'):-4]; c=mx.get_cert(code)
                if not c: self._json({'ok':False,'error':'Sertifikat topilmadi'},404); return
                self._png(mx.render_certificate(c['kind'],c['data'],c['code'])); return
            if self.path.startswith('/api/rating/'):
                kind=self.path.rsplit('/',1)[-1]
                if kind not in ('day','week','month'): self._json({'ok':False,'error':'Noto‘g‘ri davr'},400); return
                self._json({'ok':True,**mx.rating_payload(kind,self._user(),ADMIN_ID)}); return
            if self.path=='/api/admin/overview':
                uid=self._user()
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                self._json({'ok':True,**mx.overview(ADMIN_ID)}); return
            if self.path=='/api/practice/topic':
                self._json({'ok':True,'topic':daily_essay_topic()}); return
            if self.path.startswith('/api/job/'):
                uid=self._user(); j=_JOBS.get(self.path.rsplit('/',1)[-1])
                if not j or uid is None or j['uid']!=uid: self._json({'ok':False,'error':'Topilmadi'},404); return
                self._json({'ok':True,'status':j['status'],'data':j.get('data'),'error':j.get('error')}); return
            if self.path=='/api/me':
                uid=self._user()
                self._json({'ok':uid is not None,'uid':uid,'is_admin':self._is_admin(uid),'can_create':(not TEST_CREATE_ADMIN_ONLY) or self._is_admin(uid),'admin_username':str(globals().get('ADMIN_USERNAME','') or '').lstrip('@'),'ai_limit':ai_limit_for(uid) if uid else 0,'ai_used':mx.ai_used(uid) if uid else 0}); return
            if self.path=='/api/quiz/list':
                uid=self._user() if self.headers.get('X-Init-Data') else None
                self._json({'ok':True,'items':mx.quiz_list(uid,self._is_admin(uid))}); return
            if self.path=='/api/national/tests':
                tests=[{'code':t['code'],'title':t['title'],'subject':t['subject'],'duration_min':t['duration_min'],'created_at':t['created_at'],'official':t['official'],'attempts':t['attempts']} for t in mx.list_tests_ex(ADMIN_ID)]
                self._json({'ok':True,'tests':tests}); return
            if self.path=='/api/national/prep/resources':
                public=[]
                for r in list_prep_resources():
                    public.append({'id':r['id'],'title':r['title'],'kind':r['kind'],'content':r.get('content') or '', 'file_url':('/api/national/prep/file/'+str(r['id'])) if r.get('file_path') else ''})
                self._json({'ok':True,'resources':public}); return
            if self.path.startswith('/api/national/prep/file/'):
                rid=int(self.path.rsplit('/',1)[-1])
                rows=list_all_prep_resources(); r=next((x for x in rows if int(x['id'])==rid),None)
                if not r or not r.get('file_path') or not os.path.exists(r['file_path']): self._json({'ok':False,'error':'Fayl topilmadi'},404); return
                data=open(r['file_path'],'rb').read(); self.send_response(200); self.send_header('Content-Type','application/octet-stream'); self.send_header('Content-Disposition',f'inline; filename="{os.path.basename(r["file_path"])}"'); self.end_headers(); self.wfile.write(data); return
            if self.path.startswith('/api/national/test/'):
                code=self.path.rsplit('/',1)[-1]; t=get_test(code)
                if not t:self._json({'ok':False,'error':'Test topilmadi'},404); return
                public={'id':t['id'],'code':t['code'],'title':t['title'],'subject':t['subject'],'duration_min':t['duration_min'],'essay_topic':t.get('essay_topic',''),'essay_link':(f'https://t.me/{BOT_USERNAME}?start=essay_{t["code"]}' if BOT_USERNAME and t.get('essay_topic') else ''),'questions':[{'number':i+1,'type':q.get('type','Y1'),'text':q.get('text',''),'options':q.get('options',[]),'points':q.get('points',1)} for i,q in enumerate(t['questions'])]}
                self._json({'ok':True,'test':public}); return
            if self.path.startswith('/api/national/essay-score/'):
                try:
                    uid=int(self.path.rsplit('/',1)[-1])
                    if self._user()!=uid: self._json({'ok':False,'error':'Telegram ichida oching.'},401); return
                    _t=get_test((self.query.get('code') or [''])[0]) if self.query.get('code') else None
                    essay=essay_for_test(uid,_t) if _t else latest_essay_check(uid)
                    self._json({'ok':True,'essay_score':essay['total'] if essay else None,'check_id':essay['id'] if essay else None,'topic':(_t or {}).get('essay_topic','')})
                except Exception as e:
                    self._json({'ok':False,'error':str(e)},400)
                return
            if self.path.startswith('/api/stats/'):
                try:
                    uid=int(self.path.rsplit('/',1)[-1])
                    if self._user()!=uid: self._json({'ok':False,'error':'Telegram ichida oching.'},401); return
                    s,last,prev=stats_for_user(uid)
                    self._json({'ok':True,'stats':s,'last':last,'previous':prev})
                except Exception as e:
                    self._json({'ok':False,'error':str(e)},400)
                return
            self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.end_headers(); self.wfile.write(b'Esse baholovchi bot ishlayapti.')
        except Exception as e:
            self._json({'ok':False,'error':str(e)},500)
    def do_POST(self):
        try:
            self.path=urlparse(self.path).path
            n=int(self.headers.get('Content-Length','0'))
            if n>300000: self._json({'ok':False,'error':'So‘rov juda katta.'},413); return
            body=json.loads(self.rfile.read(n).decode('utf-8'))
            uid=self._user()
            if uid is None: self._json({'ok':False,'error':'Telegram orqali oching: foydalanuvchi tasdiqlanmadi.'},401); return
            if not self._guard(uid,60): return
            if not isinstance(body,dict): self._json({'ok':False,'error':'Noto‘g‘ri so‘rov.'},400); return
            if self.path=='/api/admin/ban':
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                tid=int(body.get('user_id',0))
                if tid==ADMIN_ID or tid<=0: self._json({'ok':False,'error':'Bu foydalanuvchini bloklab bo‘lmaydi.'},400); return
                mx.ban(tid,str(body.get('reason','admin'))[:200],uid); self._json({'ok':True}); return
            if self.path=='/api/admin/unban':
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                mx.unban(int(body.get('user_id',0))); self._json({'ok':True}); return
            if self.path=='/api/quiz/create':
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin savol qo‘sha oladi.'},403); return
                qid,err=mx.quiz_create(uid,body)
                self._json({'ok':qid is not None,'id':qid,'error':err},200 if qid else 400); return
            if self.path=='/api/quiz/delete':
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                mx.quiz_delete(int(body.get('id',0))); self._json({'ok':True}); return
            if self.path=='/api/quiz/answer':
                if not mx.allow('quiz:%s'%uid,30,600): self._json({'ok':False,'error':'Juda tez-tez. Biroz kuting.'},429); return
                res,err=mx.quiz_answer(uid,int(body.get('id',0)),body.get('answer',''))
                self._json({'ok':res is not None,'error':err,**(res or {})},200 if res else 400); return
            if self.path in ('/api/practice/submit','/api/evidence'):
                if self.path=='/api/evidence':
                    topic=str(body.get('topic','')).strip()
                    if len(topic)<8 or len(topic)>400: self._json({'ok':False,'error':'Mavzuni 8–400 belgi orasida yozing.'},400); return
                else:
                    topic=daily_essay_topic(); essay=str(body.get('essay','')).strip()[:7000]
                    if word_count(essay)<40: self._json({'ok':False,'error':'Esse juda qisqa (kamida 40 so‘z yozing).'},400); return
                if not mx.ai_consume(uid,ai_limit_for(uid)):
                    self._json({'ok':False,'error':'Bugungi AI limitingiz tugadi. Ertaga qayta urinib ko‘ring.','limit':True},429); return
                jid=start_ai_job(uid,(lambda: _evidence_job(uid,topic)) if self.path=='/api/evidence' else (lambda: _practice_job(uid,topic,essay)))
                self._json({'ok':True,'job':jid}); return
            if self.path=='/api/cert/send':
                c=mx.get_cert(str(body.get('code','')))
                if not c or int(c['user_id'])!=uid: self._json({'ok':False,'error':'Sertifikat topilmadi.'},404); return
                if not mx.allow('certsend:%s'%uid,5,600): self._json({'ok':False,'error':'Juda tez-tez. 10 daqiqadan keyin urinib ko‘ring.'},429); return
                threading.Thread(target=lambda: mx.send_photo(TELEGRAM_BOT_TOKEN,uid,mx.render_certificate(c['kind'],c['data'],c['code']),'📜 Sertifikatingiz'),daemon=True).start()
                self._json({'ok':True}); return
            if self.path=='/api/national/delete':
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin o‘chira oladi.'},403); return
                delete_test_by_code(str(body.get('code',''))); self._json({'ok':True}); return
            if self.path=='/api/national/prep/create':
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin material qo‘sha oladi.'},403); return
                t=str(body.get('title','')).strip()[:150]; c=str(body.get('content','')).strip()[:6000]
                if not t or not c: self._json({'ok':False,'error':'Sarlavha va matnni kiriting.'},400); return
                create_prep_resource(t,str(body.get('kind','manba'))[:40],content=c,created_by=uid); self._json({'ok':True}); return
            if self.path=='/api/national/create':
                if TEST_CREATE_ADMIN_ONLY and not self._is_admin(uid):
                    self._json({'ok':False,'error':'Test kiritish faqat admin uchun.'},403); return
                title=str(body.get('title','')).strip()[:100]; questions=body.get('questions') or []
                if not self._is_admin(uid):
                    if not mx.allow('create:%s'%uid,3,3600): self._json({'ok':False,'error':'Soatiga 3 tadan ko‘p test yaratib bo‘lmaydi.'},429); return
                    if mx.count_user_tests(uid,mx.period_bounds('day')[0])>=5: self._json({'ok':False,'error':'Bir kunda 5 tadan ko‘p test yaratib bo‘lmaydi.'},429); return
                if not isinstance(questions,list): self._json({'ok':False,'error':'Savollar noto‘g‘ri.'},400); return
                if not uid: self._json({'ok':False,'error':'Foydalanuvchi aniqlanmadi.'},400); return
                if not title: self._json({'ok':False,'error':'Test nomi kiritilmagan.'},400); return
                essay_topic=re.sub(r'\s+',' ',str(body.get('essay_topic','')).strip())
                if len(essay_topic)<8 or len(essay_topic)>300: self._json({'ok':False,'error':'Esse mavzusini kiriting (8–300 belgi).'},400); return
                if len(questions)!=45: self._json({'ok':False,'error':'Milliy sertifikat testi 45 ta topshiriqdan iborat bo‘lishi kerak.'},400); return
                for i,q in enumerate(questions,1):
                    if not isinstance(q,dict):
                        self._json({'ok':False,'error':f'{i}-savol ma’lumoti noto‘g‘ri.'},400); return
                    typ=q.get('type','Y1')
                    expected='Y1' if i<=32 else ('Y2' if i<=35 else ('O1' if i<=39 else ('O1AB' if i<=44 else 'O2')))
                    if typ != expected:
                        self._json({'ok':False,'error':f'{i}-savol turi {expected} bo‘lishi kerak.'},400); return
                    if typ in ('Y1','Y2') and not str(q.get('answer','')).strip():
                        self._json({'ok':False,'error':f'{i}-savolning to‘g‘ri javobi belgilanmagan.'},400); return
                    if typ=='O1' and not q.get('answers'):
                        self._json({'ok':False,'error':f'{i}-savolning to‘g‘ri javobi kiritilmagan.'},400); return
                    if typ=='O1AB' and (not q.get('a_answers') or not q.get('b_answers')):
                        self._json({'ok':False,'error':f'{i}-savolning a) va b) javoblari kiritilmagan.'},400); return
                for q in questions:
                    tx=str(q.get('text','')).strip()[:1500]
                    if tx: q['text']=tx
                    else: q.pop('text',None)
                code=create_test(title,questions,uid,subject=str(body.get('subject','Ona tili va adabiyot')),duration=int(body.get('duration_min',180)),publish=1,essay_topic=essay_topic)
                if not self._is_admin(uid):
                    nm=mx.user_name(uid)
                    threading.Thread(target=lambda: tg_api('sendMessage',{'chat_id':ADMIN_ID,'text':f"🆕 Yangi foydalanuvchi testi\n\nNomi: {title}\nKod: {code}\nMuallif: {nm} (ID {uid})\n\nMini App → Admin panelda ko‘rib, kerak bo‘lsa o‘chiring yoki muallifni bloklang."}),daemon=True).start()
                self._json({'ok':True,'code':code}); return
            if self.path!='/api/national/submit': self._json({'ok':False,'error':'Not found'},404); return
            code=str(body.get('code','')).upper().strip(); answers=body.get('answers') or {}
            if not isinstance(answers,dict) or len(json.dumps(answers))>20000: self._json({'ok':False,'error':'Javoblar noto‘g‘ri.'},400); return
            if not self._is_admin(uid) and not mx.allow('submit:%s'%uid,10,600): self._json({'ok':False,'error':'Juda tez-tez topshiryapsiz. Biroz kuting.'},429); return
            t=get_test(code)
            if not t:self._json({'ok':False,'error':'Test topilmadi'},404); return
            raw,score,errors,maxp=grade_national(t,answers); essay=essay_for_test(uid,t)
            dr=diagnostic_result(t,uid,errors,essay)       # Rasch T (test) + esse (75 ballik jadval); umumiy = o'rtacha
            score=dr['test_t']; essay_score=dr['essay24']; combined=dr['combined']; lvl=dr['level']
            save_attempt(uid,t['id'],essay['id'] if essay else None,answers,raw,combined,lvl,errors)
            cert_code=None
            try:
                cdata={'name':mx.user_name(uid),'subject':t.get('subject','Ona tili va adabiyot'),'score':round(float(combined),1),'level':lvl,'test_score':round(float(score),1),'essay':(round(float(essay_score),1) if essay_score is not None else '—'),'essay75':dr['essay_t'],'raw':raw,'max':maxp,'title':t['title'],'test_code':t['code'],'date':datetime.now(mx.TZ).strftime('%d.%m.%Y')}
                cert_code=mx.new_cert(uid,'diag',cdata)
                threading.Thread(target=lambda: mx.send_photo(TELEGRAM_BOT_TOKEN,uid,mx.render_certificate('diag',cdata,cert_code),'📜 Diagnostik sertifikatingiz tayyor!\nBu — tayyorlov natijasi, rasmiy davlat sertifikati emas.'),daemon=True).start()
            except Exception as e: logging.warning('cert error: %s',e)
            self._json({'ok':True,'raw_score':raw,'max_score':maxp,'score_75':score,'combined_score_75':combined,'level':lvl,'errors':errors,'essay_score':essay_score,'essay_75':dr['essay_t'],'rasch':dr['rasch'],'cohort':dr['cohort'],'note':dr['note'],'essay_topic':t.get('essay_topic',''),'cert_code':cert_code})
        except Exception as e: self._json({'ok':False,'error':str(e)},400)
    def log_message(self,*args): pass

def backup_db_bytes():
    """Bazaning bir butun (izchil) nusxasini bayt ko'rinishida qaytaradi."""
    import tempfile
    fd,tmp=tempfile.mkstemp(suffix='.sqlite3'); os.close(fd)
    try:
        with DB_LOCK:
            src=sqlite3.connect(DB_PATH,timeout=30); dst=sqlite3.connect(tmp)
            src.backup(dst); dst.close(); src.close()
        with open(tmp,'rb') as f: return f.read()
    finally:
        try: os.remove(tmp)
        except Exception: pass

def restore_db_bytes(data):
    """Zaxira faylini tekshirib, joriy bazani shu nusxa bilan almashtiradi."""
    import tempfile
    fd,tmp=tempfile.mkstemp(suffix='.sqlite3'); os.close(fd)
    try:
        with open(tmp,'wb') as f: f.write(data)
        chk=sqlite3.connect(tmp)
        try:
            ok=chk.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            tables={r[0] for r in chk.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally: chk.close()
        if not ok or not ({'users','checks'} & tables): raise ValueError('Bu fayl bot bazasiga o‘xshamaydi.')
        with DB_LOCK:
            src=sqlite3.connect(tmp); dst=sqlite3.connect(DB_PATH,timeout=30)
            src.backup(dst); dst.close(); src.close()
    finally:
        try: os.remove(tmp)
        except Exception: pass
    init_db(); init_national_db(); init_prep_db(); mx.init_extra_db()

def _backup_name(): return 'esse_bot_%s.sqlite3'%datetime.now(mx.TZ).strftime('%Y%m%d_%H%M')

def start_backup_loop():
    """Har BACKUP_HOURS soatda (standart 24) bazani adminga Telegram orqali yuboradi. Birinchisi 30 daqiqadan keyin."""
    hours=float(os.getenv('BACKUP_HOURS','24') or 24)
    if hours<=0: return
    def run():
        time.sleep(1800)
        while True:
            try:
                data=backup_db_bytes()
                if len(data)<45*1024*1024: mx.send_document(TELEGRAM_BOT_TOKEN,ADMIN_ID,_backup_name(),data,'💾 Avtomatik zaxira nusxa. Saqlab qo‘ying.')
            except Exception as e: logging.warning('backup error: %s',e)
            time.sleep(hours*3600)
    threading.Thread(target=run,daemon=True).start()

async def backup_cmd(update, context):
    if update.effective_user.id!=ADMIN_ID: return
    data=await asyncio.to_thread(backup_db_bytes)
    await update.message.reply_document(InputFile(io.BytesIO(data),filename=_backup_name()),caption='💾 Baza zaxira nusxasi. Saqlab qo‘ying.\n\nTiklash uchun shu faylni botga yuboring, izohiga yozing:\n/restore ha')

async def restore_cmd(update, context):
    if update.effective_user.id!=ADMIN_ID: return
    msg=update.message; doc=msg.document
    if (msg.caption or '').strip().lower()!='/restore ha':
        await msg.reply_text('Tiklash uchun zaxira faylini yuboring va izohiga aynan shuni yozing:\n/restore ha'); return
    if doc.file_size and doc.file_size>45*1024*1024: await msg.reply_text('Fayl juda katta.'); return
    try:
        tg_file=await context.bot.get_file(doc.file_id); data=bytes(await tg_file.download_as_bytearray())
        old=await asyncio.to_thread(backup_db_bytes)
        await msg.reply_document(InputFile(io.BytesIO(old),filename='oldingi_'+_backup_name()),caption='Xavfsizlik uchun tiklashdan oldingi baza nusxasi.')
        await asyncio.to_thread(restore_db_bytes,data)
        await msg.reply_text('✅ Baza tiklandi. Statistika va reyting zaxira holatiga qaytdi.')
    except Exception as e:
        await msg.reply_text(f'❌ Tiklab bo‘lmadi: {e}')

_flood={}
async def spam_guard(update, context):
    """Barcha yangilanishlar oldidan ishlaydi: bloklanganlarni to'xtatadi, spamni vaqtincha jim qiladi."""
    u=update.effective_user
    if u is None or int(u.id)==int(ADMIN_ID): return
    uid=int(u.id)
    if mx.is_banned(uid): raise ApplicationHandlerStop
    now_t=time.time(); st=_flood.setdefault(uid,{'until':0,'strikes':0,'warned':0})
    if now_t<st['until']: raise ApplicationHandlerStop
    if not mx.allow('tg:%s'%uid,8,10):
        st['strikes']+=1; st['until']=now_t+(60 if st['strikes']<3 else 900)
        try:
            if update.effective_chat and now_t-st['warned']>30:
                st['warned']=now_t
                await context.bot.send_message(update.effective_chat.id,'⏳ Juda tez yozyapsiz. Iltimos, bir daqiqa kutib turing.')
        except Exception: pass
        raise ApplicationHandlerStop
    m=update.effective_message
    if m is not None and (m.photo or m.document) and not mx.allow('tgfile:%s'%uid,8,600):
        try: await m.reply_text('⏳ Fayl/rasm yuborish limiti: 10 daqiqada 8 tagacha. Biroz kuting.')
        except Exception: pass
        raise ApplicationHandlerStop

async def ban_cmd(update, context):
    if update.effective_user.id!=ADMIN_ID: return
    try: tid=int(context.args[0])
    except Exception: await update.message.reply_text('Foydalanish: /ban <user_id> [sabab]'); return
    if tid==ADMIN_ID: return
    mx.ban(tid,' '.join(context.args[1:]) or 'admin',ADMIN_ID); await update.message.reply_text(f'🚫 {tid} bloklandi.')

async def unban_cmd(update, context):
    if update.effective_user.id!=ADMIN_ID: return
    try: tid=int(context.args[0])
    except Exception: await update.message.reply_text('Foydalanish: /unban <user_id>'); return
    mx.unban(tid); await update.message.reply_text(f'✅ {tid} blokdan chiqarildi.')

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


async def configure_miniapp(application):
    global BOT_USERNAME
    try:
        if not BOT_USERNAME: BOT_USERNAME = (await application.bot.get_me()).username or ""
    except Exception:
        logger.exception("bot username aniqlanmadi")
    if miniapp_web_url():
        try:
            await application.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Milliy sertifikat", web_app=WebAppInfo(url=miniapp_web_url())))
            logger.info("Mini App menu button configured: %s", MINIAPP_URL)
        except Exception:
            logger.exception("Mini App menu button setup failed")

def main():
    init_db()
    init_national_db()
    mx.init_extra_db()
    mx.award_loop(TELEGRAM_BOT_TOKEN,ADMIN_ID,log=logging.warning)
    start_backup_loop()
    init_prep_db()
    threading.Thread(target=start_health,daemon=True).start()
    app=Application.builder().token(TELEGRAM_BOT_TOKEN).concurrent_updates(20).post_init(configure_miniapp).build()
    app.add_handler(TypeHandler(Update,spam_guard),group=-1)
    app.add_handler(CommandHandler("backup",backup_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.CaptionRegex(r"^/restore"),restore_cmd))
    app.add_handler(CommandHandler("ban",ban_cmd))
    app.add_handler(CommandHandler("unban",unban_cmd))
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("new",new_cmd))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CommandHandler(["admin", "panel"], admin_cmd))
    app.add_handler(CallbackQueryHandler(subscription_callback, pattern="^check_subscription$"))
    app.add_handler(CallbackQueryHandler(evaluation_method_callback, pattern="^(eval_ai|eval_expert|expert_agree|expert_back)$"))
    app.add_handler(CallbackQueryHandler(result_format_callback, pattern="^result_(image|text)$"))
    app.add_handler(CallbackQueryHandler(mini_test_callback, pattern="^minians_[0-9]+_[0-9]+$"))
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
