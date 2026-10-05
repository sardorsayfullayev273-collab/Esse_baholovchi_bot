"""Qo'lda to'lov (admin kartasi + chek skrini + admin tasdig'i), narx paketlari va referal tizimi.

Asosiy bazadan (BOT_DB_PATH) foydalanadi. Telegram'ga bog'liq emas, shuning uchun alohida sinab ko'rish mumkin.
"""
import os
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
    "p3":  {"size": _i("PACK_ESSAYS", 3),   "stars": _i("PACK_STARS", 50),    "uzs": _i("PACK_UZS", 9000)},
    "p10": {"size": _i("PACK10_SIZE", 10),  "stars": _i("PACK10_STARS", 130), "uzs": _i("PACK10_UZS", 25000)},
    "p30": {"size": _i("PACK30_SIZE", 30),  "stars": _i("PACK30_STARS", 350), "uzs": _i("PACK30_UZS", 65000)},
}
GROWTH_STARS = _i("GROWTH_PRICE_STARS", 150)
GROWTH_UZS = _i("GROWTH_PRICE_UZS", 35000)
GROWTH_DAYS = 30
TEACHER_DEFAULT_PERCENT = _i("TEACHER_DEFAULT_PERCENT", 0)    # ustozga standart ulush (foiz); 0 = faqat o'quvchilarga chegirma
TEACHER_STUDENT_DISCOUNT = _i("TEACHER_STUDENT_DISCOUNT", 30)  # ustoz o'quvchilariga chegirma (foiz)

REF_MAX_REWARDS = _i("REF_MAX_REWARDS", 30)        # bitta odam taklif uchun olishi mumkin bo'lgan eng ko'p mukofot
REF_INVITER_BONUS = _i("REF_INVITER_BONUS", 1)     # taklif qilgan odamga (do'st 1-esseni tekshirtirgach)
REF_INVITEE_BONUS = _i("REF_INVITEE_BONUS", 1)     # taklif qilingan odamga (kanalga a'zo bo'lgach)

PROOF_TTL_HOURS = _i("PAY_PROOF_TTL_HOURS", 3)     # chek yuborish uchun muhlat
MAX_PENDING_PER_USER = _i("PAY_MAX_PENDING", 2)    # admin tekshiruvida turgan buyurtmalar chegarasi
MAX_ORDERS_PER_DAY = _i("PAY_MAX_ORDERS_DAY", 8)   # bir kunda yaratiladigan buyurtmalar chegarasi


def fmt_uzs(n):
    return f"{int(n):,}".replace(",", " ")


def valid_plan(kind, plan):
    if kind == "growth":
        return plan == "growth"
    return kind in ("essay", "tool") and plan in PACKS


def plan_title(kind, plan):
    if kind == "growth":
        return f"Esseni o‘stirish — {GROWTH_DAYS} kun"
    p = PACKS[plan]
    return f"{p['size']} ta esse tekshiruvi" if kind == "essay" else f"{p['size']} ta AI mashq/dalil"


def plan_amount_uzs(kind, plan):
    return GROWTH_UZS if kind == "growth" else PACKS[plan]["uzs"]


def plan_amount_stars(kind, plan):
    return GROWTH_STARS if kind == "growth" else PACKS[plan]["stars"]


def packs_public():
    return [{"id": k, "size": v["size"], "stars": v["stars"], "uzs": v["uzs"]} for k, v in PACKS.items()]


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
        c.execute("""CREATE TABLE IF NOT EXISTS teachers(user_id INTEGER PRIMARY KEY, percent INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS teacher_students(student_id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS teacher_commissions(id INTEGER PRIMARY KEY AUTOINCREMENT, teacher_id INTEGER NOT NULL, student_id INTEGER NOT NULL,
            order_ref TEXT NOT NULL UNIQUE, amount INTEGER NOT NULL, percent INTEGER NOT NULL, commission INTEGER NOT NULL, paid INTEGER NOT NULL DEFAULT 0, created_at TEXT)""")
        c.commit()


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

def price_uzs(uid, kind, plan):
    return _disc(plan_amount_uzs(kind, plan), student_discount(uid))

def price_stars(uid, kind, plan):
    return _disc(plan_amount_stars(kind, plan), student_discount(uid))

def packs_for(uid):
    """Foydalanuvchi uchun paketlar (chegirma bilan). old_* — chegirmagacha narx."""
    d = student_discount(uid)
    return [{"id": k, "size": v["size"], "stars": _disc(v["stars"], d), "uzs": _disc(v["uzs"], d),
             "old_stars": v["stars"], "old_uzs": v["uzs"], "discount": d} for k, v in PACKS.items()]


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


def attach_proof(order_id, file_id, unique_id, ptype):
    """'ok' | 'dup' (shu chek avval yuborilgan) | 'state' (buyurtma chek kutmayapti)."""
    with db() as c:
        if unique_id:
            dup = c.execute("SELECT 1 FROM manual_orders WHERE proof_unique_id=? AND id!=? AND status IN ('pending_review','approved') LIMIT 1", (unique_id, int(order_id))).fetchone()
            if dup:
                return "dup"
        cur = c.execute(
            "UPDATE manual_orders SET status='pending_review', proof_file_id=?, proof_unique_id=?, proof_type=?, updated_at=? "
            "WHERE id=? AND status='awaiting_proof'", (file_id, unique_id, ptype, now(), int(order_id)))
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


def revenue_summary():
    """Tasdiqlangan qo'lda to'lovlar: bugun / shu oy (so'm)."""
    t = datetime.now(TZ)
    day = t.replace(hour=0, minute=0, second=0, microsecond=0)
    month = day.replace(day=1)

    def iso(dt):
        return dt.astimezone(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"

    with db() as c:
        d = c.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM manual_orders WHERE status='approved' AND updated_at>=?", (iso(day),)).fetchone()
        m = c.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM manual_orders WHERE status='approved' AND updated_at>=?", (iso(month),)).fetchone()
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
