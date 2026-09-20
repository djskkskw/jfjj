#!/usr/bin/env python3
"""بخش‌بندی آموزش — هر بخش یک «تگ» برای کاربر + پنل مدیریت بخش‌ها.

قفل کردن این رفتار:

  1. پنل مدیر «🧩 بخش‌های آموزش» (a:secs) دارد؛ هر بخش جدا ساخته/ویرایش
     می‌شود (نام، ایموجی، محتوا، زمان ارسال، فاصله، متن پایان، دکمه‌ی پایان).
  2. محتوای هر بخش مثل آموزش اصلی <b>کپی</b> می‌شود (متن/کپشن دست‌نخورده،
     بدون هدر فوروارد) و آلبوم یک‌جا می‌رود.
  3. «دکمه‌ی پایان بخش» آخرِ محتوا می‌آید — مثلاً آخرِ آموزشِ کیف پول دکمه‌ی
     «💳 شارژ کیف پول». اگر آخرین پیام آلبوم بود (تلگرام روی آلبوم دکمه
     نمی‌گذارد)، دکمه در یک پیام جداگانه‌ی پایانی می‌رود.
  4. زمان ارسال هر بخش قابل انتخاب است: بعد از فعال‌سازی سلف، بعد از شارژ
     کیف پول، بعد از خرید امتیاز، بعد از خرید اشتراک، یا فقط با دکمه.
  5. بعد از راه‌اندازی موفق سلف، بخش‌های «بعد از فعال‌سازی» خودکار می‌روند
     (hook داخل finish و دکمه‌ی روشن‌کردن سرویس).
  6. هر بخش یک‌بار برای هر کاربر می‌رود (once)؛ زدن تگِ بخش توسط خودِ کاربر
     (tut:s:<id>) همیشه دوباره می‌فرستد.
  7. تگِ بخش‌ها پایین «📚 آموزش فعال‌سازی» به کاربر نشان داده می‌شود.

روش اجرا مثل بقیه‌ی تست‌ها: سورس واقعی manager_82 با telethon قلابی و
دیتابیس واقعی (فایلی) ران می‌شود؛ هندلر NewMessage و on_callback هم از
همان سورس استخراج و مستقیم صدا زده می‌شوند.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_tut_sections_run")
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
        # ---------- 0) سیم‌کشی سورس ----------
        src = open("manager_82.py", encoding="utf-8").read()
        check('"tut_auto": True' in src, "DEFAULTS has tut_auto")
        check('"tut_sections": []' in src, "DEFAULTS has tut_sections")
        check('B("🧩 بخش‌های آموزش", "a:secs", "success")' in src,
              "admin menu has a:secs button")
        check('B("🎬 آموزش فعال‌سازی", "a:tut", "success")' in src,
              "legacy a:tut button kept")
        check('if data.startswith("tut:s:")' in src,
              "user tag route tut:s:<id> present")
        check('self.tut_schedule(uid, "after_run",' in src,
              "auto hook after activation in finish()")
        check('self.tut_schedule(o["uid"], "after_wallet", wait=3)' in src,
              "auto hook after wallet top-up")
        check('self.tut_schedule(o["uid"], "after_points", wait=3)' in src,
              "auto hook after points purchase")
        check('self.tut_schedule(o["uid"], "after_sub", wait=3)' in src,
              "auto hook after subscription purchase")
        check('stp == "tut_set"' in src and '"sec_set"' in src,
              "content capture covers tut_set + sec_set")
        check('data in ("wq:0", "kc:x", "a:tut_done")' in src,
              "legacy fsm keep-list literal still there")
        check('a:sec_done' in src, "a:sec_done survives fsm cleanup")

        # ---------- 1) منوی مدیر ----------
        aflat = [b for row in M.admin_menu() for b in row]
        check(any(b[1][1] == b"a:secs" for b in aflat),
              "admin_menu renders a:secs")

        # ---------- Manager واقعی + ربات قلابی ----------
        real_time = time.time
        fake_now = [real_time()]
        time.time = lambda: fake_now[0]

        m = M.Manager()
        bot = FakeBot()
        m.bot = bot
        m.cfg["admin_ids"] = [ADMIN]

        # ---------- 2) ساخت/ویرایش بخش + ماندگاری ----------
        sec = m.tut_new("آموزش کامل پنل جفج")
        check(sec and sec["id"] == 1, "tut_new creates section #1")
        check(sec["when"] == "after_run" and sec["on"] and sec["once"],
              "new section defaults: after_run / on / once")
        m.tut_update(1, emoji="🎬", name="آموزش کامل پنل جفج", delay=0)
        sec2 = m.tut_new("آموزش شارژ کیف پول")
        m.tut_update(sec2["id"], emoji="💳", when="after_wallet")
        check(m.tut_find(2)["when"] == "after_wallet",
              "tut_update changes trigger")
        with open(M.CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        check([s["name"] for s in saved["tut_sections"]] ==
              ["آموزش کامل پنل جفج", "آموزش شارژ کیف پول"],
              "sections persisted to manager_config.json (restart-safe)")

        # ---------- 3) صفحه‌های پنل ----------
        ev = FakeCbEv(ADMIN, "a:secs")
        await m.on_callback(ev)
        check(ev.edits and "بخش‌های آموزش" in ev.edits[-1][0],
              "a:secs opens sections page")
        check("a:sec:1" in btn_datas(ev.edits[-1][1]),
              "sections page lists section buttons")

        ev = FakeCbEv(ADMIN, "a:sec:1")
        await m.on_callback(ev)
        txt, kb = ev.edits[-1]
        check("آموزش کامل پنل جفج" in txt, "a:sec:1 shows section page")
        check(("a:sec_set:1" in btn_datas(kb)) and ("a:sec_when:1" in btn_datas(kb))
              and ("a:sec_btn:1" in btn_datas(kb)),
              "section page has content/trigger/footer controls")

        ev = FakeCbEv(ADMIN, "a:sec_when:1")
        await m.on_callback(ev)
        check("a:sec_w:1:after_run" in btn_datas(ev.edits[-1][1]),
              "trigger page lists all events including after_run")
        ev = FakeCbEv(ADMIN, "a:sec_w:1:manual")
        await m.on_callback(ev)
        check(m.tut_find(1)["when"] == "manual", "picking trigger saves it")
        m.tut_update(1, when="after_run")

        # ---------- 4) دکمه‌ی پایان بخش (کیف پول) ----------
        ev = FakeCbEv(ADMIN, "a:sec_btn:2")
        await m.on_callback(ev)
        check("a:sec_b:2:w:topup" in btn_datas(ev.edits[-1][1]),
              "ending-button picker offers direct wallet top-up")
        ev = FakeCbEv(ADMIN, "a:sec_b:2:m:wallet")
        await m.on_callback(ev)
        s2 = m.tut_find(2)
        check(s2["btn_cmd"] == "m:wallet" and "کیف پول" in s2["btn_label"],
              "footer button target m:wallet + auto label")
        m.tut_update(2, note="برای شارژ کیف پول دکمه‌ی زیر را بزن 👇")
        ev = FakeCbEv(ADMIN, "a:sec_b:1:m:plans")
        await m.on_callback(ev)
        check(m.tut_find(1)["btn_cmd"] == "m:plans",
              "second section can have its own footer button (m:plans)")

        # ---------- 5) ثبت محتوا با هندلر واقعی ----------
        block_start = src.index("@self.bot.on(events.NewMessage(incoming=True))")
        block_end = src.index("@self.bot.on(events.CallbackQuery)")
        raw_lines = src[block_start:block_end].split("\\n")
        handler_block = "\\n".join(
            raw_lines[0] if i == 0 else
            (raw_lines[i][8:] if raw_lines[i].startswith(" " * 8) else raw_lines[i])
            for i in range(len(raw_lines)))
        ns = dict(vars(M))
        ns["self"] = m
        ns["events"] = type('E', (), {'NewMessage': type('NM', (), {'__init__': lambda s, *a, **k: None})})
        exec(compile(handler_block, "<newmessage-handler>", "exec"), ns)
        handler = bot.handlers[-1]

        ev = FakeCbEv(ADMIN, "a:sec_set:1")
        await m.on_callback(ev)
        check((m.fsm.get(ADMIN) or {}).get("step") == "sec_set",
              "a:sec_set starts section capture")
        check(m.fsm[ADMIN]["sec_id"] == 1, "capture remembers section id")

        fake_now[0] += 5
        for e in (FakeMsgEv(ADMIN, 601, "خوش آمدی!"),
                  FakeMsgEv(ADMIN, 602, "کپشن ویدیو", document=("doc", "video"),
                            grouped_id="G1"),
                  FakeMsgEv(ADMIN, 603, "", document=("doc", "video2"),
                            grouped_id="G1")):
            await handler(e)
        check(m.fsm[ADMIN]["tut_pending"] == [601, 602, 603],
              "section capture keeps order (text + album items)")
        check(any("بخش" in (t or "") for u, t, _ in bot.text_sends if u == ADMIN),
              "capture confirmation names the section")

        # دکمه‌ی دیگر = لغو ثبت
        m.fsm[ADMIN] = {"step": "sec_set", "sec_id": 1, "tut_chat": 0,
                        "tut_pending": [601]}
        ev = FakeCbEv(ADMIN, "m:home")
        await m.on_callback(ev)
        check(ADMIN not in m.fsm, "any other button cancels sec_set")

        # ثبت دوباره و ذخیره
        ev = FakeCbEv(ADMIN, "a:sec_set:1")
        await m.on_callback(ev)
        fake_now[0] += 5
        for e in (FakeMsgEv(ADMIN, 601, "خوش آمدی!"),
                  FakeMsgEv(ADMIN, 602, "کپشن ویدیو", document=("doc", "video"),
                            grouped_id="G1"),
                  FakeMsgEv(ADMIN, 603, "", document=("doc", "video2"),
                            grouped_id="G1")):
            await handler(e)
        ev = FakeCbEv(ADMIN, "a:sec_done:1")
        await m.on_callback(ev)
        s1 = m.tut_find(1)
        check(s1["ids"] == [601, 602, 603] and s1["chat"] == ADMIN,
              "a:sec_done saves ids+chat into the section")
        check(ADMIN not in m.fsm, "fsm cleared after saving section content")
        check(any("ذخیره شد" in (t or "") for t, _ in ev.edits),
              "save confirmation edited in panel")
        with open(M.CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        check(saved["tut_sections"][0]["ids"] == [601, 602, 603],
              "section content persisted")

        # ---------- 6) تحویل بخش: کپی + دکمه‌ی پایان ----------
        bot.msgs[ADMIN] = {
            601: FakeMsg(601, "خوش آمدی!"),
            602: FakeMsg(602, "کپشن ویدیو", media=("doc", "video"),
                         grouped_id="G1"),
            603: FakeMsg(603, "", media=("doc", "video2"), grouped_id="G1"),
            701: FakeMsg(701, "آموزش شارژ کیف پول"),
        }
        m.tut_update(2, chat=ADMIN, ids=[701])
        m.tut_update(1, btn_cmd="", btn_label="", note="")
        fake_now[0] += 5
        bot.msg_sends = []
        ok = await m.tut_send_section(USER, 1, force=True)
        copies = [x for x in bot.msg_sends if x[0] == USER]
        albums = [x for x in bot.files if x[0] == USER]
        check(ok and len(copies) == 1 and copies[0][1].id == 601,
              "single message copied to user (no forward header)")
        check(len(albums) == 1 and len(albums[0][1]) == 2,
              "album sent as one album")
        check(albums[0][2] == ["کپشن ویدیو", ""],
              "captions untouched (video keeps its caption)")
        check(m.db.tut_done(USER, 1), "section marked as sent for this user")

        # بخش کیف پول: محتوا + متن پایان + دکمه‌ی پایان «💳 شارژ کیف پول»
        fake_now[0] += 5
        bot.msg_sends, bot.files, bot.text_sends = [], [], []
        ok = await m.tut_send_section(USER, 2, force=True)
        copies = [x for x in bot.msg_sends if x[0] == USER]
        check(ok and len(copies) == 1, "wallet section content copied")
        check(not copies[0][2].get("buttons"),
              "with an ending note, buttons are not glued to the media")
        footers = [x for x in bot.text_sends
                   if x[0] == USER and x[2].get("buttons")]
        check(len(footers) == 1 and
              footers[0][1] == "برای شارژ کیف پول دکمه‌ی زیر را بزن 👇",
              "ending note sent as its own message")
        check("m:wallet" in btn_datas(footers[0][2]["buttons"]) and
              any("کیف پول" in t for t in btn_texts(footers[0][2]["buttons"])),
              "button under the note targets m:wallet (💳 شارژ کیف پول)")

        # بخش بدون متن پایان: دکمه روی آخرین پیام محتوا می‌نشیند
        s4 = m.tut_new("بخش بدون متن پایان")
        m.tut_update(s4["id"], chat=ADMIN, ids=[701], btn_cmd="m:wallet",
                     btn_label="", note="")
        fake_now[0] += 5
        bot.msg_sends, bot.files, bot.text_sends = [], [], []
        await m.tut_send_section(USER, s4["id"], force=True)
        copies = [x for x in bot.msg_sends if x[0] == USER]
        check(len(copies) == 1 and "m:wallet" in
              btn_datas(copies[0][2].get("buttons")),
              "no ending note -> button sticks to the last content message")
        check(not [x for x in bot.text_sends
                   if x[0] == USER and x[2].get("buttons")],
              "no extra footer message when the button is on the media")

        # آلبوم آخر بخش: تلگرام روی آلبوم دکمه نمی‌گذارد → پیام پایانی جدا
        m.tut_update(1, btn_cmd="m:plans", btn_label="", note="")
        m.db.tut_reset_user(USER)
        fake_now[0] += 5
        bot.msg_sends, bot.files, bot.text_sends = [], [], []
        await m.tut_send_section(USER, 1, force=True)
        footers = [x for x in bot.text_sends
                   if x[0] == USER and x[2].get("buttons")]
        check(len(footers) == 1, "album section -> separate footer message")
        check("m:plans" in btn_datas(footers[0][2]["buttons"]),
              "separate footer carries the plan button")

        # ---------- 7) یک‌بار برای هر کاربر ----------
        m.db.tut_reset_user(USER)
        fake_now[0] += 5
        bot.msg_sends, bot.text_sends, bot.files = [], [], []
        await m.tut_send_section(USER, 2, force=True)     # مهر «رفته»
        check(m.db.tut_done(USER, 2), "wallet section marked once sent")
        bot.msg_sends = []
        again = await m.tut_send_section(USER, 2)
        check(again is False and not [x for x in bot.msg_sends if x[0] == USER],
              "once=True: second run does not resend")
        again = await m.tut_send_section(USER, 2, force=True)
        check(again is True, "force=True resends (user pressed the tag)")
        m.tut_update(2, once=False)
        m.db.tut_reset_user(USER)
        fake_now[0] += 5
        bot.msg_sends = []
        await m.tut_send_section(USER, 2)
        n = len([x for x in bot.msg_sends if x[0] == USER])
        fake_now[0] += 5
        await m.tut_send_section(USER, 2)
        check(len([x for x in bot.msg_sends if x[0] == USER]) > n,
              "once=False: always sends again")
        m.tut_update(2, once=True)

        # ---------- 8) ارسال خودکار رویدادها ----------
        m.db.tut_reset_user(USER)
        section3 = m.tut_new("آموزش خرید امتیاز")
        m.tut_update(section3["id"], when="after_points", chat=ADMIN, ids=[701])
        check([s["id"] for s in m.tut_pending_sections(USER, "after_points")] ==
              [section3["id"]], "pending sections filtered by event")
        check(m.tut_schedule(USER, "after_sub") is False,
              "no section for event -> no task scheduled")
        sched = m.tut_schedule(USER, "after_points", wait=0)
        check(sched is True, "task scheduled for matching event")
        for _ in range(20):
            await asyncio.sleep(0.05)
            if m.db.tut_done(USER, section3["id"]):
                break
        check(m.db.tut_done(USER, section3["id"]),
              "scheduled task delivered the section")

        # ترتیب و فاصله‌ی بخش‌ها (رویداد بعد از اشتراک، تا فقط همین دو بخش باشد)
        m.db.tut_reset_user(USER)
        a_id = m.tut_new("اول")
        b_id = m.tut_new("دوم")
        m.tut_update(a_id["id"], when="after_sub", delay=0, chat=ADMIN, ids=[701])
        m.tut_update(b_id["id"], when="after_sub", delay=1, chat=ADMIN, ids=[701])
        check([s["id"] for s in m.tut_pending_sections(USER, "after_sub")] ==
              [a_id["id"], b_id["id"]], "sections keep admin order")
        fake_now[0] += 5
        bot.msg_sends = []
        task = asyncio.ensure_future(m.tut_fire(USER, "after_sub"))
        await asyncio.sleep(0.2)
        early = len([x for x in bot.msg_sends if x[0] == USER])
        await task
        late = len([x for x in bot.msg_sends if x[0] == USER])
        check(early == 1 and late == 2,
              "delay honoured: second section waits for its gap")
        check(m.db.tut_done(USER, a_id["id"]) and m.db.tut_done(USER, b_id["id"]),
              "both sections marked sent")

        # جابجایی ترتیب
        check(m.tut_move(b_id["id"], -1) is True and
              m.tut_sections()[-1]["id"] in (a_id["id"],), "tut_move reorders")

        # ---------- 9) تگ کاربر (tut:s:<id>) ----------
        fake_now[0] += 5
        m.db.tut_reset_user(USER)
        bot.msg_sends = []
        ev = FakeCbEv(USER, f"tut:s:{section3['id']}")
        await m.on_callback(ev)
        check(len([x for x in bot.msg_sends if x[0] == USER]) >= 1,
              "user pressing the section tag gets that section")
        check(any("ارسال" in a for a in ev.answers),
              "callback answered while sending")

        # ---------- 10) تگ‌ها پایین «📚 آموزش فعال‌سازی» ----------
        fake_now[0] += 5
        bot.text_sends = []
        await m.send_tutorial(USER)
        menus = [x for x in bot.text_sends
                 if x[0] == USER and "بخش‌های آموزش" in (x[1] or "")]
        check(len(menus) == 1, "section menu sent after the main tutorial")
        datas = btn_datas(menus[0][2].get("buttons"))
        check(f"tut:s:{section3['id']}" in datas,
              "section tag rendered as an inline button for the user")

        # بخش خاموش در منوی کاربر نمی‌آید
        m.tut_update(section3["id"], on=False)
        fake_now[0] += 5
        bot.text_sends = []
        await m.tut_send_menu(USER)
        off_menus = [x for x in bot.text_sends if x[0] == USER]
        check(all(f"tut:s:{section3['id']}" not in btn_datas(x[2].get("buttons"))
                  for x in off_menus), "disabled section hidden from user menu")

        # ---------- 10b) متن پایان یکسان در دو بخش: هر دو می‌روند ----------
        m.db.tut_reset_user(USER)
        x_id = m.tut_new("بخش الف")
        y_id = m.tut_new("بخش ب")
        same_note = "سوالی داشتی بپرس 👇"
        for sid_ in (x_id["id"], y_id["id"]):
            m.tut_update(sid_, chat=ADMIN, ids=[701], note=same_note,
                         btn_cmd="m:wallet", btn_label="")
        bot.text_sends = []
        await m.tut_send_section(USER, x_id["id"], force=True)
        await m.tut_send_section(USER, y_id["id"], force=True)
        notes = [x for x in bot.text_sends
                 if x[0] == USER and x[1] == same_note]
        check(len(notes) == 2,
              "identical ending notes of two sections both delivered (dedup key)")

        # ---------- 10c) دیتابیس بعد از ری‌استور: جدول tut_sent خودش ترمیم شود ----
        m.db.c.execute("DROP TABLE IF EXISTS tut_sent")
        m.db.c.commit()
        m.db._tut_ok = False
        check(m.db.tut_done(USER, 1) is False,
              "missing tut_sent table -> treated as not sent (no crash)")
        check(m.db.tut_mark(USER, 1) is True and m.db.tut_done(USER, 1) is True,
              "tut_sent table self-heals after restore from an old backup")

        # ---------- 11) پیش‌نمایش مدیر ----------
        m.tut_update(section3["id"], on=True)
        fake_now[0] += 5
        bot.msg_sends = []
        ev = FakeCbEv(ADMIN, f"a:sec_vw:{section3['id']}")
        await m.on_callback(ev)
        check(len([x for x in bot.msg_sends if x[0] == ADMIN]) >= 1,
              "a:sec_vw previews the section to the admin")

        time.time = real_time

    asyncio.run(main())
    print(f"BUILD {M.BUILD_VERSION}")
    for name, ok in results:
        print(f"CHECK {'PASS' if ok else 'FAIL'} - {name}")
    bad = [name for name, ok in results if not ok]
    print("SECTIONS_RESULT", "PASS" if not bad else "FAIL")

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
    print("--- بخش‌بندی آموزش: تگ‌ها + پنل مدیر + ارسال خودکار ---")
    reset()
    out = run_inner(8172)
    checks = [ln for ln in out.splitlines() if ln.startswith("CHECK")]
    print("\n".join(checks) or out[-3000:])
    print("\n".join(ln for ln in out.splitlines()
                    if ln.startswith(("BUILD", "SECTIONS_RESULT"))))
    good = "SECTIONS_RESULT PASS" in out and not any(
        c.endswith("FAIL") or " FAIL " in c for c in checks)
    print("sections:", "PASS" if good else "FAIL")
    if not good:
        print(out[-6000:])
    sys.exit(0 if good else 1)
