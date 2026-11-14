# -*- coding: utf-8 -*-
"""v127 — «Sertifikatni chiroyli qilish» bot oqimi (hamma uchun ochiq). Karta chizish: cert_card_render.py.
Oqim: cc:start -> rasm -> ism -> daraja -> ball (ixtiyoriy) -> 3D karta. Tugmalar: boshqa rang, aniq fayl, ulashish."""
import io, time, asyncio, logging
from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop
from cert_card_render import render, LEVELS

logger = logging.getLogger(__name__)
_cfg = {'username': lambda: '', 'banned': None}
_ST = {}          # uid -> {'step','img','name','level','score','theme','last','ts'}
_USE = {}         # uid -> [vaqtlar]  (soatiga limit)
_LOCK = None
TTL = 1800


def configure(username_fn=None, is_banned=None):
    if username_fn: _cfg['username'] = username_fn
    _cfg['banned'] = is_banned


# ------------------------------------------------------------------ bot oqimi
def _bot():
    try: return _cfg['username']() or ''
    except Exception: return ''


def _st(uid):
    s = _ST.get(uid)
    if s and time.time() - s['ts'] > TTL: _ST.pop(uid, None); s = None
    if len(_ST) > 300:
        for k in sorted(_ST, key=lambda k: _ST[k]['ts'])[:100]: _ST.pop(k, None)
    return s


def _allow(uid):
    now = time.time(); L = [t for t in _USE.get(uid, []) if now - t < 3600]
    if len(L) >= 12: _USE[uid] = L; return False
    L.append(now); _USE[uid] = L; return True


def _blocked(uid):
    try: return bool(_cfg['banned'] and _cfg['banned'](uid))
    except Exception: return False


CANCEL = InlineKeyboardMarkup([[InlineKeyboardButton('❌ Bekor qilish', callback_data='cc:cancel')]])


async def start_flow(update, context):
    uid = update.effective_user.id
    if _blocked(uid): return
    _ST[uid] = {'step': 'photo', 'ts': time.time(), 'theme': 'emerald'}
    msg = update.message or (update.callback_query.message if update.callback_query else None)
    if update.callback_query: await update.callback_query.answer()
    await msg.reply_text('🎨 <b>Sertifikatni chiroyli qilish</b>\n\nSertifikatingiz rasmini yuboring (aniq, to‘liq ko‘rinadigan bo‘lsin).\nBot undan 3D ko‘rinishdagi natija kartasini yasab beradi — o‘zingiz yoki do‘stlaringiz bilan ulashish uchun.',
                         parse_mode='HTML', reply_markup=CANCEL)


def _stop(fn):
    """Xabar boshqa (esse tekshiruvi kabi) handlerlarga o'tib ketmasligi uchun."""
    async def w(update, context):
        try: await fn(update, context)
        finally: raise ApplicationHandlerStop
    return w


class _Step(filters.MessageFilter):
    def __init__(self, step): super().__init__(); self.step = step
    def filter(self, message):
        try:
            u = message.from_user.id if message.from_user else 0
            s = _st(u); return bool(s and s['step'] == self.step)
        except Exception: return False


async def on_photo(update, context):
    uid = update.effective_user.id; s = _st(uid); m = update.message
    try:
        if m.photo: f = await m.photo[-1].get_file()
        else:
            if (m.document.file_size or 0) > 9_000_000: await m.reply_text('Rasm juda katta (9 MB gacha).'); return
            f = await m.document.get_file()
        raw = bytes(await f.download_as_bytearray())
        im = Image.open(io.BytesIO(raw)); im.verify()
    except Exception:
        await m.reply_text('Rasm o‘qilmadi. JPG yoki PNG yuboring.', reply_markup=CANCEL); return
    s.update(img=raw, step='name', ts=time.time())
    await m.reply_text('✅ Rasm olindi.\n\nIsm familiyangizni yozing (kartada shunday chiqadi). Masalan: <b>Madina Karimova</b>', parse_mode='HTML', reply_markup=CANCEL)


async def on_name(update, context):
    uid = update.effective_user.id; s = _st(uid); name = ' '.join((update.message.text or '').split())[:40]
    if len(name) < 3: await update.message.reply_text('Ism familiyani to‘liq yozing.', reply_markup=CANCEL); return
    s.update(name=name, step='level', ts=time.time())
    kb = [[InlineKeyboardButton(l, callback_data='cc:lv:' + l) for l in LEVELS]]
    await update.message.reply_text('Darajangizni tanlang:', reply_markup=InlineKeyboardMarkup(kb))


async def on_score(update, context):
    uid = update.effective_user.id; s = _st(uid); s['score'] = ' '.join((update.message.text or '').split())[:12]
    await _make(update.message, context, uid)


async def _make(msg, context, uid, theme=None):
    global _LOCK
    s = _st(uid)
    if not s or not s.get('img'): await msg.reply_text('Avval /sertifikat_karta ni bosing.'); return
    if not _allow(uid): await msg.reply_text('Bir soatda juda ko‘p karta yaratdingiz. Birozdan keyin urinib ko‘ring.'); return
    if theme: s['theme'] = theme
    if _LOCK is None: _LOCK = asyncio.Semaphore(1)
    wait = await msg.reply_text('⏳ Karta tayyorlanmoqda…')
    try:
        async with _LOCK:
            png = await asyncio.to_thread(render, s['img'], s['name'], s['level'], s.get('score', ''), s.get('theme', 'emerald'), _bot())
    except Exception:
        logger.exception('cert card render'); await wait.edit_text('⚠️ Karta yaratib bo‘lmadi. Boshqa rasm bilan qayta urinib ko‘ring: /sertifikat_karta'); return
    s.update(last=png, step='done', ts=time.time())
    bot = _bot(); link = f'https://t.me/{bot}' if bot else ''
    kb = [[InlineKeyboardButton('🎨 Boshqa rang', callback_data='cc:th'), InlineKeyboardButton('📥 Aniq fayl', callback_data='cc:file')]]
    if link: kb.append([InlineKeyboardButton('📤 Ulashish', url='https://t.me/share/url?url=%s&text=%s' % (link, 'Sertifikatingizni ham chiroyli qiling:'))])
    kb.append([InlineKeyboardButton('🔁 Yangi karta', callback_data='cc:start')])
    cap = '🎉 Tabriklaymiz, %s!\nKartangiz tayyor.%s' % (s['name'], ('\n\n' + link) if link else '')
    try: await wait.delete()
    except Exception: pass
    await msg.reply_photo(photo=png, caption=cap, reply_markup=InlineKeyboardMarkup(kb))


async def on_cb(update, context):
    q = update.callback_query; uid = q.from_user.id; data = q.data or ''
    if data == 'cc:start': await start_flow(update, context); return
    if data == 'cc:cancel':
        _ST.pop(uid, None); await q.answer('Bekor qilindi'); 
        try: await q.message.edit_text('Bekor qilindi.')
        except Exception: pass
        return
    s = _st(uid)
    if not s: await q.answer('Vaqt tugadi. /sertifikat_karta ni qayta bosing.', show_alert=True); return
    if data.startswith('cc:lv:') and s.get('step') == 'level':
        lv = data[6:]
        if lv not in LEVELS: await q.answer(); return
        s.update(level=lv, step='score', ts=time.time()); await q.answer()
        await q.message.edit_text('Daraja: <b>%s</b>\n\nBallingizni yozing (masalan: <b>72 / 75</b>) yoki o‘tkazib yuboring.' % lv, parse_mode='HTML',
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⏭ Ballsiz davom etish', callback_data='cc:skip')]])); return
    if data == 'cc:skip' and s.get('step') == 'score':
        await q.answer(); s['score'] = ''; await _make(q.message, context, uid); return
    if data == 'cc:th' and s.get('last'):
        await q.answer('Yangi rang tayyorlanmoqda…'); await _make(q.message, context, uid, theme=('midnight' if s.get('theme') != 'midnight' else 'emerald')); return
    if data == 'cc:file' and s.get('last'):
        await q.answer(); await q.message.reply_document(document=io.BytesIO(s['last']), filename='natija_kartasi.png', caption='📥 Aniq (siqilmagan) fayl'); return
    await q.answer()


def register(app):
    app.add_handler(CommandHandler('sertifikat_karta', start_flow))
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.IMAGE) & _Step('photo'), _stop(on_photo)), group=-2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & _Step('name'), _stop(on_name)), group=-2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & _Step('score'), _stop(on_score)), group=-2)
    app.add_handler(CallbackQueryHandler(on_cb, pattern=r'^cc:'))
