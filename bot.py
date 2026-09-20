import os
import re
import json
import logging
import threading
import base64
import sqlite3
import hashlib
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN va OPENAI_API_KEY Render Environment Variables orqali berilishi kerak."
    )

client = OpenAI(api_key=OPENAI_API_KEY)

# --- Deterministic repeat protection + subscription gate ---
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS result_cache (cache_key TEXT PRIMARY KEY, result_json TEXT NOT NULL)")
    conn.commit()
    return conn

def _cache_key(kind: str, topic: str, content: bytes | str) -> str:
    h = hashlib.sha256()
    h.update(kind.encode("utf-8"))
    h.update(b"\0")
    h.update(topic.strip().encode("utf-8"))
    h.update(b"\0")
    if isinstance(content, bytes):
        h.update(content)
    else:
        h.update(content.strip().encode("utf-8"))
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
    await update.message.reply_text(
        "Assalomu alaykum! Men esse tekshiruvchi botman.\n\n"
        "1) Avval esse mavzusi/vaziyatini yuboring.\n"
        "2) Keyin essening o'zini to'liq yuboring.\n"
        "3) Word, oddiy matn yoki qo'lda yozilgan esse rasmini yuborishingiz mumkin.\n"
        "4) Men 24 ballik nizom bo'yicha tekshiraman.\n\n"
        "Yordam: /help\nQayta boshlash: /new"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Foydalanish:\n"
        "/new — yangi esse tekshirish.\n\n"
        "Bot 12 mezon bo'yicha 0–2 ballik baho beradi va jami 24 ballni hisoblaydi.\n"
        "Word, matn va qo'lda yozilgan rasmni ham qabul qiladi.\n"
        "Muhim: bu AI yordamchi ekspert bahosi; rasmiy sertifikat natijasini almashtirmaydi."
    )

async def new_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _subscription_ok(update, context):
        return
    context.user_data.clear()
    await update.message.reply_text("Yangi tekshiruv boshlandi. Mavzu/vaziyatni yuboring.")

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
    special_total = None
    special_reason = None
    if word_count < 100:
        special_total = 2
        special_reason = "Esse hajmi 100 ta so'zdan kam."
    letters = re.findall(r"[A-Za-zА-Яа-яЁёҚқҒғҲҳЎў]", essay)
    cyrillic_letters = re.findall(r"[А-Яа-яЁёҚқҒғҲҳЎў]", essay)
    if letters and len(cyrillic_letters) / len(letters) > 0.85:
        special_total = 0
        special_reason = "Esse matni to'liq yoki deyarli to'liq kirill alifbosida."
    if special_total is not None:
        data["status"] = "special_case"
        data["special_reason"] = special_reason
        data["total"] = special_total
    else:
        data["status"] = data.get("status", "normal")
    _cache_put(key, data)
    return data

async def evaluate_image(topic: str, image_bytes: bytes) -> dict:
    """Read a handwritten essay image and evaluate the transcribed text by the same rubric."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
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
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"},
            ]},
        ],
    )
    text = response.output_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    return data


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _subscription_ok(update, context):
        return
    if context.user_data.get("stage") != "essay":
        await update.message.reply_text("Avval mavzu/vaziyatni matn ko'rinishida yuboring.")
        return

    topic = context.user_data.get("topic", "")
    await update.message.reply_text("⏳ Rasm o'qilmoqda va esse tekshirilmoqda. Bir oz kuting...")

    try:
        photo = update.message.photo[-1]
        tg_file = await context.bot.get_file(photo.file_id)
        buf = BytesIO()
        await tg_file.download_to_memory(buf)
        image_bytes = buf.getvalue()
        key = _cache_key("image", topic, image_bytes)
        result = _cache_get(key)
        if result is None:
            result = await evaluate_image(topic, image_bytes)

        # Apply the same deterministic rules to image evaluations.
        essay_text = str(result.get("transcription", result.get("essay_text", "")))
        if essay_text:
            result["word_count"] = count_words(essay_text)
        result = _apply_deterministic_guards(result)
        if essay_text:
            wc = result.get("word_count", 0)
            if wc < 100:
                result["status"] = "special_case"
                result["special_reason"] = "Esse hajmi 100 ta so'zdan kam."
                result["total"] = 2
            elif has_cyrillic(essay_text):
                result["status"] = "special_case"
                result["special_reason"] = "Esse matni to'liq yoki deyarli to'liq kirill alifbosida."
                result["total"] = 0
        _cache_put(key, result)
        await send_result(update, result)
    except json.JSONDecodeError:
        await update.message.reply_text("Rasmdagi matnni qayta ishlashda xatolik yuz berdi. Aniqroq rasm yuboring.")
    except Exception as e:
        logging.exception("Image evaluation error: %s", e)
        await update.message.reply_text("Rasmni tekshirishda texnik xatolik yuz berdi. Aniqroq rasm yuboring.")



def format_result(data: dict) -> str:
    lines = ["📊 ESSE NATIJASI", f"So'zlar soni: {data.get('word_count', 0)}"]
    if data.get("status") == "special_case":
        lines.append(f"⚠️ Maxsus holat: {data.get('special_reason', '')}")
        lines.append(f"Yakuniy ball: {data.get('total', 0)}/24")
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
        await update.message.reply_text(format_result(result))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _subscription_ok(update, context):
        return
    text = (update.message.text or "").strip()
    if not text:
        return

    stage = context.user_data.get("stage")

    if stage is None:
        context.user_data["topic"] = text
        context.user_data["stage"] = "essay"
        await update.message.reply_text(
            "Mavzu qabul qilindi ✅\n\nEndi essening o'zini to'liq yuboring."
        )
        return

    topic = context.user_data.get("topic", "")
    essay = text
    await update.message.reply_text("⏳ Esse tekshirilmoqda. Bir oz kuting...")

    try:
        result = await evaluate(topic, essay)
        await send_result(update, result)
    except json.JSONDecodeError:
        await update.message.reply_text(
            "Natijani qayta ishlashda xatolik yuz berdi. Esseni /new orqali qayta yuboring."
        )
    except Exception as e:
        logging.exception("Evaluation error: %s", e)
        await update.message.reply_text(
            "Texnik xatolik yuz berdi. Render Environment Variables, API kaliti yoki model nomini tekshiring."
        )

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
    app.add_handler(CallbackQueryHandler(_subscription_callback, pattern="^check_subscription$"))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Telegram bot ishga tushmoqda...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
