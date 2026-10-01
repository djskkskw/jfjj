#!/usr/bin/env python3
"""سلامِ منوی اصلی با ساعت ایران + بخش «📋 دستورات آماده» در پنل مدیر.

  1. سرورِ هاست روی UTC است؛ سلام باید طبق Asia/Tehran انتخاب شود
     (قبلاً ظهر روی «صبح» و شب روی «ظهر» می‌ماند).
  2. مدیر از «📋 دستورات آماده» متن‌ها و جمله‌های سلام را تنظیم و
     به پیش‌فرض برمی‌گرداند؛ {name} جای اسم مشتری است.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_ready_texts_run")
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
    import os, sys, json, asyncio, time, datetime
    sys.path.insert(0, os.getcwd())
    import manager_82 as M

    ADMIN = 100
    USER = 200
    results = []

    def check(cond, name):
        results.append((name, bool(cond)))

    def btn_datas(kb):
        """لیست داده‌ی همه‌ی دکمه‌های شیشه‌ای یک کیبورد."""
        out = []
        for row in (kb or []):
            for b in row:
                try:
                    d = b[1][1] if isinstance(b, tuple) else None
                except Exception:
                    d = None
                if isinstance(d, (bytes, bytearray)):
                    out.append(d.decode("utf-8", "ignore"))
        return out

    def btn_texts(kb):
        out = []
        for row in (kb or []):
            for b in row:
                try:
                    out.append(b[1][0])
                except Exception:
                    pass
        return out

    class FakeMsg:
        def __init__(self, mid, raw_text="", media=None, grouped_id=None):
            self.id = mid
            self.raw_text = raw_text
            self.media = media
            self.grouped_id = grouped_id
            self.entities = []

    class FakeBot:
        def __init__(self):
            self.msg_sends = []     # کپی پیام: (uid, Message, kw)
            self.text_sends = []    # say: (uid, text, kw)
            self.files = []         # آلبوم: (uid, media_list, caption, kw)
            self.forwards = []      # (uid, ids, chat)
            self.msgs = {}          # chat -> {id: FakeMsg}
            self.copy_fail = False
            self.fwd_fail = False
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
                if self.copy_fail:
                    raise RuntimeError("copy exploded")
                self.msg_sends.append((uid, message, kw))
                return None
            self.text_sends.append((uid, message, kw))
            return None
        async def send_file(self, uid, file=None, caption=None, **kw):
            if self.copy_fail:
                raise RuntimeError("album copy exploded")
            self.files.append((uid, file, caption, kw))
            return None
        async def forward_messages(self, uid, ids=None, from_peer=None, **kw):
            if self.fwd_fail:
                raise RuntimeError("fwd exploded")
            self.forwards.append((uid, ids, from_peer))
            return None

    class FakeMsgEv:
        def __init__(self, uid, mid, raw_text="", photo=None, document=None,
                     grouped_id=None):
            self.sender_id = uid
            self.chat_id = uid
            self.id = mid
            self.raw_text = raw_text
            self.photo = photo
            self.document = document
            self.grouped_id = grouped_id
            self.video = self.gif = self.voice = None
            self.audio = self.sticker = self.contact = None
            self.media = None
            self.is_private = True
            self.message = type("M", (), {
                "date": datetime.datetime.now(),
                "contact": None, "media": None})()
        async def get_sender(self):
            class S:
                username = "admin"
                first_name = "ادمین"
            return S()

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

    async def main():
        src = open("manager_82.py", encoding="utf-8").read()
        M = sys.modules["manager_82"]
        real_time = time.time
        fake_now = [real_time()]
        time.time = lambda: fake_now[0]       # ضد‌تکرارِ callback ۲ ثانیه‌ای

        async def cb(uid, data):
            fake_now[0] += 5
            e = FakeCbEv(uid, data)
            await m.on_callback(e)
            return e

        # ---------- 1) ساعت: Asia/Tehran، نه ساعت سرور ----------
        check(M.BOT_TZ_NAME == "Asia/Tehran", "default timezone is Asia/Tehran")
        class FixedDT(datetime.datetime):
            fixed = None
            @classmethod
            def now(cls, tz=None):
                return cls.fixed.astimezone(tz) if tz else cls.fixed.replace(tzinfo=None)
        real_dt = M.datetime
        M.datetime = FixedDT
        def at_utc(h, mi=0):
            FixedDT.fixed = datetime.datetime(2026, 10, 1, h, mi, tzinfo=datetime.timezone.utc)
        try:
            # 08:30 UTC = 12:00 تهران → ظهر (قبلاً: صبح)
            at_utc(8, 30)
            check(M.local_now().hour == 12, "08:30 UTC is 12:xx in Tehran")
            m = M.Manager()
            m.cfg["admin_ids"] = [ADMIN]
            noon = set(M.Manager.GREET_DEFAULTS["greet_noon"])
            morning = set(M.Manager.GREET_DEFAULTS["greet_morning"])
            evening = set(M.Manager.GREET_DEFAULTS["greet_evening"])
            night = set(M.Manager.GREET_DEFAULTS["greet_night"])
            check(all(m.greet() in noon for _ in range(30)), "12:00 Tehran greets noon")
            at_utc(5, 0)   # 08:30 تهران
            check(all(m.greet() in morning for _ in range(30)), "08:30 Tehran greets morning")
            at_utc(14, 0)  # 17:30 تهران
            check(all(m.greet() in evening for _ in range(30)), "17:30 Tehran greets evening")
            at_utc(18, 0)  # 21:30 تهران
            check(all(m.greet() in night for _ in range(30)), "21:30 Tehran greets night")
            at_utc(20, 45) # 00:15 تهران
            check(all(m.greet() in night for _ in range(30)), "00:15 Tehran greets night")
            at_utc(1, 0)   # 04:30 تهران
            check(all(m.greet() in night for _ in range(30)), "04:30 Tehran still night")
            check(m.greet_key(5) == "greet_morning" and m.greet_key(11) == "greet_morning"
                  and m.greet_key(12) == "greet_noon" and m.greet_key(16) == "greet_noon"
                  and m.greet_key(17) == "greet_evening" and m.greet_key(20) == "greet_evening"
                  and m.greet_key(21) == "greet_night" and m.greet_key(4) == "greet_night",
                  "greeting slot boundaries")

            # ---------- 2) پنل «📋 دستورات آماده» ----------
            check('"a:rt"' in src, "admin menu has the 📋 دستورات آماده button")
            check("a:rt" in btn_datas(M.admin_menu()), "admin_menu() exposes a:rt")
            ev = await cb(ADMIN, "a:rt")
            datas = btn_datas(ev.edits[-1][1])
            check(all(f"a:rt:{r[0]}" in datas for r in M.Manager.READY_TEXTS),
                  "list page has a button per text")
            check("دستورات آماده" in ev.edits[-1][0], "list page titled دستورات آماده")

            # پیام‌هایِ متنیِ مدیر با هندلر واقعی
            block_start = src.index("@self.bot.on(events.NewMessage(incoming=True))")
            block_end = src.index("@self.bot.on(events.CallbackQuery)")
            raw_lines = src[block_start:block_end].split("\\n")
            handler_block = "\\n".join(
                raw_lines[0] if i == 0 else
                (raw_lines[i][8:] if raw_lines[i].startswith(" " * 8) else raw_lines[i])
                for i in range(len(raw_lines)))
            bot = FakeBot()
            m.bot = bot
            ns = dict(vars(M))
            ns["self"] = m
            ns["events"] = type('E', (), {'NewMessage': type('NM', (), {'__init__': lambda s, *a, **k: None})})
            exec(compile(handler_block, "<newmessage-handler>", "exec"), ns)
            handler = bot.handlers[-1]

            ev = await cb(ADMIN, "a:rt:g_noon")
            check("a:rte:g_noon" in btn_datas(ev.edits[-1][1])
                  and "a:rtr:g_noon" not in btn_datas(ev.edits[-1][1]),
                  "item page: edit button, no reset while default")
            ev = await cb(ADMIN, "a:rte:g_noon")
            check((m.fsm.get(ADMIN) or {}).get("step") == "rt_set"
                  and m.fsm[ADMIN]["rt_id"] == "g_noon", "edit starts rt_set step")
            await handler(FakeMsgEv(ADMIN, 901, "{name} جان، ظهرت بخیر 🌞\\n\\nسلام {name}"))
            check(ADMIN not in m.fsm, "step finished after the text")
            check(m.cfg["greet_noon"] == "{name} جان، ظهرت بخیر 🌞\\nسلام {name}",
                  "greeting lines saved (blank lines dropped)")
            with open(M.CONFIG_FILE, encoding="utf-8") as f:
                check(json.load(f)["greet_noon"].startswith("{name} جان"),
                      "greeting persisted to manager_config.json")

            at_utc(8, 30)
            m.db.add(USER, "u", "علی", 0)
            hi = m.home_text(USER)
            check("علی جان، ظهرت بخیر" in hi or "سلام علی" in hi,
                  "home text puts the customer's name where {name} is")
            check("{name}" not in hi, "no raw {name} in the home text")

            # بدون اسم: جای اسم خالی می‌شود
            ns2 = m.cfg["greet_noon"]
            m.cfg["greet_noon"] = "{name} جان ظهرت بخیر"
            m.db.set(USER, name="")
            check("{name}" not in m.home_text(USER) and "  " not in
                  m.home_text(USER).split("\\n")[0], "no name -> placeholder dropped cleanly")
            m.cfg["greet_noon"] = ns2

            # بازنشانی
            ev = await cb(ADMIN, "a:rt:g_noon")
            check("a:rtr:g_noon" in btn_datas(ev.edits[-1][1]), "reset button when customised")
            ev = await cb(ADMIN, "a:rtr:g_noon")
            check(m.cfg["greet_noon"] == "" and
                  set(m.greet_options("greet_noon")) == noon,
                  "reset returns to the default greetings")

            # متن‌های تکی: خوش‌آمد / منقضی / پشتیبانی
            for rid, key, val in (("welcome", "welcome", "سلام به جفج"),
                                  ("expired", "expired_text", "اشتراکت تمام شد"),
                                  ("contact", "contact", "@sup")):
                ev = await cb(ADMIN, f"a:rte:{rid}")
                await handler(FakeMsgEv(ADMIN, 910, val))
                check(m.cfg[key] == val, f"{rid} text saved to cfg[{key}]")
            ev = await cb(ADMIN, "a:rt:welcome")
            check("سلام به جفج" in ev.edits[-1][0], "item page shows the current text")
            ev = await cb(ADMIN, "a:rte:welcome")
            await handler(FakeMsgEv(ADMIN, 911, "پیش‌فرض"))
            check(m.cfg["welcome"] == "", "typing «پیش‌فرض» clears the text")

            # ورودِ HTML امن نمایش داده می‌شود
            m.cfg["welcome"] = "<b>x"
            ev = await cb(ADMIN, "a:rt:welcome")
            check("&lt;b&gt;x" in ev.edits[-1][0], "stored text is HTML-escaped in the panel")

            # غیرمدیر راهی ندارد
            ev = await cb(USER, "a:rt")
            check(not any("دستورات آماده" in (e[0] or "") for e in ev.edits),
                  "non-admin cannot open the page")

            # رفتن به صفحه‌ی دیگر مرحله‌ی نیمه‌کاره را لغو می‌کند
            ev = await cb(ADMIN, "a:rte:contact")
            ev = await cb(ADMIN, "m:home")
            check(ADMIN not in m.fsm, "any other button cancels rt_set")

            # ---------- 3) fallback منطقه‌زمانی ----------
            M.BOT_TZ_NAME = "Asia/Tehran"
            real_zi = sys.modules.get("zoneinfo")
            sys.modules["zoneinfo"] = None   # tzdata/zoneinfo در دسترس نیست
            try:
                at_utc(8, 30)
                check(M.local_now().hour == 12, "fallback UTC+03:30 works without tzdata")
            finally:
                if real_zi is not None:
                    sys.modules["zoneinfo"] = real_zi
                else:
                    sys.modules.pop("zoneinfo", None)
        finally:
            M.datetime = real_dt
            time.time = real_time

    asyncio.run(main())
    print(f"BUILD {M.BUILD_VERSION}")
    for name, ok in results:
        print(f"CHECK {'PASS' if ok else 'FAIL'} - {name}")
    bad = [name for name, ok in results if not ok]
    print("READY_RESULT", "PASS" if not bad else "FAIL")

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
    print("--- سلام با ساعت ایران + دستورات آماده ---")
    reset()
    out = run_inner(8174)
    checks = [ln for ln in out.splitlines() if ln.startswith("CHECK")]
    print("\n".join(checks) or out[-3000:])
    print("\n".join(ln for ln in out.splitlines()
                    if ln.startswith(("BUILD", "READY_RESULT"))))
    good = "READY_RESULT PASS" in out and not any(
        c.endswith("FAIL") or " FAIL " in c for c in checks)
    print("ready texts:", "PASS" if good else "FAIL")
    if not good:
        print(out[-6000:])
    sys.exit(0 if good else 1)
