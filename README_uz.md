# Esse Tekshiruvchi Telegram Bot

Bu loyiha O'zbekiston ona tili va adabiyot fanidan esse baholash mezonlari asosida
AI yordamida esse tekshiradi.

## Bot nimalarni qiladi?

- Mavzu/vaziyatni qabul qiladi.
- Esseni qabul qiladi.
- 24 ballik tizimda 12 mezon bo'yicha baholaydi.
- Har bir mezon uchun ball va qisqa izoh beradi.
- Imlo, punktuatsiya, uslub, mantiqiylik va leksik jihatlarni tahlil qiladi.
- 100 so'zdan kam esse kabi maxsus holatlarni tekshiradi.
- Yakunda yaxshilash bo'yicha tavsiyalar beradi.

## Sizga kerak bo'ladigan 2 ta kalit

1. Telegram Bot Token — @BotFather orqali olinadi.
2. OpenAI API Key — OpenAI API platformasidan olinadi.

## Ishga tushirish

### Windows

1. Python 3.11 yoki undan yangiroq versiyani o'rnating.
2. Shu papkani oching.
3. Terminal/CMD oching.
4. Quyidagini yozing:

    pip install -r requirements.txt

5. `.env.example` faylidan nusxa olib `.env` deb nomlang.
6. `.env` ichiga tokenlarni kiriting:

    TELEGRAM_BOT_TOKEN=...
    OPENAI_API_KEY=...
    OPENAI_MODEL=gpt-5.6-luna

7. Ishga tushiring:

    python bot.py

Terminalda "Bot ishga tushdi..." chiqsa, Telegramdan botingizga `/start` yuboring.

### Muhim

API kalitlarni hech kimga yubormang va GitHubga joylamang.

## Baholash manbasi

Loyiha foydalanuvchi bergan ikki PDFdagi 24 ballik esse mezonlariga tayangan.
Asosiy mezon sifatida batafsil "Esse baholash nizomi - Basirat" hujjati ishlatilgan.
Ikkinchi PDFdagi 24 ballik umumiy tuzilma va esse qismlariga oid talablar ham promptga kiritilgan.

## Cheklov

Bot AI ekspert yordamchisi hisoblanadi. U rasmiy davlat ekspertining yakuniy bahosini
almashtirmaydi. Ayniqsa internetdan ko'chirilganlikni tashqi manbalar bilan tekshirish
ushbu oddiy versiyada avtomatik tasdiqlanmaydi.

## Eng oson keyingi qadam

Agar Pythonni bilmasangiz, bu papkani boshqa odamga berib, faqat Telegram tokeni va
OpenAI API kalitini `.env` ga kiritib ishga tushirtirishingiz mumkin.
