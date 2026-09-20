import os
import re
import json
import logging
import threading
import base64
import sqlite3
import hashlib
import asyncio
from io import BytesIO, StringIO
import csv
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
)
from openai import OpenAI

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
PORT = int(os.getenv("PORT", "10000"))
REQUIRED_CHANNEL_USERNAME = os.getenv("REQUIRED_CHANNEL_USERNAME", "@milliysertifikat_ona_tili1").strip()
DB_PATH = os.getenv("RESULT_CACHE_DB", "results_cache.db")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "1953416343").split(",") if x.strip().isdigit()}
ADMIN_CONTACT_URL = os.getenv("ADMIN_CONTACT_URL", "https://t.me/Sardor_Sayfullayev777").strip()

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN va OPENAI_API_KEY Render Environment Variables orqali berilishi kerak."
    )

client = OpenAI(api_key=OPENAI_API_KEY)

# --- Deterministic repeat protection + subscription gate ---
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS result_cache (cache_key TEXT PRIMARY KEY, result_json TEXT NOT NULL)")
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, full_name TEXT, phone TEXT, registered_at TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, score REAL, scale75 INTEGER, cache_key TEXT, created_at TEXT)")
    conn.commit()
    return conn

def _cache_key(kind: str, topic: str, content):
    h = hashlib.sha256()
    h.update(kind.encode("utf-8"))
    h.update(b"\0")
    h.update((topic or "").strip().encode("utf-8"))
    h.update(b"\0")
    if isinstance(content, bytes):
        h.update(content)
    else:
        h.update((content or "").strip().encode("utf-8"))
    return h.hexdigest()

def _cache_get(key: str):
    conn = _db()
    try:
        row = conn.execute("SELECT result_json FROM result_cache WHERE cache_key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()

def _cache_put(key: str, data: dict):
    conn = _db()
    try:
        conn.execute("INSERT OR REPLACE INTO result_cache(cache_key,result_json) VALUES(?,?)", (key, json.dumps(data, ensure_ascii=False)))
        conn.commit()
    finally:
        conn.close()


def get_user(user_id: int):
    conn = _db()
    try:
        row = conn.execute("SELECT user_id, username, first_name, last_name, full_name, phone, registered_at FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row: return None
        return dict(zip(["user_id","username","first_name","last_name","full_name","phone","registered_at"], row))
    finally:
        conn.close()

def save_user(tg_user, full_name: str, phone: str):
    conn = _db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO users(user_id,username,first_name,last_name,full_name,phone,registered_at) VALUES(?,?,?,?,?,?,?)",
            (tg_user.id, tg_user.username or "", tg_user.first_name or "", tg_user.last_name or "", full_name.strip(), phone.strip(), datetime.now().isoformat(timespec="seconds"))
        )
        conn.commit()
    finally:
        conn.close()

def all_users():
    conn = _db()
    try:
        return conn.execute("SELECT user_id, username, first_name, last_name, full_name, phone, registered_at FROM users ORDER BY registered_at").fetchall()
    finally:
        conn.close()

def add_stat(user_id: int, score: float, scale75, cache_key: str):
    conn = _db()
    try:
        conn.execute("INSERT INTO stats(user_id,score,scale75,cache_key,created_at) VALUES(?,?,?,?,?)", (user_id, float(score), scale75, cache_key, datetime.now().isoformat(timespec="seconds")))
        conn.commit()
    finally:
        conn.close()

def user_stats(user_id: int):
    conn = _db()
    try:
        return conn.execute("SELECT score, scale75, created_at FROM stats WHERE user_id=? ORDER BY id", (user_id,)).fetchall()
    finally:
        conn.close()

def export_users_csv() -> bytes:
    out = StringIO()
    w = csv.writer(out)
    w.writerow(["Telegram ID","Username","Ism","Familiya","To‘liq ism-familiya","Telefon","Ro‘yxatdan o‘tgan vaqt"])
    for row in all_users():
        w.writerow(row)
    return out.getvalue().encode("utf-8-sig")

async def _subscription_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not REQUIRED_CHANNEL_USERNAME:
        return True
    user = update.effective_user
    if not user:
        return False
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL_USERNAME, user.id)
        if member.status in {"member", "administrator", "creator"}:
            return True
        if member.status == "restricted" and getattr(member, "is_member", False):
            return True
    except Exception:
        logging.exception("Kanal obunasini tekshirishda xatolik")
    channel = REQUIRED_CHANNEL_USERNAME if REQUIRED_CHANNEL_USERNAME.startswith("@") else "@" + REQUIRED_CHANNEL_USERNAME
    keyboard = [[InlineKeyboardButton("📢 Kanalga obuna bo‘lish", url=f"https://t.me/{channel.lstrip('@')}")],
                [InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription")]]
    await update.effective_message.reply_text(
        "Botdan foydalanish uchun avval kanalga obuna bo‘ling.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return False

async def _subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await _subscription_ok(update, context):
        await q.edit_message_text("✅ Obuna tasdiqlandi. Endi botdan foydalanishingiz mumkin. /new ni bosing.")

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("✍️ Keyingi esseni tekshirish"), KeyboardButton("📊 Statistikam")],
        [KeyboardButton("👨‍💼 Admin bilan bog‘lanish"), KeyboardButton("⚠️ Bot kamchiliklari haqida xabar berish")],
        [KeyboardButton("📚 Esse qanday yoziladi?")]
    ], resize_keyboard=True)

def admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📢 E’lon yuborish"), KeyboardButton("👥 Foydalanuvchilar fayli")],
        [KeyboardButton("🏠 Oddiy rejim")]
    ], resize_keyboard=True)

async def show_main_menu(update, text="Bosh menyu"):
    await update.effective_message.reply_text(text, reply_markup=main_keyboard())

async def registration_start(update, context):
    context.user_data["reg_stage"] = "name"
    await update.effective_message.reply_text("👤 Ro‘yxatdan o‘tish uchun ism-familiyangizni yozing:", reply_markup=ReplyKeyboardRemove())

async def complete_registration(update, context, phone):
    full_name = context.user_data.get("reg_name", "").strip()
    if not full_name:
        await update.effective_message.reply_text("Avval ism-familiyangizni yozing.")
        return
    save_user(update.effective_user, full_name, phone)
    context.user_data.pop("reg_stage", None)
    context.user_data.pop("reg_name", None)
    await update.effective_message.reply_text("✅ Ro‘yxatdan o‘tish yakunlandi.", reply_markup=main_keyboard())
    if ADMIN_IDS:
        try:
            f = BytesIO(export_users_csv()); f.name = "foydalanuvchilar.csv"
            for aid in ADMIN_IDS:
                await context.bot.send_message(aid, f"🆕 Yangi foydalanuvchi ro‘yxatdan o‘tdi: {full_name}")
                f.seek(0)
                await context.bot.send_document(aid, document=f, caption="📁 Yangilangan foydalanuvchilar ro‘yxati")
        except Exception:
            logging.exception("Admin notification error")

async def ensure_registered(update, context) -> bool:
    if get_user(update.effective_user.id):
        return True
    if context.user_data.get("reg_stage"):
        return False
    await registration_start(update, context)
    return False

async def send_stats(update, context):
    rows = user_stats(update.effective_user.id)
    if not rows:
        await update.effective_message.reply_text("📊 Hali statistika yo‘q. Birinchi essengizni tekshirtiring.", reply_markup=main_keyboard())
        return
    scores=[float(r[0]) for r in rows]
    avg=sum(scores)/len(scores)
    last=scores[-1]
    prev=scores[-2] if len(scores)>1 else last
    trend="📈 O‘sish" if last>prev else ("📉 Pasayish" if last<prev else "➡️ O‘zgarmagan")
    # Store stats in a temporary dict for the card generator.
    data={"stats_scores":scores,"avg":avg,"last":last,"trend":trend,"count":len(scores)}
    await update.effective_message.reply_photo(photo=BytesIO(make_stats_card(data)), caption=f"📊 Umumiy statistika: {len(scores)} ta esse\n{trend}")

def make_stats_card(data):
    W,H=1200,900
    img=Image.new("RGB",(W,H),(250,252,251)); d=ImageDraw.Draw(img)
    green=(18,126,98); dark=(28,77,70); teal=(25,111,99); light=(236,247,245); gray=(70,112,108); white=(255,255,255)
    d.rounded_rectangle((35,30,W-35,H-35),radius=30,fill=white)
    d.text((70,55),"Esse natijalari statistikasi",font=_font(46,True),fill=dark)
    scores=data["stats_scores"]; n=len(scores)
    avg=data["avg"]; last=data["last"]
    d.text((75,125),f"Tekshirilgan esse: {n} ta",font=_font(28,True),fill=teal)
    d.text((75,170),f"O‘rtacha: {avg:.1f}/24    Oxirgi: {last:g}/24",font=_font(27),fill=gray)
    d.text((920,145),data["trend"],font=_font(28,True),fill=green if "O‘sish" in data["trend"] else (160,80,60) if "Pasayish" in data["trend"] else gray)
    x0,y0,x1,y1=90,260,1110,720
    d.rounded_rectangle((x0,y0,x1,y1),radius=20,fill=light)
    # axes
    d.line((x0+60,y1-60,x1-40,y1-60),fill=teal,width=3); d.line((x0+60,y0+40,x0+60,y1-60),fill=teal,width=3)
    for v in (0,6,12,18,24):
        y=(y1-60)-v*((y1-y0-100)/24)
        d.line((x0+55,y,x1-40,y),fill=(205,225,221),width=1); d.text((x0+12,y-12),str(v),font=_font(18),fill=gray)
    if n==1: xs=[x0+130]
    else: xs=[x0+80+i*(x1-x0-150)/(n-1) for i in range(n)]
    pts=[]
    for x,scr in zip(xs,scores):
        y=(y1-60)-scr*((y1-y0-100)/24); pts.append((int(x),int(y)))
    if len(pts)>1: d.line(pts,fill=green,width=7,joint="curve")
    for i,(x,y) in enumerate(pts,1):
        d.ellipse((x-9,y-9,x+9,y+9),fill=green); d.text((x-14,y+15),str(i),font=_font(17,True),fill=gray)
    d.text((70,770),"BBA uslubidagi rasmiy kuzatuv grafigi",font=_font(23,True),fill=dark)
    out=BytesIO(); img.save(out,format="JPEG",quality=94); return out.getvalue()

async def admin_menu(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.effective_message.reply_text("Bu bo‘lim faqat admin uchun.")
        return
    context.user_data["admin_mode"]=True
    await update.effective_message.reply_text("🔐 Admin panel",reply_markup=admin_keyboard())

async def send_admin_broadcast(update, context, content_message=None):
    if update.effective_user.id not in ADMIN_IDS: return
    users=all_users(); sent=0; failed=0
    for row in users:
        uid=row[0]
        try:
            if content_message and content_message.photo:
                await context.bot.send_photo(uid, content_message.photo[-1].file_id, caption=content_message.caption or "")
            else:
                txt=(content_message.text if content_message else update.effective_message.text) or ""
                await context.bot.send_message(uid, txt)
            sent+=1
        except Exception:
            failed+=1
    await update.effective_message.reply_text(f"📢 E’lon yakunlandi.\nYuborildi: {sent}\nYetkazilmadi: {failed}",reply_markup=admin_keyboard())

RUBRIC = r"""
Siz O‘zbekiston milliy test tizimi doirasidagi ONA TILI VA ADABIYOT fanidan yozma ish (esse) eksperti sifatida ishlaysiz.
ASOSIY MANBA — “Esse baholash nizomi - Basirat.pdf”. Baholashda faqat nizomdagi 12 mezon va undagi tavsiflardan foydalaning.

QAT’IY QOIDALAR:
- Jami 24 ball: 12 mezon × 2 ball.
- Har bir mezon faqat 0 / 0.5 / 1 / 1.5 / 2 ball oladi.
- 2 ballni faqat nizomdagi 2 ballik tavsif to‘liq bajarilganda qo‘ying.
- 1.5 ballni faqat nizomdagi 1.5 ballik tavsifga mos holatda qo‘ying.
- 1 ball va 0.5 ball ham nizomdagi tegishli tavsifga mos bo‘lishi shart.
- “Yaxshi yozilgan”, “mazmunli”, “deyarli to‘g‘ri” kabi umumiy taassurotning o‘zi yuqori ball uchun asos emas.
- Har bir yuqori ball uchun esse ichidan aniq dalil ko‘rsating.
- Xatolik bor-yo‘qligini taxmin qilmang: ko‘rinadigan/o‘qiladigan dalil bo‘lmasa, xato sanamang.
- Aksincha, matnda aniq ko‘rinib turgan xatoni “mayda xato” deb yashirmang.
- Umumiy ballni o‘zingizcha yumshatmang yoki oshirmang. Yakuniy ball 12 mezon ballarining yig‘indisi bo‘ladi.

MAXSUS HOLATLAR — odatdagi 12 mezon o‘rniga:
1) esse yozilmagan -> 0 ball;
2) esse yozilgan, lekin mavzuga mos emas -> jami 2 ball;
3) esse 100 ta so‘zdan kam -> jami 2 ball;
4) esse boshqa manbadan ko‘chirilganligi aniq -> jami 2 ball;
5) faqat kirish qismi yozilgan, boshqa qismlar yo‘q -> 0 ball;
6) matn to‘liq kirill alifbosida -> 0 ball.
Ko‘chirilganlikni dalilsiz taxmin qilmang.

NIZOMDAGI 12 MEZON VA ANIQ TAVSIFLAR:
1. Publitsistik uslub:
  2 — esse to‘liq publitsistik uslubda;
  1.5 — ayrim o‘rinlarda publitsistik uslubdan chekinilgan;
  1 — esse qisman publitsistik uslubda;
  0.5 — esse to‘liq badiiy uslubda;
  0 — esse to‘liq so‘zlashuv uslubida.

2. Vaziyat yuzasidan har ikkala qarash hamda shaxsiy qarashning yoritilishi:
  2 — har ikkala qarash va shaxsiy qarash to‘la yoritilgan;
  1.5 — har ikkala qarash yoritilgan, shaxsiy fikr yoritilmagan;
  1 — qarashlarning bittasi to‘la yoritilgan;
  0.5 — qarashlarning faqat bittasi qisman yoritilgan;
  0 — qarashlar yoritilmagan.

3. Har ikkala qarashning dalillar bilan asoslanishi:
  2 — har ikkala qarash dalillar bilan asoslangan;
  1.5 — faqat bitta qarash dalillangan;
  1 — har ikkala qarash uchun ayrim dalillar vaziyatga mos emas;
  0.5 — har ikkala qarash uchun keltirilgan dalillar vaziyatga mos emas;
  0 — har ikkala qarash dalillanmagan.

4. Kirish, asosiy qism va xulosa:
  2 — uchalasi to‘la yoritilgan;
  1.5 — qismlardan faqat ikkitasi to‘la yoritilgan;
  1 — qismlardan ikkitasi yuzaki yoritilgan;
  0.5 — faqat bittasi to‘la yoritilgan;
  0 — faqat bittasi yuzaki yoritilgan.

5. Mantiqiy-qurilish va xatboshilar:
  2 — xatolik yo‘q, xatboshilar to‘g‘ri ajratilgan;
  1.5 — 1–2 o‘rinda xatolik;
  1 — 3–4 o‘rinda xatolik;
  0.5 — 5–6 o‘rinda xatolik;
  0 — 7+ o‘rinda xatolik yoki xatboshilar umuman ajratilmagan.

6. Mantiqiy-mazmuniy izchillik va fikrlar takrori:
  2 — izchillikka to‘liq rioya qilingan, fikrlar takrori yo‘q;
  1.5 — takror 1–2 o‘rinda, izchillik buzilmagan;
  1 — takror 3–4 o‘rinda va izchillik buzilgan;
  0.5 — takror 5–6 o‘rinda va izchillik buzilgan;
  0 — takror 7+ o‘rinda va izchillik buzilgan.

7. Imlo:
  2 — xato 0; 1.5 — 1–2; 1 — 3–4; 0.5 — 5–6; 0 — 7+.
8. Punktuatsiya:
  2 — xato 0; 1.5 — 1–2; 1 — 3–4; 0.5 — 5–6; 0 — 7+.
9. Qo‘shimcha qo‘llash:
  2 — xato 0; 1.5 — 1–2; 1 — 3–4; 0.5 — 5–6; 0 — 7+.
10. So‘z qo‘llash bilan bog‘liq uslubiy xatolar:
  2 — xato 0; 1.5 — 1–2; 1 — 3–4; 0.5 — 5–6; 0 — 7+.
  Bunga so‘zni noto‘g‘ri qo‘llash, noo‘rin takror, ortiqcha qo‘llash, tushirib qoldirish,
  bog‘lovchi vositalar va kiritmalar bilan bog‘liq xatolar kiradi.

11. Leksik xilma-xillik:
  2 — tasviriy ifodalar, vaziyatga mos maxsus leksik birliklar va barqaror birliklardan unumli foydalanilgan;
  1.5 — shu birliklardan ayrim o‘rinlarda foydalanilgan;
  1 — ayrim o‘rinlarda noo‘rin foydalanilgan;
  0.5 — leksik xilma-xillik kuzatilmagan va birliklardan noo‘rin foydalanilgan;
  0 — leksik xilma-xillik kuzatilmagan va bunday birliklardan foydalanilmagan.

12. Sheva, vulgarizm, varvarizm, parazit so‘zlarning noo‘rin qo‘llanishi:
  2 — xato 0; 1.5 — 1–2; 1 — 3–4; 0.5 — 5–6; 0 — 7+ va uslubiy g‘alizlik yuzaga kelgan.

ESSE TALABLARI:
- publitsistik uslub;
- mantiqiy izchillik va adabiy til me’yorlari;
- vaziyat matnini aynan ko‘chirmaslik;
- kirish, asosiy qism, xulosa;
- reja va epigraf bo‘lmaydi;
- kirish 2–3 jumla;
- asosiy qism kamida 3 xatboshidan iborat bo‘lib, qarashlar va shaxsiy fikr dalillar bilan yoritiladi;
- xulosa 2–3 jumla.

100 so‘zni bo‘shliq bilan ajratilgan tokenlar soni sifatida hisoblang.

QAT’IY NAZORAT:
- 12 ta mezonning barchasi alohida qaytarilsin; mezon nomlari pastdagi nomlar bilan bir xil bo‘lsin.
- 2 ball berilgan 1,2,3,4,11-mezonlarda full_requirement=true, reason va kamida bitta aniq evidence/example bo‘lsin.
- 7, 8, 9, 10, 12-mezonlar uchun error_count maydonini aniq sanab qaytaring.
- 5-mezon uchun structural_error_count; 6-mezon uchun repetition_count va consistency_broken qaytaring.
- Bu sonlarni taxminiy emas, matnda ko‘rinadigan xatolar asosida sanang.

JAVOB FORMATI:
{
  "status": "normal" yoki "special_case",
  "special_reason": "...",
  "word_count": 0,
  "transcription": "...",
  "scores": [
    {"criterion": 1, "name": "...", "score": 0, "reason": "...", "examples": ["..."], "error_count": 0, "structural_error_count": 0, "repetition_count": 0, "consistency_broken": false, "full_requirement": false}
  ],
  "total": 0,
  "summary": "...",
  "improvements": ["...", "...", "..."]
}
Faqat valid JSON qaytaring. Markdown ishlatmang.
"""

def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text, flags=re.UNICODE))

def has_cyrillic(text: str) -> bool:
    letters = re.findall(r"[A-Za-zА-Яа-яЁёҚқҒғҲҳЎў]", text)
    if not letters:
        return False
    cyr = re.findall(r"[А-Яа-яЁёҚқҒғҲҳЎў]", text)
    return len(cyr) / len(letters) > 0.85

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if not await _subscription_ok(update, context):
        return
    if not get_user(update.effective_user.id):
        await registration_start(update, context)
        return
    await show_main_menu(update, "Assalomu alaykum! 👋\n\nKerakli bo‘limni tanlang:")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _subscription_ok(update, context): return
    await update.effective_message.reply_text("Foydalanish: avval mavzu/vaziyatni yuboring, keyin esseni matn yoki rasmda yuboring. Baholash 12 mezon va 24 ballik nizom asosida.", reply_markup=main_keyboard())

async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _subscription_ok(update, context): return
    if not await ensure_registered(update, context): return
    context.user_data.pop("admin_mode", None)
    context.user_data["stage"]="topic"
    await update.effective_message.reply_text("✍️ Yangi tekshiruv. Mavzu/vaziyatni yuboring.", reply_markup=main_keyboard())

async def show_guide(update, context):
    await update.effective_message.reply_text("📚 Esse qanday yoziladi?\n\n1. Kirish — 2–3 jumla.\n2. Asosiy qism — kamida 3 xatboshi; har ikki qarash va shaxsiy fikr dalillar bilan yoritiladi.\n3. Xulosa — 2–3 jumla.\n\nPublitsistik uslub, mantiqiy izchillik va adabiy til me’yorlariga rioya qiling. Reja va epigraf yozilmaydi.", reply_markup=main_keyboard())

async def handle_contact(update, context):
    if not await _subscription_ok(update, context): return
    if context.user_data.get("reg_stage")!="phone": return
    phone=update.effective_message.contact.phone_number
    await complete_registration(update, context, phone)

async def handle_registration_text(update, context):
    stage=context.user_data.get("reg_stage")
    if stage=="name":
        name=(update.effective_message.text or "").strip()
        if len(name.split())<2:
            await update.effective_message.reply_text("Iltimos, ism va familiyangizni birga yozing.")
            return
        context.user_data["reg_name"]=name; context.user_data["reg_stage"]="phone"
        kb=ReplyKeyboardMarkup([[KeyboardButton("📱 Telefon raqamimni yuborish",request_contact=True)]],resize_keyboard=True,one_time_keyboard=True)
        await update.effective_message.reply_text("📱 Telefon raqamingizni yuboring yoki raqamni yozing:",reply_markup=kb)
    elif stage=="phone":
        await complete_registration(update, context, (update.effective_message.text or "").strip())

async def handle_menu_text(update, context):
    text=(update.effective_message.text or "").strip()
    if text=="✍️ Keyingi esseni tekshirish":
        if await ensure_registered(update,context):
            context.user_data["stage"]="topic"; await update.effective_message.reply_text("Mavzu/vaziyatni yuboring:",reply_markup=main_keyboard())
        return True
    if text=="📊 Statistikam":
        if await ensure_registered(update,context): await send_stats(update,context)
        return True
    if text=="📚 Esse qanday yoziladi?":
        if await ensure_registered(update,context): await show_guide(update,context)
        return True
    if text=="👨‍💼 Admin bilan bog‘lanish":
        if ADMIN_CONTACT_URL: await update.effective_message.reply_text("👨‍💼 Admin bilan bog‘lanish:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Admin bilan bog‘lanish",url=ADMIN_CONTACT_URL)]]))
        else: await update.effective_message.reply_text("Admin kontakti hali sozlanmagan.",reply_markup=main_keyboard())
        return True
    if text=="⚠️ Bot kamchiliklari haqida xabar berish":
        if await ensure_registered(update,context):
            context.user_data["feedback_mode"]=True; await update.effective_message.reply_text("Muammo yoki taklifingizni yozing:",reply_markup=main_keyboard())
        return True
    if text=="🏠 Oddiy rejim" and update.effective_user.id in ADMIN_IDS:
        context.user_data["admin_mode"]=False; await show_main_menu(update); return True
    if text=="📢 E’lon yuborish" and update.effective_user.id in ADMIN_IDS:
        context.user_data["admin_mode"]=True; context.user_data["admin_action"]="broadcast"; await update.effective_message.reply_text("📢 E’lon matnini yuboring. Rasm yuborsangiz, caption ham e’lon sifatida jo‘natiladi.",reply_markup=admin_keyboard()); return True
    if text=="👥 Foydalanuvchilar fayli" and update.effective_user.id in ADMIN_IDS:
        f=BytesIO(export_users_csv()); f.name="foydalanuvchilar.csv"; await update.effective_message.reply_document(f,caption="📁 Foydalanuvchilar ro‘yxati",reply_markup=admin_keyboard()); return True
    return False

async def handle_feedback(update, context):
    if update.effective_user.id in ADMIN_IDS and context.user_data.get("admin_action")=="broadcast":
        return False
    if not context.user_data.get("feedback_mode"): return False
    text=(update.effective_message.text or update.effective_message.caption or "").strip()
    context.user_data["feedback_mode"]=False
    if ADMIN_IDS:
        for aid in ADMIN_IDS:
            try: await context.bot.send_message(aid, f"⚠️ BOT KAMCHILIGI / TAKLIF\nFoydalanuvchi: {update.effective_user.full_name} (@{update.effective_user.username or '-'})\n\n{text}")
            except Exception: logging.exception("Feedback send error")
    await update.effective_message.reply_text("✅ Xabaringiz adminga yuborildi. Rahmat!",reply_markup=main_keyboard())
    return True


def _apply_special_case_total(data: dict, essay_text: str = ""):
    """Apply the rubric's special-case final score after normal criterion scoring."""
    text = essay_text or str(data.get("transcription", data.get("essay_text", "")))
    wc = count_words(text) if text else int(data.get("word_count", 0) or 0)

    # Deterministic special cases explicitly stated by the rubric.
    if not text.strip():
        data["status"] = "special_case"
        data["special_reason"] = "Esse yozilmagan."
        data["total"] = 0
        data["scale_75"] = None
        return data
    if wc < 100:
        data["status"] = "special_case"
        data["special_reason"] = "Esse hajmi 100 ta so'zdan kam."
        data["total"] = 2
        data["scale_75"] = 31
        return data
    if has_cyrillic(text):
        data["status"] = "special_case"
        data["special_reason"] = "Esse matni to'liq yoki deyarli to'liq kirill alifbosida."
        data["total"] = 0
        data["scale_75"] = None
        return data

    # The model sometimes puts the special-case decision in summary/reason instead
    # of setting status=special_case. Detect the rubric phrases deterministically.
    reason = str(data.get("special_reason", "")).lower()
    summary = str(data.get("summary", "")).lower()
    combined = reason + " " + summary
    if ("mavzuga mos emas" in combined or "mavzuga mos kelmay" in combined
            or "vaziyatga mos emas" in combined
            or "vaziyatga mos kelmay" in combined
            or "vaziyatga mutlaqo mos emas" in combined
            or "mavzuga umuman mos emas" in combined):
        data["status"] = "special_case"
        data["special_reason"] = "Esse mavzuga/vaziyatga mos emas."
        data["total"] = 2
    elif ("ko'chir" in combined or "ko‘chir" in combined or "kochiril" in combined
          or "nusxa ko‘chiril" in combined):
        data["status"] = "special_case"
        data["special_reason"] = "Esse ko‘chirilgan."
        data["total"] = 2
    elif "faqat kirish" in combined or ("kirish qismi" in combined and "boshqa" in combined and "qism" in combined):
        data["status"] = "special_case"
        data["special_reason"] = "Faqat kirish qismi mavjud."
        data["total"] = 0
    elif "yozilmagan" in combined or "esse yo'q" in combined or "esse yo‘q" in combined:
        data["status"] = "special_case"
        data["special_reason"] = "Esse yozilmagan."
        data["total"] = 0
    elif data.get("status") == "special_case":
        if "ko'chir" in reason or "ko‘chir" in reason or "kochiril" in reason:
            data["total"] = 2
        elif "faqat kirish" in reason or ("kirish qismi" in reason and "boshqa" in reason):
            data["total"] = 0
        elif "yozilmagan" in reason or "esse yo'q" in reason or "esse yo‘q" in reason:
            data["total"] = 0
    # Always derive the 75-point value from the final, authoritative total.
    data["scale_75"] = to_75_scale(data.get("total", 0))
    return data

def to_75_scale(total: float):
    """Convert the 24-point result to the official 75-point scale.
    For 2..24 points, use the supplied table: 24->75, 23.5->74, ... 2->31.
    Scores below 2 are kept outside this scale because the supplied table starts at 2.
    """
    try:
        t = float(total)
    except (TypeError, ValueError):
        return None
    if t < 2 or t > 24:
        return None
    return int(round(2 * t + 27))

def _score_by_count(n: int) -> float:
    if n <= 0: return 2.0
    if n <= 2: return 1.5
    if n <= 4: return 1.0
    if n <= 6: return 0.5
    return 0.0

def _apply_deterministic_guards(data: dict):
    by_n = {int(x.get("criterion")): x for x in data.get("scores", []) if str(x.get("criterion", "")).isdigit()}
    for n in range(1, 13):
        by_n.setdefault(n, {"criterion": n, "name": CARD_NAMES.get(n, str(n)), "score": 0, "reason": "Nizom bo‘yicha yetarli dalil qaytarilmagan.", "examples": []})
    # Exact count-based criteria are calculated from the model's explicit error counts.
    for n in (7, 8, 9, 10, 12):
        item = by_n[n]
        try:
            raw = item.get("error_count", None)
            if raw is None: raise ValueError("missing error_count")
            item["score"] = _score_by_count(int(raw))
        except Exception:
            item["score"] = 0.0
    try:
        if by_n[5].get("structural_error_count", None) is None: raise ValueError("missing structural_error_count")
        structural = int(by_n[5].get("structural_error_count"))
        by_n[5]["score"] = _score_by_count(structural)
    except Exception: by_n[5]["score"] = 0.0
    try:
        if by_n[6].get("repetition_count", None) is None or by_n[6].get("consistency_broken", None) is None: raise ValueError("missing repetition fields")
        rep = int(by_n[6].get("repetition_count"))
        broken = bool(by_n[6].get("consistency_broken", False))
        if rep == 0: by_n[6]["score"] = 2.0
        elif rep <= 2 and not broken: by_n[6]["score"] = 1.5
        elif 3 <= rep <= 4 and broken: by_n[6]["score"] = 1.0
        elif 5 <= rep <= 6 and broken: by_n[6]["score"] = 0.5
        elif rep >= 7 and broken: by_n[6]["score"] = 0.0
        else: by_n[6]["score"] = min(float(by_n[6].get("score", 0)), 1.0)
    except Exception: by_n[6]["score"] = 0.0
    # A 2/2 subjective score must carry evidence.
    for n in (1, 2, 3, 4, 11):
        item = by_n[n]
        try: sc = float(item.get("score", 0))
        except Exception: sc = 0.0
        examples = item.get("examples") or []
        if sc >= 2 and (not examples or item.get("full_requirement") is not True):
            item["score"] = 1.5
            item["reason"] = str(item.get("reason", "")) + " 2 ball uchun nizomdagi to‘liq talab bajarilgani va aniq dalil yetarli tasdiqlanmagan."
    data["scores"] = [by_n[n] for n in range(1,13)]
    data["total"] = min(24.0, max(0.0, sum(float(x.get("score",0)) for x in data["scores"])))
    data["scale_75"] = to_75_scale(data["total"])
    return data


async def evaluate(topic: str, essay: str) -> dict:
    key = _cache_key("text", topic, essay)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    word_count = count_words(essay)

    user_prompt = f"""
MAVZU/Vaziyat:
{topic}

ESSE:
{essay}

Texnik ma'lumot:
- Dastlabki so'zlar soni: {word_count}
- Kirill belgilariga oid dastlabki tekshiruv: {has_cyrillic(essay)}

Yuqoridagi nizom asosida juda ehtiyotkor ekspert bahosini bering.
"""

    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = response.output_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)

    data["word_count"] = word_count

    # Normalize scores and apply deterministic rubric guards.
    allowed_scores = {0, 0.5, 1, 1.5, 2}
    for item in data.get("scores", []):
        try:
            sc = float(item.get("score", 0))
            item["score"] = sc if sc in allowed_scores else min(allowed_scores, key=lambda x: abs(x-sc))
        except Exception:
            item["score"] = 0.0
    data = _apply_deterministic_guards(data)

    # Special cases have priority over the normal 12-criterion total.
    data["status"] = data.get("status", "normal")
    data = _apply_special_case_total(data, essay)
    _cache_put(key, data)
    return data

async def evaluate_image(topic: str, image_bytes) -> dict:
    """Read a handwritten essay image and evaluate the transcribed text by the same rubric."""
    if not isinstance(image_bytes, (list, tuple)):
        image_bytes = [image_bytes]
    prompt = f"""
MAVZU/Vaziyat:
{topic}

Vazifa:
1) Rasmda qo'lda yozilgan esse matnini imkon qadar aynan o'qing va ichingizda to'liq transkripsiya qiling.
2) Noaniq o'qilgan joylarni taxmin qilib yashirmang; baholashda o'qilishi noaniq ekanini hisobga oling.
3) Avval to'liq transkripsiyani JSON dagi transcription maydoniga yozing.
4) Faqat rasmda aniq ko'rinadigan matn asosida, yuqoridagi nizomning aniq ball tavsiflari bo'yicha baholang.
5) Yuqori ballni faqat nizom tavsifi to'liq bajarilganda bering.
6) JSON javobidagi summary yoki improvements ichida kerak bo'lsa "Rasm sifati/noaniq yozuv" haqida ogohlantiring.

Faqat valid JSON qaytaring.
"""
    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": [
                {"type": "input_text", "text": prompt},
                *[{"type": "input_image", "image_url": f"data:image/jpeg;base64,{base64.b64encode(b).decode('utf-8')}"} for b in image_bytes],
            ]},
        ],
    )
    text = response.output_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    return data


MEDIA_GROUPS = {}
MEDIA_GROUP_TASKS = {}

async def _process_photo_group(key_group, update, context, file_ids):
    try:
        topic=context.user_data.get("topic","")
        await update.effective_message.reply_text("⏳ Rasm o‘qilmoqda va esse tekshirilmoqda. Bir oz kuting...")
        images=[]; seen=set()
        for fid in file_ids:
            if fid in seen: continue
            seen.add(fid); tg=await context.bot.get_file(fid); buf=BytesIO(); await tg.download_to_memory(buf); images.append(buf.getvalue())
        h=hashlib.sha256(); h.update(b"image-group\0"); h.update(topic.strip().encode())
        for b in images: h.update(hashlib.sha256(b).digest())
        cache_key=h.hexdigest(); result=_cache_get(cache_key); is_new=result is None
        if result is None: result=await evaluate_image(topic,images)
        essay_text=str(result.get("transcription",result.get("essay_text","")));
        if essay_text: result["word_count"]=count_words(essay_text)
        result=_apply_deterministic_guards(result); result=_apply_special_case_total(result,essay_text); _cache_put(cache_key,result)
        if is_new: add_stat(update.effective_user.id,result.get("total",0),result.get("scale_75"),cache_key)
        await send_result(update,result)
    except Exception as e:
        logging.exception("Image group error: %s",e); await update.effective_message.reply_text("Rasmni tekshirishda texnik xatolik yuz berdi. Aniqroq rasm yuboring.")
    finally:
        MEDIA_GROUPS.pop(key_group,None); MEDIA_GROUP_TASKS.pop(key_group,None)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _subscription_ok(update, context): return
    if update.effective_user.id in ADMIN_IDS and context.user_data.get("admin_action")=="broadcast":
        await send_admin_broadcast(update,context,update.effective_message); context.user_data.pop("admin_action",None); return
    if context.user_data.get("reg_stage"): return
    if context.user_data.get("feedback_mode"):
        context.user_data["feedback_mode"]=False
        if ADMIN_IDS:
            for aid in ADMIN_IDS:
                try: await context.bot.forward_message(aid,update.effective_chat.id,update.effective_message.message_id)
                except Exception: logging.exception("Feedback photo error")
        await update.effective_message.reply_text("✅ Xabaringiz adminga yuborildi.",reply_markup=main_keyboard()); return
    if not get_user(update.effective_user.id): await registration_start(update,context); return
    if context.user_data.get("stage")!="essay": await update.effective_message.reply_text("Avval mavzu/vaziyatni yuboring.",reply_markup=main_keyboard()); return
    media_id=update.effective_message.media_group_id
    if media_id:
        key=(update.effective_chat.id,media_id); group=MEDIA_GROUPS.setdefault(key,{"update":update,"files":[]}); group["files"].append(update.effective_message.photo[-1].file_id)
        if key not in MEDIA_GROUP_TASKS:
            async def delayed():
                await asyncio.sleep(2); item=MEDIA_GROUPS.get(key)
                if item: await _process_photo_group(key,item["update"],context,item["files"])
            MEDIA_GROUP_TASKS[key]=context.application.create_task(delayed())
        return
    await _process_photo_group((update.effective_chat.id,update.effective_message.message_id),update,context,[update.effective_message.photo[-1].file_id])



def format_result(data: dict) -> str:
    lines = ["📊 ESSE NATIJASI", f"So'zlar soni: {data.get('word_count', 0)}"]
    if data.get("status") == "special_case":
        lines.append(f"⚠️ Maxsus holat: {data.get('special_reason', '')}")
        lines.append(f"Yakuniy ball: {data.get('total', 0)}/24")
        if data.get("scale_75") is not None:
            lines.append(f"75 ball shkalasi: {data.get('scale_75')}/75")
    else:
        lines.append(f"JAMI: {data.get('total', 0)}/24")
    lines.append("")
    for item in data.get("scores", []):
        lines.append(f"{item.get('criterion', '?')}. {item.get('name', '')} — {item.get('score', 0)}/2")
        lines.append(f"   {item.get('reason', '')}")
        for ex in (item.get("examples") or [])[:2]:
            lines.append(f"   • {ex}")
        lines.append("")
    if data.get("summary"):
        lines += ["📝 Umumiy xulosa:", str(data["summary"]), ""]
    improvements = data.get("improvements") or []
    if improvements:
        lines.append("💡 Yaxshilash uchun:")
        lines.extend("• " + str(x) for x in improvements[:5])
    return "\n".join(lines)


def _font(size, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()


def _wrap(draw, text, font, width):
    out, cur = [], ""
    for w in str(text).split():
        t = w if not cur else cur + " " + w
        if draw.textbbox((0,0), t, font=font)[2] <= width:
            cur = t
        else:
            if cur: out.append(cur)
            cur = w
    if cur: out.append(cur)
    return out or [""]


CARD_NAMES = {
    1: "Publitsistik uslub",
    2: "Vaziyat yuzasidan har ikkala qarash va shaxsiy qarashning yoritilishi",
    3: "Har ikkala qarashning dalillar bilan asoslanishi",
    4: "Kirish, asosiy qism, xulosa",
    5: "Mantiqiy-qurilish va xatboshilar",
    6: "Mantiqiy-mazmuniy izchillik va fikrlar takrori",
    7: "Imlo",
    8: "Punktuatsiya",
    9: "Qo‘shimcha qo‘llash",
    10: "So‘z qo‘llash bilan bog‘liq uslubiy xatolar",
    11: "Leksik xilma-xillik, tasviriy, maxsus va barqaror birliklardan foydalanish",
    12: "Sheva, vulgarizm, varvarizm va parazit so‘zlarning noo‘rin qo‘llanishi",
}


def _font(size, bold=False):
    p = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()


def _wrap(draw, text, font, width, max_lines=None):
    words = str(text or "").split()
    out, cur = [], ""
    for w in words:
        t = w if not cur else cur + " " + w
        if draw.textbbox((0, 0), t, font=font)[2] <= width:
            cur = t
        else:
            if cur:
                out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    if not out:
        out = [""]
    if max_lines and len(out) > max_lines:
        out = out[:max_lines]
        if out[-1] and not out[-1].endswith("…"):
            out[-1] = out[-1][:-1] + "…"
    return out


def _draw_check(d, cx, cy, r, green):
    d.ellipse((cx-r, cy-r, cx+r, cy+r), fill=green)
    d.line((cx-r*0.45, cy, cx-r*0.08, cy+r*0.35, cx+r*0.52, cy-r*0.42), fill=(255,255,255), width=max(4, int(r*0.18)), joint="curve")


def _draw_score(d, x, y, score, green, font):
    text = f"{score}/2"
    bb = d.textbbox((0, 0), text, font=font)
    d.text((x-(bb[2]-bb[0]), y), text, font=font, fill=green)


def make_result_card(data: dict) -> bytes:
    # Layout intentionally follows the user's reference image:
    # emblem + header, large score, two-column 12-criterion grid,
    # conclusion, improvement tips, and BBA footer.
    W, H = 1419, 1536
    bg = (250, 252, 251)
    green = (18, 126, 98)
    dark = (28, 77, 70)
    teal = (25, 111, 99)
    light = (236, 247, 245)
    line = (54, 137, 122)
    gray = (70, 112, 108)
    white = (255, 255, 255)

    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)

    title = _font(53, True)
    subtitle = _font(30, False)
    small_bold = _font(24, True)
    body = _font(23, False)
    body_bold = _font(23, True)
    tiny = _font(19, False)
    score_big = _font(108, True)
    score_small = _font(52, True)

    # Header
    d.rounded_rectangle((35, 30, W-35, 305), radius=28, fill=white)
    emblem_path = os.path.join(os.path.dirname(__file__), "emblem.png")
    if os.path.exists(emblem_path):
        em = Image.open(emblem_path).convert("RGBA")
        em.thumbnail((235, 235), Image.Resampling.LANCZOS)
        img.paste(em, (48, 38), em)
        d = ImageDraw.Draw(img)
    else:
        d.ellipse((65, 60, 270, 265), outline=green, width=9)
        d.text((105, 122), "BBA", font=title, fill=green)

    d.text((330, 45), "Esse baholovchi bot", font=title, fill=dark)
    d.text((332, 118), "Sizning essiyingiz BBA nizomi bo‘yicha", font=subtitle, fill=teal)
    d.text((332, 157), "tekshirildi va quyidagi natija aniqlandi:", font=subtitle, fill=teal)

    # Score panel
    d.rounded_rectangle((385, 238, 1010, 410), radius=28, fill=green)
    total_value = data.get("total", 0)
    try:
        total_num = float(total_value)
        total_text = str(int(total_num)) if total_num.is_integer() else str(total_num)
    except Exception:
        total_text = str(total_value)
    d.text((450, 257), total_text, font=score_big, fill=white)
    d.text((705, 300), "/24", font=score_small, fill=white)
    d.text((565, 363), "YAKUNIY BALL", font=small_bold, fill=white)
    scale75 = data.get("scale_75")
    if scale75 is not None:
        d.text((1040, 275), f"{scale75}", font=score_small, fill=green)
        d.text((1045, 330), "75 BALL SHKALASI", font=_font(22, True), fill=teal)

    # Divider lines
    d.line((50, 410, 370, 410), fill=line, width=3)
    d.line((1025, 410, W-50, 410), fill=line, width=3)

    # Criteria area
    d.rounded_rectangle((35, 430, W-35, 950), radius=22, fill=light)
    left_x = 65
    right_x = 725
    row_y = 458
    row_h = 73
    name_width = 500
    score_x_left = 625
    score_x_right = 1350
    score_font = _font(23, True)

    items_by_n = {int(x.get("criterion")): x for x in data.get("scores", []) if str(x.get("criterion", "")).isdigit()}

    for idx in range(1, 7):
        item = items_by_n.get(idx, {})
        y = row_y + (idx-1)*row_h
        _draw_check(d, left_x+18, y+20, 17, green)
        name = CARD_NAMES[idx]
        lines = _wrap(d, name, body, name_width, 2)
        for j, ln in enumerate(lines):
            d.text((left_x+52, y+2+j*27), ln, font=body, fill=dark)
        _draw_score(d, score_x_left, y+5, item.get("score", 0), green, score_font)

    for idx in range(7, 13):
        item = items_by_n.get(idx, {})
        y = row_y + (idx-7)*row_h
        _draw_check(d, right_x+18, y+20, 17, green)
        name = CARD_NAMES[idx]
        lines = _wrap(d, name, body, 535, 2)
        for j, ln in enumerate(lines):
            d.text((right_x+52, y+2+j*27), ln, font=body, fill=dark)
        _draw_score(d, score_x_right, y+5, item.get("score", 0), green, score_font)

    # Conclusion panel
    d.rounded_rectangle((35, 970, W-35, 1190), radius=22, fill=light)
    d.line((270, 1000, 270, 1160), fill=line, width=3)
    # simple document icon
    d.rounded_rectangle((70, 1010, 225, 1155), radius=18, fill=green)
    d.rectangle((105, 1035, 185, 1120), fill=white)
    d.line((120, 1055, 172, 1055), fill=green, width=7)
    d.line((120, 1078, 172, 1078), fill=green, width=7)
    d.line((120, 1101, 155, 1101), fill=green, width=7)
    d.ellipse((164, 1090, 194, 1120), fill=green)
    d.text((300, 995), "Umumiy xulosa:", font=title, fill=dark)
    summary = data.get("summary") or "Baholash 24 ballik BBA nizomi mezonlari asosida amalga oshirildi."
    for j, ln in enumerate(_wrap(d, summary, body, W-365, 4)):
        d.text((300, 1060+j*31), ln, font=body, fill=gray)

    # Improvements
    d.rounded_rectangle((35, 1210, W-35, 1360), radius=22, fill=light)
    d.text((85, 1230), "Yaxshilash uchun:", font=small_bold, fill=dark)
    improvements = data.get("improvements") or ["Matnni yanada boyroq va rang-barang ifodalash.", "Ayrim joylarda sinonimlardan va badiiy uslublardan foydalanish."]
    yy = 1275
    for item in improvements[:2]:
        lines = _wrap(d, "• " + str(item), body, W-180, 2)
        for ln in lines:
            d.text((100, yy), ln, font=body, fill=gray)
            yy += 30

    # Footer
    d.line((140, 1400, 430, 1400), fill=line, width=2)
    d.line((990, 1400, 1280, 1400), fill=line, width=2)
    d.text((470, 1382), "BILIMNI BAHOLASH AGENTLIGI", font=small_bold, fill=dark)
    d.text((595, 1420), "SIFAT  •  ADOLAT  •  NATIJA", font=tiny, fill=gray)

    out = BytesIO()
    img.save(out, format="JPEG", quality=94, optimize=True)
    return out.getvalue()


async def send_result(update: Update, result: dict):
    try:
        card = make_result_card(result)
        await update.message.reply_photo(
            photo=BytesIO(card),
            caption="📊 BBA nizomi bo‘yicha aniq baho"
        )
    except Exception:
        logging.exception("Result card error")
        text=format_result(result)
        while text:
            chunk=text[:3900]
            if len(text)>3900:
                cut=chunk.rfind("\n")
                if cut>1000: chunk=text[:cut]
            await update.message.reply_text(chunk)
            text=text[len(chunk):].lstrip("\n")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _subscription_ok(update, context): return
    if context.user_data.get("reg_stage"):
        await handle_registration_text(update,context); return
    if await handle_feedback(update,context): return
    if update.effective_user.id in ADMIN_IDS and context.user_data.get("admin_action")=="broadcast":
        await send_admin_broadcast(update,context,update.effective_message); context.user_data.pop("admin_action",None); return
    if await handle_menu_text(update,context): return
    if not get_user(update.effective_user.id):
        await registration_start(update,context); return
    stage=context.user_data.get("stage")
    if stage in (None,"topic"):
        context.user_data["topic"]=update.effective_message.text.strip(); context.user_data["stage"]="essay"
        await update.effective_message.reply_text("Mavzu qabul qilindi ✅\n\nEndi essening o‘zini to‘liq yuboring.",reply_markup=main_keyboard()); return
    topic=context.user_data.get("topic",""); essay=update.effective_message.text.strip()
    await update.effective_message.reply_text("⏳ Esse tekshirilmoqda. Bir oz kuting...")
    try:
        key=_cache_key("text",topic,essay); cached=_cache_get(key); is_new=cached is None
        result=await evaluate(topic,essay)
        if is_new: add_stat(update.effective_user.id,result.get("total",0),result.get("scale_75"),key)
        await send_result(update,result)
    except json.JSONDecodeError: await update.effective_message.reply_text("Natijani qayta ishlashda xatolik yuz berdi. /new orqali qayta urinib ko‘ring.")
    except Exception as e:
        logging.exception("Evaluation error: %s",e); await update.effective_message.reply_text("Texnik xatolik yuz berdi. Render Environment Variables, API kaliti yoki model nomini tekshiring.")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Esse tekshiruvchi bot ishlayapti.")

    def log_message(self, format, *args):
        return

def start_health_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), HealthHandler)
    logging.info("Health server listening on 0.0.0.0:%s", PORT)
    server.serve_forever()

def main():
    threading.Thread(target=start_health_server, daemon=True).start()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("new", new_cmd))
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(CallbackQueryHandler(_subscription_callback, pattern="^check_subscription$"))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Telegram bot ishga tushmoqda...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
