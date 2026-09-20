#!/usr/bin/env python3
"""دکمه‌ی «📚 آموزش فعال‌سازی» — منو + پنل مدیریت + ارسال کپی‌شده.

قفل کردن رفتار کاملِ فیچر:

  1. منوی اصلی دکمه‌ی «📚 آموزش فعال‌سازی» (m:tut) را دارد — سبز (success)؛
     پنل مدیر هم دکمه‌ی «🎬 آموزش فعال‌سازی» (a:tut) را دارد.
  2. اگر مدیر هنوز محتوا ثبت نکرده، متن پیش‌فرض (DEFAULT_TUTORIAL) می‌رود —
     دکمه هیچ‌وقت «خالی» نیست.
  3. با محتوای ثبت‌شده، پیام‌ها <b>کپی</b> می‌شوند (send_message با آبجکتِ
     Message در Telethon) — بدون هدر فوروارد، مثل پیام خودِ ربات؛
     آلبوم هم یک‌جا و با کپشن‌ها فرستاده می‌شود.
  4. اگر کپی شکست (مثلاً FILE_REFERENCE منقضی)، همان پیام فوروارد می‌شود؛
     اگر هیچ‌طور نشد، متن پیش‌فرض می‌رود — کاربر هیچ‌وقت بی‌جواب نمی‌ماند.
  5. ثبت محتوا از پنل: مدیر در حالت tut_set هر پیامی بفرستد (متن، عکس،
     آلبوم…) به لیست اضافه می‌شود؛ «✅ تمام شد» (a:tut_done) ذخیره می‌کند
     در manager_config.json (tut_chat + tut_ids) — و می‌ماند بعد از ری‌استارت.
  6. زدن هر دکمه‌ی دیگر در حال tut_set = لغوِ ثبت (fsm پاک می‌شود)؛
     اما خودِ دکمه‌ی «تمام شد» مرحله را نمی‌کُشد.
  7. «👁 پیش‌نمایش» (a:tut_view) دقیقاً همان چیزی را به مدیر می‌فرستد
     که کاربر خواهد گرفت.

روش اجرا مثل بقیه‌ی تست‌ها: سورس واقعی manager_82 با telethon قلابی
و دیتابیس واقعی (فایلی) ران می‌شود؛ هندلر NewMessage هم از همان سورس
استخراج و مستقیم صدا زده می‌شود.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_tutorial_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
SRC_REPO = os.environ.get("REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── minimal fake telethon, enough for `import manager_82` ──
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

# ── inner script: drive the REAL Manager with a fake bot ──
INNER = textwrap.dedent('''
    import os, sys, json, asyncio, time, datetime, textwrap
    sys.path.insert(0, os.getcwd())
    import manager_82 as M

    ADMIN = 100
    results = []

    def check(cond, name):
        results.append((name, bool(cond)))

    class FakeTutMsg:
        def __init__(self, mid, raw_text="", media=None, grouped_id=None):
            self.id = mid
            self.raw_text = raw_text
            self.media = media
            self.grouped_id = grouped_id
            self.entities = []

    class FakeBot:
        def __init__(self):
            self.msg_sends = []   # کپی پیام: (uid, message_obj, kw)
            self.text_sends = []  # say: (uid, text, kw)
            self.files = []       # آلبوم: (uid, media_list, caption, kw)
            self.forwards = []    # (uid, ids, chat)
            self.msgs = {}        # chat -> {id: FakeTutMsg}
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
        def __init__(self, uid, mid, raw_text="", photo=None, document=None):
            self.sender_id = uid
            self.chat_id = uid
            self.id = mid
            self.raw_text = raw_text
            self.photo = photo
            self.document = document
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
        # ---------- 0) سیم‌کشی سورس ----------
        src = open("manager_82.py", encoding="utf-8").read()
        check('B("📚 آموزش فعال‌سازی", "m:tut", "success")' in src,
              "main menu has green m:tut button")
        check('B("🎬 آموزش فعال‌سازی", "a:tut", "success")' in src,
              "admin menu has a:tut button")
        check('if data == "m:tut":' in src, "on_callback handles m:tut")
        check('"ok_days", "acct_n", "fjoin_add", "tut_set"' in src,
              "fsm cleanup list includes tut_set")
        check('data in ("wq:0", "kc:x", "a:tut_done")' in src,
              "a:tut_done survives fsm cleanup")
        check('"tut_chat": 0' in src and '"tut_ids": []' in src,
              "DEFAULTS has tut_chat/tut_ids")
        check("pend.append(ev.id)" in src and 'stp == "tut_set"' in src,
              "NewMessage captures tut_set content")

        # ---------- منوها ----------
        rows = M.main_menu(is_admin=False, shop_on=True, points_on=True)
        flat = [b for row in rows for b in row]
        tut = [b for b in flat if b[1][1] == b"m:tut"]
        check(len(tut) == 1 and tut[0][2].get("style") == "success",
              "menu button m:tut present, green")
        arows = M.admin_menu()
        aflat = [b for row in arows for b in row]
        check(any(b[1][1] == b"a:tut" for b in aflat), "admin menu has a:tut")

        # ---------- Manager واقعی + ربات قلابی ----------
        real_time = time.time
        fake_now = [real_time()]
        time.time = lambda: fake_now[0]

        m = M.Manager()
        bot = FakeBot()
        m.bot = bot
        m.cfg["admin_ids"] = [ADMIN]

        # ---------- 1) بدون محتوا → متن پیش‌فرض ----------
        check(m.tut_src() == (0, []), "tut_src empty by default")
        fake_now[0] += 3
        await m.send_tutorial(200)
        check(any(t and t.startswith("📚") for _, t, _ in bot.text_sends
                  if _ == 200) or any(t and t.startswith("📚")
                                      for u, t, _ in bot.text_sends if u == 200),
              "no content -> DEFAULT_TUTORIAL sent")
        check(M.DEFAULT_TUTORIAL in [t for u, t, _ in bot.text_sends if u == 200],
              "sent default == DEFAULT_TUTORIAL constant")

        # ---------- 2) کپی محتوا: متن + آلبوم دوتایی ----------
        bot.msgs[ADMIN] = {
            1: FakeTutMsg(1, "سلام! این آموزش فعال‌سازی است."),
            2: FakeTutMsg(2, "توضیح ویدیو", media=("doc", "video"),
                          grouped_id="G1"),
            3: FakeTutMsg(3, "", media=("doc", "video2"), grouped_id="G1"),
        }
        m.cfg["tut_chat"] = ADMIN
        m.cfg["tut_ids"] = [1, 2, 3]
        m.cfg.save()

        groups = m._tut_groups([bot.msgs[ADMIN][i] for i in (1, 2, 3)])
        check(len(groups) == 2 and len(groups[1]) == 2,
              "_tut_groups keeps album together")

        fake_now[0] += 3
        await m.send_tutorial(201)
        copies = [x for x in bot.msg_sends if x[0] == 201]
        albums = [x for x in bot.files if x[0] == 201]
        fwds = [x for x in bot.forwards if x[0] == 201]
        check(len(copies) == 1 and copies[0][1].id == 1,
              "single message copied via send_message(Message) - no forward header")
        check(len(albums) == 1 and isinstance(albums[0][1], list)
              and len(albums[0][1]) == 2,
              "album sent as one send_file with both medias")
        check(albums and albums[0][2] == ["توضیح ویدیو", ""],
              "album captions preserved per item")
        check(not fwds, "no forward when copy works")
        check(any("آموزش فعال‌سازی" in (t or "") and "🚀" in str(b)
                  for u, t, b in bot.text_sends if u == 201),
              "helper message with setup button after content")

        # ---------- 3) کپی شکست → فوروارد ----------
        bot.copy_fail = True
        fake_now[0] += 3
        await m.send_tutorial(202)
        check(len([x for x in bot.forwards if x[0] == 202]) >= 1,
              "copy failure -> forward fallback")

        # ---------- 4) کپی و فوروارد هر دو شکست → پیش‌فرض ----------
        bot.fwd_fail = True
        fake_now[0] += 3
        await m.send_tutorial(203)
        check(M.DEFAULT_TUTORIAL in [t for u, t, _ in bot.text_sends if u == 203],
              "total failure -> DEFAULT_TUTORIAL")
        bot.copy_fail = False
        bot.fwd_fail = False

        # ---------- 5) ثبت محتوا از پنل (هندلر واقعی NewMessage) ----------
        block_start = src.index("@self.bot.on(events.NewMessage(incoming=True))")
        block_end = src.index("@self.bot.on(events.CallbackQuery)")
        raw_lines = src[block_start:block_end].split("\\n")
        # خط اول (دکوریتور) بدون تورفتگی پیدا شده؛ از بقیه دقیقاً ۸ فاصله بردار
        handler_block = "\\n".join(
        raw_lines[0] if i == 0 else (raw_lines[i][8:] if raw_lines[i].startswith(" " * 8) else raw_lines[i])
        for i in range(len(raw_lines)))
        ns = dict(vars(M))
        ns["self"] = m
        ns["events"] = M_events_stub
        exec(compile(handler_block, "<newmessage-handler>", "exec"), ns)
        handler = bot.handlers[-1]
        check(callable(handler), "NewMessage handler extracted from real source")

        m.fsm[ADMIN] = {"step": "tut_set", "tut_chat": 0, "tut_pending": []}
        fake_now[0] += 3
        evs = [FakeMsgEv(ADMIN, 501, "متن آموزش"),
               FakeMsgEv(ADMIN, 502, "کپشن ویدیو", photo=("photo", 1)),
               FakeMsgEv(ADMIN, 503, "", photo=("photo", 2))]
        for ev in evs:
            await handler(ev)
        check(m.fsm[ADMIN]["tut_pending"] == [501, 502, 503],
              "admin messages captured in order (text + album items)")
        check(any("عکس" in (t or "") for u, t, _ in bot.text_sends
                  if u == ADMIN and t),
              "confirmation mentions media kind")

        # ---------- 6) «✅ تمام شد» ذخیره می‌کند ----------
        ev = FakeCbEv(ADMIN, "a:tut_done")
        await m.on_callback(ev)
        check(m.cfg["tut_ids"] == [501, 502, 503], "a:tut_done saves tut_ids")
        check(m.cfg["tut_chat"] == ADMIN, "a:tut_done saves tut_chat")
        check(ADMIN not in m.fsm, "fsm cleared after save")
        with open(M.CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        check(saved.get("tut_ids") == [501, 502, 503]
              and saved.get("tut_chat") == ADMIN,
              "settings persisted to manager_config.json (restart-safe)")
        check(any("ذخیره شد" in (t or "") for t, _ in ev.edits),
              "confirmation edited in panel")

        # ---------- 7) دکمه‌ی دیگر = لغو ثبت ----------
        m.fsm[ADMIN] = {"step": "tut_set", "tut_chat": 0, "tut_pending": [999]}
        ev = FakeCbEv(ADMIN, "m:home")
        await m.on_callback(ev)
        check(ADMIN not in m.fsm, "any other button cancels tut_set")

        # ---------- 8) پیش‌نمایش همان است که کاربر می‌گیرد ----------
        bot.msgs[ADMIN][501] = FakeTutMsg(501, "متن آموزش")
        bot.msgs[ADMIN][502] = FakeTutMsg(502, "کپشن ویدیو", media=("doc", "v"))
        bot.msgs[ADMIN][503] = FakeTutMsg(503, "", media=("doc", "v2"))
        bot.msg_sends = []
        ev = FakeCbEv(ADMIN, "a:tut_view")
        await m.on_callback(ev)
        preview = [x for x in bot.msg_sends if x[0] == ADMIN]
        check(len(preview) == 3 and preview[0][1].id == 501,
              "a:tut_view copies content to admin")
        check(any("پیش‌نمایش" in (t or "") for t, _ in ev.edits),
              "preview confirmation edited")

        time.time = real_time


    asyncio.run(main())
    print(f"BUILD {M.BUILD_VERSION}")
    for name, ok in results:
        print(f"CHECK {'PASS' if ok else 'FAIL'} - {name}")
    bad = [name for name, ok in results if not ok]
    print("TUTORIAL_RESULT", "PASS" if not bad else "FAIL")

''')

INNER = INNER.replace("M_events_stub", "type('E', (), {'NewMessage': type('NM', (), {'__init__': lambda s, *a, **k: None})})")


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
                       capture_output=True, text=True, timeout=120)
    return p.stdout + p.stderr


if __name__ == "__main__":
    print("--- آموزش فعال‌سازی: منو + پنل + کپی + ثبت محتوا ---")
    reset()
    out = run_inner(8171)
    checks = [l for l in out.splitlines() if l.startswith("CHECK")]
    print("\n".join(checks) or out[-2000:])
    print("\n".join(l for l in out.splitlines()
                    if l.startswith(("BUILD", "TUTORIAL_RESULT"))))
    good = "TUTORIAL_RESULT PASS" in out and not any(
        c.endswith("FAIL") or " FAIL " in c for c in checks)
    print("tutorial:", "PASS" if good else "FAIL")
    if not good:
        print(out[-4000:])
    sys.exit(0 if good else 1)
