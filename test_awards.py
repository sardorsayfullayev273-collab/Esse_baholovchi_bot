# -*- coding: utf-8 -*-
"""v121 — admin o‘tkazgan oddiy testlarda 1–3-o‘rin sovrindorlariga «bilimdon» sertifikati.

Qoida: test yakunlanganda (muddat tugadi / qo‘lda yakunlandi) — test ADMIN tomonidan yaratilgan bo‘lsa,
eng ko‘p to‘g‘ri javob bergan 3 ishtirokchiga shu TEST MAVZUSIga qarab nomlangan sertifikat beriladi
(masalan: «G‘azal bilimdoni», «Ilmiy matn bilimdoni»). Teng natijada avval topshirgan yuqori o‘rinda.
Sertifikatlar mini_certs jadvaliga (kind='topaward', kod 'TP-…') yoziladi: Mini App havolasi /api/cert/<kod>.png,
tekshirish /api/cert/verify/<kod>; dizayn: cert_award.py (3D…7D).

Admin buyruqlari: /sert_namuna  /sert_uslub  /sert_nom  /sert_top
"""
import asyncio, io, json, logging, re
from datetime import datetime

from national_certificate import db, now, setting, set_setting

log = logging.getLogger("test_awards")
KIND = "simple"
STYLE_KEY = "award_cert_style"
_CFG = {"admin_id": None, "token": None}


def configure(admin_id, token=None):
    _CFG.update(admin_id=admin_id, token=token)


def init():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS test_awards(
            kind TEXT NOT NULL, code TEXT NOT NULL, rank INTEGER NOT NULL, user_id INTEGER NOT NULL,
            cert_code TEXT, created_at TEXT, PRIMARY KEY(kind, code, rank))""")
        c.commit()


# ------------------------------------------------------------------ uslub (3D…7D)
def current_style():
    import cert_award as ca
    s = (setting(STYLE_KEY, "") or "").strip().upper()
    return s if s in ca.STYLES else ca.DEFAULT_STYLE


def set_style(s):
    import cert_award as ca
    s = str(s or "").strip().upper()
    if s not in ca.STYLES:
        return False
    set_setting(STYLE_KEY, s)
    return True


# ------------------------------------------------------------------ sertifikat sarlavhasi (test mavzusidan)
_NOISE = re.compile(
    r"(?:\b\d+\s*[-–.]?\s*(?:mavzu|variant|dars|test|savol|bosqich|bo‘lim|bolim|qism)\w*"
    r"|\b(?:mavzu|variant|dars|test|savol|bosqich|qism)\w*\s*[-–.:№#]?\s*\d+"
    r"|\b(?:test|testi|testlar|testlari|savol|savollar|savollari|sinov|nazorat|diagnostik|mashq|mavzusi|mavzu|variant|variantlari|bo[‘’'`ʻ]yicha)\b)", re.I)

_NOISE_NUM = re.compile(r"(?:\b\d+\s*[-–.]?\s*(?:mavzu|variant|dars|test|savol|bosqich|bo‘lim|bolim|qism)\w*|\b(?:mavzu|variant|dars|test|savol|bosqich|qism)\w*\s*[-–.:№#]?\s*\d+)", re.I)


def _apos(s):
    return re.sub(r"([OoGg])['’ʻ`‘]", r"\1‘", s)


def derive_title(subject, title):
    """Test mavzusidan sertifikat nomi: «G‘azal» → «G‘azal bilimdoni». Mavzu bo‘sh bo‘lsa — test nomidan."""
    src = (subject or "").strip()
    from_subject = len(src) >= 2
    if not from_subject:
        src = (title or "").strip()
    s = _apos(src)
    s = re.sub(r"[«»\"“”()\[\]]", " ", s)
    s = (_NOISE_NUM if from_subject else _NOISE).sub(" ", s)   # mavzu admin tomonidan aniq yozilgan: faqat raqamli qo‘shimchalar olib tashlanadi
    s = re.sub(r"[—–\-:;,.|/\\№#]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) < 2:
        s = _apos((title or "").strip())
        s = re.sub(r"[«»\"“”()\[\]—–\-:;,.|/\\№#\d]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
    if s.lower().endswith("bilimdoni"):
        s = s[: -len("bilimdoni")].strip()
    if len(s) > 38:
        s = s[:38].rsplit(" ", 1)[0] if " " in s[:38] else s[:38]
    if not s:
        return "Test bilimdoni"
    s = s[0].upper() + (s[1:].lower() if s.isupper() else s[1:])
    return f"{s} bilimdoni"


def title_override(code):
    v = (setting("award_title:" + str(code).upper(), "") or "").strip()
    return v


def set_title_override(code, text):
    set_setting("award_title:" + str(code).upper(), (text or "").strip()[:60])


def award_title_for(test):
    """Admin qo‘lda kiritgan nom > mavzudan avtomatik nom. '-' — avtomatik sertifikat o‘chirilgan (None)."""
    ov = title_override(test["code"])
    if ov == "-":
        return None
    return ov or derive_title(test.get("subject"), test.get("title"))


# ------------------------------------------------------------------ reyting
def _test_row(code):
    with db() as c:
        r = c.execute("SELECT id,code,title,subject,created_by FROM simple_tests WHERE code=?", (str(code).upper().strip(),)).fetchone()
    return dict(r) if r else None


def ranking(code, admin_id=None, is_banned=None, limit=3):
    """Eng ko‘p to‘g‘ri javob (teng bo‘lsa — avval topshirgan). Admin va bloklanganlar kirmaydi; 0 ta to‘g‘ri — kirmaydi."""
    t = _test_row(code)
    if not t:
        return []
    with db() as c:
        rows = c.execute("SELECT id,user_id,correct,total,created_at FROM simple_attempts WHERE test_id=? ORDER BY id", (t["id"],)).fetchall()
    best = {}
    for r in rows:   # har foydalanuvchining birinchi urinishi
        if r["user_id"] not in best:
            best[r["user_id"]] = dict(r)
    out = []
    for r in best.values():
        if admin_id is not None and int(r["user_id"]) == int(admin_id):
            continue
        if is_banned and is_banned(int(r["user_id"])):
            continue
        if int(r["correct"] or 0) <= 0:
            continue
        out.append(r)
    out.sort(key=lambda r: (-int(r["correct"]), r["created_at"], r["id"]))
    res = []
    for i, r in enumerate(out[:limit], 1):
        tot = int(r["total"] or 0)
        res.append({"rank": i, "user_id": int(r["user_id"]), "correct": int(r["correct"]), "total": tot,
                    "percent": round(int(r["correct"]) / tot * 100) if tot else 0, "at": r["created_at"]})
    return res


def already_awarded(code):
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM test_awards WHERE kind=? AND code=?", (KIND, str(code).upper().strip())).fetchone()[0] > 0


def awards_of(code):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM test_awards WHERE kind=? AND code=? ORDER BY rank", (KIND, str(code).upper().strip())).fetchall()]


def issue(code, force=False):
    """Sertifikatlarni yaratadi (rasmni emas). Qaytaradi: {'ok','reason','title','awards':[{rank,user_id,name,cert_code,data}]}.
    force=True — admin buyrug‘i: test muallifi admin bo‘lmasa ham, '-' belgilangan bo‘lsa ham beradi. Bir test uchun bir marta."""
    import mini_extra as mx
    admin_id = _CFG["admin_id"]
    code = str(code).upper().strip()
    t = _test_row(code)
    if not t:
        return {"ok": False, "reason": "Test topilmadi.", "awards": []}
    if not force and (admin_id is None or int(t["created_by"] or 0) != int(admin_id)):
        return {"ok": False, "reason": "not_admin_test", "awards": []}
    title = award_title_for(t)
    if title is None and not force:
        return {"ok": False, "reason": "disabled", "awards": []}
    if title is None:
        title = derive_title(t.get("subject"), t.get("title"))
    if already_awarded(code):
        return {"ok": False, "reason": "already", "title": title, "awards": []}
    top = ranking(code, admin_id, getattr(mx, "is_banned", None))
    if not top:
        return {"ok": False, "reason": "no_winners", "title": title, "awards": []}
    style = current_style()
    out = []
    for r in top:
        data = {"name": mx.user_name(r["user_id"]), "rank": r["rank"], "award": title, "testname": t["title"], "subject": t.get("subject") or "",
                "correct": r["correct"], "total": r["total"], "percent": r["percent"], "style": style, "test_code": code,
                "date": datetime.now(mx.TZ).strftime("%d.%m.%Y")}
        cc = mx.new_cert(r["user_id"], "topaward", data)
        with db() as c:
            c.execute("INSERT OR IGNORE INTO test_awards(kind,code,rank,user_id,cert_code,created_at) VALUES(?,?,?,?,?,?)", (KIND, code, r["rank"], r["user_id"], cc, now()))
            c.commit()
        out.append({"rank": r["rank"], "user_id": r["user_id"], "name": data["name"], "cert_code": cc, "data": data, "correct": r["correct"], "total": r["total"]})
    return {"ok": True, "reason": "", "title": title, "awards": out}


def caption_for(a):
    d = a["data"]
    return (f"🏆 Tabriklaymiz! «{d['testname']}» testida {d['rank']}-o‘rin!\n🏅 «{d['award']}» sertifikatingiz tayyor.\n"
            f"✅ {d['correct']}/{d['total']} to‘g‘ri javob ({d['percent']}%)\n\n🔎 Tekshirish kodi: {a['cert_code']}")


def summary_for(code, res):
    if not res["ok"]:
        return {"not_admin_test": "", "disabled": "", "already": f"ℹ️ {code} uchun sertifikatlar avval berilgan.",
                "no_winners": f"ℹ️ {code}: sertifikat beriladigan ishtirokchi yo‘q (hech kim to‘g‘ri javob bermagan yoki ishtirokchi yo‘q)."}.get(res["reason"], "ℹ️ " + str(res["reason"]))
    lines = [f"🏅 «{res['title']}» sertifikatlari yuborildi ({code}):"]
    for a in res["awards"]:
        lines.append(f"{a['rank']}-o‘rin — {a['name']} • {a['correct']}/{a['total']} • {a['cert_code']}")
    lines.append("\nNomni o‘zgartirish: /sert_nom " + code + " Yangi nom")
    return "\n".join(lines)


# ------------------------------------------------------------------ Telegram (admin buyruqlari)
def _is_admin(update):
    u = update.effective_user
    return bool(u and _CFG["admin_id"] is not None and int(u.id) == int(_CFG["admin_id"]))


async def sert_namuna_cmd(update, context):
    if not _is_admin(update):
        return
    import cert_award as ca
    cur = current_style()
    await update.message.reply_text("🎨 5 ta namuna tayyorlanyapti (bir necha soniya)…")
    for st in ca.STYLES:
        try:
            png = await asyncio.to_thread(ca.render, dict(ca.SAMPLE, style=st), "TP-NAMUNA0001", st)
            await update.message.reply_photo(io.BytesIO(png), caption=f"{st} — {ca.STYLE_NAMES[st]}" + ("  ✅ hozirgi" if st == cur else ""))
        except Exception:
            log.exception("sert_namuna %s", st)
    await update.message.reply_text("Tanlash: /sert_uslub 5D   (3D, 4D, 5D, 6D yoki 7D)")


async def sert_uslub_cmd(update, context):
    if not _is_admin(update):
        return
    import cert_award as ca
    args = context.args or []
    if not args:
        await update.message.reply_text("🎨 Hozirgi uslub: " + current_style() + "\n" + "\n".join(f"{s} — {ca.STYLE_NAMES[s]}" for s in ca.STYLES) + "\n\nO‘zgartirish: /sert_uslub 5D\nNamunalar: /sert_namuna")
        return
    if set_style(args[0]):
        await update.message.reply_text(f"✅ Endi yangi sertifikatlar {current_style()} uslubida beriladi. (Berilgan sertifikatlar o‘zgarmaydi.)")
    else:
        await update.message.reply_text("❌ Uslub: 3D, 4D, 5D, 6D yoki 7D.")


async def sert_nom_cmd(update, context):
    if not _is_admin(update):
        return
    args = context.args or []
    if len(args) < 1:
        await update.message.reply_text("Ishlatish:\n/sert_nom KOD Yangi nom — masalan: /sert_nom T-AB12CD G‘azal bilimdoni\n/sert_nom KOD auto — mavzudan avtomatik\n/sert_nom KOD - — bu testga sertifikat berilmasin")
        return
    code = args[0].upper()
    t = _test_row(code)
    if not t:
        await update.message.reply_text("❌ Bunday oddiy test topilmadi.")
        return
    if len(args) == 1:
        await update.message.reply_text(f"🏅 {code} uchun hozirgi nom: «{award_title_for(t) or 'o‘chirilgan'}»")
        return
    val = " ".join(args[1:]).strip()
    if val.lower() == "auto":
        set_title_override(code, "")
        await update.message.reply_text(f"✅ Avtomatik nom: «{derive_title(t.get('subject'), t.get('title'))}»")
    elif val == "-":
        set_title_override(code, "-")
        await update.message.reply_text("✅ Bu testga avtomatik sertifikat berilmaydi. (Qo‘lda: /sert_top " + code + ")")
    else:
        set_title_override(code, _apos(val))
        await update.message.reply_text(f"✅ Sertifikat nomi: «{_apos(val)[:60]}»")


async def sert_top_cmd(update, context):
    """Admin: testning 1–3-o‘rin sertifikatlarini hoziroq berish (test yakunlangan yoki yakunlanmagan bo‘lishidan qat’i nazar; bir marta)."""
    if not _is_admin(update):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text("Ishlatish: /sert_top KOD — shu testning 1–3-o‘rin sovrindorlariga sertifikat beradi (bir marta).")
        return
    code = args[0].upper()
    res = await asyncio.to_thread(issue, code, True)
    await update.message.reply_text(summary_for(code, res) or "ℹ️ Berilmadi.")
    if res["ok"]:
        await asyncio.to_thread(deliver, res)


def deliver(res, token=None):
    """Tayyor sertifikatlarni sovrindorlarga rasm qilib yuboradi (bloklovchi — oqimda chaqiring)."""
    import mini_extra as mx, time
    token = token or _CFG["token"]
    n = 0
    for a in res.get("awards", []):
        try:
            png = mx.render_certificate("topaward", a["data"], a["cert_code"])
            mx.send_photo(token, a["user_id"], png, caption_for(a))
            n += 1
            time.sleep(0.4)
        except Exception as e:
            log.warning("award send %s: %s", a.get("user_id"), e)
    return n


def register(app):
    from telegram.ext import CommandHandler
    app.add_handler(CommandHandler("sert_namuna", sert_namuna_cmd))
    app.add_handler(CommandHandler("sert_uslub", sert_uslub_cmd))
    app.add_handler(CommandHandler("sert_nom", sert_nom_cmd))
    app.add_handler(CommandHandler("sert_top", sert_top_cmd))
