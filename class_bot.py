# -*- coding: utf-8 -*-
"""v109: sinf nazorati — Telegram qismi (guruh buyruqlari, tugmalar, ota-ona kirishi, xabar yuboruvchi sikl).
Mantiq class_ctl.py da. Bu fayl bo'lmasa yoki xato bersa bot baribir ishlaydi (bot-1-1.py da try/except)."""
import json
import logging
import threading
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (ApplicationHandlerStop, CallbackQueryHandler, ChatMemberHandler, CommandHandler, MessageHandler, filters)

import class_ctl as cc

log = logging.getLogger('class_bot')
_cfg = {'admin_id': 0, 'bot_username': lambda: '', 'webapp_url': lambda: '', 'send': None}
_warned = {}          # (chat, user) -> vaqt: ulanmaganlarga eslatma shovqini cheklovi
ANON_ADMIN_ID = 1087968824


def configure(admin_id, bot_username, webapp_url, send):
    _cfg.update(admin_id=int(admin_id), bot_username=bot_username, webapp_url=webapp_url, send=send)


def _uname(): return (_cfg['bot_username']() or '').lstrip('@')
def _is_admin(uid): return uid is not None and int(uid) == _cfg['admin_id']
def _can_teach(uid): return bool(uid) and (_is_admin(uid) or cc.is_teacher_user(uid))
def _link(cid): return f"https://t.me/{_uname()}?start=c_{cid}" if _uname() else ''


def _app_url(go='teacher'):
    base = _cfg['webapp_url']() or ''
    if not base: return ''
    return base + ('&' if '?' in base else '?') + 'go=' + go


async def _reply(update, text, **kw):
    try: return await update.effective_message.reply_text(text, **kw)
    except Exception: log.exception('reply'); return None


def _args(update):
    p = (update.effective_message.text or '').split(None, 1)
    return p[1].strip() if len(p) > 1 else ''


def _kb(rows): return InlineKeyboardMarkup([[InlineKeyboardButton(**b) for b in r] for r in rows])


def _manager(uid, k): return bool(k) and (cc.can_manage(k, uid, _is_admin(uid)))


# ------------------------------------------------------------------ guruhga qo'shilish / ulash
async def on_my_chat_member(update, context):
    ev = update.my_chat_member
    if not ev or ev.chat.type not in ('group', 'supergroup'): return
    new, old = ev.new_chat_member.status, ev.old_chat_member.status
    if new in ('left', 'kicked'):
        cc.class_unlink_chat(ev.chat.id); return
    if new in ('member', 'administrator') and old in ('left', 'kicked'):
        await context.bot.send_message(ev.chat.id,
            "👋 Salom! Men sinf nazorati yordamchisiman: vazifa, davomat va test qatnashuvini kuzataman, ota-onalarga xabar beraman.\n\n"
            "Ustoz, guruhni sinfga ulash uchun /guruh_ulash yozing.\n"
            "💡 Meni guruh ADMINI qiling — shunda o‘quvchilar javoblarini ko‘ra olaman.")


async def cmd_link(update, context):
    u = update.effective_user; chat = update.effective_chat
    if chat.type not in ('group', 'supergroup'): await _reply(update, 'Bu buyruq guruh ichida ishlaydi.'); return
    if u.id == ANON_ADMIN_ID: await _reply(update, '⚠️ «Anonim admin» rejimida ustozni aniqlab bo‘lmaydi. Anonimlikni o‘chirib qayta yozing.'); return
    if not _can_teach(u.id): await _reply(update, 'Guruhni sinfga faqat ustoz ulay oladi. Ustoz bo‘lish: admin bilan bog‘laning.'); return
    mine = [k for k in cc.teacher_classes(u.id, False) if k['teacher_id'] == u.id]
    rows = [[{'text': f"{k['name']}" + (' ✅' if k['chat_id'] == chat.id else ''), 'callback_data': f"cc_gl:{k['id']}"}] for k in mine[:20]]
    rows.append([{'text': '➕ Yangi sinf (guruh nomi bilan)', 'callback_data': 'cc_gn'}])
    await _reply(update, 'Guruhni qaysi sinfga ulaymiz?', reply_markup=_kb(rows))


async def _linked_ok(context, chat, k):
    kb = _kb([[{'text': '👤 Men shu sinf o‘quvchisiman', 'url': _link(k['id'])}]]) if _uname() else None
    await context.bot.send_message(chat.id,
        f"✅ Guruh «{k['name']}» sinfiga ulandi.\n\n"
        "👥 O‘quvchilar: pastdagi tugma orqali ro‘yxatdagi ismingizni tanlang.\n"
        "👩‍🏫 Ustoz buyruqlari:\n/vazifa [muddat] matn — vazifa berish\n/davomat [daqiqa] [kodsiz] — davomat\n/sinftest KOD [soat] — testni biriktirish\n/holat — sinf holati\n"
        "👥 Hamma uchun: /keldim KOD • /reyting • /vazifalar", reply_markup=kb)


# ------------------------------------------------------------------ vazifa
async def cmd_vazifa(update, context):
    chat = update.effective_chat; u = update.effective_user; k = cc.class_by_chat(chat.id)
    if not k: await _reply(update, 'Avval guruhni sinfga ulang: /guruh_ulash'); return
    if not _manager(u.id, k): await _reply(update, 'Vazifani faqat ustoz bera oladi.'); return
    raw = _args(update)
    if not raw:
        await _reply(update, "Namuna:\n/vazifa ertaga 18:00 5-mashq, 34-bet\n/vazifa 24s Insho yozing\n/vazifa 15.11 20:00 Sinov\nMuddat yozilmasa — ertaga 20:00."); return
    due, rest = cc.parse_due(raw)
    if not rest: await _reply(update, 'Vazifa matnini ham yozing.'); return
    title = rest.split('\n')[0][:80]
    hid = cc.hw_create(k['id'], u.id, title, rest, due)
    h = cc.hw_get(hid)
    m = await context.bot.send_message(chat.id,
        f"📚 YANGI VAZIFA\n\n{rest}\n\n⏰ Muddat: {cc.fmt(h['due_at'])}\n\n"
        "Topshirish: ishingizni (rasm / fayl / matn) shu xabarga REPLY qilib yuboring yoki pastdagi ✅ tugmani bosing.",
        reply_markup=_kb([[{'text': '✅ Topshirdim', 'callback_data': f'cc_hd:{hid}'}, {'text': '📊 Holat', 'callback_data': f'cc_hs:{hid}'}]]))
    cc.hw_set_msg(hid, chat.id, m.message_id)


async def cmd_vazifalar(update, context):
    k = cc.class_by_chat(update.effective_chat.id)
    if not k: return
    with cc.nc.db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM cc_hw WHERE class_id=? ORDER BY id DESC LIMIT 5", (k['id'],))]
    if not rows: await _reply(update, 'Hozircha vazifa yo‘q.'); return
    L = ['📚 Oxirgi vazifalar:']
    for h in rows:
        d, t = cc.hw_counts(h['id']); L.append(f"• {h['title']} — {cc.fmt(h['due_at'])} ({d}/{t} topshirdi)")
    await _reply(update, '\n'.join(L))


async def _link_prompt(context, chat_id, user_id, k):
    now = time.time(); key = (chat_id, user_id)
    if now - _warned.get(key, 0) < 600 or not _uname(): return
    _warned[key] = now
    if len(_warned) > 5000: _warned.clear()
    await context.bot.send_message(chat_id, 'Siz sinf ro‘yxatiga ulanmagansiz. Tugmani bosib ismingizni tanlang:',
                                   reply_markup=_kb([[{'text': '👤 Ro‘yxatga ulanish', 'url': _link(k['id'])}]]))


def _my_roster(uid, class_id):
    for r in cc.student_rosters(uid):
        if r['class_id'] == class_id: return r
    return None


async def on_group_message(update, context):
    """Bog'langan guruhdagi oddiy xabarlar: vazifa xabariga reply qilingan javobni qayd etadi.
    Bog'langan guruhda eski handlerlar (esse tekshiruvi va h.k.) ishlamasligi uchun to'xtatiladi."""
    m = update.effective_message; chat = update.effective_chat
    if not m or not chat: return
    k = cc.class_by_chat(chat.id)
    if not k: return
    u = update.effective_user
    try:
        rp = m.reply_to_message
        if rp and u and not u.is_bot:
            h = cc.hw_by_msg(chat.id, rp.message_id)
            if h:
                r = _my_roster(u.id, k['id'])
                if r:
                    if cc.hw_submit(h['id'], r['id'], 'reply') == 'new':
                        await m.reply_text(f"✅ {r['full_name']}, vazifangiz qabul qilindi.")
                elif not _manager(u.id, k): await _link_prompt(context, chat.id, u.id, k)
    except Exception: log.exception('group message')
    raise ApplicationHandlerStop


# ------------------------------------------------------------------ davomat
async def cmd_davomat(update, context):
    chat = update.effective_chat; u = update.effective_user; k = cc.class_by_chat(chat.id)
    if not k: await _reply(update, 'Avval guruhni sinfga ulang: /guruh_ulash'); return
    if not _manager(u.id, k): await _reply(update, 'Davomatni faqat ustoz ochadi.'); return
    minutes, mode, title = 20, 'code', []
    for a in _args(update).split():
        if a.isdigit(): minutes = int(a)
        elif a.lower() in ('kodsiz', 'tugma'): mode = 'button'
        else: title.append(a)
    s = cc.att_start(k['id'], minutes, ' '.join(title), mode)
    rows = []
    if s['mode'] == 'button': rows.append([{'text': '🙋 Keldim', 'callback_data': f"cc_ak:{s['id']}"}])
    rows.append([{'text': '🏁 Yakunlash (ustoz)', 'callback_data': f"cc_ae:{s['id']}"}])
    how = "Belgilanish: darsda ustoz e’lon qilgan KOD bilan /keldim KOD yozing." if s['mode'] == 'code' else "Belgilanish uchun «🙋 Keldim» tugmasini bosing."
    m = await context.bot.send_message(chat.id, f"🕘 DAVOMAT — {s['title']}\n\n{how}\n⏳ {minutes} daqiqa ochiq. Keyin belgilanmaganlar «kelmadi» deb yoziladi.", reply_markup=_kb(rows))
    cc.att_set_msg(s['id'], chat.id, m.message_id)
    if s['mode'] == 'code':
        try: await context.bot.send_message(u.id, f"🔑 «{k['name']}» davomat kodi: {s['code']}\nUni darsda o‘quvchilarga e’lon qiling (guruhga yozmang).")
        except Exception: await context.bot.send_message(chat.id, '⚠️ Ustoz, kodni ko‘rish uchun botga shaxsiy chatda /start bosing yoki Mini App → Ustoz paneliga kiring.')


async def cmd_keldim(update, context):
    u = update.effective_user; chat = update.effective_chat; m = update.effective_message
    ok, text = cc.att_self(u.id, _args(update))
    if chat.type in ('group', 'supergroup'):
        try: await m.delete()   # kod boshqalarga ko'rinmasin (bot admin bo'lsa)
        except Exception: pass
        if ok: await context.bot.send_message(chat.id, text)
        else: await context.bot.send_message(chat.id, f"{u.first_name or ''}: {text}")
    else:
        await _reply(update, text)


# ------------------------------------------------------------------ test, reyting, holat
async def cmd_sinftest(update, context):
    chat = update.effective_chat; u = update.effective_user; k = cc.class_by_chat(chat.id)
    if not k: await _reply(update, 'Avval guruhni sinfga ulang: /guruh_ulash'); return
    if not _manager(u.id, k): await _reply(update, 'Testni faqat ustoz biriktiradi.'); return
    a = _args(update).split()
    if not a: await _reply(update, 'Namuna: /sinftest ABC123 48   (kod va muddat — soatda, standart 48)'); return
    code = a[0].upper(); hours = int(a[1]) if len(a) > 1 and a[1].isdigit() else 48
    t = None
    for kind in ('ms', 'simple'):
        if cc._test_meta(kind, code): t = (kind, cc._test_meta(kind, code)); break
    if not t: await _reply(update, 'Bunday kodli test topilmadi.'); return
    tid = cc.test_assign(k['id'], t[0], code, hours); row = cc.test_get(tid)
    kb = _kb([[{'text': '📝 Testni boshlash', 'url': f"https://t.me/{_uname()}?start=test_{code}"}]]) if _uname() else None
    await context.bot.send_message(chat.id, f"📝 TEST: {t[1]['title'] or code}\nKod: {code}\n⏰ Muddat: {cc.fmt(row['due_at'])}\n\nMuddatgacha ishlamaganlar haqida ustoz va ota-onalarga xabar beriladi.", reply_markup=kb)


async def cmd_reyting(update, context):
    k = cc.class_by_chat(update.effective_chat.id)
    if k: await _reply(update, cc.rating_text(k['id']))


async def cmd_holat(update, context):
    k = cc.class_by_chat(update.effective_chat.id)
    if not k: return
    if not _manager(update.effective_user.id, k): await _reply(update, 'Faqat ustoz uchun.'); return
    await _reply(update, cc.class_status_text(k['id']))


# ------------------------------------------------------------------ tugmalar
async def on_callback(update, context):
    q = update.callback_query; d = q.data or ''; u = q.from_user
    try:
        if d.startswith('cc_hd:'):
            h = cc.hw_get(int(d[6:])); k = cc.class_get(h['class_id']) if h else None
            if not k: await q.answer('Vazifa topilmadi.', show_alert=True); return
            r = _my_roster(u.id, k['id'])
            if not r:
                await q.answer('Siz ro‘yxatga ulanmagansiz. Pastda chiqadigan tugmadan ulaning.', show_alert=True)
                if q.message: await _link_prompt(context, q.message.chat.id, u.id, k)
                return
            res = cc.hw_submit(h['id'], r['id'], 'button')
            await q.answer('✅ Qabul qilindi!' if res == 'new' else 'Siz allaqachon topshirgansiz.', show_alert=False)
        elif d.startswith('cc_hs:'):
            h = cc.hw_get(int(d[6:])); k = cc.class_get(h['class_id']) if h else None
            if not k: await q.answer('Topilmadi.', show_alert=True); return
            done, tot = cc.hw_counts(h['id'])
            await q.answer(f'✅ Topshirdi: {done}/{tot}', show_alert=True)
            if _manager(u.id, k):
                det = cc.hw_detail(h['id']); miss = [r['name'] for r in det['rows'] if r['status'] == 'miss']
                try: await context.bot.send_message(u.id, f"📚 «{h['title']}» — topshirmaganlar ({len(miss)}):\n" + (', '.join(miss) or '—'))
                except Exception: pass
        elif d.startswith('cc_ak:'):
            s = cc.att_get(int(d[6:])); k = cc.class_get(s['class_id']) if s else None
            if not k: await q.answer('Topilmadi.', show_alert=True); return
            ok, text = cc.att_self(u.id)
            if not ok and 'ulanmagansiz' in text and q.message: await _link_prompt(context, q.message.chat.id, u.id, k)
            await q.answer(text[:190], show_alert=not ok)
        elif d.startswith('cc_ae:'):
            s = cc.att_get(int(d[6:])); k = cc.class_get(s['class_id']) if s else None
            if not k or not _manager(u.id, k): await q.answer('Faqat ustoz.', show_alert=True); return
            res = cc.att_finalize(s['id'])
            await q.answer('Yakunlandi.' if res else 'Allaqachon yakunlangan.')
            try: await q.edit_message_text(f"🏁 DAVOMAT yakunlandi — {s['title']}" + (f"\n✅ {res['present']} • ⏰ {res['late']} • ❌ {res['absent']}" if res else ''))
            except Exception: pass
        elif d.startswith('cc_np:'):
            _, kind, ref = d.split(':'); ref = int(ref)
            if kind == 'att': s = cc.att_get(ref); cid = s['class_id'] if s else 0
            elif kind == 'hw': s = cc.hw_get(ref); cid = s['class_id'] if s else 0
            else: s = cc.test_get(ref); cid = s['class_id'] if s else 0
            k = cc.class_get(cid)
            if not k or not _manager(u.id, k): await q.answer('Faqat ustoz.', show_alert=True); return
            res = {'att': cc.att_notify, 'hw': cc.hw_notify, 'tst': cc.test_notify}[kind](ref)
            await q.answer(f"Yuborildi: {res['sent']} ta", show_alert=True)
            try: await q.edit_message_reply_markup(reply_markup=None)
            except Exception: pass
            if res['no_parent']: await context.bot.send_message(u.id, '⚠️ Ota-onasi ulanmagan: ' + ', '.join(res['no_parent'][:20]))
        elif d.startswith('cc_ex:'):
            _, sid, rid = d.split(':'); s = cc.att_get(int(sid)); k = cc.class_get(s['class_id']) if s else None
            if not k or not _manager(u.id, k): await q.answer('Faqat ustoz.', show_alert=True); return
            cc.att_mark(int(sid), int(rid), 'e', 'teacher'); await q.answer('Sababli deb belgilandi.')
            try: await q.edit_message_reply_markup(reply_markup=None)
            except Exception: pass
        elif d.startswith('cc_gl:') or d == 'cc_gn':
            chat = q.message.chat if q.message else None
            if not chat or chat.type not in ('group', 'supergroup') or not _can_teach(u.id): await q.answer('Faqat ustoz, guruh ichida.', show_alert=True); return
            if d == 'cc_gn':
                cid = cc.class_create(u.id, chat.title or 'Yangi sinf', '', chat.id, chat.title or '')
            else:
                cid = int(d[6:]); k0 = cc.class_get(cid)
                if not k0 or not (k0['teacher_id'] == u.id or _is_admin(u.id)): await q.answer('Bu sinf sizniki emas.', show_alert=True); return
                cc.class_link_chat(cid, chat.id, chat.title or '')
            await q.answer('Ulandi!')
            try: await q.edit_message_text('✅ Ulandi.')
            except Exception: pass
            await _linked_ok(context, chat, cc.class_get(cid))
        elif d.startswith('cc_jn:'):
            cid = int(d.split(':')[1]); ok, msg, rid = cc.join_self(cid, u.id, getattr(u, 'full_name', None) or u.first_name or '')
            await q.answer('✅ Qo‘shildingiz!' if ok else msg[:190], show_alert=not ok)
            if ok:
                k = cc.class_get(cid)
                try: await q.edit_message_text(f"✅ Siz «{k['name']}» sinfiga «{msg}» sifatida qo‘shildingiz.\nVazifa va testlaringiz endi ustozga ko‘rinadi. Ismingiz noto‘g‘ri bo‘lsa, ustozga ayting.")
                except Exception: pass
                if k: cc.tell_teacher(k, f"👤 {msg} sinfga qo‘shildi (@{u.username or u.id}).", None, 'link')
        elif d.startswith('cc_ln:'):
            _, cid, rid = d.split(':'); ok, msg = cc.link_student(int(rid), u.id)
            await q.answer('✅ Ulandi!' if ok else msg[:190], show_alert=not ok)
            if ok:
                k = cc.class_get(int(cid))
                try: await q.edit_message_text(f"✅ Siz «{k['name']}» sinfida «{msg}» sifatida ro‘yxatga ulandingiz.\nEndi vazifa, davomat va testlaringiz ustozga ko‘rinadi.")
                except Exception: pass
                if k: cc.tell_teacher(k, f"👤 {msg} Telegramga ulandi (@{u.username or u.id}).", None, 'link')
        else:
            await q.answer()
    except ApplicationHandlerStop: raise
    except Exception:
        log.exception('cc callback %s', d)
        try: await q.answer('Xatolik. Qayta urinib ko‘ring.')
        except Exception: pass


# ------------------------------------------------------------------ shaxsiy chat: o'quvchi ulanishi, ota-ona
async def student_link_start(update, context, cid):
    """/start c_<sinf_id> havolasi: o'quvchi ro'yxatdan ismini tanlaydi yoki bir bosishda o'zi qo'shiladi (ro'yxat shart emas)."""
    k = cc.class_get(cid); u = update.effective_user
    if not k: await _reply(update, 'Bu sinf havolasi eskirgan.'); return
    mine = _my_roster(u.id, k['id'])
    if mine: await _reply(update, f"Siz «{k['name']}» sinfida «{mine['full_name']}» sifatida ulangansiz ✅"); return
    free = cc.roster_unlinked(k['id'])
    rows = [[{'text': r['full_name'][:60], 'callback_data': f"cc_ln:{k['id']}:{r['id']}"}] for r in free[:40]]
    me = (getattr(u, 'full_name', None) or u.first_name or '').strip()[:40]
    if me: rows.append([{'text': f"✅ Qo‘shilish: «{me}»", 'callback_data': f"cc_jn:{k['id']}"}])
    head = f"👩‍🏫 «{k['name']}» sinfiga xush kelibsiz!\n"
    await _reply(update, head + ('Ro‘yxatdan ismingizni tanlang (faqat o‘zingizniki!) yoki pastdagi tugma bilan qo‘shiling:' if free else 'Sinfga qo‘shilish uchun pastdagi tugmani bosing:'), reply_markup=_kb(rows))


async def parent_link_start(update, context, arg):
    """/start p_<o'quvchi_id>_<token>: ota-ona havola orqali farzandiga ulanadi (login/parol kerak emas)."""
    u = update.effective_user
    try: _, rid, tok = str(arg).split('_', 2); rid = int(rid)
    except Exception: await _reply(update, 'Havola noto‘g‘ri. Ustozdan yangisini so‘rang.'); return
    ok, msg, rid = cc.parent_bind(u.id, rid, tok)
    if not ok: await _reply(update, '❌ ' + msg); return
    url = _app_url('teacher')
    kb = _kb([[{'text': '📊 Farzandim natijalarini ochish', 'web_app': WebAppInfo(url=url)}]]) if url else None
    await _reply(update, f"✅ Siz «{msg}» ning ota-onasi sifatida ulandingiz.\nEndi davomat, vazifa va test natijalari shu yerga keladi.\n/farzand — hozirgi holat", reply_markup=kb)
    try:
        r = cc.roster_get(rid); k = cc.class_get(r['class_id']) if r else None
        if k: cc.tell_teacher(k, f"👪 {msg} ning ota-onasi ulandi (@{u.username or u.id}).", None, 'plink')
    except Exception: log.exception('plink notify')


async def cmd_ota_ona(update, context):
    url = _app_url('teacher')
    kb = _kb([[{'text': '👪 Ota-ona bo‘limini ochish', 'web_app': WebAppInfo(url=url)}]]) if url else None
    await _reply(update, "👪 OTA-ONA BO‘LIMI\n\nUstoz bergan login va parol bilan kiring:\n• Mini Appda: Ustoz paneli → «Ota-ona kirishi»\n• yoki shu yerda: /kirish login parol\n\nChiqish: /chiqish • Farzand holati: /farzand", reply_markup=kb)


async def cmd_kirish(update, context):
    if update.effective_chat.type != 'private': return
    a = _args(update).split()
    try: await update.effective_message.delete()   # parol chatda qolmasin
    except Exception: pass
    if len(a) < 2: await context.bot.send_message(update.effective_chat.id, 'Namuna: /kirish login parol'); return
    ok, msg, rid = cc.parent_login(update.effective_user.id, a[0], a[1])
    if ok: await context.bot.send_message(update.effective_chat.id, f"✅ Kirdingiz. Farzandingiz: {msg}\nEndi davomat, vazifa va test xabarlari shu yerga keladi.\n/farzand — hozirgi holat", reply_markup=_kb([[{'text': '👪 Batafsil', 'web_app': WebAppInfo(url=_app_url('teacher'))}]]) if _app_url('teacher') else None)
    else: await context.bot.send_message(update.effective_chat.id, '❌ ' + msg)


async def cmd_chiqish(update, context):
    cc.parent_logout(update.effective_user.id); await _reply(update, 'Ota-ona hisobidan chiqdingiz.')


async def cmd_farzand(update, context):
    kids = cc.parent_children(update.effective_user.id)
    if not kids: await _reply(update, 'Siz ota-ona sifatida kirmagansiz. /ota_ona'); return
    for kd in kids: await _reply(update, cc.parent_weekly_text(kd['rid']) or kd['name'])


# ------------------------------------------------------------------ yuboruvchi sikl
def _send_row(row):
    payload = {'chat_id': row['chat_id'], 'text': row['text']}
    if row.get('markup_json'): payload['reply_markup'] = json.loads(row['markup_json'])
    ok, code = _cfg['send']('sendMessage', payload)
    return ok, code


def flush_outbox(limit=30):
    n = 0
    for row in cc.outbox_due(limit):
        try:
            ok, code = _send_row(row)
            if ok: cc.outbox_done(row['id'], True)
            elif code in (400, 403): cc.outbox_done(row['id'], False, 'blocked')
            else: cc.outbox_done(row['id'], False, 'http%s' % code)
        except Exception:
            log.exception('outbox'); cc.outbox_done(row['id'], False, 'exc')
        n += 1; time.sleep(0.05)
    return n


def _loop():
    time.sleep(20)
    while True:
        try: cc.tick()
        except Exception: log.exception('class tick')
        try: flush_outbox()
        except Exception: log.exception('class flush')
        time.sleep(30)


def start_loop():
    if not _cfg['send']: log.warning('class_bot: send berilmagan — xabar sikli ishga tushmadi'); return
    threading.Thread(target=_loop, daemon=True, name='class_ctl').start()


def register(app):
    cc.init()
    G = getattr(filters, 'ChatType', None)
    grp = G.GROUPS if G is not None else None
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER), group=-6)
    for name, fn in (('guruh_ulash', cmd_link), ('vazifa', cmd_vazifa), ('vazifalar', cmd_vazifalar), ('davomat', cmd_davomat),
                     ('sinftest', cmd_sinftest), ('reyting', cmd_reyting), ('holat', cmd_holat)):
        app.add_handler(CommandHandler(name, fn, filters=grp) if grp is not None else CommandHandler(name, fn), group=-6)
    app.add_handler(CommandHandler('keldim', cmd_keldim), group=-6)
    app.add_handler(CommandHandler('ota_ona', cmd_ota_ona), group=-6)
    app.add_handler(CommandHandler('kirish', cmd_kirish), group=-6)
    app.add_handler(CommandHandler('chiqish', cmd_chiqish), group=-6)
    app.add_handler(CommandHandler('farzand', cmd_farzand), group=-6)
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r'^cc_'), group=-6)
    if grp is not None:
        app.add_handler(MessageHandler(grp & ~filters.COMMAND, on_group_message), group=-6)
