# -*- coding: utf-8 -*-
"""v123 — «Yutuqlar zinasi»: har kuni olishga undaydigan yutuq kartalarini AVTOMATIK berish.

  Kun qahramoni      — kunlik reytingda 1-o‘rin (mini_extra.award_loop → on_award)
  Seriya olovi       — kunlik seriya 7 / 30 / 100 / 365 kunga yetganda (after_submit → on_streak)
  Shon-sharaf devori — haftalik reytingning TOP-5 (har dushanba, on_award)
  Sertifikat bilimdoni — sertifikatlar soni 3 / 10 / 25 ga yetganda (mini_extra.ON_NEW_CERT)
  Mavsum afsonasi    — mavsum (Qish/Bahor/Yoz/Kuz) tugaganda reytingda 1-o‘rin (check_season, har 30 daqiqada)

Hammasi bir martalik (achv_log jadvali). Ball manbai — mavjud reyting (mini_extra.leaderboard: admin testlari + savollar).
Maxfiylik: foydalanuvchi /yutuq_yashirin bilan ismini kartada yashirishi mumkin; kanalga e’lon admin /yutuq_kanal bilan yoqiladi (standart: o‘chiq).
Admin buyruqlari: /yutuq  /yutuq_namuna  /yutuq_kanal on|off.  Foydalanuvchi: /yutuq_yashirin.
"""
import asyncio, io, logging, secrets, threading, time
from datetime import datetime, timedelta

from national_certificate import db, now, setting, set_setting
import mini_extra as mx
import achv_cards as ac

log = logging.getLogger("achievements")
_CFG = {"admin_id": None, "token": None, "channel": None, "bot_username": "", "webapp_url": ""}
STREAK_MARKS = (7, 30, 100, 365)
CERT_LEVELS = (3, 10, 25)
SEASONS = {12: "Qish", 3: "Bahor", 6: "Yoz", 9: "Kuz"}


def configure(admin_id, token, channel=None, bot_username="", webapp_url=""):
    _CFG.update(admin_id=admin_id, token=token, channel=channel, bot_username=bot_username or "", webapp_url=webapp_url or "")


def init():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS achv_log(
            kind TEXT NOT NULL, period_key TEXT NOT NULL, user_id INTEGER NOT NULL, rank INTEGER DEFAULT 0,
            cert_code TEXT, created_at TEXT, PRIMARY KEY(kind, period_key, user_id))""")
        c.commit()


def _once(kind, key, uid, rank=0, code=None):
    """True — birinchi marta belgilandi (bir yutuq bir marta beriladi)."""
    with db() as c:
        cur = c.execute("INSERT OR IGNORE INTO achv_log(kind,period_key,user_id,rank,cert_code,created_at) VALUES(?,?,?,?,?,?)", (kind, str(key), int(uid), rank, code, now()))
        c.commit()
        return cur.rowcount == 1


def _marked(kind, key):
    with db() as c:
        return c.execute("SELECT 1 FROM achv_log WHERE kind=? AND period_key=? LIMIT 1", (kind, str(key))).fetchone() is not None


def count_for(uid, kind=None):
    with db() as c:
        if kind:
            return c.execute("SELECT COUNT(*) FROM achv_log WHERE user_id=? AND kind=?", (int(uid), kind)).fetchone()[0]
        return c.execute("SELECT COUNT(*) FROM achv_log WHERE user_id=?", (int(uid),)).fetchone()[0]


# ------------------------------------------------------------------ maxfiylik / sozlamalar
def is_hidden(uid):
    return setting("achv_hide:%d" % int(uid), "") == "1"


def set_hidden(uid, on):
    set_setting("achv_hide:%d" % int(uid), "1" if on else "")


def shown_name(uid):
    return "Yashirin o‘quvchi" if is_hidden(uid) else mx.user_name(int(uid))


def channel_on():
    return setting("achv_channel", "") == "1"


def set_channel(on):
    set_setting("achv_channel", "1" if on else "")


def _code():
    return "YT-" + secrets.token_hex(5).upper()


# ------------------------------------------------------------------ yuborish
def _markup():
    rows = []
    if _CFG["webapp_url"]:
        rows.append([{"text": "🚀 Mini ilovani ochish", "web_app": {"url": _CFG["webapp_url"]}}])
    if _CFG["bot_username"]:
        rows.append([{"text": "📤 Do‘stlarga ulashish", "url": "https://t.me/share/url?url=https://t.me/%s&text=%s" % (_CFG["bot_username"], "Men Esse Akademiyasida yutuq qo‘lga kiritdim! Sen ham sinab ko‘r 👇")}])
    return {"inline_keyboard": rows} if rows else None


def send_card(uid, png, caption):
    try:
        mx.send_photo(_CFG["token"], int(uid), png, caption, reply_markup=_markup())
        return True
    except Exception as e:
        log.warning("achv send %s: %s", uid, e)
        return False


def post_channel(png, caption):
    if not (channel_on() and _CFG.get("channel")):
        return False
    try:
        mx.send_photo(_CFG["token"], _CFG["channel"], png, caption)
        return True
    except Exception as e:
        log.warning("achv channel: %s", e)
        return False


def _admin_copy(png, caption):
    if _CFG.get("admin_id"):
        try:
            mx.send_photo(_CFG["token"], _CFG["admin_id"], png, caption)
        except Exception as e:
            log.warning("achv admin copy: %s", e)


# ------------------------------------------------------------------ kartalarni tuzish
def _gn(x):
    return ("%g" % x).replace(".", ",")


def build_hero(uid, pts, n, day_label, streak=0):
    data = {"name": shown_name(uid), "desc": f"{day_label} kuni {_gn(pts)} ball to‘plab, eng faol o‘quvchi bo‘ldi",
            "stats": [("KUNLIK BALL", _gn(pts)), ("TESTLAR", f"{n} ta"), ("SERIYA", f"{streak} kun")], "date": day_label}
    return ac.render("hero", data, _code())


def build_streak(uid, cur, best):
    nxt = next((m for m in STREAK_MARKS if m > cur), None)
    data = {"name": shown_name(uid), "desc": f"{cur} kun ketma-ket har kuni mashq qildi — odat shakllandi", "days": cur,
            "stats": [("SERIYA", f"{cur} kun"), ("REKORD", f"{max(best, cur)} kun"), ("KEYINGISI", f"{nxt} kun" if nxt else "—")],
            "date": datetime.now(mx.TZ).strftime("%d.%m.%Y")}
    return ac.render("streak", data, _code())


def build_wall(top, period_label, total):
    rows = [(shown_name(r["user_id"]), r["pts"]) for r in top[:5]]
    while len(rows) < 5:
        rows.append(("—", 0))
    data = {"period": f"Hafta · {period_label}", "top": rows, "date": period_label,
            "chips": [("HAFTA SARDORI", f"{_gn(top[0]['pts'])} ball"), ("ISHTIROKCHI", f"{total} kishi"), ("KEYINGI HAFTA", "dushanba")]}
    return ac.render("wall", data, _code())


def cert_level(count):
    lv = 0
    for i, t in enumerate(CERT_LEVELS, 1):
        if count >= t:
            lv = i
    return lv


def build_bilimdon(uid, count):
    lv = cert_level(count)
    nxt = next((t for t in CERT_LEVELS if t > count), None)
    desc = (f"{count} ta sertifikat to‘pladi. Keyingi daraja uchun yana {nxt - count} ta kerak" if nxt else f"{count} ta sertifikat to‘pladi — eng yuqori darajaga yetdi")
    data = {"name": shown_name(uid), "desc": desc, "count": count, "stats": [("SERTIFIKAT", f"{count} ta"), ("DARAJA", f"{lv}-daraja"), ("KEYINGISI", f"{nxt} ta" if nxt else "—")],
            "date": datetime.now(mx.TZ).strftime("%d.%m.%Y")}
    return ac.render("bilimdon", data, _code())


def build_legend(uid, pts, total, season_name):
    pct = ("%.1f" % (100.0 / total)).replace(".", ",") if total else "—"
    data = {"name": shown_name(uid), "desc": f"{season_name}: eng ko‘p ball to‘plab, reytingda 1-o‘rinni egalladi",
            "stats": [("MAVSUM BALLI", _gn(pts)), ("O‘RIN", "1"), ("NOYOBLIK", f"{pct}%")], "date": season_name}
    return ac.render("legend", data, _code())


# ------------------------------------------------------------------ triggerlar
def _bounds_prev(kind):
    """award_due bilan bir xil: tugagan oxirgi davr (UTC iso, kalit, nom)."""
    cur_start = datetime.fromisoformat(mx.period_bounds(kind)[0])
    return mx.period_bounds(kind, cur_start - timedelta(seconds=1))


def on_award(a):
    """mx.award_loop hook: a = {user_id, code, kind: day|week|month, rank, data}. Faqat 1-o‘rin uchun yangi karta."""
    try:
        if int(a.get("rank", 0)) != 1:
            return
        if a["kind"] == "day":
            hero(a)
        elif a["kind"] == "week":
            wall(a)
    except Exception:
        log.exception("achv on_award")


def hero(a):
    uid = int(a["user_id"]); d = a["data"]
    if not _once("hero", d.get("range", ""), uid, 1):
        return None
    try:
        import growth_tests as gt
        st = gt.get_streak(uid).get("current", 0)
    except Exception:
        st = 0
    png = build_hero(uid, d.get("pts", 0), d.get("tests", 0), d.get("range", ""), st)
    cap = f"🏆 Tabriklaymiz! {d.get('range','Kecha')} sizning kuningiz edi — siz «Kun qahramoni»siz!\n⭐ {_gn(d.get('pts', 0))} ball, {d.get('tests', 0)} ta test.\nBugun ham shu o‘rinni egallay olasizmi? 💪"
    send_card(uid, png, cap)
    post_channel(png, f"🏆 Kun qahramoni — {d.get('range','')}\n{shown_name(uid)} • {_gn(d.get('pts', 0))} ball\n\nErtaga navbat sizniki! 👇")
    return png


def wall(a):
    s, e, key, name = _bounds_prev("week")
    if not _once("wall", key, 0, 0):
        return None
    rows = mx.leaderboard("week", _CFG["admin_id"], start=s, end=e)
    if not rows:
        return None
    png = build_wall(rows, name, len(rows))
    for r in rows[:5]:
        send_card(r["user_id"], png, f"🏛 Siz Shon-sharaf devoridasiz! Hafta {name}: {r['rank']}-o‘rin, {_gn(r['pts'])} ball.\nKeyingi hafta devorning markaziga chiqing!")
        time.sleep(0.3)
    post_channel(png, f"🏛 Shon-sharaf devori — hafta {name}\nHar kuni bitta mashq — devorga yo‘l! 👇")
    _admin_copy(png, f"🏛 Shon-sharaf devori yuborildi (hafta {name}): {min(5, len(rows))} ta o‘quvchiga.\nKanalga: /yutuq_kanal on")
    return png


def on_streak(uid, streak):
    """after_submit hook: streak = {current, best, new_today}."""
    try:
        if not streak or not streak.get("new_today"):
            return
        cur = int(streak.get("current", 0))
        if cur not in STREAK_MARKS or not _once("streak", cur, uid, 0):
            return
        png = build_streak(uid, cur, int(streak.get("best", cur)))
        nxt = next((m for m in STREAK_MARKS if m > cur), None)
        send_card(uid, png, f"🔥 {cur} kunlik seriya! Bu — haqiqiy odat.\n" + (f"Keyingi marra: {nxt} kun. Bugun ham bitta mashq qiling!" if nxt else "Siz eng yuqori marraga yetdingiz!"))
    except Exception:
        log.exception("achv on_streak")


def on_cert(uid, kind):
    """mx.ON_NEW_CERT hook: sertifikatlar soni 3 / 10 / 25 ga yetsa — «Sertifikat bilimdoni»."""
    try:
        with db() as c:
            n = c.execute("SELECT COUNT(*) FROM mini_certs WHERE user_id=?", (int(uid),)).fetchone()[0]
        if n not in CERT_LEVELS or not _once("bilimdon", n, uid, 0):
            return
        threading.Thread(target=_send_bilimdon, args=(uid, n), daemon=True).start()
    except Exception:
        log.exception("achv on_cert")


def _send_bilimdon(uid, n):
    try:
        png = build_bilimdon(uid, n)
        lv = cert_level(n)
        send_card(uid, png, f"📜 Tabriklaymiz! {n} ta sertifikat — siz «Sertifikat bilimdoni»siz ({lv}-daraja)!\nKeyingi darajaga qarab davom eting.")
    except Exception:
        log.exception("achv bilimdon")


def season_bounds(ref=None):
    """(boshlanish_utc_iso, tugash_utc_iso, kalit, nom) — Toshkent vaqti; Qish: dek–fev, Bahor: mar–may, Yoz: iyun–avg, Kuz: sen–noy."""
    from datetime import timezone
    d = (ref or datetime.now(mx.TZ)).astimezone(mx.TZ)
    m, y = d.month, d.year
    if m == 12:
        sm, sy = 12, y
    elif m in (1, 2):
        sm, sy = 12, y - 1
    else:
        sm, sy = (m // 3) * 3, y
    s = datetime(sy, sm, 1, tzinfo=mx.TZ)
    em, ey = (sm + 3, sy) if sm + 3 <= 12 else (sm + 3 - 12, sy + 1)
    e = datetime(ey, em, 1, tzinfo=mx.TZ)
    name = f"{SEASONS[sm]} mavsumi, {sy}" if sm != 12 else f"Qish mavsumi, {sy}–{str(sy + 1)[2:]}"
    u = lambda x: x.astimezone(timezone.utc).isoformat(timespec="seconds")
    return u(s), u(e), f"{sy}-{sm:02d}", name


def check_season(ref=None):
    """Oxirgi tugagan mavsum g‘olibini (1-o‘rin) bir marta e’lon qiladi. Qaytaradi: png yoki None."""
    cur_start = datetime.fromisoformat(season_bounds(ref)[0])
    s, e, key, name = season_bounds(cur_start - timedelta(days=1))
    if _marked("legend", key):
        return None
    st = started_at()
    if st is not None and datetime.fromisoformat(e) <= st:   # tizim yoqilishidan OLDIN tugagan mavsum — kech e'lon qilinmaydi
        _once("legend", key, 0, 0)
        return None
    rows = mx.leaderboard("month", _CFG["admin_id"], start=s, end=e)
    if not rows:
        _once("legend", key, 0, 0)
        return None
    w = rows[0]
    if not _once("legend", key, w["user_id"], 1):
        return None
    png = build_legend(w["user_id"], w["pts"], len(rows), name)
    send_card(w["user_id"], png, f"👑 Tabriklaymiz! {name}: siz «Mavsum afsonasi»siz!\n{_gn(w['pts'])} ball bilan reytingda 1-o‘rin. Bu — eng yuqori yutuq!")
    post_channel(png, f"👑 Mavsum afsonasi — {name}\n{shown_name(w['user_id'])} • {_gn(w['pts'])} ball")
    _admin_copy(png, f"👑 Mavsum afsonasi e’lon qilindi: {name} — {mx.user_name(w['user_id'])}")
    return png


def season_loop():
    def run():
        time.sleep(90)
        while True:
            try:
                check_season()
            except Exception:
                log.exception("season loop")
            time.sleep(1800)
    threading.Thread(target=run, daemon=True).start()


def started_at():
    """Yutuqlar tizimi birinchi marta yoqilgan vaqt (UTC) — shundan oldingi mavsumlar e'lon qilinmaydi."""
    v = setting("achv_started", "")
    try:
        return datetime.fromisoformat(v) if v else None
    except ValueError:
        return None


def start():
    """Botning ishga tushishida chaqiriladi: sertifikat hook va mavsum tekshiruvchisi."""
    if not setting("achv_started", ""):
        from datetime import timezone
        set_setting("achv_started", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    mx.ON_NEW_CERT = on_cert
    season_loop()


# ------------------------------------------------------------------ Telegram buyruqlari
def _admin(update):
    u = update.effective_user
    return bool(u and _CFG["admin_id"] is not None and int(u.id) == int(_CFG["admin_id"]))


async def yutuq_yashirin_cmd(update, context):
    uid = update.effective_user.id
    on = not is_hidden(uid)
    set_hidden(uid, on)
    await update.message.reply_text("🙈 Yutuq kartalarida ismingiz «Yashirin o‘quvchi» deb ko‘rsatiladi." if on else "👀 Yutuq kartalarida ismingiz ko‘rsatiladi.")


async def yutuq_cmd(update, context):
    if not _admin(update):
        return
    with db() as c:
        rows = c.execute("SELECT kind, COUNT(*) FROM achv_log WHERE user_id<>0 GROUP BY kind").fetchall()
    cnt = {r[0]: r[1] for r in rows}
    await update.message.reply_text(
        "🏅 Yutuqlar zinasi\n\n"
        f"Kun qahramoni: {cnt.get('hero', 0)}\nSeriya olovi: {cnt.get('streak', 0)}\nShon-sharaf devori: har dushanba (so‘nggi: avtomatik)\n"
        f"Sertifikat bilimdoni: {cnt.get('bilimdon', 0)}\nMavsum afsonasi: {cnt.get('legend', 0)}\n\n"
        f"Kanalga e’lon: {'YOQILGAN' if channel_on() else 'o‘chiq'} ({_CFG.get('channel') or '—'})\n"
        "Buyruqlar: /yutuq_namuna • /yutuq_kanal on|off")


async def yutuq_namuna_cmd(update, context):
    if not _admin(update):
        return
    await update.message.reply_text("🎨 5 ta namuna tayyorlanyapti…")
    for k in ac.KINDS:
        try:
            png = await asyncio.to_thread(ac.render, k, None, "YT-NAMUNA0001")
            await update.message.reply_photo(io.BytesIO(png), caption=f"{ac.STYLE_OF[k]} — {ac.TITLES[k].title()}")
        except Exception:
            log.exception("yutuq_namuna %s", k)


async def yutuq_kanal_cmd(update, context):
    if not _admin(update):
        return
    a = (context.args or [""])[0].lower()
    if a not in ("on", "off"):
        await update.message.reply_text(f"Kanalga e’lon: {'YOQILGAN' if channel_on() else 'o‘chiq'}.\n/yutuq_kanal on — yoqish, /yutuq_kanal off — o‘chirish.\n(Bot kanalda admin bo‘lishi va xabar yuborish huquqiga ega bo‘lishi kerak.)")
        return
    set_channel(a == "on")
    await update.message.reply_text("✅ Kanalga e’lon " + ("yoqildi." if a == "on" else "o‘chirildi."))


def register(app):
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("yutuq", yutuq_cmd))
    app.add_handler(CommandHandler("yutuq_namuna", yutuq_namuna_cmd))
    app.add_handler(CommandHandler("yutuq_kanal", yutuq_kanal_cmd))
    app.add_handler(CommandHandler("yutuq_yashirin", yutuq_yashirin_cmd))
