import os
import re
import json
import asyncio
import logging
import threading
import hashlib
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InputFile, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI
from openai import APIError, AuthenticationError, RateLimitError, BadRequestError

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
PORT = int(os.getenv("PORT", "10000"))
ADMIN_CONTACT_URL = os.getenv("ADMIN_CONTACT_URL", "")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN Render Environment Variables orqali berilishi kerak.")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY Render Environment Variables orqali berilishi kerak.")

client = OpenAI(api_key=OPENAI_API_KEY, timeout=90.0, max_retries=2)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("esse_bot")

# ============================================================
# BASIRAT NIZOMI — BERILGAN PDFDAGI MEZONLAR
# ============================================================

RUBRIC = r""" Siz O'zbekiston milliy test tizimi doirasida ONA TILI VA ADABIYOT fanidan yozma ish (esse)ni baholovchi qat'iy ekspert sifatida ishlaysiz. ASOSIY MANBA: "ESSE BAHOLASH NIZOMI - BASIRAT.pdf" - Jami 24 ball. - 12 mezon. - Har bir mezon faqat 0, 0.5, 1, 1.5 yoki 2 ball. - Maxsus holatlar oddiy baholashdan ustun: 1) Esse yozilmagan -> 0 ball. 2) Esse mavzuga mos emas -> jami 2 ball. 3) Esse 100 ta so'zdan kam -> jami 2 ball. 4) Esse boshqa manbadan ko'chirilganligi ishonchli aniqlansa -> jami 2 ball. 5) Faqat kirish qismi yozilib, boshqa qismlar yozilmagan -> jami 0 ball. 6) Esse matni to'liq kirill alifbosida -> jami 0 ball. - Ko'chirilganlikni dalilsiz taxmin qilmang. - Berilgan vaziyat matnini aynan ko'chirish — talabga zid, ammo bu o'z-o'zidan internetdan ko'chirilganlik dalili emas. - Esse uchun reja tuzilmaydi, epigraf qo'yilmaydi. 12 MEZON: 1. PUBLITSISTIK USLUB 2: to'liq publitsistik uslub. 1.5: ayrim o'rinlarda publitsistik uslubdan chekinilgan. 1: qisman publitsistik. 0.5: to'liq badiiy uslub. 0: to'liq so'zlashuv uslubi. 2. IKKALA QARASH + SHAXSIY QARASH 2: ikkala qarash va shaxsiy qarash to'la yoritilgan. 1.5: ikkala qarash bor, shaxsiy fikr yo'q. 1: qarashlarning bittasi to'la yoritilgan. 0.5: faqat bittasi qisman yoritilgan. 0: qarashlar yoritilmagan. 3. IKKALA QARASHNI DALILLASH 2: ikkala qarash dalillar bilan asoslangan. 1.5: faqat bitta qarash dalillangan. 1: ikkala qarash uchun ayrim dalillar vaziyatga mos emas. 0.5: ikkala qarash dalillari vaziyatga mos emas. 0: ikkala qarash dalillanmagan. 4. KIRISH + ASOSIY QISM + XULOSA 2: uchala qism to'la. 1.5: faqat ikki qism to'la. 1: ikki qism yuzaki. 0.5: faqat bir qism to'la. 0: faqat bir qism yuzaki. 5. MANTIQIY-QURILISH VA XATBOSHI 2: xato yo'q, xatboshilar to'g'ri. 1.5: 1-2 o'rin xato. 1: 3-4 o'rin. 0.5: 5-6 o'rin. 0: 7+ o'rin yoki umuman xatboshisiz. 6. MANTIQIY-MAZMUNIY IZCHILLIK VA FIKR TAKRORI 2: izchillik to'liq, takror yo'q. 1.5: takror 1-2 o'rin, izchillik buzilmagan. 1: takror 3-4 o'rin va izchillik buzilgan. 0.5: takror 5-6 o'rin va izchillik buzilgan. 0: takror 7+ o'rin va izchillik buzilgan. 7. IMLO 2: 0 xato. 1.5: 1-2. 1: 3-4. 0.5: 5-6. 0: 7+. 8. PUNKTUATSIYA 2: 0 xato. 1.5: 1-2. 1: 3-4. 0.5: 5-6. 0: 7+. 9. QO'SHIMCHA QO'LLASH 2: 0 xato. 1.5: 1-2. 1: 3-4. 0.5: 5-6. 0: 7+. 10. SO'Z QO'LLASH BILAN BOG'LIQ USLUBIY XATOLAR 2: 0 xato. 1.5: 1-2. 1: 3-4. 0.5: 5-6. 0: 7+. Bunga so'zni noto'g'ri qo'llash, noo'rin takror, ortiqcha qo'llash, tushirib qoldirish, bog'lovchi vositalar va kiritmalar bilan bog'liq xatolar kiradi. 11. LEKSIK XILMA-XILLIK 2: tasviriy ifodalar, vaziyatga mos maxsus leksik birliklar va barqaror birikmalardan unumli foydalanilgan. 1.5: leksik xilma-xillik bor, ayrim o'rinlarda foydalanilgan. 1: leksik xilma-xillik bor, ayrim o'rinlarda noo'rin foydalanilgan. 0.5: leksik xilma-xillik kuzatilmagan, birliklar noo'rin. 0: leksik xilma-xillik kuzatilmagan, bunday birliklardan foydalanilmagan. 12. SHEVA/VULGARIZM/VARVARIZM/PARAZIT SO'ZLAR 2: 0 xato. 1.5: 1-2 xato, uslubiy g'alizlik yo'q. 1: 3-4 xato, uslubiy g'alizlik bor. 0.5: 5-6 xato, uslubiy g'alizlik bor. 0: 7+ xato, uslubiy g'alizlik bor. QAT'IY: - Baholashni saxiylashtirmang. "Umuman yaxshi" degan taassurot 2/2 uchun yetarli emas. - 2/2 faqat aynan 2-ball deskriptori TO'LIQ bajarilganda beriladi. - 1.5/2 yoki undan past ball berishdan qo'rqmang; kamchilik bo'lsa aniq ko'rsating. - 4-mezon uchun kirish, asosiy qism va xulosaning mavjudligini alohida aniqlang. Xulosa bo'lmasa, 4-mezonni 2/2 QILMANG. - 7,8,9,10,12 da ballni xato soni belgilaydi. - 5 da ballni xato soni belgilaydi. - 6 da repetition_count + coherence_intact asosida ballni dastur hisoblaydi. - 5,7,8,9,10,12 mezonlarida error_count nechta bo'lsa, errors ro'yxatida ham aynan shuncha alohida xato bo'lsin. - Har bir xato SO'ZMA-SO'Z ko'rsatiladi: "wrong", "correct", "explanation". To'g'ri variant mavjud bo'lmasa, correct bo'sh qoldirilsin va nima noto'g'ri ekanini tushuntiring. - "errors" ro'yxatiga umumiy gap yozmang. Har bir element bitta aniq xato bo'lsin. - Fikr takrorida takrorlangan aniq so'z/birikma yoki gap parchasi ko'rsatilsin. - Bir xil xatoni ikki mezonda takroran sanamang. - Natijada aynan 12 mezon bo'lsin. """

CRITERION_NAMES = {
    1: "Publitsistik uslub",
    2: "Ikkala qarash va shaxsiy qarash",
    3: "Har ikkala qarashning dalillar bilan asoslanishi",
    4: "Kirish, asosiy qism, xulosa",
    5: "Mantiqiy-qurilish va xatboshilar",
    6: "Mantiqiy-mazmuniy izchillik va fikrlar takrori",
    7: "Imlo",
    8: "Punktuatsiya",
    9: "Qo'shimcha qo'llash",
    10: "So'z qo'llash uslubiyati",
    11: "Leksik xilma-xillik",
    12: "Sheva, vulgarizm, varvarizm, parazit so'zlar",
}

# ============================================================
# CACHE / LOCK / STATISTIKA
# ============================================================

USER_LOCKS = {}
USER_LOCKS_GUARD = asyncio.Lock()
RESULT_CACHE = {}
CACHE_GUARD = threading.Lock()
CACHE_MAX = 100

STATS = {"checks": 0, "text_checks": 0, "image_checks": 0, "errors": 0}
STATS_GUARD = threading.Lock()

def inc_stat(key):
    with STATS_GUARD:
        STATS[key] = STATS.get(key, 0) + 1

def cache_key(*parts):
    raw = "\n---\n".join(str(x or "") for x in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def cache_get(key):
    with CACHE_GUARD:
        return RESULT_CACHE.get(key)

def cache_put(key, value):
    with CACHE_GUARD:
        if len(RESULT_CACHE) >= CACHE_MAX:
            RESULT_CACHE.pop(next(iter(RESULT_CACHE)))
        RESULT_CACHE[key] = value

async def get_user_lock(user_id):
    async with USER_LOCKS_GUARD:
        if user_id not in USER_LOCKS:
            USER_LOCKS[user_id] = asyncio.Lock()
        return USER_LOCKS[user_id]

# ============================================================
# KEYBOARD
# ============================================================

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["✍️ Keyingi esseni tekshirish", "📊 Statistikam"],
        ["👨‍💼 Admin bilan bog‘lanish", "⚠️ Bot kamchiliklari haqida xabar berish"],
        ["📚 Esse qanday yoziladi?"],
    ],
    resize_keyboard=True,
)

# ============================================================
# DETERMINISTIK TEKSHIRUVLAR
# ============================================================

def count_words(text):
    return len(re.findall(r"\S+", text or "", flags=re.UNICODE))

def is_full_cyrillic(text):
    letters = re.findall(r"[A-Za-zА-Яа-яЁёҚқҒғҲҳЎў]", text or "")
    if not letters:
        return False
    cyr = re.findall(r"[А-Яа-яЁёҚқҒғҲҳЎў]", text or "")
    return len(cyr) / len(letters) >= 0.98

def clean_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def score_from_error_count(n):
    n = max(0, int(n))
    if n == 0:
        return 2.0
    if n <= 2:
        return 1.5
    if n <= 4:
        return 1.0
    if n <= 6:
        return 0.5
    return 0.0

def validate_scores(data):
    scores = data.get("scores")
    if not isinstance(scores, list) or len(scores) != 12:
        raise ValueError("AI 12 ta mezonni to'liq qaytarmadi.")

    seen = set()
    for item in scores:
        c = int(item["criterion"])
        if c in seen or c not in range(1, 13):
            raise ValueError("Mezon raqamlari noto'g'ri.")
        seen.add(c)

        score = float(item.get("score", 0))
        if score not in {0.0, 0.5, 1.0, 1.5, 2.0}:
            raise ValueError(f"{c}-mezon balli noto'g'ri.")
        if not isinstance(item.get("errors", []), list):
            raise ValueError(f"{c}-mezon errors ro'yxati noto'g'ri.")
        if not isinstance(item.get("evidence", []), list):
            raise ValueError(f"{c}-mezon evidence ro'yxati noto'g'ri.")

    if seen != set(range(1, 13)):
        raise ValueError("12 mezonning barchasi yo'q.")

def normalize_scores(data):
    by_c = {int(x["criterion"]): x for x in data["scores"]}

    # Har bir xato so'zma-so'z ro'yxatda bo'lishi shart.
    for c in (5, 7, 8, 9, 10, 12):
        item = by_c[c]
        errors = item.get("errors") or []
        # AI sanog'i bilan real ro'yxatni moslashtiramiz: ro'yxatdagi har bir
        # element alohida xato hisoblanadi.
        item["errors"] = [e for e in errors if isinstance(e, dict)]
        n = len(item["errors"])
        item["error_count"] = n
        item["score"] = score_from_error_count(n)

    # 6 — fikr takrorlari ham aniq ko'rsatiladi.
    item = by_c[6]
    errors = item.get("errors") or []
    item["errors"] = [e for e in errors if isinstance(e, dict)]
    rep = len(item["errors"])
    coherent = bool(item.get("coherence_intact", False))
    item["repetition_count"] = rep
    item["coherence_intact"] = coherent

    if rep == 0 and coherent:
        item["score"] = 2.0
    elif rep <= 2 and coherent:
        item["score"] = 1.5
    elif 3 <= rep <= 4 and not coherent:
        item["score"] = 1.0
    elif 5 <= rep <= 6 and not coherent:
        item["score"] = 0.5
    elif rep >= 7 and not coherent:
        item["score"] = 0.0
    else:
        if rep >= 7:
            item["score"] = 0.0
        elif rep >= 5:
            item["score"] = 0.5
        elif rep >= 3:
            item["score"] = 1.0
        elif rep >= 1:
            item["score"] = 1.5
        else:
            item["score"] = 1.0

    # 4-mezonni tuzilma bo'yicha majburiy qayta hisoblash.
    st = data.get("structure") or {}
    hi = bool(st.get("has_introduction"))
    hm = bool(st.get("has_main_part"))
    hc = bool(st.get("has_conclusion"))
    ic = bool(st.get("introduction_complete", hi))
    mc = bool(st.get("main_part_complete", hm))
    cc = bool(st.get("conclusion_complete", hc))
    complete = sum([hi and ic, hm and mc, hc and cc])
    if complete == 3:
        by_c[4]["score"] = 2.0
    elif complete == 2:
        by_c[4]["score"] = 1.5
    elif complete == 1:
        # Nizomda faqat bir qism to'liq bo'lsa 0.5; faqat yuzaki bo'lsa 0.
        by_c[4]["score"] = 0.5
    else:
        by_c[4]["score"] = 0.0

    # 2-mezon: ikkala qarash + shaxsiy qarash.
    vp = data.get("viewpoints") or {}
    a = bool(vp.get("viewpoint_a_full"))
    b = bool(vp.get("viewpoint_b_full"))
    personal = bool(vp.get("personal_view_present"))
    if a and b and personal:
        by_c[2]["score"] = 2.0
    elif a and b and not personal:
        by_c[2]["score"] = 1.5
    elif a or b:
        by_c[2]["score"] = 1.0 if bool(vp.get("viewpoint_a_present")) or bool(vp.get("viewpoint_b_present")) else 0.5
    else:
        by_c[2]["score"] = 0.0

    # 3-mezon: ikkala qarashga dalil bo'lmasa 2/2 bo'lmaydi.
    ev = data.get("evidence") or {}
    ea = bool(ev.get("viewpoint_a_evidence_present"))
    eb = bool(ev.get("viewpoint_b_evidence_present"))
    if ea and eb:
        # Model bergan ball 2 bo'lmasa, uni oshirmaymiz.
        by_c[3]["score"] = min(float(by_c[3].get("score", 0)), 2.0)
    elif ea or eb:
        by_c[3]["score"] = min(float(by_c[3].get("score", 0)), 1.5)
    else:
        by_c[3]["score"] = min(float(by_c[3].get("score", 0)), 0.0)

    data["scores"] = sorted(by_c.values(), key=lambda x: int(x["criterion"]))
    data["total"] = round(sum(float(x["score"]) for x in data["scores"]), 1)
    return data

def apply_special_case(data, essay):
    word_count = count_words(essay)
    data["word_count"] = word_count

    if not essay.strip():
        data["status"] = "special_case"
        data["special_reason"] = "Esse yozilmagan."
        data["total"] = 0.0
        return data

    if is_full_cyrillic(essay):
        data["status"] = "special_case"
        data["special_reason"] = "Esse matni to'liq kirill alifbosida yozilgan."
        data["total"] = 0.0
        return data

    if data.get("only_introduction") is True:
        data["status"] = "special_case"
        data["special_reason"] = "Faqat kirish qismi yozilgan, boshqa qismlar yozilmagan."
        data["total"] = 0.0
        return data

    if data.get("off_topic") is True:
        data["status"] = "special_case"
        data["special_reason"] = "Esse berilgan mavzuga mos emas."
        data["total"] = 2.0
        return data

    if word_count < 100:
        data["status"] = "special_case"
        data["special_reason"] = "Esse hajmi 100 ta so'zdan kam."
        data["total"] = 2.0
        return data

    if data.get("copied_with_evidence") is True:
        data["status"] = "special_case"
        data["special_reason"] = "Esse boshqa manbadan ko'chirilganligi aniqlandi."
        data["total"] = 2.0
        return data

    data["status"] = "normal"
    data["special_reason"] = ""
    return normalize_scores(data)

# ============================================================
# OPENAI
# ============================================================

def make_eval_prompt(topic, essay):
    return f""" MAVZU/VAZIYAT: {topic} ESSE: {essay} Dastur hisoblagan so'zlar soni: {count_words(essay)} Sizning vazifangiz — BASIRAT NIZOMINI juda qat'iy qo'llab, ortiqcha ball bermaslik. Matndagi real dalilsiz 2/2 qo'ymang. Har bir xulosani essening aniq parchasi bilan asoslang. Faqat quyidagi JSON strukturani qaytaring: {{ "off_topic": false, "copied_with_evidence": false, "only_introduction": false, "structure": {{ "has_introduction": true, "has_main_part": true, "has_conclusion": false, "introduction_complete": true, "main_part_complete": true, "conclusion_complete": false }}, "viewpoints": {{ "viewpoint_a_present": true, "viewpoint_a_full": true, "viewpoint_b_present": true, "viewpoint_b_full": true, "personal_view_present": true }}, "evidence": {{ "viewpoint_a_evidence_present": true, "viewpoint_b_evidence_present": true }}, "scores": [ {{ "criterion": 1, "name": "Publitsistik uslub", "score": 0, "reason": "Nizom deskriptori bilan bog'langan xolis asos", "evidence": ["essening aynan ko'ringan qisqa parchasi"], "errors": [], "error_count": 0, "repetition_count": 0, "coherence_intact": true }} ], "summary": "Xolis umumiy xulosa", "improvements": ["Aniq tavsiya 1", "Aniq tavsiya 2", "Aniq tavsiya 3"] }} HAR BIR MEZON UCHUN: - reason — nima sababdan aynan shu ball berilganini yozing. - evidence — essedan aynan ko'ringan qisqa dalil(lar). - errors — faqat aniq xatolar uchun ishlatiladi. - 5,7,8,9,10,12 da error_count nechta bo'lsa, errors ham aynan shuncha bo'lsin. - Har bir error: {{"wrong":"esseda aynan yozilgan so'z/birikma","correct":"to'g'ri shakl","explanation":"xatoning aniq sababi"}} - So'zma-so'z xatoni ko'rsatmasdan "imlo xatolari bor" kabi umumiy xulosa yozmang. - 6-mezonda repetition_count nechta bo'lsa, takrorlarning aniq parchalarini errors ichida ko'rsating. - Bir xil xatoni ikki xil mezonda hisoblamang. QAT'IY BAHOLASH: - 1,2,3,4,11 mezonlarida 2/2 faqat tegishli 2-ball sharti to'liq bajarilganda. - 4-mezon: kirish + asosiy qism + xulosa uchalasi to'liq bo'lmasa 2/2 bermang. - 2-mezon: ikkala qarash va shaxsiy qarashning barchasi to'liq bo'lmasa 2/2 bermang. - 3-mezon: ikkala qarashning har biri aniq dalil bilan asoslanmasa 2/2 bermang. - 11-mezon: shunchaki "so'zlar turlicha" degani 2/2 uchun yetarli emas; tasviriy/maxsus/barqaror birliklarning aniq misolini ko'rsating. - 5,7,8,9,10,12 uchun ballni dastur error_count orqali qayta hisoblaydi. - 6 uchun ballni dastur repetition_count + coherence_intact orqali qayta hisoblaydi. - Faqat kirish qismi bo'lsa only_introduction=true. - Mavzuga mos kelmasa off_topic=true. - Dalilsiz copied_with_evidence=true qo'ymang. - Markdown ishlatmang. """

async def call_openai(topic, essay):
    try:
        response = await asyncio.to_thread(
            client.responses.create,
            model=MODEL,
            input=[
                {"role": "system", "content": RUBRIC},
                {"role": "user", "content": make_eval_prompt(topic, essay)},
            ],
        )
    except AuthenticationError as e:
        raise RuntimeError("OPENAI_API_KEY noto'g'ri yoki faol emas.") from e
    except RateLimitError as e:
        raise RuntimeError("OpenAI API limiti yoki krediti mavjud emas.") from e
    except BadRequestError as e:
        raise RuntimeError(f"OpenAI so'rovi rad etildi: {e}") from e
    except APIError as e:
        raise RuntimeError("OpenAI API xatosi yuz berdi.") from e

    raw = clean_json(response.output_text)
    if not raw:
        raise RuntimeError("OpenAI bo'sh javob qaytardi.")

    try:
        data = json.loads(raw)
        validate_scores(data)
        return normalize_scores(data)
    except Exception as e:
        logger.exception("AI JSON validation error: %s", raw[:1500])
        raise RuntimeError("AI javobi noto'g'ri formatda qaytdi.") from e

async def evaluate_text(topic, essay):
    key = cache_key("text", topic, essay, MODEL)
    cached = cache_get(key)
    if cached is not None:
        return cached

    data = await call_openai(topic, essay)
    data = apply_special_case(data, essay)
    cache_put(key, data)
    return data

async def evaluate_image(topic, image_bytes):
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    key = cache_key("image", topic, image_hash, MODEL)
    cached = cache_get(key)
    if cached is not None:
        return cached

    import base64
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = f""" MAVZU/VAZIYAT: {topic} Rasmdagi qo'lda yozilgan esseni o'qing va aynan ko'ringan matn asosida baholang. Ko'rinmagan so'zlarni o'ylab topmang. O'qilishi noaniq joylarni reason ichida qayd eting. So'zlar sonini transkripsiya qilingan matn asosida hisoblang. JSON: {{ "transcription": "o'qilgan matn", "off_topic": false, "copied_with_evidence": false, "only_introduction": false, "scores": [ {{"criterion":1,"name":"Publitsistik uslub","score":0,"reason":"","examples":[],"error_count":0,"repetition_count":0,"coherence_intact":true}} ], "summary":"", "improvements":[] }} """

    try:
        response = await asyncio.to_thread(
            client.responses.create,
            model=MODEL,
            input=[
                {"role": "system", "content": RUBRIC},
                {"role": "user", "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"},
                ]},
            ],
        )
    except AuthenticationError as e:
        raise RuntimeError("OPENAI_API_KEY noto'g'ri yoki faol emas.") from e
    except RateLimitError as e:
        raise RuntimeError("OpenAI API limiti yoki krediti mavjud emas.") from e
    except BadRequestError as e:
        raise RuntimeError(f"OpenAI rasm so'rovi rad etildi: {e}") from e
    except APIError as e:
        raise RuntimeError("OpenAI API xatosi yuz berdi.") from e

    raw = clean_json(response.output_text)
    try:
        data = json.loads(raw)
        validate_scores(data)
        data = normalize_scores(data)
    except Exception as e:
        logger.exception("Image JSON validation error")
        raise RuntimeError("Rasmni o'qish/baholash javobi noto'g'ri formatda qaytdi.") from e

    transcription = str(data.get("transcription") or "")
    data["word_count"] = count_words(transcription)
    data = apply_special_case(data, transcription)
    data["_image_mode"] = True
    cache_put(key, data)
    return data

# ============================================================
# 75 BALLIK KO'RSATKICH
# ============================================================

# Basirat PDFning o'zida 75 ballik konversiya jadvali yo'q.
# Shuning uchun bu "rasmiy 75 ball" deb ko'rsatilmaydi:
# 24 ballning matematik ekvivalenti sifatida ko'rsatiladi.
def to_75(total24):
    """24-lik natijani foydalanuvchi so'ragan 75-24 shkala bo'yicha o'tkazadi. 24 -> 75 23.5 -> 74 23 -> 73 22.5 -> 72 ... """
    try:
        x = round(float(total24) * 2) / 2
        return round(75.0 - (24.0 - x) * 2.0, 1)
    except (TypeError, ValueError):
        return 0.0

# ============================================================
# RASMLI NATIJA
# ============================================================

def get_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def wrap_text(draw, text, fnt, width):
    words = str(text).split()
    if not words:
        return [""]
    lines, current = [], ""
    for word in words:
        test = word if not current else current + " " + word
        if draw.textbbox((0, 0), test, font=fnt)[2] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def load_emblem(max_size=(190, 190)):
    """Repo ichidagi emblem.png bo'lsa, natija kartasiga joylaydi."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "emblem.png"),
        "emblem.png",
    ]
    for path in candidates:
        try:
            if os.path.exists(path):
                im = Image.open(path).convert("RGBA")
                im.thumbnail(max_size, Image.LANCZOS)
                return im
        except Exception:
            logger.exception("emblem.png o'qilmadi")
    return None

def draw_wrapped(draw, text, xy, font, fill, width, line_gap=7, max_lines=None):
    lines = wrap_text(draw, str(text or ""), font, width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = lines[-1].rstrip(". ") + "..."
    x, y = xy
    line_h = int(font.size * 1.25) + line_gap
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h
    return y, len(lines) * line_h

def error_lines(item):
    errs = item.get("errors") or []
    result = []
    for i, e in enumerate(errs, 1):
        if not isinstance(e, dict):
            continue
        wrong = str(e.get("wrong") or "").strip()
        correct = str(e.get("correct") or "").strip()
        explanation = str(e.get("explanation") or "").strip()
        if not wrong and not explanation:
            continue
        if correct:
            line = f"{i}) {wrong} -> {correct}"
        else:
            line = f"{i}) {wrong}"
        result.append((line, explanation))
    return result

def make_result_image(data):
    # Avvalgi BBA ko'rinishiga yaqin: emblem + katta ball + 2 ustunli mezonlar.
    W = 1500
    M = 55
    bg = (248, 252, 251)
    white = (255, 255, 255)
    teal = (24, 126, 101)
    teal_dark = (31, 91, 84)
    teal_light = (233, 246, 243)
    text = (35, 64, 61)
    muted = (86, 111, 108)
    border = (215, 235, 231)
    red = (173, 70, 70)

    title = get_font(48, True)
    subtitle = get_font(28)
    score_big = get_font(74, True)
    score_small = get_font(27, True)
    crit = get_font(22, True)
    body = get_font(21)
    small = get_font(18)
    tiny = get_font(16)

    items = sorted(data.get("scores", []), key=lambda x: int(x["criterion"]))
    cards = []
    for item in items:
        c = int(item["criterion"])
        score = float(item.get("score", 0))
        reason = str(item.get("reason") or "").strip()
        evidence = item.get("evidence") or []
        errs = error_lines(item)

        content = []
        if reason:
            content.append(("reason", reason))
        if evidence and c in (1, 2, 3, 4, 11):
            content.append(("evidence", "Dalil: " + " | ".join(str(x) for x in evidence[:2])))

        if c in (5, 7, 8, 9, 10, 12):
            content.append(("count", f"Xatolar soni: {len(item.get('errors') or [])}"))
        if c == 6:
            content.append(("count", f"Fikr takrori: {len(item.get('errors') or [])}"))

        for line, explanation in errs:
            content.append(("error", "XATO: " + line))
            if explanation:
                content.append(("error_explain", explanation))

        cards.append((c, score, content))

    # Card balandligi dinamik: xatolar ko'p bo'lsa card kattalashadi.
    dummy = Image.new("RGB", (10, 10), white)
    dd = ImageDraw.Draw(dummy)
    card_w = (W - 2*M - 30) // 2
    inner_w = card_w - 44

    def header_line_count(c):
        name = CRITERION_NAMES.get(c, str(c))
        score_sample = "2/2"
        score_w = dd.textbbox((0, 0), score_sample, font=crit)[2]
        name_w = inner_w - score_w - 30
        return len(wrap_text(dd, name, crit, name_w))

    def card_height(content, c):
        header_lines = header_line_count(c)
        h = 62 + max(0, header_lines - 1) * 27
        for kind, val in content:
            if kind == "reason":
                h += len(wrap_text(dd, val, body, inner_w)) * 31 + 6
            elif kind == "evidence":
                h += len(wrap_text(dd, val, small, inner_w)) * 26 + 5
            elif kind == "count":
                h += 29
            elif kind == "error":
                h += len(wrap_text(dd, val, small, inner_w)) * 26 + 4
            elif kind == "error_explain":
                h += len(wrap_text(dd, val, tiny, inner_w-13)) * 23 + 4
        return max(h, 120)

    card_heights = [card_height(c[2], c[0]) for c in cards]
    row_heights = []
    for i in range(0, len(cards), 2):
        row_heights.append(max(card_heights[i:i+2]))

    header_h = 360
    cards_start = header_h
    rows_h = sum(h + 22 for h in row_heights)
    footer_h = 330
    H = cards_start + rows_h + footer_h + 50

    img = Image.new("RGB", (W, H), bg)
    dr = ImageDraw.Draw(img)

    # Header
    dr.rounded_rectangle((M, 30, W-M, 330), radius=35, fill=white, outline=border, width=2)

    emblem = load_emblem((210, 210))
    if emblem:
        img.alpha_composite(emblem, (M+28, 72)) if img.mode == "RGBA" else img.paste(emblem, (M+28, 72), emblem)
        tx = M + 265
    else:
        tx = M + 55

    dr.text((tx, 62), "Esse baholovchi bot", font=title, fill=teal_dark)
    dr.text((tx, 128), "Sizning essseeingiz BBA nizomi bo'yicha", font=subtitle, fill=teal_dark)
    dr.text((tx, 165), "tekshirildi va quyidagi natija aniqlandi:", font=subtitle, fill=teal_dark)

    # Score pill
    pill_x1, pill_y1, pill_x2, pill_y2 = 420, 205, 1080, 315
    dr.rounded_rectangle((pill_x1, pill_y1, pill_x2, pill_y2), radius=28, fill=teal)
    total = float(data.get("total", 0))
    dr.text((pill_x1+80, pill_y1+13), f"{total:g}", font=score_big, fill=white)
    dr.text((pill_x1+315, pill_y1+42), "/24", font=score_small, fill=white)
    dr.text((pill_x1+255, pill_y1+76), "YAKUNIY BALL", font=score_small, fill=white)

    # 75 ekvivalent
    eq = to_75(total)
    dr.text((W-500, 55), f"75 BALLIK EKVIVALENT: {eq:g}/75", font=get_font(24, True), fill=teal)
    dr.text((W-500, 90), f"So'zlar soni: {int(data.get('word_count', 0))}", font=small, fill=muted)

    # Criteria cards
    y = cards_start
    for row_i, rh in enumerate(row_heights):
        x_positions = [M, M + card_w + 30]
        for col in range(2):
            idx = row_i*2 + col
            if idx >= len(cards):
                continue
            c, score, content = cards[idx]
            x = x_positions[col]
            y2 = y + rh
            dr.rounded_rectangle((x, y, x+card_w, y2), radius=24, fill=teal_light, outline=border, width=2)

            # header
            dr.ellipse((x+22, y+22, x+57, y+57), fill=teal)
            score_txt = f"{score:g}/2"
            sw = dr.textbbox((0,0), score_txt, font=crit)[2]
            dr.text((x+card_w-28-sw, y+19), score_txt, font=crit, fill=teal)

            name = CRITERION_NAMES.get(c, str(c))
            name_w = inner_w - sw - 35
            name_lines = wrap_text(dr, name, crit, name_w)
            ny = y + 19
            for line in name_lines[:2]:
                dr.text((x+70, ny), line, font=crit, fill=text)
                ny += 27
            cy = y + 68 + max(0, len(name_lines[:2])-1)*27
            for kind, val in content:
                if kind == "reason":
                    cy, _ = draw_wrapped(dr, val, (x+22, cy), body, muted, inner_w, line_gap=4)
                    cy += 5
                elif kind == "evidence":
                    cy, _ = draw_wrapped(dr, val, (x+22, cy), small, teal_dark, inner_w, line_gap=3)
                    cy += 4
                elif kind == "count":
                    dr.text((x+22, cy), val, font=small, fill=muted)
                    cy += 29
                elif kind == "error":
                    cy, _ = draw_wrapped(dr, val, (x+22, cy), small, red, inner_w, line_gap=2)
                    cy += 2
                elif kind == "error_explain":
                    cy, _ = draw_wrapped(dr, "Izoh: " + val, (x+35, cy), tiny, muted, inner_w-13, line_gap=2)
                    cy += 2
        y += rh + 22

    # Footer summary + improvements
    fy = y + 5
    dr.rounded_rectangle((M, fy, W-M, fy+170), radius=24, fill=white, outline=border, width=2)
    dr.text((M+30, fy+22), "Umumiy xulosa:", font=get_font(34, True), fill=teal_dark)
    summary = str(data.get("summary") or "").strip()
    draw_wrapped(dr, summary, (M+30, fy+70), body, muted, W-2*M-60, line_gap=3, max_lines=4)

    fy2 = fy + 190
    improvements = data.get("improvements") or []
    if improvements:
        extra_h = 42 + min(5, len(improvements))*34 + 20
        dr.rounded_rectangle((M, fy2, W-M, fy2+extra_h), radius=24, fill=teal_light, outline=border, width=2)
        dr.text((M+30, fy2+18), "Yaxshilash uchun:", font=get_font(28, True), fill=teal_dark)
        yy = fy2 + 58
        for imp in improvements[:5]:
            yy, _ = draw_wrapped(dr, "• " + str(imp), (M+40, yy), small, muted, W-2*M-80, line_gap=2)
    else:
        fy2 += 0

    # Bottom brand
    bottom = H - 55
    dr.text((W//2-190, bottom), "BILIMNI BAHOLASH AGENTLIGI", font=get_font(22, True), fill=teal_dark)

    out = BytesIO()
    out.name = "esse_natijasi.jpg"
    img.save(out, "JPEG", quality=93, optimize=True)
    out.seek(0)
    return out

def make_stats_image():
    with STATS_GUARD:
        st = dict(STATS)

    W, H = 1100, 850
    blue = (24,67,108)
    green = (21,116,75)
    dark = (38,38,38)
    gray = (90,90,90)

    img = Image.new("RGB", (W,H), "white")
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle((20,20,W-20,H-20), radius=32, outline=blue, width=5)
    dr.text((70,65), "📊 STATISTIKAM", font=get_font(52,True), fill=blue)

    values = [
        ("Jami tekshiruvlar", st["checks"]),
        ("Matnli tekshiruvlar", st["text_checks"]),
        ("Rasmli tekshiruvlar", st["image_checks"]),
        ("Texnik xatolar", st["errors"]),
    ]

    y = 180
    for label, value in values:
        dr.rounded_rectangle((70,y,W-70,y+105), radius=18, outline=gray, width=2)
        dr.text((105,y+28), label, font=get_font(28,True), fill=dark)
        dr.text((W-280,y+25), str(value), font=get_font(38,True), fill=green)
        y += 135

    dr.text((70,H-85), "Statistika bot ishga tushganidan beri saqlanadi.", font=get_font(20), fill=gray)

    out = BytesIO()
    out.name = "statistika.jpg"
    img.save(out, "JPEG", quality=91, optimize=True)
    out.seek(0)
    return out

# ============================================================
# TELEGRAM
# ============================================================

async def send_result(message, data):
    # Faqat BITTA natija rasmi. Ikkinchi marta uzun yozuv yuborilmaydi.
    image = await asyncio.to_thread(make_result_image, data)
    await message.reply_photo(
        photo=InputFile(image, filename="esse_natijasi.jpg"),
        caption=f"📊 Natija: {float(data.get('total',0)):g}/24 | 75 ekvivalent: {to_75(data.get('total',0)):g}/75",
    )

async def send_stats(message):
    image = await asyncio.to_thread(make_stats_image)
    await message.reply_photo(
        photo=InputFile(image, filename="statistika.jpg"),
        caption="📊 Statistikangiz",
    )

async def start(update, context):
    context.user_data.clear()
    await update.message.reply_text(
        "Assalomu alaykum! 👋\n\n"
        "Men ONA TILI VA ADABIYOT esse tekshiruvchi botman.\n"
        "Baholash 24 ballik Basirat nizomi bo'yicha amalga oshiriladi.",
        reply_markup=MAIN_KEYBOARD,
    )

async def new_cmd(update, context):
    context.user_data.clear()
    await update.message.reply_text(
        "📝 Yangi tekshiruv.\n\nMavzu/vaziyatni yuboring.",
        reply_markup=MAIN_KEYBOARD,
    )

async def help_cmd(update, context):
    await update.message.reply_text(
        "📚 Foydalanish:\n"
        "1) Mavzu/vaziyatni yuboring.\n"
        "2) Essening o'zini yuboring.\n"
        "3) Natija bitta rasm ko'rinishida keladi.\n\n"
        "12 mezon, jami 24 ball.",
        reply_markup=MAIN_KEYBOARD,
    )

async def handle_photo(update, context):
    if context.user_data.get("stage") != "essay":
        await update.message.reply_text(
            "Avval «✍️ Keyingi esseni tekshirish» tugmasini bosing.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    lock = await get_user_lock(update.effective_user.id)
    if lock.locked():
        await update.message.reply_text("⏳ Oldingi tekshiruv tugamadi. Kutib turing.")
        return

    async with lock:
        topic = context.user_data.get("topic","")
        status = await update.message.reply_text("⏳ Rasm o'qilmoqda va nizom bo'yicha tekshirilmoqda...")
        try:
            file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
            tg_file = await context.bot.get_file(file_id)
            buf = BytesIO()
            await tg_file.download_to_memory(buf)

            result = await evaluate_image(topic, buf.getvalue())
            inc_stat("checks")
            inc_stat("image_checks")
            await send_result(update.message, result)

            context.user_data.clear()
            await status.edit_text("✅ Tekshiruv tugadi.")
        except Exception as e:
            inc_stat("errors")
            logger.exception("Image evaluation error")
            await status.edit_text(f"⚠️ {e}")
            context.user_data.clear()

async def handle_text(update, context):
    text = (update.message.text or "").strip()
    if not text:
        return

    if text == "✍️ Keyingi esseni tekshirish":
        context.user_data.clear()
        context.user_data["stage"] = "topic"
        await update.message.reply_text("📝 Mavzu/vaziyatni yuboring.", reply_markup=MAIN_KEYBOARD)
        return

    if text == "📊 Statistikam":
        await send_stats(update.message)
        return

    if text == "👨‍💼 Admin bilan bog‘lanish":
        await update.message.reply_text(
            f"👨‍💼 Admin bilan bog‘lanish:\n{ADMIN_CONTACT_URL}"
            if ADMIN_CONTACT_URL else "Admin kontakti sozlanmagan.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text == "⚠️ Bot kamchiliklari haqida xabar berish":
        context.user_data["feedback_mode"] = True
        await update.message.reply_text("Kamchilikni yozib yuboring.", reply_markup=MAIN_KEYBOARD)
        return

    if text == "📚 Esse qanday yoziladi?":
        await update.message.reply_text(
            "📚 Esse tuzilishi:\n"
            "• Kirish\n• Asosiy qism\n• Xulosa\n"
            "• Ikki qarash + shaxsiy qarash\n"
            "• Har ikki qarashga dalil\n"
            "• Publitsistik uslub\n"
            "• Kamida 100 so'z\n"
            "• Reja va epigraf qo'yilmaydi",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if context.user_data.get("feedback_mode"):
        logger.warning("USER FEEDBACK %s: %s", update.effective_user.id, text[:2000])
        context.user_data.clear()
        await update.message.reply_text("✅ Xabaringiz qabul qilindi.", reply_markup=MAIN_KEYBOARD)
        return

    stage = context.user_data.get("stage")
    if stage in (None, "topic"):
        context.user_data["topic"] = text
        context.user_data["stage"] = "essay"
        await update.message.reply_text(
            "Mavzu qabul qilindi ✅\n\nEndi essening o'zini yuboring.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if stage != "essay":
        return

    lock = await get_user_lock(update.effective_user.id)
    if lock.locked():
        await update.message.reply_text("⏳ Oldingi tekshiruv tugamadi. Kutib turing.")
        return

    async with lock:
        topic = context.user_data.get("topic","")
        status = await update.message.reply_text("⏳ Esse tekshirilmoqda...")
        try:
            result = await evaluate_text(topic, text)
            inc_stat("checks")
            inc_stat("text_checks")
            await send_result(update.message, result)

            context.user_data.clear()
            await status.edit_text("✅ Tekshiruv tugadi.")
        except Exception as e:
            inc_stat("errors")
            logger.exception("Text evaluation error")
            await status.edit_text(f"⚠️ Tekshiruvda xatolik: {e}")
            context.user_data.clear()

# ============================================================
# RENDER HEALTH + START
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Esse tekshiruvchi bot ishlayapti.")

    def log_message(self, format, *args):
        return

def start_health_server():
    ThreadingHTTPServer(("0.0.0.0", PORT), HealthHandler).serve_forever()

def main():
    threading.Thread(target=start_health_server, daemon=True).start()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", new_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Esse bot ishga tushdi. Model=%s", MODEL)
    app.run_polling(drop_pending_updates=True, close_loop=False)

if __name__ == "__main__":
    main()
