#!/usr/bin/env python3
"""متنِ جداگانه برای «گفتی جوین شدم ولی عضو نیستی» (msg_claim_no).

قبلاً دو حالتِ کاملاً متفاوت — «طرف ادعا کرده جوین شده ولی عضو نیست» و
«طرف از اول نیامده و ادعایی نکرده» — هر دو همان msg_no را می‌گرفتند.
حالا کلیدِ msg_claim_no هست و اگر تنظیم نشده باشد به msg_no برمی‌گردد.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_claim_text_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")

DRIVER = r"""
import asyncio, importlib.util, json, os, sys, time
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


# ═══════ C1 — پیش‌فرض و بازگشت به msg_no ═══════
check(m.DEFAULTS["exchange"].get("msg_claim_no") == "",
      "C1: msg_claim_no پیش‌فرض خالی است")

eng = fresh()
out = eng.ex_render("msg_claim_no", "ali", "@theirchan")
check(out == "نیومدی\n@mychan",
      "C1: بدونِ هیچ متنی → «نیومدی» + کانالِ من (بود %r)" % out)
check("@theirchan" not in out, "C1: لینکِ طرف اتوماتیک نمی‌آید")

x = eng.ex_cfg()
x["msg_no"] = "سفارشیِ ناموفق"
check(eng.ex_render("msg_claim_no", "ali", "@theirchan") == "سفارشیِ ناموفق",
      "C1: با msg_no سفارشی → همان msg_no (بدون لینک)")
check(eng.ex_render("msg_no", "ali", "@theirchan") == "سفارشیِ ناموفق",
      "C1: خودِ msg_no دست‌نخورده")

x["msg_claim_no"] = "ادعا کردی ولی نیستی"
check(eng.ex_render("msg_claim_no", "ali", "@theirchan") == "ادعا کردی ولی نیستی",
      "C1: با msg_claim_no سفارشی → فقط همان")
check(eng.ex_render("msg_no", "ali", "@theirchan") == "سفارشیِ ناموفق",
      "C1: msg_no از msg_claim_no اثر نمی‌گیرد")

x["msg_claim_no"] = "{name} جان، {mychannel} را جوین نشدی"
check(eng.ex_render("msg_claim_no", "ali", "@theirchan")
      == "ali جان، @mychan را جوین نشدی", "C1: placeholderها کار می‌کنند")
print("DONE C1 ex_render fallback")


# ═══════ C2 — دستورِ «پیام ادعای جوین» ═══════
eng = fresh()
r = eng.exchange_cmd("پیام ادعای جوین سلام تو نیومدی")
check("ذخیره شد" in r, "C2: ذخیره شد (%r)" % r[:40])
check(eng.ex_cfg()["msg_claim_no"] == "سلام تو نیومدی", "C2: متن ثبت شد")
r = eng.exchange_cmd("پیام ادعای جوین")
check("سلام تو نیومدی" in r, "C2: نمایشِ متنِ فعلی")
r = eng.exchange_cmd("پیام ادعا خاموش")
check("برداشته شد" in r and eng.ex_cfg()["msg_claim_no"] == "",
      "C2: خاموش شد و میان‌برِ «پیام ادعا» کار کرد")
r = eng.exchange_cmd("پیام ادعا")
check("پیام ناموفق" in r, "C2: بدونِ متن → توضیحِ بازگشت به «پیام ناموفق»")
check("msg_claim_no" in eng.ex_msgs_text() or "ادعا" in eng.ex_msgs_text(),
      "C2: در منوی متن‌ها هست")
print("DONE C2 command")


# ═══════ C3 — send_not_joined_reminder واقعی ═══════
a = src.find("    async def send_not_joined_reminder(rec):")
b = src.find("    # ---------- پیدا کردن کانال طرف ----------", a)
assert a > 0 and b > a, "send_not_joined_reminder markers missing"
ded = "\n".join(ln[4:] if ln.startswith("    ") else ln
                for ln in src[a:b].splitlines())

eng = fresh()
x = eng.ex_cfg()
x["reply"] = True
x["msg_claim_no"] = "ادعا کردی!"
CD0 = m.ExCooldown(gap_min=0, gap_max=0)
SENT = []

class FakeClient:
    async def send_message(self, chat, body, reply_to=None, link_preview=True):
        SENT.append(body)
        return True

sns = {"eng": eng, "time": time, "asyncio": asyncio, "ex_cd": CD0,
       "DRY_RUN": False, "client": FakeClient()}
exec(ded, sns)
send_rem = sns["send_not_joined_reminder"]

def mk(peer, claimed):
    # claimed=1 یعنی طرف ادعای «جوین شدم» کرده ولی عضو نیست (دروغگو)؛
    # claimed=0 یعنی طرف اصلاً ادعایی نکرده و فقط عضو نشده.
    # متنِ یادآوری بر اساس همین پرچم انتخاب می‌شود — نه direction.
    r, _n = eng.db.ex_add(peer, "p%d" % peer, "@c%d" % peer)
    eng.db.ex_set(r["id"], peer_id=peer, claimed=claimed,
                  src_chat=11, src_msg=22, reminders_total=0)
    return eng.db.ex_get(r["id"])

SENT.clear()
asyncio.run(send_rem(mk(8001, 1)))
check(SENT == ["ادعا کردی!"], "C3: claimed=1 (ادعای جوین) → متنِ ادعا (بود %r)" % SENT)

SENT.clear()
asyncio.run(send_rem(mk(8002, 0)))
check(SENT == ["نیومدی\n@mychan"],
      "C3: claimed=0 (بدون ادعا) → همان «نیومدی» (بود %r)" % SENT)
print("DONE C3 reminder claimed flag")


# ═══════ C4 — مهاجرتِ تنظیمِ قدیمی ═══════
old = {"exchange": {"msg_no": "متنِ سفارشیِ خودم", "msg_ok": ""}}
with open(m.SETTINGS_FILE, "w", encoding="utf-8") as f:
    json.dump(old, f, ensure_ascii=False)
mig = m.Engine()
mig.st.prof("standard")["channel"] = "@mychan"
mx = mig.ex_cfg()
check(mx["msg_no"] == "متنِ سفارشیِ خودم", "C4: متنِ سفارشیِ قدیمی حفظ شد")
check(mx.get("msg_claim_no") == "", "C4: کلیدِ تازه خالی اضافه شد")
check(mig.ex_render("msg_claim_no") == "متنِ سفارشیِ خودم",
      "C4: مسیرِ ادعا همان متنِ قدیمی را می‌دهد")
os.remove(m.SETTINGS_FILE)
print("DONE C4 migration")


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
        shutil.copy2(os.path.join(REPO, f), APP)


def run():
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["PORT"] = "8273"
    env["JAFJ_PORT"] = "8273"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "RENDER", "RENDER_SERVICE_NAME", "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY",
              "BOT_TOKEN", "API_ID", "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=300)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- claim-vs-never-came texts (msg_claim_no) ---")
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
