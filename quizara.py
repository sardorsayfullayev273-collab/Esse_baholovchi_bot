# -*- coding: utf-8 -*-
"""v130 — «Mashq 2.0 / Bosqich A»: ⭐ yulduz hisobi, 7 kunlik sovg'a, kunlik vazifalar.
Hammasi SERVERDA hisoblanadi (mijoz faqat ko'rsatadi): yulduz faqat serverda tekshirilgan natijadan beriladi.
• Yulduz manbalari: o'yin natijasi (game_plays.points — kunlik chegara va «kuniga bir marta» qoidalari allaqachon qo'llangan), duel g'alabasi (+10, kuniga 3 tagacha),
  kunlik sovg'a (7 kunlik zanjir), kunlik vazifalar. Har bir tushum qz_ledger da bitta qatorda (UNIQUE user+reason+ref) — takror berilmaydi.
• Vazifalar o'yin tarixidan (game_plays) hisoblanadi — alohida hisoblagich yo'q, aldab bo'lmaydi."""
import secrets
from datetime import datetime, timedelta, timezone
from national_certificate import db, now

TZ = timezone(timedelta(hours=5))   # Toshkent
GIFT = (10, 15, 20, 25, 30, 40, 50)  # 1..7-kun
DUEL_WIN = 10
DUEL_WIN_PER_DAY = 3
TASKS = (
    {'id': 'play',    'title': '1 ta o‘yin o‘ynang',           'need': 1,  'reward': 10},
    {'id': 'correct', 'title': '10 ta to‘g‘ri javob bering',   'need': 10, 'reward': 15},
    {'id': 'daily',   'title': 'Kunlik 5 savolni bajaring',    'need': 1,  'reward': 20},
)
_ready = False


def _today(): return datetime.now(TZ).strftime('%Y-%m-%d')
def _day_start_utc():
    d = datetime.now(TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return d.astimezone(timezone.utc).isoformat(timespec='seconds')


def _yesterday(): return (datetime.now(TZ) - timedelta(days=1)).strftime('%Y-%m-%d')


def init():
    global _ready
    if _ready: return
    import mini_extra as _mx
    _mx._games_init()   # game_plays jadvali (vazifalar shundan hisoblanadi)
    with db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS qz_wallet(user_id INTEGER PRIMARY KEY, stars INTEGER NOT NULL DEFAULT 0, updated_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS qz_ledger(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, delta INTEGER, reason TEXT, ref TEXT, created_at TEXT, UNIQUE(user_id, reason, ref))")
        c.execute("CREATE TABLE IF NOT EXISTS qz_gift(user_id INTEGER PRIMARY KEY, last_day TEXT, day_no INTEGER NOT NULL DEFAULT 0)")
        # v131: raqib (ghost), viloyatlar, turnir
        c.execute("CREATE TABLE IF NOT EXISTS qz_ghost(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, seed INTEGER, correct INTEGER, total INTEGER, log TEXT, created_at TEXT)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_qz_ghost_u ON qz_ghost(user_id, created_at)")
        c.execute("CREATE TABLE IF NOT EXISTS qz_ghost_seen(user_id INTEGER, ghost_id INTEGER, created_at TEXT, PRIMARY KEY(user_id, ghost_id))")
        c.execute("CREATE TABLE IF NOT EXISTS qz_region_user(user_id INTEGER PRIMARY KEY, region TEXT, set_at REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS qz_region_play(user_id INTEGER, day TEXT, region TEXT, correct INTEGER, total INTEGER, PRIMARY KEY(user_id, day))")
        c.execute("CREATE TABLE IF NOT EXISTS qz_tour(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, start_at REAL, end_at REAL, per_q INTEGER DEFAULT 15, prizes TEXT, min_plays INTEGER DEFAULT 3, status TEXT DEFAULT 'open', created_at TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS qz_tour_q(tour_id INTEGER, idx INTEGER, q TEXT, opts TEXT, ans INTEGER, PRIMARY KEY(tour_id, idx))")
        c.execute("CREATE TABLE IF NOT EXISTS qz_tour_play(tour_id INTEGER, user_id INTEGER, started_at REAL, finished_at REAL, correct INTEGER, ms INTEGER, PRIMARY KEY(tour_id, user_id))")
        c.commit()
    _ready = True


def _credit(c, uid, delta, reason, ref):
    """Bitta ledger qatori + hamyon. Takror (bir xil user+reason+ref) bo'lsa 0 qaytaradi. `c` — ochiq ulanish (commit tashqarida)."""
    cur = c.execute("INSERT OR IGNORE INTO qz_ledger(user_id,delta,reason,ref,created_at) VALUES(?,?,?,?,?)", (uid, int(delta), reason, str(ref), now()))
    if cur.rowcount != 1: return 0
    c.execute("INSERT INTO qz_wallet(user_id,stars,updated_at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET stars=stars+excluded.stars, updated_at=excluded.updated_at", (uid, int(delta), now()))
    return int(delta)


def stars(uid):
    init()
    with db() as c:
        r = c.execute("SELECT stars FROM qz_wallet WHERE user_id=?", (uid,)).fetchone()
    return int(r[0]) if r else 0


# ------------------------------------------------------------------ sovg'a
def _gift_view(uid):
    with db() as c:
        r = c.execute("SELECT last_day, day_no FROM qz_gift WHERE user_id=?", (uid,)).fetchone()
    last, no = (r[0], int(r[1])) if r else ('', 0)
    today, yest = _today(), _yesterday()
    if last == today: claimed, done, cur = True, no, no
    elif last == yest and no < 7: claimed, done, cur = False, no, no + 1
    else: claimed, done, cur = False, 0, 1          # zanjir uzilgan yoki 7-kundan keyin qaytadan
    days = [{'n': i + 1, 'reward': GIFT[i], 'state': ('done' if i + 1 <= done else 'today' if (i + 1 == cur and not claimed) else 'locked')} for i in range(7)]
    return {'claimed_today': claimed, 'day': cur, 'reward': GIFT[cur - 1], 'days': days, 'streak': done}


def claim_gift(uid):
    """(natija, xato). Kuniga bir marta."""
    init(); v = _gift_view(uid)
    if v['claimed_today']: return None, 'Bugungi sovg‘a allaqachon olingan.'
    day, rew, today = v['day'], v['reward'], _today()
    with db() as c:
        got = _credit(c, uid, rew, 'gift', today)
        if not got: return None, 'Bugungi sovg‘a allaqachon olingan.'
        c.execute("INSERT INTO qz_gift(user_id,last_day,day_no) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET last_day=excluded.last_day, day_no=excluded.day_no", (uid, today, day))
        c.commit()
    return {'gained': rew, 'day': day, 'stars': stars(uid)}, None


# ------------------------------------------------------------------ vazifalar
def _progress(uid):
    day = _today()
    with db() as c:
        rows = c.execute("SELECT game, correct FROM game_plays WHERE user_id=? AND day=?", (uid, day)).fetchall()
    plays = len(rows); corr = sum(int(r[1] or 0) for r in rows); daily = 1 if any(r[0] == 'daily' for r in rows) else 0
    return {'play': plays, 'correct': corr, 'daily': daily}


def tasks_view(uid):
    init(); pr = _progress(uid); day = _today()
    with db() as c:
        cl = {r[0] for r in c.execute("SELECT ref FROM qz_ledger WHERE user_id=? AND reason='task' AND ref LIKE ?", (uid, day + ':%'))}
    out = []
    for t in TASKS:
        have = min(pr.get(t['id'], 0), t['need'])
        out.append({'id': t['id'], 'title': t['title'], 'need': t['need'], 'have': have, 'reward': t['reward'],
                    'done': have >= t['need'], 'claimed': (day + ':' + t['id']) in cl})
    return out


def claim_task(uid, tid):
    init(); t = next((x for x in tasks_view(uid) if x['id'] == tid), None)
    if not t: return None, 'Noma’lum vazifa.'
    if not t['done']: return None, 'Vazifa hali bajarilmagan.'
    if t['claimed']: return None, 'Mukofot allaqachon olingan.'
    with db() as c:
        got = _credit(c, uid, t['reward'], 'task', _today() + ':' + tid); c.commit()
    if not got: return None, 'Mukofot allaqachon olingan.'
    return {'gained': got, 'stars': stars(uid), 'tasks': tasks_view(uid)}, None


# ------------------------------------------------------------------ o'yin natijasi -> yulduz
def after_submit(uid, game, correct, total, gained_points=0, already=False, meta=None):
    """O'yin saqlangach chaqiriladi. {'stars_gained','stars','duel_bonus'} qaytaradi (hech qachon xato ko'tarmaydi)."""
    init(); meta = meta or {}; gained = 0; bonus = 0; ghost_res = None
    try:
        gp = 0 if already else max(0, int(gained_points or 0))
        with db() as c:
            if gp: gained += _credit(c, uid, gp, 'play', secrets.token_hex(6))
            if game == 'duel' and meta.get('mode') == 'ghost':
                ghost_res = _settle_ghost(c, uid, meta.get('ghost_id'), correct)
                if ghost_res: gained += ghost_res['bonus']
            elif game == 'duel' and not already:
                try: vs = int(meta.get('vs')); seed = int(meta.get('seed')); cor = int(correct)
                except Exception: vs = seed = cor = None
                if vs is not None and 0 <= vs < cor and 0 < seed < 10 ** 9:
                    n = c.execute("SELECT COUNT(*) FROM qz_ledger WHERE user_id=? AND reason='duelwin' AND created_at>=?", (uid, _day_start_utc())).fetchone()[0]
                    if n < DUEL_WIN_PER_DAY: bonus = _credit(c, uid, DUEL_WIN, 'duelwin', 'seed:%s' % seed); gained += bonus
            if game == 'duel': _save_ghost(c, uid, meta.get('seed'), correct, total, meta.get('log'))
            c.commit()
    except Exception:
        pass
    out = {'stars_gained': gained, 'duel_bonus': bonus, 'stars': stars(uid)}
    if ghost_res: out['ghost'] = ghost_res
    return out


def state(uid):
    init()
    with db() as c: rs = c.execute("SELECT 1 FROM qz_region_user WHERE user_id=?", (uid,)).fetchone() is not None
    return {'stars': stars(uid), 'gift': _gift_view(uid), 'tasks': tasks_view(uid), 'region_set': rs}


# =================================================================== v131: RAQIB (ghost) bilan o'yin
GHOST_WIN, GHOST_DRAW, GHOST_WIN_PER_DAY = 20, 8, 5
GHOST_DAYS = 14
BOT_NAME = 'Bot'


def _valid_log(log, correct, total):
    try: lg = [int(x) for x in log]
    except Exception: return None
    if len(lg) != 5 or any(x not in (0, 1) for x in lg): return None
    try:
        if int(total) != 5 or int(correct) != sum(lg): return None
    except Exception: return None
    return lg


def _save_ghost(c, uid, seed, correct, total, log):
    """Duel natijasini (5 savol) keyingi o'yinchilarga «raqib» sifatida saqlaydi. Noto'g'ri yozuv e'tiborga olinmaydi."""
    try: seed = int(seed)
    except Exception: return
    lg = _valid_log(log or [], correct, total)
    if lg is None or not (0 < seed < 10 ** 9): return
    c.execute("INSERT INTO qz_ghost(user_id,seed,correct,total,log,created_at) VALUES(?,?,?,?,?,?)", (uid, seed, sum(lg), 5, ''.join(map(str, lg)), now()))
    c.execute("DELETE FROM qz_ghost WHERE user_id=? AND id NOT IN (SELECT id FROM qz_ghost WHERE user_id=? ORDER BY id DESC LIMIT 30)", (uid, uid))


def _bot_log(rnd=None):
    import random
    r = rnd or random; p = r.uniform(0.5, 0.85)
    return [1 if r.random() < p else 0 for _ in range(5)]


def match(uid):
    """Tasodifiy raqib: boshqa foydalanuvchining oldin yozilgan natijasi; topilmasa — Bot (ochiq ko'rsatiladi)."""
    init()
    import random
    cut = (datetime.now(timezone.utc) - timedelta(days=GHOST_DAYS)).isoformat(timespec='seconds')
    with db() as c:
        row = c.execute("""SELECT g.id,g.user_id,g.seed,g.correct,g.log FROM qz_ghost g
            WHERE g.user_id>0 AND g.user_id<>? AND g.created_at>=? AND g.id NOT IN (SELECT ghost_id FROM qz_ghost_seen WHERE user_id=?)
              AND g.user_id NOT IN (SELECT user_id FROM mini_banned)
            ORDER BY RANDOM() LIMIT 1""", (uid, cut, uid)).fetchone()
        if row:
            gid, gu, seed, cor, log = row
            c.execute("INSERT OR IGNORE INTO qz_ghost_seen(user_id,ghost_id,created_at) VALUES(?,?,?)", (uid, gid, now())); c.commit()
            import mini_extra as _mx
            return {'ghost_id': gid, 'seed': int(seed), 'name': _mx.user_name(gu), 'bot': False, 'correct': int(cor), 'log': [int(x) for x in log]}
        lg = _bot_log(); seed = random.randint(1, 899999)
        c.execute("DELETE FROM qz_ghost WHERE user_id=0 AND created_at<?", ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec='seconds'),))
        cur = c.execute("INSERT INTO qz_ghost(user_id,seed,correct,total,log,created_at) VALUES(0,?,?,5,?,?)", (seed, sum(lg), ''.join(map(str, lg)), now())); c.commit()
        return {'ghost_id': cur.lastrowid, 'seed': seed, 'name': BOT_NAME, 'bot': True, 'correct': sum(lg), 'log': lg}


def _settle_ghost(c, uid, gid, correct):
    """Raqib bilan o'yin natijasi (serverdagi raqib balli bilan solishtiriladi). Bir match — bir mukofot; g'alaba kuniga 5 tagacha."""
    try: gid = int(gid); correct = int(correct)
    except Exception: return None
    r = c.execute("SELECT correct,user_id FROM qz_ghost WHERE id=?", (gid,)).fetchone()
    if not r or not (0 <= correct <= 5): return None
    theirs = int(r[0]); res = 'win' if correct > theirs else 'draw' if correct == theirs else 'lose'
    bonus = 0
    if res == 'win':
        n = c.execute("SELECT COUNT(*) FROM qz_ledger WHERE user_id=? AND reason='ghost' AND delta=? AND created_at>=?", (uid, GHOST_WIN, _day_start_utc())).fetchone()[0]
        if n < GHOST_WIN_PER_DAY: bonus = _credit(c, uid, GHOST_WIN, 'ghost', gid)
    elif res == 'draw': bonus = _credit(c, uid, GHOST_DRAW, 'ghost', gid)
    else: _credit(c, uid, 0, 'ghost', gid)   # yutqazish ham qayd qilinadi (bir match — bir natija)
    return {'result': res, 'mine': correct, 'theirs': theirs, 'bonus': bonus}


# =================================================================== v131: VILOYATLAR bellashuvi
REGIONS = (('tsh', 'Toshkent shahri'), ('tvi', 'Toshkent viloyati'), ('and', 'Andijon'), ('bux', 'Buxoro'), ('far', 'Farg‘ona'), ('jiz', 'Jizzax'),
           ('nam', 'Namangan'), ('nav', 'Navoiy'), ('qas', 'Qashqadaryo'), ('qqr', 'Qoraqalpog‘iston'), ('sam', 'Samarqand'), ('sir', 'Sirdaryo'),
           ('sur', 'Surxondaryo'), ('xor', 'Xorazm'))
REGION_KEYS = {k for k, _ in REGIONS}
REGION_CHANGE_DAYS = 7


def _week_start():
    d = datetime.now(TZ); return (d - timedelta(days=d.weekday())).strftime('%Y-%m-%d')


def _secs_to_midnight():
    d = datetime.now(TZ); nxt = (d + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((nxt - d).total_seconds())


def set_region(uid, key):
    init()
    if key not in REGION_KEYS: return None, 'Noma’lum viloyat.'
    import time
    with db() as c:
        r = c.execute("SELECT region,set_at FROM qz_region_user WHERE user_id=?", (uid,)).fetchone()
        if r and r[0] != key and time.time() - float(r[1] or 0) < REGION_CHANGE_DAYS * 86400:
            return None, 'Viloyatni %d kundan keyin almashtirish mumkin.' % REGION_CHANGE_DAYS
        c.execute("INSERT INTO qz_region_user(user_id,region,set_at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET region=excluded.region, set_at=CASE WHEN qz_region_user.region=excluded.region THEN qz_region_user.set_at ELSE excluded.set_at END", (uid, key, time.time()))
        c.commit()
    return region_state(uid), None


def region_play(uid, correct, total):
    """Kuniga bir marta. Natija viloyat hisobiga qo'shiladi; ⭐ = to'g'ri javoblar soni."""
    init()
    try: correct = int(correct); total = int(total)
    except Exception: return None, 'Noto‘g‘ri natija.'
    if not (5 <= total <= 10 and 0 <= correct <= total): return None, 'Noto‘g‘ri natija.'
    with db() as c:
        r = c.execute("SELECT region FROM qz_region_user WHERE user_id=?", (uid,)).fetchone()
        if not r: return None, 'Avval viloyatingizni tanlang.'
        day = _today()
        cur = c.execute("INSERT OR IGNORE INTO qz_region_play(user_id,day,region,correct,total) VALUES(?,?,?,?,?)", (uid, day, r[0], correct, total))
        if cur.rowcount != 1: return None, 'Bugungi bellashuvda qatnashgansiz.'
        got = _credit(c, uid, correct, 'region', day) if correct else 0
        c.commit()
    return {'gained': got, 'stars': stars(uid), **region_state(uid)}, None


def region_state(uid):
    init()
    import mini_extra as _mx
    ws, day = _week_start(), _today()
    with db() as c:
        me = c.execute("SELECT region,set_at FROM qz_region_user WHERE user_id=?", (uid,)).fetchone()
        rows = c.execute("SELECT region, SUM(correct), COUNT(*) FROM qz_region_play WHERE day>=? GROUP BY region", (ws,)).fetchall()
        pl = c.execute("SELECT correct,total FROM qz_region_play WHERE user_id=? AND day=?", (uid, day)).fetchone()
        top = []
        if me:
            top = c.execute("SELECT user_id, SUM(correct) s FROM qz_region_play WHERE day>=? AND region=? GROUP BY user_id ORDER BY s DESC LIMIT 5", (ws, me[0])).fetchall()
    pts = {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in rows}
    names = dict(REGIONS)
    board = sorted(({'key': k, 'name': names[k], 'pts': pts.get(k, (0, 0))[0], 'plays': pts.get(k, (0, 0))[1]} for k in names), key=lambda x: (-x['pts'], x['name']))
    for i, b in enumerate(board): b['rank'] = i + 1
    import time
    return {'regions': [{'key': k, 'name': n} for k, n in REGIONS], 'mine': me[0] if me else None,
            'can_change': (not me) or (time.time() - float(me[1] or 0) >= REGION_CHANGE_DAYS * 86400),
            'played_today': bool(pl), 'today': ({'correct': pl[0], 'total': pl[1]} if pl else None), 'secs_left': _secs_to_midnight(),
            'board': board, 'top': [{'name': _mx.user_name(r[0]), 'pts': int(r[1]), 'me': r[0] == uid} for r in top]}


# =================================================================== v131: TURNIR (savollar serverda, baholash ham serverda)
import json as _json, time as _time
DEFAULT_PRIZES = ((1, 1, 2000), (2, 2, 1000), (3, 4, 500), (5, 8, 200))   # (dan, gacha, ⭐)
TOUR_JOIN_NOTE = 'Turnirda qatnashish uchun kamida %d ta o‘yin o‘ynagan bo‘lish kerak.'


def parse_questions(text):
    """Admin matni -> [{'q','opts','ans'}]. Format: savol qatori, keyin A) B) C) D) qatorlari; to'g'ri javob oxirida * bilan. Savollar bo'sh qator bilan ajratiladi."""
    import re
    out, errs = [], []
    for bi, block in enumerate(re.split(r'\n\s*\n', (text or '').strip().replace('\r', '')), 1):
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        if not lines: continue
        q = re.sub(r'^\d+\s*[.)]\s*', '', lines[0]).strip(); opts, ans = [], None
        for l in lines[1:]:
            m = re.match(r'^[A-Ea-e][).:]\s*(.+)$', l)
            if not m: errs.append('%d-savol: variant «A) ...» ko‘rinishida bo‘lsin' % bi); break
            o = m.group(1).strip()
            if o.endswith('*'): o = o[:-1].strip(); ans = len(opts)
            opts.append(o)
        else:
            if len(q) < 3: errs.append('%d-savol matni yo‘q' % bi)
            elif not (2 <= len(opts) <= 5): errs.append('%d-savolda 2–5 ta variant bo‘lsin' % bi)
            elif ans is None: errs.append('%d-savolda to‘g‘ri javob * bilan belgilanmagan' % bi)
            else: out.append({'q': q[:400], 'opts': [o[:200] for o in opts], 'ans': ans})
    return out, errs


def tour_create(title, start_ts, end_ts, per_q, text, min_plays=3, prizes=None):
    init(); title = (title or '').strip()[:80]
    qs, errs = parse_questions(text)
    if errs: return None, errs[0]
    if not title: return None, 'Turnir nomini yozing.'
    if not (5 <= len(qs) <= 30): return None, 'Turnirda 5 dan 30 gacha savol bo‘lishi kerak (hozir %d).' % len(qs)
    try: start_ts = float(start_ts); end_ts = float(end_ts); per_q = int(per_q); min_plays = int(min_plays)
    except Exception: return None, 'Sana yoki vaqt noto‘g‘ri.'
    if end_ts <= start_ts or end_ts - start_ts < 600: return None, 'Tugash vaqti boshlanishdan kamida 10 daqiqa keyin bo‘lsin.'
    if not (5 <= per_q <= 60): return None, 'Har savolga 5–60 soniya.'
    pr = prizes or DEFAULT_PRIZES
    with db() as c:
        cur = c.execute("INSERT INTO qz_tour(title,start_at,end_at,per_q,prizes,min_plays,status,created_at) VALUES(?,?,?,?,?,?,?,?)", (title, start_ts, end_ts, per_q, _json.dumps([list(x) for x in pr]), max(0, min_plays), 'open', now()))
        tid = cur.lastrowid
        for i, q in enumerate(qs): c.execute("INSERT INTO qz_tour_q(tour_id,idx,q,opts,ans) VALUES(?,?,?,?,?)", (tid, i, q['q'], _json.dumps(q['opts'], ensure_ascii=False), q['ans']))
        c.commit()
    return {'id': tid, 'questions': len(qs)}, None


def tour_delete(tid):
    init()
    with db() as c:
        for t in ('qz_tour_q', 'qz_tour_play'): c.execute("DELETE FROM %s WHERE tour_id=?" % t, (tid,))
        c.execute("DELETE FROM qz_tour WHERE id=?", (tid,)); c.commit()
    return True


def _tour_row(c, tid):
    return c.execute("SELECT id,title,start_at,end_at,per_q,prizes,min_plays,status FROM qz_tour WHERE id=?", (tid,)).fetchone()


def _rank_rows(c, tid):
    return c.execute("SELECT user_id,correct,ms FROM qz_tour_play WHERE tour_id=? AND finished_at IS NOT NULL ORDER BY correct DESC, ms ASC, user_id ASC", (tid,)).fetchall()


def tour_list(uid):
    """Faol, kutilayotgan va yaqinda tugagan turnirlar (7 kun). Tugagan turnir mukofotlari shu yerda (bir marta) tarqatiladi."""
    init(); t0 = _time.time(); out = []
    with db() as c:
        rows = c.execute("SELECT id FROM qz_tour WHERE end_at>=? ORDER BY start_at ASC", (t0 - 7 * 86400,)).fetchall()
    for (tid,) in rows:
        v = tour_view(uid, tid)
        if v: out.append(v)
    return out


def tour_view(uid, tid):
    init(); t0 = _time.time()
    with db() as c:
        r = _tour_row(c, tid)
        if not r: return None
        n = c.execute("SELECT COUNT(*) FROM qz_tour_q WHERE tour_id=?", (tid,)).fetchone()[0]
        players = c.execute("SELECT COUNT(*) FROM qz_tour_play WHERE tour_id=? AND finished_at IS NOT NULL", (tid,)).fetchone()[0]
        mine = c.execute("SELECT started_at,finished_at,correct,ms FROM qz_tour_play WHERE tour_id=? AND user_id=?", (tid, uid)).fetchone()
        rk = _rank_rows(c, tid)
        plays = c.execute("SELECT COUNT(*) FROM game_plays WHERE user_id=?", (uid,)).fetchone()[0]
    state = 'soon' if t0 < r[2] else 'open' if t0 < r[3] else 'ended'
    my_rank = next((i + 1 for i, x in enumerate(rk) if x[0] == uid), None)
    return {'id': r[0], 'title': r[1], 'start': r[2], 'end': r[3], 'per_q': r[4], 'prizes': _json.loads(r[5] or '[]'), 'min_plays': r[6], 'n': n,
            'state': state, 'players': players, 'secs': int((r[2] if state == 'soon' else r[3]) - t0) if state != 'ended' else 0,
            'my': ({'started': True, 'finished': mine[1] is not None, 'correct': mine[2], 'ms': mine[3], 'rank': my_rank} if mine else None),
            'can_join': plays >= r[6], 'need_plays': max(0, r[6] - plays), 'prize_done': r[7] == 'done'}


def tour_start(uid, tid):
    init(); t0 = _time.time()
    with db() as c:
        r = _tour_row(c, tid)
        if not r: return None, 'Turnir topilmadi.'
        if t0 < r[2]: return None, 'Turnir hali boshlanmagan.'
        if t0 >= r[3]: return None, 'Turnir tugagan.'
        plays = c.execute("SELECT COUNT(*) FROM game_plays WHERE user_id=?", (uid,)).fetchone()[0]
        if plays < r[6]: return None, TOUR_JOIN_NOTE % r[6]
        cur = c.execute("INSERT OR IGNORE INTO qz_tour_play(tour_id,user_id,started_at) VALUES(?,?,?)", (tid, uid, t0))
        if cur.rowcount != 1: return None, 'Siz bu turnirda allaqachon qatnashgansiz (faqat bir marta o‘ynaladi).'
        qs = c.execute("SELECT q,opts FROM qz_tour_q WHERE tour_id=? ORDER BY idx", (tid,)).fetchall(); c.commit()
    return {'title': r[1], 'per_q': r[4], 'questions': [{'q': q, 'opts': _json.loads(o)} for q, o in qs], 'started': t0}, None


def tour_finish(uid, tid, answers):
    init(); t1 = _time.time()
    with db() as c:
        r = _tour_row(c, tid)
        if not r: return None, 'Turnir topilmadi.'
        p = c.execute("SELECT started_at,finished_at FROM qz_tour_play WHERE tour_id=? AND user_id=?", (tid, uid)).fetchone()
        if not p: return None, 'Avval turnirni boshlang.'
        if p[1] is not None: return None, 'Natija allaqachon yuborilgan.'
        key = c.execute("SELECT ans FROM qz_tour_q WHERE tour_id=? ORDER BY idx", (tid,)).fetchall()
        n = len(key); ans = list(answers or [])[:n] + [-1] * max(0, n - len(answers or []))
        correct = 0
        for a, k in zip(ans, key):
            try: correct += 1 if int(a) == int(k[0]) else 0
            except Exception: pass
        limit = n * r[4] + 15                     # har savolga belgilangan vaqt + kichik zaxira
        elapsed = min(max(0.0, t1 - p[0]), limit)
        ms = int(elapsed * 1000)
        c.execute("UPDATE qz_tour_play SET finished_at=?, correct=?, ms=? WHERE tour_id=? AND user_id=?", (t1, correct, ms, tid, uid))
        got = _credit(c, uid, 10, 'tourjoin', tid)   # qatnashgani uchun
        c.commit()
    v = tour_view(uid, tid)
    return {'correct': correct, 'total': n, 'ms': ms, 'rank': (v['my'] or {}).get('rank'), 'gained': got, 'stars': stars(uid), 'tour': v}, None


def tour_board(uid, tid, limit=50):
    init(); import mini_extra as _mx
    with db() as c:
        if not _tour_row(c, tid): return None
        rk = _rank_rows(c, tid)
    top = [{'rank': i + 1, 'name': _mx.user_name(u), 'correct': cor, 'ms': ms, 'me': u == uid} for i, (u, cor, ms) in enumerate(rk[:limit])]
    my = next(({'rank': i + 1, 'correct': cor, 'ms': ms} for i, (u, cor, ms) in enumerate(rk) if u == uid), None)
    return {'top': top, 'my': my, 'players': len(rk)}


def tour_finalize(tid, force=False):
    """Tugagan turnir mukofotlarini tarqatadi (bir marta). [(user_id, rank, ⭐)] qaytaradi — chaqiruvchi xabar yuboradi."""
    init(); t0 = _time.time(); winners = []
    with db() as c:
        r = _tour_row(c, tid)
        if not r or r[7] == 'done' or (t0 < r[3] and not force): return []
        tiers = _json.loads(r[5] or '[]'); rk = _rank_rows(c, tid)
        for i, (u, cor, ms) in enumerate(rk):
            place = i + 1
            st = next((x[2] for x in tiers if x[0] <= place <= x[1]), 0)
            if st and cor > 0 and _credit(c, u, st, 'tourprize', tid): winners.append((u, place, st))
        c.execute("UPDATE qz_tour SET status='done' WHERE id=?", (tid,)); c.commit()
    return winners


def tour_finalize_due():
    init(); out = []
    with db() as c: ids = [x[0] for x in c.execute("SELECT id FROM qz_tour WHERE status<>'done' AND end_at<?", (_time.time(),)).fetchall()]
    for tid in ids:
        with db() as c: title = _tour_row(c, tid)[1]
        for w in tour_finalize(tid): out.append((tid, title) + w)
    return out
