"""v92 avtomatik testlar: python -m unittest tests.test_v92   (loyiha ildizidan)"""
import os, sys, sqlite3, tempfile, hashlib, unittest, py_compile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_d = tempfile.mkdtemp(); os.environ["BOT_DB_PATH"] = _d + "/t.db"; os.environ["EXAM_DATE"] = "2099-01-01"
import growth_v92 as g

def iso(days): return (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds") + "Z"

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = sqlite3.connect(os.environ["BOT_DB_PATH"])
        c.executescript("""
        CREATE TABLE users(user_id INTEGER PRIMARY KEY,username,first_name,last_name,joined_at,last_seen);
        CREATE TABLE streaks(user_id INTEGER PRIMARY KEY,current INT,best INT,last_day TEXT,remind_day TEXT);
        CREATE TABLE reminders(user_id INTEGER PRIMARY KEY,last_sent,optout INT);
        CREATE TABLE mini_banned(user_id INTEGER PRIMARY KEY);
        CREATE TABLE manual_orders(id INTEGER PRIMARY KEY,user_id INT,status,amount INT);
        CREATE TABLE referrals(invitee_id INTEGER PRIMARY KEY,inviter_id INT,created_at,invitee_bonus INT DEFAULT 0,inviter_rewarded INT DEFAULT 0,rewarded_at);
        CREATE TABLE teachers(user_id INTEGER PRIMARY KEY,percent INT,active INT DEFAULT 1,created_at);
        CREATE TABLE teacher_students(student_id INTEGER PRIMARY KEY,teacher_id INT,created_at);
        CREATE TABLE game_plays(id INTEGER PRIMARY KEY,user_id INT,game,day TEXT,correct INT,total INT,points INT,created_at);
        """)
        for u, n, idle in [(1, "Ali", 3), (2, "Vali", 6), (3, "Gul", 11), (4, "Sam", 1), (5, "Old", 45), (6, "Opt", 4), (7, "Ban", 4)]:
            c.execute("INSERT INTO users VALUES(?,?,?,?,?,?)", (u, "", n, "", iso(idle + 3), iso(idle)))
        c.execute("INSERT INTO reminders VALUES(6,NULL,1)"); c.execute("INSERT INTO mini_banned VALUES(7)")
        c.commit(); c.close(); g.init()

    def test_winback_stages_and_dedup(self):
        cand = sorted((u, s) for u, _, s, _ in g.winback_candidates())
        self.assertEqual(cand, [(1, 1), (2, 2), (3, 3)])          # 4 (1 kun), 5 (45 kun), 6 (optout), 7 (ban) chiqmaydi
        g.WB_FROM_HOUR, g.WB_TO_HOUR = 0, 24
        sent = []
        n = g.winback_run_once(lambda m, p: (sent.append(p["chat_id"]) or (True, 0)), lambda u: None, "https://x", sleep=0)
        self.assertEqual(n, 3); self.assertEqual(g.winback_candidates(), [])

    def test_blocked_user_marked(self):
        marked = []
        g.WB_FROM_HOUR, g.WB_TO_HOUR = 0, 24
        c = sqlite3.connect(os.environ["BOT_DB_PATH"]); c.execute("INSERT OR REPLACE INTO users VALUES(50,'','Blk','',?,?)", (iso(10), iso(7))); c.commit(); c.close()
        g.winback_run_once(lambda m, p: (False, 403), marked.append, "", sleep=0)
        self.assertIn(50, marked)
        c = sqlite3.connect(os.environ["BOT_DB_PATH"]); c.execute("DELETE FROM users WHERE user_id=50"); c.commit(); c.close()

    def test_onboarding(self):
        self.assertTrue(g.ob_needed(900)); g.ob_set(900, target="a", step="target"); g.ob_set(900, minutes=20, step="done")
        self.assertFalse(g.ob_needed(900)); self.assertIn("20 daqiqa", g.ob_done_text(900))

    def test_invite_text(self):
        c = sqlite3.connect(os.environ["BOT_DB_PATH"])
        for i in range(2): c.execute("INSERT INTO referrals(invitee_id,inviter_id,created_at,invitee_bonus) VALUES(?,?,?,1)", (7000 + i, 700, iso(0)))
        c.commit(); c.close()
        self.assertIn("Jami: 2 ta do‘st", g.on_invite_joined(700))

    def test_essay_topics(self):
        added, bad = g.essay_add_many("1. Ba’zilar kitob o‘qishni vaqt yo‘qotish deb biladi, boshqalar esa uni eng yaxshi mashg‘ulot deb hisoblaydi.\n- Qisqa\n"
                                      "2) Yoshlar uchun ekologik muammolarning ahamiyati haqida fikringizni asoslab yozing.\nBa’zilar kitob o‘qishni vaqt yo‘qotish deb biladi, boshqalar esa uni eng yaxshi mashg‘ulot deb hisoblaydi.", 1)
        self.assertEqual(len(added), 2); self.assertEqual(len(bad), 2)               # 1 ta qisqa, 1 ta takror
        defaults = ["Standart mavzu raqam bir — bu yerda yetarlicha uzun matn."]
        self.assertEqual(len(g.essay_pool(defaults)), 3)
        t1 = g.essay_today(defaults); self.assertEqual(t1, g.essay_today(defaults))   # kun davomida o'zgarmaydi
        g.essay_set_active(added[0], False); g.essay_set_active(added[1], False)
        self.assertEqual(g.essay_pool(defaults), defaults)
        g.essay_set_active(added[1], True); self.assertEqual(g.essay_set_today(added[1]), g.essay_today(defaults))
        self.assertIsNone(g.essay_set_today(added[0]))                               # o'chirilgan mavzuni bugunga qo'yib bo'lmaydi

    def test_class_panel(self):
        c = sqlite3.connect(os.environ["BOT_DB_PATH"]); today = g._today().isoformat()
        c.execute("INSERT OR REPLACE INTO teachers VALUES(600,10,1,NULL)")
        for s in (11, 12, 13):
            c.execute("INSERT OR REPLACE INTO users VALUES(?,?,?,?,?,?)", (s, "", f"Stu{s}", "", iso(0), iso(0)))
            c.execute("INSERT OR REPLACE INTO teacher_students VALUES(?,600,NULL)", (s,))
        c.execute("INSERT INTO game_plays(user_id,game,day,correct,total,points) VALUES(11,'x',?,5,5,50)", (today,)); c.commit(); c.close()
        self.assertTrue(g.is_teacher(600)); self.assertFalse(g.is_teacher(11))
        o = g.class_overview(600); self.assertIn("faol: 1", o); self.assertIn("nofaol: 2", o)
        self.assertIn("Stu11", g.student_class_board(11)); self.assertEqual(len(g.class_parent_reports(600)), 3)

    def test_region_and_share(self):
        self.assertEqual(g.region_set(1, 0), g.REGIONS[0]); self.assertIsNone(g.region_set(1, 99))
        self.assertIn(g.REGIONS[0], g.region_board(1))
        text, url = g.share_card(1, "https://t.me/b?start=ref_1", lambda u: {"score": 50, "max": 75, "level": "B"}, 5)
        self.assertIn("50/75", text); self.assertTrue(url.startswith("https://t.me/share/url?"))

    def test_report(self):
        out = "\n".join(g.report_lines(g._today() - timedelta(days=1))); self.assertIn("USHLAB QOLISH", out); self.assertIn("Baza:", out)

class Safety(unittest.TestCase):
    def test_payment_untouched(self):
        want = open(os.path.join(ROOT, "tests", "manual_pay.sha256")).read().strip()
        got = hashlib.sha256(open(os.path.join(ROOT, "manual_pay.py"), "rb").read()).hexdigest()
        self.assertEqual(got, want, "manual_pay.py o'zgartirilgan!")

    def test_daily_plan_js(self):
        import shutil, subprocess
        if not shutil.which("node"): self.skipTest("node yo'q")
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "daily_plan_check.js")], cwd=os.path.join(ROOT, "miniapp"), capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_compiles(self):
        for f in ("bot-1-1.py", "growth_v92.py", "growth_tests.py", "engage_v87.py"):
            py_compile.compile(os.path.join(ROOT, f), doraise=True)

if __name__ == "__main__":
    unittest.main()
