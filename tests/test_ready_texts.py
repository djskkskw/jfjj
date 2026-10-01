#!/usr/bin/env python3
"""سلامِ منوی اصلی با ساعت ایران + «📝 متن‌های ربات» + «📋 دستورات آماده».

  1. سرورِ هاست روی UTC است؛ سلام باید طبق Asia/Tehran انتخاب شود
     (قبلاً ظهر روی «صبح» و شب روی «ظهر» می‌ماند).
  2. مدیر از «📝 متن‌های ربات» متن‌ها و جمله‌های سلام را تنظیم و
     به پیش‌فرض برمی‌گرداند؛ {name} جای اسم مشتری است.
  3. مدیر از «📋 دستورات آماده» راهنمای مرحله‌به‌مرحله‌ی فعال‌سازی سلف را
     ثبت می‌کند (عنوان/دستور/توضیح) و مشتری آن را شماره‌دار با <code>
     می‌بیند تا با یک لمس کپی شود.
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

            # ---------- 2) پنل «📝 متن‌های ربات» ----------
            check('"a:rt"' in src, "admin menu has the 📝 متن‌های ربات button")
            check("a:rt" in btn_datas(M.admin_menu()), "admin_menu() exposes a:rt")
            ev = await cb(ADMIN, "a:rt")
            datas = btn_datas(ev.edits[-1][1])
            check(all(f"a:rt:{r[0]}" in datas for r in M.Manager.READY_TEXTS),
                  "list page has a button per text")
            check("متن‌های ربات" in ev.edits[-1][0], "list page titled متن‌های ربات")

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
            check(not any("متن‌های ربات" in (e[0] or "") for e in ev.edits),
                  "non-admin cannot open the text panel")

            # رفتن به صفحه‌ی دیگر مرحله‌ی نیمه‌کاره را لغو می‌کند
            ev = await cb(ADMIN, "a:rte:contact")
            ev = await cb(ADMIN, "m:home")
            check(ADMIN not in m.fsm, "any other button cancels rt_set")

            # ---------- 3) «📋 دستورات آماده» (a:cm*) ----------
            check('"a:cm"' in src, "admin menu has the 📋 دستورات آماده button")
            check("a:cm" in btn_datas(M.admin_menu()), "admin_menu() exposes a:cm")
            check('B("📋 دستورات آماده", "m:cmds", "success")' in src,
                  "menu and the sold message both wire m:cmds")

            # لیستِ خالی
            check(m.cmd_items() == [] and not m.has_cmds(), "cmd_items starts empty")
            check("m:cmds" not in btn_datas(M.main_menu(False, True, True,
                                                        False, False, True)),
                  "main menu hides m:cmds while nothing is registered")
            ev = await cb(ADMIN, "a:cm")
            d = btn_datas(ev.edits[-1][1])
            check("a:cmi" in d and "a:cmx" in d and "a:cme:intro" in d
                  and "a:cm:prev" in d,
                  "empty list offers add / starter / intro / preview")
            check("⚪" in ev.edits[-1][0], "empty list says nothing is registered")
            ev = await cb(ADMIN, "a:cm:prev")
            check("چیزی برای نمایش نیست" in ev.edits[-1][0],
                  "preview of an empty list is explained")

            # «⚡️ پیشنهادِ شروع» — پنج دستور از راهنمای خودِ سلف
            starter = M.Manager.CMD_STARTER
            check(len(starter) == 5, "starter suggestion has five commands")
            check({c[1] for c in starter} == {".panel", "کانال @channel",
                                              "افزودن گروه @group",
                                              "تبادل روشن", "راهنما"},
                  "starter = panel / channel / group / exchange-on / help")
            ev = await cb(ADMIN, "a:cmx")
            check(all(c[1] in ev.edits[-1][0] for c in starter),
                  "starter page lists every preset command")
            ev = await cb(ADMIN, "a:cmxy")
            check([i["cmd"] for i in m.cmd_items()] == [c[1] for c in starter],
                  "starter applied to cfg[cmd_items] in order")
            with open(M.CONFIG_FILE, encoding="utf-8") as f:
                check(len(json.load(f)["cmd_items"]) == 5,
                      "cmd_items persisted to manager_config.json")
            ev = await cb(ADMIN, "a:cm")
            check("a:cmx" not in btn_datas(ev.edits[-1][1])
                  and "a:cmi" in btn_datas(ev.edits[-1][1]),
                  "starter button only shows while the list is empty")

            # افزودنِ سه‌قدمی: عنوان → دستور → توضیح
            ev = await cb(ADMIN, "a:cmi")
            check((m.fsm.get(ADMIN) or {}).get("step") == "cm_add"
                  and m.fsm[ADMIN]["n"] == 1, "add starts at step 1")
            check("قدم ۱ از ۳" in ev.edits[-1][0], "step 1 asks for the title")
            await handler(FakeMsgEv(ADMIN, 920, "عنوان تست"))
            check(m.fsm[ADMIN]["n"] == 2 and "قدم ۲ از ۳" in bot.text_sends[-1][1],
                  "step 2 asks for the command")
            await handler(FakeMsgEv(ADMIN, 921, ".test"))
            check(m.fsm[ADMIN]["n"] == 3 and "قدم ۳ از ۳" in bot.text_sends[-1][1],
                  "step 3 asks for the note")
            await handler(FakeMsgEv(ADMIN, 922, "-"))
            check(ADMIN not in m.fsm, "step finished after the third answer")
            check(m.cmd_items()[-1] == {"title": "عنوان تست", "cmd": ".test",
                                        "note": ""},
                  "3-step add appended the command («-» skips the note)")
            check(len(m.cmd_items()) == 6, "list grew to six items")

            # توضیح هم ذخیره می‌شود
            ev = await cb(ADMIN, "a:cmi")
            await handler(FakeMsgEv(ADMIN, 923, "با توضیح"))
            await handler(FakeMsgEv(ADMIN, 924, ".note"))
            await handler(FakeMsgEv(ADMIN, 925, "یک توضیح ساده"))
            check(m.cmd_items()[-1]["note"] == "یک توضیح ساده", "note stored")

            # ویرایشِ هر فیلد
            ev = await cb(ADMIN, "a:cme:6")
            d = btn_datas(ev.edits[-1][1])
            check("a:cme:6:t" in d and "a:cme:6:c" in d and "a:cme:6:n" in d
                  and "a:cmu:6:u" in d and "a:cmu:6:d" in d and "a:cmd:6" in d,
                  "item page offers each field, both moves and delete")
            check("جایگاه" in ev.edits[-1][0], "item page shows the position")
            for code, field, val in (("t", "title", "عنوانِ عوض‌شده"),
                                     ("c", "cmd", ".edited"),
                                     ("n", "note", "توضیحِ عوض‌شده")):
                ev = await cb(ADMIN, "a:cme:6:%s" % code)
                check((m.fsm.get(ADMIN) or {}).get("step") == "cm_edit"
                      and m.fsm[ADMIN]["idx"] == 6 and m.fsm[ADMIN]["f"] == code,
                      "field %s starts cm_edit" % code)
                await handler(FakeMsgEv(ADMIN, 930, val))
                check(ADMIN not in m.fsm, "cm_edit finished for %s" % code)
                check(m.cmd_items()[6][field] == val, "%s field updated" % field)

            # جابه‌جایی با ⬆️⬇️
            ev = await cb(ADMIN, "a:cmu:6:u")
            check(m.cmd_items()[5]["cmd"] == ".edited", "⬆️ moved the item up")
            ev = await cb(ADMIN, "a:cmu:5:d")
            check(m.cmd_items()[6]["cmd"] == ".edited", "⬇️ moved it back down")
            frozen = m.cmd_items()
            ev = await cb(ADMIN, "a:cmu:0:u")
            check(m.cmd_items() == frozen, "cannot move past the top")
            ev = await cb(ADMIN, "a:cmu:99:d")
            check(m.cmd_items() == frozen, "out-of-range move is ignored")

            # حذف با تأیید
            ev = await cb(ADMIN, "a:cmd:6")
            check("a:cmd:6:y" in btn_datas(ev.edits[-1][1])
                  and m.cmd_items()[6]["cmd"] == ".edited",
                  "delete asks for confirmation first")
            ev = await cb(ADMIN, "a:cmd:6:y")
            check(len(m.cmd_items()) == 6
                  and all(i["cmd"] != ".edited" for i in m.cmd_items()),
                  "confirmed delete removed the item")

            # متنِ بالای صفحه
            ev = await cb(ADMIN, "a:cme:intro")
            check((m.fsm.get(ADMIN) or {}).get("step") == "cm_intro",
                  "intro button starts cm_intro")
            await handler(FakeMsgEv(ADMIN, 940, "اینها را در Saved Messages بفرست."))
            check(m.cfg["cmd_intro"] == "اینها را در Saved Messages بفرست.",
                  "intro saved to cfg[cmd_intro]")
            with open(M.CONFIG_FILE, encoding="utf-8") as f:
                check(json.load(f)["cmd_intro"].startswith("اینها"),
                      "cmd_intro persisted")

            # ---------- نمای مشتری ----------
            check("m:cmds" in btn_datas(M.main_menu(False, True, True, False,
                                                    False, True, has_cmds=True)),
                  "main menu shows m:cmds once commands exist")
            pages = m.cmds_pages()
            check(len(pages) == 1, "six short commands fit in one message")
            check(all(("<code>%s</code>" % M.Manager._esc(i["cmd"])) in pages[0]
                      for i in m.cmd_items()),
                  "every command is inside <code> for one-tap copy")
            check(all(("%d)" % n) in pages[0] for n in range(1, 7)),
                  "steps are numbered")
            check("اینها را در Saved Messages بفرست." in pages[0],
                  "intro text sits at the top of the customer page")
            bot.text_sends.clear()
            ev = await cb(USER, "m:cmds")
            check(len(bot.text_sends) == 1 and bot.text_sends[0][0] == USER,
                  "m:cmds sends the guide to the customer")
            check(btn_datas(bot.text_sends[-1][2].get("buttons")) == ["m:home"],
                  "customer page carries a back button")

            # متنِ بلند به چند پیام شکسته می‌شود (سقف ~۳۸۰۰ حرف)
            keep = m.cfg.get("cmd_items")
            m.cmd_save([{"title": "مرحله %d" % i, "cmd": ".cmd%d" % i,
                         "note": "ت" * 300} for i in range(1, 31)])
            pages = m.cmds_pages()
            check(len(pages) > 1, "a long list is split into several messages")
            check(all(len(p) <= M.Manager.CM_MSG_LIMIT for p in pages),
                  "no page exceeds the %d-char limit" % M.Manager.CM_MSG_LIMIT)
            check("".join(pages).count("<code>") == 30,
                  "all 30 commands survive the split")
            bot.text_sends.clear()
            ev = await cb(USER, "m:cmds")
            check(len(bot.text_sends) == len(pages), "each page is its own message")
            check(not btn_datas(bot.text_sends[0][2].get("buttons")),
                  "only the last page carries the back button")
            m.cmd_save(keep)

            # ورودیِ HTML امن نمایش داده می‌شود
            m.cmd_save([{"title": "<b>x", "cmd": "<script>", "note": "a & b"}])
            pg = m.cmds_pages()[0]
            check("&lt;b&gt;x" in pg and "&lt;script&gt;" in pg and "a &amp; b" in pg,
                  "customer view is HTML-escaped")
            check("<script>" not in pg, "no raw tag reaches Telegram")
            ev = await cb(ADMIN, "a:cm")
            check("&lt;script&gt;" in ev.edits[-1][0], "admin list is escaped too")

            # غیرمدیر راهی به پنل ندارد
            ev = await cb(USER, "a:cm")
            check(not ev.edits, "non-admin cannot open the commands panel")

            # رفتن به صفحه‌ی دیگر مرحله‌ی نیمه‌کاره را لغو می‌کند
            for start in ("a:cmi", "a:cme:intro", "a:cme:0:t"):
                ev = await cb(ADMIN, start)
                check(ADMIN in m.fsm, "%s leaves a pending step" % start)
                ev = await cb(ADMIN, "m:home")
                check(ADMIN not in m.fsm, "any other button cancels %s" % start)

            # داده‌ی خراب در cfg نباید صفحه را بیندازد
            m.cfg.d["cmd_items"] = ["x", None, {"title": "", "cmd": ""},
                                    {"title": "سالم", "cmd": ".ok"}]
            check([i["cmd"] for i in m.cmd_items()] == [".ok"],
                  "broken cmd_items entries are dropped, valid one kept")
            m.cmd_save(keep)

            # ---------- 4) fallback منطقه‌زمانی ----------
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
    print("--- سلام با ساعت ایران + متن‌های ربات + دستورات آماده ---")
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
