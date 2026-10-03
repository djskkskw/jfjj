#!/usr/bin/env python3
"""🗂 «توضیحات» — فهرستِ تپ‌کردنیِ همه‌ی توضیحات.

قفل کردن این رفتار:

  1. منوی مشتری یک دکمه‌ی جدا دارد: «🗂 توضیحات» (m:hub) — کنارِ
     «📚 آموزش فعال‌سازی» که دست‌نخورده می‌ماند.
  2. فهرست، همه‌ی بخش‌های فعالِ «🧩 بخش‌های آموزش» را خودکار نشان می‌دهد
     (هیچ کارِ دوباره‌ای لازم نیست) + آیتمِ «📖 آموزش فعال‌سازی (کامل)».
  3. هر بخش در فهرست یک دکمه است: تپ = فقط همان آموزش می‌رود + دکمه‌ی
     «🗂 همه‌ی آموزش‌ها» برای برگشت به فهرست (حتی اگر once=True باشد).
  4. صفحه‌بندی: با hub_page_size (پیش‌فرض ۸) ورق می‌خورد؛ «⬅️ قبلی/➡️ بعدی».
  5. «📤 ارسال همه‌ی آموزش‌ها» همه‌ی آموزش‌های فهرست را پشت‌سرهم می‌فرستد.
  6. پنل مدیر: صفحه‌ی «🗂 توضیحات» — روشن/خاموش دکمه، متن بالای صفحه،
     تعداد در هر صفحه، و ✅/⬜ کردنِ هر آموزش در فهرست (in_hub).
  7. بخشِ خاموش یا in_hub=False در فهرست نمی‌آید؛ خاموش‌کردنِ hub_on دکمه را
     از منوی مشتری برمی‌دارد.
  8. توضیحاتِ پیش‌فرضِ قابلیت‌های ربات (HUB_DEFAULTS) تا وقتی مدیر متنِ خودش را
     نگذاشته در فهرست می‌آیند؛ با «📥 تبدیل به بخش» به بخشِ قابل‌ویرایش
     (preset=hub:<key>) تبدیل می‌شوند و دیگر تکراری نشان داده نمی‌شوند.

روش اجرا مثل بقیه‌ی تست‌ها: سورس واقعی manager_82 با telethon قلابی و
دیتابیس واقعی (فایلی) ران می‌شود.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_tut_hub_run")
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
            self.msg_sends = []
            self.text_sends = []
            self.files = []
            self.msgs = {}
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
        check('"hub_on": True' in src, "DEFAULTS has hub_on")
        check('"hub_intro": ""' in src, "DEFAULTS has hub_intro")
        check('"hub_page_size": 8' in src, "DEFAULTS has hub_page_size")
        check('B("🗂 توضیحات", "m:hub", "success")' in src,
              "user main menu has m:hub button")
        check('B("📚 آموزش فعال‌سازی", "m:tut", "success")' in src,
              "legacy 📚 آموزش فعال‌سازی button kept")
        check('B("🗂 توضیحات (فهرست تپ‌کردنی)", "a:hub", "success")' in src,
              "admin menu has a:hub button")
        check('"in_hub": bool(s.get("in_hub", True))' in src,
              "tut_norm carries in_hub (default True)")
        check('if data == "m:hub":' in src, "route m:hub present")
        check('if data.startswith("hub:p:"):' in src, "route hub:p:<page> present")
        check('if data == "hub:all":' in src, "route hub:all present")
        check('if data.startswith("hub:s:"):' in src,
              "route hub:s:<id> (tap an item) present")
        check('if data == "hub:list":' in src, "route hub:list present")
        check('stp == "hub_intro"' in src, "hub_intro text step handled")
        check('"hub_defaults": True' in src, "DEFAULTS has hub_defaults")
        check("HUB_DEFAULTS = (" in src, "HUB_DEFAULTS table present")
        check('if data.startswith("hub:d:"):' in src,
              "route hub:d:<key> (default topic) present")
        check('if k == "hub_mk":' in src, "admin action a:hub_mk present")
        check('if k == "hub_def":' in src, "admin action a:hub_def present")
        check('"hub_intro"' in src.split('"cm_add", "cm_edit", "cm_intro"')[1][:80],
              "hub_intro cleared like cm_intro on other buttons")

        # ---------- 1) منوی مدیر ----------
        aflat = [b for row in M.admin_menu() for b in row]
        check(any(b[1][1] == b"a:hub" for b in aflat),
              "admin_menu renders a:hub")

        # ---------- منوی مشتری ----------
        check("m:hub" in btn_datas(M.main_menu(has_hub=True)),
              "main_menu shows 🗂 توضیحات when has_hub")
        check("m:hub" not in btn_datas(M.main_menu(has_hub=False)),
              "main_menu hides 🗂 آموزش‌ها when has_hub=False")

        # ---------- Manager واقعی + ربات قلابی ----------
        real_time = time.time
        fake_now = [real_time()]
        time.time = lambda: fake_now[0]

        m = M.Manager()
        bot = FakeBot()
        m.bot = bot
        m.cfg["admin_ids"] = [ADMIN]

        # ---------- 2) ساخت بخش‌ها ----------
        sec_a = m.tut_new("آموزش کامل پنل جفج")
        m.tut_update(sec_a["id"], emoji="🎬", chat=ADMIN, ids=[601])
        sec_b = m.tut_new("آموزش شارژ کیف پول")
        m.tut_update(sec_b["id"], emoji="💳", chat=ADMIN, ids=[602],
                     btn_cmd="m:wallet", btn_label="")
        sec_c = m.tut_new("آموزش خرید امتیاز")
        m.tut_update(sec_c["id"], emoji="🎯", chat=ADMIN, ids=[602], on=False)
        bot.msgs[ADMIN] = {601: FakeMsg(601, "محتوای آموزش اصلی"),
                           602: FakeMsg(602, "محتوای بقیه")}

        check([s["id"] for s in m.hub_sections()] == [sec_a["id"], sec_b["id"]],
              "hub auto-lists enabled sections (no re-work for the admin)")
        check(all(s.get("in_hub") is True for s in m.tut_sections()),
              "sections default to in_hub=True")

        # ---------- 3) صفحه‌ی فهرست ----------
        txt, kb = m.hub_view(0)
        datas = btn_datas(kb)
        check("m:tut" in datas, "hub page 1 offers the full main tutorial")
        check(f"hub:s:{sec_a['id']}" in datas and f"hub:s:{sec_b['id']}" in datas,
              "each section is a tappable item in the hub")
        check(f"hub:s:{sec_c['id']}" not in datas,
              "disabled section is not listed")
        check("hub:all" in datas, "📤 ارسال همه button present")
        check("m:home" in datas, "back button present")

        # ---------- 4) تپِ یک آموزش ----------
        m.db.tut_reset_user(USER)
        fake_now[0] += 5
        bot.msg_sends, bot.text_sends = [], []
        ev = FakeCbEv(USER, f"hub:s:{sec_a['id']}")
        await m.on_callback(ev)
        copies = [x for x in bot.msg_sends if x[0] == USER]
        check(len(copies) == 1, "tapping a hub item sends just that tutorial")
        check("hub:list" in btn_datas(copies[0][2].get("buttons")),
              "sent tutorial carries 🗂 همه‌ی آموزش‌ها back button")
        check(any("ارسال" in a for a in ev.answers),
              "callback answered while sending")
        # once=True هم با تپ دوباره می‌رود
        fake_now[0] += 5
        bot.msg_sends = []
        ev = FakeCbEv(USER, f"hub:s:{sec_a['id']}")
        await m.on_callback(ev)
        check(len([x for x in bot.msg_sends if x[0] == USER]) == 1,
              "tapping again re-sends (force) even with once=True")

        # بخش متعلق به خودش: دکمه‌ی پایان + برگشت به فهرست، هر دو
        m.tut_update(sec_b["id"], note="برای شارژ دکمه را بزن 👇")
        fake_now[0] += 5
        bot.msg_sends, bot.text_sends = [], []
        ev = FakeCbEv(USER, f"hub:s:{sec_b['id']}")
        await m.on_callback(ev)
        foots = [x for x in bot.text_sends
                 if x[0] == USER and x[2].get("buttons")]
        check(len(foots) == 1, "section with note sends its own footer message")
        fdatas = btn_datas(foots[0][2]["buttons"])
        check("m:wallet" in fdatas and "hub:list" in fdatas,
              "footer carries both the section button and the hub back button")

        # ---------- 5) بازگشت به فهرست (hub:list) ----------
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "hub:list")
        await m.on_callback(ev)
        hubs = [x for x in bot.text_sends if x[0] == USER
                and f"hub:s:{sec_a['id']}" in btn_datas(x[2].get("buttons"))]
        check(len(hubs) == 1, "hub:list opens the list again")

        # ---------- 6) ارسال همه ----------
        m.db.tut_reset_user(USER)
        fake_now[0] += 5
        bot.msg_sends, bot.text_sends = [], []
        ev = FakeCbEv(USER, "hub:all")
        await m.on_callback(ev)
        sent = [x for x in bot.msg_sends if x[0] == USER]
        check(len(sent) == 2, "hub:all sends every listed tutorial")
        bulk_datas = [btn_datas(x[2].get("buttons")) for x in sent]
        bulk_datas += [btn_datas(x[2].get("buttons")) for x in bot.text_sends
                       if x[0] == USER and x[2].get("buttons")]
        check(sum(1 for d in bulk_datas if "hub:list" in d) == 2,
              "each bulk tutorial keeps the back-to-list button")

        # ---------- 7) صفحه‌بندی ----------
        m.cfg["hub_page_size"] = 4
        ids = []
        for i in range(9):
            s = m.tut_new(f"آموزش شماره {i + 1}")
            m.tut_update(s["id"], chat=ADMIN, ids=[602])
            ids.append(s["id"])
        m.tut_update(sec_c["id"], on=True)      # ۱۲ بخش فعال
        total = len(m.hub_sections())
        check(total == 12, "12 enabled sections in the hub")
        check(m.hub_pages() == 3, "12 sections / 4 per page = 3 pages")
        p0 = btn_datas(m.hub_view(0)[1])
        p1 = btn_datas(m.hub_view(1)[1])
        p2 = btn_datas(m.hub_view(2)[1])
        s0 = [d for d in p0 if d.startswith("hub:s:")]
        s1 = [d for d in p1 if d.startswith("hub:s:")]
        s2 = [d for d in p2 if d.startswith("hub:s:")]
        check(len(s0) == 4 and len(s1) == 4 and len(s2) == 4,
              "each page shows hub_page_size items")
        check(not (set(s0) & set(s1)) and not (set(s1) & set(s2)),
              "pages do not repeat items")
        check("hub:p:1" in p0 and "hub:p:0" not in p0,
              "page 1 has next, no previous")
        check("hub:p:1" in p2 and "hub:p:2" not in p2,
              "last page has previous, no next")
        check("m:tut" in p0 and "m:tut" not in p1,
              "main tutorial only on the first page")
        check("صفحه‌ی 2 از 3" in m.hub_view(1)[0], "page counter printed")

        # ورق‌زدن، همان پیام را ویرایش می‌کند (چت شلوغ نمی‌شود)
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "hub:p:1")
        await m.on_callback(ev)
        check(ev.edits and "صفحه‌ی 2 از 3" in ev.edits[-1][0],
              "hub:p:<page> edits the same message")
        check(not [x for x in bot.text_sends if x[0] == USER],
              "paging does not spam a new message")

        # صفحه‌ی نامعتبر → نزدیک‌ترین صفحه (بدون خطا)
        check("صفحه‌ی 3 از 3" in m.hub_view(99)[0],
              "out-of-range page clamps to the last page")

        # ---------- 8) پنل مدیر: صفحه‌ی 🗂 توضیحات ----------
        ev = FakeCbEv(ADMIN, "a:hub")
        await m.on_callback(ev)
        txt, kb = ev.edits[-1]
        check("توضیحات" in txt and "a:hub_t" in " ".join(btn_datas(kb)),
              "a:hub opens the hub admin page")
        check("a:hub_on" in btn_datas(kb) and "a:hub_i" in btn_datas(kb),
              "hub page has on/off + intro controls")

        # ✅/⬜ کردنِ یک آموزش
        ev = FakeCbEv(ADMIN, f"a:hub_t:{sec_b['id']}")
        await m.on_callback(ev)
        check(m.tut_find(sec_b["id"])["in_hub"] is False,
              "a:hub_t hides a section from the list")
        check(f"hub:s:{sec_b['id']}" not in btn_datas(m.hub_view(0)[1]),
              "hidden section disappears from the customer list")
        fake_now[0] += 5
        ev = FakeCbEv(ADMIN, f"a:hub_t:{sec_b['id']}")
        await m.on_callback(ev)
        check(m.tut_find(sec_b["id"])["in_hub"] is True, "a:hub_t shows it again")
        with open(M.CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        check(saved["tut_sections"][1].get("in_hub") is True,
              "in_hub persisted to manager_config.json")

        # از صفحه‌ی خودِ بخش هم می‌شود
        ev = FakeCbEv(ADMIN, f"a:sec_hub:{sec_b['id']}")
        await m.on_callback(ev)
        check(m.tut_find(sec_b["id"])["in_hub"] is False,
              "a:sec_hub toggles from the section page too")
        fake_now[0] += 5
        ev = FakeCbEv(ADMIN, f"a:sec_hub:{sec_b['id']}")
        await m.on_callback(ev)
        check(m.tut_find(sec_b["id"])["in_hub"] is True, "and back again")

        # تعداد در هر صفحه
        m.cfg["hub_page_size"] = 4
        ev = FakeCbEv(ADMIN, "a:hub_pg")
        await m.on_callback(ev)
        check(m.cfg["hub_page_size"] == 6, "a:hub_pg cycles the page size")
        m.cfg["hub_page_size"] = 4

        # خاموش‌کردن دکمه‌ی مشتری
        ev = FakeCbEv(ADMIN, "a:hub_on")
        await m.on_callback(ev)
        check(m.hub_on() is False, "a:hub_on turns the menu button off")
        check("m:hub" not in btn_datas(M.main_menu(has_hub=m.hub_on())),
              "turning it off removes 🗂 from the customer menu")
        fake_now[0] += 5
        bot.text_sends = []
        await m.tut_send_menu(USER)
        check(not any("m:hub" in btn_datas(x[2].get("buttons"))
                      for x in bot.text_sends if x[0] == USER),
              "turning it off also hides the link in the tag menu")
        fake_now[0] += 5
        ev = FakeCbEv(ADMIN, "a:hub_on")
        await m.on_callback(ev)
        check(m.hub_on() is True, "a:hub_on turns it back on")

        # پیش‌نمایش + ارسال همه از پنل
        fake_now[0] += 5
        bot.text_sends, bot.msg_sends = [], []
        ev = FakeCbEv(ADMIN, "a:hub_p")
        await m.on_callback(ev)
        check(any(x[0] == ADMIN for x in bot.text_sends),
              "a:hub_p previews the hub for the admin")
        fake_now[0] += 5
        bot.msg_sends, bot.text_sends = [], []
        ev = FakeCbEv(ADMIN, "a:hub_all")
        await m.on_callback(ev)
        check(len([x for x in bot.msg_sends if x[0] == ADMIN]) == len(m.hub_sections()),
              "a:hub_all sends every listed tutorial to the admin")

        # ---------- 9) متن بالای فهرست ----------
        ev = FakeCbEv(ADMIN, "a:hub_i")
        await m.on_callback(ev)
        check((m.fsm.get(ADMIN) or {}).get("step") == "hub_intro",
              "a:hub_i starts the intro-text step")

        # هندلر واقعیِ پیام‌ها را از سورس بیرون می‌کشیم (مثل تست بخش‌ها)
        src = open("manager_82.py", encoding="utf-8").read()
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

        fake_now[0] += 5
        await handler(FakeMsgEv(ADMIN, 901, "این‌جا هر آموزش را بزن تا بیاید 👇"))
        check(m.cfg["hub_intro"] == "این‌جا هر آموزش را بزن تا بیاید 👇",
              "admin text saved as hub intro")
        check("این‌جا هر آموزش را بزن تا بیاید" in m.hub_view(0)[0],
              "saved intro shows at the top of the list")
        m.fsm[ADMIN] = {"step": "hub_intro"}
        fake_now[0] += 5
        await handler(FakeMsgEv(ADMIN, 902, "-"))
        check(m.cfg["hub_intro"] == "", "dash restores the default intro")

        # دکمه‌ی دیگر = لغو
        m.fsm[ADMIN] = {"step": "hub_intro"}
        fake_now[0] += 5
        await m.on_callback(FakeCbEv(ADMIN, "m:home"))
        check(ADMIN not in m.fsm, "any other button cancels hub_intro")

        # ---------- 10) منوی تگ‌ها دکمه‌ی فهرست را دارد ----------
        fake_now[0] += 5
        bot.text_sends = []
        await m.tut_send_menu(USER)
        menus = [x for x in bot.text_sends if x[0] == USER]
        check(menus and "m:hub" in btn_datas(menus[-1][2].get("buttons")),
              "section-tag menu links to the 🗂 list")

        # ---------- 11) توضیحاتِ پیش‌فرضِ قابلیت‌ها ----------
        # تا وقتی بخشی در فهرست نیست، اینها جای خالی را پر می‌کنند
        keys = [d[0] for d in m.HUB_DEFAULTS]
        bodies = {k: m.hub_default_text(k) for k in keys}
        check(all(b.strip() for b in bodies.values()),
              "every default topic has a real description text")
        check(all(len(b) > 120 for b in bodies.values()),
              "default descriptions are substantial (not one-liners)")
        check(all("{" not in b and "}" not in b and "None" not in b
                  and "<<" not in b for b in bodies.values()),
              "no leftover placeholders / raw braces in default texts")
        want_kw = {"start": "سلف", "trial": "رایگان", "exchange": "جوین",
                   "wallet": "کیف پول", "points": "امتیاز", "sub": "اشتراک",
                   "ref": "دعوت", "security": "کد", "panel": ".panel",
                   "svc": "خاموش", "support": "تیکت"}
        check(all(want_kw[k] in bodies[k] for k in keys),
              "each default text describes its own capability")

        # خالی‌کردنِ فهرست از بخش‌ها → پیش‌فرض‌ها می‌آیند
        for sec in m.tut_sections():
            m.tut_update(sec["id"], in_hub=False)
        check(not m.hub_sections(), "list emptied of admin sections (test setup)")
        defaults = m.hub_default_items()
        check(len(defaults) == len(m.HUB_DEFAULTS),
              "all built-in feature topics fill the empty list")
        txt, kb = m.hub_view(0)
        datas = btn_datas(kb)
        check("hub:d:start" in datas and "hub:d:trial" in datas,
              "default topics are tappable items in the list")

        # تپِ یک توضیحِ پیش‌فرض: متن + دکمه‌ی همان کار + بازگشت به فهرست
        fake_now[0] += 5
        bot.text_sends, bot.msg_sends = [], []
        ev = FakeCbEv(USER, "hub:d:trial")
        await m.on_callback(ev)
        sent = [x for x in bot.text_sends if x[0] == USER]
        check(len(sent) == 1, "tapping a default topic sends its description")
        d_datas = btn_datas(sent[0][2].get("buttons"))
        check("m:trial" in d_datas and "hub:list" in d_datas,
              "default topic carries its own action button + back to list")

        # توضیحی که دکمه‌ی کار ندارد (تبادل/امنیت) هم می‌رود
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "hub:d:exchange")
        await m.on_callback(ev)
        sent = [x for x in bot.text_sends if x[0] == USER]
        check(len(sent) == 1 and "hub:list" in
              btn_datas(sent[0][2].get("buttons")),
              "topics without their own button still work")

        # کلیدِ ناشناخته → بی‌صدا و بدون خطا
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "hub:d:nope")
        await m.on_callback(ev)
        check(not [x for x in bot.text_sends if x[0] == USER],
              "unknown default key sends nothing")

        # «📤 ارسال همه» با فهرستِ پیش‌فرض‌ها
        fake_now[0] += 5
        bot.text_sends, bot.msg_sends = [], []
        ev = FakeCbEv(USER, "hub:all")
        await m.on_callback(ev)
        got = len([x for x in bot.text_sends if x[0] == USER]) + \
            len([x for x in bot.msg_sends if x[0] == USER])
        check(got == len(m.hub_default_items()),
              "hub:all sends the default topics too")

        # خاموش‌کردنِ پیش‌فرض‌ها از پنل
        ev = FakeCbEv(ADMIN, "a:hub_def")
        await m.on_callback(ev)
        check(m.hub_defaults_on() is False, "a:hub_def turns defaults off")
        check(not m.hub_default_items(), "defaults gone from the list")
        check("hub:d:start" not in btn_datas(m.hub_view(0)[1]),
              "no default topic button while off")
        with open(M.CONFIG_FILE, encoding="utf-8") as f:
            check(json.load(f)["hub_defaults"] is False,
                  "hub_defaults persisted")
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(USER, "hub:d:start")
        await m.on_callback(ev)
        check(not [x for x in bot.text_sends if x[0] == USER],
              "tapping a disabled default sends nothing")
        fake_now[0] += 5
        ev = FakeCbEv(ADMIN, "a:hub_def")
        await m.on_callback(ev)
        check(m.hub_defaults_on() is True, "a:hub_def turns them back on")

        # یکی از بخش‌ها را برمی‌گردانیم → پیش‌فرض‌ها کنار می‌روند
        m.tut_update(m.tut_sections()[0]["id"], in_hub=True)
        check(not m.hub_default_items(),
              "as soon as one section is listed, defaults step aside")

        # ---------- 12) تبدیلِ پیش‌فرض‌ها به بخشِ قابل‌ویرایش ----------
        for sec in m.tut_sections():
            m.tut_update(sec["id"], in_hub=False)
        n_before = len(m.tut_sections())
        n_defs = len(m.hub_defaults_all())
        ev = FakeCbEv(ADMIN, "a:hub_mk")
        await m.on_callback(ev)
        secs = m.tut_sections()
        check(len(secs) == n_before + n_defs,
              "a:hub_mk turns every default into an editable section")
        made = [s for s in secs if str(s.get("preset") or "").startswith("hub:")]
        check(len(made) == n_defs, "materialised sections remember their key")
        check(all(s["when"] == "manual" for s in made),
              "materialised sections only send from the list (no auto-spam)")
        start_sec = next((s for s in made if s["preset"] == "hub:start"), None)
        check(start_sec is not None and start_sec["btn_cmd"] == "s:setup",
              "materialised section keeps its action button")
        check(m.tut_body_text(start_sec) == m.hub_default_text("start"),
              "materialised section shows the default text until the admin edits it")
        check(not m.hub_defaults_all(),
              "materialised defaults are not offered again")
        all_datas = []
        for pg in range(m.hub_pages()):
            all_datas += btn_datas(m.hub_view(pg)[1])
        check(f"hub:s:{start_sec['id']}" in all_datas,
              "materialised section is now a list item")
        check(not [d for d in all_datas if d.startswith("hub:d:")],
              "no duplicate default buttons next to their sections")
        # ویرایشِ متن توسطِ مدیر روی همان بخش می‌نشیند
        m.tut_update(start_sec["id"], text="📌 متنِ خودم برای راه‌اندازی")
        check(m.tut_body_text(m.tut_find(start_sec["id"])) ==
              "📌 متنِ خودم برای راه‌اندازی",
              "admin text replaces the default description")
        # اجرای دوباره‌ی a:hub_mk چیزی تکراری نمی‌سازد
        n_now = len(m.tut_sections())
        fake_now[0] += 5
        ev = FakeCbEv(ADMIN, "a:hub_mk")
        await m.on_callback(ev)
        check(len(m.tut_sections()) == n_now,
              "running a:hub_mk twice does not duplicate sections")

        time.time = real_time

    asyncio.run(main())
    print(f"BUILD {M.BUILD_VERSION}")
    for name, ok in results:
        print(f"CHECK {'PASS' if ok else 'FAIL'} - {name}")
    bad = [name for name, ok in results if not ok]
    print("HUB_RESULT", "PASS" if not bad else "FAIL")

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
    print("--- 🗂 توضیحات: فهرستِ تپ‌کردنیِ همه‌ی توضیحات ---")
    reset()
    out = run_inner(8173)
    checks = [ln for ln in out.splitlines() if ln.startswith("CHECK")]
    print("\n".join(checks) or out[-3000:])
    print("\n".join(ln for ln in out.splitlines()
                    if ln.startswith(("BUILD", "HUB_RESULT"))))
    good = "HUB_RESULT PASS" in out and not any(
        c.endswith("FAIL") or " FAIL " in c for c in checks)
    print("hub:", "PASS" if good else "FAIL")
    if not good:
        print(out[-6000:])
    sys.exit(0 if good else 1)
