#!/usr/bin/env python3
"""پین‌کردنِ «الگوریتمِ فاصله‌ها».

هیچ عددِ فاصله‌ای نباید در فیکس‌های بعدی جابه‌جا شود. این تست همه‌ی
پیش‌فرض‌ها، CheckGate، ExCooldown، تطبیقی (فلود/آپ‌تایم)، فرمول‌های
زمان‌بندی و سیم‌کشیِ صف را قفل می‌کند؛ اگر عددی عوض شود فوراً قرمز می‌شود.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.join(tempfile.gettempdir(), "jafj_spacing_algorithm_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")

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


# ═══════════ S1 — پیش‌فرض‌های فاصله ═══════════
X = m.DEFAULTS["exchange"]
PINNED = {
    "op_gap_min_sec": 15, "op_gap_max_sec": 20,
    "check_min_sec": 15, "check_max_sec": 30,
    "reminder_min_sec": 20, "reminder_max_sec": 40,
    "response_min_sec": 11, "response_max_sec": 48,
    "come_min_sec": 34, "come_max_sec": 35,
    "reply_min_sec": 5, "reply_max_sec": 18,
    "max_reminders": 2, "max_strikes": 2,
    "adaptive_flood_step_sec": 15, "adaptive_flood_max_sec": 120,
    "adaptive_uptime_threshold_hours": 3, "adaptive_uptime_extra_sec": 30,
    "adaptive_uptime_per_hour_sec": 10, "adaptive_uptime_max_sec": 90,
}
for k, v in PINNED.items():
    check(X.get(k) == v, "S1: %s == %r (بود %r)" % (k, v, X.get(k)))
print("DONE S1 defaults pinned")


# ═══════════ S2 — CheckGate ═══════════
T = 1_700_000_000.0
g = m.CheckGate()
check(g.base_gap == 1.5, "S2: base_gap پیش‌فرض ۱.۵")
LOADS = {0: 1.5, 1: 1.5, 2: 1.5, 3: 1.8, 5: 3.0, 10: 6.0, 13: 7.8,
         50: 8.0, 500: 8.0}
for n, want in LOADS.items():
    g.set_load(n)
    check(abs(g.base_gap - want) < 1e-9,
          "S2: set_load(%d) → %.1f (بود %.2f)" % (n, want, g.base_gap))

g = m.CheckGate(base_gap=1.5)
g.penalize(30, now=T)
check(g.flood_extra == 1.5, "S2: penalize → +۱.۵")
check(g.cooldown_until == T + 30 + 2.0, "S2: cooldown_until = now+w+2")
check(g.blocked(T + 10), "S2: در طولِ جریمه blocked است")
check(not g.blocked(T + 33), "S2: بعد از جریمه باز می‌شود")
for i in range(30):
    g.penalize(1, now=T + 100 + i)
check(g.flood_extra == 20.0, "S2: سقفِ flood_extra روی ۲۰")

g2 = m.CheckGate(base_gap=1.5)
g2.penalize(1, now=T)
g2.penalize(1, now=T + 1)
g2.maybe_decay(now=T + 200)
check(g2.flood_extra == 3.0, "S2: زیرِ ۵ دقیقه هیچ کاهشی نیست")
g2.maybe_decay(now=T + 1 + 301)
check(g2.flood_extra == 2.0, "S2: بعد از ۵ دقیقه −۱")
for i in range(10):
    g2.maybe_decay(now=T + 1 + 301 + 301 * (i + 1))
check(g2.flood_extra == 0.0, "S2: هرگز منفی نمی‌شود")
print("DONE S2 CheckGate")


# ═══════════ S3 — ExCooldown ═══════════
cd = m.ExCooldown(gap_min=15, gap_max=20)
check((cd.gap_min, cd.gap_max) == (15.0, 20.0), "S3: بازه‌ی پیش‌فرضِ صف ۱۵–۲۰")
check(cd.floor_seconds() == 15.0, "S3: floor_seconds = کفِ بازه")
for _ in range(30):
    s = cd.seconds()
    if not (15.0 <= s <= 20.0):
        check(False, "S3: seconds خارج از بازه")
        break
else:
    check(True, "S3: seconds همیشه داخلِ بازه")

# خواندن از تنظیمات
for f in ("jafj_settings.json", "jafj.db", "jafj_limits.json"):
    if os.path.exists(f):
        os.remove(f)
eng = m.Engine()
cfg_cd = m.ExCooldown(cfg=eng.ex_cfg)
cfg_cd.apply_config()
check((cfg_cd.gap_min, cfg_cd.gap_max) == (15.0, 20.0),
      "S3: صف بازه را از تنظیمات می‌خواند")
check(cfg_cd.floor_seconds() == 15.0, "S3: floor_seconds از تنظیمات")

fast = m.ExCooldown(gap_min=0.4, gap_max=0.4)
stamps = []
async def _two():
    async def op():
        stamps.append(time.time())
    await fast.action("check", 7, op)
    await fast.action("reminder", 7, op)
asyncio.run(_two())
check(len(stamps) == 2 and (stamps[1] - stamps[0]) >= 0.4,
      "S3: فاصله‌ی واقعیِ دو عملکرد ≥ gap (%.2f)" % (stamps[1] - stamps[0]))

w = m.ExCooldown(gap_min=10, gap_max=10)
check(w.wait_for(None) == 0.0 and w.ready(None), "S3: بدون رکورد → آماده")
w.mark_done(5, now=time.time())
check(w.wait_for(5) > 8 and not w.ready(5), "S3: رکوردِ تازه در خنک‌کننده")
ok, ts = w.defer_if_due({"id": 5}, int(time.time()))
check(ok is False and ts > int(time.time()), "S3: defer_if_due نوبت را جلو می‌برد")
ok2, ts2 = w.defer_if_due({"id": 6}, int(time.time()))
check(ok2 is True and ts2 == 0, "S3: رکوردِ آزاد → نوبتش رسیده")
print("DONE S3 ExCooldown")


# ═══════════ S4 — adaptive_extra / effective_join_gap ═══════════
xx = eng.ex_cfg()
now = int(time.time())
eng.started = now
xx["_adaptive_flood_extra"] = 0
lo, hi = eng.effective_join_gap(now)
check((lo, hi) == (30, 60), "S4: پایه‌ی فاصله‌ی جوین ۳۰–۶۰")

for i in range(1, 5):
    eng.adaptive_on_flood(30, now=now)
    check(xx["_adaptive_flood_extra"] == min(120, 15 * i),
          "S4: فلود #%d → +%d" % (i, min(120, 15 * i)))
for i in range(10):
    eng.adaptive_on_flood(30, now=now)
check(xx["_adaptive_flood_extra"] == 120, "S4: سقفِ فلود ۱۲۰")

xx["_adaptive_flood_extra"] = 0
xx["_adaptive_hard_until"] = 0
eng.adaptive_on_flood(600, now=now)
check(xx["_adaptive_flood_extra"] == 120, "S4: فلودِ ≥۶۰۰ → مستقیم سقف")
check(int(xx.get("_adaptive_hard_until") or 0) > now,
      "S4: فلودِ بزرگ → _adaptive_hard_until در آینده")

xx["_adaptive_flood_extra"] = 0
for hours, want in ((0.5, 0), (3.5, 30), (6, 60), (24, 90), (240, 90)):
    eng.started = now - int(hours * 3600)
    _f, up, tot = eng.adaptive_extra(now)
    check(up == want and tot == want,
          "S4: آپ‌تایم %sh → +%d (بود %d)" % (hours, want, up))
eng.started = now
print("DONE S4 adaptive")


# ═══════════ S5 — فرمول‌های زمان‌بندی ═══════════
a = src.find("    def op_gap_seconds():")
b = src.find("    def response_delay_seconds():")
assert a > 0 and b > a, "timing helpers not found"
ded = "\n".join(ln[4:] if ln.startswith("    ") else ln
                for ln in src[a:b].splitlines())
tns = {"eng": eng, "time": time, "random": __import__("random"),
       "ex_cd": m.ExCooldown(gap_min=0, gap_max=0), "asyncio": asyncio}
exec(ded, tns)
membership_check_delay = tns["membership_check_delay"]
reminder_delay = tns["reminder_delay"]
watch_delay_seconds = tns["watch_delay_seconds"]
op_gap_seconds = tns["op_gap_seconds"]

check(all(15 <= op_gap_seconds() <= 20 for _ in range(50)),
      "S5: op_gap_seconds داخلِ ۱۵–۲۰")
check(all(15 <= membership_check_delay() <= 30 for _ in range(50)),
      "S5: چک عضویت ۱۵–۳۰")
check(all(20 <= reminder_delay() <= 40 for _ in range(50)),
      "S5: یادآوری ۲۰–۴۰")

# کفِ check/reminder از op_gap_min_sec گرفته می‌شود
xx["check_min_sec"] = 2
xx["check_max_sec"] = 3
xx["reminder_min_sec"] = 2
xx["reminder_max_sec"] = 3
check(all(membership_check_delay() >= 15 for _ in range(30)),
      "S5: کفِ چک = op_gap_min_sec (۱۵)")
check(all(reminder_delay() >= 15 for _ in range(30)),
      "S5: کفِ یادآوری = op_gap_min_sec (۱۵)")
xx["check_min_sec"], xx["check_max_sec"] = 15, 30
xx["reminder_min_sec"], xx["reminder_max_sec"] = 20, 40

# پله‌های watch_delay
tns["membership_check_delay"] = lambda: 10.0
watch_delay_seconds = tns["watch_delay_seconds"]
nowf = time.time()
for age_h, mult in ((0.1, 1), (0.49, 1), (1.9, 2), (5.9, 4), (10, 8)):
    rec = {"joined_at": int(nowf - age_h * 3600)}
    got = watch_delay_seconds(rec)
    check(abs(got - 10.0 * mult) < 0.5,
          "S5: watch_delay سن %sh → ×%d (بود %.1f)" % (age_h, mult, got))
print("DONE S5 timing formulas")


# ═══════════ S6 — سیم‌کشیِ صف ═══════════
for kind in ("check", "join", "leave", "reminder", "reply_joined", "say"):
    check('ex_cd.action("%s"' % kind in src,
          "S6: عملکردِ %s داخلِ صف است" % kind)
nq = src.count("queue=False")
check(nq <= 2, "S6: queue=False حداکثر در ۲ جا (بود %d)" % nq)
print("DONE S6 queue wiring")


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
    env["PORT"] = "8271"
    env["JAFJ_PORT"] = "8271"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "RENDER", "RENDER_SERVICE_NAME", "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY",
              "BOT_TOKEN", "API_ID", "API_HASH", "BACKUP_CHAT", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=300)
    return p.stdout, p.stderr, p.returncode


def main():
    print("--- spacing algorithm: pinned numbers ---")
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
