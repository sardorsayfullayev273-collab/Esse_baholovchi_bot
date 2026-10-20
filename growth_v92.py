"""V92 — onboarding, qaytarish (win-back) xabarlari va ushlab qolish hisoboti.

To'lov tizimiga (manual_pay.py, buyurtmalar, narxlar) TEGMAYDI. Hisobotda to'lovlar faqat O'QILADI.
Barcha yangi jadvallar: ob_profile, wb_log (national_certificate.db() ichida).
"""
import os, time, threading, logging
from datetime import datetime, timedelta, timezone, date

from national_certificate import db

log = logging.getLogger("growth_v92")
UZ = timezone(timedelta(hours=5))

WB_ENABLED = os.getenv("WINBACK", "1") != "0"
WB_STAGES = [2, 5, 10]                                   # yo'qolgan kunlar
WB_MAX_IDLE = int(os.getenv("WINBACK_MAX_IDLE", "30") or 30)
WB_FROM_HOUR = int(os.getenv("WINBACK_FROM_HOUR", "10") or 10)   # Toshkent vaqti
WB_TO_HOUR = int(os.getenv("WINBACK_TO_HOUR", "21") or 21)
WB_BATCH = int(os.getenv("WINBACK_BATCH", "120") or 120)         # bir tsiklda ko'pi bilan
WB_MIN_GAP_H = 40                                        # ikki win-back oralig'i (soat)

TARGETS = {"b": ("B+ (60 ball)", 60), "a": ("A (70 ball)", 70), "ap": ("A+ (80 ball)", 80), "n": ("hali bilmayman", 0)}
MINUTES = {"10": 10, "20": 20, "30": 30}


def _has_table(c, name):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def _act_expr(c):
    """Oxirgi faollik sanasi ifodasi: bot xabari, seriya va (bo'lsa) o'yinlar."""
    parts = ["COALESCE(substr(u.last_seen,1,10),'')", "COALESCE(s.last_day,'')"]
    if _has_table(c, "game_plays"):
        parts.append("COALESCE((SELECT MAX(g.day) FROM game_plays g WHERE g.user_id=u.user_id),'')")
    return "MAX(" + ",".join(parts) + ")"


def _now_utc():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _today():
    return datetime.now(UZ).date()


def init():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS ob_profile(
            user_id INTEGER PRIMARY KEY, target TEXT, minutes INTEGER, step TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS wb_log(
            user_id INTEGER NOT NULL, stage INTEGER NOT NULL, anchor TEXT NOT NULL, sent_at TEXT NOT NULL,
            PRIMARY KEY(user_id, stage, anchor))""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_wb_user ON wb_log(user_id, sent_at)")
        c.execute("CREATE TABLE IF NOT EXISTS essay_topics(id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, norm TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1, added_by INTEGER, added_at TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS essay_today(day TEXT PRIMARY KEY, text TEXT NOT NULL)")
        try: c.execute("ALTER TABLE ob_profile ADD COLUMN region TEXT")
        except Exception: pass
        c.commit()


# ------------------------------------------------------------------ onboarding
def ob_get(uid):
    with db() as c:
        r = c.execute("SELECT target,minutes,step FROM ob_profile WHERE user_id=?", (int(uid),)).fetchone()
    return dict(r) if r else None


def ob_needed(uid):
    """Profil umuman yo'q bo'lsa — bir marta so'raladi (o'tkazib yuborilgan ham «bor» hisoblanadi)."""
    return ob_get(uid) is None


def ob_set(uid, target=None, minutes=None, step=None):
    t = _now_utc()
    with db() as c:
        c.execute("INSERT OR IGNORE INTO ob_profile(user_id,step,created_at,updated_at) VALUES(?,?,?,?)", (int(uid), "new", t, t))
        if target is not None:
            c.execute("UPDATE ob_profile SET target=?, updated_at=? WHERE user_id=?", (target, t, int(uid)))
        if minutes is not None:
            c.execute("UPDATE ob_profile SET minutes=?, updated_at=? WHERE user_id=?", (int(minutes), t, int(uid)))
        if step is not None:
            c.execute("UPDATE ob_profile SET step=?, updated_at=? WHERE user_id=?", (step, t, int(uid)))
        c.commit()


def exam_days_left():
    raw = os.getenv("EXAM_DATE", "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            d = datetime.strptime(raw[:len(datetime.now().strftime(fmt))], fmt).date()
            n = (d - _today()).days
            return n if n >= 0 else None
        except Exception:
            continue
    return None


def ob_question_target():
    return ("🎯 Qaysi natijani maqsad qilgansiz?\n\nShunga qarab sizga shaxsiy reja tuzaman (10 soniya).",
            [[("B+ (60 ball)", "ob_t_b"), ("A (70 ball)", "ob_t_a")],
             [("A+ (80 ball)", "ob_t_ap"), ("Hali bilmayman", "ob_t_n")],
             [("⏭ Keyinroq", "ob_skip")]])


def ob_question_minutes():
    return ("⏱ Kuniga qancha vaqt ajrata olasiz?",
            [[("10 daqiqa", "ob_m_10"), ("20 daqiqa", "ob_m_20"), ("30 daqiqa", "ob_m_30")]])


def ob_done_text(uid):
    p = ob_get(uid) or {}
    tname = TARGETS.get(p.get("target") or "n", TARGETS["n"])[0]
    mins = int(p.get("minutes") or 10)
    n = exam_days_left()
    lines = ["✅ Shaxsiy rejangiz tayyor!", ""]
    if p.get("target") and p.get("target") != "n":
        lines.append(f"🎯 Maqsad: {tname}")
    if n is not None:
        lines.append(f"📅 Imtihongacha: {n} kun")
    lines.append(f"⏱ Kuniga: {mins} daqiqa")
    lines.append("")
    plan = {10: "5 ta kunlik savol + 1 ta qoida", 20: "5 ta kunlik savol + xatolar daftari + 1 ta qoida",
            30: "5 ta kunlik savol + xatolar daftari + zaif mavzu mashqi"}[mins if mins in (10, 20, 30) else 10]
    lines.append(f"📌 Har kun: {plan}.")
    lines.append("Avval hozirgi darajangizni bilish uchun diagnostik testni ishlab ko‘ring 👇")
    return "\n".join(lines)


# ------------------------------------------------------------------ win-back
def _last_activity_rows(limit):
    """[(uid, first_name, last_day(date))] — faqat nomzodlar (idle oralig'ida), tartib: eng yangi yo'qolganlar avval."""
    lo = (_today() - timedelta(days=WB_MAX_IDLE)).isoformat()
    hi = (_today() - timedelta(days=WB_STAGES[0])).isoformat()
    with db() as c:
        act = _act_expr(c)
        banned = "AND u.user_id NOT IN (SELECT user_id FROM mini_banned)" if _has_table(c, "mini_banned") else ""
        rem = "LEFT JOIN reminders r ON r.user_id=u.user_id" if _has_table(c, "reminders") else ""
        optc = "COALESCE(r.optout,0)=0" if rem else "1=1"
        rows = c.execute(
            f"""SELECT u.user_id AS uid, COALESCE(u.first_name,'') AS fn,
                      {act} AS ld
               FROM users u
               LEFT JOIN streaks s ON s.user_id=u.user_id
               {rem}
               WHERE {optc} {banned}
               GROUP BY u.user_id
               HAVING ld>=? AND ld<=?
               ORDER BY ld DESC LIMIT ?""", (lo, hi, int(limit) * 4)).fetchall()
    return rows


def _stage_for(idle):
    st = 0
    for i, d in enumerate(WB_STAGES, 1):
        if idle >= d:
            st = i
    return st


def winback_candidates(limit=None):
    """[(uid, first_name, stage, anchor)] — hali yuborilmagan eng yuqori bosqich; oxirgi win-back dan >= WB_MIN_GAP_H."""
    limit = limit or WB_BATCH
    today = _today(); out = []
    try:
        rows = _last_activity_rows(limit)
    except Exception:
        log.exception("winback rows"); return []
    gap_cut = (datetime.utcnow() - timedelta(hours=WB_MIN_GAP_H)).isoformat(timespec="seconds") + "Z"
    with db() as c:
        for r in rows:
            try:
                ld = date.fromisoformat(r["ld"])
            except Exception:
                continue
            idle = (today - ld).days
            st = _stage_for(idle)
            if st <= 0:
                continue
            uid = int(r["uid"])
            sent = c.execute("SELECT stage, sent_at FROM wb_log WHERE user_id=? AND anchor=? ORDER BY stage DESC", (uid, r["ld"])).fetchall()
            if sent and int(sent[0]["stage"]) >= st:
                continue
            last = c.execute("SELECT MAX(sent_at) FROM wb_log WHERE user_id=?", (uid,)).fetchone()[0]
            if last and last > gap_cut:
                continue
            out.append((uid, r["fn"], st, r["ld"]))
            if len(out) >= limit:
                break
    return out


def winback_text(uid, name, stage, topics_fn=None, forecast_fn=None):
    nm = (name or "").strip()[:30] or "Do‘st"
    p = ob_get(uid) or {}
    n = exam_days_left()
    head = f"👋 {nm}, "
    exam = f"\n📅 Imtihongacha {n} kun qoldi." if n is not None else ""
    weak = None
    try:
        ts = [t for t in (topics_fn(uid) if topics_fn else []) if t.get("t", 0) >= 3]
        if ts:
            weak = min(ts, key=lambda t: t["p"])
    except Exception:
        weak = None
    if stage == 1:
        body = "sizni sog‘inib qoldik!" + exam
        if weak:
            body += f"\n🎯 Eng zaif mavzuingiz: «{weak['c']}» ({weak['p']}%). 5 ta savol — 3 daqiqa."
        else:
            body += "\n🎯 Bugungi 5 ta savol — atigi 3 daqiqa."
    elif stage == 2:
        fc = None
        try:
            fc = forecast_fn(uid) if forecast_fn else None
        except Exception:
            fc = None
        if fc and fc.get("next_level") and fc.get("next_gap"):
            body = (f"taxminiy balingiz {fc['score']}/{fc['max']}. {fc['next_level']} darajasigacha yana {fc['next_gap']} ball qoldi — "
                    "kuniga 10 daqiqa yetadi." + exam)
        elif p.get("target") and p.get("target") != "n":
            body = f"maqsadingiz — {TARGETS.get(p['target'], ('',0))[0]}. Har kunlik mashq sizni unga yaqinlashtiradi." + exam
        else:
            body = "bugun yangi qoida kartasi va 5 ta savol sizni kutyapti." + exam
    else:
        body = ("seriyangizni qaytadan boshlash vaqti keldi — bugun 5 ta savol yetarli.\n"
                "Bu oxirgi eslatma. O‘chirish: /eslatma off")
    return head + body


def winback_run_once(send, mark_block, webapp_url, topics_fn=None, forecast_fn=None, is_banned=None, sleep=0.08):
    """send(method, payload) -> (ok, code). Qaytaradi: yuborilganlar soni."""
    now = datetime.now(UZ)
    if not (WB_FROM_HOUR <= now.hour < WB_TO_HOUR):
        return 0
    sent = 0
    for uid, name, stage, anchor in winback_candidates():
        if is_banned and is_banned(uid):
            continue
        payload = {"chat_id": uid, "disable_notification": True, "text": winback_text(uid, name, stage, topics_fn, forecast_fn)}
        if webapp_url:
            payload["reply_markup"] = {"inline_keyboard": [[{"text": "🚀 Mashq qilish", "web_app": {"url": webapp_url}}]]}
        ok, code = send("sendMessage", payload)
        if ok:
            with db() as c:
                c.execute("INSERT OR IGNORE INTO wb_log(user_id,stage,anchor,sent_at) VALUES(?,?,?,?)", (uid, stage, anchor, _now_utc()))
                c.commit()
            sent += 1
        elif code in (400, 403):
            try: mark_block(uid)           # bot bloklangan — boshqa yubormaymiz
            except Exception: pass
        time.sleep(sleep)
    return sent


def start_winback_thread(send, mark_block, webapp_url_fn, topics_fn=None, forecast_fn=None, is_banned=None):
    if not WB_ENABLED:
        return None
    def run():
        time.sleep(180)
        while True:
            try:
                n = winback_run_once(send, mark_block, webapp_url_fn(), topics_fn, forecast_fn, is_banned)
                if n: log.info("winback yuborildi: %s", n)
            except Exception:
                log.exception("winback loop")
            time.sleep(600)
    t = threading.Thread(target=run, daemon=True, name="winback"); t.start()
    return t


# ------------------------------------------------------------------ hisobot (ushlab qolish + voronka) — faqat O'QIYDI
def _cohort(c, joined_day, n):
    """joined_day (date) kuni qo'shilganlar; ularning qanchasi >= n kundan keyin ham faol bo'lgan."""
    a = joined_day.isoformat()
    act = _act_expr(c)
    rows = c.execute(
        f"""SELECT u.user_id, {act} AS ld
           FROM users u LEFT JOIN streaks s ON s.user_id=u.user_id
           WHERE substr(u.joined_at,1,10)=? GROUP BY u.user_id""", (a,)).fetchall()
    tot = len(rows)
    need = (joined_day + timedelta(days=n)).isoformat()
    back = sum(1 for r in rows if r["ld"] and r["ld"] >= need)
    return tot, back


def _pct(a, b):
    return f"{round(a * 100.0 / b)}%" if b else "—"


def report_lines(day_tk):
    """Kunlik hisobotga qo'shiladigan qatorlar (HTML emas, oddiy matn). day_tk — hisobot kuni (date)."""
    out = []
    today = _today()
    try:
        with db() as c:
            for n in (1, 7, 30):
                d = today - timedelta(days=n + 1)
                tot, back = _cohort(c, d, n)
                if tot:
                    out.append(f"    • D{n}: {back}/{tot} ({_pct(back, tot)}) — {d.strftime('%d.%m')} da qo‘shilganlar")
            a = day_tk.isoformat()
            new = c.execute("SELECT COUNT(*) FROM users WHERE substr(joined_at,1,10)=?", (a,)).fetchone()[0]
            ob = c.execute("SELECT COUNT(*) FROM ob_profile p JOIN users u ON u.user_id=p.user_id WHERE substr(u.joined_at,1,10)=? AND p.step='done'", (a,)).fetchone()[0]
            try:
                played = c.execute("SELECT COUNT(DISTINCT g.user_id) FROM game_plays g JOIN users u ON u.user_id=g.user_id WHERE substr(u.joined_at,1,10)=?", (a,)).fetchone()[0]
            except Exception:
                played = 0
            try:
                paid = c.execute("SELECT COUNT(DISTINCT o.user_id) FROM manual_orders o JOIN users u ON u.user_id=o.user_id "
                                 "WHERE o.status='approved' AND o.amount>0 AND substr(u.joined_at,1,10)>=?",
                                 ((today - timedelta(days=7)).isoformat(),)).fetchone()[0]
                new7 = c.execute("SELECT COUNT(*) FROM users WHERE substr(joined_at,1,10)>=?", ((today - timedelta(days=7)).isoformat(),)).fetchone()[0]
            except Exception:
                paid, new7 = 0, 0
            wb = c.execute("SELECT COUNT(*) FROM wb_log WHERE substr(sent_at,1,10)=?", (a,)).fetchone()[0]
        hdr = ["", "📈 USHLAB QOLISH (taxminiy: oxirgi faollik bo‘yicha)"]
        if not out:
            hdr.append("    • (hali yetarli ma’lumot yo‘q)")
        hdr += out
        hdr.append(f"🔻 VORONKA ({day_tk.strftime('%d.%m')} da kirganlar): yangi {new} → profil to‘ldirgan {ob} ({_pct(ob, new)}) → mashq qilgan {played} ({_pct(played, new)})")
        hdr.append(f"💳 Oxirgi 7 kunda kirganlardan to‘lov qilgan: {paid}/{new7} ({_pct(paid, new7)})")
        hdr.append(f"🔔 Qaytarish xabarlari (shu kuni): {wb}")
        try:
            from national_certificate import DB_PATH
            mb = os.path.getsize(DB_PATH) / 1048576
            hdr.append(f"💾 Baza: {mb:.1f} MB" + ("" if os.path.isabs(DB_PATH) else " ⚠️ yo‘l nisbiy — doimiy Disk ulanganini tekshiring"))
        except Exception:
            pass
        return hdr
    except Exception:
        log.exception("report_lines")
        return []


# ================================================================== 2-bosqich: referal xabari (mukofotlar MAVJUD ❄️/Elchi/joker tizimidan — yangi tizim yo'q)
def invited_count(inviter):
    """Kanalga a'zo bo'lib, bonus olgan (haqiqiy kirgan) do'stlar soni. manual_pay jadvali FAQAT O'QILADI."""
    try:
        with db() as c:
            return int(c.execute("SELECT COUNT(*) FROM referrals WHERE inviter_id=? AND invitee_bonus>0", (int(inviter),)).fetchone()[0])
    except Exception:
        return 0


def _perks(uid):
    try:
        import mini_extra as mx
        return mx.game_perks(int(uid))
    except Exception:
        return None


def on_invite_joined(inviter):
    """Do'st haqiqatan qo'shilganda taklif qiluvchiga xabar matni. Mukofot: do'st Mini App'da o'ynasa mavjud zinapoya ochiladi."""
    txt = f"🎉 Do‘stingiz botga qo‘shildi! Jami: {invited_count(inviter)} ta do‘st."
    p = _perks(inviter)
    if p:
        txt += "\n❄️ Seriya himoyasi: %d ta." % p.get("freeze_left", 0)
        nx = p.get("next")
        if nx:
            txt += f"\n🎯 Do‘stingiz o‘yin o‘ynasa hisoblanadi. Keyingi mukofot: yana {nx['left']} ta do‘st → {nx['reward']}."
    return txt


def freeze_info_text(uid):
    p = _perks(uid)
    if not p:
        return "❄️ Seriya himoyasi hozir mavjud emas."
    L = [f"❄️ Seriya himoyasi: {p.get('freeze_left', 0)} ta", f"👥 O‘yin o‘ynagan do‘stlaringiz: {p.get('friends', 0)}",
         "Bir kun «Kunlik 5 savol»ni o‘tkazib yuborsangiz, himoya seriyangizni avtomatik saqlaydi.", ""]
    for st in p.get("steps", []):
        L.append(("✅ " if st["done"] else "▫️ ") + f"{st['need']} do‘st — {st['title']}")
    L.append("\nDo‘st taklif qilish: /taklif")
    return "\n".join(L)


# ================================================================== 3-bosqich: ustoz paneli, viloyat reytingi, ulashish
REGIONS = ["Toshkent sh.", "Toshkent v.", "Andijon", "Buxoro", "Farg‘ona", "Jizzax", "Xorazm", "Namangan",
           "Navoiy", "Qashqadaryo", "Samarqand", "Sirdaryo", "Surxondaryo", "Qoraqalpog‘iston"]


def _cut(days):
    return (_today() - timedelta(days=days)).isoformat()


def _fname(c, uid):
    r = c.execute("SELECT first_name, username FROM users WHERE user_id=?", (int(uid),)).fetchone()
    if not r: return str(uid)
    return (r[0] or "").strip()[:20] or (("@" + r[1]) if r[1] else str(uid))


def is_teacher(uid):
    try:
        with db() as c:
            return c.execute("SELECT 1 FROM teachers WHERE user_id=? AND active=1", (int(uid),)).fetchone() is not None
    except Exception:
        return False


def _week_stats(c, ids_sql, params, days=7):
    """{uid: (points, active_days)} — game_plays bo'yicha."""
    if not _has_table(c, "game_plays"):
        return {}
    rows = c.execute(f"SELECT user_id, COALESCE(SUM(points),0) p, COUNT(DISTINCT day) d FROM game_plays WHERE day>=? AND user_id IN ({ids_sql}) GROUP BY user_id",
                     (_cut(days), *params)).fetchall()
    return {int(r[0]): (int(r[1]), int(r[2])) for r in rows}


def class_overview(teacher_id, days=7):
    """Ustoz paneli matni: faol/nofaol o'quvchilar va sinf reytingi."""
    sub, par = "SELECT student_id FROM teacher_students WHERE teacher_id=?", (int(teacher_id),)
    with db() as c:
        ids = [int(r[0]) for r in c.execute(sub, par).fetchall()]
        if not ids:
            return "👩‍🏫 Sizda hali o‘quvchi yo‘q. Ustoz havolangiz orqali kirgan o‘quvchilar shu yerda ko‘rinadi."
        st = _week_stats(c, sub, par, days)
        names = {i: _fname(c, i) for i in ids}
    act = sorted([i for i in ids if i in st], key=lambda i: -st[i][0])
    idle = [i for i in ids if i not in st]
    L = [f"👩‍🏫 SINF HISOBOTI (oxirgi {days} kun)", f"👥 O‘quvchilar: {len(ids)} • faol: {len(act)} • nofaol: {len(idle)}", ""]
    if act:
        L.append("🏆 Eng faollar:")
        for k, i in enumerate(act[:5], 1):
            L.append(f"{k}. {names[i]} — {st[i][0]} ball, {st[i][1]} kun")
    if idle:
        L.append("")
        L.append("😴 Mashq qilmaganlar: " + ", ".join(names[i] for i in idle[:15]) + (f" va yana {len(idle) - 15} ta" if len(idle) > 15 else ""))
    L.append("")
    L.append("Ota-onalarga yuborish uchun hisobot: /sinf hisobot")
    return "\n".join(L)


def parent_report(student_id, topics_fn=None, forecast_fn=None, days=7):
    with db() as c:
        nm = _fname(c, student_id)
        st = _week_stats(c, "SELECT ?", (int(student_id),), days).get(int(student_id), (0, 0))
    lines = [f"📋 {nm} — haftalik hisobot", f"• Mashq qilgan kunlar: {st[1]}/7", f"• To‘plangan ball: {st[0]}"]
    try:
        ts = [t for t in (topics_fn(student_id) if topics_fn else []) if t.get("t", 0) >= 3]
        if ts:
            w = min(ts, key=lambda t: t["p"]); lines.append(f"• Zaif mavzu: {w['c']} ({w['p']}%)")
    except Exception: pass
    try:
        fc = forecast_fn(student_id) if forecast_fn else None
        if fc: lines.append(f"• Taxminiy ball: {fc['score']}/{fc['max']} ({fc['level']})")
    except Exception: pass
    if st[1] == 0:
        lines.append("• Bu hafta mashq qilinmadi — iltimos, kuniga 10 daqiqa ajratishini eslating.")
    return "\n".join(lines)


def class_parent_reports(teacher_id, topics_fn=None, forecast_fn=None, days=7, limit=40):
    with db() as c:
        ids = [int(r[0]) for r in c.execute("SELECT student_id FROM teacher_students WHERE teacher_id=? LIMIT ?", (int(teacher_id), int(limit))).fetchall()]
    return [parent_report(i, topics_fn, forecast_fn, days) for i in ids]


def student_class_board(uid, days=7):
    """O'quvchining sinf (ustozi bo'yicha) haftalik reytingi; ustozi bo'lmasa None."""
    with db() as c:
        r = c.execute("SELECT teacher_id FROM teacher_students WHERE student_id=?", (int(uid),)).fetchone()
        if not r: return None
        sub, par = "SELECT student_id FROM teacher_students WHERE teacher_id=?", (int(r[0]),)
        st = _week_stats(c, sub, par, days)
        ranked = sorted(st.items(), key=lambda kv: -kv[1][0])
        names = {i: _fname(c, i) for i, _ in ranked[:10]}
        total = c.execute("SELECT COUNT(*) FROM teacher_students WHERE teacher_id=?", par).fetchone()[0]
    if not ranked:
        return f"🏫 Sinfingizda bu hafta hali hech kim mashq qilmagan ({total} o‘quvchi). Birinchi bo‘ling!"
    me = next((k for k, (i, _) in enumerate(ranked, 1) if i == int(uid)), None)
    L = [f"🏫 SINF REYTINGI (oxirgi {days} kun, {total} o‘quvchi)"]
    for k, (i, (p, d)) in enumerate(ranked[:10], 1):
        L.append(f"{k}. {'👉 ' if i == int(uid) else ''}{names[i]} — {p} ball")
    L.append("")
    L.append(f"Sizning o‘rningiz: {me}" if me else "Siz bu hafta hali mashq qilmadingiz — reytingga kirish uchun 1 ta o‘yin yetadi.")
    return "\n".join(L)


def region_set(uid, idx):
    if not (0 <= int(idx) < len(REGIONS)): return None
    ob_set(uid)
    with db() as c:
        c.execute("UPDATE ob_profile SET region=?, updated_at=? WHERE user_id=?", (REGIONS[int(idx)], _now_utc(), int(uid))); c.commit()
    return REGIONS[int(idx)]


def region_get(uid):
    with db() as c:
        r = c.execute("SELECT region FROM ob_profile WHERE user_id=?", (int(uid),)).fetchone()
    return r[0] if r and r[0] else None


def region_board(uid, days=7):
    """Viloyat ichidagi top-10 va viloyatlar o'rtasidagi top-5 (jami ball)."""
    reg = region_get(uid)
    with db() as c:
        if not _has_table(c, "game_plays"):
            return "Reyting hali tayyor emas."
        tot = c.execute("""SELECT p.region, COALESCE(SUM(g.points),0) s, COUNT(DISTINCT g.user_id) n
                           FROM ob_profile p JOIN game_plays g ON g.user_id=p.user_id
                           WHERE p.region IS NOT NULL AND g.day>=? GROUP BY p.region ORDER BY s DESC LIMIT 5""", (_cut(days),)).fetchall()
        mine = []
        if reg:
            mine = c.execute("""SELECT g.user_id, SUM(g.points) s FROM game_plays g JOIN ob_profile p ON p.user_id=g.user_id
                                WHERE p.region=? AND g.day>=? GROUP BY g.user_id ORDER BY s DESC LIMIT 10""", (reg, _cut(days))).fetchall()
        names = {int(r[0]): _fname(c, r[0]) for r in mine}
    L = [f"🗺 VILOYATLAR REYTINGI (oxirgi {days} kun)"]
    for k, r in enumerate(tot, 1):
        L.append(f"{k}. {r[0]} — {int(r[1])} ball ({int(r[2])} ishtirokchi)")
    if not tot: L.append("Hali ma’lumot yo‘q — birinchi bo‘lib viloyatingizni tanlang!")
    if reg:
        L += ["", f"📍 {reg} — top o‘quvchilar:"]
        for k, r in enumerate(mine, 1):
            L.append(f"{k}. {'👉 ' if int(r[0]) == int(uid) else ''}{names[int(r[0])]} — {int(r[1])} ball")
    else:
        L += ["", "Viloyatingizni tanlash: /viloyat"]
    return "\n".join(L)


def share_card(uid, link, forecast_fn=None, streak=0):
    """Ulashish kartasi matni va t.me/share havolasi."""
    from urllib.parse import quote
    fc = None
    try: fc = forecast_fn(uid) if forecast_fn else None
    except Exception: pass
    lines = ["📊 Ona tili va adabiyot — Milliy sertifikatga tayyorlanyapman!"]
    if fc: lines.append(f"🎯 Taxminiy ballim: {fc['score']}/{fc['max']} ({fc['level']})")
    if streak and streak >= 2: lines.append(f"🔥 Ketma-ket mashq: {streak} kun")
    lines.append("Sen ham o‘z darajangni bepul sinab ko‘r 👇")
    text = "\n".join(lines)
    return text, f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(text, safe='')}"


# ================================================================== Kunlik esse mavzulari (admin kiritadi)
import re as _re
ESSAY_MIN, ESSAY_MAX = 25, 400


def _norm(t):
    return _re.sub(r"[^\w']+", " ", str(t).lower().replace("‘", "'").replace("’", "'").replace("ʻ", "'").replace("`", "'")).strip()


def _clean_line(t):
    t = _re.sub(r"^\s*(?:\d+\s*[\).:-]|[-•*▪️])\s*", "", t.strip())
    return _re.sub(r"\s+", " ", t).strip()


def essay_add_many(raw, by):
    """Bir nechta qatorli matndan mavzularni qo'shadi. Qaytaradi: (qo'shilgan_idlar, [(qator, sabab)])."""
    added, bad = [], []
    for line in str(raw).split("\n"):
        t = _clean_line(line)
        if not t:
            continue
        if len(t) < ESSAY_MIN:
            bad.append((t[:40], f"juda qisqa (<{ESSAY_MIN} belgi)")); continue
        if len(t) > ESSAY_MAX:
            bad.append((t[:40], f"juda uzun (>{ESSAY_MAX} belgi)")); continue
        try:
            with db() as c:
                cur = c.execute("INSERT INTO essay_topics(text,norm,active,added_by,added_at) VALUES(?,?,1,?,?)", (t, _norm(t), int(by), _now_utc()))
                c.commit(); added.append(cur.lastrowid)
        except Exception:
            bad.append((t[:40], "bunday mavzu allaqachon bor"))
    return added, bad


def essay_set_active(tid, active):
    with db() as c:
        cur = c.execute("UPDATE essay_topics SET active=? WHERE id=?", (1 if active else 0, int(tid))); c.commit()
        return cur.rowcount > 0


def essay_counts():
    with db() as c:
        r = c.execute("SELECT COALESCE(SUM(active),0), COUNT(*) FROM essay_topics").fetchone()
    return int(r[0]), int(r[1])


def essay_list(page=1, per=10):
    with db() as c:
        rows = c.execute("SELECT id,text,active FROM essay_topics ORDER BY id DESC LIMIT ? OFFSET ?", (int(per), (max(1, int(page)) - 1) * int(per))).fetchall()
    return [dict(r) for r in rows]


def essay_pool(defaults):
    with db() as c:
        adm = [r[0] for r in c.execute("SELECT text FROM essay_topics WHERE active=1 ORDER BY id").fetchall()]
    return list(defaults) + adm


def essay_today(defaults):
    """Bugungi mavzu: kun davomida o'zgarmaydi (admin yangi mavzu qo'shsa ham). Yaqinda ishlatilganlar qayta chiqmaydi."""
    day = _today().isoformat()
    with db() as c:
        r = c.execute("SELECT text FROM essay_today WHERE day=?", (day,)).fetchone()
        if r:
            return r[0]
        pool = essay_pool(defaults)
        recent = {x[0] for x in c.execute("SELECT text FROM essay_today ORDER BY day DESC LIMIT ?", (max(1, min(60, len(pool) - 1)),)).fetchall()}
        cand = [t for t in pool if t not in recent] or pool
        pick = cand[_today().toordinal() % len(cand)]
        c.execute("INSERT OR IGNORE INTO essay_today(day,text) VALUES(?,?)", (day, pick)); c.commit()
        r = c.execute("SELECT text FROM essay_today WHERE day=?", (day,)).fetchone()
    return r[0]


def essay_set_today(tid):
    """Bugungi mavzuni admin mavzularidan biriga almashtiradi. Qaytaradi: matn yoki None."""
    with db() as c:
        r = c.execute("SELECT text FROM essay_topics WHERE id=? AND active=1", (int(tid),)).fetchone()
        if not r:
            return None
        c.execute("INSERT INTO essay_today(day,text) VALUES(?,?) ON CONFLICT(day) DO UPDATE SET text=excluded.text", (_today().isoformat(), r[0])); c.commit()
    return r[0]
