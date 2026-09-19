import os
import re
import json
import logging
import threading
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
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


def make_result_card(data: dict) -> bytes:
    W, H = 1400, 2050
    M = 65
    green, dark, white, bg, gray, line = (37,105,91), (35,45,48), (255,255,255), (244,248,247), (105,115,118), (218,228,225)
    img = Image.new("RGB", (W,H), bg)
    d = ImageDraw.Draw(img)
    title, head, body, small = _font(48,True), _font(30,True), _font(24), _font(21)

    d.rounded_rectangle((30,30,W-30,285), radius=30, fill=white, outline=line, width=3)
    # BBA-style emblem header
    cx, cy = 145, 155
    d.ellipse((65,75,225,235), outline=green, width=10)
    d.ellipse((88,98,202,212), outline=green, width=4)
    d.text((107,102), "BBA", font=_font(43,True), fill=green)
    d.text((265,70), "BBA nizomi bo‘yicha", font=head, fill=green)
    d.text((265,115), "aniq baho", font=title, fill=dark)
    d.text((265,190), "ONA TILI — ESSE BAHOLASH", font=small, fill=gray)

    total = data.get("total", 0)
    d.rounded_rectangle((M,320,W-M,480), radius=25, fill=green)
    d.text((M+35,350), "YAKUNIY BALL", font=head, fill=white)
    s = f"{total}/24"; bb=d.textbbox((0,0),s,font=_font(62,True))
    d.text((W-M-35-(bb[2]-bb[0]),340), s, font=_font(62,True), fill=white)

    d.rounded_rectangle((M,515,W-M,625), radius=20, fill=white, outline=line, width=2)
    d.text((M+30,550), f"So‘zlar soni: {data.get('word_count',0)}", font=head, fill=dark)
    if data.get("status") == "special_case":
        d.text((M+410,550), "⚠ Maxsus holat", font=head, fill=green)

    y=665
    d.text((M,y), "12 MEZON BO‘YICHA NATIJA", font=head, fill=dark); y+=50
    scores=data.get("scores",[])
    if scores:
        for item in scores[:12]:
            name=str(item.get("name",""))
            if len(name)>62: name=name[:59]+"..."
            d.rounded_rectangle((M,y,W-M,y+62), radius=12, fill=white)
            d.text((M+18,y+14), f"{item.get('criterion','?')}. {name}", font=body, fill=dark)
            ss=f"{item.get('score',0)}/2"; bb=d.textbbox((0,0),ss,font=head)
            d.text((W-M-18-(bb[2]-bb[0]),y+15),ss,font=head,fill=green)
            y+=70
    else:
        d.rounded_rectangle((M,y,W-M,y+85), radius=12, fill=white)
        d.text((M+20,y+25),"Maxsus holat: odatdagi 12 mezon qo‘llanilmadi.",font=body,fill=dark)
        y+=110

    y+=10
    if data.get("summary"):
        d.text((M,y),"UMUMIY XULOSA",font=head,fill=dark); y+=42
        for ln in _wrap(d,data["summary"],small,W-2*M):
            d.text((M,y),ln,font=small,fill=dark); y+=27
            if y>H-210: break

    improvements=data.get("improvements") or []
    if improvements and y<H-120:
        y+=8; d.text((M,y),"YAXSHILASH UCHUN",font=head,fill=dark); y+=40
        for item in improvements[:3]:
            for ln in _wrap(d,"• "+str(item),small,W-2*M):
                d.text((M,y),ln,font=small,fill=dark); y+=26
                if y>H-85: break

    d.line((M,H-60,W-M,H-60),fill=line,width=2)
    d.text((M,H-48),"BBA nizomi asosida AI yordamchi baholashi",font=small,fill=gray)
    out=__import__("io").BytesIO()
    img.save(out,format="JPEG",quality=92,optimize=True)
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
        await send_result(update, result)


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
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("Telegram bot ishga tushmoqda...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
