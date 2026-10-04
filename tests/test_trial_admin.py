#!/usr/bin/env python3
"""پنلِ «🎁 تست رایگان» در پنل مدیر: مدتِ دلخواه + ریست برای همه.

درخواست کاربر: «می‌خوام توی پنل مدیر تعیین کنم تست رایگان چند ساعت باشه
(نیم‌ساعت، ۱ ساعت، هرچی) و بتونم ریست کنم؛ یعنی دوباره به همه تست رایگان بدم».

آنچه این تست قفل می‌کند:

  ۱. دکمه‌ی منوی مدیر «🎁 تست رایگان: …» حالا صفحه‌ی تنظیمات را باز
     می‌کند (`a:trial`) — روشن/خاموش، مدت‌های آماده (30/60/120/180/
     360/720/1440 دقیقه)، یادآوری (5/10/15/30 دقیقه) و مقدار دلخواه.
  ۲. انتخاب مدت، `trial_minutes` را ذخیره می‌کند و همان لحظه در برچسبِ
     دکمه‌ی کاربر («🎁 تست رایگان 2 ساعت») و متن‌های کاربر (راه‌اندازی،
     بخشِ توضیحات، مانعِ «قبلاً استفاده شده») دیده می‌شود.
  ۳. یادآوری هرگز بیش از نصفِ مدت نمی‌شود (۳۰ دقیقه تست + یادآوری ۳۰
     دقیقه‌ای یعنی پیامِ فوری).
  ۴. «♻️ ریست تست برای همه» پرونده‌ی تستِ همه را پاک می‌کند تا دوباره
     واجد شرایط شوند؛ تستِ در حال اجرا قطع نمی‌شود (تایمرش می‌ماند)،
     اشتراکِ فعال و امتیازها دست نمی‌خورد.
  ۵. ریستِ تک‌کاربر از صفحه‌ی همان کاربر (`aut:<uid>`).
  ۶. مقدارِ دلخواه هم با «دقیقه» و هم با «2 ساعت» قابل ثبت است
     (سقف ۳۰ روز، مقدار نامعتبر رد می‌شود).

روش اجرا مثل بقیه‌ی تست‌ها: سورس واقعی manager_82 با telethon قلابی و
دیتابیس واقعی (فایلی) اجرا می‌شود و on_callback مستقیم صدا زده می‌شود.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_trial_admin_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
SRC_REPO = os.environ.get("REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAKE_TELETHON = textwrap.dedent('''
    class TelegramClient:
        def __init__(self, session, api_id, api_hash, **kw):
            pass
        async def connect(self):
            return
        async def is_user_authorized(self):
            return True
        async def start(self, bot_token=None):
            return self
        async def disconnect(self):
            return
        async def get_me(self):
            class U:
                username = "fakebot"
                id = 1
            return U()
        def on(self, *a, **k):
            def deco(fn):
                return fn
            return deco
        async def run_until_disconnected(self):
            return
        async def send_message(self, *a, **k):
            class R:
                id = 1
            return R()
        async def get_entity(self, x):
            class E:
                username = None
            return E()
        async def send_file(self, *a, **k):
            return None
        async def forward_messages(self, *a, **k):
            return None
        async def get_messages(self, *a, **k):
            return []
        def iter_messages(self, *a, **k):
            async def _gen():
                return
                yield
            return _gen()
        async def download_media(self, *a, **k):
            return None

    class Button:
        @staticmethod
        def inline(*a, **k):
            return ("inline", a, k)
        @staticmethod
        def url(*a, **k):
            return ("url", a, k)
        @staticmethod
        def request_phone(*a, **k):
            return ("phone", a, k)
        @staticmethod
        def text(*a, **k):
            return ("text", a, k)
        @staticmethod
        def clear(*a, **k):
            return None

    class events:
        class NewMessage:
            def __init__(self, *a, **k):
                pass
        class CallbackQuery:
            def __init__(self, *a, **k):
                pass

    class _Err(Exception):
        pass
    FloodWaitError = _Err
    PhoneNumberBannedError = _Err
    PhoneNumberInvalidError = _Err
    SessionPasswordNeededError = _Err
    PhoneCodeInvalidError = _Err
    PhoneCodeExpiredError = _Err
    UserNotParticipantError = _Err
''')

FAKE_SESSIONS = textwrap.dedent('''
    class StringSession:
        def __init__(self, s=""):
            self._s = s or ""
            self.dc_id = 1
            self.server_address = "127.0.0.1"
            self.port = 443
            self.auth_key = b"fake-auth-key-1234567890"
        def save(self):
            return self._s

    class SQLiteSession:
        def __init__(self, *a, **k):
            pass
        def set_dc(self, *a, **k):
            pass
        def save(self):
            pass
        def close(self):
            pass
''')

FAKE_ERRORS = textwrap.dedent('''
    class FloodWaitError(Exception):
        def __init__(self, seconds=0, *a, **k):
            super().__init__(f"FloodWait {seconds}")
            self.seconds = int(seconds or 0)

    class PhoneNumberBannedError(Exception):
        pass
    class PhoneNumberInvalidError(Exception):
        pass
    class SessionPasswordNeededError(Exception):
        pass
    class PhoneCodeInvalidError(Exception):
        pass
    class PhoneCodeExpiredError(Exception):
        pass
    class UserNotParticipantError(Exception):
        pass
''')


INNER = textwrap.dedent('''
    import os, sys, asyncio, time
    sys.path.insert(0, os.getcwd())
    import manager_82 as M

    ADMIN = 100
    U_DONE = 201      # تستش تمام شده
    U_RUN = 202       # همین حالا داخل تست
    U_SUB = 203       # اشتراکِ فعال
    U_NEW = 204       # تازه‌وارد

    results = []

    def check(cond, name):
        results.append((name, bool(cond)))

    def btn_items(kb):
        out = []
        for row in (kb or []):
            for b in row:
                try:
                    out.append((b[1][0], b[1][1]))
                except Exception:
                    pass
        return out

    def btn_datas(kb):
        out = []
        for _, d in btn_items(kb):
            out.append(d.decode("utf-8", "ignore") if isinstance(d, (bytes, bytearray)) else d)
        return out

    def btn_texts(kb):
        return [t for t, _ in btn_items(kb)]

    class FakeBot:
        def __init__(self):
            self.text_sends = []
        def on(self, *a, **k):
            def deco(fn):
                return fn
            return deco
        async def send_message(self, uid, message=None, **kw):
            self.text_sends.append((uid, message, kw))
            return None
        async def get_messages(self, *a, **k):
            return []
        async def send_file(self, *a, **k):
            return None

    class FakeCbEv:
        def __init__(self, uid, data):
            self.sender_id = uid
            self.chat_id = uid
            self.data = data.encode()
            self.message_id = 777
            self.answers = []
            self.edits = []
        async def answer(self, t=""):
            self.answers.append(t)
        async def edit(self, text, parse_mode=None, buttons=None,
                       link_preview=False, **kw):
            self.edits.append((text, buttons))
            return True

    async def cb(mgr, data):
        """یک فشار دکمه‌ی مدیر — بدون ضدتکرار (تست سریع‌تر از ۲ ثانیه است)."""
        mgr._cb_dedup = {}
        ev = FakeCbEv(ADMIN, data)
        await mgr.on_callback(ev)
        return ev

    async def main():
        src = open("manager_82.py", encoding="utf-8").read()

        # ═══ T1 — برچسبِ مدت ═══
        check(M.trial_duration_label(30) == "30 دقیقه", "T1: 30 → «30 دقیقه»")
        check(M.trial_duration_label(60) == "1 ساعت", "T1: 60 → «1 ساعت»")
        check(M.trial_duration_label(90) == "1 ساعت و 30 دقیقه",
              "T1: 90 → «1 ساعت و 30 دقیقه»")
        check(M.trial_duration_label(1440) == "24 ساعت", "T1: 1440 → «24 ساعت»")
        check(M.trial_duration_label(0) == "30 دقیقه",
              "T1: مقدار خراب → پیش‌فرض 30 دقیقه")
        check(M.DEFAULTS.get("trial_minutes") == 30,
              "T1: پیش‌فرضِ تنظیمات همان ۳۰ دقیقه می‌ماند")

        # ═══ T2 — صفحه‌ی تست در پنل مدیر ═══
        m = M.Manager()
        bot = FakeBot()
        m.bot = bot
        m.cfg["admin_ids"] = [ADMIN]
        m.cfg["trial_on"] = True
        m.cfg["trial_minutes"] = 30
        m.cfg["trial_warning_minutes"] = 10

        check('data.startswith("a:") and adm' in src
              and 'if k == "trial":' in src, "T2: شاخه‌ی a:trial در on_callback")
        check('B(tr_lbl, "a:trial"' in src,
              "T2: دکمه‌ی منوی مدیر حالا به صفحه‌ی تست وصل است")

        ev = await cb(m, "a:trial")
        txt, kb = ev.edits[-1]
        datas = btn_datas(kb)
        check("30 دقیقه" in txt and "یادآوری" in txt,
              "T2: صفحه مدت و یادآوری را نشان می‌دهد")
        for d in ("a:trial_tog", "a:trial_min:30", "a:trial_min:60",
                  "a:trial_min:120", "a:trial_min:180", "a:trial_min:360",
                  "a:trial_min:720", "a:trial_min:1440", "a:trial_min:x",
                  "a:trial_warn:10", "a:trial_reset"):
            check(d in datas, "T2: دکمه‌ی %s هست" % d)
        check(any(t.startswith("✅ 30 دقیقه") for t in btn_texts(kb)),
              "T2: مدتِ فعلی با ✅ مشخص است")

        # انتخاب مدت ۲ ساعت
        ev = await cb(m, "a:trial_min:120")
        check(m.cfg["trial_minutes"] == 120, "T2: a:trial_min:120 ذخیره شد")
        txt, kb = ev.edits[-1]
        check("2 ساعت" in txt and any("✅ 2 ساعت" in t for t in btn_texts(kb)),
              "T2: صفحه با مدتِ جدید (2 ساعت) دوباره رندر شد")

        # یادآوری: هرگز بیشتر از نصفِ مدت
        m.cfg["trial_minutes"] = 30
        ev = await cb(m, "a:trial_warn:30")
        check(m.cfg["trial_warning_minutes"] == 15,
              "T2: یادآوری ۳۰ دقیقه‌ای برای تستِ ۳۰ دقیقه‌ای → ۱۵ دقیقه (نصف)")
        m.cfg["trial_minutes"] = 120
        ev = await cb(m, "a:trial_warn:30")
        check(m.cfg["trial_warning_minutes"] == 30,
              "T2: تست ۲ ساعته → یادآوری ۳۰ دقیقه مجاز است")

        # خاموش/روشن از همان صفحه
        ev = await cb(m, "a:trial_tog")
        check(m.cfg["trial_on"] is False and "🔴" in ev.edits[-1][0],
              "T2: دکمه‌ی خاموش‌کردن کار می‌کند")
        ev = await cb(m, "a:trial_tog")
        check(m.cfg["trial_on"] is True, "T2: روشن‌کردن دوباره")

        # ═══ T3 — تنظیم مدت: عددی و ساعتی ═══
        check(m._parse_trial_minutes("90") == 90, "T3: «90» → ۹۰ دقیقه")
        check(m._parse_trial_minutes("2 ساعت") == 120, "T3: «2 ساعت» → ۱۲۰ دقیقه")
        check(m._parse_trial_minutes("۱.۵ ساعت") == 90,
              "T3: «۱.۵ ساعت» (ارقام فارسی) → ۹۰ دقیقه")
        check(m._parse_trial_minutes("نیم ساعت") == 0,
              "T3: متن نامعتبر → ۰")
        check(m._parse_trial_minutes("500000") == 30 * 24 * 60,
              "T3: سقف ۳۰ روز اعمال می‌شود")
        mins, warn = m._set_trial_minutes(45)
        check(mins == 45 and warn <= 22 and m.cfg["trial_minutes"] == 45,
              "T3: _set_trial_minutes هم ذخیره می‌کند و هم یادآوری را می‌بندد")
        check("stp == \\"trial_min" in src or 'stp == "trial_min"' in src,
              "T3: مرحله‌ی trial_min در on_message هندل می‌شود")

        # ═══ T4 — مدت در متن‌های کاربر ═══
        m.cfg["trial_minutes"] = 120
        check(m.trial_label() == "2 ساعت", "T4: trial_label از تنظیمات می‌خواند")
        kb = M.main_menu(False, True, True, False, False, True,
                         has_cmds=False, has_hub=True,
                         trial_label=m.trial_label())
        check(any(t == "🎁 تست رایگان 2 ساعت" for t in btn_texts(kb)),
              "T4: دکمه‌ی کاربر مدتِ تنظیم‌شده را نشان می‌دهد")
        hub = m.hub_default_text("trial")
        check("2 ساعت" in hub, "T4: بخشِ توضیحاتِ تست با مدت هم‌خوان است")

        # ═══ T5 — دیتابیسِ تست + ریست ═══
        db = m.db
        t0 = int(time.time())
        db.add(U_DONE, "done", "تمام‌شده", 0)
        db.set(U_DONE, status="expired", trial_used=1, trial_started_at=t0 - 7200,
               trial_expires_at=t0 - 3600, trial_warning_sent=1)
        db.add(U_RUN, "run", "در حال تست", 0)
        db.set(U_RUN, status="active", expires_at=t0 + 1800, trial_used=1,
               trial_started_at=t0 - 600, trial_expires_at=t0 + 1800)
        db.add(U_SUB, "sub", "اشتراکی", 0)
        db.set(U_SUB, status="active", expires_at=t0 + 30 * 86400)
        db.add(U_NEW, "new", "تازه", 0)

        check(m.trial_available(U_DONE) is False,
              "T5: کسی که تستش تمام شده، قبل از ریست واجد شرایط نیست")
        total, running, used = db.trial_stats()
        check(total >= 4 and running >= 1 and used >= 2,
              "T5: آمار پنل درست است (%d/%d/%d)" % (total, running, used))

        n, running_n = db.trial_reset_all()
        c_done = db.get(U_DONE)
        c_run = db.get(U_RUN)
        c_sub = db.get(U_SUB)
        check(n >= 4 and running_n >= 1, "T5: ریست همه اجرا شد")
        check(int(c_done["trial_used"]) == 0 and int(c_done["trial_started_at"]) == 0
              and int(c_done["trial_expires_at"]) == 0,
              "T5: پرونده‌ی تستِ کاربرِ تمام‌شده کامل پاک شد")
        check(int(c_run["trial_expires_at"]) == t0 + 1800
              and int(c_run["trial_started_at"]) == 0
              and int(c_run["trial_used"]) == 0,
              "T5: تایمرِ کسی که داخل تست است دست‌نخورده ماند")
        check(m.trial_available(U_DONE) is True and m.trial_available(U_RUN) is True,
              "T5: بعد از ریست، هر دو دوباره می‌توانند تست بگیرند")
        check(m.trial_active(U_RUN) is True,
              "T5: تستِ در حال اجرا قطع نشد (هنوز active است)")
        check(int(c_sub["trial_expires_at"]) == 0
              and int(c_sub["expires_at"]) == t0 + 30 * 86400,
              "T5: اشتراک دست‌نخورده ماند")
        check(m.trial_available(U_SUB) is False,
              "T5: کسی که اشتراک دارد هنوز واجد تست نیست")

        # ریستِ تک‌کاربر
        db.set(U_DONE, trial_used=1, trial_started_at=t0 - 100,
               trial_expires_at=t0 - 50)
        check(m.trial_available(U_DONE) is False,
              "T5: کاربرِ تست‌سوخته دوباره بسته شد")
        db.trial_reset_one(U_DONE)
        check(m.trial_available(U_DONE) is True,
              "T5: ریستِ تک‌کاربر او را واجد شرایط کرد")

        # ═══ T6 — صفحه‌ی کاربر و دکمه‌ی ریستش ═══
        c = db.get(U_DONE)
        kb = m._admin_user_kb(c)
        check("aut:%d" % U_DONE in btn_datas(kb),
              "T6: دکمه‌ی «♻️ ریست تست رایگان» در صفحه‌ی کاربر هست")
        check(any("ریست تست" in t for t in btn_texts(kb)),
              "T6: برچسبِ دکمه درست است")
        db.set(U_DONE, trial_used=1, trial_started_at=t0 - 100, trial_expires_at=t0 - 50)
        check(m.trial_available(U_DONE) is False, "T6: کاربر دوباره تست‌سوخته شد")
        ev = await cb(m, "aut:%d" % U_DONE)
        check(m.trial_available(U_DONE) is True and "ریست" in ev.edits[-1][0],
              "T6: شاخه‌ی aut: تستِ همان کاربر را از نو کرد")

        # ═══ T7 — تأییدِ ریستِ همه ═══
        ev = await cb(m, "a:trial_reset")
        check("مطمئنی؟" in ev.edits[-1][0]
              and "a:trial_reset_yes" in btn_datas(ev.edits[-1][1]),
              "T7: ریستِ همه اول تأیید می‌گیرد")
        db.set(U_DONE, trial_used=1, trial_started_at=t0 - 100, trial_expires_at=t0 - 50)
        ev = await cb(m, "a:trial_reset_yes")
        check("ریست شد" in ev.edits[-1][0] and m.trial_available(U_DONE) is True,
              "T7: با تأییدِ مدیر، همه دوباره واجد تست شدند")

        print("RESULTS " + repr(results))

    asyncio.run(main())
''')


def reset():
    shutil.rmtree(ROOT, ignore_errors=True)
    os.makedirs(APP, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    for f in ("manager_82.py", "95.py"):
        shutil.copy2(os.path.join(SRC_REPO, f), APP)
    tel = os.path.join(APP, "telethon")
    os.makedirs(tel, exist_ok=True)
    with open(os.path.join(tel, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_TELETHON)
    with open(os.path.join(tel, "sessions.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_SESSIONS)
    with open(os.path.join(tel, "errors.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_ERRORS)


def run_inner(port=8187):
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["PORT"] = str(port)
    env["JAFJ_PORT"] = str(port)
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY", "BACKUP_CHAT", "BACKUP_EVERY",
              "BOT_TOKEN", "API_ID", "API_HASH", "ADMIN_IDS"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", INNER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=180)
    return p.stdout + p.stderr


if __name__ == "__main__":
    print("--- پنل تست رایگان: مدت دلخواه + ریست برای همه ---")
    reset()
    out = run_inner()
    line = [ln for ln in out.splitlines() if ln.startswith("RESULTS ")]
    if not line:
        print(out[-4000:])
        print("ALL: FAIL")
        sys.exit(1)
    results = eval(line[0][len("RESULTS "):])
    bad = [(n, ok) for n, ok in results if not ok]
    print("%d checks, %d failed" % (len(results), len(bad)))
    for n, _ok in bad:
        print("FAIL", n)
    if bad:
        print("ALL: FAIL")
        sys.exit(1)
    print("ALL: PASS")
    sys.exit(0)
