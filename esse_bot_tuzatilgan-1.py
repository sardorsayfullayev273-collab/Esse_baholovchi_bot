import os
import asyncio
import re
import json
import logging
import threading
import base64
import hashlib
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
)
from openai import OpenAI
from openai import APIError, AuthenticationError, RateLimitError, BadRequestError

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
PORT = int(os.getenv("PORT", "10000"))

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN va OPENAI_API_KEY Render Environment Variables orqali berilishi kerak."
    )

client = OpenAI(api_key=OPENAI_API_KEY, timeout=90.0, max_retries=2)


def _cache_key(*parts):
    """Build a stable cache key from any text-like parts."""
    raw = "\n".join("" if x is None else str(x) for x in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

RUBRIC = r"""
Siz O'zbekiston milliy test tizimi doirasidagi ONA TILI VA ADABIYOT fanidan yozma ish (esse)
eksperti sifatida ishlaysiz. Asosiy baholash manbasi: "Esse baholash nizomi - Basirat.pdf".
Ikkinchi manba "Ona tili baholash mezoni.pdf" dagi umumiy 24 ballik tuzilma va talablar bilan
moslashtiruvchi qo'shimcha manba sifatida ishlatiladi.

MUHIM:
- Umumiy ball 24.
- 12 ta mezonning har biri 0 / 0.5 / 1 / 1.5 / 2 ball diapazonida baholanadi.
- Quyidagi maxsus holatlarda odatdagi mezonlarni qo'llamasdan yakuniy ballni belgilang:
  1) esse yozilmagan -> 0 ball;
  2) esse mavzuga mos emas -> 2 ball;
  3) 100 ta so'zdan kam -> 2 ball;
  4) ko'chirilganligi aniq bo'lsa -> 2 ball;
  5) faqat kirish qismi yozilgan, boshqa qismlar yo'q -> 0 ball;
  6) matn to'liq kirill alifbosida -> 0 ball.
  Agar ko'chirilganlikni ishonchli tekshirish imkoni bo'lmasa, "aniq ko'chirilgan" deb hukm chiqarmang.
- 100 so'zni bo'shliq bilan ajratilgan tokenlar soni sifatida hisoblang va hisobni alohida ko'rsating.
- Foydalanuvchi bergan mavzu/vaziyatni aynan ko'chirishni alohida salbiy belgi sifatida ko'ring, lekin
  "internetdan ko'chirilgan" degan xulosani dalilsiz chiqarmang.
- Publitsistik uslub, mavzuning ikki qarashi va shaxsiy qarash, dalillar, kirish-asosiy qism-xulosa,
  mantiqiy qurilish va izchillik, imlo, punktuatsiya, qo'shimcha qo'llash, so'z qo'llash uslubiyati,
  leksik xilma-xillik va noo'rin sheva/vulgarizm/varvarizm/parazit so'zlar mezonlarini hisobga oling.

12 MEZON:
1. Publitsistik uslub.
2. Vaziyat yuzasidan har ikkala qarash + shaxsiy qarashning yoritilishi.
3. Har ikkala qarashning dalillar bilan asoslanishi.
4. Kirish, asosiy qism, xulosa.
5. Mantiqiy-qurilish va xatboshilar.
6. Mantiqiy-mazmuniy izchillik va fikrlar takrori.
7. Imlo.
8. Punktuatsiya.
9. Qo'shimcha qo'llash.
10. So'z qo'llash bilan bog'liq uslubiy xatolar.
11. Leksik xilma-xillik, tasviriy/maxsus/barqaror birliklardan foydalanish.
12. Sheva, vulgarizm, varvarizm, parazit so'zlarning noo'rin qo'llanishi.

XATOLAR SONI bo'yicha aniq diapazonlar:
- 7, 8, 9, 10, 12: 0; 1-2; 3-4; 5-6; 7+ xatolar mos ravishda
  2; 1.5; 1; 0.5; 0 ballga olib keladi.
- 5: mantiqiy-qurilish/xatboshi xatolari 0; 1-2; 3-4; 5-6; 7+ o'rin.
- 6: fikr takrori 0; 1-2; 3-4; 5-6; 7+ o'rin; izchillik buzilishi ham hisobga olinadi.
- 1-3, 4 va 11 mezonlarida nizomdagi sifat tavsiflariga tayaning; 2 ball eng to'liq,
  0 ball esa eng past holatga mos keladi. 0.5 va 1.5 ballni oraliq holatga qarab qo'ying.
- Nizomda bo'lmagan yangi mezon qo'shmang.

HAR BIR MEZON UCHUN:
- ball (0, 0.5, 1, 1.5, 2)
- qisqa asos
- kerak bo'lsa xato namunasi va tuzatish
bering.

JAVOB FORMATI:
{
  "status": "normal" yoki "special_case",
  "special_reason": "...",
  "word_count": 0,
  "scores": [
    {"criterion": 1, "name": "...", "score": 0, "reason": "...", "examples": ["..."]},
    ...
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

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✍️ Keyingi esseni tekshirish", "📊 Statistikam"],
        ["👨‍💼 Admin bilan bog‘lanish", "⚠️ Bot kamchiliklari haqida xabar berish"],
        ["📚 Esse qanday yoziladi?"],
    ],
    resize_keyboard=True,
)

ADMIN_CONTACT_URL = os.getenv("ADMIN_CONTACT_URL", "")

async def send_long(message, text: str):
    """Telegram 4096 belgilik limitini hisobga olib xabarni bo‘lib yuboradi."""
    if not text:
        return
    chunk_size = 3900
    for i in range(0, len(text), chunk_size):
        await message.reply_text(text[i:i + chunk_size])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Assalomu alaykum! Men esse tekshiruvchi botman.\n\n"
        "✍️ Esse tekshirish uchun tugmani bosing.\n"
        "Keyin mavzu/vaziyat va essening o‘zini yuborasiz.",
        reply_markup=MAIN_KEYBOARD,
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
    context.user_data.clear()
    await update.message.reply_text("Yangi tekshiruv boshlandi. Mavzu/vaziyatni yuboring.", reply_markup=MAIN_KEYBOARD)

async def evaluate(topic: str, essay: str) -> dict:
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

    try:
        response = await asyncio.to_thread(
            client.responses.create,
            model=MODEL,
            input=[
                {"role": "system", "content": RUBRIC},
                {"role": "user", "content": user_prompt},
            ],
        )
    except AuthenticationError as e:
        logging.exception("OpenAI authentication error during essay evaluation")
        raise RuntimeError("OPENAI_API_KEY noto'g'ri yoki faol emas.") from e
    except RateLimitError as e:
        logging.exception("OpenAI quota/rate-limit error during essay evaluation")
        raise RuntimeError("OpenAI API limiti yoki krediti mavjud emas.") from e
    except BadRequestError as e:
        logging.exception("OpenAI bad request during essay evaluation")
        raise RuntimeError(f"OpenAI so'rovi rad etildi: {e}") from e
    except APIError as e:
        logging.exception("OpenAI API error during essay evaluation")
        raise RuntimeError("OpenAI API xatosi yuz berdi. Render Logs ni tekshiring.") from e

    text = (response.output_text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    if not text:
        raise RuntimeError("OpenAI bo'sh javob qaytardi.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logging.error("OpenAI returned non-JSON output: %r", text[:2000])
        raise RuntimeError("OpenAI javobi JSON formatida kelmadi.") from e

    data["word_count"] = word_count

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
        try:
            total = sum(float(x["score"]) for x in data.get("scores", []))
            data["total"] = min(24, max(0, total))
        except Exception:
            pass

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
3) Faqat rasmda ko'rinadigan esse mazmuni asosida yuqoridagi nizom bo'yicha baholang.
4) JSON javobidagi summary yoki improvements ichida kerak bo'lsa "Rasm sifati/noaniq yozuv" haqida ogohlantiring.

Faqat valid JSON qaytaring.
"""
    try:
        response = await asyncio.to_thread(
            client.responses.create,
            model=MODEL,
            input=[
                {"role": "system", "content": RUBRIC},
                {"role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"},
                ]},
            ],
        )
    except AuthenticationError as e:
        logging.exception("OpenAI authentication error during image evaluation")
        raise RuntimeError("OPENAI_API_KEY noto'g'ri yoki faol emas.") from e
    except RateLimitError as e:
        logging.exception("OpenAI quota/rate-limit error during image evaluation")
        raise RuntimeError("OpenAI API limiti yoki krediti mavjud emas.") from e
    except BadRequestError as e:
        logging.exception("OpenAI bad request during image evaluation")
        raise RuntimeError(f"OpenAI rasm so'rovi rad etildi: {e}") from e
    except APIError as e:
        logging.exception("OpenAI API error during image evaluation")
        raise RuntimeError("OpenAI API xatosi yuz berdi. Render Logs ni tekshiring.") from e

    text = (response.output_text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    if not text:
        raise RuntimeError("OpenAI bo'sh javob qaytardi.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logging.error("OpenAI returned non-JSON image output: %r", text[:2000])
        raise RuntimeError("OpenAI rasm javobi JSON formatida kelmadi.") from e
    return data


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        result = await evaluate_image(topic, buf.getvalue())

        # Keep the same deterministic special-case rules for image essays when the model
        # returns the transcribed word count.
        essay_text = str(result.get("transcription", result.get("essay_text", "")))
        if essay_text:
            wc = count_words(essay_text)
            result["word_count"] = wc
            if wc < 100:
                result["status"] = "special_case"
                result["special_reason"] = "Esse hajmi 100 ta so'zdan kam."
                result["total"] = 2
            elif has_cyrillic(essay_text):
                result["status"] = "special_case"
                result["special_reason"] = "Esse matni to'liq yoki deyarli to'liq kirill alifbosida."
                result["total"] = 0

        await update.message.reply_text(format_result(result))
    except RuntimeError as e:
        logging.exception("Image evaluation error: %s", e)
        await update.message.reply_text(f"⚠️ {e}")
    except Exception as e:
        logging.exception("Unexpected image evaluation error: %s", e)
        await update.message.reply_text("⚠️ Rasmni tekshirishda texnik xatolik yuz berdi. Render Logs ni tekshiring.")


def format_result(data: dict) -> str:
    lines = [
        "📊 ESSE NATIJASI",
        f"So'zlar soni: {data.get('word_count', 0)}",
    ]

    if data.get("status") == "special_case":
        lines.append(f"⚠️ Maxsus holat: {data.get('special_reason', '')}")
        lines.append(f"Yakuniy ball: {data.get('total', 0)}/24")
    else:
        lines.append(f"JAMI: {data.get('total', 0)}/24")

    lines.append("")

    for item in data.get("scores", []):
        score = item.get("score", 0)
        name = item.get("name", "")
        reason = item.get("reason", "")
        lines.append(f"{item.get('criterion', '?')}. {name} — {score}/2")
        lines.append(f"   {reason}")
        for ex in (item.get("examples") or [])[:2]:
            lines.append(f"   • {ex}")
        lines.append("")

    if data.get("summary"):
        lines.append("📝 Umumiy xulosa:")
        lines.append(str(data["summary"]))
        lines.append("")

    improvements = data.get("improvements") or []
    if improvements:
        lines.append("💡 Yaxshilash uchun:")
        for x in improvements[:5]:
            lines.append(f"• {x}")

    return "\n".join(lines)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return

    # Menu buttons
    if text == "✍️ Keyingi esseni tekshirish":
        context.user_data.clear()
        await update.message.reply_text(
            "📝 Mavzu/vaziyatni yuboring.", reply_markup=MAIN_KEYBOARD
        )
        return

    if text == "📊 Statistikam":
        await update.message.reply_text(
            "📊 Statistikam\n\nBu botda shaxsiy natijalar faqat shu suhbatdagi joriy tekshiruv uchun saqlanadi.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text == "👨‍💼 Admin bilan bog‘lanish":
        if ADMIN_CONTACT_URL:
            await update.message.reply_text(
                f"👨‍💼 Admin bilan bog‘lanish:\n{ADMIN_CONTACT_URL}",
                reply_markup=MAIN_KEYBOARD,
            )
        else:
            await update.message.reply_text(
                "Admin kontakti hali sozlanmagan.", reply_markup=MAIN_KEYBOARD
            )
        return

    if text == "⚠️ Bot kamchiliklari haqida xabar berish":
        await update.message.reply_text(
            "⚠️ Kamchilikni shu yerga yozib yuboring. Muammoni log orqali tekshirish mumkin.",
            reply_markup=MAIN_KEYBOARD,
        )
        context.user_data["feedback_mode"] = True
        return

    if text == "📚 Esse qanday yoziladi?":
        await update.message.reply_text(
            "📚 Esse qanday yoziladi?\n\n"
            "• Kirish qismini yozing.\n"
            "• Mavzuning ikki qarashini dalillar bilan yoritib bering.\n"
            "• Shaxsiy fikringizni aniq bildiring.\n"
            "• Asosiy qism va xulosani ajrating.\n"
            "• Imlo va punktuatsiyani tekshiring.\n"
            "• Kamida 100 ta so‘z yozing.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if context.user_data.get("feedback_mode"):
        context.user_data["feedback_mode"] = False
        await update.message.reply_text(
            "Rahmat. Xabaringiz qabul qilindi.", reply_markup=MAIN_KEYBOARD
        )
        return

    if context.user_data.get("busy"):
        await update.message.reply_text(
            "⏳ Oldingi esse hali tekshirilmoqda. Iltimos, natija chiqishini kuting.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    stage = context.user_data.get("stage")

    if stage is None:
        context.user_data["topic"] = text
        context.user_data["stage"] = "essay"
        await update.message.reply_text(
            "Mavzu qabul qilindi ✅\n\nEndi essening o‘zini to‘liq yuboring.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    topic = context.user_data.get("topic", "")
    essay = text
    context.user_data["busy"] = True
    await update.message.reply_text(
        "⏳ Esse tekshirilmoqda. Bir oz kuting...", reply_markup=MAIN_KEYBOARD
    )

    try:
        result = await evaluate(topic, essay)
        await send_long(update.message, format_result(result))
        context.user_data["stage"] = None
        context.user_data.pop("topic", None)
    except json.JSONDecodeError:
        logging.exception("JSON parsing error during evaluation")
        await update.message.reply_text(
            "⚠️ AI javobini o‘qishda xatolik yuz berdi. Iltimos, esseni qayta yuboring.",
            reply_markup=MAIN_KEYBOARD,
        )
    except AuthenticationError:
        logging.exception("OpenAI authentication error")
        await update.message.reply_text(
            "⚠️ OpenAI API kaliti noto‘g‘ri yoki faol emas. Render → Environment Variables → OPENAI_API_KEY ni tekshiring.",
            reply_markup=MAIN_KEYBOARD,
        )
    except RateLimitError:
        logging.exception("OpenAI quota/rate-limit error")
        await update.message.reply_text(
            "⚠️ OpenAI API limiti yoki krediti tugagan. OpenAI API billing/credits ni tekshiring.",
            reply_markup=MAIN_KEYBOARD,
        )
    except BadRequestError as e:
        logging.exception("OpenAI bad request: %s", e)
        await update.message.reply_text(
            "⚠️ OpenAI so‘rovi rad etildi. Render'dagi OPENAI_MODEL qiymatini tekshiring.",
            reply_markup=MAIN_KEYBOARD,
        )
    except Exception as e:
        logging.exception("Evaluation error: %s", e)
        await update.message.reply_text(
            f"⚠️ Tekshiruvda xatolik yuz berdi: {type(e).__name__}. /new orqali qayta urinib ko‘ring.",
            reply_markup=MAIN_KEYBOARD,
        )
    finally:
        context.user_data["busy"] = False

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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Telegram bot ishga tushmoqda...")
    app.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    main()
