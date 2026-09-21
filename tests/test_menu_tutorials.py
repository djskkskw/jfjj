#!/usr/bin/env python3
"""دکمه‌های «📚 آموزش …» آخرِ منوها + ارسال خودکارِ آموزشِ سلف.

قفل کردن رفتار کاملِ فیچر:

  1. منوی «💳 کیف پول» (m:wallet) دکمه‌ی «📚 آموزش شارژ کیف پول» (tut:x:wallet)،
     منوی «🎯 خرید امتیاز» (m:packs) دکمه‌ی «📚 آموزش خرید امتیاز» (tut:x:points)
     و منوی «💎 اشتراک ماهانه» (m:plans) دکمه‌ی «📚 آموزش اشتراک ماهانه»
     (tut:x:sub) را دقیقاً <b>بالای</b> ردیف «⬅️ بازگشت» دارند (قبلاً اشتباهی
     زیر بازگشت بودند).
  2. زدن هر دکمه = ارسال خودکارِ آموزشِ همان کار (با پاسخ «در حال ارسال…»)
     با تحویلِ تمیز (tut_send_section با bare=True): فقط و فقط «محتوای ثبت‌شده‌ی
     مدیر» + «دکمه‌ی پایانِ همان کار» (💳 شارژ کیف پول / 🎯 خرید امتیاز /
     💎 اشتراک ماهانه) — بدون هیچ متنِ اضافه‌ای بینشان: نه «متن پایان» (note) و
     نه تزریقِ متنِ آماده‌ی پیش‌فرض وقتی مدیر پیام/محتوا ثبت کرده. دکمه به
     آخرین پیامِ محتوا می‌چسبد؛ اگر آخرین پیام آلبوم بود، یک پیامِ بدون‌متن فقط
     با دکمه می‌رود. fallback (وقتی محتوایی ثبت نشده): متن آماده‌ی پیش‌فرض +
     همان دکمه — بدون note. مسیرهای خودکار و تگ‌های آموزش (after_wallet و…) با
     متن پایان قبلی دست‌نخورده می‌مانند.
  3. زدن دوباره‌ی دکمه دوباره می‌فرستد (فقط ارسال خودکارِ رویدادها «یک‌بار» است).
  4. سلف: خودکار — به‌محض فعال‌شدن سلف، آموزش می‌رود (hook داخل finish و
     دکمه‌ی روشن‌کردن سرویس). اگر مدیر بخشِ «بعد از فعال‌سازی» نساخته باشد،
     متن آماده‌ی پیش‌فرض (tut_preset_text('after_run')) یک‌بار برای هر کاربر
     می‌رود (tut_schedule_self_default)؛ اگر بخش باشد همان می‌رود و پیش‌فرض
     کنار می‌رود.

روش اجرا مثل بقیه‌ی تست‌ها: سورس واقعی manager_82 با telethon قلابی
و دیتابیس واقعی (فایلی) ران می‌شود؛ هندلر on_callback هم از همان سورس
استخراج و مستقیم صدا زده می‌شود.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_menu_tut_run")
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
    USER = 200
    results = []

    def check(cond, name):
        results.append((name, bool(cond)))

    def btn_items(kb):
        """[(text, data), ...] همه‌ی دکمه‌های شیشه‌ای یک کیبورد."""
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

    class FakeMsg:
        """پیام ثبت‌شده‌ی مدیر در چتِ مرجع (برای _tut_load / _tut_copy)."""
        def __init__(self, mid, text="", media=None, gid=None):
            self.id = mid
            self.raw_text = text
            self.text = text
            self.caption = text
            self.media = media
            self.grouped_id = gid

    class FakeBot:
        def __init__(self):
            self.text_sends = []    # say: (uid, text, kw)
            self.msg_sends = []     # کپی پیام: (uid, Message, kw)
            self.files = []         # آلبوم
            self.forwards = []      # (uid, ids, chat)
            self.msgs = {}          # chat -> {id: FakeMsg}
            self.handlers = []
        def on(self, *a, **k):
            def deco(fn):
                self.handlers.append(fn)
                return fn
            return deco
        async def get_messages(self, chat, ids=None):
            store = self.msgs.get(chat, {})
            return [store.get(i) for i in (ids or [])]
        async def send_message(self, uid, message=None, **kw):
            if hasattr(message, "id") and hasattr(message, "media"):
                self.msg_sends.append((uid, message, kw))
                return None
            self.text_sends.append((uid, message, kw))
            return None
        async def send_file(self, uid, file=None, caption=None, **kw):
            self.files.append((uid, file, caption, kw))
            return None
        async def forward_messages(self, uid, ids=None, from_peer=None, **kw):
            self.forwards.append((uid, ids, from_peer))
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

    def texts_for(uid, bot):
        return [x for x in bot.text_sends if x[0] == uid]

    async def main():
        src = open("manager_82.py", encoding="utf-8").read()
        check('"tut:x:wallet"' in src and '"tut:x:points"' in src and '"tut:x:sub"' in src,
              "menus wire tut:x:wallet / tut:x:points / tut:x:sub")
        check("📚 آموزش شارژ کیف پول" in src and "📚 آموزش خرید امتیاز" in src
              and "📚 آموزش اشتراک ماهانه" in src,
              "labels: آموزش شارژ کیف پول / آموزش خرید امتیاز / آموزش اشتراک ماهانه")
        check('data.startswith("tut:x:")' in src, "on_callback has the tut:x: branch")
        check("bare=True" in src, "menu button delivers via tut_send_section bare mode")
        check(src.count("self.tut_schedule_self_default(") == 2,
              "both activation hooks (finish + s:on) schedule the self tutorial")

        real_time = time.time
        fake_now = [real_time()]
        time.time = lambda: fake_now[0]

        m = M.Manager()
        bot = FakeBot()
        m.bot = bot
        m.cfg["admin_ids"] = [ADMIN]

        # ---------- 1) دکمه‌ی آموزش دقیقاً بالای ردیف «⬅️ بازگشت» ----------\n
        ev = FakeCbEv(USER, "m:wallet")
        await m.on_callback(ev)
        datas, labels = btn_datas(ev.edits[-1][1]), btn_texts(ev.edits[-1][1])
        check(bool(datas) and labels[-1] == "⬅️ بازگشت" and datas[-1] == "m:home"
              and datas[-2] == "tut:x:wallet" and "📚 آموزش شارژ کیف پول" in labels,
              "wallet: 📚 آموزش شارژ کیف پول (tut:x:wallet) right above ⬅️ بازگشت")
        check("w:topup" in datas and "m:home" in datas,
              "wallet menu keeps its own buttons before the tutorial button")

        fake_now[0] += 5
        ev = FakeCbEv(USER, "m:packs")
        await m.on_callback(ev)
        datas, labels = btn_datas(ev.edits[-1][1]), btn_texts(ev.edits[-1][1])
        check(bool(datas) and labels[-1] == "⬅️ بازگشت" and datas[-1] == "m:home"
              and datas[-2] == "tut:x:points" and "📚 آموزش خرید امتیاز" in labels,
              "packs: 📚 آموزش خرید امتیاز (tut:x:points) right above ⬅️ بازگشت")

        fake_now[0] += 5
        ev = FakeCbEv(USER, "m:plans")
        await m.on_callback(ev)
        datas, labels = btn_datas(ev.edits[-1][1]), btn_texts(ev.edits[-1][1])
        check(bool(datas) and labels[-1] == "⬅️ بازگشت" and datas[-1] == "m:home"
              and datas[-2] == "tut:x:sub" and "📚 آموزش اشتراک ماهانه" in labels,
              "plans: 📚 آموزش اشتراک ماهانه (tut:x:sub) right above ⬅️ بازگشت")
        check(any((d or "").startswith("p:") for d in datas),
              "plans menu still lists the plan rows before the tutorial button")

        # ---------- 2) زدن دکمه = fallback تمیز: متن پیش‌فرض + دکمه، بدون note ----------\n
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "tut:x:wallet")
        await m.on_callback(ev)
        check(any("در حال ارسال" in a for a in ev.answers),
              "pressing the button answers: sending…")
        sends = texts_for(USER, bot)
        check(len(sends) == 1 and "آموزش کیف پول" in sends[0][1],
              "tut:x:wallet sends the wallet tutorial (default text)")
        check(btn_datas(sends[0][2].get("buttons")) == ["w:topup"],
              "fallback: default text + 💳 شارژ کیف پول button only (no extra rows)")
        check("دکمه‌ی زیر را بزن" not in (sends[0][1] or "")
              and (sends[0][1] or "").strip() != "👇",
              "fallback sends no note text")

        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "tut:x:points")
        await m.on_callback(ev)
        sends = texts_for(USER, bot)
        check(len(sends) == 1 and "آموزش خرید امتیاز" in sends[0][1]
              and "m:packs" in btn_datas(sends[0][2].get("buttons")),
              "tut:x:points sends the points tutorial + 🎯 خرید امتیاز button")

        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "tut:x:sub")
        await m.on_callback(ev)
        sends = texts_for(USER, bot)
        check(len(sends) == 1 and "آموزش اشتراک ماهانه" in sends[0][1]
              and "m:plans" in btn_datas(sends[0][2].get("buttons")),
              "tut:x:sub sends the subscription tutorial + 💎 اشتراک ماهانه button")

        # دکمه/کلید ناشناخته کاری نمی‌کند
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "tut:x:hack")
        await m.on_callback(ev)
        check(not texts_for(USER, bot), "unknown tut:x: key sends nothing")

        # ---------- 3) محتوای ثبت‌شده‌ی مدیر + دکمه — بدون متنِ اضافه ----------

        s, created = m.tut_new_preset("sub")
        check(created and s["preset"] == "sub",
              "admin can build the subscription tutorial from the ready preset")
        m.tut_update(s["id"], text="متن دلخواه مدیر برای اشتراک")
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "tut:x:sub")
        await m.on_callback(ev)
        sends = texts_for(USER, bot)
        check(len(sends) == 1 and sends[0][1] == "متن دلخواه مدیر برای اشتراک"
              and "m:plans" in btn_datas(sends[0][2].get("buttons")),
              "clean delivery: admin text + ending button attached (no note between)")
        check(all("دکمه‌ی زیر را بزن" not in (x[1] or "") for x in sends),
              "registered text: no note and no extra text")

        # زدن دوباره = دوباره می‌رود (فقط ارسال خودکارِ رویدادها «یک‌بار» است)
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "tut:x:sub")
        await m.on_callback(ev)
        sends = texts_for(USER, bot)
        check(len(sends) == 1 and sends[0][1] == "متن دلخواه مدیر برای اشتراک",
              "pressing the button again re-sends (force)")

        # خاموشِ بخش = برگشت به متن پیش‌فرض؛ دکمه هیچ‌وقت خالی نیست
        m.tut_update(s["id"], on=False)
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "tut:x:sub")
        await m.on_callback(ev)
        sends = texts_for(USER, bot)
        check(len(sends) == 1 and "آموزش اشتراک ماهانه" in sends[0][1],
              "section off -> default text; the button is never empty")
        m.tut_update(s["id"], on=True)

        # ---------- 4) پیام‌های ثبت‌شده: فقط محتوا + دکمه روی آخرین پیام ----------

        s3, created3 = m.tut_new_preset("points")
        check(created3, "admin can build the points tutorial from the ready preset")
        bot.msgs[555] = {1: FakeMsg(1, "پیام اول آموزش"),
                         2: FakeMsg(2, "پیام دوم آموزش")}
        m.tut_update(s3["id"], chat=555, ids=[1, 2])
        fake_now[0] += 5
        bot.text_sends, bot.msg_sends = [], []
        ev = FakeCbEv(USER, "tut:x:points")
        await m.on_callback(ev)
        copies = [x for x in bot.msg_sends if x[0] == USER]
        texts = texts_for(USER, bot)
        check(len(copies) == 2 and copies[-1][2].get("buttons") is not None
              and "m:packs" in btn_datas(copies[-1][2].get("buttons")),
              "registered messages: button attaches to the last content message")
        check(not texts,
              "registered messages: no note and no default-text injection")

        # آخرین پیام آلبوم -> یک پیامِ بدون‌متن فقط با دکمه
        bot.msgs[556] = {1: FakeMsg(1, "کپشن ۱", media="m1", gid=9),
                         2: FakeMsg(2, "کپشن ۲", media="m2", gid=9)}
        m.tut_update(s3["id"], chat=556, ids=[1, 2])
        fake_now[0] += 5
        bot.text_sends, bot.msg_sends, bot.files = [], [], []
        ev = FakeCbEv(USER, "tut:x:points")
        await m.on_callback(ev)
        texts = texts_for(USER, bot)
        check(len(bot.files) == 1, "album copied as one album")
        check(len(texts) == 1
              and not any(ch.isalnum() for ch in (texts[0][1] or ""))
              and "👇" not in (texts[0][1] or "")
              and "m:packs" in btn_datas(texts[0][2].get("buttons")),
              "album last -> one text-less message with just the ending button")

        # ---------- 5) مسیر تگ/خودکار (bare=False) با متن پایان قبلی دست‌نخورده ----------

        m.tut_update(s3["id"], chat=555, ids=[1], note="متن پایان مدیر")
        fake_now[0] += 5
        bot.text_sends, bot.msg_sends = [], []
        ok = await m.tut_send_section(USER, s3["id"], force=True)
        texts = texts_for(USER, bot)
        check(ok and any("متن پایان مدیر" in (x[1] or "") for x in texts),
              "auto/tag path (bare=False) still sends the note")
        check(any("آموزش خرید امتیاز" in (x[1] or "") for x in texts),
              "auto/tag path (bare=False) keeps the previous body behaviour")

        # ---------- 6) سلف: خودکار وقتی فعال شد ----------
        m.db.tut_reset_user(USER)
        check(m.tut_self_default_pending(USER) is True,
              "with no after_run section, the default self tutorial is pending")
        fake_now[0] += 5
        bot.text_sends = []
        check(m.tut_schedule_self_default(USER, wait=0) is True, "self default scheduled")
        for _ in range(40):
            await asyncio.sleep(0.05)
            if m.db.tut_done(USER, M.Manager.TUT_SELF_DEF_ID):
                break
        sends = texts_for(USER, bot)
        check(m.db.tut_done(USER, M.Manager.TUT_SELF_DEF_ID)
              and any("سلف روی اکانتت فعال شد" in (x[1] or "") for x in sends),
              "self tutorial auto-sent when the self got activated")
        check(m.tut_schedule_self_default(USER, wait=0) is False,
              "sent once per user — not again")

        # اگر مدیر بخشِ «بعد از فعال‌سازی» بسازد، همان می‌رود و پیش‌فرض کنار می‌رود
        m.db.tut_reset_user(USER)
        s2 = m.tut_new("بخش بعد از فعال‌سازی")
        m.tut_update(s2["id"], text="متن بخش مدیر")
        check(m.tut_self_default_pending(USER) is False,
              "an after_run section owns the event — default stays away")
        check(m.tut_schedule_self_default(USER, wait=0) is False,
              "no default send while an after_run section exists")

        time.time = real_time

    asyncio.run(main())
    print(f"BUILD {M.BUILD_VERSION}")
    for name, ok in results:
        print(f"CHECK {'PASS' if ok else 'FAIL'} - {name}")
    bad = [name for name, ok in results if not ok]
    print("MENU_TUT_RESULT", "PASS" if not bad else "FAIL")

''')


def reset():
    """Fresh APP with the current source + fake telethon."""
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


def run_inner(port):
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
    print("--- دکمه‌های آموزشِ منوها + ارسال خودکارِ آموزشِ سلف ---")
    reset()
    out = run_inner(8183)
    checks = [ln for ln in out.splitlines() if ln.startswith("CHECK")]
    print("\n".join(checks) or out[-3000:])
    print("\n".join(ln for ln in out.splitlines()
                    if ln.startswith(("BUILD", "MENU_TUT_RESULT"))))
    good = "MENU_TUT_RESULT PASS" in out and not any(
        c.endswith("FAIL") or " FAIL " in c for c in checks)
    print("menu tutorials:", "PASS" if good else "FAIL")
    if not good:
        print(out[-6000:])
    sys.exit(0 if good else 1)
