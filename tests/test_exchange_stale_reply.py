#!/usr/bin/env python3
"""دو باگِ گزارش‌شده در یادآوریِ «نیومدی»:

  1. «نیومدی» به پیامِ چندساعت‌پیش می‌پرید (reply روی src_msg کهنه‌ی
     تبادلِ پیش‌قدم). حالا فقط وقتی پیامِ مرجع تازه باشد رویش ریپلای
     می‌شود؛ وگرنه «نیومدی» به‌صورت پیامِ تازه در همان چت می‌رود.

  2. متنِ «ادعای جوین» (msg_claim_no) قبلاً با direction انتخاب می‌شد؛
     یعنی دروغگویِ پیش‌قدم (direction=out که ادعای جوین کرده) همان
     «پیام ناموفق» می‌گرفت و طرفی که اصلاً ادعایی نکرده ولی direction=in
     بود «ادعای جوین» می‌گرفت. حالا پرچمِ جداگانه‌ی claimed مبناست:
       claimed=1 (ادعا کرد و دروغ گفت) → msg_claim_no
       claimed=0 (ادعایی نکرد، فقط نیامد) → msg_no

  3. مسیرِ «عضو نیست» پرچم claimed را درست ست می‌کند (۱ اگر ادعا، ۰ اگر نه).
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_exchange_stale_reply_run")
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


def fresh():
    for f in ("jafj_settings.json", "jafj.db", "jafj_limits.json"):
        if os.path.exists(f):
            os.remove(f)
    e = m.Engine()
    e.st.prof("standard")["channel"] = "@mychan"
    return e


# ── 0) مهاجرتِ ستون‌های جدید ─────────────────────────────────────────────
eng = fresh()
cols = {r[1] for r in eng.db.conn.execute("PRAGMA table_info(exchange)")}
check("src_ts" in cols, "0: ستون src_ts ساخته شد")
check("claimed" in cols, "0: ستون claimed ساخته شد")

# ── 1) سورس: معیارِ متنِ ادعا دیگر direction نیست، claimed است ─────────
a = src.find("    async def send_not_joined_reminder")
b = src.find("    # ---------- پیدا کردن کانال طرف", a)
assert a > 0 and b > a, "send_not_joined_reminder not found"
fn_src = "\n".join(ln[4:] if ln.startswith("    ") else ln
                   for ln in src[a:b].splitlines())
check("bool(rec.get(\"claimed\"))" in fn_src,
      "1: send_not_joined_reminder از claimed استفاده می‌کند (نه direction)")
check("STALE_REPLY_AGE" in fn_src, "1: منطقِ کهنه/تازه‌بودن پیامِ مرجع هست")
check("reply_to=reply_to" in fn_src or "reply_to=" in fn_src,
      "1: reply_to با منطقِ تازه‌بودن انتخاب می‌شود")

# ── 2) سورس: مسیر «عضو نیست» پرچم claimed را ست می‌کند ──────────────────
i = src.find("# ── عضو نیست → «نیومدی»")
j = src.find("# ── نامشخص ──", i)
assert i > 0 and j > i, "member-is-False branch markers missing"
branch = src[i:j]
check("claimed=1 if claim else 0" in branch,
      "2: مسیر «عضو نیست» پرچم claimed را بر اساس claim ست می‌کند")
check('_say_key = "msg_claim_no" if claim else "msg_no"' in branch,
      "2: پاسخِ فوری هنوز بر اساس claim است")

# ── 3) رفتاری: reply روی پیامِ تازه، بدون ریپلای روی پیامِ کهنه ────────
class FakeClient:
    def __init__(self):
        self.sent = []
    async def send_message(self, chat, body, reply_to=None, link_preview=False):
        self.sent.append((chat, body, reply_to))

fake = FakeClient()
CD0 = m.ExCooldown(gap_min=0, gap_max=0)
ns = {"eng": eng, "client": fake, "DRY_RUN": m.DRY_RUN,
      "ex_cd": CD0, "time": time}
exec(fn_src, ns)
send_rem = ns["send_not_joined_reminder"]

# تازه: src_msg همین حالا ست شده (src_ts خودکار = now)
r, _n = eng.db.ex_add(9001, "@liar", "@theirchan")
eng.db.ex_set(r["id"], src_chat=111, src_msg=222)
ok = asyncio.run(send_rem(eng.db.ex_get(r["id"])))
check(ok is True and fake.sent[-1] == (111, "نیومدی\n@mychan", 222),
      "3: پیامِ مرجع تازه → ریپلای روی خودش (بود %r)" % (fake.sent[-1],))

# کهنه: پیامِ مرجع مال ۳ ساعت پیش → بدون ریپلای (پیامِ تازه)
r2, _n = eng.db.ex_add(9002, "@old", "@oldchan")
eng.db.ex_set(r2["id"], src_chat=111, src_msg=222)
eng.db.ex_set(r2["id"], src_ts=int(time.time()) - 3 * 3600)
ok = asyncio.run(send_rem(eng.db.ex_get(r2["id"])))
check(ok is True and fake.sent[-1] == (111, "نیومدی\n@mychan", None),
      "3: پیامِ مرجع ۳ساعت‌پیش → بدون ریپلای (بود %r)" % (fake.sent[-1],))

# ── 4) رفتاری: متنِ ادعا فقط برای claimed=1 ─────────────────────────────
x = eng.ex_cfg()
x["msg_claim_no"] = "ادعا کردی ولی نیستی"
r3, _n = eng.db.ex_add(9003, "@claimed", "@c3")
eng.db.ex_set(r3["id"], src_chat=111, src_msg=222, claimed=1,
              direction="out")
ok = asyncio.run(send_rem(eng.db.ex_get(r3["id"])))
check(ok is True and fake.sent[-1][1] == "ادعا کردی ولی نیستی",
      "4: پیش‌قدمِ دروغگو (out + claimed=1) → متنِ ادعا (بود %r)"
      % (fake.sent[-1][1],))

r4, _n = eng.db.ex_add(9004, "@noclaim", "@c4")
eng.db.ex_set(r4["id"], src_chat=111, src_msg=222, claimed=0,
              direction="in")
ok = asyncio.run(send_rem(eng.db.ex_get(r4["id"])))
check(ok is True and fake.sent[-1][1] == "نیومدی\n@mychan",
      "4: بدون ادعا (in + claimed=0) → «نیومدی» (بود %r)"
      % (fake.sent[-1][1],))

# ── 5) رفتاری: مسیر «عضو نیست» پرچم claimed را درست ذخیره می‌کند ────────
a = src.find("# ── عضو نیست → «نیومدی»")
b = src.find("# ── نامشخص ──", a)
assert a > 0 and b > a
blk = src[a:b]
blines = blk.splitlines()
while blines and (blines[0].lstrip().startswith("#") or not blines[0].strip()):
    blines.pop(0)
while blines and not blines[-1].strip():
    blines.pop()
ded8 = "\n".join(ln[8:] if ln.startswith("        ") else ln
                 for ln in blines)
branch_src = (
    "async def _blk(eng, x, member, event, sender, sender_name, say,\n"
    "               find_their_channel, reminder_delay, on_exchange_request,\n"
    "               claim=False):\n"
    + "\n".join("    " + ln for ln in ded8.splitlines())
    + "\n"
)
bns = {"time": time, "ex_cd": CD0,
       "next_action_after": lambda rec, base=None: int(base)}
exec(branch_src, bns)
_blk = bns["_blk"]

class Evt:
    chat_id = 111
    id = 333
class Sender:
    id = 7001
class FnHolder:
    pass

async def fake_say(key, channel="", fallbacks=()):
    return True

async def fake_find(event, sender, chat_id, deep=True):
    return "@theirchan", "از پیام خودش"

def gap30():
    return 15

holder = FnHolder()
eng2 = fresh()
xx = eng2.ex_cfg()
xx["reply"] = True

# رکوردِ پیش‌قدمِ موجود: direction=out، status=joined
pre, _n = eng2.db.ex_add(7001, "tester", "@theirchan")
eng2.db.ex_set(pre["id"], status="joined", direction="out", peer_id=7001)

asyncio.run(_blk(eng2, xx, False, Evt(), Sender(), "tester",
                 fake_say, fake_find, gap30, holder, claim=True))
rec = eng2.db.ex_get(pre["id"])
check(rec["claimed"] == 1, "5: ادعای جوین (claim=True) → claimed=1 (بود %r)"
      % (rec["claimed"],))
check(rec["src_msg"] == 333, "5: پیامِ مرجع به پیامِ جدید آپدیت شد")

asyncio.run(_blk(eng2, xx, False, Evt(), Sender(), "tester",
                 fake_say, fake_find, gap30, holder, claim=False))
rec = eng2.db.ex_get(pre["id"])
check(rec["claimed"] == 0, "5: بدون ادعا (claim=False) → claimed=0 (بود %r)"
      % (rec["claimed"],))

if FAILS:
    print("FAILED:", len(FAILS))
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("DONE PASS")
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
    env["PORT"] = "8274"
    env["JAFJ_PORT"] = "8274"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "RENDER", "RENDER_SERVICE_NAME", "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY",
              "BOT_TOKEN", "API_ID", "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=300)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- stale reply target + claimed-flag (msg_claim_no) ---")
    reset()
    out, err, rc = run()
    if err.strip():
        print("--- driver stderr (tail) ---")
        print(err[-3000:])
    print("--- driver output ---")
    for line in out.splitlines():
        if line.startswith(("OK", "FAIL", "DONE", "FAILED", "  -")):
            print(line)
    if "DONE PASS" in out and "FAIL" not in out:
        print("ALL: PASS")
        return True
    print("ALL: FAIL")
    return False


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
