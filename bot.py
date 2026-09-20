import os
import re
import json
import logging
import threading
import base64
import hashlib
import asyncio
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ContextTypes, filters
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

if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN va OPENAI_API_KEY Render Environment Variables orqali berilishi kerak."
    )

client = OpenAI(api_key=OPENAI_API_KEY)

# Bir xil esse qayta yuborilsa, qayta AI baholashning oldini olamiz.
EVALUATION_CACHE = {}
MEDIA_GROUPS = {}
MEDIA_GROUP_TASKS = {}
CACHE_MAX = 500

def _cache_key(topic: str, essay: str) -> str:
    normalized = re.sub(r"\s+", " ", (topic + "\n" + essay).strip()).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def _cache_get(key):
    return EVALUATION_CACHE.get(key)

def _cache_put(key, value):
    if len(EVALUATION_CACHE) >= CACHE_MAX:
        EVALUATION_CACHE.pop(next(iter(EVALUATION_CACHE)))
    EVALUATION_CACHE[key] = value

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
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
    context.user_data.clear()
    await update.message.reply_text("Yangi tekshiruv boshlandi. Mavzu/vaziyatni yuboring.")

async def evaluate(topic: str, essay: str) -> dict:
    key = _cache_key(topic, essay)
    cached = _cache_get(key)
    if cached is not None:
        logging.info("Cached evaluation returned: %s", key[:12])
        return json.loads(json.dumps(cached, ensure_ascii=False))

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

    _cache_put(key, data)
    return json.loads(json.dumps(data, ensure_ascii=False))

async def evaluate_image(topic: str, image_bytes_list) -> dict:
    """Evaluate one or several pages/images as ONE essay."""
    if not isinstance(image_bytes_list, (list, tuple)):
        image_bytes_list = [image_bytes_list]

    prompt = f"""
MAVZU/Vaziyat:
{topic}

Vazifa:
- Berilgan rasmlar bir essening ketma-ket sahifalari bo'lishi mumkin. Ularning barchasini BIRTA ESSE sifatida o'qing va baholang.
- Rasmlar 1, 2, 3... tartibida berilgan deb hisoblang.
- Bir xil matn ikki rasmda takrorlangan bo'lsa, uni ikki marta hisoblamang.
- Rasmda ko'rinmagan matnni o'ylab topmang.
- O'qilishi noaniq joylarni alohida qayd eting.
- 100 so'zdan kam, mavzuga mos emas, to'liq kirill va boshqa maxsus holatlar nizomdagi maxsus qoida bo'yicha yakuniy ballga ta'sir qiladi.

Faqat valid JSON qaytaring.
"""

    content = [{"type": "input_text", "text": prompt}]
    for image_bytes in image_bytes_list:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"})

    response = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": content},
        ],
    )
    text = response.output_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)

    # Model maxsus holatni aniqlagan bo'lsa, mezonlar yig'indisi uni bosib ketmasin.
    if data.get("status") == "special_case":
        reason = str(data.get("special_reason", "")).lower()
        if any(x in reason for x in ["mavzuga mos emas", "mavzuga mos kelmay", "100 ta so'zdan kam", "ko'chiril", "kirill"]):
            if "100 ta so'zdan kam" in reason:
                data["total"] = 2
            elif "kirill" in reason:
                data["total"] = 0
            else:
                data["total"] = 2

    return data


async def _process_photo_group(group_key, update, context, photo_items):
    try:
        topic = context.user_data.get("topic", "")
        await update.message.reply_text("⏳ Rasm o'qilmoqda va esse tekshirilmoqda. Bir oz kuting...")

        images = []
        seen = set()
        for file_id in photo_items:
            if file_id in seen:
                continue
            seen.add(file_id)
            tg_file = await context.bot.get_file(file_id)
            buf = BytesIO()
            await tg_file.download_to_memory(buf)
            images.append(buf.getvalue())

        result = await evaluate_image(topic, images)
        await update.message.reply_text(format_result(result))
    except json.JSONDecodeError:
        await update.message.reply_text("Rasmdagi matnni qayta ishlashda xatolik yuz berdi. Aniqroq rasm yuboring.")
    except Exception as e:
        logging.exception("Image evaluation error: %s", e)
        await update.message.reply_text("Rasmni tekshirishda texnik xatolik yuz berdi. Aniqroq rasm yuboring.")
    finally:
        MEDIA_GROUPS.pop(group_key, None)
        MEDIA_GROUP_TASKS.pop(group_key, None)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("stage") != "essay":
        await update.message.reply_text("Avval mavzu/vaziyatni matn ko'rinishida yuboring.")
        return

    # Telegram albomidagi barcha rasmlar bir xil media_group_id oladi.
    media_group_id = update.message.media_group_id
    if media_group_id:
        key = (update.effective_chat.id, media_group_id)
        group = MEDIA_GROUPS.setdefault(key, {"update": update, "files": []})
        group["files"].append(update.message.photo[-1].file_id)

        if key not in MEDIA_GROUP_TASKS:
            async def delayed_process():
                await asyncio.sleep(2.0)
                item = MEDIA_GROUPS.get(key)
                if item:
                    await _process_photo_group(key, item["update"], context, item["files"])
            MEDIA_GROUP_TASKS[key] = context.application.create_task(delayed_process())
        return

    # Bitta rasm bo'lsa ham umumiy evaluator ishlaydi.
    await _process_photo_group(
        (update.effective_chat.id, update.message.message_id),
        update, context, [update.message.photo[-1].file_id]
    )


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
        await update.message.reply_text(format_result(result))
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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Telegram bot ishga tushmoqda...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
