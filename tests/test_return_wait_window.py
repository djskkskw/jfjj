#!/usr/bin/env python3
"""«مهلت بازگشت پیش‌قدم» — چرا ربات زودتر از موعد از کانال طرف لفت می‌داد.

گزارش کاربر (آمار روز):

    ✅ Join شده: ۱۳ کانال
    👋 لفت داده‌شده: ۹۸ کانال
    👥 جذب موفق تبادل: ۰ نفر

دو ریشه‌ی واقعی که این تست قفل می‌کند:

  1. در حالت «پیش‌قدم» ربات خودش اول جوین می‌شود و طرف باید برگردد؛ ولی
     هر نبودنِ طرف از همان دقیقه‌ی اول «اخطار لفت» حساب می‌شد. چون ربات
     خودش بعد از جوین پیامش را می‌فرستد (replied=1)، مسیر مهربانِ «نیومدی»
     دور زده می‌شد و طرف فقط ~۱–۲ دقیقه فرصت داشت — یعنی عملاً هیچ‌کس
     نمی‌رسید. نتیجه: سیلِ لفت و صفر جذب.
     فیکس: ``return_wait_minutes`` (پیش‌فرض ۱۸۰). تا پایان این مهلت،
     نبودنِ طرفِ پیش‌قدمِ «هرگز تأییدنشده» اخطار/لفت حساب نمی‌شود؛
     فقط چند یادآوریِ فاصله‌دار می‌رود. هر تأییدِ عضویت (member_ok_at)
     مهلت را تمام می‌کند و منطقِ تقلب‌کار (۲ نبودنِ تأییدشده → لفت)
     سر جایش می‌ماند.

  2. آمارِ «لفت داده‌شده» هر تلاشِ لفت را می‌شمرد، حتی وقتی لفت
     **انجام نمی‌شد** (لینک منقضی/فلود) و هر بارِ تلاش دوباره. پس عددِ
     ۹۸ الکی بزرگ بود. فیکس: فقط لفتِ موفق ``ex_left`` ثبت می‌شود؛
     تلاش ناموفق ``ex_leave_fail`` جدا می‌رود.

حلقه‌ی نگهبانی و حلقه‌ی یادآوری از سورس واقعی 95.py استخراج و با
دیتابیس واقعی و استاب‌های تلگرام اجرا می‌شوند (همان روش
test_claim_flow_fixes / test_exchange_notjoined_flow).
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_return_wait_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
SRC_REPO = REPO


DRIVER = r"""
import asyncio, importlib.util, os, sys, time
sys.path.insert(0, os.getcwd())

spec = importlib.util.spec_from_file_location("m95", "95.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

src = open("95.py", encoding="utf-8").read()

FAILS = []


def check(cond, label):
    if cond:
        print("OK", label)
        return True
    print("FAIL", label)
    FAILS.append(label)
    return False


def fresh_engine():
    for f in ("jafj_settings.json", "jafj.db", "jafj_limits.json"):
        if os.path.exists(f):
            os.remove(f)
    return m.Engine()


def extract(start_marker, end_marker, ind=16):
    a = src.find(start_marker)
    b = src.find(end_marker, a)
    assert a > 0 and b > a, "markers missing: %r / %r" % (start_marker, end_marker)
    lines = src[a:b].splitlines()
    while lines and (lines[0].lstrip().startswith("#") or not lines[0].strip()):
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(ln[ind:] if ln.startswith(" " * ind) else ln
                     for ln in lines)


REM = extract("# ── یادآوری عضو‌نشده: دو پیام «نیومدی»", "# ۳) چک دوره‌ای")
WATCH = extract("# ۳) چک دوره‌ای", "# برای دقت فاصله‌ی یادآوری")

rem_src = (
    "import asyncio, time\n"
    "fa = m.fa\n"
    "async def _run(eng, x, stub):\n"
    "    now_rem = int(time.time())\n"
    "    confirm_peer_membership = stub.confirm\n"
    "    send_not_joined_reminder = stub.send_rem\n"
    "    leave_link = stub.leave\n"
    "    reminder_delay = stub.reminder_delay\n"
    "    membership_check_delay = stub.check_delay\n"
    "    note = stub.note\n"
    "    warn_membership_check_broken = stub.warn\n"
    "    check_gate = stub.gate\n"
    "    unk_fallback = stub.unk_fallback\n"
    "    next_action_after = lambda rec, base=None: int(base)\n"
    + "\n".join("    " + ln for ln in REM.splitlines())
    + "\n"
)
rns = {"m": m, "ex_cd": m.ExCooldown(gap_min=0, gap_max=0)}
exec(rem_src, rns)
run_reminder = rns["_run"]

watch_src = (
    "import asyncio, time\n"
    "fa = m.fa\n"
    "async def _runw(eng, x, stub):\n"
    "    confirm_peer_membership = stub.confirm\n"
    "    send_not_joined_reminder = stub.send_rem\n"
    "    leave_link = stub.leave\n"
    "    reminder_delay = stub.reminder_delay\n"
    "    membership_check_delay = stub.check_delay\n"
    "    watch_delay_seconds = stub.watch_delay\n"
    "    warn_membership_check_broken = stub.warn\n"
    "    note = stub.note\n"
    "    check_gate = stub.gate\n"
    "    unk_fallback = stub.unk_fallback\n"
    "    next_action_after = lambda rec, base=None: int(base)\n"
    + "\n".join("    " + ln for ln in WATCH.splitlines())
    + "\n"
)
wns = {"m": m, "ex_cd": m.ExCooldown(gap_min=0, gap_max=0)}
exec(watch_src, wns)
run_watch = wns["_runw"]


class Stub:
    def __init__(self, member_map=None, send_ok=True,
                 leave_ok=True, leave_err=""):
        self.member_map = member_map or {}
        self.send_ok = send_ok
        self.leave_ok = leave_ok
        self.leave_err = leave_err
        self.sent = []
        self.left = []
        self.notes = []
        self.warns = []
        self.gate = m.CheckGate(base_gap=0.0)

    def unk_fallback(self, rec, extra=1):
        return False

    async def confirm(self, pid, fast=False, rec_id=None, confirm=True):
        return self.member_map.get(pid)

    async def send_rem(self, rec):
        if not self.send_ok:
            return False
        self.sent.append(rec["id"])
        return True

    async def leave(self, link, rec_id=None):
        if not self.leave_ok:
            return False, self.leave_err
        self.left.append(link)
        return True, ""

    async def note(self, text):
        self.notes.append(text)

    async def warn(self, now):
        self.warns.append(now)

    @staticmethod
    def reminder_delay():
        return 15

    @staticmethod
    def check_delay():
        return 15

    @staticmethod
    def watch_delay(rec):
        return 15


def mkrec(eng, peer, link, status="joined", direction="out", reminders=0,
          joined_at=None, replied=0, member_ok_at=0, strikes=0,
          next_check_due=True, next_reminder=0):
    r, _n = eng.db.ex_add(peer, "p%d" % peer, link)
    now = int(time.time())
    eng.db.ex_set(r["id"], status=status, direction=direction,
                  reminders=reminders, peer_id=peer, replied=replied,
                  strikes=strikes, member_ok_at=member_ok_at,
                  src_chat=111, src_msg=222,
                  joined_at=joined_at if joined_at is not None else now,
                  last_check=now - 5 if next_check_due else 0,
                  next_check=now - 5 if next_check_due else 0,
                  next_reminder=next_reminder)
    return eng.db.ex_get(r["id"])


def event_count(eng, kind):
    row = eng.db._x("SELECT COUNT(*) c FROM events WHERE kind=?",
                    (kind,), "one")
    return int(row["c"] if row else 0)


# ═══════════ W1 — تنظیم و سیم‌کشی ═══════════
X = m.DEFAULTS["exchange"]
check(X.get("return_wait_minutes") == 180,
      "W1: پیش‌فرض مهلت بازگشت پیش‌قدم ۱۸۰ دقیقه است (بود %r)"
      % X.get("return_wait_minutes"))
check("member_ok_at" in src, "W1: ستونِ تأییدِ عضویت (member_ok_at) در سورس هست")
check("ex_return_wait" in src, "W1: رویداد ex_return_wait ثبت می‌شود")
check('"ex_left" if ok else "ex_leave_fail"' in src,
      "W1: فقط لفتِ موفق ex_left ثبت می‌شود (تلاش ناموفق جدا)")
check("مهلت بازگشت پیش‌قدم — لفت معلق" in src,
      "W1: یادداشتِ «مهلت بازگشت» در هر دو حلقه هست")

# ═══════════ W2 — پیش‌قدمِ تازه داخل مهلت ═══════════
eng = fresh_engine()
x = eng.ex_cfg()
x["enabled"] = True
r = mkrec(eng, 9701, "@w1", direction="out", replied=1)
stub = Stub({9701: False})
asyncio.run(run_watch(eng, x, stub))
g = eng.db.ex_get(r["id"])
check(stub.left == [], "W2: داخل مهلت بازگشت → لفت انجام نشد")
check(g["status"] == "joined" and int(g["strikes"] or 0) == 0,
      "W2: وضعیت joined و بدون اخطار ماند")
check(g["reminders"] == 1 and len(stub.sent) == 1,
      "W2: دقیقاً یک یادآوری فاصله‌دار رفت")
check(int(g["next_check"] or 0) > int(time.time()) + 60,
      "W2: چکِ بعدی با فاصله‌ی بلندِ مهلت زمان‌بندی شد (نه ۱۵ ثانیه)")
check(int(g["next_reminder"] or 0) == 0,
      "W2: پنجره‌ی پیامِ پشت‌سرهم باز نشد")
check("مهلت بازگشت" in (g.get("note") or ""), "W2: یادداشت ثبت شد")
check(event_count(eng, "ex_return_wait") >= 1, "W2: رویداد ex_return_wait ثبت شد")

# ═══════════ W3 — طرف برگشت → member_ok_at و پایان مهلت ═══════════
eng.db.ex_set(r["id"], next_check=int(time.time()) - 5, reminders=1)
stub = Stub({9701: True})
asyncio.run(run_watch(eng, x, stub))
g = eng.db.ex_get(r["id"])
check(int(g["member_ok_at"] or 0) > 0,
      "W3: عضویتِ تأییدشده در member_ok_at ثبت شد")
check(g["reminders"] == 0 and int(g["strikes"] or 0) == 0,
      "W3: شمارنده‌های یادآوری/اخطار صفر شدند")

# ═══════════ W4 — بعد از تأیید، تقلب‌کار سریع لفت می‌خورد ═══════════
stub = Stub({9701: False})
eng.db.ex_set(r["id"], next_check=int(time.time()) - 5)
asyncio.run(run_watch(eng, x, stub))
g = eng.db.ex_get(r["id"])
check(stub.left == [] and int(g["strikes"] or 0) == 1,
      "W4: تأییدشده → نبودنِ اول فقط اخطار (محافظ منفیِ کاذب)")
eng.db.ex_set(r["id"], next_check=int(time.time()) - 5)
asyncio.run(run_watch(eng, x, stub))
g = eng.db.ex_get(r["id"])
check(stub.left == ["@w1"] and g["status"] == "left",
      "W4: تأییدشده → بعد از ۲ نبودنِ تأییدشده لفت انجام شد")

# ═══════════ W5 — مهلت خاموش (۰) = رفتار قبلی ═══════════
eng = fresh_engine()
x = eng.ex_cfg()
x["enabled"] = True
x["return_wait_minutes"] = 0
r = mkrec(eng, 9702, "@w2", direction="out", replied=0)
stub = Stub({9702: False})
asyncio.run(run_watch(eng, x, stub))
g = eng.db.ex_get(r["id"])
check(int(g["strikes"] or 0) == 1 and int(g["next_reminder"] or 0) > 0,
      "W5: با مهلت خاموش، مسیر قدیمی (اخطار + دور «نیومدی») اجرا شد")
eng.db.ex_set(r["id"], next_reminder=int(time.time()) - 5)
asyncio.run(run_reminder(eng, x, stub))
g = eng.db.ex_get(r["id"])
check(g["reminders"] == 2, "W5: دومین «نیومدی» رفت")
eng.db.ex_set(r["id"], next_reminder=int(time.time()) - 5)
asyncio.run(run_reminder(eng, x, stub))
g = eng.db.ex_get(r["id"])
check(stub.left == ["@w2"] and g["status"] == "left",
      "W5: بعد از دو «نیومدی» لفت شد")
check(event_count(eng, "ex_left") >= 1, "W5: لفتِ موفق ex_left ثبت شد")

# ═══════════ W6 — لفتِ ناموفق آمار را بالا نمی‌برد ═══════════
eng = fresh_engine()
x = eng.ex_cfg()
x["enabled"] = True
x["return_wait_minutes"] = 0
r = mkrec(eng, 9703, "@w3", direction="out", replied=1, reminders=2,
           next_reminder=int(time.time()) - 5)
stub = Stub({9703: False}, leave_ok=False, leave_err="لینک منقضی")
asyncio.run(run_reminder(eng, x, stub))
g = eng.db.ex_get(r["id"])
check(g["status"] == "joined" and int(g["leave_fail"] or 0) == 1,
      "W6: لفت نشد → رکورد joined ماند و تلاش شمرده شد")
check(event_count(eng, "ex_left") == 0,
      "W6: تلاشِ ناموفق «لفت داده‌شده» حساب نشد")
check(event_count(eng, "ex_leave_fail") >= 1,
      "W6: تلاشِ ناموفق جدا (ex_leave_fail) ثبت شد")

# ═══════════ W7 — دستور تنظیم مهلت ═══════════
eng = fresh_engine()
eng.exchange_cmd("مهلت پیشقدم ۳۶۰")
check(int(eng.ex_cfg().get("return_wait_minutes")) == 360,
      "W7: `تبادل مهلت پیشقدم ۳۶۰` اعمال شد")
shown = eng.exchange_cmd("مهلت پیشقدم")
check("360" in shown, "W7: نمایش وضعیت مهلت درست است")
eng.exchange_cmd("مهلت پیشقدم ۰")
check(int(eng.ex_cfg().get("return_wait_minutes")) == 0,
      "W7: مهلت خاموش (۰) اعمال شد")

print("DONE return-wait window")
if FAILS:
    print("FAILED:", len(FAILS))
    for f in FAILS:
        print("  -", f)
    print("ALL: FAIL")
    sys.exit(1)
print("ALL: PASS")
"""


def reset():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(APP, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    for f in ("95.py", "manager_82.py"):
        shutil.copy2(os.path.join(SRC_REPO, f), APP)


def run():
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["PORT"] = "8231"
    env["JAFJ_PORT"] = "8231"
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=240)
    out = (p.stdout or "") + (p.stderr or "")
    print(out.strip())
    return p.returncode == 0 and "ALL: PASS" in out


def main():
    print("--- return-wait window (§پیش‌قدم) ---")
    reset()
    ok = run()
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
