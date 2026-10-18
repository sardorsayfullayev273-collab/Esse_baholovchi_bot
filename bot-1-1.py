from urllib.parse import quote, urlparse, unquote, parse_qsl, parse_qs
import os
try:   # v68: xotira — glibc arena soni 2 ta (standartda oqim sonicha ko'payib, RSS ni shishiradi)
    import ctypes as _ctypes_early; _ctypes_early.CDLL("libc.so.6").mallopt(-8, 2)
except Exception: pass
import re
import csv
import io
import json
import sqlite3
import asyncio
import hashlib
import hmac, secrets
import time
import urllib.request
import logging
import threading
import random
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, BadRequestError
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, MenuButtonWebApp, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, PreCheckoutQueryHandler, ContextTypes, filters, TypeHandler, ApplicationHandlerStop
import mini_extra as mx
import manual_pay as mp
try:
    import pay_nudge
except ImportError:   # v72: pay_nudge.py bo'lmasa bot baribir ishlaydi (eslatma tsikli o'chiriladi)
    pay_nudge = None
import simple_tests as st_
import books_store as bk_
import qrich as qr_
import test_results as tr_
import growth_tests as gt_
import teacher_pro as tp_
import ai_cost as ac_
import mock_mod as mk_
import learn_hub as lh_
import mashq_seed as ms_
try:
    from result_blue import make_result_blue, errors_text_chunks
    try:
        from result_blue import collect_errors
    except Exception:
        collect_errors = None
except Exception:  # rasm moduli bo'lmasa eski rasm ishlaydi
    make_result_blue = None
    errors_text_chunks = None
import html as _html

# Milliy sertifikat testi — mavjud esse/dictionary/growth manbalariga tegmaydigan qo'shimcha modul
from national_certificate import (pending_set, pending_get, pending_clear, parse_manual_essay, init_national_db, init_prep_db, get_test, list_tests, create_test, grade as grade_national, level_for, save_attempt, has_attempt as national_has_attempt, split_alts, cert_hold, cert_pending_list, cert_mark_issued, latest_essay_check, essay_for_test, diagnostic_result, set_setting, setting, NATIONAL_ADMIN_ID, combined_diagnostic_score, create_prep_resource, list_prep_resources, list_all_prep_resources)

# ============================================================
# CONFIG
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
AUDIT_MODEL = os.getenv("AUDIT_MODEL", "").strip() or MODEL   # ixtiyoriy: xato auditorlari uchun arzonroq model (standart: MODEL bilan bir xil)
SCORING_VERSION = "fair-v7-local-special"
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
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "4"))
MAX_PDF_RENDER_DIM = int(os.getenv("MAX_PDF_RENDER_DIM", "1200"))
MAX_PDF_JPEG_QUALITY = int(os.getenv("MAX_PDF_JPEG_QUALITY", "78"))
PDF_PROCESS_TIMEOUT = int(os.getenv("PDF_PROCESS_TIMEOUT", "150"))
# Majburiy kanal obunasi
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "@milliysertifikat_ona_tili1")
GROWTH_PRICE_STARS = mp.GROWTH_STARS  # standart 150 ⭐ (Render: GROWTH_PRICE_STARS)
# --- Tejamkorlik rejimi: kunlik bepul limit + Stars paketi
FREE_ESSAY_DAILY = int(os.getenv("FREE_ESSAY_DAILY", "3"))      # v45: botda JAMI (bir martalik) bepul esse tekshiruvi, kunlik EMAS
PACK_ESSAYS = int(os.getenv("PACK_ESSAYS", "3"))                # bitta paketdagi tekshiruvlar soni
PACK_STARS = int(os.getenv("PACK_STARS", "50"))                 # bitta paket narxi (Telegram Stars)
MIN_ESSAY_WORDS = int(os.getenv("MIN_ESSAY_WORDS", "40"))       # bundan qisqa matn AI'ga yuborilmaydi
MAX_ESSAY_WORDS = int(os.getenv("MAX_ESSAY_WORDS", "1500"))     # bundan uzun matn AI'ga yuborilmaydi
MAX_ESSAY_IMAGES = int(os.getenv("MAX_ESSAY_IMAGES", "4"))      # bitta essedagi rasmlar soni
MAX_IMAGE_FILE_MB = float(os.getenv("MAX_IMAGE_FILE_MB", "12")) # rasm-fayl hajmi chegarasi
MAX_IMAGE_SIDE = int(os.getenv("MAX_IMAGE_SIDE", "1280"))       # rasmning uzun tomoni (px)
GROWTH_DAYS = 30
REQUIRED_CHANNEL_URL = os.getenv("REQUIRED_CHANNEL_URL", "https://t.me/milliysertifikat_ona_tili1")
APP_VERSION = "v76"
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

_JSON_FMT_OK = True

def responses_create_json(**kwargs):
    """OpenAI chaqiruvi + token/narxni hisoblagichga yozish (_feature: xarajat turi)."""
    feature = kwargs.pop('_feature', None)
    resp = _responses_create_json_raw(**kwargs)
    ac_.record_response(resp, kwargs.get('model'), feature)
    return resp

def _responses_create_json_raw(**kwargs):
    """Responses API chaqiruvi: javob sintaksisi to'g'ri JSON bo'lishini talab qiladi (qayta urinishlar kamayadi).
    Model/SDK buni qabul qilmasa, avvalgi usulga (formatsiz) o'tadi."""
    global _JSON_FMT_OK
    if _JSON_FMT_OK:
        try:
            return client.responses.create(**kwargs, text={"format": {"type": "json_object"}})
        except BadRequestError as e:
            msg = str(e).lower()
            if not ("json_object" in msg or "text.format" in msg or "text_format" in msg):
                raise  # boshqa sabab (masalan rasm xatosi) — oddiy xato sifatida ko'tariladi
            if "unsupported" in msg or "not supported" in msg:
                _JSON_FMT_OK = False  # model bu rejimni bilmaydi: keyingi chaqiruvlar ham formatsiz
            logger.warning("json_object rejimi rad etildi, shu chaqiruv formatsiz takrorlanadi: %s", str(e)[:200])
        except TypeError:
            _JSON_FMT_OK = False  # eski SDK 'text' parametrini bilmaydi
    return client.responses.create(**kwargs)

async def openai_json(input_payload, max_output_tokens=12000, feature=None):
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
            if feature: kwargs["_feature"] = feature
            response = await asyncio.to_thread(responses_create_json, **kwargs)
            raw = clean_json(response.output_text)
            if not raw:
                raise ValueError("OpenAI javobi bo'sh.")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("OpenAI JSON obyekti qaytarmadi.")
            return data
        except RateLimitError as e:
            last_error = e
            _m = str(e)
            logger.warning("OpenAI rate limit, retry %s/3: %s", attempt + 1, _m[:300])   # v66: sababi logda ko'rinsin
            if "insufficient_quota" in _m or getattr(e, "code", None) == "insufficient_quota":
                # Hisobda mablag'/kvota tugagan: qayta urinishning foydasi yo'q
                raise RuntimeError("OpenAI hisobida mablag‘ yoki kvota tugagan (insufficient_quota). platform.openai.com → Billing ni tekshiring.") from e
            if attempt < 2:
                _w = 0.0
                try: _w = float((getattr(e, "response", None).headers or {}).get("retry-after") or 0)
                except Exception: _w = 0.0
                await asyncio.sleep(min(60.0, max(_w, 12.0 * (attempt + 1))))   # v66: 12s, 24s (avval 2s, 4s edi — juda qisqa)
        except (AuthenticationError, BadRequestError) as e:
            logger.exception("OpenAI request rejected")
            raise
        except (json.JSONDecodeError, ValueError) as e:
            # Javob buzuq/bo'sh: har bir qayta urinish to'liq narx turadi, shuning uchun faqat 1 marta qayta uriniladi.
            last_error = e
            logger.warning("OpenAI JSON problem, retry %s/2: %s", attempt + 1, type(e).__name__)
            if attempt >= 1:
                break
            await asyncio.sleep(1)
        except APIError as e:
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

def admin_err(uid, e):
    """v66: faqat ADMIN ga xatoning haqiqiy sababi ko'rsatiladi (oddiy foydalanuvchi hech narsa ko'rmaydi)."""
    try:
        if int(uid) != ADMIN_ID: return ""
        root = e.__cause__ or e
        return f"\n\n🛠 (faqat admin) {type(e).__name__}: {str(e)[:160]}" + (f"\n↳ {type(root).__name__}: {str(root)[:200]}" if root is not e else "")
    except Exception:
        return ""

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

class _ClosingConn(sqlite3.Connection):
    """`with db() as c:` oxirida commit/rollback qiladi va ulanishni YOPADI (xotira oqishi oldini oladi)."""
    def __exit__(self, et, ev, tb):
        try:
            return super().__exit__(et, ev, tb)
        finally:
            try: self.close()
            except Exception: pass

def db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False, factory=_ClosingConn)
    conn.row_factory = sqlite3.Row
    try: conn.execute('PRAGMA cache_size=-1500')
    except Exception: pass
    return conn

try: mk_.configure(db, DB_LOCK)
except Exception: pass

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
    try: gt_.touch(user_id)
    except Exception: logger.exception('streak touch failed')
    try:
        inviter = mp.reward_inviter(user_id)
        if inviter:
            threading.Thread(target=_notify_inviter, args=(inviter,), daemon=True).start()
    except Exception:
        logger.exception("referral reward failed")

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
CACHE_MAX = 40
USER_LOCKS = {}
USER_LOCKS_GUARD = asyncio.Lock()

# ============================================================
# GLOBAL EVALUATION QUEUE
# 10-20 users can submit essays at once without freezing the bot.
# Users do not see queue numbers or internal concurrency details.
# Only a small number of expensive AI evaluations run simultaneously;
# the rest wait silently while Telegram remains responsive.
# ============================================================
MAX_PARALLEL_EVALUATIONS = max(1, int(os.getenv("MAX_PARALLEL_EVALUATIONS", "1")))
EVALUATION_SEMAPHORE = asyncio.Semaphore(MAX_PARALLEL_EVALUATIONS)
EVALUATION_WAIT_TIMEOUT = max(60, int(os.getenv("EVALUATION_WAIT_TIMEOUT", "900")))

def cache_key(*parts):
    return hashlib.sha256("\n---\n".join(str(x or "") for x in parts).encode()).hexdigest()

def _mem_put(k, v):
    if len(CACHE) >= CACHE_MAX:
        CACHE.pop(next(iter(CACHE)))
    CACHE[k] = v

def cache_get(k):
    """Natijani avval xotiradan, topilmasa doimiy keshdan (SQLite) oladi. Har safar yangi nusxa qaytaradi."""
    with CACHE_LOCK:
        sv = CACHE.get(k)
    if sv is None:
        try:
            sv = mx.cache_load(k)
        except Exception:
            logger.warning("persistent cache read failed")
            sv = None
        if sv is not None:
            with CACHE_LOCK:
                _mem_put(k, sv)
    if sv is None:
        return None
    try:
        return json.loads(sv)
    except Exception:
        return None

def cache_put(k, v):
    try:
        sv = json.dumps(v, ensure_ascii=False)
    except Exception:
        return
    with CACHE_LOCK:
        _mem_put(k, sv)
    try:
        mx.cache_store(k, sv)
    except Exception:
        logger.warning("persistent cache write failed")

def _norm_key_text(t):
    """Kesh kaliti uchun: ortiqcha bo'shliq/qator farqlari bir xil esse hisoblanadi (mazmun o'zgarmaydi)."""
    t = str(t or "").replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t\u00a0]+", " ", t)
    t = re.sub(r" ?\n ?", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def key_text(topic, essay):
    return cache_key("text", _norm_key_text(topic), _norm_key_text(essay), MODEL, SCORING_VERSION)

def key_image(topic, image_bytes):
    return cache_key("image", topic, hashlib.sha256(image_bytes).hexdigest(), MODEL, SCORING_VERSION)

def key_images(topic, images):
    digest = hashlib.sha256()
    for b in images:
        digest.update(hashlib.sha256(b).digest())
    return cache_key("images", topic, digest.hexdigest(), MODEL, SCORING_VERSION)

def key_pdf(topic, pdf_bytes):
    return cache_key("pdf", topic, hashlib.sha256(pdf_bytes).hexdigest(), MODEL, SCORING_VERSION)

def shrink_image(data):
    """Katta rasmni (ayniqsa 'fayl' sifatida yuborilganini) MAX_IMAGE_SIDE ga kichraytiradi: AI uchun token tejaladi.
    XOTIRA: 48 MP rasm to'liq ochilsa ~170 MB RAM ketadi (Render limitini oshiradi). Shuning uchun JPEG'ni
    draft() bilan eng boshidan kichik o'lchamda dekodlaymiz va ortiqcha nusxa yaratmaymiz."""
    im = None
    try:
        from PIL import ImageOps
        im = Image.open(io.BytesIO(data))
        fmt = im.format
        orient = (im.getexif() or {}).get(274, 1)
        w, h = im.size
        if w * h > 120_000_000:           # haddan tashqari katta rasm (dekompressiya bombasi)
            logger.warning("shrink_image: rasm juda katta (%sx%s)", w, h)
            raise ValueError("rasm juda katta")
        if max(w, h) <= MAX_IMAGE_SIDE and len(data) <= 1_500_000 and fmt == "JPEG" and orient in (1, None):
            return data
        if fmt == "JPEG":
            im.draft("RGB", (MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))   # 1/2, 1/4, 1/8 masshtabda dekodlash
        im = ImageOps.exif_transpose(im, in_place=False) if orient not in (1, None) else im
        if im.mode != "RGB":
            im = im.convert("RGB")
        if max(im.size) > MAX_IMAGE_SIDE:
            im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        im.save(out, "JPEG", quality=82, optimize=True)
        small = out.getvalue()
        return small if len(small) < len(data) or max(w, h) > MAX_IMAGE_SIDE else data
    except Exception:
        logger.warning("shrink_image failed; original ishlatiladi")
        return data
    finally:
        try:
            if im is not None: im.close()
        except Exception: pass

async def user_lock(user_id):
    async with USER_LOCKS_GUARD:
        if user_id not in USER_LOCKS:
            if len(USER_LOCKS) > 2000:
                for _k in [k for k, l in USER_LOCKS.items() if not l.locked()][:1500]: USER_LOCKS.pop(_k, None)
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
    "🔒 Botdan foydalanish uchun avval majburiy kanal(lar)ga a’zo bo‘ling.\n\n"
    "📢 Barcha kanallarga a’zo bo‘lgach, «✅ A’zolikni tekshirish» tugmasini bosing."
)

def extra_channels():
    """Admin qo'shgan qo'shimcha majburiy kanallar: [{'chat':..., 'url':..., 'title':...}]."""
    try:
        v = json.loads(mp.setting("extra_channels", "[]") or "[]")
        return [x for x in v if isinstance(x, dict) and x.get("chat") and x.get("url")]
    except Exception:
        return []

def save_extra_channels(lst):
    mp.set_setting("extra_channels", json.dumps(lst, ensure_ascii=False))

def subscription_keyboard():
    rows = [[InlineKeyboardButton("📢 Kanalga a’zo bo‘lish", url=REQUIRED_CHANNEL_URL)]]
    for i, ch in enumerate(extra_channels(), 2):
        rows.append([InlineKeyboardButton(f"📢 {ch.get('title') or ('Kanal '+str(i))}", url=ch["url"])])
    rows.append([InlineKeyboardButton("✅ A’zolikni tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(rows)

async def _member_of(user_id, bot, chat):
    member = await bot.get_chat_member(chat_id=chat, user_id=user_id)
    status = getattr(member, "status", "")
    if status in ("member", "administrator", "creator"):
        return True
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return False

async def is_subscribed(user_id, bot):
    try:
        if not await _member_of(user_id, bot, REQUIRED_CHANNEL):
            return False
    except Exception:
        logger.exception("Subscription check failed for user=%s channel=%s", user_id, REQUIRED_CHANNEL)
        return False
    for ch in extra_channels():
        try:
            if not await _member_of(user_id, bot, ch["chat"]):
                return False
        except Exception:
            # Bot kanalda admin emas / kanal topilmasa — foydalanuvchini qulflab qo'ymaymiz
            logger.exception("Extra channel check failed channel=%s", ch.get("chat"))
    return True

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
        await grant_invitee_bonus(context.bot, user.id)
    else:
        await query.answer("❌ Siz hali barcha kanallarga a’zo bo‘lmagansiz.", show_alert=True)

async def evaluation_method_callback(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    if user_id != ADMIN_ID and not await is_subscribed(user_id, context.bot):
        await query.answer("❌ Avval kanalga a’zo bo‘ling.", show_alert=True)
        return
    await query.answer()

    if query.data == "eval_ai":
        _ma = MOCK_AI_ACTIVE.get(user_id)   # v76: mock rejimi faqat mock mavzusi uchun
        if _ma:
            try:
                from national_certificate import norm_topic as _nt
                if _nt(context.user_data.get("topic", "")) != _nt((get_test(_ma) or {}).get("essay_topic", "")): MOCK_AI_ACTIVE.pop(user_id, None)
            except Exception: MOCK_AI_ACTIVE.pop(user_id, None)
        context.user_data["method"] = "ai"
        context.user_data["stage"] = "essay_ai"
        await query.message.reply_text(
            "🤖 Sun’iy intellekt yordamida baholash tanlandi.\n\n"
            f"🎁 Dastlabki {FREE_ESSAY_DAILY} ta esse tekshiruvi BEPUL (bir martalik).\n"
            f"💳 Bepul {FREE_ESSAY_DAILY} tadan keyin: {PACK_ESSAYS} ta esse — {PACK_STARS} ⭐ yoki {mp.fmt_uzs(mp.PACKS['p3']['uzs'])} so‘m (karta orqali). Esse tekshirish jarayoni to‘liq pullik sun’iy intellekt (AI) orqali amalga oshiriladi.\n\n"
            "📌 Endi esseingizni yuboring:\n"
            "• matn ko‘rinishida; yoki\n"
            "• rasm(lar) ko‘rinishida; yoki\n"
            "• PDF ko‘rinishida.\n\n"
            f"💡 Yozma matn yoki matnli PDF eng tez va aniq tekshiriladi. Qo‘lyozma uchun ko‘pi bilan {MAX_ESSAY_IMAGES} ta aniq rasm yuboring.\n"
            f"✂️ Matn hajmi: {MIN_ESSAY_WORDS}–{MAX_ESSAY_WORDS} so‘z.\n\n"
            "⚠️ Juda ko‘p talabgorlar foydalanayotgan paytda saytda uzilishlar kuzatilishi mumkin. "
            "Bunday holatda biroz kutib, qayta urinib ko‘ring.\n\n"
            f"📄 PDF uchun: maksimal {MAX_PDF_SIZE_MB:g} MB va {MAX_PDF_PAGES} sahifa.",
            reply_markup=MAIN_KEYBOARD
        )
        return

    if query.data == "eval_expert":
        context.user_data["stage"] = "method"
        await expert_offer_flow(query.message, query.from_user.id)   # v57: avtomatik oqim — admin bilan yozishish yo'q
        return

    if query.data == "expert_back":
        context.user_data["stage"] = "method"
        await query.message.reply_text("⬅️ Baholash usulini tanlang:", reply_markup=EVALUATION_METHOD_KEYBOARD)
        return

    if query.data == "expert_agree":
        context.user_data["stage"] = "method"
        await expert_offer_flow(query.message, query.from_user.id)
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
        await send_result_gated(query.message, result, mode, query.from_user.id)
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

ESSE_VIDEO_N = 0   # v73: Esse -> Videodars videolari book_id=0 ostida saqlanadi (alohida bo'lim, hech bir esse elementiga bog'liq emas)
def _esse_video_open():
    try: return mp.setting('esse_video_open','0')=='1'
    except Exception: return False

def growth_premium_active(user_id):
    exp=growth_premium_until(user_id)
    if not exp: return False
    from datetime import timezone
    return exp > datetime.now(timezone.utc)

def growth_premium_text(user_id):
    exp=growth_premium_until(user_id)
    if not exp or not growth_premium_active(user_id): return "🔒 Premium faol emas"
    return f"✅ Premium faol\n⏳ Amal qilish muddati: {exp.strftime('%d.%m.%Y %H:%M')} UTC"

def growth_gate_keyboard(uid=None):
    d=mp.student_discount(uid); tag=f" (−{d}%)" if d else ""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐ Stars — {mp.price_stars(uid,'growth','growth')} ⭐{tag}",callback_data="buy_growth")],
        [InlineKeyboardButton(f"💳 Karta orqali — {mp.fmt_uzs(mp.price_uzs(uid,'growth','growth'))} so‘m{tag}",callback_data="cardpay_growth_growth")],
        [InlineKeyboardButton("📄 Shartlar",callback_data="growth_terms")],
    ])
GROWTH_GATE_KEYBOARD=growth_gate_keyboard()

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
        await context.bot.send_invoice(chat_id=uid,title="Esseni o‘stirish — 30 kun",description=f"{GROWTH_DAYS} kun: kuniga {AI_PREMIUM_DAILY} ta AI esse mashqi/dalil + {mp.PREMIUM_BONUS_ESSAYS} ta esse tekshiruvi sovg‘a + namunaviy esselar kutubxonasi.",payload=f"growth_premium_30d:{uid}",provider_token="",currency="XTR",prices=[LabeledPrice("Esseni o‘stirish — 30 kun",mp.price_stars(uid,"growth","growth"))],start_parameter="growth-premium-30d")
    except Exception:
        logger.exception("growth invoice error"); await query.message.reply_text("⚠️ To‘lov oynasini ochishda xatolik yuz berdi. Keyinroq qayta urinib ko‘ring.",reply_markup=MAIN_KEYBOARD)

async def growth_terms_callback(update,context):
    query=update.callback_query; await query.answer()
    await query.message.reply_text("📄 PREMIUM SHARTLARI\n\n• Premium 30 kun amal qiladi.\n"+f"• Narx: {GROWTH_PRICE_STARS} Telegram Stars.\n• Premium: kuniga {AI_PREMIUM_DAILY} ta AI mashq/dalil (oddiy foydalanuvchida {AI_FREE_DAILY} ta).\n• Sovg‘a: {mp.PREMIUM_BONUS_ESSAYS} ta esse tekshiruvi (muddatsiz saqlanadi).\n• Namunaviy esselar kutubxonasi (Mini App → Esse) Premium muddati davomida ochiq.\n• To‘lov va xarid bo‘yicha yordam: /paysupport\n• Xarid qilishdan oldin ushbu shartlarni o‘qib chiqing.",reply_markup=growth_gate_keyboard(uid))

async def precheckout_growth(update,context):
    q=update.pre_checkout_query; payload=q.invoice_payload or ""
    if not payload.startswith("growth_premium_30d:"):
        await q.answer(ok=False,error_message="Buyurtma ma’lumoti noto‘g‘ri."); return
    try: uid=int(payload.split(":",1)[1])
    except Exception: await q.answer(ok=False,error_message="Buyurtma ma’lumoti noto‘g‘ri."); return
    if uid!=q.from_user.id or q.currency!="XTR" or q.total_amount not in (GROWTH_PRICE_STARS, mp.price_stars(uid,"growth","growth")):
        await q.answer(ok=False,error_message="To‘lov ma’lumoti mos kelmaydi."); return
    await q.answer(ok=True)

def grant_growth_premium(uid, days, charge_id, stars):
    """Premiumni `days` kunga beradi/uzaytiradi. Muddat tugash vaqtini qaytaradi."""
    from datetime import timezone,timedelta
    now=datetime.now(timezone.utc); old=growth_premium_until(uid); start=max(now,old) if old and old>now else now; exp=start+timedelta(days=days)
    with DB_LOCK, db() as c:
        c.execute("""INSERT INTO growth_premium(user_id,expires_at,payment_charge_id,stars,purchased_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET expires_at=excluded.expires_at,payment_charge_id=excluded.payment_charge_id,stars=excluded.stars,purchased_at=excluded.purchased_at""",(uid,exp.isoformat().replace("+00:00","Z"),str(charge_id),int(stars),now.isoformat().replace("+00:00","Z"))); c.commit()
    return exp

async def successful_payment_growth(update,context):
    payment=update.message.successful_payment; payload=payment.invoice_payload or ""
    if not payload.startswith("growth_premium_30d:"): return
    try: uid=int(payload.split(":",1)[1])
    except Exception: uid=update.effective_user.id
    if uid!=update.effective_user.id: return
    cid=payment.telegram_payment_charge_id
    if not mx.claim_charge(cid,uid,"growth",payment.total_amount):
        await update.message.reply_text("ℹ️ Bu to‘lov avval hisobga olingan."); return
    try:
        exp=grant_growth_premium(uid,GROWTH_DAYS,cid,payment.total_amount)
    except Exception:
        mx.release_charge(cid); raise
    try: mp.record_commission(uid,f"stars:{cid}",mp.price_uzs(uid,"growth","growth"))
    except Exception: logger.exception("ustoz komissiyasi (premium)")
    try: mp.add_credits(uid,"essay",mp.PREMIUM_BONUS_ESSAYS)
    except Exception: logger.exception("premium bonus esse")
    await update.message.reply_text("🎉 PREMIUM FAOLLASHDI!\n\n"+f"🌟 {GROWTH_DAYS} kun davomida kuniga {AI_PREMIUM_DAILY} ta AI mashq/dalil.\n🎁 Sovg‘a: {mp.PREMIUM_BONUS_ESSAYS} ta esse tekshiruvi hisobingizga qo‘shildi.\n"+f"⏳ Amal qilish muddati: {exp.strftime('%d.%m.%Y %H:%M')} UTC",reply_markup=MAIN_KEYBOARD)

async def terms_cmd(update,context):
    pk="\n".join(f"  – {pack_label(p)}: {p['stars']} ⭐ yoki {mp.fmt_uzs(p['uzs'])} so‘m" for p in mp.PACKS.values())
    await update.message.reply_text("📄 SHARTLAR\n\n"+f"• Esse tekshirish: jami {FREE_ESSAY_DAILY} ta bepul (bir martalik). Keyin paketlar:\n{pk}\n"+"• To‘lov: plastik karta orqali (to‘lovdan so‘ng xizmat avtomatik ochiladi) yoki Telegram Stars.\n• Sotib olingan tekshiruvlar muddatsiz saqlanadi; texnik xato bo‘lsa tekshiruv hisobga qaytariladi.\n"+f"• Premium ({GROWTH_DAYS} kun): {GROWTH_PRICE_STARS} ⭐ yoki {mp.fmt_uzs(mp.GROWTH_UZS)} so‘m — kuniga {AI_PREMIUM_DAILY} ta AI mashq/dalil.\n• Raqamli xizmatlar uchun mo‘ljallangan; to‘lov qaytarilmaydi, xato bo‘lsa /paysupport orqali murojaat qiling.\nYordam: /paysupport")

async def paysupport_cmd(update,context):
    await update.message.reply_text("🆘 TO‘LOV YORDAMI\n\n"+f"Esse paketlari: {PACK_ESSAYS} ta — {PACK_STARS} ⭐ / {mp.fmt_uzs(mp.PACKS['p3']['uzs'])} so‘m va boshqalar (/balans).\nPremium: {GROWTH_PRICE_STARS} ⭐ yoki {mp.fmt_uzs(mp.GROWTH_UZS)} so‘m / {GROWTH_DAYS} kun.\nKarta orqali to‘lov qilgan bo‘lsangiz va 1 soat ichida tasdiqlanmasa, chekni adminga yuboring.\nTo‘lov amalga oshgan bo‘lsa-yu hisobingizda ko‘rinmasa (/balans), admin bilan bog‘laning.\n👨‍💼 @{ADMIN_USERNAME}")

# ============================================================
# 💳 KVOTA VA STARS PAKETLARI (tejamkorlik rejimi)
#   • 'essay' — botda esse tekshirish: kuniga FREE_ESSAY_DAILY ta bepul, keyin PACK_ESSAYS ta = PACK_STARS ⭐
#   • 'tool'  — esse mashqi va dalil topish (Mini App va bot): bepul limit ai_limit_for(), keyin xuddi shu paket
# ============================================================
POOL_NAMES = {"essay": "esse tekshiruvi", "tool": "AI mashq/dalil"}

def free_limit_for(uid, kind):
    return FREE_ESSAY_DAILY if kind == "essay" else ai_limit_for(uid)

def pack_info():
    return {"stars": PACK_STARS, "size": PACK_ESSAYS}

def essay_free_warning(uid):
    """Esse yuborishdan OLDIN: bepul tekshiruvlar haqida ogohlantirish."""
    if int(uid) == int(ADMIN_ID): return ""
    try: st = mx.quota_status(uid, "essay", FREE_ESSAY_DAILY)
    except Exception: return ""
    if st["free_left"] > 0:
        t = f"🎁 Sizda {st['free_left']}/{FREE_ESSAY_DAILY} ta BEPUL esse tekshiruvi bor.\n"
        if st["free_left"] == 1:
            t += "⚠️ Bu oxirgi bepul tekshiruv: natijada faqat ball ko‘rsatiladi, xatolar tahlilini ochish uchun 1 ta pullik tekshiruv kerak.\n"
        return t + "\n"
    if st.get("pass_until") or st["credits"] > 0:
        return f"💼 Hisobingizda: {st['credits']} ta pullik tekshiruv" + (f" + 7 kunlik paket (bugun {st['pass_left']} ta)" if st.get("pass_until") else "") + ".\n\n"
    return f"🔒 {FREE_ESSAY_DAILY} ta bepul tekshiruv tugagan. Davom etish uchun paket kerak (/paket).\n\n"

def pack_label(p):
    """Paket nomi: '3 ta' yoki '7 kun cheksiz'."""
    return f"{p['days']} kun (kuniga {mp.PASS_DAILY_CAP} tagacha)" if p.get("days") else f"{p['size']} ta"

def offer_line(uid):
    fo = mp.first_offer(uid)
    if not fo: return ""
    return f"⏰ Birinchi xarid uchun −{fo[0]}% chegirma: {fo[1].strftime('%d.%m %H:%M')} gacha (Toshkent vaqti)!\n"

def paywall_text(uid, kind):
    st = mx.quota_status(uid, kind, free_limit_for(uid, kind))
    if kind == "essay":
        head = f"🔒 Sizning {FREE_ESSAY_DAILY} ta bepul esse tekshiruvingiz tugadi."
        what = "esse tekshiruvi"
    else:
        head = "🔒 Bugungi bepul AI limitingiz (esse mashqi va dalil topish) tugadi."
        what = "AI mashq/dalil"
    lines = "\n".join(f"👉 {pack_label(p)} {what if not p.get('days') else ''} — {p['stars']} ⭐ yoki {mp.fmt_uzs(p['uzs'])} so‘m".replace("  —"," —") + (f" (−{p['discount']}%)" if p['discount'] else "") for p in mp.packs_for(uid, kind))
    return (head + "\n\n"
            "💡 Nega pullik? Esse tekshirish jarayoni to‘liq pullik sun’iy intellekt (AI) tizimida amalga oshiriladi: "
            "har bir esse bir necha bosqichda tekshiriladi va xarajat har safar bizdan ketadi. "
            "Shu sababli bepul limitdan keyin:\n"
            f"{lines}\n\n"
            "✅ Sotib olingan tekshiruvlar muddatsiz saqlanadi.\n"
            + ("🕛 Bepul limit har kuni 00:00 da (Toshkent vaqti) yangilanadi.\n" if kind != "essay" else "") +
            "🎁 Do‘stlaringizni taklif qilsangiz — bepul tekshiruv olasiz.\n"
            + offer_line(uid) +
            f"💼 Hisobingizda: {st['credits']} ta pullik tekshiruv.")

def pack_keyboard(kind, uid=None):
    rows = []
    for p in mp.packs_for(uid, kind):
        pid = p["id"]; nm = f"{p['days']} kun" if p.get("days") else f"{p['size']} ta"
        rows.append([
            InlineKeyboardButton(f"⭐ {nm} — {p['stars']}", callback_data=f"buy_pack_{kind}_{pid}"),
            InlineKeyboardButton(f"💳 {nm} — {mp.fmt_uzs(p['uzs'])} so‘m", callback_data=f"cardpay_{kind}_{pid}"),
        ])
    rows.append([InlineKeyboardButton("🎁 Do‘st taklif qilib bepul olish", callback_data="ref_info")])
    return InlineKeyboardMarkup(rows)

async def send_paywall(message, uid, kind):
    await message.reply_text(paywall_text(uid, kind), reply_markup=pack_keyboard(kind, uid))

MOCK_AI_ACTIVE = {}   # v76: uid -> mock test kodi (mock uchun bepul AI esse tekshiruvi rejimi)

async def quota_gate(message, uid, kind, cache_k=None):
    """AI chaqirishdan oldin ruxsatni tekshiradi va 1 birlik yechadi.
    Qaytaradi: 'admin' | 'cache' | 'free' | 'paid' — davom etish mumkin; None — limit tugagan (paywall ko'rsatildi).
    Keshdan beriladigan natija AI chaqirmaydi, shuning uchun limit sarflanmaydi."""
    if int(uid) == int(ADMIN_ID):
        return "admin"
    if kind == "essay" and int(uid) in MOCK_AI_ACTIVE:   # v76: MOCK — 1 martalik bepul AI (kesh ishlatilmaydi: huquq har doim sarflanadi)
        _mc = MOCK_AI_ACTIVE[int(uid)]
        if mk_.ai_free_use(_mc, uid): return "mockfree"
        await message.reply_text("🤖 Mock uchun bepul AI tekshiruvi 1 martalik edi va allaqachon ishlatilgan (yoki bugungi aksiya tugagan).\n\n"
                                 f"👨‍🏫 Esse balli uchun ekspert tekshiruvi: {mp.fmt_uzs(mp.MOCK_EXPERT_UZS)} so‘m. Mini App → Mock → «Ekspertga yuborish».", reply_markup=MAIN_KEYBOARD)
        return None
    if cache_k and cache_get(cache_k) is not None:
        return "cache"
    src = mx.quota_consume(uid, kind, free_limit_for(uid, kind))
    if src is None:
        await send_paywall(message, uid, kind)
        return None
    return src

def quota_refund(uid, kind, src):
    """Tekshiruv xato bilan tugasa limitni qaytaradi."""
    if src == "mockfree":   # v76
        try: mk_.ai_free_refund(MOCK_AI_ACTIVE.get(int(uid), ""), uid)
        except Exception: logger.exception("mock ai refund failed")
        return
    if src in ("free", "pass", "paid"):
        try:
            mx.quota_refund(uid, kind, src)
        except Exception:
            logger.exception("quota refund failed")

def precheck_essay_text(text):
    """AI'ga yuborishdan oldin bepul tekshiruv. Xato matnini qaytaradi, yaroqli bo'lsa None."""
    n = word_count(text)
    if n < MIN_ESSAY_WORDS:
        return f"⚠️ Esse juda qisqa ({n} so‘z). Kamida {MIN_ESSAY_WORDS} so‘z yozing. Bu yuborish limitingizdan yechilmadi."
    if n > MAX_ESSAY_WORDS:
        return f"⚠️ Esse juda uzun ({n} so‘z). Ko‘pi bilan {MAX_ESSAY_WORDS} so‘z yuboring. Bu yuborish limitingizdan yechilmadi."
    return None

async def buy_pack_callback(update, context):
    query = update.callback_query; await query.answer(); uid = query.from_user.id
    m = re.match(r"^buy_pack_(essay|tool)(?:_([pw][0-9]+))?$", query.data or "")
    if not m: return
    kind = m.group(1); pid = m.group(2) or "p3"
    if pid not in mp.PACKS or not mp.valid_plan(kind, pid): return
    if uid != ADMIN_ID and not await is_subscribed(uid, context.bot):
        await query.message.reply_text(SUBSCRIPTION_TEXT, reply_markup=subscription_keyboard()); return
    title = mp.plan_title(kind, pid)
    try:
        await context.bot.send_invoice(
            chat_id=uid, title=title,
            description="Esse tekshirish jarayoni to‘liq pullik sun’iy intellekt (AI) orqali amalga oshiriladi. Paket muddatsiz saqlanadi; bepul kunlik limitdan keyin ishlatiladi.",
            payload=f"pack:{kind}:{uid}:{pid}", provider_token="", currency="XTR",
            prices=[LabeledPrice(title, mp.price_stars(uid, kind, pid))], start_parameter=f"pack-{kind}-{pid}")
    except Exception:
        logger.exception("pack invoice error")
        await query.message.reply_text("⚠️ To‘lov oynasini ochishda xatolik yuz berdi. Keyinroq qayta urinib ko‘ring.", reply_markup=MAIN_KEYBOARD)

def parse_pack_payload(payload):
    """'pack:<kind>:<uid>[:<plan>]' -> (kind, uid, plan) yoki None. Eski to'lovlar (plan yo'q) 'p3' deb olinadi."""
    try:
        parts = (payload or "").split(":")
        if parts[0] != "pack" or len(parts) not in (3, 4): return None
        kind = parts[1]; uid = int(parts[2]); pid = parts[3] if len(parts) == 4 else "p3"
        if kind not in ("essay", "tool") or pid not in mp.PACKS or not mp.valid_plan(kind, pid): return None
        return kind, uid, pid
    except Exception:
        return None


# ================= v57: AVTOMATIK KARTA TO'LOVI (Telegram Payments: Click / Payme / Uzum) =================
def _auto_invoice_args(uid, kind, plan):
    amount = int(mp.price_uzs(uid, kind, plan)) * 100          # UZS: tiyin
    full = mp.plan_title(kind, plan)
    title = full if len(full) <= 32 else full[:31] + "…"
    return {"title": title, "description": (full + "\nTo‘lovdan so‘ng xizmat avtomatik ochiladi.")[:250],
            "payload": mp.invoice_payload(uid, kind, plan), "amount": amount, "prices": [{"label": title, "amount": amount}]}

async def precheckout_auto(update, context):
    q = update.pre_checkout_query; parsed = mp.parse_invoice_payload(q.invoice_payload)
    ok = False
    try:
        if parsed and parsed[2] == q.from_user.id and q.currency == "UZS" and mp.valid_plan(parsed[0], parsed[1]):
            ok = q.total_amount in (int(mp.price_uzs(parsed[2], parsed[0], parsed[1])) * 100, int(mp.plan_amount_uzs(parsed[0], parsed[1])) * 100)
    except Exception:
        logger.exception("precheckout_auto")
    if ok: await q.answer(ok=True)
    else: await q.answer(ok=False, error_message="To‘lov ma’lumoti mos kelmaydi. Qayta urinib ko‘ring.")

async def successful_payment_auto(update, context):
    p = update.message.successful_payment; parsed = mp.parse_invoice_payload(p.invoice_payload)
    if not parsed or parsed[2] != update.effective_user.id or p.currency != "UZS": return
    kind, plan, uid = parsed; amount = int(p.total_amount) // 100
    st, oid = mp.create_auto_order(uid, kind, plan, amount, p.telegram_payment_charge_id)
    if st == "dup": return
    order = mp.get_order(oid)
    if mp.claim_grant(oid):
        try:
            await _grant_manual_order(order, context)
        except Exception:
            logger.exception("avto-to'lov: xizmat ochilmadi oid=%s", oid)
            mp.release_grant(oid)   # v58: card_grant_loop keyingi aylanishda qayta urinadi (to'lagan odam xizmatsiz qolmaydi)
            try: await update.message.reply_text("✅ To‘lovingiz qabul qilindi. Xizmat bir necha daqiqada avtomatik ochiladi. Ochilmasa: /paysupport", reply_markup=MAIN_KEYBOARD)
            except Exception: pass
            try: await context.bot.send_message(ADMIN_ID, f"⚠️ AVTO-TO‘LOV: xizmat ochilmadi (qayta uriniladi). buyurtma #{oid}, id {uid}, {mp.plan_title(kind, plan)}, charge {p.telegram_payment_charge_id}")
            except Exception: pass
    try: mp.record_commission(uid, f"auto:{p.telegram_payment_charge_id}", amount)
    except Exception: logger.exception("ustoz komissiyasi (avto)")
    try: await context.bot.send_message(ADMIN_ID, f"💳 Avto-to‘lov #{oid}: {mp.plan_title(kind, plan)} — {mp.fmt_uzs(amount)} so‘m (id {uid})")
    except Exception: pass

async def send_auto_invoice(bot, uid, kind, plan):
    a = _auto_invoice_args(uid, kind, plan)
    await bot.send_invoice(chat_id=uid, title=a["title"], description=a["description"], payload=a["payload"], provider_token=mp.PROVIDER_TOKEN,
                           currency="UZS", prices=[LabeledPrice(a["title"], a["amount"])], start_parameter=f"pay-{kind}-{plan}"[:60])

async def precheckout_unified(update, context):
    q = update.pre_checkout_query; payload = q.invoice_payload or ""
    if payload.startswith("uzs|"):
        return await precheckout_auto(update, context)
    if payload.startswith("growth_premium_30d:"):
        return await precheckout_growth(update, context)
    parsed = parse_pack_payload(payload)
    if not parsed or parsed[1] != q.from_user.id or q.currency != "XTR" or q.total_amount not in (mp.PACKS[parsed[2]]["stars"], mp.price_stars(parsed[1], parsed[0], parsed[2])):
        await q.answer(ok=False, error_message="To‘lov ma’lumoti mos kelmaydi."); return
    await q.answer(ok=True)

async def successful_payment_unified(update, context):
    payment = update.message.successful_payment; payload = payment.invoice_payload or ""
    if payload.startswith("uzs|"):
        return await successful_payment_auto(update, context)
    if payload.startswith("growth_premium_30d:"):
        return await successful_payment_growth(update, context)
    parsed = parse_pack_payload(payload)
    if not parsed: return
    kind, uid, pid = parsed
    if uid != update.effective_user.id: return
    size = mp.PACKS[pid]["size"]
    if mp.PACKS[pid].get("days"):
        is_new = mx.grant_pass(uid, payment.telegram_payment_charge_id, payment.total_amount, mp.PACKS[pid]["days"])
        if not is_new:
            await update.message.reply_text("ℹ️ Bu to‘lov avval hisobga olingan."); return
        try: mp.record_commission(uid,f"stars:{payment.telegram_payment_charge_id}",mp.price_uzs(uid,kind,pid))
        except Exception: logger.exception("ustoz komissiyasi (stars)")
        await update.message.reply_text(pass_activated_text(uid), reply_markup=MAIN_KEYBOARD); return
    is_new = mx.grant_pack(uid, kind, payment.telegram_payment_charge_id, payment.total_amount, size)
    st = mx.quota_status(uid, kind, free_limit_for(uid, kind))
    if not is_new:
        await update.message.reply_text("ℹ️ Bu to‘lov avval hisobga olingan."); return
    try: mp.record_commission(uid,f"stars:{payment.telegram_payment_charge_id}",mp.price_uzs(uid,kind,pid))
    except Exception: logger.exception("ustoz komissiyasi (stars)")
    what = "esse tekshiruvi" if kind == "essay" else "AI mashq/dalil"
    again = "Endi esseni qayta yuboring." if kind == "essay" else "Endi mashqni yoki dalil so‘rovini qayta yuboring."
    await update.message.reply_text(f"🎉 To‘lov qabul qilindi!\n\n➕ {size} ta {what} qo‘shildi.\n💼 Hisobingizda: {st['credits']} ta pullik tekshiruv.\n\n{again}", reply_markup=MAIN_KEYBOARD)

def pass_activated_text(uid):
    pu = mx.pass_until(uid)
    until = datetime.fromisoformat(pu.rstrip("Z")).replace(tzinfo=timezone.utc).astimezone(mx.TZ).strftime("%d.%m.%Y %H:%M") if pu else "-"
    return (f"🎉 {mp.PACKS['w7']['days']} KUNLIK PAKET FAOLLASHDI!\n\n✍️ Kuniga {mp.PASS_DAILY_CAP} tagacha esse tekshirtirishingiz mumkin.\n"
            f"⏳ Amal qilish muddati: {until} (Toshkent vaqti)\n\nEsseni shu chatga yuboring.")

async def balance_cmd(update, context):
    upsert_user(update.effective_user); uid = update.effective_user.id
    e = mx.quota_status(uid, "essay", FREE_ESSAY_DAILY); t = mx.quota_status(uid, "tool", ai_limit_for(uid))
    await update.message.reply_text(
        "💼 HISOBIM\n\n"
        f"✍️ Esse tekshirish: bepul {e['free_left']}/{FREE_ESSAY_DAILY} qoldi • pullik {e['credits']} ta\n"
        + (f"🗓 7 kunlik paket: bugun {e['pass_left']}/{mp.PASS_DAILY_CAP} qoldi\n" if e.get('pass_until') else "") +
        f"🧠 Esse mashqi/dalil: bugun bepul {t['free_left']}/{ai_limit_for(uid)} qoldi • pullik {t['credits']} ta\n\n"
        f"💳 Paketlar: /paket  •  🌟 Premium: /premium  •  🎁 Do‘st taklif qilish: /taklif",
        reply_markup=MAIN_KEYBOARD)

def _latest_check(uid):
    """(id, result dict) — foydalanuvchining oxirgi saqlangan natijasi yoki (None, None)."""
    with DB_LOCK, db() as c:
        row = c.execute("SELECT id, result_json FROM checks WHERE user_id=? AND result_json IS NOT NULL ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    if not row: return None, None
    try: return int(row[0]), json.loads(row[1])
    except Exception: return int(row[0]), None

def essay_result_locked(uid):
    """3-bepul esse natijasi (batafsil tahlil) yopiqmi? Yopiq bo'lsa True."""
    if int(uid) == int(ADMIN_ID): return False
    st = mx.lock_get(uid)
    if not st: return False
    if st[0] == "armed":
        cid, _ = _latest_check(uid)
        if cid is None: return False
        mx.lock_set(uid, "locked", cid)
    return True   # pullik tekshiruv ishlatilguncha yoki «Ochish» bosilguncha yopiq (keshdan qayta yuborib ochib bo'lmaydi)

def _check_by_id(uid, cid):
    with DB_LOCK, db() as c:
        row = c.execute("SELECT result_json FROM checks WHERE id=? AND user_id=?", (int(cid), uid)).fetchone()
    try: return json.loads(row[0]) if row and row[0] else None
    except Exception: return None

def locked_keyboard(uid):
    rows = [[InlineKeyboardButton("🔓 Batafsil tahlilni ochish", callback_data="unlock_full")]]
    rows += pack_keyboard("essay", uid).inline_keyboard
    return InlineKeyboardMarkup(rows)

async def send_locked_result(message, data, uid):
    total = authoritative_total24(data); normalize_summary_score(data)
    n_err = 0
    if collect_errors is not None:
        try: n_err = len(list(collect_errors(data)))
        except Exception: n_err = 0
    txt = (f"📊 NATIJANGIZ: {total:g}/24  •  75 ballik: {to_75(total)}/75\n\n"
           + (f"❌ Esseda {n_err} ta xato topildi.\n" if n_err else "")
           + "🔒 Xatolar ro‘yxati, mezonlar bo‘yicha izoh va tavsiyalar yopiq.\n\n"
           "🔓 Ochish uchun 1 ta pullik tekshiruv kerak (paket sotib olsangiz, tugmani qayta bosing).\n\n"
           + offer_line(uid) +
           "💡 Bu sizning oxirgi bepul esseingiz edi.")
    await message.reply_text(txt, reply_markup=locked_keyboard(uid))

async def send_result_gated(message, data, mode, uid):
    if essay_result_locked(uid):
        await send_locked_result(message, data, uid)
    else:
        await send_result(message, data, mode)

async def unlock_callback(update, context):
    q = update.callback_query; uid = q.from_user.id; await q.answer()
    st = mx.lock_get(uid)
    cid = int(st[1]) if st else 0
    data = _check_by_id(uid, cid) if cid else _latest_check(uid)[1]
    if not st or data is None:
        await q.message.reply_text("ℹ️ Bu natija allaqachon ochiq. Ko‘rish: /natija", reply_markup=MAIN_KEYBOARD); return
    src = mx.quota_consume_paid_only(uid)
    if src is None:
        await q.message.reply_text("🔒 Batafsil tahlilni ochish uchun paket kerak.\n\n" + offer_line(uid) + "To‘lovdan keyin «🔓 Batafsil tahlilni ochish» tugmasini qayta bosing.",
                                   reply_markup=pack_keyboard("essay", uid)); return
    mx.lock_release(uid)
    try:
        await send_result(q.message, data, get_result_mode(uid))
    except Exception:
        logger.exception("unlock send error")
        mx.quota_refund(uid, "essay", src); mx.lock_set(uid, "locked", cid)
        await q.message.reply_text("⚠️ Natijani ko‘rsatib bo‘lmadi. Hisobingizdan yechilmadi, qayta urinib ko‘ring.", reply_markup=MAIN_KEYBOARD)

async def last_result_cmd(update, context):
    """Oxirgi natijani bazadan qayta ko'rsatadi — AI chaqirilmaydi, limit sarflanmaydi."""
    upsert_user(update.effective_user)
    if not await require_subscription(update, context): return
    uid = update.effective_user.id
    with DB_LOCK, db() as c:
        row = c.execute("SELECT result_json FROM checks WHERE user_id=? AND result_json IS NOT NULL ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
    if not row:
        await update.message.reply_text("Hozircha saqlangan natija yo‘q.", reply_markup=MAIN_KEYBOARD); return
    try:
        data = json.loads(row[0])
        await send_result_gated(update.message, data, get_result_mode(uid), uid)
    except Exception:
        logger.exception("last result error")
        await update.message.reply_text("⚠️ Natijani ko‘rsatib bo‘lmadi.", reply_markup=MAIN_KEYBOARD)

# ============================================================
# KEYBOARDS
# ============================================================
APP_BUTTON_TEXT = "🎓 Milliy sertifikat"
LEGACY_MOVED = {"📊 Statistika","🌱 Esseni o‘stirish","🧠 Xatolarim","📚 Xatolar ustida ishlash","📚 Xato darsi","🧪 Mini test","🎯 Shaxsiy rejam",
                "🔄 Esseni yaxshilash","✍️ Esse yozish mashqi","🗂️ Esse rejasini tuzish","💡 Dalil topib berish","📊 Chuqur statistika","⬅️ Asosiy menyu","🎓 Milliy sertifikat"}
REF_BUTTON_TEXT = "🎁 Do‘st taklif qilish"
BALANCE_BUTTON_TEXT = "💼 Hisobim"
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["✍️ Esse tekshirish", APP_BUTTON_TEXT],
    [REF_BUTTON_TEXT, BALANCE_BUTTON_TEXT],
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
_WORD_RE = re.compile(r"[^\W_][^\s]*", flags=re.UNICODE)

def word_count(text):
    """Faqat harf yoki raqam bor so'zlar sanaladi (yolg'iz '-', '—', '...' so'z emas)."""
    return len(_WORD_RE.findall(text or ""))

class TranscriptionIncomplete(ValueError):
    """Qo'lyozma rasmdan matn to'liq o'qilmadi (100 so'zdan kam)."""

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

def coerce_and_validate_ai(data):
    """AI javobini tartibga soladi (ballni 0,5 qadamga keltiradi) va 12 mezon to'liqligini tekshiradi."""
    scores = data.get("scores")
    if not isinstance(scores, list):
        raise ValueError("scores ro'yxati yo'q")
    for x in scores:
        if not isinstance(x, dict):
            raise ValueError("mezon obyekti noto'g'ri")
        try:
            x["criterion"] = int(x.get("criterion"))
            x["score"] = clamp_half(x.get("score", 0) or 0)
        except Exception:
            raise ValueError("mezon yoki ball noto'g'ri")
        if not isinstance(x.get("errors"), list):
            x["errors"] = []
    validate_ai(data)
    return data

async def openai_eval_json(payload):
    """openai_json + javob tuzilishini tekshirish; buzuq bo'lsa 1 marta qayta so'raydi."""
    last = None
    for attempt in range(2):
        data = await openai_json(payload)
        try:
            return coerce_and_validate_ai(data)
        except ValueError as e:
            last = e
            logger.warning("AI javobi yaroqsiz (%s), urinish %s/2", e, attempt + 1)
    raise last

def apply_deterministic_rules(data, essay, topic, handwritten=False):
    data.setdefault("status", "normal")

    # "xo‘sh" is a valid discourse marker in an introduction and must not
    # be counted as a stylistic/word-choice error merely because it occurs
    # repeatedly. Remove any AI-generated error entry that targets this word.
    for item in data.get("scores", []) or []:
        c = int(item.get("criterion", 0) or 0)
        errs = item.get("errors") or []
        if c in (10, 12):
            kept = []
            removed = 0
            for err in errs:
                if isinstance(err, dict) and _norm_apos(err.get("wrong")) in {"xo'sh", "xosh"}:
                    removed += 1
                    continue
                kept.append(err)
            item["errors"] = kept
            if removed:
                item["error_count"] = max(0, int(item.get("error_count", 0) or 0) - removed)
                item["reason"] = str(item.get("reason", "")).replace("xo‘sh", "").replace("xo'sh", "").strip()

    data["word_count"] = word_count(essay)
    by = {int(x["criterion"]): x for x in data["scores"]}

    # Qo'shimcha jazolar bitta mezondan ko'pi bilan 1 ball (6-mezon: 1,5) ayirishi mumkin.
    _pen = {}
    _cap = {6: 1.5}
    def deduct(c, amt):
        room = _cap.get(c, 1.0) - _pen.get(c, 0.0)
        a = min(float(amt), room)
        if a > 0:
            set_score(by[c], by[c]["score"] - a)
            _pen[c] = _pen.get(c, 0.0) + a

    flags = data.get("flags") or {}
    data["flags"] = flags
    def _num(key):
        v = flags.get(key)
        if v is None or v == "":
            return None
        try:
            return int(v)
        except Exception:
            return None

    # Sheva so'zi 12-mezonda xato sifatida BIR marta sanaladi (qo'shimcha -1 yo'q).
    dialect_count = _num("dialect_count") or 0
    err_count = {}
    for c in (5,7,8,9,10,12):
        n = max(0, int(by[c].get("error_count", 0) or 0))
        if c == 12 and dialect_count > n:
            n = dialect_count
        err_count[c] = n
        by[c]["error_count"] = n
        set_score(by[c], score_errors(n))

    rep = max(0, int(by[6].get("repetition_count", 0) or 0))
    coherent = bool(by[6].get("coherence_intact", True))
    by[6]["repetition_count"] = rep
    by[6]["coherence_intact"] = coherent
    if rep == 0 and coherent: set_score(by[6], 2)
    elif rep <= 2 and coherent: set_score(by[6], 1.5)
    elif 3 <= rep <= 4 and not coherent: set_score(by[6], 1)
    elif 5 <= rep <= 6 and not coherent: set_score(by[6], 0.5)
    elif rep >= 7 and not coherent: set_score(by[6], 0)
    else: set_score(by[6], 1.0 if rep >= 3 else 1.5)

    # Xulosa yo'q / bo'lim to'liq emas -> 4 va 5 (jami 1 ball gacha).
    if flags.get("missing_conclusion") or flags.get("incomplete_section"):
        deduct(4, 1); deduct(5, 1)
        by[4].setdefault("examples", []).append("XULOSA TO'LIQ EMAS")

    # Kirish mavzuni so'zma-so'z takrorlagan.
    if flags.get("intro_copies_topic"):
        deduct(4, 1); deduct(5, 1)
        by[4].setdefault("examples", []).append("KIRISH MAVZUNI SO'ZMA-SO'Z TAKRORLAGAN")

    if flags.get("paragraph_structure_problem"):
        deduct(5, 0.5)

    if flags.get("artistic_poetic_style"):
        if by[1]["score"] > 1:
            set_score(by[1], 1)
        by[1]["reason"] = (str(by[1].get("reason", "")) + " Publitsistik uslubdan chetlashilgan.").strip()

    # Sheva: 12-mezonda xato sifatida sanaldi; 1-mezonga yengil ta'sir.
    if dialect_count > 0:
        deduct(1, 0.5)

    # 2-mezon: bayroq berilmagan bo'lsa jazolamaymiz (None != 0).
    left_args = _num("view1_reason_count")
    right_args = _num("view2_reason_count")
    if (left_args is not None and left_args < 2) or (right_args is not None and right_args < 2):
        if by[2]["score"] > 1:
            set_score(by[2], 1)
        by[2]["reason"] = (str(by[2].get("reason", "")) + " Asosiy qarashlardan kamida birida 2 ta aniq sabab/argument yetarli emas.").strip()

    # 3-mezon: nizomning H bandi — ikki qarash ham dalillangan bo'lsa 2.
    evidence = str(flags.get("evidence_status", "none"))
    s1 = _num("strong_evidence_view1_count"); s2 = _num("strong_evidence_view2_count")
    evidence_strong = bool(flags.get("evidence_strong", False))
    counts_ok = (s1 is None or s1 >= 1) and (s2 is None or s2 >= 1)
    if evidence == "both" and (evidence_strong or (s1 is not None and s2 is not None and s1 >= 1 and s2 >= 1)) and counts_ok:
        set_score(by[3], 2)
    elif evidence in {"both", "one"}:
        set_score(by[3], 1.5)
        by[3]["reason"] = (str(by[3].get("reason", "")) +
            " Dalillar to‘liq ikkala qarash uchun yetarlicha aniq va mustahkam emas.").strip()
    elif evidence == "irrelevant":
        deduct(3, 1); deduct(6, 0.5)
    elif evidence == "none" and by[3]["score"] > 1:
        # Dalil umuman yo'q: «faqat bittasi dalillangan» 1,5 ball bo'lgani uchun, dalilsiz esse 1 balldan oshmaydi.
        set_score(by[3], 1)
        by[3]["reason"] = (str(by[3].get("reason", "")) + " Qarashlarning birortasi ham aniq dalil bilan mustahkamlanmagan.").strip()

    off_sent = _num("off_topic_sentence_count") or 0
    if off_sent > 0:
        deduct(6, 0.5 * off_sent)

    bad_idiom = _num("bad_proverb_idiom_count") or 0
    if bad_idiom > 0:
        deduct(6, 0.5 * bad_idiom); deduct(11, 0.5 * bad_idiom)

    # 11-mezon: 2 ball kam beriladi (kamida 2 ta aniq misol + model tasdig'i).
    lexical_examples = data.get("lexical_examples") or []
    lexical_strong = bool(flags.get("lexical_strong", False))
    if by[11]["score"] >= 2 and not (lexical_strong and len(lexical_examples) >= 2):
        set_score(by[11], 1.5)
        by[11]["reason"] = "Leksik xilma-xillik yaxshi, ammo 2 ball uchun kamida 2 ta aniq va o‘rinli leksik birlik dalillanishi kerak."

    # Xulosa pozitsiyasi: faqat aniq buzilish jazolanadi ("unknown" — jazo emas).
    conclusion = str(flags.get("conclusion_position", "view1"))
    if conclusion in {"both_correct", "off_topic"} and flags.get("conclusion_present", True):
        deduct(4, 1); deduct(6, 1)
        by[4]["reason"] = (str(by[4].get("reason", "")) + " Xulosada ikki qarashdan birini aniq qo'llab-quvvatlash talabi bajarilmagan.").strip()

    if flags.get("personal_opinion_in_intro_or_body"):
        deduct(1, 0.5); deduct(6, 0.5)

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
    if data["word_count"] < 100 and handwritten:
        raise TranscriptionIncomplete(
            f"rasmdan faqat {data['word_count']} ta so'z o'qildi (100 dan kam)"
        )
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
Har bir obyekt: {"wrong":"...","correct":"...","explanation":"...","context":"...","type":"imlo|punktuatsiya|qo'shimcha|so'z"}
"type" xatoning HAQIQIY turini bildiradi: tinish belgisi -> punktuatsiya; yozilish -> imlo; kelishik/egalik/ko'plik/fe'l shakli -> qo'shimcha; so'z tanlash/ma'no -> so'z.
"""

ADJUDICATOR_PROMPT = r"""
Siz FINAL XATO NAZORATCHISISIZ. Quyida esse va auditorlar topgan NOMZOD xatolar beriladi.
Maqsad: adolatli baho. Soxta xato o'quvchiga zarar qiladi.
Sizning vazifangiz:
A) Har bir nomzod xatoni original matn bilan tekshirish: "wrong" matnda aynan bor-yo'qligini va norma bo'yicha rostdan xato ekanini aniqlash.
B) Haqiqiy bo'lmagan, taxminiy, did/uslub afzalligiga asoslangan yoki matnda topilmaydigan xatolarni OLIB TASHLANG. Shubha bo'lsa — olib tashlang.
C) YANGI xato QO'SHMANG. Faqat berilgan nomzodlarni tasdiqlang yoki rad eting.
D) Bir xil xatoning takroriy yozuvlarini (turlicha ta'rif bilan) BIR marta qoldiring.
E) "xo'sh"/"xo‘sh"ni mavjudligi yoki takrori sababli xato qilmang.
F) Qo'lyozmadan transkripsiya qilingan matnda gumon qilingan xato o'qish xatosiga o'xshasa (masalan, harfi noaniq so'z) — rad eting.
G) Har bir qolgan xatoda "type" (imlo|punktuatsiya|qo'shimcha|so'z) ni to'g'ri qo'ying va aniq KONTEKST bering.

Faqat JSON qaytaring:
{"errors":{"7":[],"8":[],"9":[],"10":[]}}
Har bir obyekt: {"wrong":"...","correct":"...","explanation":"...","context":"...","type":"..."}
"""

async def _call_error_auditor(system_prompt, essay):
    try:
        r = await asyncio.to_thread(responses_create_json, _feature='xato_auditi', model=AUDIT_MODEL, input=[
            {"role":"system","content":system_prompt},
            {"role":"user","content":str(essay or "")}
        ])
        raw = clean_json(r.output_text)
        obj = json.loads(raw)
        errs = obj.get("errors") or {}
        return {str(k): (v if isinstance(v, list) else []) for k,v in errs.items()}
    except Exception:
        logger.exception("Error audit failed")
        return None

def first_pass_errors(data):
    """Asosiy baholash chaqiruvi topgan 7-10 mezon xatolari (adjudikatorga nomzod sifatida beriladi)."""
    out = {"7": [], "8": [], "9": [], "10": []}
    for item in (data.get("scores") or []):
        try:
            c = int(item.get("criterion", 0))
        except Exception:
            continue
        if c in (7, 8, 9, 10):
            out[str(c)].extend(e for e in (item.get("errors") or []) if isinstance(e, dict))
    return out

async def audit_text_errors(essay, first_pass=None, extra_coro=None):
    """Ikki mustaqil auditor (+ ixtiyoriy rasm auditori) + asosiy chaqiruv xatolari -> BITTA adjudikator.
    Natija None bo'lsa audit butunlay ishlamagan (chaqiruvchi asosiy chaqiruv xatolarini saqlaydi)."""
    tasks = [
        _call_error_auditor(AUDIT_SCHEMA_PROMPT, essay),
        _call_error_auditor(AUDIT_SCHEMA_PROMPT + "\nSiz boshqa auditorning natijasini ko'rmaysiz. Mustaqil qayta tekshiring.", essay),
    ]
    if extra_coro is not None:
        tasks.append(extra_coro)
    results = await asyncio.gather(*tasks)
    ok = [r for r in results if r is not None]
    if not ok:
        return None
    candidates = {"7": [], "8": [], "9": [], "10": []}
    for src in ok + ([first_pass] if first_pass else []):
        for c in candidates:
            candidates[c].extend(src.get(c, []) or [])
    if not any(candidates.values()):
        return {"7": [], "8": [], "9": [], "10": []}   # nomzod xato yo'q: hakam YANGI xato qo'sha olmaydi (prompt C bandi) -> chaqiruv bekor
    return await adjudicate_errors(essay, candidates, fallback=consensus_errors(ok + ([first_pass] if first_pass else [])))

async def audit_image_errors(images):
    import base64
    content = [{"type":"input_text","text":AUDIT_SCHEMA_PROMPT + "\nBu rasmlar bitta esse. Qo'lda yozilgan matnni bevosita ko'rib, xatolarni aniqlang. Transkripsiya xatosiga emas, rasmdagi haqiqiy yozuvga tayaning."}]
    for b in images:
        b64 = base64.b64encode(b).decode()
        content.append({"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"})
    try:
        r = await asyncio.to_thread(responses_create_json, _feature='xato_auditi', model=MODEL, input=[{"role":"system","content":AUDIT_SCHEMA_PROMPT},{"role":"user","content":content}])
        raw = clean_json(r.output_text)
        obj = json.loads(raw)
        errs = obj.get("errors") or {}
        return {str(k): (v if isinstance(v, list) else []) for k,v in errs.items()}
    except Exception:
        logger.exception("Image error audit failed")
        return None

def _err_sig(e):
    return (_norm_apos(e.get("wrong")), _norm_apos(e.get("correct")))

def consensus_errors(sources):
    """Adjudikator ishlamaganda: xatoni kamida 2 ta manba (yoki bitta manba bo'lsa, o'sha) tasdiqlagan bo'lsa qoldiradi."""
    srcs = [s for s in sources if s]
    need = 2 if len(srcs) >= 2 else 1
    out = {"7": [], "8": [], "9": [], "10": []}
    for c in out:
        votes, first = {}, {}
        for src in srcs:
            seen = set()
            for e in (src.get(c, []) or []):
                if not isinstance(e, dict):
                    continue
                sig = _err_sig(e)
                if sig in seen:
                    continue
                seen.add(sig)
                votes[sig] = votes.get(sig, 0) + 1
                first.setdefault(sig, e)
        out[c] = [first[sig] for sig, v in votes.items() if v >= need]
    return out

async def adjudicate_errors(essay, candidates, fallback=None):
    payload = {
        "essay": str(essay or ""),
        "candidate_errors": candidates,
    }
    try:
        r = await asyncio.to_thread(responses_create_json, _feature='xato_auditi', model=MODEL, input=[
            {"role":"system","content":ADJUDICATOR_PROMPT},
            {"role":"user","content":json.dumps(payload, ensure_ascii=False)}
        ])
        raw = clean_json(r.output_text)
        obj = json.loads(raw)
        errs = obj.get("errors") or {}
        return {str(k): (v if isinstance(v, list) else []) for k,v in errs.items()}
    except Exception:
        logger.exception("Final error adjudication failed")
        # Filtrlanmagan nomzodlar o'quvchiga soxta xato bo'lib tushmasin: konsensus.
        return fallback if fallback is not None else candidates

def _norm_apos(v):
    """YAGONA normalizator: kichik harf, barcha apostroflar (‘ ’ ʻ ʼ ` ´) -> ', ortiqcha bo'shliqlar yo'q."""
    t = str(v or "").strip().lower()
    for ch in "‘’ʻʼ`´": t = t.replace(ch, "'")
    return re.sub(r"\s+", " ", t)

def _route_error_to_criterion(original_criterion, err):
    """Xatoni uning haqiqiy turiga mos mezonga yo'naltiradi.
    Tartib: (1) faqat tinish belgisi farqi -> 8; (2) auditor bergan 'type'; (3) aniq so'z-iboralar."""
    c = int(original_criterion)
    wrong = str(err.get("wrong") or "").strip()
    correct = str(err.get("correct") or "").strip()

    def strip_punct(v):
        return re.sub(r"[^\w\s]", "", str(v or "").lower(), flags=re.UNICODE).split()
    if wrong and correct and wrong != correct and strip_punct(wrong) == strip_punct(correct):
        return 8

    t = _norm_apos(err.get("type"))
    if t.startswith("punkt") or t.startswith("tinish"):
        return 8
    if t.startswith("imlo"):
        return 7
    if t.startswith("qo'shimcha") or t.startswith("qoshimcha"):
        return 9
    if t.startswith("so'z") or t.startswith("soz"):
        return 10

    blob = _norm_apos(f"{err.get('explanation') or ''} {err.get('context') or ''}")
    def has(*pats):
        return any(re.search(p, blob) for p in pats)

    if has(r"\bvergul", r"\bnuqta\b", r"ikki nuqta", r"nuqtali vergul", r"\btire\b", r"qo'sh tirnoq",
           r"\btinish belgi", r"\bishoraviy", r"punktuats"):
        return 8
    if has(r"\bkelishik", r"\begalik", r"\bko'plik", r"\baffiks", r"fe'l shakl", r"grammatik shakl",
           r"qo'shimchasi\b", r"qo'shimchani\b"):
        return 9
    if has(r"\bimlo\b", r"\bimloviy", r"yozilishi", r"harf xato", r"\bapostrof"):
        return 7
    if has(r"so'z qo'llash", r"so'z tanlash", r"ma'nosiga mos", r"mazmunga mos", r"\buslubiy", r"\bleksik"):
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
            norm = _norm_apos
            # Bir xil xato (turlicha kontekst/izoh bilan) bir marta; mezonlararo ham takrorlanmaydi.
            sig = (norm(e.get("wrong")), norm(e.get("correct")))
            if sig in seen:
                continue
            seen.add(sig)
            e.pop("criterion", None)
            final[key].append(e)
    return final

def merge_audit_errors(data, *audits):
    """Adjudikator natijasi (asosiy chaqiruv xatolarini ham ko'rib chiqqan) yagona manba.
    Audit butunlay ishlamasa (hammasi None) — asosiy chaqiruv xatolari saqlanadi."""
    by = {int(x["criterion"]): x for x in data.get("scores", [])}
    valid = [a for a in audits if a is not None]

    combined_by = {"7": [], "8": [], "9": [], "10": []}
    if valid:
        for audit in valid:
            for c in combined_by:
                combined_by[c].extend(list((audit or {}).get(c, []) or []))
    else:
        for c in (7, 8, 9, 10):
            combined_by[str(c)].extend(list(by.get(c, {}).get("errors") or []))
    routed_all = _reclassify_errors(combined_by)

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
            if c == 10 and _norm_apos(wrong) in {"xo'sh", "xosh"}:
                continue
            if _norm_apos(wrong) == _norm_apos(correct):
                continue  # "xato"ning to'g'risi o'zi bilan bir xil — haqiqiy xato emas
            cleaned.append({"wrong": wrong, "correct": correct, "explanation": explanation, "context": context})
        item["errors"] = cleaned
        item["error_count"] = len(cleaned)
        item["reason"] = f"Aniqlangan xatolar: {len(cleaned)} ta." if cleaned else "Aniq xato topilmadi."
    return data

def local_special_result(topic, essay):
    """AI chaqirmasdan aniq hal bo'ladigan holatlar: esse bo'sh, to'liq kirill yoki 100 so'zdan kam.
    Natija qoidalar bo'yicha belgilangan (0 yoki 2 ball), shuning uchun AI ham, foydalanuvchi limiti ham sarflanmaydi.
    None — oddiy esse (AI kerak)."""
    essay = essay or ""
    if essay.strip() and not full_cyrillic(essay) and word_count(essay) >= 100:
        return None
    data = {"scores": [{"criterion": i, "name": CRITERION_NAMES.get(i, f"Mezon {i}"), "score": 0, "error_count": 0, "errors": [], "reason": ""}
                       for i in range(1, 13)], "flags": {}, "summary": "", "improvements": []}
    data = apply_deterministic_rules(data, essay, topic)
    data["_local_special"] = True
    data["_topic"] = str(topic or "")[:300]
    return data

def _needs_error_audit(data, essay):
    """Xato auditi (2 auditor + hakam) faqat ball xatolarga bog'liq bo'lsa kerak. Maxsus holatlarda (bo'sh, kirill, <100 so'z,
    faqat kirish, mavzuga mos emas, ko'chirma) yakuniy ball qat'iy belgilangan — audit bekor xarajat."""
    if not (essay or "").strip() or full_cyrillic(essay) or word_count(essay) < 100: return False
    return not any(data.get(k) for k in ("only_introduction", "off_topic", "copied_with_evidence"))

async def evaluate_text(topic, essay):
    loc = local_special_result(topic, essay)
    if loc is not None: return loc
    k = key_text(topic, essay)
    old = cache_get(k)
    if old: return old
    data = await openai_eval_json([{"role":"system","content":RUBRIC},{"role":"user","content":eval_schema_prompt(topic,essay)}])
    audit = await audit_text_errors(essay, first_pass_errors(data)) if _needs_error_audit(data, essay) else None
    data = merge_audit_errors(data, audit)
    data = apply_deterministic_rules(data, essay, topic)
    data["_topic"] = str(topic or "")[:300]
    cache_put(k, data)
    return data

async def evaluate_image(topic, image_bytes):
    k = key_image(topic, image_bytes)
    old = cache_get(k)
    if old: return old
    import base64
    image_bytes = await asyncio.to_thread(shrink_image, image_bytes)
    b64 = base64.b64encode(image_bytes).decode()
    prompt = eval_schema_prompt(topic, "[ESSENING MATNI RASMDAN O'QILADI]") + "\nRasmdagi qo'lda yozilgan matnni avval transcription maydonida to'liq yozing. Ko'rinmagan so'zni o'ylab topmang."
    payload = [{"role":"system","content":RUBRIC},{"role":"user","content":[
        {"type":"input_text","text":prompt},
        {"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"}
    ]}]
    data = await openai_eval_json(payload)
    transcription = str(data.get("transcription") or data.get("essay_text") or "")
    if not transcription:
        # Ask for transcription in the same response is preferred; if absent, use the available text field.
        transcription = str(data.get("text") or "")
    data["transcription"] = transcription
    audit_all = await audit_text_errors(transcription, first_pass_errors(data), audit_image_errors([image_bytes])) if _needs_error_audit(data, transcription) else None
    data = merge_audit_errors(data, audit_all)
    data = apply_deterministic_rules(data, transcription, topic, handwritten=True)
    data["_image_mode"] = True
    data["_topic"] = str(topic or "")[:300]
    cache_put(k, data)
    return data


async def evaluate_images(topic, images):
    """Bir nechta Telegram albom rasmini bitta esse sifatida tekshiradi."""
    import base64
    if not images:
        raise ValueError("Rasmlar topilmadi.")
    k = key_images(topic, images)
    old = cache_get(k)
    if old:
        return old
    images = [await asyncio.to_thread(shrink_image, b) for b in images]
    content = [{"type":"input_text","text": eval_schema_prompt(topic, "[ESSE BIR NECHTA RASMDA BERILGAN]") + "\nRasmlar ketma-ket bitta essega tegishli. Barcha rasmlardagi matnni tartib bilan to‘liq transcription qiling. Rasmlar orasidagi gaplarni o‘zingizcha qo‘shmang."}]
    for b in images:
        b64 = base64.b64encode(b).decode()
        content.append({"type":"input_image","image_url":f"data:image/jpeg;base64,{b64}"})
    data = await openai_eval_json([{"role":"system","content":RUBRIC},{"role":"user","content":content}])
    transcription = str(data.get("transcription") or data.get("essay_text") or data.get("text") or "")
    data["transcription"] = transcription
    audit_all = await audit_text_errors(transcription, first_pass_errors(data), audit_image_errors(images)) if _needs_error_audit(data, transcription) else None
    data = merge_audit_errors(data, audit_all)
    data = apply_deterministic_rules(data, transcription, topic, handwritten=True)
    data["_image_mode"] = True
    data["_image_count"] = len(images)
    data["_topic"] = str(topic or "")[:300]
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

    from pypdf import PdfReader   # v68: lazy import (xotira)
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

    k = key_pdf(topic, pdf_bytes)
    old = cache_get(k)
    if old:
        return old

    prepared = await asyncio.wait_for(
        asyncio.to_thread(_prepare_pdf_sync, pdf_bytes),
        timeout=PDF_PROCESS_TIMEOUT,
    )

    if prepared["kind"] == "text":
        _wc = word_count(prepared["payload"])
        if _wc < MIN_ESSAY_WORDS:
            raise ValueError(f"PDFdagi matn juda qisqa ({_wc} so‘z; kamida {MIN_ESSAY_WORDS} so‘z kerak)")
        if _wc > MAX_ESSAY_WORDS:
            raise ValueError(f"PDFdagi matn juda uzun ({_wc} so‘z; ko‘pi bilan {MAX_ESSAY_WORDS} so‘z)")
        data = await evaluate_text(topic, prepared["payload"])
    else:
        data = await evaluate_images(topic, prepared["payload"])

    data["_pdf_mode"] = True
    data["_pdf_pages"] = prepared["pages"]
    data["_topic"] = str(topic or "")[:300]
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
    if str(data.get("status", "")) == "special_case":
        lines += ["⚠️ " + str(data.get("special_reason") or "Esse baholashga yaroqsiz."),
                  "Maxsus holatda mezonlar bo‘yicha batafsil baho berilmaydi."]
        rows = []
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

def _chat_display_name(message):
    ch=getattr(message,"chat",None)
    n=getattr(ch,"full_name",None) or getattr(ch,"first_name",None) or getattr(ch,"title",None) or ""
    if not n and getattr(ch,"username",None): n="@"+ch.username
    return str(n)[:40]

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
        for i, chunk in enumerate(chunks):
            await message.reply_text(chunk, reply_markup=(share_keyboard(message.chat_id) if i == len(chunks)-1 else None))
        return
    img=None
    if make_result_blue is not None:
        try:
            _t75=to_75(total)
            img=await asyncio.to_thread(make_result_blue,data,total,_t75,level_for(_t75),
                                        _chat_display_name(message),str(data.get("_topic") or ""),None,BOT_USERNAME)
        except Exception:
            logger.exception("make_result_blue failed, eski rasmga qaytildi")
            img=None
    if img is None:
        img=await asyncio.to_thread(make_result_image,data)
    caption=(
        f"📊 {total:g}/24  •  75 ballik ekvivalent: {to_75(total)}/75"
        + disclaimer
    )
    await message.reply_photo(photo=InputFile(img,filename="esse_natijasi.jpg"),caption=caption[:1024],reply_markup=share_keyboard(message.chat_id))
    # Barcha xatolar rasm ortidan yozma xabarda (nusxalash mumkin, siqilmaydi).
    if errors_text_chunks is not None:
        try:
            for ch in errors_text_chunks(data):
                await message.reply_text(ch)
        except Exception:
            logger.exception("xatolar matni yuborilmadi")

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
        for e in errors[:12]:
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
            for err in (item.get('errors') or []):
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
    uid=update.effective_user.id
    existed=user_exists(uid)
    upsert_user(update.effective_user)
    context.user_data.clear()
    arg=(context.args[0] if getattr(context,"args",None) else "")
    ust_linked=False
    if arg.startswith("ref_"):
        try: mp.register_referral(uid,int(arg[4:]),is_new=not existed)
        except Exception: logger.exception("referral register failed")
    if arg.startswith("duel_"):
        try:
            _dp=arg[5:].split("_")
            if len(_dp)>=3 and _dp[2].isdigit():
                mp.register_referral(uid,int(_dp[2]),is_new=not existed)
                mx.game_ref_register(uid,int(_dp[2]),not existed,int(_dp[0]) if _dp[0].isdigit() else 0,int(_dp[1]) if _dp[1].isdigit() else -1)
        except Exception: logger.exception("duel referral failed")
    if arg.startswith("play_"):
        try:
            if arg[5:].isdigit():
                mp.register_referral(uid,int(arg[5:]),is_new=not existed)
                mx.game_ref_register(uid,int(arg[5:]),not existed)
        except Exception: logger.exception("play referral failed")
    if arg.startswith("ust_"):
        try: ust_linked=mp.register_teacher_student(uid,int(arg[4:]),is_new=not existed)
        except Exception: logger.exception("ustoz biriktirish xatosi")
    if not await require_subscription(update, context): return
    await grant_invitee_bonus(context.bot, uid)
    if ust_linked and mp.student_discount(uid):
        await update.message.reply_text(f"👩‍🏫 Siz ustoz havolasi orqali kirdingiz!\n\n🎁 Barcha paketlar va Premium uchun doimiy chegirma: −{mp.student_discount(uid)}%. Narxlar to‘lov oynasida avtomatik chegirma bilan chiqadi.")
    if arg=="topic":
        await send_daily_essay_practice(update.message, uid, context); return
    if arg.startswith("mockexpert_"):
        await mock_expert_flow(update.message, uid, arg[11:]); return
    if arg.startswith("mockai_"):
        await mock_ai_flow(update.message, uid, arg[7:], context); return
    if arg.startswith("essay_"):
        t=get_test(arg[6:])
        if t and uid != ADMIN_ID and mk_.is_mock_code(t["code"]):   # v76: mock esse mavzusi faqat Mock bo'limidagi 2 yo'l orqali
            await update.message.reply_text("📝 Mock esse mavzusi faqat Mini App → Mock bo‘limidagi ikki yo‘ldan biri bilan tekshiriladi: 🤖 bepul AI (1 martalik) yoki 👨‍🏫 ekspert.", reply_markup=MAIN_KEYBOARD); return
        if t and (t.get("essay_topic") or "").strip():
            context.user_data["topic"]=t["essay_topic"].strip(); context.user_data["stage"]="method"
            await update.message.reply_text(f"📝 Diagnostik test ({t['code']}) esse mavzusi:\n\n«{t['essay_topic']}»\n\nShu mavzuda esse yozing. Baholash usulini tanlang:",reply_markup=EVALUATION_METHOD_KEYBOARD)
            return
    if arg=="invite":
        await send_referral_info(update.message, uid); return
    if arg.startswith("test_"):
        await open_shared_test(update.message, arg[5:], uid, not existed); return
    if arg.startswith("duel_"):
        await open_duel(update.message, arg[5:]); return
    if arg.startswith("play_"):
        await open_play_invite(update.message, arg[5:]); return
    if arg == "expert":
        await expert_cmd(update, context); return
    if arg.startswith("pay_"):
        parts=arg.split("_")
        if len(parts)==3 and parts[1]=="gazallib": parts[1]="gazal_lib"
        if len(parts)==3 and parts[1]=="gazalitem": parts[1]="gazal_item"
        if len(parts)==3 and mp.valid_plan(parts[1],parts[2]):
            await start_card_order(update.message, context, uid, parts[1], parts[2]); return
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n\n"
        "✍️ Esse tekshirish — esseni baho va tavsiyalar bilan tekshirtiring.\n"
        "🎓 Esse Akademiyasi — lug‘atlar, testlar, reyting, esse mashqi, dalil topish, statistika va muallif haqida ma’lumot.\n"
        "🎁 Do‘stlaringizni taklif qiling — ikkalangizga bepul tekshiruv.",
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
        "4. Tekshiruvdan so‘ng natija rasmli yoki matnli shaklda olinadi.\n\n"
        f"🎁 Dastlabki {FREE_ESSAY_DAILY} ta esse bepul (bir martalik), keyin {PACK_ESSAYS} ta esse — {PACK_STARS} ⭐ yoki {mp.fmt_uzs(mp.PACKS['p3']['uzs'])} so‘m.\n"
        "🎁 /taklif — do‘stlaringizni taklif qilib bepul tekshiruv oling.\n"
        "🔔 /eslatma — kunlik eslatmani yoqish/o‘chirish.\n"
        "💼 /balans — hisobingiz • 🔁 /natija — oxirgi natijani qayta ko‘rish (bepul).",
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
    if len(file_ids) > MAX_ESSAY_IMAGES:
        try: await message.reply_text(f"⚠️ Bitta essega ko‘pi bilan {MAX_ESSAY_IMAGES} ta rasm yuborish mumkin (siz {len(file_ids)} ta yubordingiz). Rasmlarni kamaytirib yoki matnli PDF qilib qayta yuboring. Limitingizdan yechilmadi.",reply_markup=MAIN_KEYBOARD)
        except Exception: pass
        return
    src=None
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
            src=await quota_gate(message,user_id,"essay",key_images(topic,images))
            if src is None:
                try: await status.delete()
                except Exception: pass
                return
            result=await run_evaluation_silently(lambda: evaluate_images(topic, images))
            save_check(user_id,"image",topic,result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
            context.user_data["pending_result"] = result
            context.user_data["stage"] = "result_mode"
            await status.edit_text(f"✅ {len(file_ids)} ta rasmli esse tekshirildi.")
            await message.reply_text("📬 Natijani qanday usulda qabul qilasiz?", reply_markup=RESULT_FORMAT_KEYBOARD)
    except TranscriptionIncomplete as e:
        quota_refund(user_id,"essay",src)
        logger.warning("album transcription incomplete: %s", e)
        try:
            await message.reply_text(f"⚠️ Matn rasmdan to‘liq o‘qilmadi: {e}. Limitingiz qaytarildi. Rasmni yorug‘da, tekis va yaqindan qayta oling (barcha varaq kadrga sig‘sin) yoki matnni yozib yuboring.")
        except Exception:
            pass
        context.user_data.clear()
    except Exception as _e:
        quota_refund(user_id,"essay",src)
        logger.exception("photo album error")
        try:
            await message.reply_text("⚠️ Rasmlar bilan tekshiruvni yakunlashda texnik muammo yuz berdi. Limitingiz qaytarildi, birozdan so‘ng qayta urinib ko‘ring."+admin_err(user_id,_e))
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
        uid=update.effective_user.id; src=None
        status=await update.message.reply_text("⏳ Mashq PDF fayli tekshirilmoqda...",reply_markup=GROWTH_KEYBOARD)
        try:
            f=await context.bot.get_file(document.file_id); b=io.BytesIO(); await asyncio.wait_for(f.download_to_memory(b),timeout=60)
            session=context.user_data.get("growth_practice") or {"topic":""}
            src=await quota_gate(update.message,uid,"tool",key_pdf(session["topic"],b.getvalue()))
            if src is None:
                try: await status.delete()
                except Exception: pass
                return
            session=context.user_data.pop("growth_practice",session)
            result=await run_evaluation_silently(lambda: evaluate_pdf(session["topic"],b.getvalue()))
            save_check(update.effective_user.id,"growth_pdf",session["topic"],result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
            await send_result(update.message,result,"text")
            tips=result.get("improvements") or []
            if tips: await update.message.reply_text("🎯 MASHQ UCHUN TAVSIYALAR\n\n"+"\n".join("• "+str(x) for x in tips[:8]),reply_markup=GROWTH_KEYBOARD)
            await status.edit_text("✅ Mashq PDF essesi tekshirildi.")
        except Exception:
            quota_refund(uid,"tool",src)
            logger.exception("growth practice pdf error"); await status.edit_text("⚠️ Mashq PDFni tekshirishda texnik muammo yuz berdi. Limitingiz qaytarildi.")
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
        uid = update.effective_user.id; src = None
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
            src = await quota_gate(update.message, uid, "essay", key_pdf(topic, pdf_bytes))
            if src is None:
                try: await status.delete()
                except Exception: pass
                return
            result = await run_evaluation_silently(
                lambda: evaluate_pdf(topic, pdf_bytes)
            )
            if result.get("_local_special"): quota_refund(uid, "essay", src)   # AI ishlatilmadi -> limit qaytariladi
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
            quota_refund(uid, "essay", src)
            logger.warning("pdf rejected: %s", e)
            await status.edit_text(
                f"⚠️ PDF qabul qilinmadi: {e}.\n"
                f"Maksimal hajm {MAX_PDF_SIZE_MB:g} MB, maksimal {MAX_PDF_PAGES} sahifa. Limitingizdan yechilmadi."
            )
            context.user_data.clear()
        except asyncio.TimeoutError:
            quota_refund(uid, "essay", src)
            logger.warning("pdf processing timeout")
            await status.edit_text(
                "⚠️ PDFni qayta ishlash juda uzoq davom etdi. Faylni kichraytirib "
                "yoki sahifalar sonini kamaytirib qayta yuboring."
            )
            context.user_data.clear()
        except Exception:
            quota_refund(uid, "essay", src)
            logger.exception("pdf error")
            await status.edit_text(
                "⚠️ PDFni tekshirishda texnik muammo yuz berdi. Limitingiz qaytarildi. "
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
            uid=update.effective_user.id; src=None
            status=await update.message.reply_text("⏳ Mashq rasmi o‘qilmoqda va tekshirilmoqda...",reply_markup=GROWTH_KEYBOARD)
            try:
                file_id=update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
                f=await context.bot.get_file(file_id); b=io.BytesIO(); await f.download_to_memory(b)
                session=context.user_data.get("growth_practice") or {"topic":""}
                src=await quota_gate(update.message,uid,"tool",key_image(session["topic"],b.getvalue()))
                if src is None:
                    try: await status.delete()
                    except Exception: pass
                    return
                session=context.user_data.pop("growth_practice",session)
                result=await run_evaluation_silently(lambda: evaluate_image(session["topic"],b.getvalue()))
                save_check(update.effective_user.id,"growth_image",session["topic"],result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
                await send_result(update.message,result,"text")
                tips=result.get("improvements") or []
                if tips: await update.message.reply_text("🎯 MASHQ UCHUN TAVSIYALAR\n\n"+"\n".join("• "+str(x) for x in tips[:8]),reply_markup=GROWTH_KEYBOARD)
                await status.edit_text("✅ Mashq essesi tekshirildi.")
            except Exception:
                quota_refund(uid,"tool",src)
                logger.exception("growth practice image error")
                await status.edit_text("⚠️ Mashq rasmini tekshirishda texnik muammo yuz berdi. Limitingiz qaytarildi.")
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
    if update.message.document and int(update.message.document.file_size or 0) > MAX_IMAGE_FILE_MB*1024*1024:
        await update.message.reply_text(f"⚠️ Rasm fayli juda katta (maksimal {MAX_IMAGE_FILE_MB:g} MB). Rasmni oddiy rasm sifatida yuboring.",reply_markup=MAIN_KEYBOARD); return
    async with lock:
        uid=update.effective_user.id; src=None
        status=await update.message.reply_text("⏳ Rasm o‘qilmoqda va tekshirilmoqda...")
        try:
            file_id=update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
            f=await context.bot.get_file(file_id); b=io.BytesIO(); await f.download_to_memory(b)
            topic=context.user_data.get("topic","")
            src=await quota_gate(update.message,uid,"essay",key_image(topic,b.getvalue()))
            if src is None:
                try: await status.delete()
                except Exception: pass
                return
            result=await run_evaluation_silently(lambda: evaluate_image(topic,b.getvalue()))
            save_check(update.effective_user.id,"image",topic,result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
            context.user_data["pending_result"] = result
            context.user_data["stage"] = "result_mode"
            await status.edit_text("✅ Tekshiruv tugadi.")
            await update.message.reply_text("📬 Natijani qanday usulda qabul qilasiz?", reply_markup=RESULT_FORMAT_KEYBOARD)
        except TranscriptionIncomplete as e:
            quota_refund(uid,"essay",src)
            logger.warning("image transcription incomplete: %s", e)
            await status.edit_text(f"⚠️ Matn rasmdan to‘liq o‘qilmadi: {e}. Limitingiz qaytarildi. Rasmni yorug‘da, tekis va yaqindan qayta oling yoki matnni yozib yuboring.")
            context.user_data.clear()
        except Exception as _e:
            quota_refund(uid,"essay",src)
            logger.exception("image error")
            await status.edit_text("⚠️ Tekshiruvni yakunlashda texnik muammo yuz berdi. Limitingiz qaytarildi, birozdan so‘ng qayta urinib ko‘ring."+admin_err(uid,_e))
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
    return DAILY_ESSAY_TOPICS[datetime.now(mx.TZ).date().toordinal() % len(DAILY_ESSAY_TOPICS)]

async def send_daily_essay_practice(message, user_id, context):
    topic=daily_essay_topic()
    context.user_data["growth_practice"]={"topic":topic,"started_at":datetime.utcnow().isoformat()}
    await message.reply_text("✍️ ESSE YOZISH MASHQI\n\n📝 Bugungi mavzu:\n"+topic+"\n\nEsseni shu chatga yuboring. Matn, rasm yoki PDF yuborishingiz mumkin.\nBot uni BBA 24 ballik mezonlar asosida tekshiradi va xatolar hamda tavsiyalarni ko‘rsatadi.",reply_markup=GROWTH_KEYBOARD)

async def finish_growth_practice_text(message,user_id,essay_text,context):
    session=context.user_data.pop("growth_practice",None)
    if not session: return False
    bad=precheck_essay_text(essay_text)
    if bad:
        context.user_data["growth_practice"]=session
        await message.reply_text(bad,reply_markup=GROWTH_KEYBOARD); return True
    if local_special_result(session["topic"],essay_text) is not None: src=None   # lokal natija: limit sarflanmaydi
    else:
        src=await quota_gate(message,user_id,"tool",key_text(session["topic"],essay_text))
        if src is None:
            context.user_data["growth_practice"]=session
            return True
    await message.reply_text("⏳ Mashq essesi tekshirilmoqda...",reply_markup=GROWTH_KEYBOARD)
    try:
        result=await evaluate_text(session["topic"],essay_text)
        save_check(user_id,"growth_text",session["topic"],result.get("total",0),result.get("word_count",0),result.get("status","normal"),result)
        await send_result(message,result,"text")
        tips=result.get("improvements") or []
        if tips: await message.reply_text("🎯 MASHQ UCHUN TAVSIYALAR\n\n"+"\n".join("• "+str(x) for x in tips[:8]),reply_markup=GROWTH_KEYBOARD)
    except Exception:
        quota_refund(user_id,"tool",src)
        logger.exception("growth essay practice error")
        await message.reply_text("⚠️ Mashq esseni tekshirishda texnik muammo yuz berdi. Limitingiz qaytarildi, qayta urinib ko‘ring.",reply_markup=GROWTH_KEYBOARD)
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
        data=await openai_json(prompt,max_output_tokens=5000,feature='esse_reja'); lines=["🗂️ INDIVIDUAL ESSE REJASI","",f"📝 Mavzu: {topic}",""]
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
    src=await quota_gate(message,user_id,"tool")
    if src is None: return
    await message.reply_text("🔎 Mavzu uchun dalil turlari tayyorlanmoqda...",reply_markup=GROWTH_KEYBOARD)
    prompt=f'''Sen argumentli esse uchun dalil tayyorlovchi yordamchisan.
Mavzu: {topic}
5 tur ber: statistik dalil, hayotiy misol, tarixiy misol, mutaxassis fikri, mantiqiy dalil.
Muhim: manbasi tekshirilmagan raqam, ism yoki iqtibosni fakt sifatida UYDIMA. Ishonchli aniq manba bo‘lmasa, raqam o‘rniga qanday statistikani izlash kerakligini ayt. Mutaxassis fikrida tasdiqlanmagan iqtibosni qo‘shtirnoqqa olma.
JSON: {{"statistical":{{"claim":"...","source":"..."}},"life":"...","historical":"...","expert":{{"claim":"...","source":"..."}},"logical":"..."}}'''
    try:
        data=await openai_json(prompt,max_output_tokens=6000,feature='dalil_topish'); st=data.get("statistical") or {}; ex=data.get("expert") or {}
        lines=["💡 DALILLAR BANKI","",f"📝 Mavzu: {topic}","","📊 STATISTIK DALIL",str(st.get("claim","—")),f"Manba: {st.get('source','Tekshirish kerak')}","","👤 HAYOTIY MISOL",str(data.get("life","—")),"","🏛️ TARIXIY MISOL",str(data.get("historical","—")),"","🎓 MUTAXASSIS FIKRI",str(ex.get("claim","—")),f"Manba: {ex.get('source','Tekshirish kerak')}","","🧠 MANTIQIY DALIL",str(data.get("logical","—")),"","⚠️ Statistik raqam va iqtibosni ishlatishdan oldin manbasini tekshiring."]
        await message.reply_text("\n".join(lines)[:3900],reply_markup=GROWTH_KEYBOARD)
    except Exception:
        quota_refund(user_id,"tool",src)
        logger.exception("evidence helper error"); await message.reply_text("⚠️ Dalillarni tayyorlashda texnik muammo yuz berdi. Limitingiz qaytarildi, mavzuni qayta yuboring.",reply_markup=GROWTH_KEYBOARD)

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
O1|Savol matni|to‘g‘ri javob/muqobil javob|1|Izoh
O1AB|Savol|a javob;;b javob|1|Izoh

Y-1/Y-2 uchun javob harfi, O-1 uchun so‘z/jumla, O-1 a/b uchun `A javob;;B javob`.\n⚠️ Bir savolga bir nechta to‘g‘ri javob bo‘lsa, ularni / belgisi bilan ajrating (masalan: KITOB/KITOBLAR). Katta-kichik harf va ‘ ’ ʻ ʼ belgilari farqlanmaydi.""" ); return
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
        await update.message.reply_text(essay_free_warning(update.effective_user.id)+"📝 Esse mavzusi/vaziyatini yuboring.", reply_markup=MAIN_KEYBOARD)
        return
    if text==REF_BUTTON_TEXT:
        await send_referral_info(update.message, update.effective_user.id); return
    if text==BALANCE_BUTTON_TEXT:
        await balance_cmd(update, context); return
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
    if context.user_data.get("nes_manual"):
        mv=parse_manual_essay(text)
        if mv is None:
            await update.message.reply_text("❌ Esse balli 0 dan 24 gacha son bo‘lishi kerak (masalan: 17.5)."); return
        uid_=update.effective_user.id; pend=pending_get(uid_); test_=get_test(pend['code']) if pend else None
        context.user_data.pop("nes_manual",None)
        if not test_:
            await update.message.reply_text("ℹ️ Kutilayotgan test topilmadi. Testni qaytadan boshlang.",reply_markup=MAIN_KEYBOARD); return
        await finish_national(update.message,uid_,test_,pend['answers'],'manual',mv); return
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
        try:   # v76: ochiq mockning esse mavzusi oddiy yo'l bilan tekshirilmaydi
            _pm = mk_.promo_mock(update.effective_user.id, False) if update.effective_user.id != ADMIN_ID else None
            if _pm:
                from national_certificate import norm_topic as _nt
                if _nt(text) == _nt((get_test(_pm["test_code"]) or {}).get("essay_topic", "")):
                    await update.message.reply_text("📝 Bu mock esse mavzusi. Uni Mini App → Mock bo‘limida tekshirtirasiz: 🤖 bepul AI (1 martalik) yoki 👨‍🏫 ekspert.", reply_markup=MAIN_KEYBOARD); return
        except Exception: logger.exception("mock topic guard")
        context.user_data["topic"] = text
        context.user_data["stage"] = "method"
        await update.message.reply_text(
            "✅ Esse mavzusi qabul qilindi.\n\nEndi baholash usulini tanlang:",
            reply_markup=EVALUATION_METHOD_KEYBOARD
        )
        return
    if stage!="essay_ai": return
    bad=precheck_essay_text(text)
    if bad: await update.message.reply_text(bad,reply_markup=MAIN_KEYBOARD); return
    lock=await user_lock(update.effective_user.id)
    if lock.locked(): await update.message.reply_text("⏳ Oldingi tekshiruv tugamadi."); return
    async with lock:
        uid=update.effective_user.id; topic=context.user_data.get("topic","")
        loc=local_special_result(topic,text)   # <100 so'z / kirill: AI ham, limit ham sarflanmaydi
        if loc is None:
            src=await quota_gate(update.message,uid,"essay",key_text(topic,text))
            if src is None: return
        else: src=None
        status=await update.message.reply_text("⏳ Esse tekshirilmoqda...")
        try:
            result=loc if loc is not None else await run_evaluation_silently(lambda: evaluate_text(topic,text))
            save_check(update.effective_user.id,"text",topic,result.get("total",0),result.get("word_count",word_count(text)),result.get("status","normal"),result)
            context.user_data["pending_result"] = result
            context.user_data["stage"] = "result_mode"
            await status.edit_text("✅ Tekshiruv tugadi.")
            await update.message.reply_text("📬 Natijani qanday usulda qabul qilasiz?", reply_markup=RESULT_FORMAT_KEYBOARD)
        except Exception as e:
            quota_refund(uid,"essay",src)
            logger.exception("text error"); await status.edit_text("⚠️ Tekshiruvni yakunlashda texnik muammo yuz berdi. Limitingiz qaytarildi, birozdan so‘ng qayta urinib ko‘ring."+admin_err(uid,e)); context.user_data.clear()


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
        "Javoblar yopiq topshiriqlarda harf, ochiq topshiriqlarda esa javobning o‘zi bilan kiritiladi.\n⚠️ Ochiq topshiriqda faqat BITTA javob yozing (/ belgisini ishlatmang). Katta-kichik harf va ‘ ’ ʻ ʼ belgilari farqlanmaydi.\n📜 Sertifikat test yakunlangach beriladi.\n\n"
        "🔑 Test kodini yuboring:")

def _parse_test_wizard_line(text):
    # Format: TYPE|QUESTION|ANSWER(S)|POINTS|EXPLANATION
    parts=[x.strip() for x in text.split('|',4)]
    if len(parts)<3:return None
    typ=parts[0].upper()
    if typ not in ('Y1','Y2','O1','O1AB'): return None
    q={'type':typ,'text':parts[1],'points':float(parts[3]) if len(parts)>3 and parts[3] else 1.0,'explanation':parts[4] if len(parts)>4 else ''}
    if typ in ('Y1','Y2'): q['answer']=parts[2].upper()
    elif typ=='O1': q['answers']=split_alts(parts[2])
    else:
        ab=parts[2].split(';;',1)
        if len(ab)!=2:return None
        q['a_answers']=split_alts(ab[0])
        q['b_answers']=split_alts(ab[1])
    return q

async def send_essay_choice(message,uid,test):
    """Test tugagach: esse ballini qanday hisobga olish — mavjud esse / mavzuga esse yozish / qo'lda kiritish / esse'siz."""
    ex=essay_for_test(uid,test)
    st=mx.quota_status(uid,'essay',FREE_ESSAY_DAILY)
    rows=[]
    if ex: rows.append([InlineKeyboardButton(f"✅ Mavjud esse bali ({float(ex['total']):g}/24) bilan hisoblash",callback_data="nes_auto")])
    rows+=[[InlineKeyboardButton("✍️ Mavzuga esse yozaman (bot tekshiradi)",callback_data="nes_write")],
           [InlineKeyboardButton("🔢 Esse ballini o‘zim kiritaman",callback_data="nes_manual")],
           [InlineKeyboardButton("⏭ Esse‘siz (faqat test natijasi)",callback_data="nes_none")]]
    topic=test.get('essay_topic') or ''
    await message.reply_text("✅ Test javoblari qabul qilindi!\n\n📝 Endi esse (45-topshiriq) ballini qanday hisobga olamiz?"
        +(f"\nMavzu: «{topic}»" if topic else "")
        +f"\n\n🎁 Botda dastlabki {FREE_ESSAY_DAILY} ta esse tekshiruvi BEPUL (sizda {st['free_left']} ta qoldi)."
        +"\nEsse balli kiritilmasa, natija faqat test bo‘yicha (Rasch modelida) hisoblanadi.",
        reply_markup=InlineKeyboardMarkup(rows))

async def finish_national(message,uid,test,answers,mode='auto',manual=None):
    if int(uid)!=int(ADMIN_ID) and national_has_attempt(uid,test['id']):
        pending_clear(uid); await message.reply_text('Siz bu testni allaqachon ishlagansiz. Test faqat bir marta topshiriladi.',reply_markup=MAIN_KEYBOARD); return
    raw,score,errors,maxp=grade_national(test,answers)
    if mode=='manual' and manual is not None: essay={'id':None,'total':manual,'manual':True}
    elif mode=='none': essay=None
    else: essay=essay_for_test(uid,test)
    dr=diagnostic_result(test,uid,errors,essay)
    score=dr['test_t']; combined=dr['combined']; lvl=dr['level']
    essay_total=dr['essay24']
    if not save_attempt(uid,test['id'],essay['id'] if essay else None,answers,raw,combined,lvl,errors,allow_repeat=(int(uid)==int(ADMIN_ID))):
        await message.reply_text('Siz bu testni allaqachon ishlagansiz. Test faqat bir marta topshiriladi.',reply_markup=MAIN_KEYBOARD); return
    await message.reply_text(
        f"❌ TESTDAGI XATOLAR\n\n"
        + ("\n".join([f"{e['number']}-savol: siz — {e.get('user_text',e['user'])} | to‘g‘ri — {e.get('correct_text',e['correct'])}" + (f"  (qisman: {e['earned']:g}/{e['points']:g} ball)" if e.get('wrong_parts') is not None and e.get('earned') else "") for e in errors[:35]]) if errors else '🎉 Barcha javoblar to‘g‘ri!')
        + f"\n\n📊 To‘g‘ri javob: {raw:g}/{maxp:g}"
        + f"\n🧪 Test ({'Rasch T-ball' if dr['rasch'] else 'taxminiy, foiz'}): {score:.1f}/75"
        + (f"\n📝 Esse: {essay_total:g}/24 → {dr['essay_t']:g}/75" + (" (o‘zingiz kiritgan ball)" if essay and essay.get('manual') else "") if essay_total is not None else ((f"\n📝 Esse: «{test['essay_topic']}» mavzusida hali yozilmagan" if test.get('essay_topic') else "\n📝 Esse hali tekshirtirilmagan") + (" (umumiy ballga kirmadi)" if dr.get('essay_missing') else " → 0/75")))
        + (f"\n\n📈 UMUMIY (faqat test): {combined:.1f}/75\n🏅 Daraja: {lvl}\n💡 Esseni ham tekshirtirsangiz, umumiy ball esse bilan birga hisoblanadi." if dr.get('essay_missing') else f"\n\n📈 UMUMIY: ({score:.1f} + {dr['essay_t']:g}) ÷ 2 = {combined:.1f}/75\n🏅 Daraja: {lvl}")
        + (f"\n\nℹ️ {dr['note']}" if dr['note'] else "")
        + "\n\nBu rasmiy davlat sertifikati emas, tayyorlov diagnostikasi.",
        reply_markup=MAIN_KEYBOARD)
    pending_clear(uid)

async def national_essay_choice_callback(update,context):
    q=update.callback_query; uid=q.from_user.id; await q.answer()
    pend=pending_get(uid)
    test=get_test(pend['code']) if pend else None
    if not pend or not test:
        await q.message.reply_text("ℹ️ Kutilayotgan test topilmadi. Testni qaytadan boshlang: «🎓 Milliy sertifikat».",reply_markup=MAIN_KEYBOARD); return
    act=q.data
    if act=="nes_none":
        await finish_national(q.message,uid,test,pend['answers'],'none')
    elif act=="nes_auto":
        if not essay_for_test(uid,test):
            await q.message.reply_text("📝 Bu mavzuda esse topilmadi. Avval esseni tekshirtiring yoki ballni qo‘lda kiriting.",reply_markup=MAIN_KEYBOARD); return
        await finish_national(q.message,uid,test,pend['answers'],'auto')
    elif act=="nes_manual":
        context.user_data['nes_manual']=True
        await q.message.reply_text("🔢 Esse ballini 0 dan 24 gacha yozing (masalan: 17 yoki 17.5).")
    elif act=="nes_write":
        topic=test.get('essay_topic') or ''
        st=mx.quota_status(uid,'essay',FREE_ESSAY_DAILY)
        kb=InlineKeyboardMarkup([[InlineKeyboardButton("📊 Esse tekshirildi — natijani hisoblash",callback_data="nes_auto")],
                                 [InlineKeyboardButton("⏭ Esse‘siz (faqat test natijasi)",callback_data="nes_none")]])
        await q.message.reply_text("✍️ ESSE YOZISH\n\n"+(f"Mavzu: «{topic}»\n\n" if topic else "")
            +"1) Pastdagi menyudan «✍️ Esse tekshirish» tugmasini bosing.\n2) Shu mavzuni yuboring.\n3) Esse matni, rasmi yoki PDF’ini yuboring.\n4) Natija chiqqach shu xabardagi «Natijani hisoblash» tugmasini bosing.\n\n"
            +f"🎁 Sizda {st['free_left']}/{FREE_ESSAY_DAILY} ta bepul esse tekshiruvi bor.",reply_markup=kb)

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
        await update.message.reply_text(f"🧪 {session['index']}/45\n{qr_.strip(nq.get('text',''))}\n\n✏️ {hint}")
    else:
        context.user_data.pop('national_session',None)
        uid_=update.effective_user.id
        pending_set(uid_,test['code'],session['answers'])
        await send_essay_choice(update.message,uid_,test)
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

def tg_send_document(chat_id, filename, data, caption='', mime='application/pdf'):
    """v70: faylni (xotiradan, DISKKA YOZMASDAN) bot orqali Telegram'ga yuboradi. (file_id, size, mime) qaytaradi.
    Fayl Render xotirasida saqlanmaydi: Telegram'da qoladi, bazaga faqat file_id yoziladi."""
    bnd='----essebot'+secrets.token_hex(12); crlf=b'\r\n'; parts=[]
    def _f(name,val): parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'%(bnd,name,val)).encode('utf-8'))
    _f('chat_id',int(chat_id)); _f('disable_notification','true')
    if caption: _f('caption',caption[:1000])
    safe=re.sub(r'[\r\n"\\]+','_',filename or 'fayl.pdf')[:120]
    parts.append(('--%s\r\nContent-Disposition: form-data; name="document"; filename="%s"\r\nContent-Type: %s\r\n\r\n'%(bnd,safe,mime)).encode('utf-8'))
    parts.append(data); parts.append(crlf+('--%s--\r\n'%bnd).encode())
    body=b''.join(parts)
    req=urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument",data=body,headers={"Content-Type":"multipart/form-data; boundary="+bnd})
    try:
        with urllib.request.urlopen(req,timeout=120) as r: res=json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: res=json.loads(e.read().decode())
        except Exception: res={'ok':False,'description':'HTTP %s'%e.code}
    if not res.get('ok'): raise RuntimeError(str(res.get('description') or 'Telegram xatosi'))
    d=(res.get('result') or {}).get('document') or {}
    if not d.get('file_id'): raise RuntimeError('Telegram file_id qaytarmadi.')
    return d['file_id'], int(d.get('file_size') or len(data)), d.get('mime_type') or mime

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
AI_FREE_DAILY=int(os.getenv("AI_FREE_DAILY","1")); AI_PREMIUM_DAILY=int(os.getenv("AI_PREMIUM_DAILY","4"))
_JOBS={}; _JOBS_LOCK=threading.Lock(); _AI_SEM=threading.BoundedSemaphore(2)

def ai_limit_for(uid):
    if int(uid)==int(ADMIN_ID): return 1000
    try: return AI_PREMIUM_DAILY if growth_premium_active(uid) else AI_FREE_DAILY
    except Exception: return AI_FREE_DAILY

async def _practice_job(uid,topic,text):
    ac_.FEATURE.set('esse_mashq'); ac_.UID.set(uid)
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
    d=await openai_json(prompt,max_output_tokens=6000,feature='dalil_topish'); st=d.get("statistical") or {}; ex=d.get("expert") or {}
    return {"kind":"evidence","topic":topic,"statistical":{"claim":str(st.get("claim","—")),"source":str(st.get("source","Tekshirish kerak"))},
            "life":str(d.get("life","—")),"historical":str(d.get("historical","—")),"expert":{"claim":str(ex.get("claim","—")),"source":str(ex.get("source","Tekshirish kerak"))},"logical":str(d.get("logical","—"))}

def user_has_running_job(uid):
    with _JOBS_LOCK:
        return any(v["uid"]==uid and v["status"]=="running" and time.time()-v["t"]<900 for v in _JOBS.values())

def start_ai_job(uid,make_coro,src="free"):
    """Fon ishini boshlaydi. Foydalanuvchida allaqachon ishlayotgan job bo'lsa None qaytaradi (ikki marta to'lovdan himoya)."""
    import secrets
    jid=secrets.token_hex(8)
    with _JOBS_LOCK:
        for k in [k for k,v in _JOBS.items() if time.time()-v["t"]>3600]: _JOBS.pop(k,None)
        if any(v["uid"]==uid and v["status"]=="running" and time.time()-v["t"]<900 for v in _JOBS.values()): return None
        _JOBS[jid]={"uid":uid,"status":"running","t":time.time()}
    def run():
        try:
            ac_.UID.set(uid)
            with _AI_SEM: data=asyncio.run(make_coro())
            _JOBS.setdefault(jid,{"uid":uid,"t":time.time()}).update(status="done",data=data)
        except Exception:
            logger.exception("ai job error"); quota_refund(uid,"tool",src)
            _JOBS.setdefault(jid,{"uid":uid,"t":time.time()}).update(status="error",error="Texnik muammo yuz berdi. Limitingiz qaytarildi, birozdan so‘ng qayta urinib ko‘ring.")
    threading.Thread(target=run,daemon=True).start(); return jid

def send_results_file(kind, code, to_uid, caption=None):
    """Natijalar faylini (.xlsx) Telegramda yuboradi. True/False."""
    res = tr_.build_xlsx(kind, code)
    if not res: return False
    fn, data = res; m = tr_.get_meta(kind, code) or {}
    cap = caption or f"📊 {m.get('title','Test')} — natijalar\nKod: {code}"
    try:
        mx.send_document(TELEGRAM_BOT_TOKEN, to_uid, fn, data, cap); return True
    except Exception as e:
        logging.warning('send_results_file failed: %s', e); return False

def issue_held_certificates(code):
    """Test yakunlangach: sertifikatga loyiq (C va undan yuqori) ishtirokchilarga sertifikatlar birma-bir (RAM/trafikni tejab) yuboriladi."""
    try:
        rows = cert_pending_list(code)
        for r in rows:
            try:
                cc = mx.new_cert(r['user_id'], 'diag', r['data'])
                data = mx.render_certificate('diag', r['data'], cc)
                mx.send_photo(TELEGRAM_BOT_TOKEN, r['user_id'], data, '📜 Diagnostik sertifikatingiz tayyor! Test yakunlandi.\nBu — tayyorlov natijasi, rasmiy davlat sertifikati emas.')
                cert_mark_issued(r['id'], cc)
            except Exception as e:
                logging.warning('cert issue failed uid=%s: %s', r.get('user_id'), e)
                cert_mark_issued(r['id'], None)
            time.sleep(0.2)
        logging.info('CERTS | %s: %s ta sertifikat yuborildi', code, len(rows))
    except Exception: logger.exception('issue_held_certificates')

def finish_and_send(kind, code, reason='muddati tugadi'):
    """Testni yakunlaydi va fayl muallifga (bo'lmasa adminga) boradi."""
    m = tr_.get_meta(kind, code)
    if not m: return False
    new = tr_.finish(kind, code)
    if not new: return False
    if kind == 'ms' and not mk_.is_mock_code(code): threading.Thread(target=issue_held_certificates, args=(code,), daemon=True).start()   # MOCK: admin e'lon qilgach
    n = len({p['user_id'] for p in tr_.participants(kind, code)})
    cap = f"🏁 Test yakunlandi ({reason})\n\n📝 {m['title']}\nKod: {m['code']}\n👥 Ishtirokchilar: {n}\n\nQuyida to‘liq natijalar fayli."
    ok = bool(m.get('created_by')) and send_results_file(kind, code, int(m['created_by']), cap)
    if not ok and m.get('created_by') != ADMIN_ID: send_results_file(kind, code, ADMIN_ID, cap + "\n(Muallifga yuborib bo‘lmadi)")
    return True

def _notify_test_bonus(creator, kind, code):
    try:
        m = tr_.get_meta(kind, code) or {}
        tg_api('sendMessage', {'chat_id': int(creator), 'disable_notification': True,
               'text': f"🎉 Test havolangiz orqali kelgan yangi o‘quvchi «{m.get('title','test')}» testini ishladi!\n➕ +{gt_.TEST_REF_BONUS} ta bepul esse tekshiruvi hisobingizga qo‘shildi. (/balans)"})
    except Exception as e: logging.warning('notify_test_bonus: %s', e)

def after_submit(uid, kind, code):
    """Test topshirilgach: kunlik seriya, ustozga bonus, test ichidagi o'rin. Natija javobga qo'shiladi."""
    out = {}
    try: out['streak'] = gt_.touch(uid)
    except Exception: logger.exception('streak touch failed')
    try:
        cr = gt_.reward_creator(uid, kind, code)
        if cr: threading.Thread(target=_notify_test_bonus, args=(cr, kind, code), daemon=True).start()
    except Exception: logger.exception('test creator reward failed')
    try: out['rank'] = gt_.rank_of(kind, code, uid)
    except Exception: logger.exception('rank failed')
    return out

def send_deadline_reminders():
    """Tugashiga ~1 soat qolgan testlar: ishlamagan (havolani ochgan) o'quvchilarga va muallifga eslatma."""
    for kind, code, closes in gt_.reminder_candidates():
        m = tr_.get_meta(kind, code)
        if not m: continue
        pend = gt_.pending_visitors(kind, code); cn = gt_.counts(kind, code); url = miniapp_test_url(code)
        markup = {'inline_keyboard': [[{'text': '🚀 Testni ishlash', 'web_app': {'url': url}}]]} if url else None
        for u in pend:
            try:
                payload = {'chat_id': int(u), 'text': f"⏰ «{m['title']}» testi taxminan 1 soatdan keyin yopiladi.\nUlgurib qoling — natijangiz darhol ko‘rinadi!"}
                if markup: payload['reply_markup'] = markup
                tg_api('sendMessage', payload)
            except Exception: pass
            time.sleep(0.05)
        if m.get('created_by'):
            try:
                tg_api('sendMessage', {'chat_id': int(m['created_by']), 'disable_notification': True,
                       'text': f"⏰ Testingiz taxminan 1 soatdan keyin yakunlanadi.\n📝 {m['title']} ({m['code']})\n👥 Ishlaganlar: {cn['users']} • havolani ochib, hali ishlamaganlar: {len(pend)} (ularga eslatma yuborildi)"})
            except Exception: pass

def send_streak_reminders():
    """Kechagi seriyasi bor, bugun hali mashq qilmaganlarga kuniga bir marta eslatma."""
    url = miniapp_web_url()
    for uid, cur in gt_.streak_reminders():
        try:
            payload = {'chat_id': int(uid), 'disable_notification': True, 'text': f"🔥 Sizning seriyangiz — {cur} kun!\nBugun test ishlang yoki esse yozing, seriya uzilib qolmasin."}
            if url: payload['reply_markup'] = {'inline_keyboard': [[{'text': '🚀 Mashq qilish', 'web_app': {'url': url}}]]}
            tg_api('sendMessage', payload)
        except Exception: pass
        time.sleep(0.05)

def send_weekly_digests():
    """v72: yakshanba kechqurun faol o'quvchilarga haftalik shaxsiy hisobot (opt-out: /eslatma off)."""
    url = miniapp_web_url()
    for uid in lh_.digest_candidates():
        try:
            if mx.is_banned(uid) or mx.reminder_optout(uid): continue
            text = lh_.digest_message(uid)
            if not text: continue
            payload = {'chat_id': int(uid), 'disable_notification': True, 'text': text + '\n\nO‘chirish: /eslatma off'}
            if url: payload['reply_markup'] = {'inline_keyboard': [[{'text': '🚀 Mashqni davom ettirish', 'web_app': {'url': url}}]]}
            tg_api('sendMessage', payload)
        except Exception: pass
        time.sleep(0.05)

def results_watcher():
    """Har daqiqada muddati tugagan testlarni yakunlaydi va natijani yuboradi."""
    import time as _t
    while True:
        try:
            for kind, code in tr_.due(): finish_and_send(kind, code)
        except Exception as e: logging.warning('results_watcher: %s', e)
        try: send_deadline_reminders()
        except Exception as e: logging.warning('deadline reminders: %s', e)
        try: send_streak_reminders()
        except Exception as e: logging.warning('streak reminders: %s', e)
        try: send_weekly_digests()
        except Exception as e: logging.warning('weekly digests: %s', e)
        _t.sleep(60)

def notify_creator_attempt(kind, code, uid, line):
    """Muallifga: kimdir testni ishladi (ovozsiz xabar)."""
    try:
        m = tr_.get_meta(kind, code)
        if not m or not m.get('created_by') or int(m['created_by']) == int(uid): return
        tg_api('sendMessage', {'chat_id': int(m['created_by']), 'disable_notification': True,
               'text': f"👤 {mx.user_name(uid)} testni ishladi\n📝 {m['title']} ({m['code']})\n{line}"})
    except Exception as e: logging.warning('notify_creator: %s', e)

def _n(x):
    try:
        f=float(x); return int(f) if f==int(f) else round(f,1)
    except Exception: return x

def _deadline_hours(body, uid_is_admin):
    try: h = int(body.get('deadline_hours', 0 if uid_is_admin else 24))
    except Exception: h = 24
    return h if h in tr_.DEADLINE_CHOICES else (0 if uid_is_admin else 24)

def _can_manage(uid, kind, code):
    m = tr_.get_meta(kind, code)
    return bool(m) and uid is not None and (int(uid) == int(ADMIN_ID) or (m.get('created_by') is not None and int(m['created_by']) == int(uid)))



# ================= v56: USTOZ PRO (tahlil, PDF) =================
def teacher_overview_payload(uid, admin):
    p = gt_.panel(uid); until = tp_.pro_until(uid)
    return {'ok': True, 'pro': {'active': bool(until) or bool(admin), 'until': (until.strftime('%d.%m.%Y') if until else ''), 'price': mp.TEACHER_PRO_UZS, 'days': mp.TEACHER_PRO_DAYS, 'admin': bool(admin)},
            'free_left': tp_.free_left(uid), 'free_max_n': tp_.FREE_REPORT_MAX_N, 'tests': p['tests'], 'totals': p['totals']}

def teacher_stats_payload(uid, kind, code, admin):
    a = tp_.analytics(kind, code)
    if not a: return {'ok': False, 'error': 'Test topilmadi.'}
    ok, why = tp_.access(uid, kind, code, a['n'], admin)
    out = {'ok': True, 'kind': kind, 'code': code, 'title': a['title'], 'n': a['n'], 'access': why}
    if not ok:
        teaser = {k: a[k] for k in ('summary', 'levels', 'grades') if k in a} if not a.get('empty') else {}
        return {**out, 'locked': True, 'teaser': teaser, 'price': mp.TEACHER_PRO_UZS, 'free_max_n': tp_.FREE_REPORT_MAX_N, 'reason': why}
    out.update(a); out['locked'] = False; out['fanmap_text'] = tp_.fanmap_text(kind, code)
    if kind == 'ms': out['progress'] = tp_.progress(uid)
    return out

def teacher_pdf_send(uid, kind, code, admin):
    a = tp_.analytics(kind, code)
    if not a: return {'ok': False, 'error': 'Test topilmadi.'}
    ok, why = tp_.access(uid, kind, code, a['n'], admin)
    if not ok: return {'ok': False, 'locked': True, 'error': 'PDF hisobot Ustoz Pro uchun.'}
    data = tp_.build_pdf(a, mx.user_name(uid) or '', tp_.progress(uid) if kind == 'ms' else None)
    fn = f"sinf_hisoboti_{code}.pdf"
    try: mx.send_document(TELEGRAM_BOT_TOKEN, uid, fn, data, f"📄 Sinf hisoboti — {a['title']}\nKod: {code} • ishtirokchilar: {a['n']}")
    except Exception as e:
        logging.warning('teacher pdf send failed: %s', e); return {'ok': False, 'error': 'Faylni yuborib bo‘lmadi. Botga /start bosganingizni tekshiring.'}
    return {'ok': True}

BOOKS_DIR=bk_.find_dir(os.path.dirname(os.path.abspath(__file__)))

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
        self.send_response(200); self.send_header('Content-Type','image/jpeg' if data[:2]==b'\xff\xd8' else 'image/png'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(data)
    def _guard(self, uid, per_min=90):
        """Spam/blok himoyasi: IP va foydalanuvchi bo'yicha tezlik cheklovi + ban. True: davom etish mumkin."""
        if not mx.allow('ip:'+self._ip(), 300, 60): self._json({'ok':False,'error':'Juda ko‘p so‘rov. Bir daqiqadan keyin urinib ko‘ring.'},429); return False
        if uid is not None:
            if mx.is_banned(uid): self._json({'ok':False,'error':'Hisobingiz bloklangan.'},403); return False
            if not self._is_admin(uid) and not mx.allow('u:%s'%uid, per_min, 60): self._json({'ok':False,'error':'Juda tez-tez so‘rov yuboryapsiz. Biroz kuting.'},429); return False
        return True
    def _is_admin(self,uid): return uid is not None and int(uid)==int(ADMIN_ID)
    def _card_sms_webhook(self, body):
        """Bank SMS (kirim) -> buyurtmaga mos kelsa avtomatik tasdiqlanadi. Xizmatni card_grant_loop beradi (xato bo'lsa qayta urinadi)."""
        given=self.headers.get('X-Pay-Secret','') or (body.get('secret','') if isinstance(body,dict) else '')
        if not mx.allow('smshook:'+self._ip(),30,60): self._json({'ok':False,'error':'rate'},429); return
        if not mp.check_secret(given): self._json({'ok':False,'error':'forbidden'},403); return
        if not isinstance(body,dict): self._json({'ok':False,'error':'bad'},400); return
        text=''
        for k in ('text','message','body','sms','content','msg'):
            if body.get(k): text=str(body.get(k)); break
        st,oid,amount=mp.process_bank_sms(text)
        try:
            if st in ('no_order','ambiguous') and amount:
                tg_api('sendMessage',{'chat_id':ADMIN_ID,'text':('⚠️ Karta kirimi aniqlandi: %s so‘m — mos buyurtma TOPILMADI. Foydalanuvchi chek yuborsa, qo‘lda tasdiqlang.'%mp.fmt_uzs(amount)) if st=='no_order' else ('⚠️ Karta kirimi %s so‘m bir nechta buyurtmaga mos keldi — avto-tasdiq QILINMADI. Chekni qo‘lda tekshiring.'%mp.fmt_uzs(amount))})
        except Exception: logger.exception('sms webhook admin xabari')
        self._json({'ok':True,'status':st,'order':oid})
    def _books_paid(self,_u):
        """Badiiy asarlar bo'limi ochiq va foydalanuvchi to'lagan (yoki admin)."""
        return bool(self._is_admin(_u) or (mp.books_ready() and _u and mp.group_has(_u,'books')))
    def _books_full_access(self,_u,n=None):
        """Asar ichini (rasm, ma'lumot, test) ko'ra oladimi: admin, to'lov qilgan yoki bepul namuna asar (v40)."""
        if self._books_paid(_u): return True
        try: return bool(n is not None and mp.books_ready() and int(n)==bk_.free_id())
        except Exception: return False
    def _general_open(self):
        """«Umumiy test» foydalanuvchilarga ochiqmi (admin: /umumiy_ochiq, /umumiy_yopiq). Standart: qulf."""
        try: return mp.setting('general_open','0')=='1'
        except Exception: return False
    def _gazal_open(self):
        """«G'azal tahlilini o'rganamiz» foydalanuvchilarga ochiqmi (admin: /gazal_ochish, /gazal_yopish). Standart: yopiq."""
        try: return mp.gazal_lib_open()
        except Exception: return False
    def _gazal_paid(self,_u):
        """G'azal tahlili bo'limiga to'lagan (yoki admin)."""
        return bool(self._is_admin(_u) or (self._gazal_open() and _u and mp.group_has(_u,'gazal_lib')))
    def _gazal_owns(self,_u,n):
        """G'azal tahlili papkasi (n) ochiqmi: admin, eski «hammasi» xaridi yoki shu papkaning o'zi sotib olinganmi."""
        if self._is_admin(_u): return True
        if not (_u and n): return False
        try: return bool(mp.group_has(_u,'gazal_lib') or mp.group_has(_u,'gzi%d'%int(n)))
        except Exception: return False
    def _coll_full_access(self,_u,sec,n=None):
        """Kolleksiya ichini ko'ra oladimi. Badiiy asarlar: to'lovchi + bepul namuna. Umumiy test: admin (ochilsa — to'lovchi).
        Premium, Esse va Attestatsiya HOZIRCHA FAQAT ADMIN (foydalanuvchiga «Jarayonda»)."""
        if sec=='asar': return self._books_full_access(_u,n)
        if sec in bk_.MQ_SECS: return True   # v66: Mashq bo'limlari hamma uchun
        if sec=='gazal': return bool(self._is_admin(_u) or self._gazal_open())   # papkalar hammaga ko'rinadi; ichki qism — _books_extra_access
        if sec=='general': return bool(self._is_admin(_u) or (self._general_open() and self._books_paid(_u)))
        if sec=='esse': return bool(self._is_admin(_u) or (_u and growth_premium_active(_u)))   # v56: namunaviy esselar — Premium obunachilarga
        return bool(self._is_admin(_u))
    def _books_extra_access(self,_u,sec='asar',n=None):
        """«Testlar» va «Ma'lumotlar»: admin, to'lovchi yoki bepul namuna asar. Pullik qilish shartini shu yerda o'zgartiring."""
        if self._is_admin(_u): return True
        if sec=='general': return self._coll_full_access(_u,'general')
        if sec in bk_.MQ_SECS: return True   # v66
        if sec=='gazal': return self._gazal_owns(_u,n)
        if sec=='esse': return self._coll_full_access(_u,'esse')
        if sec!='asar': return False
        return self._books_full_access(_u,n)
    _STATIC_CACHE={}
    MIME={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'application/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml','.ico':'image/x-icon'}
    def _static_big(self, full, ext, _mt, size):
        """v68: Katta fayllar diskdan 64 KB bo'laklab beriladi; gzip nusxa diskda BIR marta tayyorlanadi. RAM da hech narsa saqlanmaydi."""
        import gzip, shutil, tempfile
        use_gz = ext in ('.json','.js','.css','.html') and 'gzip' in self.headers.get('Accept-Encoding','')
        path, length = full, size
        if use_gz:
            gdir = os.path.join(tempfile.gettempdir(), 'esse_gz'); os.makedirs(gdir, exist_ok=True)
            gp = os.path.join(gdir, hashlib.md5(f'{full}|{int(_mt)}|{size}'.encode()).hexdigest() + '.gz')
            if not os.path.exists(gp):
                tmp = gp + f'.{os.getpid()}.{threading.get_ident()}.tmp'
                with open(full,'rb') as src, gzip.open(tmp,'wb',compresslevel=6) as dst: shutil.copyfileobj(src, dst, 65536)
                os.replace(tmp, gp)
            path, length = gp, os.path.getsize(gp)
        _etag = '"%x-%x%s"' % (int(_mt), size, '-gz' if use_gz else '')
        _cc = 'public, max-age=86400' if ext == '.json' else 'no-cache'
        if self.headers.get('If-None-Match','') == _etag:
            self.send_response(304); self.send_header('ETag',_etag); self.send_header('Cache-Control',_cc); self.send_header('Vary','Accept-Encoding')
            self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); return True
        self.send_response(200)
        self.send_header('Content-Type',self.MIME.get(ext,'application/octet-stream')); self.send_header('Cache-Control',_cc); self.send_header('ETag',_etag)
        if use_gz: self.send_header('Content-Encoding','gzip'); self.send_header('Vary','Accept-Encoding')
        self.send_header('Content-Length',str(length)); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers()
        with open(path,'rb') as f: shutil.copyfileobj(f, self.wfile, 65536)
        return True
    def _static(self, rel):
        """miniapp/ papkasidagi fayllarni (index.html, style.css, app.js, *.json) beradi."""
        base=os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'miniapp'))
        rel=unquote(rel).lstrip('/') or 'index.html'
        full=os.path.realpath(os.path.join(base,rel))
        if not full.startswith(base+os.sep) or not os.path.isfile(full): return False
        ext=os.path.splitext(full)[1].lower()
        _mt=os.path.getmtime(full); _ck=(full,_mt)
        try: _sz=os.path.getsize(full)
        except OSError: return False
        if _sz>262144: return self._static_big(full,ext,_mt,_sz)   # v68: katta fayllar (lug'atlar) xotiraga YUKLANMAYDI
        _c=HealthHandler._STATIC_CACHE.get(_ck)
        if _c is None:
            if len(HealthHandler._STATIC_CACHE)>8: HealthHandler._STATIC_CACHE.clear()
            _raw=open(full,'rb').read(); _gz=None
            if ext in ('.json','.js','.css','.html') and len(_raw)>1024:
                import gzip; _gz=gzip.compress(_raw,compresslevel=6)
            _c=HealthHandler._STATIC_CACHE[_ck]=(_raw,_gz)
        data=_c[0]
        _use_gz = _c[1] is not None and 'gzip' in self.headers.get('Accept-Encoding','')
        # ETag: fayl o'zgarmagan bo'lsa brauzerga 304 (tana yuborilmaydi) -> Render trafigi keskin kamayadi
        _etag='"%x-%x%s"' % (int(_mt), len(_c[0]), '-gz' if _use_gz else '')
        _cc='public, max-age=86400' if ext=='.json' else 'no-cache'
        if self.headers.get('If-None-Match','')==_etag:
            self.send_response(304); self.send_header('ETag',_etag); self.send_header('Cache-Control',_cc); self.send_header('Vary','Accept-Encoding')
            self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); return True
        self.send_response(200)
        self.send_header('Content-Type',self.MIME.get(ext,'application/octet-stream'))
        # Trafikni tejash: katta lug'at fayllari 1 kunga keshlanadi va siqiladi (gzip)
        self.send_header('Cache-Control',_cc); self.send_header('ETag',_etag)
        if _use_gz:
            data=_c[1]; self.send_header('Content-Encoding','gzip'); self.send_header('Vary','Accept-Encoding')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Access-Control-Allow-Origin','*')
        self.end_headers(); self.wfile.write(data); return True
    def do_GET(self):
        try:
            # ?api=... kabi query qismi route'ni buzmasligi uchun faqat path olinadi
            _u=urlparse(self.path); self.path=_u.path; self.query=parse_qs(_u.query)
            if self.path=='/miniapp':
                self.send_response(301); self.send_header('Location','/miniapp/'); self.end_headers(); return
            if self.path=='/gcard.jpg':
                try:
                    from share_cards import sign, render_card
                    q={k:v[0] for k,v in self.query.items()}
                    k=q.get('k','play'); n=q.get('n','')[:22]; c=int(q.get('c','0')); t=int(q.get('t','5')); r=q.get('r','')[:30]
                    if k not in ('duel','play') or not hmac.compare_digest(q.get('s',''),sign(_game_card_secret(),k,n,c,t,r)): self._json({'ok':False},403); return
                    if not mx.allow('gcard:'+self._ip(),60,60): self._json({'ok':False},429); return
                    data=render_card(k,n,c,t,r).getvalue()
                    self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','public, max-age=86400'); self.end_headers(); self.wfile.write(data); return
                except Exception: self._json({'ok':False},400); return
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
            if self.path=='/api/esse/videos':   # v73: Esse -> Videodars (alohida bo'lim). Obunachi: admin ochmaguncha «Tez orada ochiladi»
                _u=self._user() if self.headers.get('X-Init-Data') else None
                adm=self._is_admin(_u); has=bool(adm or (_u and growth_premium_active(_u))); opn=_esse_video_open()
                out={'ok':True,'is_admin':adm,'has_access':has,'open':opn,'locked':not has,'soon':bool(has and not opn and not adm),'price':mp.GROWTH_UZS,'videos':[]}
                if adm or (has and opn): out['videos']=bk_.video_list(ESSE_VIDEO_N)
                self._json(out); return
            if self.path=='/api/me':
                uid=self._user()
                self._json({'ok':uid is not None,'uid':uid,'is_admin':self._is_admin(uid),'free_essay_total':FREE_ESSAY_DAILY,'free_essay_left':(mx.quota_status(uid,'essay',FREE_ESSAY_DAILY)['free_left'] if uid else FREE_ESSAY_DAILY),'can_create':(not TEST_CREATE_ADMIN_ONLY) or self._is_admin(uid),'admin_username':str(globals().get('ADMIN_USERNAME','') or '').lstrip('@'),'ai_limit':ai_limit_for(uid) if uid else 0,'ai_used':mx.ai_used(uid) if uid else 0,'ai_credits':(mx.quota_status(uid,'tool',ai_limit_for(uid))['credits'] if uid else 0),'pack_stars':mp.price_stars(uid,'tool','p3'),'pack_size':PACK_ESSAYS,'packs':mp.packs_for(uid,'tool'),'bot_username':BOT_USERNAME,'gazal_price':mp.GAZAL_GROUP_UZS,'gazal_joined':(mp.group_has(uid,'gazal') if uid else False),'version':APP_VERSION,'auto_pay':mp.auto_pay_enabled(),'card_auto':mp.card_auto_enabled(),'exam_date':os.getenv('EXAM_DATE','').strip(),'exam_name':os.getenv('EXAM_NAME','Milliy sertifikat imtihoni').strip(),'streak':(gt_.get_streak(uid) if uid else {'current':0,'best':0,'done_today':False}),'ref_link':(ref_link(uid) if uid else ''),'channel_url':REQUIRED_CHANNEL_URL,'ref_stats':(mp.ref_stats(uid) if uid else {'invited':0,'rewarded':0,'left':0}),'ref_inviter_bonus':mp.REF_INVITER_BONUS,'ref_invitee_bonus':mp.REF_INVITEE_BONUS}); return
            if self.path=='/api/quiz/list':
                uid=self._user() if self.headers.get('X-Init-Data') else None
                self._json({'ok':True,'items':mx.quiz_list(uid,self._is_admin(uid))}); return
            if self.path=='/api/streak':
                _who=self._user()
                if not _who: self._json({'ok':False,'error':'Foydalanuvchi aniqlanmadi.'},400); return
                self._json({'ok':True,**gt_.streak_card(_who)}); return
            if self.path=='/api/teacher/overview':
                _who=self._user()
                if not _who: self._json({'ok':False,'error':'Foydalanuvchi aniqlanmadi.'},400); return
                self._json(teacher_overview_payload(_who,self._is_admin(_who))); return
            if self.path=='/api/teacher/stats':
                kind=(self.query.get('kind') or [''])[0]; code=(self.query.get('code') or [''])[0].upper().strip(); _who=self._user()
                if kind not in ('ms','simple') or not _can_manage(_who,kind,code): self._json({'ok':False,'error':'Tahlilni faqat test muallifi va admin ko‘ra oladi.'},403); return
                self._json(teacher_stats_payload(_who,kind,code,self._is_admin(_who))); return
            if self.path=='/api/panel':
                _who=self._user()
                if not _who: self._json({'ok':False,'error':'Foydalanuvchi aniqlanmadi.'},400); return
                self._json({'ok':True,**gt_.panel(_who)}); return
            if self.path=='/api/test/top':
                kind=(self.query.get('kind') or [''])[0]; code=(self.query.get('code') or [''])[0].upper().strip(); _who=self._user()
                if kind not in ('ms','simple') or not _who or not tr_.get_meta(kind,code): self._json({'ok':False,'error':'Test topilmadi.'},404); return
                tp=gt_.top(kind,code,_who)
                if not tp['me'] and not _can_manage(_who,kind,code): self._json({'ok':False,'error':'Reytingni ko‘rish uchun avval testni ishlang.'},403); return
                self._json({'ok':True,**tp}); return
            if self.path.startswith('/api/test/results'):
                kind=(self.query.get('kind') or [''])[0]; code=(self.query.get('code') or [''])[0].upper().strip(); _who=self._user()
                if kind not in ('ms','simple') or not _can_manage(_who,kind,code): self._json({'ok':False,'error':'Natijalarni faqat test muallifi va admin ko‘ra oladi.'},403); return
                m=tr_.get_meta(kind,code); ps=tr_.participants(kind,code)
                self._json({'ok':True,'title':m['title'],'code':m['code'],'questions':len(m['questions']),**tr_.info(kind,code),
                    'participants':[{'name':(p['first']+' '+p['last']).strip(),'username':p['username'],'attempt':p['attempt'],'score':(f"{_n(p['correct'])}/{_n(p['total'])}"),'percent':p['percent'],'level':p.get('level',''),'errors':p['errors'],'at':p['at']} for p in ps]}); return
            if self.path=='/api/viewstats':
                _u=self._user() if self.headers.get('X-Init-Data') else None
                if not self._is_admin(_u): self._json({'ok':False,'error':'Faqat admin.'},403); return
                self._json({'ok':True,**view_report()}); return
            if self.path.startswith('/api/qimg/'):
                if self._user() is None: self._json({'ok':False,'error':'Telegram orqali oching.'},401); return
                try: data=qr_.get_image(int(self.path.rsplit('/',1)[-1]))
                except Exception: data=None
                if not data: self._json({'ok':False,'error':'Topilmadi'},404); return
                self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','private, max-age=86400'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(data); return
            if self.path=='/api/game/state':
                _u=self._user() if self.headers.get('X-Init-Data') else None
                self._json({'ok':True,**mx.game_state(_u or 0,ADMIN_ID)}); return
            if self.path=='/api/expert/info':
                _u=self._user() if self.headers.get('X-Init-Data') else None
                if _u is None: self._json({'ok':False,'error':'Telegram orqali oching.'},401); return
                self._json({'ok':True,**mp.expert_public(_u)}); return
            if self.path=='/api/game/qx':
                _u=self._user() if self.headers.get('X-Init-Data') else None
                if _u is None: self._json({'ok':False,'error':'Telegram orqali oching.'},401); return
                _c=(self.query.get('cat') or [''])[0]
                if _c and _c not in mx.QX_CATS: self._json({'ok':False,'error':'Bo‘lim noto‘g‘ri.'},400); return
                self._json({'ok':True,'items':mx.qx_list(_c or None),'counts':mx.qx_counts()}); return
            if self.path=='/api/books/list':
                _u=self._user() if self.headers.get('X-Init-Data') else None
                sec=((getattr(self,'query',{}) or {}).get('sec') or ['asar'])[0]
                if sec not in bk_.COLLECTIONS: sec='asar'
                adm=self._is_admin(_u); cfg=bk_.COLLECTIONS[sec]
                if sec=='gazal':   # pullik: ro'yxat (muqova, nom, fayllar soni) hamma ko'radi, fayllar faqat to'lovchiga
                    gopen=self._gazal_open(); has=self._gazal_paid(_u)
                    if not (gopen or adm): self._json({'ok':True,'sec':sec,'title':cfg['title'],'item_name':cfg['item'],'is_admin':adm,'extra':False,'soon':True,'ready':False,'has_access':False,'items':[]}); return
                    items=[{'n':x['n'],'title':x['title'],'files':x['files'],'videos':len(bk_.video_list(x['n'])),'qn':x['qn'],'has_info':x['has_info'],'slides':x['slides'] if adm else 0,
                            'price':bk_.item_price(x['n']),'owned':self._gazal_owns(_u,x['n'])} for x in bk_.list_books('gazal')]
                    self._json({'ok':True,'sec':sec,'title':cfg['title'],'item_name':cfg['item'],'is_admin':adm,'extra':has,'soon':False,'ready':gopen,'has_access':has,'items':items}); return
                if sec=='esse':   # v56: ro'yxat hammaga ko'rinadi, ichi — Premium obunachi va admin uchun
                    has=bool(adm or (_u and growth_premium_active(_u)))
                    self._json({'ok':True,'sec':sec,'title':cfg['title'],'item_name':cfg['item'],'is_admin':adm,'extra':has,'soon':False,'locked':not has,'ready':True,'has_access':has,'items':bk_.list_books('esse'),'price':mp.GROWTH_UZS,'bonus':mp.PREMIUM_BONUS_ESSAYS,'video_open':_esse_video_open(),'video_n':(len(bk_.video_list(ESSE_VIDEO_N)) if (adm or (has and _esse_video_open())) else 0)}); return
                if sec in bk_.MQ_SECS:   # v66: Mashq bo'limlari (Grammatika, Matn, Adabiyot, Esse) — hamma uchun ochiq
                    self._json({'ok':True,'sec':sec,'title':cfg['title'],'item_name':cfg['item'],'is_admin':adm,'extra':True,'soon':False,'ready':True,'has_access':True,'mq':True,'items':bk_.list_books(sec)}); return
                if sec!='asar':   # Premium / Attestatsiya: kontent hozircha faqat admin uchun
                    items=bk_.list_books(sec) if adm else []
                    self._json({'ok':True,'sec':sec,'title':cfg['title'],'item_name':cfg['item'],'is_admin':adm,'extra':adm,'soon':not adm,'ready':True,'has_access':adm,'items':items}); return
                ready=mp.books_ready(); has=bool(adm or (_u and mp.group_has(_u,'books')))
                items=bk_.list_books('asar') if (ready or adm) else []
                _fid=bk_.free_id()
                if adm: items=[dict(x,free=(x['n']==_fid)) for x in items]
                else:   # v40: nimalar borligini hamma ko'radi (soni), ichiga kirish huquqi alohida tekshiriladi
                    items=[{'n':x['n'],'title':x['title'],'author':x['author'],'pics':x['pics'],'has_info':x['has_info'],'qn':x['qn'],'free':(x['n']==_fid)} for x in items]
                _gid=bk_.general_id(create=bool(adm))
                _gen=({'n':_gid,'qn':bk_.question_count(_gid),'open':bool(adm or (self._general_open() and has)),'public':self._general_open()} if (_gid and (ready or adm)) else None)
                self._json({'ok':True,'sec':'asar','title':cfg['title'],'item_name':cfg['item'],'ready':ready,'is_admin':adm,'has_access':has,'extra':bool(has),'price':mp.BOOKS_UZS,'items':items,'general':_gen}); return
            if self.path.startswith('/api/books/detail/') or self.path.startswith('/api/books/quiz/') or self.path.startswith('/api/books/admin/'):
                _u=self._user() if self.headers.get('X-Init-Data') else None
                _p=self.path; _qs=getattr(self,'query',{}) or {}
                try: n=int(_p.rsplit('/',1)[-1])
                except Exception: n=0
                d=bk_.get_detail(n)
                if not d: self._json({'ok':False,'error':'Topilmadi.'},404); return
                if not self._coll_full_access(_u,d['sec'],n): self._json({'ok':False,'error':'Bu bo‘lim yopiq yoki to‘lov qilinmagan.'},403); return
                extra=self._books_extra_access(_u,d['sec'],n)
                if _p.startswith('/api/books/detail/'):
                    cfg=bk_.COLLECTIONS.get(d['sec'],bk_.COLLECTIONS['asar'])
                    out={'ok':True,'n':d['n'],'sec':d['sec'],'coll_title':cfg['title'],'item_name':cfg['item'],'title':d['title'],'author':d['author'],'pics':d['pics'],'extra':extra,'is_admin':self._is_admin(_u),'sample':bool(d['sec']=='asar' and not self._books_paid(_u))}
                    if extra:
                        out['videos']=d['videos'] if (d['sec']!='gazal' and self._books_paid(_u)) else []; out['files']=d['files'] if d['sec'] in bk_.FILE_SECS else []; out['counts']=d['counts']; out['sections']=bk_.get_sections(n); out['section_names']=bk_.section_names(d['sec']); out['slides']=d['slides'] if self._is_admin(_u) else []
                        if d['sec']=='esse': out['videos']=[]; out['slides']=[]; out['counts']={'closed':0,'open':0}; out['sections']={}   # v73: Esse elementida faqat «Faylni olish» (PDF)
                        out['best']={k:bk_.best_score(_u,n,k) for k in bk_.KINDS} if _u else {}
                    if d['sec']=='gazal':   # papka ichidagi fayl/video NOMLARI hammaga ko'rinadi (qulf bilan); yuborish faqat to'lovchiga
                        out['owned']=bool(extra); out['price']=bk_.item_price(n); out['files']=d['files']; out['videos']=d['videos']
                    self._json(out); return
                if not extra: self._json({'ok':False,'error':'Bu qism hozircha faqat admin uchun ochiq.'},403); return
                if d['sec']=='esse': self._json({'ok':False,'error':'Esse bo‘limida testlar yo‘q.'},404); return   # v73
                if _p.startswith('/api/books/admin/'):
                    if not self._is_admin(_u): self._json({'ok':False,'error':'Faqat admin.'},403); return
                    self._json({'ok':True,'title':d['title'],'author':d['author'],'sections':bk_.get_sections(n),'section_names':bk_.section_names(d['sec']),
                                'questions':bk_.questions(n,with_answers=True)}); return
                kind=(_qs.get('kind') or ['closed'])[0]
                if kind not in bk_.KINDS: kind='closed'
                self._json({'ok':True,'title':d['title'],'kind':kind,'questions':bk_.questions(n,kind=kind)}); return
            if self.path.startswith(('/api/books/img/','/api/books/thumb/','/api/books/pic/','/api/books/slide/','/api/books/sthumb/')):
                _u=self._user() if self.headers.get('X-Init-Data') else None
                adm=self._is_admin(_u); kind=self.path.split('/')[3]; thumb=kind in ('thumb','sthumb')
                try: n=int(self.path.rsplit('/',1)[-1])
                except Exception: n=0
                if kind in ('slide','sthumb'):
                    if not adm: self._json({'ok':False,'error':'Bu qism hozircha faqat admin uchun.'},403); return   # slaydlar: hozircha faqat admin
                    data,_bk=bk_.get_slide(n,thumb)
                else:
                    bid=bk_.pic_book(n) if kind=='pic' else n
                    sec=(bk_.get_sec(bid) if bid else None) or 'asar'
                    if sec=='asar': okacc=bool(adm or (mp.books_ready() and (thumb or (_u and mp.group_has(_u,'books')) or (bid and bid==bk_.free_id()))))
                    elif sec=='gazal': okacc=bool(adm or (self._gazal_open() and (thumb or kind=='img' or self._gazal_owns(_u,bid))))   # muqova hammaga; qo'shimcha rasmlar — to'lovchiga
                    else: okacc=adm
                    if not okacc: self._json({'ok':False,'error':'Bu bo‘lim yopiq.'},403); return
                    data=(bk_.get_pic(n) if kind=='pic' else bk_.get_image(n,thumb))
                if not data: self._json({'ok':False,'error':'Topilmadi'},404); return
                self.send_response(200); self.send_header('Content-Type','image/jpeg'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','private, max-age=3600'); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(data); return
            if self.path=='/api/simple/tests':
                _me=self._user() if self.headers.get('X-Init-Data') else None
                self._json({'ok':True,'tests':[{**{k:v for k,v in t.items() if k!='created_by'},'mine':(_me is not None and t.get('created_by')==_me),**{k:v for k,v in tr_.info('simple',t['code']).items() if k in ('closes_at','closed')}} for t in st_.list_all()]}); return
            if self.path.startswith('/api/simple/test/'):
                t=st_.get(self.path.rsplit('/',1)[-1])
                if not t: self._json({'ok':False,'error':'Test topilmadi'},404); return
                if tr_.is_closed('simple',t['code']): self._json({'ok':False,'error':'Bu test yakunlangan. Natijalar muallifga yuborilgan.'},410); return
                _me=self._user() if self.headers.get('X-Init-Data') else None
                if _me and not self._is_admin(_me) and st_.has_attempt(_me,t['id']): self._json({'ok':False,'already':True,'error':'Siz bu testni allaqachon ishlagansiz. Test faqat bir marta topshiriladi.'},409); return
                self._json({'ok':True,'test':{'code':t['code'],'title':t['title'],'subject':t['subject'],'questions':[{'number':i+1,'text':q['text'],'options':q['options']} for i,q in enumerate(t['questions'])]}}); return
            if self.path=='/api/mock/my-result':   # v68: foydalanuvchining mock natijasi (e'longacha faqat esse balli)
                _uu=self._user() if self.headers.get('X-Init-Data') else None
                if _uu is None: self._json({'ok':False,'error':'Kirish kerak.'},401); return
                try:
                    _mr=mk_.get(int((self.query.get('id') or ['0'])[0]))
                    if not _mr or not _mr['test_code']: self._json({'ok':False,'error':'Mock topilmadi.'},404); return
                    _code=_mr['test_code']
                    if not mk_.is_joined(_uu,_mr['id']) and not self._is_admin(_uu): self._json({'ok':False,'error':'Siz bu mockda ro‘yxatdan o‘tmagansiz.'},403); return
                    if mk_.is_published(_code):
                        _sn=mk_.snapshot_get(_code,_uu)
                        if _sn and 'class_stats' not in _sn:   # v71: eski e'lon qilingan natijalarni bir marta boyitamiz
                            try:
                                _an=tp_.ms_analytics(_code)
                                if _an and not _an.get('empty'): mock_enrich_snapshot(_code,_uu,_sn,_an); mk_.snapshot_set(_code,_uu,_sn)
                            except Exception: logger.exception('mock lazy enrich')
                        self._json({'ok':True,'published':True,'taken':bool(_sn),'title':_mr['title'],'code':_code,'result':_sn,'history':mk_.history(_uu),'bands':tp_.level_bands()}); return
                    _t=get_test(_code)
                    with DB_LOCK, db() as c:
                        _row=c.execute("SELECT essay_check_id FROM national_attempts WHERE user_id=? AND test_id=? ORDER BY id LIMIT 1",(_uu,_t['id'])).fetchone() if _t else None
                        _es=None
                        if _row and _row['essay_check_id']:
                            _er=c.execute("SELECT total FROM checks WHERE id=?",(_row['essay_check_id'],)).fetchone(); _es=(float(_er[0]) if _er else None)
                    self._json({'ok':True,'published':False,'taken':bool(_row),'title':_mr['title'],'essay_score':_es,'essay_pending':bool(_row) and _es is None}); return
                except Exception as e:
                    logger.exception('mock my-result'); self._json({'ok':False,'error':str(e)},400); return
            if self.path=='/api/mock/results':
                _uu=self._user() if self.headers.get('X-Init-Data') else None
                if not self._is_admin(_uu): self._json({'ok':False,'error':'Faqat admin.'},403); return
                try:
                    _mr=mk_.get(int((self.query.get('id') or ['0'])[0]))
                    if not _mr or not _mr['test_code']: self._json({'ok':False,'error':'Mock yoki unga biriktirilgan test topilmadi.'},404); return
                    _a=tp_.analytics('ms',_mr['test_code']); _regs=mk_.regs_of(_mr['test_code'])
                    _done={p['user_id'] for p in (_a or {}).get('people',[])} if _a and not _a.get('empty') else set()
                    _abs=[u for u in _regs if u not in _done]
                    self._json({'ok':True,'mock':{'id':_mr['id'],'title':_mr['title'],'code':_mr['test_code'],'opens_at':_mr['opens_at'],'closes_at':_mr['closes_at']},
                                'registered':len(_regs),'participated':len(_done),'absent':len(_abs),'absent_names':[mx.user_name(u) for u in _abs[:40]],
                                'open':mk_._parse(_mr['opens_at'])<=mk_._now()<mk_._parse(_mr['closes_at']),'closed':mk_._now()>=mk_._parse(_mr['closes_at']),
                                'published':bool((_mr['published_at'] or '').strip()),'analytics':_a,'trend':mk_.class_trend()}); return
                except Exception as e:
                    logger.exception('mock results'); self._json({'ok':False,'error':str(e)},400); return
            if self.path.startswith('/api/hub/'):
                _r=lh_.handle_get(self.path,self._user() if self.headers.get('X-Init-Data') else None)
                if _r is not None: self._json(_r[0],_r[1]); return
            if self.path=='/api/mock/pdf/list':   # v74: mock testining PDF varianti
                _uu=self._user() if self.headers.get('X-Init-Data') else None
                try: _mr=mk_.get(int((self.query.get('id') or ['0'])[0]))
                except Exception: _mr=None
                if not _mr: self._json({'ok':False,'error':'Mock topilmadi.'},404); return
                if not mk_.pdf_visible(_uu,_mr,self._is_admin(_uu)): self._json({'ok':False,'error':'PDF faqat ro‘yxatdan o‘tganlarga, mock ochiq paytda ko‘rinadi.'},403); return
                self._json({'ok':True,'pdfs':mk_.pdf_list(_mr['id']),'is_admin':self._is_admin(_uu),'regs':len(mk_.regs_of(_mr['test_code'])) if _mr['test_code'] else 0}); return
            if self.path.startswith('/api/mock/'):
                _uu=self._user() if self.headers.get('X-Init-Data') else None
                _r=mk_.handle_get(self.path,_uu,self._is_admin(_uu))
                if _r is not None: self._json(_r[0],_r[1]); return
            if self.path=='/api/national/tests':
                tests=[{'code':t['code'],'title':t['title'],'subject':t['subject'],'duration_min':t['duration_min'],'created_at':t['created_at'],'official':t['official'],'attempts':t['attempts'],**{k:v for k,v in tr_.info('ms',t['code']).items() if k in ('closes_at','closed')},'mine':bool((_mm:=tr_.get_meta('ms',t['code'])) and self._user() and _mm.get('created_by')==self._user())} for t in mx.list_tests_ex(ADMIN_ID)]
                _mc=mk_.mock_codes()
                tests=[x for x in tests if x['code'] not in _mc or self._is_admin(self._user())]
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
                if tr_.is_closed('ms',t['code']): self._json({'ok':False,'error':'Bu test yakunlangan. Natijalar muallifga yuborilgan.'},410); return
                _me=self._user() if self.headers.get('X-Init-Data') else None
                _gt=mk_.test_gate(t['code'],_me,self._is_admin(_me))
                if _gt is not None: self._json(_gt[0],_gt[1]); return
                if _me and not self._is_admin(_me) and national_has_attempt(_me,t['id']): self._json({'ok':False,'already':True,'error':'Siz bu testni allaqachon ishlagansiz. Test faqat bir marta topshiriladi.'},409); return
                public={'id':t['id'],'code':t['code'],'title':t['title'],'subject':t['subject'],'duration_min':t['duration_min'],'essay_topic':t.get('essay_topic',''),'essay_link':(f'https://t.me/{BOT_USERNAME}?start=essay_{t["code"]}' if BOT_USERNAME and t.get('essay_topic') else ''),'questions':[{'number':i+1,'type':q.get('type','Y1'),'text':q.get('text',''),'options':q.get('options',[]),'points':q.get('points',1)} for i,q in enumerate(t['questions'])]}
                try:
                    if mk_.is_mock_code(t['code']):
                        public['is_mock']=True
                        public['expert']={'uzs':mk_.MOCK_EXPERT_UZS,'job':(mk_.expert_job_for(_me,t['code']) if _me else None),'score':(mk_.expert_score_get(t['code'],_me) if _me else None),
                                          'link':(f'https://t.me/{BOT_USERNAME}?start=mockexpert_{t["code"]}' if BOT_USERNAME else '')}
                        public['ai']={**mk_.ai_free_info(t['code'],_me),'link':(f'https://t.me/{BOT_USERNAME}?start=mockai_{t["code"]}' if BOT_USERNAME else '')}   # v76
                except Exception: logger.exception('mock payload')
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
            if n>(20000000 if self.path in ('/api/books/admin/pdfup','/api/mock/pdf/up') else 6500000 if self.path in ('/api/books/admin/docx','/api/simple/docx','/api/game/qx/upload') else (3300000 if self.path in ('/api/simple/create','/api/books/admin/create','/api/books/admin/upload','/api/qimg/upload') else 300000)): self._json({'ok':False,'error':'So‘rov juda katta.'},413); return
            body=json.loads(self.rfile.read(n).decode('utf-8'))
            if self.path=='/api/pay/sms':   # v58: admin telefonidagi SMS-yo'naltiruvchi ilova shu manzilga bank SMS'ini yuboradi (Telegram emas, SIR bilan himoyalangan)
                self._card_sms_webhook(body); return
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
                if user_has_running_job(uid):
                    self._json({'ok':False,'error':'Oldingi so‘rovingiz hali tugamadi. Natijani kuting.'},429); return
                is_ev=(self.path=='/api/evidence')
                if self._is_admin(uid): src='admin'
                elif (not is_ev) and (cache_get(key_text(topic,essay)) is not None or local_special_result(topic,essay) is not None): src='cache'   # kesh yoki lokal natija: limit sarflanmaydi
                else:
                    src=mx.quota_consume(uid,'tool',ai_limit_for(uid))
                    if src is None:
                        self._json({'ok':False,'limit':True,'need_payment':True,'pack_stars':mp.price_stars(uid,'tool','p3'),'pack_size':PACK_ESSAYS,'packs':mp.packs_for(uid,'tool'),
                                    'error':'Bugungi bepul limitingiz tugadi. Esse tekshirish jarayoni to‘liq pullik sun’iy intellekt (AI) orqali amalga oshiriladi, shuning uchun paket sotib oling (Stars yoki karta).'},402); return
                jid=start_ai_job(uid,(lambda: _evidence_job(uid,topic)) if is_ev else (lambda: _practice_job(uid,topic,essay)),src)
                if jid is None:
                    quota_refund(uid,'tool',src); self._json({'ok':False,'error':'Oldingi so‘rovingiz hali tugamadi. Natijani kuting.'},429); return
                self._json({'ok':True,'job':jid}); return
            if self.path=='/api/pay/uzs':
                if not mp.auto_pay_enabled(): self._json({'ok':False,'error':'Avtomatik to‘lov hozircha ulanmagan.'},400); return
                if not mx.allow('uzs:%s'%uid,10,600): self._json({'ok':False,'error':'Juda tez-tez. Biroz kuting.'},429); return
                kind=str(body.get('kind','')); plan=str(body.get('plan',''))
                kind={'gazallib':'gazal_lib','gazalitem':'gazal_item'}.get(kind,kind)
                if not mp.valid_plan(kind,plan): self._json({'ok':False,'error':'Paket topilmadi.'},400); return
                if not self._is_admin(uid):
                    if kind=='books' and mp.group_has(uid,'books'): self._json({'ok':False,'error':'Bu bo‘lim sizda allaqachon ochiq.'},400); return
                    if kind=='gazal_lib' and (mp.group_has(uid,'gazal_lib') or not mp.gazal_lib_open()): self._json({'ok':False,'error':'Bu bo‘lim ochiq yoki hali ishga tushmagan.'},400); return
                    if kind=='gazal_item' and (mp.group_has(uid,'gazal_lib') or mp.group_has(uid,'gzi%s'%plan) or not mp.gazal_lib_open()): self._json({'ok':False,'error':'Bu qo‘llanma ochiq yoki hali ishga tushmagan.'},400); return
                    if kind=='group' and mp.group_has(uid,plan): self._json({'ok':False,'error':'Siz allaqachon qabul qilingansiz.'},400); return
                try:
                    a=_auto_invoice_args(int(uid),kind,plan)
                    r=tg_api('createInvoiceLink',{'title':a['title'],'description':a['description'],'payload':a['payload'],'provider_token':mp.PROVIDER_TOKEN,'currency':'UZS','prices':a['prices']})
                    self._json({'ok':bool(r.get('ok')),'link':r.get('result'),'error':None if r.get('ok') else 'To‘lov havolasini yaratib bo‘lmadi.'}); return
                except Exception:
                    logger.exception('createInvoiceLink uzs'); self._json({'ok':False,'error':'To‘lov havolasini yaratib bo‘lmadi.'},500); return
            if self.path=='/api/pay/invoice':
                kind='tool' if str(body.get('kind','tool'))=='tool' else 'essay'
                if not mx.allow('invoice:%s'%uid,6,600): self._json({'ok':False,'error':'Juda tez-tez. Biroz kuting.'},429); return
                pid=str(body.get('plan','p3'))
                if pid not in mp.PACKS or not mp.valid_plan(kind,pid): pid='p3'
                title=mp.plan_title(kind,pid)
                try:
                    r=tg_api('createInvoiceLink',{'title':title,'description':'Esse tekshirish jarayoni to‘liq pullik sun’iy intellekt (AI) orqali amalga oshiriladi. Paket muddatsiz saqlanadi; bepul kunlik limitdan keyin ishlatiladi.','payload':'pack:%s:%s:%s'%(kind,uid,pid),'provider_token':'','currency':'XTR','prices':[{'label':title,'amount':mp.price_stars(uid,kind,pid)}]})
                    self._json({'ok':bool(r.get('ok')),'link':r.get('result'),'error':None if r.get('ok') else 'To‘lov havolasini yaratib bo‘lmadi.'}); return
                except Exception:
                    logger.exception('createInvoiceLink'); self._json({'ok':False,'error':'To‘lov havolasini yaratib bo‘lmadi.'},500); return
            if self.path=='/api/cert/send':
                c=mx.get_cert(str(body.get('code','')))
                if not c or int(c['user_id'])!=uid: self._json({'ok':False,'error':'Sertifikat topilmadi.'},404); return
                if not mx.allow('certsend:%s'%uid,5,600): self._json({'ok':False,'error':'Juda tez-tez. 10 daqiqadan keyin urinib ko‘ring.'},429); return
                threading.Thread(target=lambda: mx.send_photo(TELEGRAM_BOT_TOKEN,uid,mx.render_certificate(c['kind'],c['data'],c['code']),'📜 Sertifikatingiz'),daemon=True).start()
                self._json({'ok':True}); return
            if self.path=='/api/mock/my-report':   # v71: talabgorning shaxsiy mock hisobotini botga PDF qilib yuborish
                try:
                    _mr=mk_.get(int(body.get('id') or 0))
                    if not _mr or not _mr['test_code']: self._json({'ok':False,'error':'Mock topilmadi.'},404); return
                    _code=_mr['test_code']
                    if not mk_.is_published(_code): self._json({'ok':False,'error':'Natijalar hali e‘lon qilinmagan.'},403); return
                    _sn=mk_.snapshot_get(_code,uid)
                    if not _sn: self._json({'ok':False,'error':'Siz bu mockni topshirmagansiz.'},404); return
                    if not mx.allow('mockrep:%s'%uid,4,600): self._json({'ok':False,'error':'Juda tez-tez. Bir necha daqiqadan keyin urinib ko‘ring.'},429); return
                    if 'class_stats' not in _sn:
                        _an=tp_.ms_analytics(_code)
                        if _an and not _an.get('empty'): mock_enrich_snapshot(_code,uid,_sn,_an); mk_.snapshot_set(_code,uid,_sn)
                    _pdf=tp_.build_mock_personal_pdf(_sn,mk_.history(uid),mx.user_name(uid) or '')
                    try: mx.send_document(TELEGRAM_BOT_TOKEN,uid,'mock_natija_%s.pdf'%_code,_pdf,'📄 Mock natija hisoboti — %s\nBall: %s/75 • Daraja: %s'%(_mr['title'],_sn.get('combined_score_75'),_sn.get('level')))
                    except Exception as e:
                        logger.warning('mock report send failed: %s',e); self._json({'ok':False,'error':'Faylni yuborib bo‘lmadi. Botga /start bosganingizni tekshiring.'},502); return
                    _pdf=None; self._json({'ok':True}); return
                except Exception as e:
                    logger.exception('mock my-report'); self._json({'ok':False,'error':'Hisobotni tayyorlab bo‘lmadi.'},500); return
            if self.path=='/api/teacher/pdf':
                kind=str(body.get('kind','')); code=str(body.get('code','')).upper().strip()
                if kind not in ('ms','simple') or not _can_manage(uid,kind,code): self._json({'ok':False,'error':'Faqat test muallifi yoki admin.'},403); return
                self._json(teacher_pdf_send(int(uid),kind,code,self._is_admin(uid))); return
            if self.path=='/api/teacher/fanmap':
                kind=str(body.get('kind','')); code=str(body.get('code','')).upper().strip()
                if kind not in ('ms','simple') or not _can_manage(uid,kind,code): self._json({'ok':False,'error':'Faqat test muallifi yoki admin.'},403); return
                fm=tp_.set_fanmap(kind,code,str(body.get('text',''))[:3000]); self._json({'ok':True,'fans':len(fm)}); return
            if self.path in ('/api/test/send','/api/test/finish'):
                kind=str(body.get('kind','')); code=str(body.get('code','')).upper().strip()
                if kind not in ('ms','simple') or not _can_manage(uid,kind,code): self._json({'ok':False,'error':'Faqat test muallifi yoki admin.'},403); return
                if self.path=='/api/test/finish':
                    new=finish_and_send(kind,code,'muallif tomonidan yakunlandi')
                    self._json({'ok':True,'already':not new}); return
                ok=send_results_file(kind,code,int(uid)); self._json({'ok':ok,'error':'' if ok else 'Faylni yuborib bo‘lmadi. Botga /start bosganingizni tekshiring.'}); return
            if self.path in ('/api/game/qx/upload','/api/game/qx/clear'):
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin uchun.'},403); return
                _c=str(body.get('cat','')).strip()
                if _c not in mx.QX_CATS: self._json({'ok':False,'error':'Bo‘lim tanlanmadi.'},400); return
                if self.path=='/api/game/qx/clear':
                    self._json({'ok':True,'removed':mx.qx_clear(_c),'counts':mx.qx_counts()}); return
                import base64
                _txt=str(body.get('text','') or '')
                _b64=str(body.get('file','') or '')
                if _b64:
                    if ',' in _b64[:80]: _b64=_b64.split(',',1)[1]
                    try: _raw=base64.b64decode(_b64)
                    except Exception: self._json({'ok':False,'error':'Fayl o‘qilmadi.'},400); return
                    if _raw[:2]==b'PK':
                        try: _txt,_w=qr_.docx_to_text(_raw,uid,allow_images=False)
                        except ValueError as e: self._json({'ok':False,'error':str(e)},400); return
                    else:
                        try: _txt=_raw.decode('utf-8-sig')
                        except Exception: _txt=_raw.decode('cp1251',errors='ignore')
                if not _txt.strip(): self._json({'ok':False,'error':'Fayl bo‘sh.'},400); return
                _items,_errs=mx.qx_parse(_c,_txt[:600000])
                if not _items: self._json({'ok':False,'error':'Savol topilmadi. Format: «1. Savol / A) ... / Javob: B»'+(('\n'+'\n'.join(_errs[:6])) if _errs else '')},400); return
                if _errs and not body.get('skip_errors'): self._json({'ok':False,'error':'Hech narsa qo‘shilmadi, xatolarni tuzating:\n'+'\n'.join(_errs[:8]),'can_skip':True,'found':len(_items)},400); return
                try: _tot=mx.qx_add(_c,_items,replace=bool(body.get('replace')))
                except ValueError as e: self._json({'ok':False,'error':str(e)},400); return
                self._json({'ok':True,'added':len(_items),'total':_tot,'skipped':len(_errs),'counts':mx.qx_counts()}); return
            if self.path=='/api/game/submit':
                if not mx.allow('gamesub:%s'%uid,60,3600): self._json({'ok':False,'error':'Juda tez-tez. Biroz kuting.'},429); return
                res,err=mx.game_submit(uid,str(body.get('game','')),body.get('correct',0),body.get('total',0),ADMIN_ID)
                if res is not None:
                    try:
                        for _cid,_txt in mx.game_after_submit(uid,str(body.get('game','')),body.get('correct',0),body.get('total',0),body.get('meta') if isinstance(body.get('meta'),dict) else {},credit_fn=mp.add_credits):
                            try: tg_api('sendMessage',{'chat_id':_cid,'text':_txt})
                            except Exception: pass
                        res=mx.game_state(uid,ADMIN_ID) | {k:res[k] for k in ('gained','already') if k in res}
                    except Exception: logger.exception('game_after_submit')
                self._json({'ok':res is not None,'error':err,**(res or {})},200 if res else 400); return
            if self.path=='/api/game/joker':
                left,err=mx.game_joker_use(uid)
                self._json({'ok':left is not None,'left':left,'error':err},200 if left is not None else 400); return
            if self.path=='/api/game/share':
                if not mx.allow('gshare:%s'%uid,30,3600): self._json({'ok':False,'error':'Juda tez-tez.'},429); return
                kind='duel' if str(body.get('kind'))=='duel' else 'play'
                try: c=max(0,min(int(body.get('correct',0)),20)); t=max(1,min(int(body.get('total',5)),20)); sd=max(1,min(int(body.get('seed',1)),999999999))
                except Exception: c,t,sd=0,5,1
                nm=_first_name(uid); lk=(f'https://t.me/{BOT_USERNAME}?start=duel_{sd}_{c}_{uid}' if kind=='duel' else f'https://t.me/{BOT_USERNAME}?start=play_{uid}') if BOT_USERNAME else ''
                out={'ok':True,'link':lk,'msg_id':None}
                try:
                    pu=game_card_url(kind,nm,c,t,'')
                    if pu and lk:
                        cap=(f'⚔️ {nm} sizni ona tili bellashuviga chaqirdi!\n🎯 Natijasi: {c}/{t}. O‘zib keta olasizmi?' if kind=='duel' else f'🎮 {nm} sizni «Ona tilini o‘ynab o‘rganamiz» o‘yiniga chaqirdi!\nKunlik savollar, DTM sinov va bellashuv.')
                        r=tg_api('savePreparedInlineMessage',{'user_id':uid,'allow_user_chats':True,'allow_bot_chats':False,'allow_group_chats':True,'allow_channel_chats':False,
                            'result':{'type':'photo','id':'g%s'%secrets.token_hex(6),'photo_url':pu,'thumbnail_url':pu,'photo_width':1200,'photo_height':630,'caption':cap,
                                      'reply_markup':{'inline_keyboard':[[{'text':'⚔️ Qabul qilaman' if kind=='duel' else '🎮 O‘ynashni boshlash','url':lk}]]}}})
                        out['msg_id']=((r or {}).get('result') or {}).get('id')
                except Exception: logger.exception('prepared message failed')
                self._json(out); return
            if self.path=='/api/view':
                if not uid: self._json({'ok':False}); return
                ok=False
                try: ok=mx.record_view(uid,str(body.get('section','')))
                except Exception: logger.exception('record_view')
                self._json({'ok':ok}); return
            if self.path=='/api/books/quiz':
                try: n=int(body.get('n'))
                except Exception: n=0
                _qd=bk_.get_detail(n) if uid else None
                if not uid or not _qd or not (self._coll_full_access(uid,_qd['sec'],n) and self._books_extra_access(uid,_qd['sec'],n)): self._json({'ok':False,'error':'Bu qism yopiq yoki to‘lov qilinmagan.'},403); return
                kind=str(body.get('kind') or 'closed')
                res=bk_.grade(uid,n,body.get('answers') or {},kind)
                if not res: self._json({'ok':False,'error':'Bu testda savol yo‘q.'},404); return
                try: res['streak']=gt_.touch(uid)
                except Exception: pass
                if _qd['sec'] in bk_.MQ_SECS and not self._is_admin(uid):   # v66: Mashq testlari -> reyting balli (server tekshirgan natija)
                    try: res['rating']=mx.mq_award(uid,n,res.get('kind') or kind,res.get('correct',0),res.get('total',0),ADMIN_ID)
                    except Exception: logger.exception('mq_award')
                self._json({'ok':True,**res}); return
            if self.path.startswith('/api/books/admin/'):
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                act=self.path.rsplit('/',1)[-1]
                def _img():
                    import base64
                    b64=str(body.get('image','') or '')
                    if not b64: return None,''
                    if ',' in b64[:64]: b64=b64.split(',',1)[1]
                    try: raw=base64.b64decode(b64)
                    except Exception: return None,'Rasm o‘qilmadi.'
                    return (raw,'') if 0<len(raw)<=2400000 else (None,'Rasm juda katta (2 MB gacha).')
                if act=='create':
                    sec=str(body.get('sec') or 'asar')
                    title=str(body.get('title','')).strip()[:120]
                    if sec not in bk_.COLLECTIONS or not title: self._json({'ok':False,'error':'Nomini kiriting.'},400); return
                    raw,err=_img()
                    if err: self._json({'ok':False,'error':err},400); return
                    _pr=body.get('price') if sec=='gazal' else None
                    if _pr not in (None,'',0,'0'):
                        try: _pr=int(_pr)
                        except Exception: _pr=-1
                        if _pr<bk_.MIN_PRICE or _pr>bk_.MAX_PRICE: self._json({'ok':False,'error':'Narx %s dan %s so‘mgacha bo‘lsin.'%(mp.fmt_uzs(bk_.MIN_PRICE),mp.fmt_uzs(bk_.MAX_PRICE))},400); return
                    else: _pr=None
                    try: nn=bk_.add(title,raw,sec)
                    except Exception: self._json({'ok':False,'error':'Rasm yaroqsiz yoki juda katta.'},400); return
                    if _pr: bk_.set_item_price(nn,_pr)
                    self._json({'ok':True,'n':nn,'price':bk_.item_price(nn) if sec=='gazal' else None}); return
                try: n=int(body.get('n'))
                except Exception: n=0
                if n==ESSE_VIDEO_N and act not in ('vidmode','rmvideo','mvvideo','renvideo'): self._json({'ok':False,'error':'Topilmadi.'},404); return
                if n!=ESSE_VIDEO_N and not bk_.exists(n): self._json({'ok':False,'error':'Topilmadi.'},404); return
                if act in ('vidmode','mvvideo','renvideo') and n!=ESSE_VIDEO_N and bk_.get_sec(n)=='esse': self._json({'ok':False,'error':'Esse elementlariga video qo‘shilmaydi. «Videodars» bo‘limidan foydalaning.'},400); return
                if act=='setprice':
                    if bk_.get_sec(n)!='gazal': self._json({'ok':False,'error':'Narx faqat «G‘azal tahlili» papkalari uchun.'},400); return
                    ok=bk_.set_item_price(n,body.get('price'))
                    self._json({'ok':ok,'price':bk_.item_price(n),'error':'' if ok else 'Narx %s dan %s so‘mgacha bo‘lsin (0 — standart narx).'%(mp.fmt_uzs(bk_.MIN_PRICE),mp.fmt_uzs(bk_.MAX_PRICE))}); return
                if act=='upload':
                    raw,err=_img(); target=str(body.get('target') or 'pic')
                    if err or not raw: self._json({'ok':False,'error':err or 'Rasm yuboring.'},400); return
                    try:
                        if target=='slide':
                            ok,r=bk_.add_slide(n,raw,str(body.get('caption','')))
                            if not ok: self._json({'ok':False,'error':r},400); return
                        elif target=='cover': bk_.set_cover(n,raw)
                        else:
                            if bk_.pic_count(n)>=bk_.MAX_PICS: self._json({'ok':False,'error':f'Rasmlar {bk_.MAX_PICS} tadan oshmasin.'},400); return
                            bk_.add_pic(n,raw)
                    except Exception: self._json({'ok':False,'error':'Rasm yaroqsiz yoki juda katta.'},400); return
                    self._json({'ok':True,'pics':bk_.pic_ids(n),'slides':bk_.slide_list(n)}); return
                if act=='pdfup':   # v70: PDF Mini App'dan to'g'ridan-to'g'ri yuklanadi -> bot orqali Telegram'ga ketadi (Render xotirasi/diskiga yozilmaydi)
                    import base64
                    if bk_.get_sec(n) not in bk_.FILE_SECS: self._json({'ok':False,'error':'Bu bo‘limga fayl yuklab bo‘lmaydi.'},400); return
                    b64=str(body.get('file','') or ''); body['file']=''
                    if ',' in b64[:80]: b64=b64.split(',',1)[1]
                    try: raw=base64.b64decode(b64)
                    except Exception: self._json({'ok':False,'error':'Fayl o‘qilmadi.'},400); return
                    del b64
                    if not raw or len(raw)>bk_.PDF_MAX_BYTES: self._json({'ok':False,'error':'PDF hajmi %d MB dan oshmasin.'%(bk_.PDF_MAX_BYTES//1048576)},400); return
                    if raw[:5]!=b'%PDF-': self._json({'ok':False,'error':'Bu PDF fayl emas. Faqat .pdf yuklang.'},400); return
                    fname=(str(body.get('name') or 'fayl.pdf').strip() or 'fayl.pdf')
                    if not fname.lower().endswith('.pdf'): fname+='.pdf'
                    title=str(body.get('title') or '').strip()[:150] or os.path.splitext(fname)[0][:150]
                    if len(bk_.file_list(n))>=bk_.MAX_FILES: self._json({'ok':False,'error':'Bitta elementga %d tadan ko‘p fayl qo‘shib bo‘lmaydi.'%bk_.MAX_FILES},400); return
                    _dd=bk_.get_detail(n); _cfg=bk_.COLLECTIONS.get(_dd['sec'] if _dd else 'esse',{})
                    try: tid_,sz_,mm_=tg_send_document(ADMIN_ID,fname,raw,'📎 %s\n%s %s • %s\n✅ Bazaga saqlandi (Mini App orqali yuklandi).'%(title,_cfg.get('ico',''),_cfg.get('title',''),(_dd or {}).get('title','')))
                    except Exception as e:
                        logger.warning('pdf upload to telegram failed: %s',e); self._json({'ok':False,'error':'Faylni botga yuborib bo‘lmadi. Botga /start yozib, qayta urinib ko‘ring. (%s)'%str(e)[:120]},502); return
                    finally: raw=None
                    fid_=bk_.add_file(n,tid_,title,mm_ or 'application/pdf',sz_)
                    if fid_ is None: self._json({'ok':False,'error':'Fayllar soni chegaradan oshdi.'},400); return
                    self._json({'ok':True,'id':fid_,'files':bk_.file_list(n)}); return
                if act in('filemode','rmfile','mvfile','renfile'):
                    if bk_.get_sec(n) not in bk_.FILE_SECS: self._json({'ok':False,'error':'Fayllar bu bo‘limda qo‘llab-quvvatlanmaydi.'},400); return
                    if act=='filemode':
                        _BOOKS_STATE[ADMIN_ID]={'mode':'gfile','n':n,'title':str(body.get('title','')).strip()[:150],'count':0}
                        self._json({'ok':True}); return
                    try: xid=int(body.get('id') or 0)
                    except Exception: xid=0
                    if act=='rmfile': ok=bk_.delete_file(n,xid)
                    elif act=='mvfile': ok=bk_.move_file(n,xid,int(body.get('dir') or 1))
                    else: ok=bk_.rename_file(n,xid,str(body.get('title','')))
                    self._json({'ok':ok,'error':'' if ok else 'Bajarilmadi.','files':bk_.file_list(n)}); return
                if act in('vidmode','rmvideo','mvvideo','renvideo'):
                    if act=='vidmode':
                        _BOOKS_STATE[ADMIN_ID]={'mode':'video','n':n,'title':str(body.get('title','')).strip()[:150],'count':0}
                        self._json({'ok':True}); return
                    try: xid=int(body.get('id') or 0)
                    except Exception: xid=0
                    if act=='rmvideo': ok=bk_.delete_video(n,xid)
                    elif act=='mvvideo': ok=bk_.move_video(n,xid,int(body.get('dir') or 1))
                    else: ok=bk_.rename_video(n,xid,str(body.get('title','')))
                    self._json({'ok':ok,'error':'' if ok else 'Bajarilmadi.','videos':bk_.video_list(n)}); return
                if act in('rmpic','rmslide','mvslide','capslide','rename','delitem'):
                    try: xid=int(body.get('id') or 0)
                    except Exception: xid=0
                    if act=='rmpic': ok=bk_.delete_pic(n,xid)
                    elif act=='rmslide': ok=bk_.delete_slide(n,xid)
                    elif act=='mvslide': ok=bk_.move_slide(n,xid,int(body.get('dir') or 1))
                    elif act=='capslide': ok=bk_.set_slide_caption(n,xid,str(body.get('caption','')))
                    elif act=='rename':
                        t=str(body.get('title','')).strip()
                        ok=bool(t) and bk_.rename(n,t)
                    else: ok=bk_.delete(n)
                    self._json({'ok':ok,'error':'' if ok else 'Bajarilmadi.','pics':bk_.pic_ids(n) if act!='delitem' else [],'slides':bk_.slide_list(n) if act!='delitem' else []}); return
                if act=='info':
                    secs={k:str(body.get(k,'')) for k in bk_.SECTION_KEYS if k in body}
                    bk_.set_sections(n,secs,author=(str(body['author']) if 'author' in body else None))
                    self._json({'ok':True,'sections':bk_.get_sections(n),'author':bk_.get_detail(n)['author']}); return
                kind=str(body.get('kind') or 'closed')
                if kind not in bk_.KINDS: self._json({'ok':False,'error':'Test turi noto‘g‘ri.'},400); return
                if act=='docx':
                    import base64
                    b64=str(body.get('file','') or '')
                    if ',' in b64[:80]: b64=b64.split(',',1)[1]
                    try: raw=base64.b64decode(b64)
                    except Exception: self._json({'ok':False,'error':'Fayl o‘qilmadi.'},400); return
                    try: txt,warns=qr_.docx_to_text(raw,uid)
                    except ValueError as e: self._json({'ok':False,'error':str(e)},400); return
                    qs,errs=bk_.parse_bulk(txt[:400000],kind)
                    if not qs: self._json({'ok':False,'error':'Savol topilmadi. Word’da «1. Savol / A) ... / Javob: B» ko‘rinishida yozing (har bir savol yangi qatordan).'},400); return
                    if errs: self._json({'ok':False,'error':'Hech narsa saqlanmadi:\n'+'\n'.join(errs[:8])},400); return
                    if bk_.question_count(n,kind)+len(qs)>bk_.MAX_Q_PER_KIND: self._json({'ok':False,'error':f'Bitta testda {bk_.MAX_Q_PER_KIND} tadan ko‘p savol bo‘lmasin.'},400); return
                    bk_.add_questions(n,qs,kind=kind); self._json({'ok':True,'added':len(qs),'count':bk_.question_count(n,kind),'warnings':warns}); return
                if act=='add':
                    opts=[str(x) for x in (body.get('options') or [])][:10]
                    ok,r=bk_.add_question(n,kind,str(body.get('text','')),opts,str(body.get('answer','')),str(body.get('explanation','')))
                    self._json({'ok':True,'count':r} if ok else {'ok':False,'error':r}, 200 if ok else 400); return
                if act=='bulk':
                    qs,errs=bk_.parse_bulk(str(body.get('text',''))[:60000],kind)
                    if not qs: self._json({'ok':False,'error':'Savol topilmadi. Namunadagi ko‘rinishda yozing.'},400); return
                    if errs: self._json({'ok':False,'error':'Hech narsa saqlanmadi:\n'+'\n'.join(errs[:8])},400); return
                    if bk_.question_count(n,kind)+len(qs)>bk_.MAX_Q_PER_KIND: self._json({'ok':False,'error':f'Bitta testda {bk_.MAX_Q_PER_KIND} tadan ko‘p savol bo‘lmasin.'},400); return
                    bk_.add_questions(n,qs,kind=kind); self._json({'ok':True,'added':len(qs),'count':bk_.question_count(n,kind)}); return
                if act=='delete':
                    try: ok=bk_.delete_question(n,int(body.get('id')))
                    except Exception: ok=False
                    self._json({'ok':ok,'error':'' if ok else 'Savol topilmadi.'}); return
                if act=='clear':
                    self._json({'ok':True,'deleted':bk_.clear_questions(n,kind)}); return
                self._json({'ok':False,'error':'Noma‘lum amal.'},404); return
            if self.path=='/api/esse/video/open':   # v73: admin Videodarsni ochadi/yopadi
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                mp.set_setting('esse_video_open','1' if body.get('open') else '0'); self._json({'ok':True,'open':_esse_video_open()}); return
            if self.path=='/api/books/ready':
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                mp.set_books_ready(bool(body.get('ready'))); self._json({'ok':True,'ready':mp.books_ready()}); return
            if self.path=='/api/gazal/file/send':
                if not uid: self._json({'ok':False,'error':'Telegram orqali oching.'},401); return
                try: fid=int(body.get('id') or 0)
                except Exception: fid=0
                f=bk_.get_file(fid)
                _fs=bk_.get_sec(f['book_id']) if f else None
                if not f or _fs not in bk_.FILE_SECS: self._json({'ok':False,'error':'Fayl topilmadi.'},404); return
                if _fs!='gazal':   # v70: Esse / Attestatsiya — bo'limga kirish huquqi bor foydalanuvchiga (esse: Premium, attestatsiya: hozircha admin)
                    if not (self._coll_full_access(uid,_fs,f['book_id']) and self._books_extra_access(uid,_fs,f['book_id'])): self._json({'ok':False,'error':'🔒 Bu bo‘lim yopiq yoki Premium talab qilinadi.'},403); return
                elif not self._gazal_owns(uid,f['book_id']): self._json({'ok':False,'error':'🔒 Bu qo‘llanma hali sotib olinmagan (%s so‘m). Qo‘llanma sahifasidagi «Sotib olish» tugmasini bosing.'%mp.fmt_uzs(bk_.item_price(f['book_id']))},403); return
                if not self._is_admin(uid) and not (mx.allow('gfile:%s'%uid,25,3600) and mx.allow('gfileday:%s'%uid,80,86400)): self._json({'ok':False,'error':'Juda ko‘p so‘rov. Birozdan keyin urinib ko‘ring.'},429); return
                _d=bk_.get_detail(f['book_id'])
                try:
                    r=tg_api('sendDocument',{'chat_id':int(uid),'document':f['file_id'],'caption':('📎 '+f['title']+'\n'+bk_.COLLECTIONS[_fs]['ico']+' '+(_d['title'] if _d else '')+'\n\n🔒 Fayl faqat shu bot ichida foydalanish uchun. Tarqatish taqiqlanadi.')[:1000],'protect_content':True})
                    if not r.get('ok'): raise RuntimeError(str(r.get('description')))
                except Exception as e:
                    logger.warning('gazal file send failed: %s',e); self._json({'ok':False,'error':'Fayl yuborib bo‘lmadi. Avval botga /start yozing va qayta urinib ko‘ring.'},502); return
                self._json({'ok':True}); return
            if self.path=='/api/books/video/send':
                if not uid: self._json({'ok':False,'error':'Telegram orqali oching.'},401); return
                try: vid=int(body.get('id') or 0)
                except Exception: vid=0
                v=bk_.get_video(vid)
                if not v: self._json({'ok':False,'error':'Video topilmadi.'},404); return
                if v['book_id']==ESSE_VIDEO_N:   # v73: Esse -> Videodars: Premium obunachi + admin ochgan bo'lsa
                    if not self._is_admin(uid):
                        if not growth_premium_active(uid): self._json({'ok':False,'error':'🔒 Videodarslar Premium obunachilar uchun.'},403); return
                        if not _esse_video_open(): self._json({'ok':False,'error':'Videodarslar tez orada ochiladi.'},403); return
                        if not mx.allow('vidsend:%s'%uid,40,3600): self._json({'ok':False,'error':'Juda ko‘p so‘rov. Birozdan keyin urinib ko‘ring.'},429); return
                    try:
                        _m='sendDocument' if v['kind']=='document' else 'sendVideo'; _f='document' if v['kind']=='document' else 'video'
                        _pl={'chat_id':int(uid),_f:v['file_id'],'caption':('🎬 '+v['title'])[:1000],'protect_content':True}
                        if _m=='sendVideo': _pl['supports_streaming']=True
                        tg_api(_m,_pl)
                    except Exception as e:
                        logger.warning('esse video send failed: %s',e); self._json({'ok':False,'error':'Video yuborib bo‘lmadi. Avval botga /start yozing.'},502); return
                    self._json({'ok':True}); return
                _d=bk_.get_detail(v['book_id'])
                _gz=bool(_d and _d['sec']=='gazal')
                if not _d or not (self._coll_full_access(uid,_d['sec'],_d['n']) and self._books_extra_access(uid,_d['sec'],_d['n']) and (_gz or self._books_paid(uid))):
                    self._json({'ok':False,'error':('🔒 Bu qo‘llanma hali sotib olinmagan (%s so‘m). Qo‘llanma sahifasidagi «Sotib olish» tugmasini bosing.'%mp.fmt_uzs(bk_.item_price(_d['n']))) if _gz else 'Bu bo‘lim yopiq yoki to‘lov qilinmagan.'},403); return
                if not self._is_admin(uid) and not mx.allow('vidsend:%s'%uid,40,3600): self._json({'ok':False,'error':'Juda ko‘p so‘rov. Birozdan keyin urinib ko‘ring.'},429); return
                try:
                    _m='sendDocument' if v['kind']=='document' else 'sendVideo'
                    _f='document' if v['kind']=='document' else 'video'
                    tg_api(_m,{'chat_id':int(uid),_f:v['file_id'],'caption':('🎬 '+v['title']+'\n'+_d['title'])[:1000],'protect_content':True,'supports_streaming':True} if _m=='sendVideo' else {'chat_id':int(uid),_f:v['file_id'],'caption':('🎬 '+v['title'])[:1000],'protect_content':True})
                except Exception as e:
                    logger.warning('video send failed: %s',e); self._json({'ok':False,'error':'Video yuborib bo‘lmadi. Avval botga /start yozing.'},502); return
                self._json({'ok':True}); return
            if self.path in ('/api/qimg/upload','/api/simple/docx'):
                if self.path=='/api/qimg/upload' and not self._is_admin(uid): self._json({'ok':False,'error':'Rasm yuklash faqat admin uchun.'},403); return
                if not (self._is_admin(uid) or not TEST_CREATE_ADMIN_ONLY): self._json({'ok':False,'error':'Test yaratish ruxsati yo‘q.'},403); return
                if not self._is_admin(uid) and not mx.allow('qimg:%s'%uid,40,3600): self._json({'ok':False,'error':'Soatiga juda ko‘p yuklash. Keyinroq urinib ko‘ring.'},429); return
                import base64
                b64=str(body.get('image' if self.path=='/api/qimg/upload' else 'file','') or '')
                if ',' in b64[:80]: b64=b64.split(',',1)[1]
                try: raw=base64.b64decode(b64)
                except Exception: self._json({'ok':False,'error':'Fayl o‘qilmadi.'},400); return
                if self.path=='/api/qimg/upload':
                    if not raw or len(raw)>8000000: self._json({'ok':False,'error':'Rasm yuboring (8 MB gacha).'},400); return
                    try: iid=qr_.add_image(raw,uid)
                    except ValueError as e: self._json({'ok':False,'error':str(e)},400); return
                    self._json({'ok':True,'id':iid}); return
                try: txt,warns=qr_.docx_to_text(raw,uid,allow_images=self._is_admin(uid))
                except ValueError as e: self._json({'ok':False,'error':str(e)},400); return
                qs,errs=bk_.parse_bulk(txt[:400000],'closed')
                if not qs: self._json({'ok':False,'error':'Savol topilmadi. Word’da «1. Savol / A) ... / Javob: B» ko‘rinishida yozing.'},400); return
                if errs: self._json({'ok':False,'error':'Hech narsa qo‘shilmadi:\n'+'\n'.join(errs[:8])},400); return
                self._json({'ok':True,'questions':qs,'warnings':warns}); return
            if self.path=='/api/simple/create':
                if not uid: self._json({'ok':False,'error':'Foydalanuvchi aniqlanmadi.'},400); return
                title=str(body.get('title','')).strip()[:120]
                if not title: self._json({'ok':False,'error':'Test nomini kiriting.'},400); return
                if not self._is_admin(uid):
                    if not mx.allow('screate:%s'%uid,3,3600) or st_.count_recent(uid,1)>=3: self._json({'ok':False,'error':'Soatiga 3 tadan ko‘p test yaratib bo‘lmaydi.'},429); return
                    if st_.count_recent(uid,24)>=5: self._json({'ok':False,'error':'Bir kunda 5 tadan ko‘p test yaratib bo‘lmaydi.'},429); return
                qs,err=st_.validate(body.get('questions'))
                if err: self._json({'ok':False,'error':err},400); return
                code=st_.create(title,str(body.get('subject','')).strip()[:80],qs,uid)
                tr_.set_deadline('simple',code,_deadline_hours(body,self._is_admin(uid)))
                if not self._is_admin(uid):
                    nm=mx.user_name(uid)
                    threading.Thread(target=lambda: tg_api('sendMessage',{'chat_id':ADMIN_ID,'text':f"🆕 Yangi oddiy test\n\nNomi: {title}\nKod: {code}\nSavollar: {len(qs)}\nMuallif: {nm} (ID {uid})\n\nMini App → Diagnostik test → Oddiy testlar orqali ko‘rib, kerak bo‘lsa o‘chiring. Bloklash: /ban {uid}"}),daemon=True).start()
                self._json({'ok':True,'code':code,'count':len(qs)}); return
            if self.path=='/api/simple/delete':
                self._json({'ok':st_.delete(str(body.get('code','')),by=uid,admin=self._is_admin(uid))}); return
            if self.path=='/api/simple/submit':
                if not uid: self._json({'ok':False,'error':'Foydalanuvchi aniqlanmadi.'},400); return
                if not self._is_admin(uid) and not mx.allow('ssubmit:%s'%uid,20,600): self._json({'ok':False,'error':'Juda tez-tez topshiryapsiz. Biroz kuting.'},429); return
                ans=body.get('answers') or {}
                if not isinstance(ans,dict) or len(json.dumps(ans))>20000: self._json({'ok':False,'error':'Javoblar noto‘g‘ri.'},400); return
                t=st_.get(str(body.get('code','')))
                if not t: self._json({'ok':False,'error':'Test topilmadi'},404); return
                if tr_.is_closed('simple',t['code']): self._json({'ok':False,'error':'Bu test yakunlangan, endi javob qabul qilinmaydi.'},410); return
                res=st_.grade(t,ans,uid,allow_repeat=self._is_admin(uid))
                if res is None: self._json({'ok':False,'already':True,'error':'Siz bu testni allaqachon ishlagansiz. Test faqat bir marta topshiriladi.'},409); return
                threading.Thread(target=notify_creator_attempt,args=('simple',t['code'],uid,f"Natija: {res['correct']}/{res['total']} ({res['percent']}%)"),daemon=True).start()
                self._json({'ok':True,**res,**after_submit(uid,'simple',t['code'])}); return
            if self.path=='/api/national/delete':
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin o‘chira oladi.'},403); return
                delete_test_by_code(str(body.get('code',''))); self._json({'ok':True}); return
            if self.path in ('/api/mock/pdf/up','/api/mock/pdf/del','/api/mock/pdf/blast','/api/mock/pdf/send'):   # v74: mock testining PDF varianti
                try: _mr=mk_.get(int(body.get('id') or 0))
                except Exception: _mr=None
                if not _mr: self._json({'ok':False,'error':'Mock topilmadi.'},404); return
                def _pdf_cap(f): return '📄 '+f['title']+'\n🎯 '+_mr['title']+'\n\n🔒 Fayl faqat shu bot ichida foydalanish uchun. Tarqatish taqiqlanadi.'
                if self.path=='/api/mock/pdf/send':   # foydalanuvchi o'zi oladi (ro'yxatdan o'tgan + mock ochiq)
                    if not uid: self._json({'ok':False,'error':'Telegram orqali oching.'},401); return
                    if not mk_.pdf_visible(uid,_mr,self._is_admin(uid)): self._json({'ok':False,'error':'PDF faqat ro‘yxatdan o‘tganlarga, mock ochiq paytda beriladi.'},403); return
                    try: _f=mk_.pdf_get(int(body.get('pdf') or 0))
                    except Exception: _f=None
                    if not _f or _f['mock_id']!=_mr['id']: self._json({'ok':False,'error':'PDF topilmadi.'},404); return
                    if not self._is_admin(uid) and not mx.allow('mockpdf:%s'%uid,20,3600): self._json({'ok':False,'error':'Juda ko‘p so‘rov. Birozdan keyin urinib ko‘ring.'},429); return
                    try:
                        r=tg_api('sendDocument',{'chat_id':int(uid),'document':_f['file_id'],'caption':_pdf_cap(_f)[:1000],'protect_content':True})
                        if not r.get('ok'): raise RuntimeError(str(r.get('description')))
                        mk_.pdf_sent_mark(_f['id'],uid)
                    except Exception as e:
                        logger.warning('mock pdf send failed: %s',e); self._json({'ok':False,'error':'PDF yuborib bo‘lmadi. Avval botga /start yozing va qayta urinib ko‘ring.'},502); return
                    self._json({'ok':True}); return
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                if self.path=='/api/mock/pdf/up':
                    import base64
                    b64=str(body.get('file','') or ''); body['file']=''
                    if ',' in b64[:80]: b64=b64.split(',',1)[1]
                    try: raw=base64.b64decode(b64)
                    except Exception: self._json({'ok':False,'error':'Fayl o‘qilmadi.'},400); return
                    del b64
                    if not raw or len(raw)>bk_.PDF_MAX_BYTES: self._json({'ok':False,'error':'PDF hajmi %d MB dan oshmasin.'%(bk_.PDF_MAX_BYTES//1048576)},400); return
                    if raw[:5]!=b'%PDF-': self._json({'ok':False,'error':'Bu PDF fayl emas. Faqat .pdf yuklang.'},400); return
                    if len(mk_.pdf_list(_mr['id']))>=mk_.MAX_PDFS: self._json({'ok':False,'error':'Bitta mockka %d tadan ko‘p PDF qo‘shib bo‘lmaydi.'%mk_.MAX_PDFS},400); return
                    fname=(str(body.get('name') or 'test.pdf').strip() or 'test.pdf')
                    if not fname.lower().endswith('.pdf'): fname+='.pdf'
                    title=str(body.get('title') or '').strip()[:150] or os.path.splitext(fname)[0][:150]
                    try: tid_,sz_,mm_=tg_send_document(ADMIN_ID,fname,raw,'📄 %s\n🎯 %s\n✅ Mock test PDF saqlandi.'%(title,_mr['title']))
                    except Exception as e:
                        logger.warning('mock pdf upload failed: %s',e); self._json({'ok':False,'error':'Faylni botga yuborib bo‘lmadi. Botga /start yozib, qayta urinib ko‘ring. (%s)'%str(e)[:120]},502); return
                    finally: raw=None
                    pid_=mk_.pdf_add(_mr['id'],tid_,title,sz_)
                    if pid_ is None: self._json({'ok':False,'error':'PDF soni chegaradan oshdi.'},400); return
                    self._json({'ok':True,'id':pid_,'pdfs':mk_.pdf_list(_mr['id'])}); return
                if self.path=='/api/mock/pdf/del':
                    try: ok=mk_.pdf_del(_mr['id'],int(body.get('pdf') or 0))
                    except Exception: ok=False
                    self._json({'ok':ok,'error':'' if ok else 'Bajarilmadi.','pdfs':mk_.pdf_list(_mr['id'])}); return
                if self.path=='/api/mock/pdf/blast':   # ro'yxatdan o'tganlarga yuborish (har bir PDF har kimga bir martadan)
                    if mk_._now()>=mk_._parse(_mr['closes_at']): self._json({'ok':False,'error':'Mock yakunlangan.'},400); return
                    _pdfs=mk_.pdf_list(_mr['id'])
                    if not _pdfs: self._json({'ok':False,'error':'Avval PDF yuklang.'},400); return
                    _jobs=[(mk_.pdf_get(x['id']),mk_.pdf_unsent(x['id'],_mr['id'])) for x in _pdfs]
                    _users={u for _,us in _jobs for u in us}
                    def _bg(jobs):
                        for f,us in jobs:
                            for u in us:
                                try:
                                    r=tg_api('sendDocument',{'chat_id':int(u),'document':f['file_id'],'caption':_pdf_cap(f)[:1000],'protect_content':True})
                                    if r.get('ok'): mk_.pdf_sent_mark(f['id'],u)
                                    time.sleep(0.06)
                                except Exception: pass
                    threading.Thread(target=_bg,args=(_jobs,),daemon=True).start()
                    self._json({'ok':True,'sent':len(_users),'registered':len(mk_.regs_of(_mr['test_code']))}); return
            if self.path=='/api/mock/publish':   # v68: natijalarni e'lon qilish (faqat mock yopilgach)
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                _mr=mk_.get(int(body.get('id') or 0))
                if not _mr or not _mr['test_code']: self._json({'ok':False,'error':'Mock topilmadi.'},404); return
                if mk_._now()<mk_._parse(_mr['closes_at']): self._json({'ok':False,'error':'Natijalarni mock YOPILGANDAN keyin e‘lon qilish mumkin.'},400); return
                if (_mr['published_at'] or '').strip(): self._json({'ok':False,'error':'Natijalar allaqachon e‘lon qilingan.'},400); return
                self._json({'ok':True,'participants':publish_mock_results(_mr)}); return
            if self.path=='/api/mock/remind':   # v67: qatnashmaganlarga eslatma (mock ochiq bo'lsa)
                if not self._is_admin(uid): self._json({'ok':False,'error':'Faqat admin.'},403); return
                _mr=mk_.get(int(body.get('id') or 0))
                if not _mr or not _mr['test_code']: self._json({'ok':False,'error':'Mock topilmadi.'},404); return
                if not (mk_._parse(_mr['opens_at'])<=mk_._now()<mk_._parse(_mr['closes_at'])): self._json({'ok':False,'error':'Eslatma faqat mock ochiq paytda yuboriladi.'},400); return
                _t=get_test(_mr['test_code']); _a=tp_.analytics('ms',_mr['test_code']); _done={p['user_id'] for p in (_a or {}).get('people',[])} if _a and not _a.get('empty') else set()
                _todo=[u for u in mk_.regs_of(_mr['test_code']) if u not in _done]
                def _bg(ids,title,close):
                    for u in ids:
                        try: tg_api('sendMessage',{'chat_id':int(u),'text':f'⏰ «{title}» mocki hozir OCHIQ!\nYopilish: {close}\nMini App → Mock → ▶ Boshlash. Esse majburiy.'}); time.sleep(0.05)
                        except Exception: pass
                threading.Thread(target=_bg,args=(_todo,_mr['title'],_mr['closes_at']),daemon=True).start()
                self._json({'ok':True,'sent':len(_todo)}); return
            if self.path.startswith('/api/hub/'):
                _r=lh_.handle_post(self.path,uid,body)
                if _r is not None: self._json(_r[0],_r[1]); return
            if self.path.startswith('/api/mock/'):
                _r=mk_.handle_post(self.path,uid,self._is_admin(uid),body)
                if _r is not None: self._json(_r[0],_r[1]); return
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
                    for _k in ('answers','a_answers','b_answers'):
                        if _k in q: q[_k]=split_alts(q.get(_k))
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
                    tx=str(q.get('text','')).strip()[:6000]
                    if tx: q['text']=tx
                    else: q.pop('text',None)
                code=create_test(title,questions,uid,subject=str(body.get('subject','Ona tili va adabiyot')),duration=int(body.get('duration_min',180)),publish=1,essay_topic=essay_topic)
                if not self._is_admin(uid):
                    nm=mx.user_name(uid)
                    threading.Thread(target=lambda: tg_api('sendMessage',{'chat_id':ADMIN_ID,'text':f"🆕 Yangi foydalanuvchi testi\n\nNomi: {title}\nKod: {code}\nMuallif: {nm} (ID {uid})\n\nMini App → Admin panelda ko‘rib, kerak bo‘lsa o‘chiring yoki muallifni bloklang."}),daemon=True).start()
                tr_.set_deadline('ms',code,_deadline_hours(body,self._is_admin(uid)))
                self._json({'ok':True,'code':code}); return
            if self.path!='/api/national/submit': self._json({'ok':False,'error':'Not found'},404); return
            code=str(body.get('code','')).upper().strip(); answers=body.get('answers') or {}
            if not isinstance(answers,dict) or len(json.dumps(answers))>20000: self._json({'ok':False,'error':'Javoblar noto‘g‘ri.'},400); return
            if not self._is_admin(uid) and not mx.allow('submit:%s'%uid,10,600): self._json({'ok':False,'error':'Juda tez-tez topshiryapsiz. Biroz kuting.'},429); return
            t=get_test(code)
            if not t:self._json({'ok':False,'error':'Test topilmadi'},404); return
            if tr_.is_closed('ms',t['code']): self._json({'ok':False,'error':'Bu test yakunlangan, endi javob qabul qilinmaydi.'},410); return
            _gt=mk_.test_gate(code,uid,self._is_admin(uid),submit=True)
            if _gt is not None: self._json(_gt[0],_gt[1]); return
            if not self._is_admin(uid) and national_has_attempt(uid,t['id']): self._json({'ok':False,'already':True,'error':'Siz bu testni allaqachon ishlagansiz. Test faqat bir marta topshiriladi.'},409); return
            raw,score,errors,maxp=grade_national(t,answers)
            _mk_row=None if self._is_admin(uid) else mk_.by_code(code); essay_pending=False
            em=str(body.get('essay_mode','auto'))
            if _mk_row is not None:   # v67: MOCK — esse MAJBURIY; qo'lda ball ham, «esse'siz» ham yo'q. Esse: bot (AI) yoki ekspert orqali
                if em in ('manual','none'): self._json({'ok':False,'error':'Mock testida esse majburiy: bepul AI (1 martalik) yoki ekspert tekshiruvidan birini tanlang. Esse balli bo‘lmasa test natijasi hisoblanmaydi.'},400); return
                if em=='expert':
                    _ej=mk_.expert_job_for(uid,t['code'])
                    if not _ej: self._json({'ok':False,'error':'Avval esseni ekspertga yuboring (botda), keyin testni yakunlang.'},400); return
                    _sc=mk_.expert_score_get(t['code'],uid)
                    if _sc is None: essay=None; essay_pending=True
                    else: essay={'id':_save_expert_check(uid,t,_sc,_ej),'total':_sc}
                else:
                    essay=essay_for_test(uid,t)
                    if not essay: self._json({'ok':False,'error':'Mock testi uchun esse majburiy: bepul AI (1 martalik) yoki ekspert tekshiruvidan birini tanlang. Esse balli bo‘lmasa test natijasi hisoblanmaydi.'},400); return
                    if not _essay_in_window(essay.get('id'),_mk_row): self._json({'ok':False,'error':'Mock uchun esseni test boshlangandan keyin yozishingiz kerak. Mavzuga yangi esse yozing.'},400); return
            elif em=='manual':
                mv=parse_manual_essay(body.get('essay_manual'))
                if mv is None: self._json({'ok':False,'error':'Esse balli 0 dan 24 gacha bo‘lishi kerak.'},400); return
                essay={'id':None,'total':mv,'manual':True}
            elif em=='none': essay=None
            else: essay=essay_for_test(uid,t)
            dr=diagnostic_result(t,uid,errors,essay)       # Rasch T (test) + esse (75 ballik jadval); umumiy = o'rtacha
            score=dr['test_t']; essay_score=dr['essay24']; combined=dr['combined']; lvl=dr['level']
            if not save_attempt(uid,t['id'],essay['id'] if essay else None,answers,raw,combined,lvl,errors,allow_repeat=self._is_admin(uid)): self._json({'ok':False,'already':True,'error':'Siz bu testni allaqachon ishlagansiz. Test faqat bir marta topshiriladi.'},409); return
            threading.Thread(target=notify_creator_attempt,args=('ms',t['code'],uid,f"Test: {raw}/{maxp} • umumiy: {round(float(combined),1)} • {lvl}"),daemon=True).start()
            cert_code=None
            try:
                cdata={'name':mx.user_name(uid),'subject':t.get('subject','Ona tili va adabiyot'),'score':round(float(combined),1),'level':lvl,'test_score':round(float(score),1),'essay':(round(float(essay_score),1) if essay_score is not None else '—'),'essay75':dr['essay_t'],'raw':raw,'max':maxp,'title':t['title'],'test_code':t['code'],'date':datetime.now(mx.TZ).strftime('%d.%m.%Y')}
                if lvl!='Sertifikat berilmadi' and _mk_row is None: cert_hold(t['code'],uid,cdata,lvl)   # sertifikat test YAKUNLANGANDAN keyin beriladi (MOCK: admin e'lon qilgach)
            except Exception as e: logging.warning('cert error: %s',e)
            if _mk_row is not None:   # v68: MOCK — admin e'lon qilguncha test va umumiy natija YASHIRIN; foydalanuvchi faqat esse ballini biladi
                _asub=after_submit(uid,'ms',t['code']); _asub.pop('rank',None)
                self._json({'ok':True,'is_mock':True,'hidden':True,'essay_score':essay_score,'essay_pending':essay_pending,'streak':_asub.get('streak')}); return
            self._json({'ok':True,'raw_score':raw,'max_score':maxp,'score_75':score,'combined_score_75':combined,'level':lvl,'errors':errors,'essay_score':essay_score,'essay_75':dr['essay_t'],'rasch':dr['rasch'],'cohort':dr['cohort'],'note':dr['note'],'essay_missing':bool(dr.get('essay_missing')),'essay_manual':bool(essay and essay.get('manual')),'essay_source':dr.get('essay_source','none'),'essay_topic':t.get('essay_topic',''),'cert_code':None,'cert_pending':lvl!='Sertifikat berilmadi','cert_eligible':lvl!='Sertifikat berilmadi','is_mock':_mk_row is not None,'essay_pending':essay_pending,'fan_report':tp_.fan_report(t['code'],uid),**after_submit(uid,'ms',t['code'])})
        except Exception as e: self._json({'ok':False,'error':str(e)},400)
    def log_message(self,*args): pass

def backup_db_file():
    """Bazaning izchil nusxasini vaqtinchalik FAYLGA yozadi (RAM'ga o'qimaydi). Fayl yo'lini qaytaradi; chaqiruvchi o'chiradi."""
    import tempfile
    fd,tmp=tempfile.mkstemp(suffix='.sqlite3'); os.close(fd)
    try:
        with DB_LOCK:
            src=sqlite3.connect(DB_PATH,timeout=30); dst=sqlite3.connect(tmp)
            src.backup(dst); dst.close(); src.close()
        return tmp
    except Exception:
        try: os.remove(tmp)
        except Exception: pass
        raise

def backup_db_bytes():
    """Faqat /restore xavfsizlik nusxasi uchun (kamdan-kam). Katta bazada RAM ishlatadi."""
    tmp=backup_db_file()
    try:
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
    init_db(); init_national_db(); init_prep_db(); mx.init_extra_db(); st_.init_simple_db(); tr_.init_results_db(); gt_.init_growth_db(); lh_.init(); ac_.init_cost_db(); bk_.init_books_db()

def _backup_name(): return 'esse_bot_%s.sqlite3'%datetime.now(mx.TZ).strftime('%Y%m%d_%H%M')

# ---------------------------------------------------------------- v42: disk va xotirani tejash (qo'shimcha xarajatsiz)
RETAIN_VIEWS_DAYS = int(os.getenv('RETAIN_VIEWS_DAYS','180') or 180)    # bo'lim ko'rishlari statistikasi
RETAIN_GAMES_DAYS = int(os.getenv('RETAIN_GAMES_DAYS','400') or 400)    # o'yin natijalari (seriya hisobi uchun uzoq saqlanadi)

def db_cleanup():
    """Eski statistika qatorlarini o'chiradi (reyting, to'lov, test, esse natijalariga TEGMAYDI). O'chirilgan qatorlar soni qaytadi."""
    from datetime import timedelta, timezone
    out={}
    with mx.db() as c:
        for tbl,days in (('section_views',RETAIN_VIEWS_DAYS),('game_plays',RETAIN_GAMES_DAYS)):
            try:
                cut=(datetime.now(mx.TZ)-timedelta(days=days)).strftime('%Y-%m-%d')
                out[tbl]=c.execute(f'DELETE FROM {tbl} WHERE day<?',(cut,)).rowcount
            except Exception as e: out[tbl]=0; (logging.warning('cleanup %s: %s',tbl,e) if 'no such table' not in str(e) else None)
        try: out['orders']=c.execute("DELETE FROM manual_orders WHERE status IN ('awaiting_proof','cancelled') AND created_at<?",((datetime.now(mx.TZ)-timedelta(days=30)).astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds')+'Z',)).rowcount
        except Exception as e: out['orders']=0; logging.warning('cleanup orders: %s',e)
        c.commit()
    return out

def db_report():
    """Disk va xotira holati: baza hajmi, bo'sh joy, eng katta jadvallar."""
    import shutil
    lines=[]
    try:
        sz=os.path.getsize(DB_PATH); lines.append(f'💾 Baza: {sz/1048576:.1f} MB ({DB_PATH})')
    except Exception: sz=0; lines.append(f'💾 Baza fayli topilmadi: {DB_PATH}')
    try:
        cp=mx.CACHE_DB_PATH
        if os.path.exists(cp): lines.append(f'🗂 Kesh bazasi: {os.path.getsize(cp)/1048576:.1f} MB')
    except Exception: pass
    try:
        du=shutil.disk_usage(os.path.dirname(os.path.abspath(DB_PATH)) or '.'); lines.append(f'📀 Disk: bo‘sh {du.free/1048576:.0f} MB / jami {du.total/1048576:.0f} MB')
    except Exception: pass
    try:
        rss=0
        with open('/proc/self/status') as f:
            for ln in f:
                if ln.startswith('VmRSS:'): rss=int(ln.split()[1])//1024
        if rss: lines.append(f'🧠 Xotira (RAM): {rss} MB')
    except Exception: pass
    try:
        with mx.db() as c:
            rows=c.execute('SELECT name, SUM(pgsize) s FROM dbstat WHERE name NOT LIKE \'sqlite_%\' GROUP BY name ORDER BY s DESC LIMIT 8').fetchall()
        if rows: lines.append('\n📊 Eng katta jadvallar:\n'+'\n'.join(f'• {r[0]}: {r[1]/1048576:.1f} MB' for r in rows))
    except Exception:
        try:
            with mx.db() as c:
                names=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                cnt=sorted(((n,c.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0]) for n in names),key=lambda x:-x[1])[:8]
            lines.append('\n📊 Eng ko‘p qatorli jadvallar:\n'+'\n'.join(f'• {n}: {k}' for n,k in cnt))
        except Exception: pass
    return '\n'.join(lines), sz

async def baza_cmd(update, context):
    if update.effective_user.id!=ADMIN_ID: return
    txt,_=await asyncio.to_thread(db_report)
    await update.message.reply_text(txt+'\n\n🧹 Tozalash: /tozala (eski statistikani o‘chiradi) • /tozala siq (bazani siqadi)')

async def tozala_cmd(update, context):
    """/tozala — eski statistikani o'chiradi. /tozala siq — VACUUM (bo'sh joy yetarli bo'lsa)."""
    if update.effective_user.id!=ADMIN_ID: return
    import shutil
    res=await asyncio.to_thread(db_cleanup)
    msg='🧹 O‘chirildi: '+', '.join(f'{k}: {v}' for k,v in res.items())
    if context.args and context.args[0].lower().startswith('siq'):
        try:
            sz=os.path.getsize(DB_PATH); free=shutil.disk_usage(os.path.dirname(os.path.abspath(DB_PATH)) or '.').free
            if free<sz*1.3+20*1048576: msg+=f'\n⚠️ Siqish uchun diskda joy yetmaydi (kerak ≈{sz*1.3/1048576:.0f} MB, bor {free/1048576:.0f} MB). Avval /backup oling.'
            else:
                def _vac():
                    with DB_LOCK:
                        cx=sqlite3.connect(DB_PATH,timeout=60); cx.isolation_level=None
                        try: cx.execute('VACUUM')
                        finally: cx.close()
                await asyncio.to_thread(_vac); msg+=f'\n✅ Baza siqildi: {sz/1048576:.1f} MB → {os.path.getsize(DB_PATH)/1048576:.1f} MB'
        except Exception as e: msg+=f'\n⚠️ Siqib bo‘lmadi: {e}'
    await update.message.reply_text(msg)

def start_cleanup_loop():
    """Har kuni bir marta eski statistikani tozalaydi (birinchisi 1 soatdan keyin)."""
    def run():
        time.sleep(3600)
        while True:
            try: logging.info('CLEANUP | %s',db_cleanup())
            except Exception as e: logging.warning('cleanup error: %s',e)
            time.sleep(86400)
    threading.Thread(target=run,daemon=True).start()

def start_backup_loop():
    """Har BACKUP_HOURS soatda (standart 24) bazani adminga Telegram orqali yuboradi. Birinchisi 30 daqiqadan keyin."""
    hours=float(os.getenv('BACKUP_HOURS','24') or 24)
    if hours<=0: return
    def run():
        time.sleep(1800)
        while True:
            try:
                tmp=backup_db_file()
                try:
                    if os.path.getsize(tmp)<45*1024*1024: mx.send_document_file(TELEGRAM_BOT_TOKEN,ADMIN_ID,_backup_name(),tmp,'💾 Avtomatik zaxira nusxa. Saqlab qo‘ying.')
                    else: logging.warning('backup: baza 45 MB dan katta, Telegram orqali yuborilmadi')
                finally:
                    try: os.remove(tmp)
                    except Exception: pass
            except Exception as e: logging.warning('backup error: %s',e)
            time.sleep(hours*3600)
    threading.Thread(target=run,daemon=True).start()

async def backup_cmd(update, context):
    if update.effective_user.id!=ADMIN_ID: return
    tmp=await asyncio.to_thread(backup_db_file)
    try:
        with open(tmp,'rb') as _bf:
            await update.message.reply_document(InputFile(_bf,filename=_backup_name()),caption='💾 Baza zaxira nusxasi. Saqlab qo‘ying.\n\nTiklash uchun shu faylni botga yuboring, izohiga yozing:\n/restore ha')
    finally:
        try: os.remove(tmp)
        except Exception: pass

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
    # Kanal postlari va kanaldan avtomatik ko'chirilgan xabarlarga bot umuman javob bermaydi
    if getattr(update,'channel_post',None) or getattr(update,'edited_channel_post',None): raise ApplicationHandlerStop
    _m=update.effective_message
    if _m is not None and (getattr(_m,'is_automatic_forward',False) or getattr(getattr(_m,'chat',None),'type','')=='channel'): raise ApplicationHandlerStop
    u=update.effective_user
    if u is not None: ac_.UID.set(int(u.id))
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

async def xatosavollar_cmd(update, context):
    """v72: savol sifati hisoboti (shikoyatlar va shubhali savollar). Faqat admin."""
    if update.effective_user.id!=ADMIN_ID: return
    try: await update.message.reply_text(lh_.report_text()[:3900])
    except Exception: logger.exception("xatosavollar_cmd"); await update.message.reply_text("⚠️ Hisobotni tayyorlab bo‘lmadi.")

async def savol_yashir_cmd(update, context):
    if update.effective_user.id!=ADMIN_ID: return
    try: qid=int(str(context.args[0]).lstrip('bB'))
    except Exception: await update.message.reply_text('Foydalanish: /savol_yashir <savol_id>'); return
    lh_.set_override(qid,True); await update.message.reply_text(f'🙈 Savol {qid} o‘yinlardan yashirildi (foydalanuvchilarda bir necha soat ichida yangilanadi).')

async def savol_och_cmd(update, context):
    if update.effective_user.id!=ADMIN_ID: return
    try: qid=int(str(context.args[0]).lstrip('bB'))
    except Exception: await update.message.reply_text('Foydalanish: /savol_och <savol_id>'); return
    lh_.set_override(qid,False); await update.message.reply_text(f'👁 Savol {qid} yana ko‘rsatiladi.')

async def unban_cmd(update, context):
    if update.effective_user.id!=ADMIN_ID: return
    try: tid=int(context.args[0])
    except Exception: await update.message.reply_text('Foydalanish: /unban <user_id>'); return
    mx.unban(tid); await update.message.reply_text(f'✅ {tid} blokdan chiqarildi.')

def start_memory_guard():
    """Har 5 daqiqada: gc.collect + malloc_trim (ishlatilmagan xotirani OT'ga qaytaradi) va RSS'ni logga yozadi.
    Render logida 'MEMORY | rss=...' qatorini kuzating: xotira qachon oshayotganini ko'rsatadi."""
    import gc, ctypes
    def rss_mb():
        try:
            for l in open('/proc/self/status'):
                if l.startswith('VmRSS:'): return int(l.split()[1]) // 1024
        except Exception: pass
        return 0
    SOFT=int(os.getenv('MEMORY_SOFT_MB','320') or 320); HARD=int(os.getenv('MEMORY_HARD_MB','450') or 450)
    def free_caches():
        try: HealthHandler._STATIC_CACHE.clear()
        except Exception: pass
        try:
            with CACHE_LOCK: CACHE.clear()
        except Exception: pass
        try: mx._png_cache.clear()
        except Exception: pass
        try:
            with mx._lock:
                mx._hits.clear(); mx._seen.clear()
        except Exception: pass
        try: ALBUM_BUFFERS.clear()
        except Exception: pass
    def trim():
        gc.collect()
        try: ctypes.CDLL('libc.so.6').malloc_trim(0)
        except Exception: pass
    def run():
        tick = 0
        while True:
            time.sleep(20); tick += 1
            try:
                r = rss_mb()
                if r >= HARD:
                    free_caches(); trim(); r2 = rss_mb()
                    if r2 >= HARD:
                        logger.error('MEMORY | rss=%s MB >= %s MB: bot xotira tugamasdan oldin qayta ishga tushirilyapti', r2, HARD)
                        time.sleep(1); os._exit(1)   # Render avtomatik qayta ishga tushiradi
                elif r >= SOFT:
                    free_caches(); trim()
                    logger.warning('MEMORY | rss=%s MB -> keshlar tozalandi, hozir %s MB', r, rss_mb())
                if tick % 15 == 0:   # har 5 daqiqada
                    before = rss_mb(); trim()
                    logger.info('MEMORY | rss=%s MB (tozalashdan oldin %s MB) | threads=%s', rss_mb(), before, threading.active_count())
            except Exception: pass
    threading.Thread(target=run, daemon=True).start()

class _BoundedHTTPServer(ThreadingHTTPServer):
    """Bir vaqtda ishlaydigan so'rovlar soni cheklangan (HTTP_MAX_THREADS, standart 24): xotira portlamasligi uchun."""
    daemon_threads=True
    request_queue_size=64
    _sem=threading.BoundedSemaphore(int(os.getenv('HTTP_MAX_THREADS','16') or 16))
    def process_request(self, request, client_address):
        if not self._sem.acquire(timeout=5):
            try: self.close_request(request)
            except Exception: pass
            return
        super().process_request(request, client_address)
    def process_request_thread(self, request, client_address):
        try: super().process_request_thread(request, client_address)
        finally: self._sem.release()

def start_health():
    _BoundedHTTPServer(("0.0.0.0",PORT),HealthHandler).serve_forever()

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


async def card_grant_loop(bot):
    """v58: SMS/provayder orqali avtomatik tasdiqlangan, lekin xizmati hali berilmagan buyurtmalarga xizmat beradi (har 5 soniyada; xato bo'lsa qayta urinadi)."""
    class _Ctx:  # _grant_manual_order faqat context.bot ishlatadi
        def __init__(self, b): self.bot = b
    ctx = _Ctx(bot)
    while True:
        try:
            await asyncio.sleep(5)
            for order in mp.ungranted_auto(10):
                oid = int(order["id"])
                if not mp.claim_grant(oid): continue
                try:
                    await _grant_manual_order(order, ctx)
                except Exception:
                    logger.exception("card_grant_loop: xizmat ochilmadi oid=%s", oid)
                    mp.release_grant(oid); await asyncio.sleep(30); continue
                uid = int(order["user_id"]); amount = int(order["amount"])
                if str(order["note"] or "").startswith("sms:"):
                    try: mp.record_commission(uid, f"sms:{oid}", amount)
                    except Exception: logger.exception("ustoz komissiyasi (sms)")
                    try: await bot.send_message(ADMIN_ID, f"💳 Karta avto-to‘lov #{oid}: {mp.plan_title(order['kind'], order['plan'])} — {mp.fmt_uzs(amount)} so‘m (id {uid})")
                    except Exception: pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("card_grant_loop")

async def configure_miniapp(application):
    global BOT_USERNAME
    try:
        if not BOT_USERNAME: BOT_USERNAME = (await application.bot.get_me()).username or ""
    except Exception:
        logger.exception("bot username aniqlanmadi")
    try:
        if pay_nudge is None: raise ImportError("pay_nudge.py topilmadi")
        asyncio.get_running_loop().create_task(pay_nudge.nudge_loop(application.bot, mp, pack_keyboard))
        logger.info("pay_nudge loop started")
    except Exception:
        logger.exception("pay_nudge start failed")
    try:
        asyncio.get_running_loop().create_task(card_grant_loop(application.bot))
        logger.info("card_grant_loop started")
    except Exception:
        logger.exception("card_grant_loop start failed")
    if not os.path.isabs(DB_PATH):
        try:
            await application.bot.send_message(ADMIN_ID, "⚠️ DIQQAT: baza yo‘li nisbiy (" + DB_PATH + "). Render'da doimiy Disk ulanmagan bo‘lsa, har deployda sotib olingan paketlar, to‘lovlar va foydalanuvchilar YO‘QOLADI.\n\nYechim: Render → Disk qo‘shing (mount: /var/data) va Environment'da BOT_DB_PATH=/var/data/esse_bot.sqlite3 deb qo‘ying.")
        except Exception:
            logger.exception("disk warning send failed")
    if miniapp_web_url():
        try:
            await application.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Milliy sertifikat", web_app=WebAppInfo(url=miniapp_web_url())))
            logger.info("Mini App menu button configured: %s", MINIAPP_URL)
        except Exception:
            logger.exception("Mini App menu button setup failed")

# ============================================================
# 💳 KARTA ORQALI TO‘LOV (chek skrini → admin tasdig‘i → avtomatik ochish)  va  🎁 REFERAL
# ============================================================
PAY_APPROVERS = {int(ADMIN_ID)} | {int(x) for x in re.findall(r"\d+", os.getenv("PAY_APPROVER_IDS", ""))}

def _esc(x):
    return _html.escape(str(x or ""))

def user_exists(uid):
    with DB_LOCK, db() as c:
        return c.execute("SELECT 1 FROM users WHERE user_id=?", (int(uid),)).fetchone() is not None

def _tashkent(iso):
    try:
        from datetime import timezone as _tz
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(mp.TZ).strftime("%d.%m %H:%M")
    except Exception:
        return iso or ""

def card_order_text(order_id, kind, plan, amount=None, discount=0):
    number, holder = mp.card_info()
    title = mp.plan_title(kind, plan); amount = amount if amount is not None else mp.plan_amount_uzs(kind, plan)
    if mp.card_auto_enabled():   # v58: admin kartasiga AVTOMATIK to'lov — chek shart emas
        return (
            "💳 <b>KARTA ORQALI TO‘LOV (avtomatik)</b>\n\n"
            f"📦 {_esc(title)}\n"
            f"💰 O‘tkazing: <b>{mp.fmt_uzs(amount)} so‘m</b>" + (f" (ustoz chegirmasi −{discount}%)" if discount else "") + "\n\n"
            f"Karta raqami (bosib nusxalang):\n<code>{_esc(mp.pretty_card(number))}</code>\n"
            + (f"👤 Karta egasi: {_esc(holder)}\n" if holder else "")
            + "\n1️⃣ Aynan <b>shu summani</b> (tiyinigacha emas, so‘mi bilan) o‘tkazing — summa sizning buyurtmangizni aniqlaydi.\n"
            "2️⃣ To‘lov tushishi bilan <b>xizmat avtomatik ochiladi</b> va sizga xabar keladi. Chek yuborish shart emas.\n\n"
            f"🧾 Buyurtma: #{order_id}\n"
            f"⏳ Summa {mp.PROOF_TTL_HOURS} soat davomida shu buyurtmaga biriktirilgan.\n"
            "⚠️ Summa boshqacha bo‘lsa, to‘lov avtomatik aniqlanmaydi. Bunday holda 2–3 daqiqa kutib, chek skrinshotini shu chatga yuboring — qo‘lda tekshiriladi."
        )
    return (
        "💳 <b>KARTA ORQALI TO‘LOV</b>\n\n"
        f"📦 {_esc(title)}\n"
        f"💰 Summa: <b>{mp.fmt_uzs(amount)} so‘m</b>" + (f" (ustoz chegirmasi −{discount}%)" if discount else "") + "\n\n"
        f"Karta raqami (bosib nusxalang):\n<code>{_esc(mp.pretty_card(number))}</code>\n"
        + (f"👤 Karta egasi: {_esc(holder)}\n" if holder else "")
        + "\n1️⃣ Yuqoridagi summani shu kartaga o‘tkazing.\n"
        "2️⃣ To‘lov <b>chekining skrinshotini</b> (rasm yoki PDF) shu chatga yuboring.\n"
        "3️⃣ To‘lov tekshiriladi — tasdiqlangach xizmat <b>avtomatik ochiladi</b>.\n\n"
        f"🧾 Buyurtma: #{order_id}\n"
        f"⏳ Chekni {mp.PROOF_TTL_HOURS} soat ichida yuboring.\n"
        "⚠️ Summa aniq bo‘lishi kerak. Soxta yoki takroriy chek tasdiqlanmaydi.\n"
        "📌 Esse rasm/PDF yubormoqchi bo‘lsangiz, avval ❌ Bekor qilish tugmasini bosing — aks holda u chek deb qabul qilinadi."
    )

async def start_card_order(message, context, uid, kind, plan):
    if not mp.valid_plan(kind, plan):
        await message.reply_text("⚠️ Paket topilmadi.", reply_markup=MAIN_KEYBOARD); return
    if kind == "mock" and uid != ADMIN_ID and mk_.has_access(uid, int(plan)) and mk_.pay_on():
        await message.reply_text("✅ Bu mock sizda allaqachon ochiq. Mini App → Mock.", reply_markup=MAIN_KEYBOARD); return
    if kind == "books" and mp.group_has(uid, "books"):
        await message.reply_text("✅ Badiiy asarlar bo‘limi sizda allaqachon ochiq. Mini App → Milliy sertifikatga tayyorlov → Badiiy asarlar.", reply_markup=MAIN_KEYBOARD); return
    if kind == "gazal_lib" and mp.group_has(uid, "gazal_lib"):
        await message.reply_text("✅ «G‘azal tahlilini o‘rganamiz» bo‘limi sizda allaqachon ochiq. Mini App → G‘azal tahlilini o‘rganamiz.", reply_markup=MAIN_KEYBOARD); return
    if kind == "gazal_item":
        if uid != ADMIN_ID and (mp.group_has(uid, "gazal_lib") or mp.group_has(uid, f"gzi{plan}")):
            await message.reply_text("✅ Bu qo‘llanma sizda allaqachon ochiq. Mini App → G‘azal tahlilini o‘rganamiz → qo‘llanmani oching, fayl shu bot chatiga yuboriladi.", reply_markup=MAIN_KEYBOARD); return
        if not mp.gazal_lib_open() and uid != ADMIN_ID:
            await message.reply_text("🚧 Bu bo‘lim hali ochilmagan. Tez orada!", reply_markup=MAIN_KEYBOARD); return
    if kind == "gazal_lib" and not mp.gazal_lib_open() and uid != ADMIN_ID:
        await message.reply_text("🚧 Bu bo‘lim hali ochilmagan. Tez orada!", reply_markup=MAIN_KEYBOARD); return
    if kind == "group" and mp.group_has(uid, plan):
        link = mp.group_link()
        await message.reply_text("✅ Siz G‘azal kursi guruhiga allaqachon qabul qilingansiz." + (f"\n\n👇 Guruh havolasi:\n{link}" if link else f"\n\nHavola uchun: @{ADMIN_USERNAME}"), reply_markup=MAIN_KEYBOARD); return
    if mp.auto_pay_enabled():   # v57: avtomatik karta to'lovi — chek ham, admin ham kerak emas
        try: await send_auto_invoice(context.bot, uid, kind, plan)
        except Exception:
            logger.exception("auto invoice"); await message.reply_text("⚠️ To‘lov oynasini ochib bo‘lmadi. Birozdan so‘ng qayta urinib ko‘ring.", reply_markup=MAIN_KEYBOARD)
        return
    number, _ = mp.card_info()
    if not number:
        await message.reply_text(f"⚠️ Karta orqali to‘lov hozircha sozlanmagan. Stars orqali to‘lang yoki adminga yozing: @{ADMIN_USERNAME}", reply_markup=MAIN_KEYBOARD)
        try: await context.bot.send_message(ADMIN_ID, "⚠️ Foydalanuvchi karta orqali to‘lamoqchi, lekin karta kiritilmagan!\nKiriting: /karta 8600123412341234 Ism Familiya")
        except Exception: pass
        return
    st, oid = mp.create_order(uid, kind, plan)
    if st == "limit":
        await message.reply_text("⏳ Sizda admin tekshiruvidagi to‘lovlar bor yoki bugungi buyurtma limiti tugagan. Avvalgi to‘lov tasdiqlanishini kuting yoki /paysupport.", reply_markup=MAIN_KEYBOARD); return
    if st != "ok":
        await message.reply_text("⚠️ Buyurtma yaratib bo‘lmadi.", reply_markup=MAIN_KEYBOARD); return
    for _k in ("stage", "growth_practice", "_pending_proof"): context.user_data.pop(_k, None)   # v58: esse bosqichi chek bilan aralashmasin
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cardcancel_{oid}")]])
    _o = mp.get_order(oid)
    await message.reply_text(card_order_text(oid, kind, plan, int(_o["amount"]), mp.student_discount(uid)), parse_mode="HTML", reply_markup=kb)

async def cardpay_callback(update, context):
    q = update.callback_query; uid = q.from_user.id
    m = re.match(r"^cardpay_(essay|tool|growth|group|books|gazallib|expert|teacher)_([pw][0-9]+|growth|gazal|all|e[13m]|pro)$", q.data or "")
    if not m:
        await q.answer(); return
    if m.group(1) == "expert" and m.group(2) == "em" and uid != ADMIN_ID and not mk_.promo_mock(uid):   # v67: aksiya faqat mock boshlangach va qatnashuvchiga
        await q.answer("Bu aksiya faqat Mock boshlangandan keyin, ro‘yxatdan o‘tganlar uchun.", show_alert=True); return
    if uid != ADMIN_ID and not await is_subscribed(uid, context.bot):
        await q.answer()
        await q.message.reply_text(SUBSCRIPTION_TEXT, reply_markup=subscription_keyboard()); return
    await q.answer()
    await start_card_order(q.message, context, uid, "gazal_lib" if m.group(1)=="gazallib" else m.group(1), m.group(2))

async def cardcancel_callback(update, context):
    q = update.callback_query; uid = q.from_user.id
    try: oid = int((q.data or "").split("_")[1])
    except Exception:
        await q.answer(); return
    ok = mp.cancel_order(oid, uid)
    await q.answer("Bekor qilindi." if ok else "Bu buyurtma allaqachon yopilgan.")
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    if ok: await q.message.reply_text("❌ Buyurtma bekor qilindi.", reply_markup=MAIN_KEYBOARD)

_PROOF_GROUPS = {}

class AwaitProofFilter(filters.MessageFilter):
    """Foydalanuvchi chek kutilayotgan buyurtmaga ega bo‘lsa, rasm/PDF esse emas, chek sifatida qabul qilinadi."""
    def filter(self, message):
        try:
            if not message.from_user: return False
            gid = getattr(message, "media_group_id", None)
            if gid and (message.from_user.id, gid) in _PROOF_GROUPS:
                return True   # chek albomining qolgan rasmlari esse sifatida ketmasin
            return bool(mp.awaiting_order(message.from_user.id))
        except Exception:
            return False

async def pay_proof_handler(update, context):
    m = update.message; u = update.effective_user; uid = u.id
    gid = getattr(m, "media_group_id", None)
    if gid:
        if (uid, gid) in _PROOF_GROUPS: return   # albomning 2-3-rasmi: birinchisi allaqachon qayta ishlangan
        if len(_PROOF_GROUPS) > 500: _PROOF_GROUPS.clear()
        _PROOF_GROUPS[(uid, gid)] = time.time()
    order = mp.awaiting_order(uid)
    if not order: return
    # v58: foydalanuvchi esse bosqichida bo'lsa — nima ekanini so'raymiz (chek o'rniga esse, esse o'rniga chek ketmasin)
    if context.user_data.get("stage") == "essay_ai" or context.user_data.get("growth_practice"):
        context.user_data["_pending_proof"] = m
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🧾 Bu to‘lov cheki", callback_data="proofis_chek")],
                                   [InlineKeyboardButton("📝 Bu esse", callback_data="proofis_esse")]])
        await m.reply_text("Bu fayl nima?\n\n🧾 To‘lov cheki — adminga tekshirishga yuboriladi.\n📝 Esse — esse sifatida tekshiriladi.", reply_markup=kb); return
    await _submit_proof(m, u, context, order)

async def proofis_callback(update, context):
    q = update.callback_query; uid = q.from_user.id
    m = context.user_data.pop("_pending_proof", None)
    await q.answer()
    try: await q.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    if m is None:
        await q.message.reply_text("⌛ Fayl topilmadi. Uni qaytadan yuboring."); return
    if q.data == "proofis_esse":
        is_pdf = bool(m.document and (m.document.mime_type or "") == "application/pdf")
        fake = Update(update.update_id, message=m)
        return await (handle_pdf if is_pdf else handle_photo)(fake, context)
    order = mp.awaiting_order(uid)
    if not order:
        await q.message.reply_text("⚠️ Buyurtma topilmadi yoki muddati o‘tgan. Qaytadan boshlang.", reply_markup=MAIN_KEYBOARD); return
    context.user_data.pop("stage", None); context.user_data.pop("growth_practice", None)
    await _submit_proof(m, q.from_user, context, order)

async def _submit_proof(m, u, context, order):
    uid = u.id; oid = order["id"]
    if m.photo:
        fid, uq, ptype = m.photo[-1].file_id, m.photo[-1].file_unique_id, "photo"
    elif m.document:
        if (m.document.file_size or 0) > 10 * 1024 * 1024:
            await m.reply_text("⚠️ Fayl juda katta (10 MB gacha)."); return
        fid, uq, ptype = m.document.file_id, m.document.file_unique_id, "document"
    else:
        return
    phash = None
    if ptype == "photo" or (m.document and (m.document.mime_type or "").startswith("image/")):
        try:
            f = await context.bot.get_file(fid)
            phash = mp.image_hash(await f.download_as_bytearray())
        except Exception:
            logger.exception("chek xeshi hisoblanmadi")
    res = mp.attach_proof(oid, fid, uq, ptype, phash)
    if res == "dup":
        await m.reply_text("⚠️ Bu chek avval yuborilgan (yoki juda o‘xshash). Yangi to‘lovning o‘z chekini yuboring.", reply_markup=MAIN_KEYBOARD); return
    if res != "ok":
        await m.reply_text("⚠️ Buyurtma topilmadi yoki muddati o‘tgan. Qaytadan boshlang.", reply_markup=MAIN_KEYBOARD); return
    title = mp.plan_title(order["kind"], order["plan"])
    uname = f"@{u.username}" if u.username else "—"
    caption = (f"💳 YANGI TO‘LOV #{oid}\n👤 {(u.full_name or '').strip()} ({uname})\n🆔 {uid}\n"
               f"📦 {title}\n💰 {mp.fmt_uzs(order['amount'])} so‘m\n🕒 {_tashkent(now_iso())}\n\n"
               "Chekdagi summa, vaqt va karta raqamini bank ilovangizda tekshiring.")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"payok_{oid}"),
                                InlineKeyboardButton("❌ Rad etish", callback_data=f"payno_{oid}")]])
    try:
        if ptype == "photo": sent = await context.bot.send_photo(ADMIN_ID, fid, caption=caption[:1024], reply_markup=kb)
        else: sent = await context.bot.send_document(ADMIN_ID, fid, caption=caption[:1024], reply_markup=kb)
        mp.set_admin_msg(oid, sent.message_id)
    except Exception:
        logger.exception("chekni adminga yuborib bo‘lmadi")
        mp.revert_to_awaiting(oid)
        await m.reply_text("⚠️ Chekni adminga yetkazib bo‘lmadi. Birozdan so‘ng qayta yuboring yoki /paysupport.", reply_markup=MAIN_KEYBOARD); return
    await m.reply_text(f"✅ Chek qabul qilindi (#{oid}).\n\nTekshiriladi. Tasdiqlangach xizmat avtomatik ochiladi va sizga xabar keladi. Odatda 5–30 daqiqa.", reply_markup=MAIN_KEYBOARD)

async def _send_gazal_item_files(context, uid, n):
    """To'lov tasdiqlangach papkadagi hamma faylni (protect_content bilan) foydalanuvchiga yuboradi."""
    d = bk_.get_detail(n)
    if not d: return
    for f in d["files"]:
        row = bk_.get_file(f["id"])
        if not row: continue
        try:
            await context.bot.send_document(uid, row["file_id"], caption=(f"📎 {row['title']}\n🌙 {d['title']}\n\n🔒 Fayl faqat shu bot ichida foydalanish uchun. Tarqatish taqiqlanadi.")[:1000], protect_content=True)
        except Exception:
            logger.exception("gazal fayl yuborilmadi uid=%s fid=%s", uid, f["id"])

async def _grant_manual_order(order, context):
    """Tasdiqlangan buyurtma bo‘yicha xizmatni ochadi va foydalanuvchiga xabar yuboradi."""
    uid = int(order["user_id"]); kind = order["kind"]; plan = order["plan"]; oid = order["id"]
    if kind == "teacher":
        until = tp_.grant_pro(uid, mp.TEACHER_PRO_DAYS, f"manual:{oid}")
        text = ("🎉 TO‘LOV TASDIQLANDI!\n\n🧑‍🏫 Ustoz Pro faollashdi — "+(until.strftime("%d.%m.%Y") if until else "")+" gacha.\n\n"
                "Mini App → Ustoz paneli: Milliy sertifikat va oddiy testlar bo‘yicha batafsil tahlil, sust savollar, ishtirokchilar jadvali va PDF hisobot.")
    elif kind == "gazal_lib":
        mp.group_add(uid, "gazal_lib", oid)
        text = ("🎉 TO‘LOV TASDIQLANDI!\n\n🌙 «G‘azal tahlilini o‘rganamiz» bo‘limi ochildi.\n\n"
                "Mini App → «G‘azal tahlilini o‘rganamiz» → kerakli qo‘llanmani tanlang va fayl sizga shu bot orqali yuboriladi.\n"
                "🔒 Fayllar faqat bot ichida foydalanish uchun: ularni boshqalarga yuborib bo‘lmaydi.")
    elif kind == "gazal_item":
        mp.group_add(uid, f"gzi{plan}", oid)
        _d = bk_.get_detail(int(plan)); _t = _d["title"] if _d else "qo‘llanma"
        text = (f"🎉 TO‘LOV TASDIQLANDI!\n\n🌙 «{_t}» ochildi.\n\n"
                "📎 Fayllar hozir shu chatga yuboriladi. Keyinroq ham: Mini App → G‘azal tahlilini o‘rganamiz → qo‘llanma.\n"
                "🎬 Videodarslar bo‘lsa, ularni ham shu yerdan olasiz.\n"
                "🔒 Fayllar faqat bot ichida foydalanish uchun: ularni boshqalarga yuborib bo‘lmaydi.")
    elif kind == "mock":
        mk_.grant(uid, int(plan))
        text = ("🎉 TO‘LOV TASDIQLANDI!\n\n📝 Mock imtihon ochildi: «" + mk_.title_of(int(plan)) + "».\n\n"
                "Mini App → Mock bo‘limiga kiring: vaqti kelganda «Mockni boshlash» tugmasi chiqadi.")
    elif kind == "books":
        mp.group_add(uid, "books", oid)
        text = ("🎉 TO‘LOV TASDIQLANDI!\n\n📚 Badiiy asarlar bo‘limi ochildi.\n\n"
                "Mini App → Milliy sertifikatga tayyorlov → «Badiiy asarlar» bo‘limiga kiring.")
    elif kind == "group":
        mp.group_add(uid, plan, oid)
        link = mp.group_link()
        if link:
            text = ("🎉 TO‘LOV TASDIQLANDI!\n\n🌙 G‘azal kursi guruhiga qabul qilindingiz.\n\n"
                    f"👇 Guruhga qo‘shilish havolasi:\n{link}\n\nXush kelibsiz! Mumtoz adabiyotni birga o‘rganamiz.")
        else:
            text = ("🎉 TO‘LOV TASDIQLANDI!\n\n🌙 G‘azal kursi guruhiga qabul qilindingiz.\n\n"
                    f"Guruh havolasi tez orada yuboriladi. Kechiksa: @{ADMIN_USERNAME}")
            try: await context.bot.send_message(ADMIN_ID, f"⚠️ G‘azal guruhi havolasi kiritilmagan! Foydalanuvchi {uid} to‘lovi tasdiqlandi. Havolani kiriting: /guruh https://t.me/+xxxx va foydalanuvchiga yuboring.")
            except Exception: pass
    elif kind == "growth":
        exp = grant_growth_premium(uid, mp.GROWTH_DAYS, f"manual:{oid}", 0)
        try: mp.add_credits(uid, "essay", mp.PREMIUM_BONUS_ESSAYS)
        except Exception: logger.exception("premium bonus esse (karta)")
        text = (f"🎉 TO‘LOV TASDIQLANDI!\n\n🌟 Premium {mp.GROWTH_DAYS} kunga faollashdi.\n"
                f"🎁 Sovg‘a: {mp.PREMIUM_BONUS_ESSAYS} ta esse tekshiruvi hisobingizga qo‘shildi.\n"
                f"📈 Kuniga {AI_PREMIUM_DAILY} ta AI mashq/dalil.\n⏳ Muddat: {exp.strftime('%d.%m.%Y %H:%M')} UTC")
    elif kind == "expert" and plan == "em":   # v67: Mock aksiyasi — faqat mock esselari uchun
        mx.grant_pack(uid, "expertm", f"manual:{oid}", 0, mp.EXPERT_PLANS["em"]["n"])
        text = ("🎉 TO‘LOV TASDIQLANDI!\n\n👨‍🏫 Mock uchun 1 ta ekspert tekshiruvi ochildi.\n\n"
                f"👇 Mock esseingizni yuborish uchun tugmani bosing. Ekspert {mp.EXPERT_HOURS} soat ichida tekshirib, balli bilan natijani shu chatga yuboradi.")
    elif kind == "expert":
        n = mp.EXPERT_PLANS[plan]["n"]
        mx.grant_pack(uid, "expert", f"manual:{oid}", 0, n)   # bir xil buyurtma ikki marta hisoblanmaydi
        text = (f"🎉 TO‘LOV TASDIQLANDI!\n\n👨‍🏫 {n} ta ekspert tekshiruvi ochildi.\n"
                f"💼 Hisobingizda: {mp.expert_balance(uid)} ta.\n\n"
                f"👇 Esseingizni yuborish uchun tugmani bosing. Ekspert esseni {mp.EXPERT_HOURS} soat ichida tekshirib, natijani shu chatga yuboradi.")
    elif mp.PACKS.get(plan, {}).get("days"):
        mx.grant_pass(uid, f"manual:{oid}", 0, mp.PACKS[plan]["days"])   # bir xil buyurtma ikki marta hisoblanmaydi
        text = "🎉 TO‘LOV TASDIQLANDI!\n\n" + pass_activated_text(uid)
    else:
        size = mp.PACKS[plan]["size"]
        mx.grant_pack(uid, kind, f"manual:{oid}", 0, size)   # bir xil buyurtma ikki marta hisoblanmaydi
        st = mx.quota_status(uid, kind, free_limit_for(uid, kind))
        what = "esse tekshiruvi" if kind == "essay" else "AI mashq/dalil"
        again = "Endi esseni qayta yuboring." if kind == "essay" else "Endi mashqni yoki dalil so‘rovini qayta yuboring."
        text = f"🎉 TO‘LOV TASDIQLANDI!\n\n➕ {size} ta {what} qo‘shildi.\n💼 Hisobingizda: {st['credits']} ta pullik tekshiruv.\n\n{again}"
    if str(order["note"] or "").startswith("gift:"): text = text.replace("🎉 TO‘LOV TASDIQLANDI!", "🎁 Sizga sovg‘a qilindi!")
    try: await context.bot.send_message(uid, text, reply_markup=(EXPERT_SEND_KB if kind == "expert" else MAIN_KEYBOARD))
    except Exception: logger.exception("foydalanuvchiga tasdiq xabari yuborilmadi uid=%s", uid)
    if kind == "gazal_item":
        try: await _send_gazal_item_files(context, uid, int(plan))
        except Exception: logger.exception("g‘azal fayllarini yuborib bo‘lmadi uid=%s", uid)

async def payadmin_callback(update, context):
    q = update.callback_query; adm = q.from_user.id
    if adm not in PAY_APPROVERS:
        await q.answer("⛔ Faqat admin.", show_alert=True); return
    m = re.match(r"^pay(ok|no)_([0-9]+)$", q.data or "")
    if not m:
        await q.answer(); return
    approve = m.group(1) == "ok"; oid = int(m.group(2))
    order = mp.get_order(oid)
    if not order:
        await q.answer("Buyurtma topilmadi.", show_alert=True); return

    async def _mark(text):
        try: await q.message.edit_caption(caption=((q.message.caption or "")[:900] + "\n\n" + text), reply_markup=None)
        except Exception:
            try: await q.message.edit_reply_markup(reply_markup=None)
            except Exception: pass

    if not mp.decide(oid, approve, adm):
        await q.answer("Bu buyurtma allaqachon ko‘rib chiqilgan.", show_alert=True); await _mark("ℹ️ Allaqachon ko‘rib chiqilgan."); return
    if approve:
        try:
            await _grant_manual_order(order, context)
        except Exception:
            logger.exception("manual grant failed oid=%s", oid)
            mp.undo_approval(oid)
            await q.answer("⚠️ Xatolik: xizmat ochilmadi. Qayta bosing.", show_alert=True); return
        try: mp.record_commission(int(order["user_id"]),f"manual:{oid}",int(order["amount"]))
        except Exception: logger.exception("ustoz komissiyasi (karta)")
        await q.answer("✅ Tasdiqlandi, xizmat ochildi.")
        await _mark(f"✅ TASDIQLANDI ({_tashkent(now_iso())})")
    else:
        await q.answer("❌ Rad etildi.")
        await _mark(f"❌ RAD ETILDI ({_tashkent(now_iso())})")
        try:
            await context.bot.send_message(int(order["user_id"]),
                f"❌ #{oid} to‘lovingiz tasdiqlanmadi.\n\nAgar to‘lovni amalga oshirgan bo‘lsangiz, /paysupport orqali murojaat qiling.", reply_markup=MAIN_KEYBOARD)
        except Exception: pass

# ---------------------------------------------------------------- Ekspert orqali esse tekshirish (v52)
EXPERT_SEND_KB = InlineKeyboardMarkup([[InlineKeyboardButton("📨 Esseni yuborish", callback_data="expsend")]])

def expert_offer_text():
    proof = "\n".join(mp.expert_proof())
    pay = ("💳 To‘lov karta orqali, <b>avtomatik</b>: to‘laysiz va esseni darhol yuborasiz." if mp.auto_pay_enabled()
           else "💳 To‘lov plastik karta orqali; to‘lov tasdiqlangach esseni yuborasiz.")
    return (f"👨‍🏫 <b>EKSPERT ORQALI ESSE TEKSHIRISH</b>\n\n"
            + (proof + "\n\n" if proof else "")
            + f"⏱ Esselar <b>{mp.EXPERT_HOURS} soat ichida</b> tekshirib beriladi.\n\n"
            f"• 1 ta esse — <b>{mp.fmt_uzs(mp.EXPERT_ONE_UZS)} so‘m</b>\n"
            f"• 🔥 Imtihongacha maxsus imkoniyat: <b>{mp.EXPERT_PACK_N} ta esse — {mp.fmt_uzs(mp.EXPERT_PACK_UZS)} so‘m</b>\n\n"
            + pay)

async def expert_offer_flow(message, uid):
    """Ekspert xizmati: balans bo'lsa — esse yuborish, aks holda ishonch bloki + to'lov tugmalari (admin kontaktisiz)."""
    bal = mp.expert_balance(uid)
    if bal > 0:
        await message.reply_text(f"👨‍🏫 Hisobingizda {bal} ta ekspert tekshiruvi bor.\n⏱ Esse {mp.EXPERT_HOURS} soat ichida tekshiriladi.", reply_markup=EXPERT_SEND_KB); return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💳 1 ta esse — {mp.fmt_uzs(mp.EXPERT_ONE_UZS)} so‘m", callback_data="cardpay_expert_e1")],
        [InlineKeyboardButton(f"🔥 {mp.EXPERT_PACK_N} ta esse — {mp.fmt_uzs(mp.EXPERT_PACK_UZS)} so‘m", callback_data="cardpay_expert_e3")]])
    await message.reply_text(expert_offer_text(), parse_mode="HTML", reply_markup=kb)

# ---------------------------------------------------------------- v68: MOCK natijalarini e'lon qilish
def mock_enrich_snapshot(code, uid, snap, a):
    """v71: natija snapshot'iga: sinf statistikasi, o'rin foizi, keyingi daraja, mavzu bo'yicha sinf o'rtachasi va ustuvor qayta o'rganish savollari qo'shiladi."""
    try:
        people = a["people"]; N = len(people)
        finals = [float(p_["final"]) for p_ in people]; mine = float(snap.get("combined_score_75") or 0)
        snap["class_stats"] = {"n": N, "mean": a["summary"]["mean"], "median": a["summary"]["median"], "best": max(finals) if finals else mine,
                               "percentile": round(100 * sum(1 for v in finals if v < mine) / N) if N else 0,
                               "top_pct": max(1, round(100 * int(snap.get("place") or N) / N)) if N else 100}
        snap["next_level"] = tp_.next_level(mine)
        cp = {f["name"]: f["pct"] for f in a.get("fans", [])}
        fr = snap.get("fan_report") or []
        for f in fr: f["class_pct"] = cp.get(f["name"])
        ip = {i["item"]: i["pct"] for i in a.get("items", [])}
        pri = [{"item": w, "fan": f["name"], "class_pct": ip.get(w)} for f in fr for w in f.get("wrong", [])]
        pri.sort(key=lambda x: -(x["class_pct"] if x["class_pct"] is not None else -1))
        snap["priority"] = pri[:8]
    except Exception:
        logger.exception("mock_enrich_snapshot")
    return snap

def publish_mock_results(mr):
    """Admin e'lon qilganda: butun guruh bo'yicha YAKUNIY ballar (Rasch + esse) hisoblanadi, har ishtirokchiga snapshot yoziladi,
    sertifikatlar beriladi va hamma ro'yxatdan o'tganlarga xabar yuboriladi. Qaytaradi: ishtirokchilar soni."""
    code = mr["test_code"]; t = get_test(code)
    a = tp_.ms_analytics(code)
    if not t or not a or a.get("empty"): return 0
    n = 0
    for p in a["people"]:
        u = p["user_id"]
        try:
            with DB_LOCK, db() as c:
                row = c.execute("SELECT id, answers_json FROM national_attempts WHERE user_id=? AND test_id=? ORDER BY id LIMIT 1", (u, t["id"])).fetchone()
            raw, _sc, errors, maxp = grade_national(t, json.loads(row["answers_json"] or "{}"))
            lvl = "Sertifikat berilmadi" if p["level"] == "NC" else p["level"]
            _noess = p.get("essay24") is None   # v76: esse balli yo'q — mock natijasi hisoblanmaydi
            if _noess: lvl = "Sertifikat berilmadi"
            snap = {"raw_score": raw, "max_score": maxp, "score_75": p["rasch"], "combined_score_75": p["final"], "level": lvl, "errors": errors,
                    "essay_score": p.get("essay24"), "essay_75": p.get("essay"), "place": p["rank"], "total": a["n"], "fan_report": tp_.fan_report(code, u),
                    "cert_eligible": lvl != "Sertifikat berilmadi", "title": t["title"], "code": code}
            if _noess: snap["no_essay"] = True
            mock_enrich_snapshot(code, u, snap, a)
            mk_.snapshot_set(code, u, snap)
            with DB_LOCK, db() as c:
                c.execute("UPDATE national_attempts SET diagnostic_score=? WHERE id=?", (float(p["final"]), row["id"]))
                try: c.execute("UPDATE national_attempts SET level=? WHERE id=?", (lvl, row["id"]))
                except Exception: pass
                c.commit()
            if lvl != "Sertifikat berilmadi":
                cdata = {"name": mx.user_name(u), "subject": t.get("subject", "Ona tili va adabiyot"), "score": round(float(p["final"]), 1), "level": lvl,
                         "test_score": round(float(p["rasch"]), 1), "essay": (round(float(p["essay24"]), 1) if p.get("essay24") is not None else "—"),
                         "essay75": p.get("essay"), "raw": raw, "max": maxp, "title": t["title"], "test_code": code, "date": datetime.now(mx.TZ).strftime("%d.%m.%Y")}
                cert_hold(code, u, cdata, lvl)
            n += 1
        except Exception:
            logger.exception("publish_mock_results uid=%s", u)
    mk_.publish_mark(mr["id"])
    def _bg():
        try: issue_held_certificates(code)
        except Exception: logger.exception("mock certs")
        try:
            import gc, ctypes; gc.collect(); ctypes.CDLL("libc.so.6").malloc_trim(0)   # sertifikat rasmlari yaratilgach xotirani qaytarish
        except Exception: pass
        done = {p["user_id"] for p in a["people"]}
        for u in set(mk_.regs_of(code)) | done:
            try:
                txt = (f"📣 «{mr['title']}» mock natijalari E'LON QILINDI!\nMini App → Mock → «📊 Natijam»." if u in done
                       else f"📣 «{mr['title']}» mock natijalari e'lon qilindi. Siz bu mockda qatnashmagansiz.")
                tg_api("sendMessage", {"chat_id": int(u), "text": txt}); time.sleep(0.05)
            except Exception: pass
    threading.Thread(target=_bg, daemon=True).start()
    return n

# ---------------------------------------------------------------- v67: MOCK — ekspert orqali esse tekshiruvi (aksiya narxi)
def parse_expert_score(text):
    """Ekspert javobidan esse ballini (0–24) ajratadi: «Ball: 18.5», «Esse balli 17», «18.5/24»."""
    t = str(text or "")
    m = (re.search(r"(?i)\b(?:esse\s*)?(?:bal+i?|score)\b\s*[:=\-–]?\s*(\d{1,2}(?:[.,]\d{1,2})?)", t)
         or re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*/\s*24\b", t))
    if not m: return None
    try: v = float(m.group(1).replace(",", "."))
    except Exception: return None
    return v if 0 <= v <= 24 else None

def _save_expert_check(uid, t, score, job_id):
    """Ekspert bergan ballni checks jadvaliga yozadi (milliy test natijasi shu yozuvga bog'lanadi). check id qaytaradi."""
    res = json.dumps({"expert": True, "job": job_id, "mock": t.get("code")}, ensure_ascii=False)
    with DB_LOCK, db() as c:
        cur = c.execute("INSERT INTO checks(user_id,mode,topic,total,words,created_at,status,result_json) VALUES(?,?,?,?,?,?,?,?)",
                        (uid, "expert", str(t.get("essay_topic") or "Mock esse")[:1000], float(score), 0, now_iso(), "expert", res))
        cid = cur.lastrowid; c.commit()
    return cid

def _essay_in_window(check_id, mock_row):
    """Mock uchun esse test boshlangandan KEYIN yozilgan bo'lishi kerak (oldindan tayyorlangan esse emas)."""
    try:
        if not check_id: return False
        with DB_LOCK, db() as c:
            r = c.execute("SELECT created_at FROM checks WHERE id=?", (int(check_id),)).fetchone()
        return bool(r) and mk_._parse(r[0]) >= mk_._parse(mock_row["opens_at"])
    except Exception:
        return True   # tekshirib bo'lmasa — to'sib qo'ymaymiz

async def mock_ai_flow(message, uid, code, context):
    """v76: Mock ishtirokchisi uchun 1 martalik BEPUL AI esse tekshiruvi — faqat shu mockning esse mavzusi."""
    code = str(code).upper().strip()
    r = mk_.promo_mock(uid, uid == ADMIN_ID)
    if not r or str(r["test_code"]).upper() != code:
        await message.reply_text("🤖 Bepul AI tekshiruvi faqat mock BOSHLANGANDAN keyin va unga «Qatnashaman» deb ro‘yxatdan o‘tganlar uchun. Mini App → Mock.", reply_markup=MAIN_KEYBOARD); return
    t = get_test(code) or {}
    topic = (t.get("essay_topic") or "").strip()
    if not topic:
        await message.reply_text("⚠️ Bu mockda esse mavzusi belgilanmagan. Adminga murojaat qiling.", reply_markup=MAIN_KEYBOARD); return
    if uid != ADMIN_ID:
        if not mk_.ai_free_day():
            await message.reply_text(f"🤖 Bepul AI tekshiruvi faqat belgilangan kunda amal qiladi va hozir yopiq.\n\n👨‍🏫 Ekspert tekshiruvi: {mp.fmt_uzs(mp.MOCK_EXPERT_UZS)} so‘m (Mini App → Mock).", reply_markup=MAIN_KEYBOARD); return
        if mk_.ai_free_used(code, uid):
            await message.reply_text(f"🤖 Siz mock uchun bepul AI imkoniyatidan foydalanib bo‘lgansiz (1 martalik).\n\n👨‍🏫 Esse balli uchun ekspert tekshiruvi: {mp.fmt_uzs(mp.MOCK_EXPERT_UZS)} so‘m (Mini App → Mock).", reply_markup=MAIN_KEYBOARD); return
    MOCK_AI_ACTIVE[uid] = code
    context.user_data["topic"] = topic; context.user_data["method"] = "ai"; context.user_data["stage"] = "essay_ai"
    await message.reply_text(
        "🤖 <b>MOCK: bepul AI esse tekshiruvi</b>\n\n🎁 Faqat mock ishtirokchilari uchun <b>1 martalik</b> imkoniyat.\n"
        f"📝 Mavzu: «{_html.escape(topic)}»\n⚠️ AI faqat shu mavzudagi esseni tekshiradi, boshqa mavzu emas.\n\n"
        "📌 Esseingizni yuboring: matn, rasm(lar) yoki PDF ko‘rinishida.\n"
        f"✂️ Matn hajmi: {MIN_ESSAY_WORDS}–{MAX_ESSAY_WORDS} so‘z.\n\n"
        "Natija chiqqach Mini App → Mock'ga qaytib testni yakunlang.",
        parse_mode="HTML", reply_markup=MAIN_KEYBOARD)

async def mock_expert_flow(message, uid, code):
    r = mk_.promo_mock(uid, uid == ADMIN_ID)
    if not r or str(r["test_code"]).upper() != str(code).upper():
        await message.reply_text("👨‍🏫 Mock uchun ekspert aksiyasi faqat mock BOSHLANGANDAN keyin va unga «Qatnashaman» deb ro‘yxatdan o‘tganlar uchun ochiladi. Mini App → Mock.", reply_markup=MAIN_KEYBOARD); return
    mk_.expert_pending_set(uid, r["test_code"])
    if mp.expertm_balance(uid) > 0:
        await message.reply_text(f"👨‍🏫 Mock uchun ekspert tekshiruvingiz tayyor.\n⏱ Esse {mp.EXPERT_HOURS} soat ichida tekshiriladi va BALL bilan yuboriladi.", reply_markup=EXPERT_SEND_KB); return
    t = get_test(r["test_code"]) or {}
    topic = (t.get("essay_topic") or "").strip()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Ekspert tekshiruvi — {mp.fmt_uzs(mp.MOCK_EXPERT_UZS)} so‘m (MOCK aksiyasi)", callback_data="cardpay_expert_em")]])
    await message.reply_text(
        f"👨‍🏫 <b>MOCK: ekspert esse tekshiruvi</b>\n\n🔥 Aksiya narxi: <b>{mp.fmt_uzs(mp.MOCK_EXPERT_UZS)} so‘m</b> (odatda {mp.fmt_uzs(mp.EXPERT_ONE_UZS)}). Faqat mock kunlari amal qiladi.\n"
        f"⏱ Esse {mp.EXPERT_HOURS} soat ichida tekshiriladi, <b>ball (0–24)</b> yuboriladi va mock natijangizga qo‘shiladi.\n\n"
        + (f"📝 Esse mavzusi: «{_html.escape(topic)}»\n\n" if topic else "") + "To‘lovdan keyin esseni shu chatga yuborasiz.",
        parse_mode="HTML", reply_markup=kb)

async def mock_expert_finalize(context, info, score, job):
    """Ekspert ball berdi: ball saqlanadi va (test topshirilgan bo'lsa) natijaga bog'lanadi. Foydalanuvchiga FAQAT esse balli yuboriladi;
    test va umumiy natija admin e'lon qilgach ko'rinadi."""
    code, uid = info["mock_code"], info["user_id"]
    mk_.expert_score_set(code, uid, score, job["id"])
    t = get_test(code)
    if t:
        try:
            with DB_LOCK, db() as c:
                row = c.execute("SELECT id FROM national_attempts WHERE user_id=? AND test_id=? ORDER BY id LIMIT 1", (uid, t["id"])).fetchone()
            if row:
                cid = _save_expert_check(uid, t, score, job["id"])
                with DB_LOCK, db() as c:
                    c.execute("UPDATE national_attempts SET essay_check_id=? WHERE id=?", (cid, row["id"])); c.commit()
        except Exception:
            logger.exception("mock_expert_finalize")
    try: await context.bot.send_message(uid, f"👨‍🏫 Ekspert esse balingiz: <b>{_n(score)}/24</b> (Mock {code}).\n\nℹ️ Test va umumiy natija, shuningdek sertifikat admin natijalarni e‘lon qilgach beriladi.", parse_mode="HTML", reply_markup=MAIN_KEYBOARD)
    except Exception: pass

async def expert_cmd(update, context):
    await expert_offer_flow(update.message, update.effective_user.id)

async def expert_send_callback(update, context):
    q = update.callback_query; uid = q.from_user.id; await q.answer()
    if mp.expert_balance(uid) + (mp.expertm_balance(uid) if mk_.expert_pending_get(uid) else 0) <= 0:
        await q.message.reply_text("Hisobingizda ekspert tekshiruvi yo‘q. /ekspert", reply_markup=MAIN_KEYBOARD); return
    mp.expert_set_active(uid, True)
    await q.message.reply_text("📨 Esseingizni yuboring: matn, rasm yoki PDF ko‘rinishida (bir necha rasm bo‘lsa, hammasini bitta albomda yuboring).\n\n"
                               f"⏱ Ekspert {mp.EXPERT_HOURS} soat ichida tekshirib, natijani shu chatga yuboradi.\n❌ Bekor qilish: /ekspert_bekor", reply_markup=MAIN_KEYBOARD)

async def expert_cancel_cmd(update, context):
    mp.expert_set_active(update.effective_user.id, False)
    await update.message.reply_text("❌ Ekspertga esse yuborish to‘xtatildi. Qayta yuborish: /ekspert", reply_markup=MAIN_KEYBOARD)

_EXP_GROUPS = {}

class ExpertSubmitFilter(filters.MessageFilter):
    """Ekspert tekshiruvi faol bo‘lgan foydalanuvchining esse xabarlari (chek kutilayotgan bo‘lsa — chek ustun)."""
    def filter(self, message):
        try:
            if not message.from_user: return False
            uid = message.from_user.id; gid = getattr(message, "media_group_id", None)
            if gid and (uid, gid) in _EXP_GROUPS: return True
            if mp.awaiting_order(uid): return False
            return mp.expert_active(uid)
        except Exception:
            return False

async def expert_submit_handler(update, context):
    m = update.message; u = update.effective_user; uid = u.id; gid = getattr(m, "media_group_id", None)
    job = _EXP_GROUPS.get((uid, gid)) if gid else None; new = job is None; due = None; mock_code = None
    if new:
        _pend = mk_.expert_pending_get(uid)
        use_m = bool(_pend) and mp.expertm_balance(uid) > 0     # v67: Mock aksiyasi balansi (faqat mock esselari)
        if not (mp.expertm_consume(uid) if use_m else mp.expert_consume(uid)):
            mp.expert_set_active(uid, False)
            await m.reply_text("Hisobingizda ekspert tekshiruvi qolmagan. /ekspert", reply_markup=MAIN_KEYBOARD); raise ApplicationHandlerStop
        job, due = mp.expert_new_job(uid)
        if use_m:
            mock_code = _pend; mk_.expert_job_link(job, mock_code, uid); mk_.expert_pending_clear(uid)
        if gid:
            if len(_EXP_GROUPS) > 500: _EXP_GROUPS.clear()
            _EXP_GROUPS[(uid, gid)] = job
    try:
        if new:
            head = await context.bot.send_message(ADMIN_ID,
                f"📝 EKSPERT ESSE #{job}" + (f" 🎯 MOCK {mock_code}" if mock_code else "") + f"\n👤 {u.full_name} " + (f"@{u.username} " if u.username else "") + f"(id {uid})\n⏰ Muddat: {_tashkent(due)}\n\n"
                "Javob berish: shu xabarga yoki esse xabariga REPLY qiling — natija foydalanuvchiga yuboriladi."
                + ("\n\n⚠️ MOCK esse: javob matnida albatta ball yozing, masalan «Ball: 18.5» (0–24). Ball mock natijasiga avtomatik qo‘shiladi." if mock_code else ""))
            mp.expert_link_msg(head.message_id, job)
        cp = await context.bot.copy_message(ADMIN_ID, m.chat_id, m.message_id)
        mp.expert_link_msg(cp.message_id, job)
    except Exception:
        logger.exception("ekspertga esse yuborilmadi uid=%s", uid)
        if new:
            (mp.expertm_refund if mock_code else mp.expert_refund)(uid)
            with mp.db() as c: c.execute("UPDATE expert_jobs SET status='failed' WHERE id=?", (job,)); c.commit()
        await m.reply_text("⚠️ Esse ekspertga yetib bormadi. Tekshiruv hisobingizda saqlandi, qayta yuboring.", reply_markup=MAIN_KEYBOARD); raise ApplicationHandlerStop
    if new:
        bal = mp.expert_balance(uid)
        if bal <= 0 and not (mp.expertm_balance(uid) > 0): mp.expert_set_active(uid, False)
        await m.reply_text(f"✅ Esseingiz ekspertga yuborildi (#{job}).\n⏱ {mp.EXPERT_HOURS} soat ichida natija shu chatga keladi.\n💼 Qolgan ekspert tekshiruvi: {bal} ta"
                           + ("\n\nYana esse yuborishingiz mumkin." if bal > 0 else ""), reply_markup=MAIN_KEYBOARD)
    raise ApplicationHandlerStop

class ExpertReplyFilter(filters.MessageFilter):
    def filter(self, message):
        try:
            return bool(message.from_user and message.from_user.id in PAY_APPROVERS and message.reply_to_message
                        and mp.expert_job_by_msg(message.reply_to_message.message_id))
        except Exception:
            return False

async def expert_reply_handler(update, context):
    m = update.message; job = mp.expert_job_by_msg(m.reply_to_message.message_id)
    if not job: return
    try: await context.bot.copy_message(job["user_id"], m.chat_id, m.message_id)
    except Exception as e:
        await m.reply_text(f"⚠️ Foydalanuvchiga yuborib bo‘lmadi: {e}"); raise ApplicationHandlerStop
    _mi = mk_.expert_job_info(job["id"])
    if _mi:   # v67: MOCK esse — ball majburiy
        _sc = parse_expert_score(m.text or m.caption or "")
        if _sc is None:
            await m.reply_text("⚠️ Bu MOCK esse: javobda ball topilmadi. Natijaga qo‘shish uchun shu xabarga yana REPLY qilib «Ball: 18.5» (0–24) yozing."); raise ApplicationHandlerStop
        await mock_expert_finalize(context, _mi, _sc, job)
    if job["status"] == "open":
        try: await context.bot.send_message(job["user_id"], f"👨‍🏫 Ekspert esseingizni tekshirdi (#{job['id']}). Natija yuqorida.", reply_markup=MAIN_KEYBOARD)
        except Exception: pass
        mp.expert_mark_replied(job["id"])
    await m.reply_text(f"✅ #{job['id']} foydalanuvchiga yuborildi.")
    raise ApplicationHandlerStop

async def unpaid_cmd(update, context):
    if update.effective_user.id not in PAY_APPROVERS: return
    try:
        await update.message.reply_text(pay_nudge.funnel_report(mp) if pay_nudge else 'pay_nudge.py topilmadi')
    except Exception:
        logger.exception("unpaid_cmd"); await update.message.reply_text("⚠️ Hisobotni tayyorlab bo‘lmadi.")

async def expert_list_cmd(update, context):
    if update.effective_user.id not in PAY_APPROVERS: return
    jobs = mp.expert_open_jobs()
    if not jobs: await update.message.reply_text("✅ Tekshirilmagan ekspert esselari yo‘q."); return
    nowi = now_iso()
    await update.message.reply_text("📝 Tekshirilmagan esselar:\n\n" + "\n".join(
        f"#{j['id']} — id {j['user_id']} — muddat {_tashkent(j['due_at'])}" + (" ⚠️ KECHIKDI" if j["due_at"] < nowi else "") for j in jobs))

BER_USAGE = ("🎁 BEPUL BERISH (faqat admin)\n\n/ber <ID> esse 5 — 5 ta esse tekshiruvi\n/ber <ID> ai 5 — 5 ta AI mashq/dalil\n/ber <ID> ekspert 2 — 2 ta ekspert tekshiruvi\n"
             "/ber <ID> premium — Premium (30 kun + bonus esselar)\n/ber <ID> hafta — 7 kunlik esse paketi\n/ber <ID> ustoz — Ustoz Pro\n"
             "/ber <ID> kitoblar — Badiiy asarlar\n/ber <ID> gazal — G‘azal tahlili (to‘liq)\n/ber <ID> guruh — G‘azal kursi guruhi\n/ber <ID> qollanma 3 — G‘azal qo‘llanmasi (papka raqami)\n\n"
             "ID — foydalanuvchining Telegram raqami (to‘lov xabarlarida «🆔» qatorida chiqadi).")

async def ber_cmd(update, context):
    """v58: admin tanlangan odamga pullik xizmatni pulsiz ochadi."""
    if update.effective_user.id != ADMIN_ID: return
    a = list(context.args or [])
    if len(a) < 2 or not a[0].isdigit():
        await update.message.reply_text(BER_USAGE); return
    uid = int(a[0]); svc = a[1].lower(); arg = a[2] if len(a) > 2 else ""
    n = int(arg) if arg.isdigit() else 0
    if svc in ("esse", "ai", "ekspert"):
        n = n or 1
        if n > 200:
            await update.message.reply_text("⚠️ Bir martada 200 tagacha."); return
        kind = {"esse": "essay", "ai": "tool", "ekspert": "expert"}[svc]
        mx.grant_pack(uid, kind, f"gift:{ADMIN_ID}:{uid}:{int(time.time())}", 0, n)
        what = {"essay": "esse tekshiruvi", "tool": "AI mashq/dalil", "expert": "ekspert tekshiruvi"}[kind]
        text = f"🎁 Sizga sovg‘a qilindi!\n\n➕ {n} ta {what} hisobingizga qo‘shildi."
        try: await context.bot.send_message(uid, text, reply_markup=(EXPERT_SEND_KB if kind == "expert" else MAIN_KEYBOARD))
        except Exception: await update.message.reply_text("⚠️ Berildi, lekin foydalanuvchiga xabar yetmadi (u botni /start qilmagan bo‘lishi mumkin)."); return
        await update.message.reply_text(f"✅ {uid} ga {n} ta {what} berildi."); return
    mapping = {"premium": ("growth", "growth"), "hafta": ("essay", "w7"), "ustoz": ("teacher", "pro"), "kitoblar": ("books", "all"),
               "gazal": ("gazal_lib", "all"), "guruh": ("group", "gazal"), "qollanma": ("gazal_item", str(n))}
    if svc not in mapping or (svc == "qollanma" and not n):
        await update.message.reply_text(BER_USAGE); return
    kind, plan = mapping[svc]
    if not mp.valid_plan(kind, plan):
        await update.message.reply_text("⚠️ Bunday xizmat/raqam topilmadi."); return
    oid = mp.create_gift_order(uid, kind, plan, ADMIN_ID)
    try:
        await _grant_manual_order(mp.get_order(oid), context)
    except Exception:
        logger.exception("ber_cmd grant oid=%s", oid)
        await update.message.reply_text("⚠️ Berishda xatolik. Loglarni tekshiring."); return
    await update.message.reply_text(f"✅ {uid} ga «{mp.plan_title(kind, plan)}» bepul ochildi (buyurtma #{oid}, 0 so‘m).")

async def avtokarta_cmd(update, context):
    """v58: admin kartasiga avtomatik to'lov holati va ulash yo'riqnomasi."""
    if update.effective_user.id not in PAY_APPROVERS: return
    n, h = mp.card_info()
    base = (os.getenv("PUBLIC_BASE_URL", "") or os.getenv("RENDER_EXTERNAL_URL", "") or "https://<sizning-render-manzilingiz>").rstrip("/")
    st = []
    st.append("✅ Karta kiritilgan: " + mp.pretty_card(n) if n else "❌ Karta kiritilmagan: /karta 8600123412341234 Ism Familiya")
    st.append("✅ PAY_WEBHOOK_SECRET qo‘yilgan" if mp.SMS_SECRET else "❌ PAY_WEBHOOK_SECRET qo‘yilmagan (Render → Environment)")
    st.append("🟢 AVTO-REJIM YOQILGAN" if mp.card_auto_enabled() else "🔴 Avto-rejim o‘chiq (chek + qo‘lda tasdiq ishlaydi)")
    rows = mp.card_tx_recent(8)
    last = "\n".join(f"• {_tashkent(r['at'])} — {mp.fmt_uzs(r['amount'])} so‘m — {r['status']}" + (f" (#{r['order_id']})" if r['order_id'] else "") for r in rows) or "hali kirim kelmagan"
    await update.message.reply_text(
        "💳 AVTOMATIK KARTA TO‘LOVI\n\n" + "\n".join(st) +
        "\n\n📲 ULASH (bir marta):\n1) Admin telefoniga «SMS Forwarder» (yoki shunga o‘xshash HTTP-yo‘naltiruvchi) ilovasini o‘rnating.\n"
        "2) Bank SMS’lari (Humo/Uzcard kirim xabari) kelganda quyidagi manzilga POST yuborsin:\n"
        f"{base}/api/pay/sms\n"
        "3) Sarlavha: X-Pay-Secret: <PAY_WEBHOOK_SECRET qiymati>\n"
        "4) Tana (JSON): {\"text\": \"<SMS matni>\"}\n\n"
        "🧾 Oxirgi kirimlar:\n" + last)

async def karta_cmd(update, context):
    if update.effective_user.id not in PAY_APPROVERS: return
    toks = list(context.args or []); digits = []; i = 0
    while i < len(toks) and toks[i].isdigit():
        digits.append(toks[i]); i += 1
    number = "".join(digits); holder = " ".join(toks[i:])
    if not number:
        n, h = mp.card_info()
        await update.message.reply_text("💳 Joriy karta: " + (f"{mp.pretty_card(n)} — {h}" if n else "kiritilmagan") + "\n\nO‘zgartirish:\n/karta 8600123412341234 Ism Familiya"); return
    if len(number) != 16:
        await update.message.reply_text("⚠️ Karta raqami 16 ta raqam bo‘lishi kerak."); return
    mp.set_card(number, holder)
    await update.message.reply_text(f"✅ Karta saqlandi:\n{mp.pretty_card(number)}\n👤 {holder or '—'}\n\nEndi to‘lov bo‘limida «💳 Karta orqali» tugmasi ishlaydi.")

async def kanal_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    args = list(context.args or []); chs = extra_channels()
    if args and args[0].lower() in ("add", "qosh", "qo‘sh") and len(args) >= 2:
        chat = args[1].strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,}", chat): chat = "@" + chat
        if not (chat.startswith("@") or re.fullmatch(r"-100[0-9]+", chat)):
            await update.message.reply_text("⚠️ Kanal @username yoki -100... ID ko‘rinishida bo‘lishi kerak."); return
        url = args[2] if len(args) >= 3 and args[2].startswith("https://t.me/") else (f"https://t.me/{chat[1:]}" if chat.startswith("@") else "")
        if not url:
            await update.message.reply_text("⚠️ Yopiq kanal uchun havola ham yozing:\n/kanal add -1001234567890 https://t.me/+xxxx"); return
        if any(c["chat"].lower() == chat.lower() for c in chs) or chat.lower() == str(REQUIRED_CHANNEL).lower():
            await update.message.reply_text("ℹ️ Bu kanal allaqachon ro‘yxatda."); return
        try:
            info = await context.bot.get_chat(chat); title = (info.title or chat)[:40]
            me = await context.bot.get_chat_member(chat, context.bot.id)
            if getattr(me, "status", "") not in ("administrator", "creator"):
                await update.message.reply_text("⚠️ Bot bu kanalda admin emas. Avval botni kanalga ADMIN qiling (a’zolikni tekshirish uchun shart), keyin qayta qo‘shing."); return
        except Exception as e:
            await update.message.reply_text(f"⚠️ Kanalni topib bo‘lmadi yoki bot kanalda emas: {e}\n\nBotni kanalga admin qilib qo‘shing."); return
        chs.append({"chat": chat, "url": url, "title": title}); save_extra_channels(chs)
        await update.message.reply_text(f"✅ Majburiy kanal qo‘shildi: {title}\nEndi foydalanuvchilar asosiy kanal va shu kanalga ham a’zo bo‘lishi kerak.\nJami qo‘shimcha kanallar: {len(chs)}"); return
    if args and args[0].lower() in ("del", "ochir", "o‘chir") and len(args) >= 2:
        key = args[1].strip().lower(); key = key if key.startswith(("@", "-")) else "@" + key
        new = [c for c in chs if c["chat"].lower() != key]
        if len(new) == len(chs):
            await update.message.reply_text("Topilmadi. Ro‘yxat: /kanal"); return
        save_extra_channels(new); await update.message.reply_text("✅ Kanal majburiy ro‘yxatdan olib tashlandi."); return
    lines = "\n".join(f"{i}. {c.get('title','')} — {c['chat']}" for i, c in enumerate(chs, 1)) or "—"
    await update.message.reply_text(
        f"📢 MAJBURIY KANALLAR\n\nAsosiy: {REQUIRED_CHANNEL}\nQo‘shimcha:\n{lines}\n\n"
        "Qo‘shish: /kanal add @kanal_username\nYopiq kanal: /kanal add -1001234567890 https://t.me/+xxxx\n"
        "O‘chirish: /kanal del @kanal_username\n\n⚠️ Bot qo‘shilayotgan kanalda ADMIN bo‘lishi shart.")

_BOOKS_STATE = {}   # admin_id -> {'mode': 'new'|'pic'|'info'|'test', 'n': asar raqami, 'first': bool}

class BooksModeFilter(filters.MessageFilter):
    """Rasm yuklash rejimi (yangi asar yoki mavjud asarga rasm)."""
    def filter(self, message):
        try:
            st = _BOOKS_STATE.get(message.from_user.id) if message.from_user else None
            return bool(st and st['mode'] in ('new', 'pic'))
        except Exception: return False

class BooksVideoFilter(filters.MessageFilter):
    """Videodars yuklash rejimi (admin)."""
    def filter(self, message):
        try:
            st = _BOOKS_STATE.get(message.from_user.id) if message.from_user else None
            return bool(st and st['mode'] == 'video')
        except Exception: return False

class GazalFileFilter(filters.MessageFilter):
    """G'azal qo'llanma fayllarini yuklash rejimi (admin)."""
    def filter(self, message):
        try:
            st = _BOOKS_STATE.get(message.from_user.id) if message.from_user else None
            return bool(st and st['mode'] == 'gfile')
        except Exception: return False

class BooksTextFilter(filters.MessageFilter):
    """Ma'lumot / test matnini kutish rejimi."""
    def filter(self, message):
        try:
            st = _BOOKS_STATE.get(message.from_user.id) if message.from_user else None
            return bool(st and st['mode'] in ('info', 'test'))
        except Exception: return False

BOOKS_HELP = (
    "📚 BADIIY ASARLAR — ADMIN\n\n"
    "➕ Yangi asar: /asar — keyin rasmni asar nomi (izoh) bilan yuboring\n"
    "🖼 Rasm qo‘shish: /asar_rasm 3 — 3-asarga yana rasmlar yuboring\n"
    "ℹ️ Ma‘lumot: /asar_malumot 3 — muallif, janr, qisqa mazmun matnini yuboring\n"
    "📝 Test: /asar_test 3 — savollarni namunadagi ko‘rinishda yuboring\n"
    "🧹 Testni tozalash: /asar_test_tozala 3\n"
    "📋 Ro‘yxat: /asarlar\n"
    "🗑 O‘chirish: /asar_ochir 3  •  ✏️ Nomi: /asar_nom 3 Yangi nom\n"
    "🎬 Videodars: /asar_video 3 — keyin videolarni yuboring\n"
    "✅ Tugatish: /asar_tamom\n\n"
    "🔓 Hamma uchun (pullik) ochish: /asar_ochiq\n🔒 Yopish («Jarayonda»): /asar_yopiq")

TEST_SAMPLE = ("1. Savol matni?\nA) birinchi variant\nB) ikkinchi variant\nC) uchinchi variant\nD) to‘rtinchi variant\nJavob: B\nIzoh: ixtiyoriy izoh\n\n2. Keyingi savol...")

def _book_arg(context):
    try: return int((context.args or [""])[0])
    except Exception: return None

async def asar_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    _BOOKS_STATE[ADMIN_ID] = {'mode': 'new', 'n': None, 'first': True}
    await update.message.reply_text(
        "📚 YANGI ASAR rejimi yoqildi.\n\n"
        "Asar rasmini yuboring va rasm ostiga (izoh/caption) <b>asar nomini</b> yozing.\n"
        "Aniq sifat uchun rasmni «Fayl» (hujjat) sifatida yuborish yaxshi.\n"
        "Bir nechta asarni ketma-ket yuborishingiz mumkin.\n\n"
        "Asar qo‘shilgach unga <b>ma‘lumot</b> (/asar_malumot N), <b>test</b> (/asar_test N) va yana <b>rasm</b> (/asar_rasm N) qo‘shasiz.\n"
        "✅ Tugatish: /asar_tamom  •  Hamma buyruqlar: /asar_yordam",
        parse_mode="HTML")

async def asar_yordam_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(BOOKS_HELP)

async def asar_video_cmd(update, context):
    """/asar_video 3 [birinchi dars nomi] — 3-elementga videodarslar yuklash rejimi."""
    if update.effective_user.id != ADMIN_ID: return
    n = _book_arg(context)
    if n is None or not bk_.exists(n):
        await update.message.reply_text("Raqamini yozing: /asar_video 3  (raqamlar /asarlar da)"); return
    title = " ".join(context.args[1:]).strip()[:150] if context.args and len(context.args) > 1 else ""
    _BOOKS_STATE[ADMIN_ID] = {'mode': 'video', 'n': n, 'title': title, 'count': 0}
    await update.message.reply_text(f"🎬 {n}-elementga VIDEODARS qo‘shish rejimi.\nVideoni yuboring (ketma-ket bir nechta ham mumkin). Video izohiga (caption) nom yozsangiz, shu nom bo‘ladi, aks holda «1-dars», «2-dars»...\nHozir: {len(bk_.video_list(n))} ta video.\n✅ Tugatish: /asar_tamom")

async def gazal_fayl_cmd(update, context):
    """/gazal_fayl 7 [nom] — 7-qo'llanmaga fayl (PDF, Word va h.k.) qo'shish rejimi. Fayl Telegram'da qoladi, serverda joy egallamaydi."""
    if update.effective_user.id != ADMIN_ID: return
    n = _book_arg(context)
    if n is None or not bk_.exists(n) or bk_.get_sec(n) not in bk_.FILE_SECS:
        items = [x for _s in bk_.FILE_SECS for x in bk_.list_books(_s)]
        lst = "\n".join(f"{x['n']}. {bk_.COLLECTIONS[x['sec']]['ico']} {x['title']} — 📎{x['files']}" for x in items) or "— hali element yo‘q (Mini App → bo‘lim → ➕ Yangi) —"
        await update.message.reply_text(f"Raqamini yozing: /gazal_fayl 7\n\n{lst}"); return
    title = " ".join(context.args[1:]).strip()[:150] if len(context.args) > 1 else ""
    _BOOKS_STATE[ADMIN_ID] = {'mode': 'gfile', 'n': n, 'title': title, 'count': 0}
    await update.message.reply_text(f"📎 {n}-qo‘llanmaga FAYL qo‘shish rejimi.\nFaylni «Fayl» (document) qilib yuboring — PDF, Word va boshqalar, ketma-ket bir nechta ham mumkin. Izohga (caption) nom yozsangiz shu nom bo‘ladi.\nHozir: {len(bk_.file_list(n))} ta fayl.\n✅ Tugatish: /asar_tamom")

async def gazal_file_handler(update, context):
    m = update.message
    if not m or update.effective_user.id != ADMIN_ID: return
    st = _BOOKS_STATE.get(ADMIN_ID)
    if not st or st.get('mode') != 'gfile': return
    try:
        d = m.document or m.audio or m.video
        if not d:
            await m.reply_text("⚠️ Faylni «Fayl» (document) sifatida yuboring. Rasm sifatida yuborilsa sifati buziladi."); raise ApplicationHandlerStop
        name = (getattr(d, 'file_name', '') or '').strip()
        title = (m.caption or '').strip() or (st.get('title') if not st.get('count') else '') or os.path.splitext(name)[0]
        fid = bk_.add_file(st['n'], d.file_id, title, getattr(d, 'mime_type', '') or '', getattr(d, 'file_size', 0) or 0)
        if fid is None: await m.reply_text(f"⚠️ Bitta qo‘llanmaga {bk_.MAX_FILES} tadan ko‘p fayl qo‘shib bo‘lmaydi."); raise ApplicationHandlerStop
        st['count'] = st.get('count', 0) + 1
        await m.reply_text(f"✅ Fayl qo‘shildi ({st['n']}-qo‘llanma). Jami: {len(bk_.file_list(st['n']))} ta.\nYana yuboring yoki /asar_tamom")
    except ApplicationHandlerStop: raise
    except Exception as e:
        logger.exception("gazal file failed")
        await m.reply_text(f"⚠️ Faylni saqlab bo‘lmadi: {e}")
    raise ApplicationHandlerStop

async def esse_video_cmd(update, context):
    """/esse_video — Esse → Videodars: holat • /esse_video_och • /esse_video_yop • /esse_video_yuklash (video qo'shish rejimi)."""
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text(f"🎬 Esse → Videodars\nHolat: {'🟢 OCHIQ' if _esse_video_open() else '🔴 YOPIQ (obunachilar «Tez orada ochiladi» ko‘radi)'}\nVideolar: {len(bk_.video_list(ESSE_VIDEO_N))} ta\n\n/esse_video_yuklash — video qo‘shish rejimi\n/esse_video_och • /esse_video_yop")

async def esse_video_och_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    mp.set_setting('esse_video_open','1'); await update.message.reply_text("✅ Esse → Videodars Premium obunachilarga OCHILDI.")

async def esse_video_yop_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    mp.set_setting('esse_video_open','0'); await update.message.reply_text("🚧 Esse → Videodars yopildi: obunachilar «Tez orada ochiladi» yozuvini ko‘radi.")

async def esse_video_yuklash_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    _BOOKS_STATE[ADMIN_ID] = {'mode': 'video', 'n': ESSE_VIDEO_N, 'title': '', 'count': 0}
    await update.message.reply_text(f"🎬 Esse → VIDEODARS qo‘shish rejimi.\nVideoni yuboring (ketma-ket bir nechta ham mumkin). Izohiga nom yozsangiz, shu nom bo‘ladi.\nHozir: {len(bk_.video_list(ESSE_VIDEO_N))} ta video.\n✅ Tugatish: /asar_tamom")

async def gazal_ochish_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    mp.set_gazal_lib_open(True)
    await update.message.reply_text("✅ «G‘azal tahlilini o‘rganamiz» foydalanuvchilarga OCHILDI (papkalar hammaga ko‘rinadi, fayllar faqat sotib olganga yuboriladi).\nNarxlar: /gazal_narx • ro‘yxat: /gazal_royxat • yopish: /gazal_yopish")

async def gazal_yopish_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    mp.set_gazal_lib_open(False)
    await update.message.reply_text("🚧 «G‘azal tahlilini o‘rganamiz» yopildi: foydalanuvchilar «Jarayonda» yozuvini ko‘radi, siz hammasini ko‘rasiz. Ochish: /gazal_ochish")

async def gazal_narx_cmd(update, context):
    """/gazal_narx — papkalar narxi ro'yxati • /gazal_narx 7 30000 — 7-papka narxi • /gazal_narx 7 0 — standart narxga qaytarish."""
    if update.effective_user.id != ADMIN_ID: return
    args = context.args or []
    if len(args) < 2:
        items = bk_.list_books('gazal')
        lines = "\n".join(f"{x['n']}. {x['title']} — {mp.fmt_uzs(bk_.item_price(x['n']))} so‘m" for x in items) or "— hali papka yo‘q —"
        await update.message.reply_text(f"💰 Papkalar narxi:\n\n{lines}\n\nO‘zgartirish: /gazal_narx 7 30000\nStandartga qaytarish: /gazal_narx 7 0"); return
    try: n = int(args[0]); v = int(args[1])
    except Exception:
        await update.message.reply_text("Format: /gazal_narx 7 30000"); return
    if not bk_.exists(n) or bk_.get_sec(n) != 'gazal':
        await update.message.reply_text("Bunday G‘azal tahlili papkasi yo‘q. Ro‘yxat: /gazal_narx"); return
    if not bk_.set_item_price(n, v):
        await update.message.reply_text(f"Narx {mp.fmt_uzs(bk_.MIN_PRICE)} dan {mp.fmt_uzs(bk_.MAX_PRICE)} so‘mgacha bo‘lsin (0 — standart narx)."); return
    await update.message.reply_text(f"✅ {n}-papka narxi: {mp.fmt_uzs(bk_.item_price(n))} so‘m (yangi buyurtmalar uchun).")

async def gazal_royxat_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    items = bk_.list_books('gazal')
    holat = "OCHIQ (papkalar hammaga ko‘rinadi)" if mp.gazal_lib_open() else "YOPIQ (faqat admin)"
    lines = "\n".join(f"{x['n']}. {x['title']} — {mp.fmt_uzs(bk_.item_price(x['n']))} so‘m • 📎{x['files']} fayl • 🎬{len(bk_.video_list(x['n']))} video • sotib olgan: {mp.group_count('gzi%d' % x['n'])}" for x in items) or "— hali papka yo‘q —"
    await update.message.reply_text(f"🌙 G‘azal tahlilini o‘rganamiz\nHolat: {holat}\n\n{lines}\n\n➕ Yangi papka (narx bilan): Mini App ichida\n📎 Fayl qo‘shish: /gazal_fayl 7\n🎬 Video qo‘shish: /asar_video 7\n💰 Narx: /gazal_narx 7 30000\n✅ Tugatish: /asar_tamom\n🔓 /gazal_ochish • 🔒 /gazal_yopish")

async def books_video_handler(update, context):
    m = update.message
    if not m or update.effective_user.id != ADMIN_ID: return
    st = _BOOKS_STATE.get(ADMIN_ID)
    if not st or st.get('mode') != 'video': return
    try:
        if m.video: fid, kind, dur, size = m.video.file_id, 'video', m.video.duration or 0, m.video.file_size or 0
        elif m.document and (m.document.mime_type or '').startswith('video/'): fid, kind, dur, size = m.document.file_id, 'document', 0, m.document.file_size or 0
        else: return
        title = (m.caption or '').strip() or (st.get('title') if not st.get('count') else '')
        vid = bk_.add_video(st['n'], fid, kind, title, dur, size)
        if vid is None: await m.reply_text(f"⚠️ Bitta elementga {bk_.MAX_VIDEOS} tadan ko‘p video qo‘shib bo‘lmaydi."); raise ApplicationHandlerStop
        st['count'] = st.get('count', 0) + 1
        await m.reply_text(f"✅ Video qo‘shildi ({st['n']}-element). Jami: {len(bk_.video_list(st['n']))} ta.\nYana yuboring yoki /asar_tamom")
    except ApplicationHandlerStop: raise
    except Exception as e:
        logger.exception("book video failed")
        await m.reply_text(f"⚠️ Videoni saqlab bo‘lmadi: {e}")
    raise ApplicationHandlerStop

async def asar_toldir_cmd(update, context):
    """/asar_toldir — books/asar_content.json dan asarlarning qahramonlar / voqealar rivoji / muhim manbalar bo'limlarini to'ldiradi
    (faqat bo'sh joylarni; band bo'limni o'zgartirmaydi). /asar_toldir force — band bo'limlarni ham yangilaydi. Testlarga tegmaydi."""
    if update.effective_user.id != ADMIN_ID: return
    force = bool(context.args and context.args[0].lower() == "force")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "books", "asar_content.json")
    try:
        done, skipped, missing = bk_.import_content(path, force=force)
    except Exception as e:
        logger.exception("asar_toldir failed")
        await update.message.reply_text(f"⚠️ Bajarilmadi: {e}"); return
    t = f"✅ To‘ldirildi: {len(done)} ta asar" + ("\n• " + "\n• ".join(done) if done else "")
    if skipped: t += f"\n\n⏭ Band bo‘lgani uchun o‘tkazildi: {len(skipped)} ta bo‘lim (yangilash: /asar_toldir force)"
    if missing: t += "\n\n❔ Botda topilmadi: " + ", ".join(missing)
    await update.message.reply_text(t[:3900])

async def asar_namuna_cmd(update, context):
    """/asar_namuna [raqam|yoq] — hamma uchun BEPUL ko'rinadigan namuna asar (standart: «Evrilish»)."""
    if update.effective_user.id != ADMIN_ID: return
    a = (context.args[0].lower() if context.args else "")
    if a in ("yoq","yo'q","yo‘q","none","0"):
        bk_.set_free(None); await update.message.reply_text("✅ Bepul namuna o‘chirildi."); return
    if a.isdigit():
        if bk_.get_sec(int(a)) != "asar": await update.message.reply_text("❌ Bunday asar yo‘q (/asarlar)."); return
        bk_.set_free(int(a))
    fid = bk_.free_id(); d = bk_.get_detail(fid) if fid else None
    await update.message.reply_text("🆓 Bepul namuna: " + (f"{d['title']} (№{fid})" if d else "yo‘q") + "\nO‘zgartirish: /asar_namuna <raqam>  •  o‘chirish: /asar_namuna yoq")

async def umumiy_ochiq_cmd(update, context):
    """/umumiy_ochiq — «Umumiy test» ni to'lov qilganlarga ochadi."""
    if update.effective_user.id != ADMIN_ID: return
    mp.set_setting("general_open","1"); await update.message.reply_text("✅ Umumiy test to‘lov qilganlarga ochildi. Yopish: /umumiy_yopiq")

async def umumiy_yopiq_cmd(update, context):
    """/umumiy_yopiq — «Umumiy test» ni yana qulflaydi (faqat admin ko'radi)."""
    if update.effective_user.id != ADMIN_ID: return
    mp.set_setting("general_open","0"); await update.message.reply_text("🔒 Umumiy test yopildi (foydalanuvchilarga qulf).")

async def asar_tamom_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    _BOOKS_STATE.pop(ADMIN_ID, None)
    await update.message.reply_text(f"✅ Rejim yopildi. Jami asarlar: {len(bk_.list_books())}\n\n/asarlar — ro‘yxat va holat", reply_markup=MAIN_KEYBOARD)

async def asar_rasm_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    n = _book_arg(context)
    if n is None or not bk_.exists(n):
        await update.message.reply_text("Raqamini yozing: /asar_rasm 3  (raqamlar /asarlar da)"); return
    _BOOKS_STATE[ADMIN_ID] = {'mode': 'pic', 'n': n, 'first': True}
    await update.message.reply_text(f"🖼 {n}-asarga RASM qo‘shish rejimi.\nRasmlarni ketma-ket yuboring (izoh shart emas). Hozir: {len(bk_.pic_ids(n))} ta qo‘shimcha rasm.\n✅ Tugatish: /asar_tamom")

async def asar_malumot_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    n = _book_arg(context)
    if n is None or not bk_.exists(n):
        await update.message.reply_text("Raqamini yozing: /asar_malumot 3  (raqamlar /asarlar da)"); return
    d = bk_.get_detail(n)
    _BOOKS_STATE[ADMIN_ID] = {'mode': 'info', 'n': n, 'first': True}
    cur = f"\n\nHozirgi ma‘lumot ({len(d['info'])} belgi) yangisi bilan ALMASHADI." if d['info'] else ""
    await update.message.reply_text(
        f"ℹ️ {n}-asar «{d['title']}» uchun MA‘LUMOT rejimi.{cur}\n\n"
        "Ma‘lumot matnini yuboring. Birinchi qatorda muallifni yozishingiz mumkin:\n"
        "Muallif: Abdulla Qodiriy\n(qolgan qatorlar — janr, yil, qisqa mazmun, qahramonlar, g‘oya...)\n\n"
        "Matn uzun bo‘lsa, bir nechta xabar qilib yuboring — ular ketma-ket qo‘shiladi.\n✅ Tugatish: /asar_tamom")

async def asar_test_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    n = _book_arg(context)
    if n is None or not bk_.exists(n):
        await update.message.reply_text("Raqamini yozing: /asar_test 3  (raqamlar /asarlar da)"); return
    d = bk_.get_detail(n)
    _BOOKS_STATE[ADMIN_ID] = {'mode': 'test', 'n': n, 'first': True}
    await update.message.reply_text(
        f"📝 {n}-asar «{d['title']}» uchun TEST rejimi. Hozir: {d['qn']} ta savol.\n\n"
        "Savollarni shu ko‘rinishda yuboring (bir xabarda ko‘p savol bo‘lishi mumkin):\n\n" + TEST_SAMPLE +
        "\n\nHar bir xabar mavjud savollarga QO‘SHILADI. Tozalash: /asar_test_tozala " + str(n) + "\n✅ Tugatish: /asar_tamom")

async def asar_test_tozala_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    n = _book_arg(context)
    if n is None or not bk_.exists(n):
        await update.message.reply_text("Raqamini yozing: /asar_test_tozala 3"); return
    await update.message.reply_text(f"🧹 {n}-asar testidan {bk_.clear_questions(n)} ta savol o‘chirildi.")

async def asar_ochiq_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    items = bk_.list_books()
    weak = [x for x in items if not x['has_info'] or not x['qn']]
    mp.set_books_ready(True)
    msg = f"🔓 Badiiy asarlar bo‘limi HAMMA UCHUN ochildi (pullik: {mp.fmt_uzs(mp.BOOKS_UZS)} so‘m).\nAsarlar: {len(items)} ta."
    if weak:
        msg += "\n\n⚠️ Ma‘lumot yoki testi yo‘q asarlar:\n" + "\n".join(f"{x['n']}. {x['title']} — " + ("ℹ️ yo‘q " if not x['has_info'] else "") + ("📝 yo‘q" if not x['qn'] else "") for x in weak[:15])
    await update.message.reply_text(msg + "\n\nYopish: /asar_yopiq")

async def asar_yopiq_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    mp.set_books_ready(False)
    await update.message.reply_text("🔒 Bo‘lim yopildi: foydalanuvchilarga «Jarayonda» yozuvi ko‘rinadi, faqat siz ko‘rasiz.\nOchish: /asar_ochiq")

async def asarlar_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    items = bk_.list_books()
    holat = "OCHIQ (foydalanuvchilar ko‘radi)" if mp.books_ready() else "JARAYONDA (faqat admin ko‘radi)"
    lines = "\n".join(f"{x['n']}. {x['title']}  —  🖼{1 + x['pics']}  ℹ️{'✅' if x['has_info'] else '❌'}  📝{x['qn']}" for x in items) or "— hali asar yo‘q —"
    await update.message.reply_text(f"📚 Badiiy asarlar: {len(items)} ta\nHolat: {holat}\n(🖼 rasm • ℹ️ ma‘lumot • 📝 test savollari)\n\n{lines}\n\n{BOOKS_HELP}\n\n{bk_.folder_report(BOOKS_DIR)}")

async def asar_import_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    n = bk_.seed_from_dir(BOOKS_DIR, force=True)
    await update.message.reply_text(f"📥 Papkadan ko‘chirildi: {n} ta asar.\nJami: {len(bk_.list_books())} ta\n\n{bk_.folder_report(BOOKS_DIR)}")

async def asar_ochir_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    try: n = int((context.args or [""])[0])
    except Exception:
        await update.message.reply_text("Raqamini yozing: /asar_ochir 3  (raqamlar /asarlar da)"); return
    await update.message.reply_text("🗑 O‘chirildi." if bk_.delete(n) else "Bunday raqam topilmadi.")

async def asar_nom_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    a = context.args or []
    if len(a) < 2 or not a[0].isdigit():
        await update.message.reply_text("Namuna: /asar_nom 3 Yangi nom"); return
    await update.message.reply_text("✅ Nomi o‘zgardi." if bk_.rename(int(a[0]), " ".join(a[1:])) else "Bunday raqam topilmadi.")

async def books_upload_handler(update, context):
    m = update.message
    if not m or update.effective_user.id != ADMIN_ID: return
    st = _BOOKS_STATE.get(ADMIN_ID) or {'mode': 'new', 'n': None}
    title = (m.caption or "").strip()
    if st['mode'] == 'new' and not title:
        await m.reply_text("⚠️ Asar nomi yozilmagan. Rasmni qayta yuboring va izohga (caption) asar nomini yozing."); raise ApplicationHandlerStop
    try:
        if m.photo: f = await m.photo[-1].get_file()
        elif m.document and (m.document.mime_type or "").startswith("image/"): f = await m.document.get_file()
        else: return
        raw = bytes(await f.download_as_bytearray())
        if st['mode'] == 'pic':
            pid = bk_.add_pic(st['n'], raw)
            await m.reply_text(f"✅ {st['n']}-asarga rasm qo‘shildi (jami qo‘shimcha: {len(bk_.pic_ids(st['n']))}). Yana yuboring yoki /asar_tamom")
        else:
            n = bk_.add(title, raw)
            await m.reply_text(f"✅ Qo‘shildi: {n}. {title}\n\nEndi shu asarga:\nℹ️ /asar_malumot {n}\n📝 /asar_test {n}\n🖼 /asar_rasm {n}\n\nYana asar rasmini yuboring yoki /asar_tamom")
    except Exception as e:
        logger.exception("books upload failed")
        await m.reply_text(f"⚠️ Rasmni saqlab bo‘lmadi: {e}")
    raise ApplicationHandlerStop

async def books_text_handler(update, context):
    """Ma'lumot yoki test matnini qabul qiladi (admin, /asar_malumot yoki /asar_test dan keyin)."""
    m = update.message
    if not m or update.effective_user.id != ADMIN_ID or not m.text: return
    st = _BOOKS_STATE.get(ADMIN_ID)
    if not st or st['mode'] not in ('info', 'test'): return
    n, text = st['n'], m.text.strip()
    try:
        if st['mode'] == 'info':
            author = None; lines = text.split("\n")
            mm = re.match(r"^\s*Muallif\s*[:\-]\s*(.+)$", lines[0], re.I)
            if mm: author = mm.group(1).strip(); text = "\n".join(lines[1:]).strip()
            bk_.set_info(n, text, author=author, append=not st['first'])
            st['first'] = False
            d = bk_.get_detail(n)
            await m.reply_text(f"✅ Saqlandi: {len(d['info'])} belgi" + (f" • muallif: {d['author']}" if d['author'] else "") + "\nYana matn yuborsangiz — qo‘shiladi. Tugatish: /asar_tamom")
        else:
            qs, errs = bk_.parse_bulk(text)
            if not qs:
                await m.reply_text("❌ Savol topilmadi. Namunadagi ko‘rinishda yozing:\n\n" + TEST_SAMPLE)
            elif errs:
                await m.reply_text("❌ Xatolar (hech narsa saqlanmadi):\n" + "\n".join(errs[:8]) + "\n\nTuzatib qayta yuboring.")
            else:
                total = bk_.add_questions(n, qs)
                await m.reply_text(f"✅ {len(qs)} ta savol qo‘shildi. Jami: {total} ta.\nYana yuboring yoki /asar_tamom")
    except Exception as e:
        logger.exception("books text failed")
        await m.reply_text(f"⚠️ Saqlab bo‘lmadi: {e}")
    raise ApplicationHandlerStop

async def guruh_cmd(update, context):
    if update.effective_user.id not in PAY_APPROVERS: return
    if context.args:
        link = context.args[0].strip()
        if not link.startswith("https://t.me/"):
            await update.message.reply_text("⚠️ Havola https://t.me/ bilan boshlanishi kerak."); return
        mp.set_group_link(link)
        await update.message.reply_text(f"✅ G‘azal guruhi havolasi saqlandi:\n{link}"); return
    await update.message.reply_text(f"🌙 G‘azal kursi guruhi\n\n🔗 Havola: {mp.group_link() or 'kiritilmagan'}\n💰 Narx: {mp.fmt_uzs(mp.GAZAL_GROUP_UZS)} so‘m\n👥 A’zolar (to‘lov qilganlar): {mp.group_count()}\n\nHavolani o‘zgartirish:\n/guruh https://t.me/+xxxxxxxx")

async def tolovlar_cmd(update, context):
    if update.effective_user.id not in PAY_APPROVERS: return
    r = mp.revenue_summary(); rows = mp.list_pending(10)
    await update.message.reply_text(
        "💳 QO‘LDA TO‘LOVLAR\n\n"
        f"Bugun: {r['day_n']} ta • {mp.fmt_uzs(r['day_sum'])} so‘m\n"
        f"Shu oy: {r['month_n']} ta • {mp.fmt_uzs(r['month_sum'])} so‘m\n"
        f"Tekshiruvni kutayotgan: {len(rows)} ta")
    for o in rows:
        cap = (f"💳 KUTILAYOTGAN #{o['id']}\n🆔 {o['user_id']}\n📦 {mp.plan_title(o['kind'], o['plan'])}\n"
               f"💰 {mp.fmt_uzs(o['amount'])} so‘m\n🕒 {_tashkent(o['updated_at'])}")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"payok_{o['id']}"),
                                    InlineKeyboardButton("❌ Rad etish", callback_data=f"payno_{o['id']}")]])
        try:
            if o["proof_type"] == "photo": await context.bot.send_photo(update.effective_chat.id, o["proof_file_id"], caption=cap, reply_markup=kb)
            else: await context.bot.send_document(update.effective_chat.id, o["proof_file_id"], caption=cap, reply_markup=kb)
        except Exception:
            logger.exception("pending order resend failed")

async def paket_cmd(update, context):
    upsert_user(update.effective_user)
    if not await require_subscription(update, context): return
    _uid = update.effective_user.id
    lines = "\n".join(f"• {pack_label(p)} — {p['stars']} ⭐ yoki {mp.fmt_uzs(p['uzs'])} so‘m" + (f" (chegirma −{p['discount']}%)" if p['discount'] else "") for p in mp.packs_for(_uid, "essay"))
    await update.message.reply_text("🛒 ESSE TEKSHIRUVI PAKETLARI\n\n" + lines + "\n\n" + offer_line(_uid) + "✅ Muddatsiz saqlanadi (7 kunlik paketdan tashqari). Bepul kunlik limitdan keyin ishlatiladi.\nTo‘lov usulini tanlang:",
                                    reply_markup=pack_keyboard("essay", _uid))

async def premium_cmd(update, context):
    upsert_user(update.effective_user)
    if not await require_subscription(update, context): return
    uid = update.effective_user.id
    await update.message.reply_text(
        "🌟 PREMIUM\n\n"
        f"• {GROWTH_DAYS} kun davomida kuniga {AI_PREMIUM_DAILY} ta AI esse mashqi / dalil topish (oddiy foydalanuvchida {AI_FREE_DAILY} ta).\n\n"
        + growth_premium_text(uid), reply_markup=GROWTH_GATE_KEYBOARD)

# ---------- Referal
def test_link(code):
    return f"https://t.me/{BOT_USERNAME}?start=test_{code}" if BOT_USERNAME else ""

def miniapp_test_url(code):
    base = miniapp_web_url()
    if not base: return ""
    return f"{base}{'&' if '?' in base else '?'}test={quote(code)}"

async def open_shared_test(message, code, uid=None, is_new=False):
    """t.me/bot?start=test_KOD havolasi: o'quvchini to'g'ri testga olib boradi (u allaqachon ro'yxatdan o'tgan)."""
    code = re.sub(r"[^A-Za-z0-9-]", "", code or "").upper()[:20]
    kind = title = None; extra = ""
    if code.startswith("T-"):
        t = st_.get(code)
        if t: kind, title, extra = "simple", t["title"], f"{len(t['questions'])} ta savol"
    else:
        t = get_test(code)
        if t: kind, title, extra = "ms", t["title"], f"{t.get('duration_min', 180)} daqiqa • 45 topshiriq"
    if not kind:
        await message.reply_text("❌ Bunday test topilmadi. Havola eskirgan yoki test o‘chirilgan bo‘lishi mumkin.", reply_markup=MAIN_KEYBOARD); return
    if tr_.is_closed(kind, code):
        await message.reply_text(f"⌛ «{title}» testi yakunlangan — javob qabul qilinmaydi.", reply_markup=MAIN_KEYBOARD); return
    try:
        if uid and int(uid)!=int(ADMIN_ID) and (st_.has_attempt(uid, t['id']) if kind=="simple" else national_has_attempt(uid, t['id'])):
            await message.reply_text(f"✅ «{title}» testini allaqachon ishlagansiz. Test faqat bir marta topshiriladi.", reply_markup=MAIN_KEYBOARD); return
    except Exception: logger.exception("attempt check failed")
    if uid:
        try: gt_.register_visit(kind, code, uid, is_new)
        except Exception: logger.exception("test visit register failed")
    url = miniapp_test_url(code)
    text = f"📝 {title}\n🔑 Kod: {code}\n{extra}\n\nTestni boshlash uchun pastdagi tugmani bosing 👇"
    if not url:
        await message.reply_text(text + "\n\n(Mini App manzili sozlanmagan — ilovani menyudan oching va kodni kiriting.)", reply_markup=MAIN_KEYBOARD); return
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Testni boshlash", web_app=WebAppInfo(url=url))]]))

def _game_card_secret(): return str(TELEGRAM_BOT_TOKEN)

def game_card_url(kind, name, correct=0, total=5, rank=""):
    """Imzolangan, ochiq rasm havolasi (Telegram rasmni shu manzildan oladi). Tashqi manzil bo'lmasa — ''."""
    if not RENDER_EXTERNAL_URL: return ""
    from share_cards import sign
    name = (name or "")[:22]; rank = (rank or "")[:30]; c = int(correct); t = int(total)
    sg = sign(_game_card_secret(), kind, name, c, t, rank)
    return f"{RENDER_EXTERNAL_URL}/gcard.jpg?k={kind}&n={quote(name)}&c={c}&t={t}&r={quote(rank)}&s={sg}"

def _first_name(uid):
    try:
        n = mx.user_name(int(uid)); return n if not n.startswith("Talabgor ") else "Do‘stingiz"
    except Exception: return "Do‘stingiz"

async def _send_game_invite(message, text, url, btn_text, caption_photo_kind=None, name="", score=0, total=5):
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, web_app=WebAppInfo(url=url))]]) if url else MAIN_KEYBOARD
    if caption_photo_kind:
        try:
            from share_cards import render_card
            buf = render_card(caption_photo_kind, name, score, total, ""); buf.name = "card.jpg"
            await message.reply_photo(buf, caption=text, reply_markup=kb); return
        except Exception: logger.exception("game card send failed")
    await message.reply_text(text, reply_markup=kb)

async def open_duel(message, arg):
    """t.me/bot?start=duel_SEED_BALL_UID — do'st chaqirgan 5 savollik bellashuvni Mini App'da ochadi (savollar SEED bo'yicha bir xil)."""
    parts = (arg or "").split("_")
    if not parts or not parts[0].isdigit() or len(parts[0]) > 9:
        await message.reply_text("Bellashuv havolasi noto‘g‘ri.", reply_markup=MAIN_KEYBOARD); return
    seed = parts[0]; score = parts[1] if len(parts) > 1 and parts[1].isdigit() and len(parts[1]) <= 2 else ""
    frm = parts[2] if len(parts) > 2 and parts[2].isdigit() and len(parts[2]) <= 12 else ""
    base = miniapp_web_url()
    nm = _first_name(frm) if frm else "Do‘stingiz"
    text = (f"⚔️ {nm} sizni ona tili bellashuviga chaqirdi!\n\n" + (f"🎯 Uning natijasi: {score}/5\n" if score else "")
            + "⏱ 5 ta savol • 2 daqiqa\n🎁 Kirganingiz uchun bonus ham hisobingizda.\n\nYenga olasizmi? 👇")
    if not base:
        await message.reply_text(text + "\n\n(Mini App manzili sozlanmagan.)", reply_markup=MAIN_KEYBOARD); return
    url = f"{base}{'&' if '?' in base else '?'}duel={seed}" + (f"_{score}" if score else "_") + (f"_{frm}" if frm else "")
    await _send_game_invite(message, text, url, "⚔️ Qabul qilaman", "duel", nm, int(score) if score else 0, 5)

async def open_play_invite(message, arg):
    """t.me/bot?start=play_UID — do'st «Ona tilini o'ynab o'rganamiz» bo'limiga chaqirdi."""
    frm = arg if arg.isdigit() and len(arg) <= 12 else ""
    nm = _first_name(frm) if frm else "Do‘stingiz"
    base = miniapp_web_url()
    text = (f"🎮 {nm} sizni «Ona tilini o‘ynab o‘rganamiz» o‘yiniga chaqirdi!\n\n"
            "📅 Kunlik 5 savol • 📝 DTM sinov • ⚔️ do‘stlar bilan bellashuv\n🔥 Har kuni seriya yig‘ing, darajangizni oshiring.\n\nHoziroq sinab ko‘ring 👇")
    if not base:
        await message.reply_text(text, reply_markup=MAIN_KEYBOARD); return
    url = f"{base}{'&' if '?' in base else '?'}game=1"
    await _send_game_invite(message, text, url, "🎮 O‘ynashni boshlash", "play", nm)

def ref_link(uid):
    return f"https://t.me/{BOT_USERNAME}?start=ref_{uid}" if BOT_USERNAME else ""

def share_keyboard(uid):
    link = ref_link(uid)
    if not link: return None
    text = "✍️ Esseni sun’iy intellekt bilan tekshirtiring — Milliy sertifikat (ona tili) uchun. Bepul sinab ko‘ring:"
    url = f"https://t.me/share/url?url={quote(link)}&text={quote(text)}"
    return InlineKeyboardMarkup([[InlineKeyboardButton("📤 Do‘stlarga ulashish", url=url)]])

async def send_referral_info(message, uid):
    link = ref_link(uid)
    if not link:
        await message.reply_text("⚠️ Havola hozircha tayyor emas. Birozdan so‘ng qayta urinib ko‘ring."); return
    s = mp.ref_stats(uid)
    await message.reply_text(
        "🎁 DO‘ST TAKLIF QILING — BEPUL TEKSHIRUV OLING\n\n"
        f"• Do‘stingiz havolangiz orqali kirib, kanalga a’zo bo‘lsa — u +{mp.REF_INVITEE_BONUS} ta bepul esse tekshiruvi oladi.\n"
        f"• U birinchi esseni tekshirtirsa — siz +{mp.REF_INVITER_BONUS} ta bepul esse tekshiruvi olasiz.\n\n"
        f"🔗 Sizning havolangiz:\n{link}\n\n"
        f"👥 Taklif qilganlar: {s['invited']} • Mukofot olingan: {s['rewarded']} (yana {s['left']} ta mumkin)",
        reply_markup=share_keyboard(uid), disable_web_page_preview=True)

async def ref_info_callback(update, context):
    q = update.callback_query; await q.answer()
    await send_referral_info(q.message, q.from_user.id)

async def taklif_cmd(update, context):
    upsert_user(update.effective_user)
    if not await require_subscription(update, context): return
    await send_referral_info(update.message, update.effective_user.id)

async def grant_invitee_bonus(bot, uid):
    try:
        inviter = mp.give_invitee_bonus(uid)
    except Exception:
        logger.exception("invitee bonus failed"); return
    if inviter and mp.REF_INVITEE_BONUS > 0:
        try: await bot.send_message(uid, f"🎁 Taklif bonusi: +{mp.REF_INVITEE_BONUS} ta bepul esse tekshiruvi hisobingizga qo‘shildi. (/balans)")
        except Exception: pass

def _notify_inviter(inviter):
    try:
        tg_api("sendMessage", {"chat_id": inviter, "text": f"🎉 Siz taklif qilgan do‘stingiz birinchi esseni tekshirtirdi!\n➕ +{mp.REF_INVITER_BONUS} ta bepul esse tekshiruvi hisobingizga qo‘shildi. (/balans)"})
    except Exception:
        logger.exception("inviter notify failed")

async def reftop_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    rows = mp.top_referrers(10)
    if not rows:
        await update.message.reply_text("🎁 Hozircha takliflar yo‘q."); return
    lines = [f"{i}. {r['first_name'] or r['uid']} {('@'+r['username']) if r['username'] else ''} (id {r['uid']}) — {r['invited']} ta taklif, {r['active']} tasi faol" for i, r in enumerate(rows, 1)]
    await update.message.reply_text("🏆 ENG KO‘P TAKLIF QILGANLAR\n\n" + "\n".join(lines))


# ============================================================
# 📣 KANALGA KUNLIK MAVZU • 🔔 ESLATMA • 🏆 SOVRIN • 👩‍🏫 USTOZLAR HAMKORLIGI
# ============================================================
import urllib.error

def _tg_blocking(method, payload):
    """tg_api'ni chaqiradi; (ok, error_code) qaytaradi."""
    try:
        tg_api(method, payload); return True, 0
    except urllib.error.HTTPError as e:
        return False, e.code
    except Exception:
        logger.exception("tg_api %s", method); return False, -1

def topic_recipients():
    """Mavzuni olishi mumkin bo'lganlar: botdan foydalangan, bloklanmagan va /eslatma off qilmaganlar."""
    with mx.db() as c:
        rows = c.execute("""SELECT user_id FROM (SELECT user_id FROM users UNION SELECT user_id FROM mini_users)
                            WHERE user_id NOT IN (SELECT user_id FROM reminders WHERE optout=1)""").fetchall()
    return [int(r[0]) for r in rows if not mx.is_banned(int(r[0]))]

def _topic_text():
    return ("📝 BUGUNGI ESSE MAVZUSI\n\n" + daily_essay_topic() + "\n\n"
            "✍️ Esseni yozing va botga yuboring — sun’iy intellekt BBA mezonlari bo‘yicha tekshiradi, xatolaringizni ko‘rsatadi.\n\n"
            "🔕 Xabarni o‘chirish: /eslatma off")

def post_channel_topic(force=False):
    """Bugungi esse mavzusini yuboradi. Rejim (/mavzu_rejim): users (standart) | channel | both | off. (ok, xabar)."""
    mode = setting("topic_mode", "users")
    if mode == "off":
        return True, "kunlik mavzu o‘chirilgan (/mavzu_rejim users)"
    day = datetime.now(mx.TZ).strftime("%Y-%m-%d")
    if not force and setting("topic_posted_day", "") == day:
        return True, "bugun allaqachon yuborilgan"
    set_setting("topic_posted_day", day)     # avval belgilaymiz: restartda ikki marta ketmasin
    text = _topic_text(); report = []
    markup = {"inline_keyboard": [[{"text": "✍️ Mavzuda esse yozish", "url": f"https://t.me/{BOT_USERNAME}?start=topic"}]]} if BOT_USERNAME else None
    ok_all = True
    if mode in ("channel", "both"):
        payload = {"chat_id": REQUIRED_CHANNEL, "text": text.replace("\n\n🔕 Xabarni o‘chirish: /eslatma off", "")}
        if markup: payload["reply_markup"] = markup
        ok, code = _tg_blocking("sendMessage", payload)
        report.append("kanal: " + ("✅" if ok else f"❌ xato {code} (bot kanalda admin bo‘lishi kerak)")); ok_all = ok_all and ok
    if mode in ("users", "both"):
        ids = topic_recipients(); sent = 0; blocked = 0
        for uid in ids:
            payload = {"chat_id": uid, "text": text, "disable_notification": True}
            if markup: payload["reply_markup"] = markup
            ok, code = _tg_blocking("sendMessage", payload)
            if ok: sent += 1
            elif code in (400, 403): blocked += 1; mx.reminder_mark(uid, optout=True)   # bot bloklangan — keyingi safar yubormaymiz
            time.sleep(0.06)
        report.append(f"foydalanuvchilar: {sent}/{len(ids)} yuborildi" + (f", {blocked} tasi botni bloklagan" if blocked else ""))
        ok_all = ok_all and (sent > 0 or not ids)
    return ok_all, " • ".join(report)

def _miniapp_check():
    """Mini App fayllari yangimi? (1) Render'dagi nusxa, (2) MINIAPP_URL alohida hostda bo'lsa o'sha manzil."""
    lines = []; marker = 'id="sModeKey"'
    try:
        local = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'miniapp', 'index.html'), encoding='utf-8').read()
        lines.append(f"• Render'dagi Mini App: {'✅ yangi (javoblar kaliti bor)' if marker in local else '❌ ESKI (javoblar kaliti yo‘q)'}")
    except Exception as e:
        lines.append(f"• Render'dagi Mini App fayli o‘qilmadi: {e}")
    ext = (MINIAPP_URL or '').split('?')[0]
    own = (RENDER_EXTERNAL_URL or '').rstrip('/')
    if ext and not ext.startswith(own + '/'):
        try:
            import urllib.request
            req = urllib.request.Request(ext, headers={'Cache-Control': 'no-cache', 'User-Agent': 'Mozilla/5.0'})
            html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', 'ignore')
            lines.append(f"• Tashqi manzil ({ext}): {'✅ yangi' if marker in html else '❌ ESKI — miniapp papkasini shu hostga qayta yuklang'}")
        except Exception as e:
            lines.append(f"• Tashqi manzil ({ext}) tekshirilmadi: {e}")
    else:
        lines.append("• Mini App Render'ning o‘zidan beriladi (MINIAPP_URL alohida host emas).")
    return lines

VIEW_LABELS = {"home":"🏠 Bosh sahifa","expert":"👨‍🏫 Ekspert esse","omonimlug":"🎭 Omonimlar lug‘ati","dict":"📖 Imlo lug‘ati","mumtoz":"📜 Mumtoz lug‘at","paronim":"🔀 Paronimlar","sinonim":"🔗 Sinonimlar","active":"⭐ Faol 1000 so‘z",
               "prep":"🎓 Milliy sertifikatga tayyorlov","gazal":"📚 G‘azal kursi","gazallib":"🌙 G‘azal tahlilini o‘rganamiz","books":"🖼 Badiiy asarlar (ro‘yxat)","games":"🎮 Ona tilini o‘ynab o‘rganamiz","growth":"✍️ Esse mashqi","rating":"🏆 Reyting",
               "author":"👤 Muallif","premium":"💎 Premium","essewin":"✍️ Esse (oyna)","attestwin":"🏅 Attestatsiyaga tayyorlov","dicts":"📚 Lug‘atlar (bo‘lim)","stats":"📊 Statistikam","national":"🧪 Diagnostik test","testResults":"📋 Test natijalari","panel":"🛠 Ustoz paneli","admin":"👑 Admin"}

def view_label(sec):
    if sec.startswith("game:"):
        return "🎮 O‘yin: " + {"imlo":"Imlo","sinonim":"Sinonim","paronim":"Paronim","omonim":"Omonim","daily":"Kunlik 5 savol","mistakes":"Xatolarim","dtm":"DTM sinov","topic":"Mavzu bo‘yicha mashq","duel":"Do‘st bilan bellashuv"}.get(sec[5:], sec[5:])
    if sec.startswith("book:"):
        try: d = bk_.get_detail(int(sec[5:]))
        except Exception: d = None
        return ("🌙 Qo‘llanma: " if d and d.get("sec") == "gazal" else "📕 Asar: ") + (d["title"] if d else sec)
    return VIEW_LABELS.get(sec, sec)

def view_report():
    """{'today':{...},'week':{...},'month':{...},'all':{...}} — har biri: jami (ko'rish, noyob) va bo'limlar ro'yxati."""
    out = {}
    for key, days in (("today", 1), ("week", 7), ("month", 30), ("all", None)):
        v, u = mx.view_totals(days)
        out[key] = {"views": v, "users": u, "items": [{"section": sc, "name": view_label(sc), "views": a, "users": b} for sc, a, b in mx.view_stats(days)[:40]]}
    return out

async def korishlar_cmd(update, context):
    """/korishlar [bugun|hafta|oy] — Mini App bo'limlari va asarlar ko'rilishi (faqat admin)."""
    if update.effective_user.id != ADMIN_ID: return
    a = (context.args[0].lower() if context.args else "hafta")
    key = {"bugun":"today","today":"today","hafta":"week","week":"week","oy":"month","month":"month","hammasi":"all","all":"all"}.get(a, "week")
    nm = {"today":"bugun","week":"oxirgi 7 kun","month":"oxirgi 30 kun","all":"butun davr"}[key]
    r = await asyncio.to_thread(view_report); d = r[key]
    lines = [f"👁 Mini App ko‘rishlari — {nm}", f"Jami: {d['views']} ta ko‘rish • {d['users']} ta alohida foydalanuvchi", ""]
    for i, x in enumerate(d["items"][:25], 1): lines.append(f"{i}. {x['name']} — {x['views']} ta ({x['users']} kishi)")
    if not d["items"]: lines.append("Hali ma’lumot yo‘q.")
    lines.append("\nDavr: /korishlar bugun | hafta | oy | hammasi")
    await update.message.reply_text("\n".join(lines))

async def versiya_cmd(update, context):
    """/versiya — bot va Mini App qaysi versiyada ishlayotganini ko'rsatadi (faqat admin)."""
    if update.effective_user.id != ADMIN_ID: return
    lines = await asyncio.to_thread(_miniapp_check)
    await update.message.reply_text(f"🧩 Bot versiyasi: {APP_VERSION}\n" + "\n".join(lines) +
        "\n\nMini App ichida (bosh sahifa pastida) ham versiya yoziladi. Agar u yo‘q yoki boshqa bo‘lsa — telefonda eski nusxa ochilyapti: Mini App'ni yoping va qayta oching.")

async def xarajat_cmd(update, context):
    """/xarajat [bugun|hafta|oy] — AI xarajati hisoboti (faqat admin)."""
    if update.effective_user.id != ADMIN_ID: return
    a = (context.args[0].lower() if context.args else "bugun")
    period = {"bugun":"bugun","today":"bugun","hafta":"hafta","week":"hafta","oy":"oy","month":"oy"}.get(a, "bugun")
    def nm(uid):
        f, l, un = tr_._split_name(uid)
        return (f + (' ' + l if l else '') + (' ' + un if un else '') + f' ({uid})').strip()
    await update.message.reply_text(ac_.fmt_report(period, nm, MODEL))

async def mavzu_rejim_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    a = (context.args[0].lower() if context.args else "")
    if a in ("users", "channel", "both", "off"):
        set_setting("topic_mode", a)
    await update.message.reply_text(
        f"📝 Kunlik mavzu rejimi: {setting('topic_mode', 'users')}\n\n"
        "users — botdan foydalanuvchilarga shaxsiy xabar (standart)\nchannel — majburiy kanalga\nboth — ikkalasiga\noff — o‘chirilgan\n\n"
        "O‘zgartirish: /mavzu_rejim users\nHoziroq yuborish: /kanalpost yana")

def start_channel_topic_loop():
    hour = int(os.getenv("CHANNEL_TOPIC_HOUR", "8") or 8)      # Toshkent vaqti; -1 = o'chirilgan
    if hour < 0: return
    def run():
        time.sleep(90); warned = ""
        while True:
            try:
                t = datetime.now(mx.TZ)
                if hour <= t.hour < hour + 6 and setting("topic_posted_day", "") != t.strftime("%Y-%m-%d"):
                    ok, msg = post_channel_topic()
                    if not ok and warned != t.strftime("%Y-%m-%d"):
                        warned = t.strftime("%Y-%m-%d")
                        _tg_blocking("sendMessage", {"chat_id": ADMIN_ID, "text": "⚠️ Kunlik mavzu yuborilmadi: " + msg})
            except Exception:
                logger.exception("channel topic loop")
            time.sleep(300)
    threading.Thread(target=run, daemon=True).start()

async def kanalpost_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    force = bool(context.args and context.args[0].lower() in ("force", "yana"))
    ok, msg = await asyncio.to_thread(post_channel_topic, force)
    await update.message.reply_text(("✅ " if ok else "⚠️ ") + msg + ("" if force else "\n(Qayta joylash uchun: /kanalpost yana)"))

# ---- Eslatma
def start_reminder_loop():
    hour = int(os.getenv("REMIND_HOUR", "9") or 9)             # Toshkent vaqti; -1 = o'chirilgan
    if hour < 0: return
    def run():
        time.sleep(120)
        while True:
            try:
                t = datetime.now(mx.TZ); day = t.strftime("%Y-%m-%d")
                if hour <= t.hour < hour + 4 and setting("remind_day", "") != day:
                    set_setting("remind_day", day)                # avval belgilaymiz: restartda ikki marta yuborilmasin
                    ids = mx.reminder_candidates(FREE_ESSAY_DAILY, AI_FREE_DAILY)
                    sent = 0
                    for uid in ids:
                        txt = (f"🔄 Bepul AI mashq/dalil limitingiz yangilandi!\n\nBugun {AI_FREE_DAILY} ta esse mashqi yoki dalil topishni bepul ishlatishingiz mumkin.\n"
                               "Mini App'ni oching.\n\n/eslatma — eslatmani o‘chirish")
                        ok, code = _tg_blocking("sendMessage", {"chat_id": uid, "text": txt})
                        if ok: mx.reminder_mark(uid); sent += 1
                        elif code in (400, 403): mx.reminder_mark(uid, optout=True)   # bot bloklangan / chat yo'q
                        time.sleep(0.08)
                    logger.info("eslatma yuborildi: %s/%s", sent, len(ids))
            except Exception:
                logger.exception("reminder loop")
            time.sleep(600)
    threading.Thread(target=run, daemon=True).start()

async def eslatma_cmd(update, context):
    upsert_user(update.effective_user); uid = update.effective_user.id
    arg = (context.args[0].lower() if context.args else "")
    if arg in ("off", "ochir", "o‘chir"): mx.reminder_mark(uid, optout=True); await update.message.reply_text("🔕 Eslatma o‘chirildi. Yoqish: /eslatma on"); return
    if arg in ("on", "yoq", "yoqish"): mx.reminder_mark(uid, optout=False); await update.message.reply_text("🔔 Eslatma yoqildi."); return
    off = mx.reminder_optout(uid)
    await update.message.reply_text(f"🔔 Eslatma hozir: {'o‘chiq' if off else 'yoqilgan'}.\n\nBepul limitingiz yangilanganda xabar beramiz (3 kunda ko‘pi bilan 1 marta).\nO‘chirish: /eslatma off • Yoqish: /eslatma on")

# ---- Haftalik/oylik 1-o'rin sovrini (Premium)
def prize_hook(a):
    days = mx.PRIZE_DAYS.get(a["kind"], 0)
    if days <= 0 or a["rank"] != 1 or mx.is_banned(a["user_id"]): return
    uid = int(a["user_id"])
    if not mx.claim_charge(f"prize:{a['kind']}:{a['code']}", uid, "prize", 0):
        return                                                    # bu sovrin avval berilgan
    try: exp = grant_growth_premium(uid, days, f"prize:{a['code']}", 0)
    except Exception:
        mx.release_charge(f"prize:{a['kind']}:{a['code']}"); raise
    _tg_blocking("sendMessage", {"chat_id": uid, "text":
        f"🎁 Sovrin: {a['data']['period_name']} reyting g‘olibi sifatida sizga Premium {days} kunga sovg‘a qilindi!\n⏳ Muddat: {exp.strftime('%d.%m.%Y %H:%M')} UTC"})

# ---- Ustozlar hamkorligi
async def ustoz_admin_cmd(update, context):
    if update.effective_user.id != ADMIN_ID: return
    a = [x for x in (context.args or [])]
    sub_ = a[0].lower() if a else ""
    try:
        if sub_ == "add" and len(a) >= 2:
            pct = mp.teacher_set(int(a[1]), int(a[2]) if len(a) >= 3 else mp.TEACHER_DEFAULT_PERCENT)
            link = f"https://t.me/{BOT_USERNAME}?start=ust_{int(a[1])}" if BOT_USERNAME else "(BOT_USERNAME aniqlanmadi)"
            await update.message.reply_text(f"✅ Ustoz qo‘shildi: {int(a[1])} — ulush {pct}% • o‘quvchilarga chegirma {mp.TEACHER_STUDENT_DISCOUNT}%\n🔗 Havola:\n{link}\n\nUstoz o‘z statistikasini /ustozim orqali ko‘radi."); return
        if sub_ == "off" and len(a) >= 2:
            await update.message.reply_text("✅ O‘chirildi." if mp.teacher_off(int(a[1])) else "Topilmadi."); return
        if sub_ == "paid" and len(a) >= 2:
            s = mp.teacher_mark_paid(int(a[1]))
            await update.message.reply_text(f"✅ To‘langan deb belgilandi: {mp.fmt_uzs(s)} so‘m"); return
    except ValueError:
        await update.message.reply_text("⚠️ ID va foiz raqam bo‘lishi kerak."); return
    rows = mp.teachers_report()
    if not rows:
        await update.message.reply_text(f"👩‍🏫 USTOZLAR\n\nHali yo‘q.\n\nQo‘shish: /ustoz add <user_id> [foiz] (foiz yozilmasa ustozga ulush {mp.TEACHER_DEFAULT_PERCENT}%; o‘quvchilarga chegirma {mp.TEACHER_STUDENT_DISCOUNT}%)\nO‘chirish: /ustoz off <user_id>\nTo‘landi: /ustoz paid <user_id>"); return
    lines = ["👩‍🏫 USTOZLAR\n"]
    for r, s in rows:
        nm = (f"@{r['un']}" if r["un"] else r["fn"] or str(r["user_id"]))
        lines.append(f"• {nm} (ID {r['user_id']}) — {r['percent']}%{'' if r['active'] else ' [o‘chirilgan]'}\n  talabalar: {s['students']} • sotuv: {s['sales_n']} ta / {mp.fmt_uzs(s['sales_sum'])} so‘m\n  ulush: {mp.fmt_uzs(s['commission'])} • to‘lanmagan: {mp.fmt_uzs(s['unpaid'])} so‘m")
    lines.append("\nQo‘shish: /ustoz add <id> [foiz] • O‘chirish: /ustoz off <id> • To‘landi: /ustoz paid <id>\nHisob Stars to‘lovlari uchun ro‘yxat narxi (so‘mda) asosida yuritiladi.")
    await update.message.reply_text("\n".join(lines))

async def ustozim_cmd(update, context):
    uid = update.effective_user.id
    t = mp.teacher_get(uid)
    if not t:
        await update.message.reply_text("Bu bo‘lim hamkor ustozlar uchun. Hamkor bo‘lish: @" + ADMIN_USERNAME); return
    s = mp.teacher_summary(uid)
    link = f"https://t.me/{BOT_USERNAME}?start=ust_{uid}" if BOT_USERNAME else "—"
    await update.message.reply_text(
        "👩‍🏫 USTOZ KABINETI\n\n"
        f"🔗 Sizning havolangiz (o‘quvchilaringizga yuboring):\n{link}\n🎁 Havola orqali kirgan o‘quvchilar doimiy −{mp.TEACHER_STUDENT_DISCOUNT}% chegirma oladi.\n\n"
        f"👥 O‘quvchilar: {s['students']}\n🧾 To‘lovlar: {s['sales_n']} ta • {mp.fmt_uzs(s['sales_sum'])} so‘m\n"
        f"💰 Sizning ulushingiz ({t['percent']}%): {mp.fmt_uzs(s['commission'])} so‘m\n⏳ Hali to‘lanmagan: {mp.fmt_uzs(s['unpaid'])} so‘m",
        disable_web_page_preview=True)

def main():
    init_db()
    init_national_db()
    mx.init_extra_db()
    mp.init_pay_db()
    try: tp_.init_teacher_db()
    except Exception: logger.exception("teacher_pro init")
    st_.init_simple_db(); tr_.init_results_db(); gt_.init_growth_db(); lh_.init(); ac_.init_cost_db(); bk_.init_books_db(); bk_.seed_from_dir(BOOKS_DIR)
    try: ms_.seed(bk_)   # v72: Mashq bo'limlariga tayyor mavzu va testlar (bir marta)
    except Exception: logger.exception('mashq_seed')
    try: mx.cache_init()
    except Exception: logger.exception("persistent cache init failed (xotira keshi ishlaydi)")
    mx.award_loop(TELEGRAM_BOT_TOKEN,ADMIN_ID,log=logging.warning,on_award=prize_hook)
    start_channel_topic_loop()
    start_reminder_loop()
    start_backup_loop()
    start_cleanup_loop()
    start_memory_guard()
    init_prep_db()
    threading.Thread(target=start_health,daemon=True).start()
    threading.Thread(target=results_watcher,daemon=True).start()
    app=Application.builder().token(TELEGRAM_BOT_TOKEN).concurrent_updates(int(os.getenv('CONCURRENT_UPDATES','4') or 4)).post_init(configure_miniapp).build()
    app.add_handler(TypeHandler(Update,spam_guard),group=-1)
    app.add_handler(CommandHandler("backup",backup_cmd))
    app.add_handler(CommandHandler("baza",baza_cmd))
    app.add_handler(CommandHandler("tozala",tozala_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.CaptionRegex(r"^/restore"),restore_cmd))
    app.add_handler(CommandHandler("xatosavollar",xatosavollar_cmd))
    app.add_handler(CommandHandler("savol_yashir",savol_yashir_cmd))
    app.add_handler(CommandHandler("savol_och",savol_och_cmd))
    app.add_handler(CommandHandler("ban",ban_cmd))
    app.add_handler(CommandHandler("unban",unban_cmd))
    app.add_handler(PreCheckoutQueryHandler(precheckout_unified))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT,successful_payment_unified))
    app.add_handler(CallbackQueryHandler(unlock_callback, pattern=r"^unlock_full$"))
    app.add_handler(CallbackQueryHandler(national_essay_choice_callback, pattern=r"^nes_(auto|none|manual|write)$"))
    app.add_handler(CallbackQueryHandler(buy_pack_callback, pattern=r"^buy_pack_(essay|tool)(_[pw][0-9]+)?$"))
    app.add_handler(CallbackQueryHandler(cardpay_callback, pattern=r"^cardpay_"))
    app.add_handler(CallbackQueryHandler(cardcancel_callback, pattern=r"^cardcancel_[0-9]+$"))
    app.add_handler(CallbackQueryHandler(payadmin_callback, pattern=r"^pay(ok|no)_[0-9]+$"))
    app.add_handler(CallbackQueryHandler(ref_info_callback, pattern=r"^ref_info$"))
    app.add_handler(CallbackQueryHandler(buy_growth_callback, pattern=r"^buy_growth$"))
    app.add_handler(CallbackQueryHandler(growth_terms_callback, pattern=r"^growth_terms$"))
    app.add_handler(CommandHandler("karta",karta_cmd))
    app.add_handler(CommandHandler("avtokarta",avtokarta_cmd))
    app.add_handler(CommandHandler("ber",ber_cmd))
    app.add_handler(CommandHandler("ekspert",expert_cmd))
    app.add_handler(CommandHandler("ekspert_bekor",expert_cancel_cmd))
    app.add_handler(CommandHandler("ekspert_royxat",expert_list_cmd))
    app.add_handler(CommandHandler("tolamaganlar",unpaid_cmd))
    app.add_handler(CallbackQueryHandler(expert_send_callback, pattern=r"^expsend$"))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND & ExpertReplyFilter(), expert_reply_handler), group=-3)
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND & ExpertSubmitFilter(), expert_submit_handler), group=-2)
    app.add_handler(CommandHandler("guruh",guruh_cmd))
    app.add_handler(CommandHandler("kanal",kanal_cmd))
    app.add_handler(CommandHandler("asar",asar_cmd))
    app.add_handler(CommandHandler("asar_tamom",asar_tamom_cmd))
    app.add_handler(CommandHandler("asarlar",asarlar_cmd))
    app.add_handler(CommandHandler("asar_import",asar_import_cmd))
    app.add_handler(CommandHandler("asar_ochir",asar_ochir_cmd))
    app.add_handler(CommandHandler("asar_nom",asar_nom_cmd))
    app.add_handler(CommandHandler("asar_yordam",asar_yordam_cmd))
    app.add_handler(CommandHandler("asar_rasm",asar_rasm_cmd))
    app.add_handler(CommandHandler("asar_malumot",asar_malumot_cmd))
    app.add_handler(CommandHandler("asar_test",asar_test_cmd))
    app.add_handler(CommandHandler("asar_video",asar_video_cmd))
    app.add_handler(CommandHandler("asar_toldir",asar_toldir_cmd))
    app.add_handler(CommandHandler("asar_test_tozala",asar_test_tozala_cmd))
    app.add_handler(CommandHandler("asar_ochiq",asar_ochiq_cmd))
    app.add_handler(CommandHandler("asar_yopiq",asar_yopiq_cmd))
    app.add_handler(CommandHandler("asar_namuna",asar_namuna_cmd))
    app.add_handler(CommandHandler("umumiy_ochiq",umumiy_ochiq_cmd))
    app.add_handler(CommandHandler("umumiy_yopiq",umumiy_yopiq_cmd))
    app.add_handler(CallbackQueryHandler(proofis_callback, pattern=r"^proofis_(chek|esse)$"))
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.IMAGE) & BooksModeFilter(), books_upload_handler), group=-2)
    app.add_handler(MessageHandler((filters.VIDEO | filters.Document.VIDEO) & BooksVideoFilter(), books_video_handler), group=-2)
    app.add_handler(CommandHandler("gazal_fayl",gazal_fayl_cmd))
    app.add_handler(CommandHandler("gazal_ochish",gazal_ochish_cmd))
    app.add_handler(CommandHandler("esse_video",esse_video_cmd))
    app.add_handler(CommandHandler("esse_video_och",esse_video_och_cmd))
    app.add_handler(CommandHandler("esse_video_yop",esse_video_yop_cmd))
    app.add_handler(CommandHandler("esse_video_yuklash",esse_video_yuklash_cmd))
    app.add_handler(CommandHandler("gazal_yopish",gazal_yopish_cmd))
    app.add_handler(CommandHandler("gazal_narx",gazal_narx_cmd))
    app.add_handler(CommandHandler("gazal_royxat",gazal_royxat_cmd))
    app.add_handler(MessageHandler((filters.Document.ALL | filters.AUDIO | filters.VIDEO | filters.PHOTO) & GazalFileFilter(), gazal_file_handler), group=-2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & BooksTextFilter(), books_text_handler), group=-2)

    app.add_handler(CommandHandler("ustoz",ustoz_admin_cmd))
    app.add_handler(CommandHandler("ustozim",ustozim_cmd))
    app.add_handler(CommandHandler("eslatma",eslatma_cmd))
    app.add_handler(CommandHandler("kanalpost",kanalpost_cmd))
    app.add_handler(CommandHandler("mavzu_rejim",mavzu_rejim_cmd))
    app.add_handler(CommandHandler("tolovlar",tolovlar_cmd))
    app.add_handler(CommandHandler("reftop",reftop_cmd))
    app.add_handler(CommandHandler("taklif",taklif_cmd))
    app.add_handler(CommandHandler("paket",paket_cmd))
    app.add_handler(CommandHandler("premium",premium_cmd))
    # Chek skrinshoti: esse rasm/PDF handlerlaridan OLDIN turishi shart
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.IMAGE | filters.Document.PDF) & AwaitProofFilter(), pay_proof_handler))
    app.add_handler(CommandHandler("balans",balance_cmd))
    app.add_handler(CommandHandler("xarajat",xarajat_cmd))
    app.add_handler(CommandHandler("korishlar",korishlar_cmd))
    app.add_handler(CommandHandler("versiya",versiya_cmd))
    app.add_handler(CommandHandler("natija",last_result_cmd))
    app.add_handler(CommandHandler("paysupport",paysupport_cmd))
    app.add_handler(CommandHandler("terms",terms_cmd))
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
