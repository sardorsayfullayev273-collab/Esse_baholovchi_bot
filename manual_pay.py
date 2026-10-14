"""Qo'lda to'lov (admin kartasi + chek skrini + admin tasdig'i), narx paketlari va referal tizimi.

Asosiy bazadan (BOT_DB_PATH) foydalanadi. Telegram'ga bog'liq emas, shuning uchun alohida sinab ko'rish mumkin.
"""
import hashlib
import hmac
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from national_certificate import db, setting, set_setting

TZ = timezone(timedelta(hours=5))  # Toshkent


def _i(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return int(default)


def now():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


# ---------------------------------------------------------------- Narxlar (hammasi Render Environment orqali o'zgaradi)
PACKS = {
    "p1":  {"size": _i("PACK1_SIZE", 1),    "stars": _i("PACK1_STARS", 22),    "uzs": _i("PACK1_UZS", 4000)},
    "p3":  {"size": _i("PACK_ESSAYS", 3),   "stars": _i("PACK_STARS", 50),    "uzs": _i("PACK_UZS", 9000)},
    "p10": {"size": _i("PACK10_SIZE", 10),  "stars": _i("PACK10_STARS", 130), "uzs": _i("PACK10_UZS", 25000)},
    "p30": {"size": _i("PACK30_SIZE", 30),  "stars": _i("PACK30_STARS", 350), "uzs": _i("PACK30_UZS", 65000)},
    # 7 kunlik "imtihon haftasi" paketi: kuniga PASS_DAILY_CAP tagacha esse (faqat esse tekshirish uchun)
    "w7":  {"size": 0, "days": _i("WEEK_PASS_DAYS", 7), "stars": _i("WEEK_PASS_STARS", 190), "uzs": _i("WEEK_PASS_UZS", 35000)},
}
FIRST_OFFER_PCT = _i("FIRST_OFFER_PCT", 30)        # bepul 3 ta tugagach, birinchi xarid uchun chegirma (foiz)
PASS_DAILY_CAP = _i("PASS_DAILY_CAP", 5)           # 7 kunlik paketda kuniga eng ko'pi bilan nechta esse
GROWTH_STARS = _i("GROWTH_PRICE_STARS", 150)
GROWTH_UZS = _i("GROWTH_PRICE_UZS", 35000)
GROWTH_DAYS = 30
# Ekspert (inson) tekshiruvi: 24 soat ichida natija. Narxlar Render Environment orqali o'zgaradi.
EXPERT_ONE_UZS = _i("EXPERT_ONE_UZS", 10000)     # 1 ta esse — doimiy narx
EXPERT_PACK_UZS = _i("EXPERT_PACK_UZS", 25000)   # imtihongacha maxsus imkoniyat: 3 ta esse
EXPERT_PACK_N = 3
EXPERT_HOURS = _i("EXPERT_HOURS", 24)
EXPERT_PLANS = {"e1": {"n": 1, "uzs": EXPERT_ONE_UZS}, "e3": {"n": EXPERT_PACK_N, "uzs": EXPERT_PACK_UZS}}
BOOKS_UZS = _i("BOOKS_UZS", 5000)   # Badiiy asarlar bo'limi (faqat karta)
GAZAL_LIB_UZS = _i("GAZAL_LIB_UZS", 25000)   # «G'azal tahlilini o'rganamiz» bo'limi (faqat karta; /gazal_narx bilan o'zgartiriladi)
GAZAL_GROUP_UZS = _i("GAZAL_GROUP_UZS", 15000)   # G'azal kursi guruhiga qo'shilish (faqat karta orqali)
TEACHER_DEFAULT_PERCENT = _i("TEACHER_DEFAULT_PERCENT", 0)    # ustozga standart ulush (foiz); 0 = faqat o'quvchilarga chegirma
TEACHER_STUDENT_DISCOUNT = _i("TEACHER_STUDENT_DISCOUNT", 30)  # ustoz o'quvchilariga chegirma (foiz)

REF_MAX_REWARDS = _i("REF_MAX_REWARDS", 30)        # bitta odam taklif uchun olishi mumkin bo'lgan eng ko'p mukofot
REF_INVITER_BONUS = _i("REF_INVITER_BONUS", 1)     # taklif qilgan odamga (do'st 1-esseni tekshirtirgach)
REF_INVITEE_BONUS = _i("REF_INVITEE_BONUS", 1)     # taklif qilingan odamga (kanalga a'zo bo'lgach)

PROOF_TTL_HOURS = _i("PAY_PROOF_TTL_HOURS", 24)    # chek yuborish uchun muhlat (v55: 3 soatdan 24 soatga — ko'p odam chekni kechroq yuborardi)
RECOVERY_PCT = _i("RECOVERY_PCT", 15)             # v55: to'lamay ketganlarga qaytish chegirmasi (foiz); 0 = o'chirilgan
RECOVERY_HOURS = _i("RECOVERY_HOURS", 24)         # qaytish chegirmasi amal qilish muddati (soat)
PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "").strip()   # v57: BotFather -> Payments (Click/Payme/Uzum) tokeni; bo'lsa to'lov AVTOMATIK
EXPERT_YEARS = _i("EXPERT_YEARS", 0)                    # ekspert tajribasi (yil) — to'lovdan oldin ko'rsatiladi
EXPERT_NOTE = os.getenv("EXPERT_EXPERIENCE_NOTE", "").strip()
EXPERT_BASE_CHECKED = _i("EXPERT_BASE_CHECKED", 20)      # ekspert HAQIQATDA tekshirgan esselar (deploy paytidagi son)
AI_BASE_CHECKED = _i("AI_BASE_CHECKED", 523)             # botda AI HAQIQATDA tekshirgan esselar (deploy paytidagi son)      # shu botdan oldin HAQIQATAN tekshirilgan esselar (ixtiyoriy, haqiqiy son)
EXPERT_BASE_USERS = _i("EXPERT_BASE_USERS", 0)
EXPERT_PROOF_MIN = _i("EXPERT_PROOF_MIN", 1)           # raqamlar shu sondan boshlab ko'rsatiladi
SMS_SECRET = os.getenv("PAY_WEBHOOK_SECRET", "").strip()   # v58: bank SMS/bildirishnomasini qabul qiluvchi webhook siri; bo'lsa karta to'lovi AVTOMATIK tasdiqlanadi
CARD_UNIQUE_MAX = _i("CARD_UNIQUE_MAX", 99)                  # v58: har buyurtmaga noyob qo'shimcha (0..N so'm) — to'lovni aniq buyurtmaga bog'lash uchun
CARD_REQUIRE_LAST4 = _i("CARD_REQUIRE_LAST4", 0)             # 1 bo'lsa SMS ichida karta oxirgi 4 raqami ham bo'lishi shart
TEACHER_PRO_UZS = _i("TEACHER_PRO_UZS", 50000)    # v56: Ustoz Pro — oyiga (faqat karta orqali)
TEACHER_PRO_DAYS = _i("TEACHER_PRO_DAYS", 30)
PREMIUM_BONUS_ESSAYS = _i("PREMIUM_BONUS_ESSAYS", 3)   # v55: Premium (30 kun) bilan birga beriladigan esse tekshiruvlari
MAX_PENDING_PER_USER = _i("PAY_MAX_PENDING", 2)    # admin tekshiruvida turgan buyurtmalar chegarasi
MAX_ORDERS_PER_DAY = _i("PAY_MAX_ORDERS_DAY", 8)   # bir kunda yaratiladigan buyurtmalar chegarasi


def fmt_uzs(n):
    return f"{int(n):,}".replace(",", " ")


def valid_plan(kind, plan):
    if kind == "mock":
        import mock_mod as _mk
        return str(plan).isdigit() and _mk.exists(int(plan))
    if kind == "teacher":
        return plan == "pro"
    if kind == "expert":
        return plan in EXPERT_PLANS
    if kind == "growth":
        return plan == "growth"
    if kind == "group":
        return plan == "gazal"
    if kind in ("books", "gazal_lib"):
        return plan == "all"
    if kind == "gazal_item":   # «G'azal tahlili» papkasi: plan = papka raqami
        try:
            import books_store as _bk
            return str(plan).isdigit() and _bk.get_sec(int(plan)) == "gazal"
        except Exception:
            return False
    if kind == "tool" and plan == "w7":
        return False   # 7 kunlik paket faqat esse tekshirish uchun
    return kind in ("essay", "tool") and plan in PACKS


def plan_title(kind, plan):
    if kind == "mock":
        import mock_mod as _mk
        return f"Mock imtihon: «{_mk.title_of(int(plan))}»"
    if kind == "teacher":
        return f"Ustoz Pro — {TEACHER_PRO_DAYS} kun"
    if kind == "expert":
        return "Ekspert esse tekshiruvi — 1 ta" if plan == "e1" else f"Ekspert esse tekshiruvi — {EXPERT_PACK_N} ta (imtihongacha maxsus imkoniyat)"
    if kind == "group":
        return "G‘azal kursi guruhiga qo‘shilish"
    if kind == "books":
        return "Badiiy asarlar bo‘limi (to‘liq kirish)"
    if kind == "gazal_lib":
        return "G‘azal tahlilini o‘rganamiz (to‘liq kirish)"
    if kind == "gazal_item":
        try:
            import books_store as _bk
            d = _bk.get_detail(int(plan))
            return f"G‘azal tahlili: «{d['title']}»" if d else "G‘azal tahlili: qo‘llanma"
        except Exception:
            return "G‘azal tahlili: qo‘llanma"
    if kind == "growth":
        return f"Esseni o‘stirish — {GROWTH_DAYS} kun"
    p = PACKS[plan]
    if p.get("days"):
        return f"{p['days']} kunlik esse paketi (kuniga {PASS_DAILY_CAP} tagacha)"
    return f"{p['size']} ta esse tekshiruvi" if kind == "essay" else f"{p['size']} ta AI mashq/dalil"


def plan_amount_uzs(kind, plan):
    if kind == "mock":
        import mock_mod as _mk
        return _mk.price()
    if kind == "teacher":
        return TEACHER_PRO_UZS
    if kind == "expert":
        return EXPERT_PLANS[plan]["uzs"]
    if kind == "books":
        return BOOKS_UZS
    if kind == "gazal_lib":
        return gazal_lib_price()
    if kind == "gazal_item":
        import books_store as _bk
        return _bk.item_price(int(plan))
    if kind == "group":
        return GAZAL_GROUP_UZS
    return GROWTH_UZS if kind == "growth" else PACKS[plan]["uzs"]


def plan_amount_stars(kind, plan):
    if kind in ("group", "books", "gazal_lib", "gazal_item", "expert", "teacher", "mock"):
        return 0   # faqat plastik karta orqali
    return GROWTH_STARS if kind == "growth" else PACKS[plan]["stars"]


def packs_public():
    return [{"id": k, "size": v["size"], "stars": v["stars"], "uzs": v["uzs"]} for k, v in PACKS.items() if not v.get("days")]


# ---------------------------------------------------------------- DB
def init_pay_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS manual_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            plan TEXT NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT NOT NULL,
            proof_file_id TEXT,
            proof_unique_id TEXT,
            proof_type TEXT,
            admin_msg_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            decided_by INTEGER,
            note TEXT)""")
        for _col in ("remind_n INTEGER NOT NULL DEFAULT 0", "remind_at TEXT"):
            try: c.execute("ALTER TABLE manual_orders ADD COLUMN " + _col)
            except Exception: pass
        try: c.execute("ALTER TABLE manual_orders ADD COLUMN proof_hash TEXT")
        except Exception: pass
        try:
            c.execute("ALTER TABLE manual_orders ADD COLUMN granted_at TEXT")
            c.execute("UPDATE manual_orders SET granted_at=updated_at WHERE status='approved'")   # eski buyurtmalar qayta berilmasin
        except Exception: pass
        c.execute("CREATE TABLE IF NOT EXISTS card_tx(tx_hash TEXT PRIMARY KEY, amount INTEGER, order_id INTEGER, status TEXT, at TEXT, raw TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS auto_pay(charge_id TEXT PRIMARY KEY, order_id INTEGER, user_id INTEGER, kind TEXT, plan TEXT, amount INTEGER, at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS pay_recovery(user_id INTEGER PRIMARY KEY, until TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS offer_nudged(user_id INTEGER PRIMARY KEY, at TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_manual_orders_user ON manual_orders(user_id, status)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_manual_orders_proof ON manual_orders(proof_unique_id)")
        c.execute("""CREATE TABLE IF NOT EXISTS referrals(
            invitee_id INTEGER PRIMARY KEY,
            inviter_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            invitee_bonus INTEGER NOT NULL DEFAULT 0,
            inviter_rewarded INTEGER NOT NULL DEFAULT 0,
            rewarded_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_referrals_inviter ON referrals(inviter_id)")
        c.execute("""CREATE TABLE IF NOT EXISTS expert_jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT, due_at TEXT, replied_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS expert_msgs(admin_msg_id INTEGER PRIMARY KEY, job_id INTEGER NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS expert_state(user_id INTEGER PRIMARY KEY, active INTEGER NOT NULL DEFAULT 0)""")
        c.execute("""CREATE TABLE IF NOT EXISTS group_members(user_id INTEGER NOT NULL, grp TEXT NOT NULL, order_id INTEGER, created_at TEXT, PRIMARY KEY(user_id, grp))""")
        c.execute("""CREATE TABLE IF NOT EXISTS teachers(user_id INTEGER PRIMARY KEY, percent INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS teacher_students(student_id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS teacher_commissions(id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
            order_ref TEXT NOT NULL UNIQUE, amount INTEGER NOT NULL, percent INTEGER NOT NULL, commission INTEGER NOT NULL, paid INTEGER NOT NULL DEFAULT 0, created_at TEXT)""")
        c.commit()
    try: expert_stats()   # boshlang'ich (deploy paytidagi) sonlarni eslab qoladi
    except Exception: pass


# ---------------------------------------------------------------- Karta rekvizitlari
def card_info():
    """(karta raqami, egasi). Avval /karta buyrug'i bilan saqlangan, bo'lmasa Environment'dan."""
    number = (setting("card_number", "") or os.getenv("ADMIN_CARD_NUMBER", "")).strip()
    holder = (setting("card_holder", "") or os.getenv("ADMIN_CARD_HOLDER", "")).strip()
    return number, holder


def set_card(number, holder):
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    set_setting("card_number", digits)
    set_setting("card_holder", holder.strip())
    return digits


def pretty_card(number):
    d = "".join(ch for ch in str(number) if ch.isdigit())
    return " ".join(d[i:i + 4] for i in range(0, len(d), 4))


# ---------------------------------------------------------------- Buyurtmalar
def student_discount(uid):
    """Foydalanuvchi faol ustozning o'quvchisi bo'lsa — chegirma foizi, aks holda 0."""
    if uid is None or TEACHER_STUDENT_DISCOUNT <= 0: return 0
    with db() as c:
        r = c.execute("SELECT 1 FROM teacher_students s JOIN teachers t ON t.user_id=s.teacher_id AND t.active=1 WHERE s.student_id=?", (int(uid),)).fetchone()
    return max(0, min(90, TEACHER_STUDENT_DISCOUNT)) if r else 0

def _disc(v, d):
    return max(1, int(v) * (100 - d) // 100) if d > 0 else int(v)

def first_offer(uid):
    """Birinchi xarid chegirmasi: (foiz, tugash vaqti Toshkent bo'yicha datetime) yoki None.
    Faqat bepul esselar tugagach 24 soat davomida va foydalanuvchi hali hech narsa sotib olmagan bo'lsa."""
    if uid is None or FIRST_OFFER_PCT <= 0: return None
    try:
        with db() as c:
            r = c.execute("SELECT until FROM first_offer WHERE user_id=?", (int(uid),)).fetchone()
            if not r or r[0] <= now(): return None
            if c.execute("SELECT 1 FROM star_payments WHERE user_id=? LIMIT 1", (int(uid),)).fetchone(): return None
            if c.execute("SELECT 1 FROM manual_orders WHERE user_id=? AND status='approved' AND kind IN ('essay','tool') LIMIT 1", (int(uid),)).fetchone(): return None
        until = datetime.fromisoformat(r[0].rstrip("Z")).replace(tzinfo=timezone.utc).astimezone(TZ)
        return max(0, min(90, FIRST_OFFER_PCT)), until
    except Exception:
        return None

def recovery_offer(uid):
    """v55: to'lamay ketgan buyurtma egasiga eslatma bilan beriladigan chegirma: foiz yoki None."""
    if uid is None or RECOVERY_PCT <= 0: return None
    try:
        with db() as c:
            r = c.execute("SELECT until FROM pay_recovery WHERE user_id=?", (int(uid),)).fetchone()
            if not r or r[0] <= now(): return None
            if c.execute("SELECT 1 FROM manual_orders WHERE user_id=? AND status='approved' AND kind IN ('essay','tool') LIMIT 1", (int(uid),)).fetchone(): return None
        return max(0, min(90, RECOVERY_PCT))
    except Exception:
        return None

def _best_disc(uid, kind):
    d = student_discount(uid)
    if kind in ("essay", "tool", None):
        fo = first_offer(uid)
        if fo: d = max(d, fo[0])
        rc = recovery_offer(uid)
        if rc: d = max(d, rc)
    return d

def price_uzs(uid, kind, plan):
    if kind in ("group", "books", "gazal_lib", "gazal_item", "expert", "teacher", "mock"):
        return plan_amount_uzs(kind, plan)   # qat'iy narx, chegirmasiz
    return _disc(plan_amount_uzs(kind, plan), _best_disc(uid, kind))

def price_stars(uid, kind, plan):
    return _disc(plan_amount_stars(kind, plan), _best_disc(uid, kind))

def packs_for(uid, kind=None):
    """Foydalanuvchi uchun paketlar (chegirma bilan). old_* — chegirmagacha narx. kind='tool' bo'lsa 7 kunlik paket kiritilmaydi."""
    d = _best_disc(uid, kind)
    return [{"id": k, "size": v["size"], "days": v.get("days", 0), "stars": _disc(v["stars"], d), "uzs": _disc(v["uzs"], d),
             "old_stars": v["stars"], "old_uzs": v["uzs"], "discount": d}
            for k, v in PACKS.items() if not (kind == "tool" and v.get("days"))]


def create_order(uid, kind, plan):
    """('ok', order_id) | ('limit', None) | ('invalid', None)."""
    if not valid_plan(kind, plan):
        return "invalid", None
    uid = int(uid)
    amount = price_uzs(uid, kind, plan)
    t = now()
    day_start = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    day_iso = day_start.replace(tzinfo=None).isoformat(timespec="seconds") + "Z"
    with db() as c:
        pending = c.execute("SELECT COUNT(*) FROM manual_orders WHERE user_id=? AND status='pending_review'", (uid,)).fetchone()[0]
        if pending >= MAX_PENDING_PER_USER:
            return "limit", None
        today = c.execute("SELECT COUNT(*) FROM manual_orders WHERE user_id=? AND created_at>=?", (uid, day_iso)).fetchone()[0]
        if today >= MAX_ORDERS_PER_DAY:
            return "limit", None
        c.execute("UPDATE manual_orders SET status='cancelled', updated_at=? WHERE user_id=? AND status='awaiting_proof'", (t, uid))
        if card_auto_enabled():   # v58: noyob summa — SMS orqali kelgan pul aynan shu buyurtmaga bog'lanadi
            amount = _unique_amount(c, amount)
            if amount is None:
                return "limit", None
        cur = c.execute(
            "INSERT INTO manual_orders(user_id,kind,plan,amount,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (uid, kind, plan, amount, "awaiting_proof", t, t))
        c.commit()
        return "ok", cur.lastrowid


def get_order(order_id):
    with db() as c:
        return c.execute("SELECT * FROM manual_orders WHERE id=?", (int(order_id),)).fetchone()


def awaiting_order(uid):
    """Foydalanuvchining chek kutayotgan (muddati o'tmagan) buyurtmasi."""
    limit = (datetime.utcnow() - timedelta(hours=PROOF_TTL_HOURS)).isoformat(timespec="seconds") + "Z"
    with db() as c:
        return c.execute(
            "SELECT * FROM manual_orders WHERE user_id=? AND status='awaiting_proof' AND created_at>=? ORDER BY id DESC LIMIT 1",
            (int(uid), limit)).fetchone()


def cancel_order(order_id, uid):
    with db() as c:
        cur = c.execute("UPDATE manual_orders SET status='cancelled', updated_at=? WHERE id=? AND user_id=? AND status='awaiting_proof'",
                        (now(), int(order_id), int(uid)))
        c.commit()
        return cur.rowcount == 1


def image_hash(data):
    """64-bitli o'xshashlik xeshi (aHash): qayta siqilgan/ozgina qirqilgan bir xil skrinshotni ham ushlaydi. Xato bo'lsa None."""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(bytes(data))).convert("L").resize((8, 8))
        px = list(im.getdata()); avg = sum(px) / 64.0
        return "%016x" % int("".join("1" if v >= avg else "0" for v in px), 2)
    except Exception:
        return None


def _ham(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def attach_proof(order_id, file_id, unique_id, ptype, phash=None):
    """'ok' | 'dup' (shu chek avval yuborilgan) | 'state' (buyurtma chek kutmayapti)."""
    with db() as c:
        if unique_id:
            dup = c.execute("SELECT 1 FROM manual_orders WHERE proof_unique_id=? AND id!=? AND status IN ('pending_review','approved') LIMIT 1", (unique_id, int(order_id))).fetchone()
            if dup:
                return "dup"
        if phash:
            for r in c.execute("SELECT proof_hash FROM manual_orders WHERE proof_hash IS NOT NULL AND id!=? AND status IN ('pending_review','approved')", (int(order_id),)).fetchall():
                try:
                    if _ham(r[0], phash) <= 4: return "dup"
                except Exception: pass
        cur = c.execute(
            "UPDATE manual_orders SET status='pending_review', proof_file_id=?, proof_unique_id=?, proof_type=?, proof_hash=?, updated_at=? "
            "WHERE id=? AND status='awaiting_proof'", (file_id, unique_id, ptype, phash, now(), int(order_id)))
        c.commit()
        return "ok" if cur.rowcount == 1 else "state"


def revert_to_awaiting(order_id):
    with db() as c:
        c.execute("UPDATE manual_orders SET status='awaiting_proof', proof_file_id=NULL, proof_unique_id=NULL, updated_at=? "
                  "WHERE id=? AND status='pending_review'", (now(), int(order_id)))
        c.commit()


def set_admin_msg(order_id, msg_id):
    with db() as c:
        c.execute("UPDATE manual_orders SET admin_msg_id=? WHERE id=?", (int(msg_id), int(order_id)))
        c.commit()


def decide(order_id, approve, admin_id, note=None):
    """Atomik qaror: faqat 'pending_review' holatidagi buyurtma bir marta tasdiqlanadi/rad etiladi."""
    with db() as c:
        cur = c.execute(
            "UPDATE manual_orders SET status=?, decided_by=?, note=?, updated_at=? WHERE id=? AND status='pending_review'",
            ("approved" if approve else "rejected", int(admin_id), note, now(), int(order_id)))
        c.commit()
        return cur.rowcount == 1


def undo_approval(order_id):
    """Berish (grant) muvaffaqiyatsiz bo'lsa — buyurtmani qayta ko'rib chiqishga qaytaradi."""
    with db() as c:
        c.execute("UPDATE manual_orders SET status='pending_review', decided_by=NULL, updated_at=? WHERE id=? AND status='approved'",
                  (now(), int(order_id)))
        c.commit()


def list_pending(limit=10):
    with db() as c:
        return c.execute("SELECT * FROM manual_orders WHERE status='pending_review' ORDER BY id LIMIT ?", (int(limit),)).fetchall()


def create_gift_order(uid, kind, plan, admin_id):
    """Admin bepul beradi: 0 so'mlik, tasdiqlangan buyurtma (audit uchun). Xizmatni chaqiruvchi beradi (claim_grant)."""
    t = now()
    with db() as c:
        cur = c.execute("INSERT INTO manual_orders(user_id,kind,plan,amount,status,created_at,updated_at,decided_by,note,granted_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (int(uid), kind, plan, 0, "approved", t, t, int(admin_id), "gift:%s" % int(admin_id), t))
        c.commit(); return cur.lastrowid


def revenue_summary():
    """Tasdiqlangan qo'lda to'lovlar: bugun / shu oy (so'm)."""
    t = datetime.now(TZ)
    day = t.replace(hour=0, minute=0, second=0, microsecond=0)
    month = day.replace(day=1)

    def iso(dt):
        return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"

    with db() as c:
        d = c.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM manual_orders WHERE status='approved' AND amount>0 AND updated_at>=?", (iso(day),)).fetchone()
        m = c.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM manual_orders WHERE status='approved' AND amount>0 AND updated_at>=?", (iso(month),)).fetchone()
    return {"day_n": d[0], "day_sum": d[1], "month_n": m[0], "month_sum": m[1]}


# ---------------------------------------------------------------- Kreditlar
def add_credits(uid, kind, n):
    with db() as c:
        c.execute("INSERT INTO ai_credits(user_id,kind,balance) VALUES(?,?,?) "
                  "ON CONFLICT(user_id,kind) DO UPDATE SET balance=balance+excluded.balance", (int(uid), kind, int(n)))
        c.commit()


# ---------------------------------------------------------------- Referal
def register_referral(invitee, inviter, is_new):
    """Faqat yangi foydalanuvchi va o'zini o'zi taklif qilmagan bo'lsa yoziladi."""
    invitee, inviter = int(invitee), int(inviter)
    if not is_new or invitee == inviter:
        return False
    with db() as c:
        cur = c.execute("INSERT OR IGNORE INTO referrals(invitee_id,inviter_id,created_at) VALUES(?,?,?)", (invitee, inviter, now()))
        c.commit()
        return cur.rowcount == 1


def give_invitee_bonus(invitee):
    """Kanalga a'zo bo'lgach bir marta: taklif qilingan odamga bonus. Bonus berilsa inviter_id qaytadi."""
    with db() as c:
        cur = c.execute("UPDATE referrals SET invitee_bonus=1 WHERE invitee_id=? AND invitee_bonus=0", (int(invitee),))
        if cur.rowcount != 1:
            return None
        row = c.execute("SELECT inviter_id FROM referrals WHERE invitee_id=?", (int(invitee),)).fetchone()
        c.commit()
    if REF_INVITEE_BONUS > 0:
        add_credits(invitee, "essay", REF_INVITEE_BONUS)
    return row[0] if row else None


def reward_inviter(invitee):
    """Taklif qilingan odam birinchi esseni tekshirtirgach, taklif qilganga mukofot (chegara bilan).
    Mukofot berilsa inviter_id, aks holda None."""
    with db() as c:
        row = c.execute("SELECT inviter_id, inviter_rewarded FROM referrals WHERE invitee_id=?", (int(invitee),)).fetchone()
        if not row or row[1]:
            return None
        inviter = row[0]
        given = c.execute("SELECT COUNT(*) FROM referrals WHERE inviter_id=? AND inviter_rewarded=1", (inviter,)).fetchone()[0]
        cur = c.execute("UPDATE referrals SET inviter_rewarded=?, rewarded_at=? WHERE invitee_id=? AND inviter_rewarded=0",
                        (1 if given < REF_MAX_REWARDS else 2, now(), int(invitee)))
        c.commit()
        if cur.rowcount != 1 or given >= REF_MAX_REWARDS:
            return None
    if REF_INVITER_BONUS > 0:
        add_credits(inviter, "essay", REF_INVITER_BONUS)
    return inviter


def ref_stats(uid):
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM referrals WHERE inviter_id=?", (int(uid),)).fetchone()[0]
        done = c.execute("SELECT COUNT(*) FROM referrals WHERE inviter_id=? AND inviter_rewarded=1", (int(uid),)).fetchone()[0]
    return {"invited": total, "rewarded": done, "left": max(0, REF_MAX_REWARDS - done)}


def top_referrers(limit=10):
    with db() as c:
        return c.execute(
            "SELECT r.inviter_id AS uid, COUNT(*) AS invited, SUM(CASE WHEN r.inviter_rewarded=1 THEN 1 ELSE 0 END) AS active, "
            "COALESCE(u.username,'') AS username, COALESCE(u.first_name,'') AS first_name "
            "FROM referrals r LEFT JOIN users u ON u.user_id=r.inviter_id GROUP BY r.inviter_id ORDER BY active DESC, invited DESC LIMIT ?",
            (int(limit),)).fetchall()


# ---------------------------------------------------------------- Ustozlar hamkorligi (hisob-kitob; to'lov qo'lda)
def teacher_set(uid, percent):
    percent = max(0, min(90, int(percent)))
    with db() as c:
        c.execute("INSERT INTO teachers(user_id,percent,active,created_at) VALUES(?,?,1,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET percent=excluded.percent, active=1", (int(uid), percent, now()))
        c.commit()
    return percent

def teacher_off(uid):
    with db() as c:
        cur = c.execute("UPDATE teachers SET active=0 WHERE user_id=?", (int(uid),)); c.commit()
        return cur.rowcount == 1

def teacher_get(uid):
    with db() as c:
        return c.execute("SELECT * FROM teachers WHERE user_id=? AND active=1", (int(uid),)).fetchone()

def register_teacher_student(student, teacher, is_new):
    """Faqat yangi foydalanuvchi, faol ustoz, o'zini o'zi emas, va hali ustozga biriktirilmagan bo'lsa."""
    student, teacher = int(student), int(teacher)
    if not is_new or student == teacher or not teacher_get(teacher):
        return False
    with db() as c:
        cur = c.execute("INSERT OR IGNORE INTO teacher_students(student_id,teacher_id,created_at) VALUES(?,?,?)", (student, teacher, now()))
        c.commit()
        return cur.rowcount == 1

def record_commission(student, order_ref, amount_uzs):
    """Talaba to'lov qilganda ustozga ulushni yozadi (bir buyurtma = bir marta). Yozilsa (ustoz_id, summa), aks holda None."""
    with db() as c:
        row = c.execute("SELECT t.user_id, t.percent FROM teacher_students s JOIN teachers t ON t.user_id=s.teacher_id AND t.active=1 "
                        "WHERE s.student_id=?", (int(student),)).fetchone()
        if not row or int(amount_uzs) <= 0: return None
        tid, pct = int(row[0]), int(row[1]); com = int(amount_uzs) * pct // 100
        cur = c.execute("INSERT OR IGNORE INTO teacher_commissions(teacher_id,student_id,order_ref,amount,percent,commission,created_at) VALUES(?,?,?,?,?,?,?)",
                        (tid, int(student), str(order_ref), int(amount_uzs), pct, com, now()))
        c.commit()
        return (tid, com) if cur.rowcount == 1 else None

def teacher_summary(uid):
    with db() as c:
        st = c.execute("SELECT COUNT(*) FROM teacher_students WHERE teacher_id=?", (int(uid),)).fetchone()[0]
        r = c.execute("SELECT COUNT(*), COALESCE(SUM(amount),0), COALESCE(SUM(commission),0), COALESCE(SUM(CASE WHEN paid=0 THEN commission ELSE 0 END),0) "
                      "FROM teacher_commissions WHERE teacher_id=?", (int(uid),)).fetchone()
    return {"students": st, "sales_n": r[0], "sales_sum": r[1], "commission": r[2], "unpaid": r[3]}

def teachers_report():
    with db() as c:
        rows = c.execute("SELECT t.user_id, t.percent, t.active, COALESCE(u.username,'') un, COALESCE(u.first_name,'') fn FROM teachers t LEFT JOIN users u ON u.user_id=t.user_id ORDER BY t.created_at").fetchall()
    return [(r, teacher_summary(r["user_id"])) for r in rows]

def teacher_mark_paid(uid):
    with db() as c:
        s = c.execute("SELECT COALESCE(SUM(commission),0) FROM teacher_commissions WHERE teacher_id=? AND paid=0", (int(uid),)).fetchone()[0]
        c.execute("UPDATE teacher_commissions SET paid=1 WHERE teacher_id=? AND paid=0", (int(uid),)); c.commit()
    return s


# ---------------------------------------------------------------- Guruh (G'azal kursi)
def group_link():
    """Guruhga taklif havolasi: avval /guruh buyrug'i bilan saqlangan, bo'lmasa Environment (GAZAL_GROUP_LINK)."""
    return (setting("gazal_group_link", "") or os.getenv("GAZAL_GROUP_LINK", "")).strip()

def set_group_link(link):
    set_setting("gazal_group_link", link.strip())

def group_add(uid, grp, order_id):
    with db() as c:
        c.execute("INSERT OR IGNORE INTO group_members(user_id,grp,order_id,created_at) VALUES(?,?,?,?)", (int(uid), grp, int(order_id), now()))
        c.commit()

def group_has(uid, grp="gazal"):
    with db() as c:
        return c.execute("SELECT 1 FROM group_members WHERE user_id=? AND grp=?", (int(uid), grp)).fetchone() is not None

def group_count(grp="gazal"):
    with db() as c:
        return c.execute("SELECT COUNT(*) FROM group_members WHERE grp=?", (grp,)).fetchone()[0]


# ---------------------------------------------------------------- Badiiy asarlar
def gazal_lib_price():
    try: return max(1000, int(setting("gazal_lib_uzs", "") or GAZAL_LIB_UZS))
    except Exception: return GAZAL_LIB_UZS

def gazal_lib_open():
    return setting("gazal_lib_open", "1") == "1"

def set_gazal_lib_open(v):
    set_setting("gazal_lib_open", "1" if v else "0")

def books_ready():
    return setting("books_ready", "0") == "1"

def set_books_ready(v):
    set_setting("books_ready", "1" if v else "0")


# ---------------------------------------------------------------- Ekspert tekshiruvi (v52)
def auto_pay_enabled():
    return bool(PROVIDER_TOKEN)


def invoice_payload(uid, kind, plan):
    return f"uzs|{kind}|{plan}|{int(uid)}"


def parse_invoice_payload(p):
    parts = str(p or "").split("|")
    if len(parts) != 4 or parts[0] != "uzs" or not parts[3].isdigit(): return None
    return parts[1], parts[2], int(parts[3])


def create_auto_order(uid, kind, plan, amount_uzs, charge_id):
    """Avtomatik (karta/provayder) to'lov: tasdiqlangan buyurtma yozadi. ('ok', oid) | ('dup', oid). Bir charge_id — bir marta."""
    uid = int(uid); t = now()
    with db() as c:
        r = c.execute("SELECT order_id FROM auto_pay WHERE charge_id=?", (str(charge_id),)).fetchone()
        if r: return "dup", int(r[0])
        c.execute("UPDATE manual_orders SET status='cancelled', updated_at=? WHERE user_id=? AND status='awaiting_proof'", (t, uid))
        cur = c.execute("INSERT INTO manual_orders(user_id,kind,plan,amount,status,created_at,updated_at,decided_by,note) VALUES(?,?,?,?,?,?,?,?,?)",
                        (uid, kind, plan, int(amount_uzs), "approved", t, t, 0, "auto:" + str(charge_id)))
        oid = cur.lastrowid
        c.execute("INSERT INTO auto_pay(charge_id,order_id,user_id,kind,plan,amount,at) VALUES(?,?,?,?,?,?,?)", (str(charge_id), oid, uid, kind, plan, int(amount_uzs), t))
        c.commit()
    return "ok", oid


def _floor_count(n):
    """Haqiqiy sondan oshmaydigan yumaloqlash (23 -> 20, 140 -> 140, 1234 -> 1200)."""
    n = int(n)
    if n < 10: return n
    step = 5 if n < 50 else 10 if n < 200 else 50 if n < 1000 else 100
    return n // step * step


def _more_than(n, noun):
    f = _floor_count(n)
    return f"{f} ta {noun}" if n < 10 else (f"{f} tadan ortiq {noun}" if noun == "esse" else f"{f} dan ortiq {noun}")


def _baseline(key, live):
    """Birinchi marta chaqirilganda joriy HAQIQIY sonni eslab qoladi: ko'rsatiladigan son = boshlang'ich + (keyingi o'sish)."""
    v = setting(key, "")
    if v == "":
        set_setting(key, str(int(live))); return int(live)
    try: return int(v)
    except Exception: return int(live)


def expert_stats():
    """Ko'rsatkichlar: ekspert tekshirgan esselar (EXPERT_BASE_CHECKED + keyingi haqiqiy o'sish), AI tekshirgan esselar (AI_BASE_CHECKED + o'sish), o'rtacha javob vaqti."""
    with db() as c:
        live_exp = c.execute("SELECT COUNT(*) FROM expert_jobs WHERE status IN ('done','replied')").fetchone()[0]
        rows = c.execute("SELECT created_at, replied_at FROM expert_jobs WHERE status IN ('done','replied') AND replied_at IS NOT NULL ORDER BY id DESC LIMIT 100").fetchall()
        try: live_ai = c.execute("SELECT COUNT(*) FROM checks WHERE mode IN ('text','photo','pdf','image')").fetchone()[0]
        except Exception: live_ai = None
    hrs = []
    for r in rows:
        try: hrs.append((datetime.fromisoformat(str(r[1]).rstrip("Z")) - datetime.fromisoformat(str(r[0]).rstrip("Z"))).total_seconds() / 3600)
        except Exception: pass
    hrs.sort(); avg = round(hrs[len(hrs) // 2], 1) if len(hrs) >= 5 else None
    exp_total = EXPERT_BASE_CHECKED + max(0, live_exp - _baseline("expert_checked_baseline", live_exp))
    ai_total = None
    if live_ai is not None:
        ai_total = AI_BASE_CHECKED + max(0, live_ai - _baseline("ai_checked_baseline", live_ai))
    return {"expert_checked": exp_total, "ai_checked": ai_total, "avg_hours": avg}


def expert_proof():
    """To'lovdan oldin ko'rsatiladigan ishonch qatorlari (ekspertning ismi/aloqasi YO'Q). Raqamlar xizmat ishlagani sari o'zi oshadi."""
    s = expert_stats(); lines = []
    if EXPERT_YEARS > 0: lines.append(f"🎓 Ekspertlikda {EXPERT_YEARS} yillik tajriba")
    if EXPERT_NOTE: lines.append(f"📚 {EXPERT_NOTE}")
    if s["ai_checked"] and s["ai_checked"] >= EXPERT_PROOF_MIN: lines.append(f"🤖 Botda hozirgacha {s['ai_checked']} ta esse sun’iy intellekt tomonidan tekshirilgan")
    if s["expert_checked"] >= EXPERT_PROOF_MIN: lines.append(f"👨‍🏫 {s['expert_checked']} ta esse ekspert tomonidan tekshirilgan")
    if s["avg_hours"] is not None: lines.append(f"⏱ O‘rtacha javob vaqti: ~{s['avg_hours']:g} soat")
    return lines


def expert_public(uid=None):
    return {"one_uzs": EXPERT_ONE_UZS, "pack_uzs": EXPERT_PACK_UZS, "pack_n": EXPERT_PACK_N, "hours": EXPERT_HOURS,
            "balance": expert_balance(uid) if uid else 0, "proof": expert_proof(), "auto_pay": auto_pay_enabled()}

def expert_balance(uid):
    with db() as c:
        r = c.execute("SELECT balance FROM ai_credits WHERE user_id=? AND kind='expert'", (int(uid),)).fetchone()
    return int(r[0]) if r else 0

def expert_set_active(uid, on):
    with db() as c:
        c.execute("INSERT INTO expert_state(user_id,active) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET active=excluded.active", (int(uid), 1 if on else 0))
        c.commit()

def expert_active(uid):
    with db() as c:
        r = c.execute("SELECT active FROM expert_state WHERE user_id=?", (int(uid),)).fetchone()
    return bool(r and r[0])

def expert_consume(uid):
    """Bitta ekspert tekshiruvini yechadi. True — yechildi."""
    with db() as c:
        cur = c.execute("UPDATE ai_credits SET balance=balance-1 WHERE user_id=? AND kind='expert' AND balance>0", (int(uid),))
        c.commit(); return cur.rowcount > 0

def expert_refund(uid):
    add_credits(uid, "expert", 1)

def expert_new_job(uid):
    t = now(); due = (datetime.utcnow() + timedelta(hours=EXPERT_HOURS)).isoformat(timespec="seconds") + "Z"
    with db() as c:
        cur = c.execute("INSERT INTO expert_jobs(user_id,status,created_at,due_at) VALUES(?,?,?,?)", (int(uid), "open", t, due))
        c.commit(); return cur.lastrowid, due

def expert_link_msg(admin_msg_id, job_id):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO expert_msgs(admin_msg_id,job_id) VALUES(?,?)", (int(admin_msg_id), int(job_id))); c.commit()

def expert_job_by_msg(admin_msg_id):
    with db() as c:
        r = c.execute("SELECT j.id,j.user_id,j.status FROM expert_msgs m JOIN expert_jobs j ON j.id=m.job_id WHERE m.admin_msg_id=?", (int(admin_msg_id),)).fetchone()
    return {"id": r[0], "user_id": r[1], "status": r[2]} if r else None

def expert_mark_replied(job_id):
    with db() as c:
        c.execute("UPDATE expert_jobs SET status='done', replied_at=? WHERE id=?", (now(), int(job_id))); c.commit()

def expert_open_jobs(limit=30):
    with db() as c:
        rows = c.execute("SELECT id,user_id,created_at,due_at FROM expert_jobs WHERE status='open' ORDER BY due_at LIMIT ?", (int(limit),)).fetchall()
    return [{"id": r[0], "user_id": r[1], "created_at": r[2], "due_at": r[3]} for r in rows]


# ---------------------------------------------------------------- v58: ADMIN KARTASIGA AVTOMATIK TO'LOV
# Oqim: buyurtma noyob summa oladi (masalan 50 000 + 17 = 50 017) -> foydalanuvchi admin kartasiga o'tkazadi ->
# admin telefonidagi SMS-yo'naltiruvchi ilova bank SMS'ini /api/pay/sms ga yuboradi -> summa buyurtmaga mos kelsa, xizmat o'zi ochiladi.
def card_auto_enabled():
    number, _ = card_info()
    return bool(SMS_SECRET and number)


def check_secret(given):
    return bool(SMS_SECRET) and hmac.compare_digest(str(given or ""), SMS_SECRET)


def _unique_amount(c, base):
    """Hozir ochiq (chek kutayotgan/tekshiruvdagi) buyurtmalar band qilmagan eng kichik base+k (k=0..CARD_UNIQUE_MAX)."""
    limit = (datetime.utcnow() - timedelta(hours=PROOF_TTL_HOURS)).isoformat(timespec="seconds") + "Z"
    rows = c.execute("SELECT amount FROM manual_orders WHERE status IN ('awaiting_proof','pending_review') AND created_at>=? AND amount BETWEEN ? AND ?",
                     (limit, int(base), int(base) + CARD_UNIQUE_MAX)).fetchall()
    used = {int(r[0]) for r in rows}
    for k in range(0, CARD_UNIQUE_MAX + 1):
        if int(base) + k not in used:
            return int(base) + k
    return None


_NEG = re.compile(r"(spisan|списан|snyat|chiqim|oplata|оплата|pokupka|покупка|to['‘’`]?lov\s+amalga|платеж|payment\s+to|withdraw|debit|yechildi|yechib)", re.I)
_POS = re.compile(r"(popolnen|пополнен|zachisl|зачисл|kirim|поступл|postuplen|perevod\s+na|перевод\s+на|o['‘’`]?tkazma|to['‘’`]?ldirildi|received|credit|\+\s*\d)", re.I)
_AMT = re.compile(r"([+\-]?)\s*(\d{1,3}(?:[ \u00a0\u202f,]\d{3})+|\d+)(?:[.,](\d{1,2}))?\s*(?:UZS|uzs|sum|so['‘’`]?m|сум|сўм)", re.I)


def parse_bank_sms(text):
    """Bank SMS'idan KIRIM summasini (so'm, butun) ajratadi. Chiqim/noaniq bo'lsa None."""
    t = str(text or "")
    if not t.strip():
        return None
    if _NEG.search(t) and not _POS.search(t):
        return None
    for m in _AMT.finditer(t):
        sign, whole, frac = m.group(1), m.group(2), m.group(3)
        if sign == "-":
            continue
        digits = re.sub(r"[ \u00a0\u202f,]", "", whole)
        if not digits.isdigit():
            continue
        amt = int(digits)
        if frac and int(frac) != 0 and len(frac) == 2 and frac != "00":
            continue   # tiyinli kirim — noyob summa so'mda bo'ladi, mos kelmaydi
        if 1000 <= amt <= 100_000_000:
            return amt
    return None


def process_bank_sms(text):
    """Webhook kirishi. Qaytaradi: (status, order_id|None, amount|None)
    status: 'matched' | 'dup' | 'no_amount' | 'no_order' | 'ambiguous' | 'wrong_card'."""
    amount = parse_bank_sms(text)
    if amount is None:
        return "no_amount", None, None
    number, _ = card_info()
    if CARD_REQUIRE_LAST4 and number and number[-4:] not in re.sub(r"\s", "", str(text)):
        return "wrong_card", None, amount
    h = hashlib.sha256(str(text).strip().encode("utf-8")).hexdigest()
    t = now()
    limit = (datetime.utcnow() - timedelta(hours=PROOF_TTL_HOURS)).isoformat(timespec="seconds") + "Z"
    with db() as c:
        if c.execute("SELECT 1 FROM card_tx WHERE tx_hash=?", (h,)).fetchone():
            return "dup", None, amount
        rows = c.execute("SELECT id FROM manual_orders WHERE amount=? AND status IN ('awaiting_proof','pending_review') AND created_at>=? ORDER BY id",
                         (amount, limit)).fetchall()
        if len(rows) == 0:
            c.execute("INSERT INTO card_tx(tx_hash,amount,order_id,status,at,raw) VALUES(?,?,?,?,?,?)", (h, amount, None, "no_order", t, str(text)[:500])); c.commit()
            return "no_order", None, amount
        if len(rows) > 1:
            c.execute("INSERT INTO card_tx(tx_hash,amount,order_id,status,at,raw) VALUES(?,?,?,?,?,?)", (h, amount, None, "ambiguous", t, str(text)[:500])); c.commit()
            return "ambiguous", None, amount
        oid = int(rows[0][0])
        cur = c.execute("UPDATE manual_orders SET status='approved', decided_by=0, note=?, updated_at=? WHERE id=? AND status IN ('awaiting_proof','pending_review')",
                        ("sms:" + h[:12], t, oid))
        if cur.rowcount != 1:
            return "no_order", None, amount
        c.execute("INSERT INTO card_tx(tx_hash,amount,order_id,status,at,raw) VALUES(?,?,?,?,?,?)", (h, amount, oid, "matched", t, str(text)[:500]))
        c.commit()
    return "matched", oid, amount


def claim_grant(order_id):
    """Xizmatni berish huquqini atomik egallaydi (ikki marta berilmasligi uchun). True — egalladingiz."""
    with db() as c:
        cur = c.execute("UPDATE manual_orders SET granted_at=? WHERE id=? AND status='approved' AND granted_at IS NULL", (now(), int(order_id)))
        c.commit()
        return cur.rowcount == 1


def release_grant(order_id):
    """Berish muvaffaqiyatsiz bo'lsa — keyingi urinish uchun qaytaradi."""
    with db() as c:
        c.execute("UPDATE manual_orders SET granted_at=NULL WHERE id=?", (int(order_id),)); c.commit()


def ungranted_auto(limit=20):
    """Avtomatik (SMS yoki Telegram-provayder) tasdiqlangan, lekin xizmati hali berilmagan buyurtmalar."""
    with db() as c:
        return c.execute("SELECT * FROM manual_orders WHERE status='approved' AND granted_at IS NULL AND (note LIKE 'sms:%' OR note LIKE 'auto:%') ORDER BY id LIMIT ?", (int(limit),)).fetchall()


def card_tx_recent(limit=15):
    with db() as c:
        return c.execute("SELECT amount, order_id, status, at FROM card_tx ORDER BY rowid DESC LIMIT ?", (int(limit),)).fetchall()
