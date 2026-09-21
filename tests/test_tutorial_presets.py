#!/usr/bin/env python3
"""چهار متنِ آماده‌ی آموزش در پنل: کیف پول / خرید امتیاز / اشتراک ماهانه / بعد از فعال‌سازی.

  1. پنل «🧩 بخش‌های آموزش» دکمه‌ی «📝 متن‌های آماده» دارد؛ هر کدام با یک
     دکمه به یک بخشِ کامل تبدیل می‌شود (متن + زمان ارسال + دکمه‌ی پایان).
  2. متن‌ها با اعدادِ تنظیمات (حداقل شارژ، امتیاز هر ساعت…) پر می‌شوند و تا
     وقتی مدیر دست نزده، همیشه به‌روز می‌مانند.
  3. هر بخش می‌تواند به‌جای/کنارِ پیام‌های ثبت‌شده، یک «📝 متن بخش» داشته
     باشد؛ ترتیب تحویل: پیام‌ها → متن → متن پایان + دکمه.
  4. «♻️ متن آماده» متنِ دست‌کاری‌شده را به متن آماده برمی‌گرداند.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_tut_presets_run")
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
        check('"text": str(s.get("text") or "")[:3500]' in src,
              "tut_norm keeps a per-section text field")
        check('"preset": str(s.get("preset") or "")[:20]' in src,
              "tut_norm keeps the preset key")
        check('"a:sec_tpl"' in src, "panel has the presets page (a:sec_tpl)")
        check('"sec_text"' in src and 'stp == "sec_text"' in src,
              "admin can type a section text (sec_text step)")

        real_time = time.time
        fake_now = [real_time()]
        time.time = lambda: fake_now[0]

        m = M.Manager()
        bot = FakeBot()
        m.bot = bot
        m.cfg["admin_ids"] = [ADMIN]

        # ---------- 1) چهار متن آماده: ساخت با یک دکمه ----------
        keys = [k for k, _ in M.Manager.TUT_PRESETS]
        check(keys == ["wallet", "points", "sub", "after_run"],
              "four presets: wallet / points / sub / after_run")
        for k in keys:
            t = m.tut_preset_text(k)
            check(len(t) > 200 and "<b>" in t, f"preset text {k} is real HTML text")
        check(M.money(m.cfg["min_topup"]) in m.tut_preset_text("wallet"),
              "wallet text filled with min_topup from settings")
        check("Saved Messages" in m.tut_preset_text("after_run") and
              ".panel" in m.tut_preset_text("after_run"),
              "after_run text explains .panel in Saved Messages")

        ev = FakeCbEv(ADMIN, "a:secs")
        await m.on_callback(ev)
        check("a:sec_tpl" in btn_datas(ev.edits[-1][1]),
              "sections page offers the presets button while presets are missing")

        ev = FakeCbEv(ADMIN, "a:sec_tpl")
        await m.on_callback(ev)
        datas = btn_datas(ev.edits[-1][1])
        check("a:sec_tpl_one:wallet" in datas and "a:sec_tpl_one:points" in datas
              and "a:sec_tpl_one:sub" in datas
              and "a:sec_tpl_one:after_run" in datas and "a:sec_tpl_all" in datas,
              "presets page lists all four + build-all")

        ev = FakeCbEv(ADMIN, "a:sec_tpl_one:wallet")
        await m.on_callback(ev)
        w = m.tut_find_preset("wallet")
        check(w is not None and w["when"] == "after_wallet" and w["btn_cmd"] == "w:topup"
              and w["on"] and w["once"],
              "wallet preset -> section: after_wallet + 💳 شارژ کیف پول button")
        check("ساخته شد" in ev.edits[-1][0], "creation confirmed in panel")

        fake_now[0] += 5
        ev = FakeCbEv(ADMIN, "a:sec_tpl_one:wallet")
        await m.on_callback(ev)
        check(len([s for s in m.tut_sections() if s["preset"] == "wallet"]) == 1
              and "قبلاً" in ev.edits[-1][0],
              "pressing the same preset twice does not duplicate")

        ev = FakeCbEv(ADMIN, "a:sec_tpl_all")
        await m.on_callback(ev)
        p = m.tut_find_preset("points")
        r = m.tut_find_preset("after_run")
        sb = m.tut_find_preset("sub")
        check(p and p["when"] == "after_points" and p["btn_cmd"] == "m:packs",
              "points preset: after_points + 🎯 خرید امتیاز button")
        check(sb and sb["when"] == "after_sub" and sb["btn_cmd"] == "m:plans",
              "sub preset: after_sub + 💎 اشتراک ماهانه button")
        check(r and r["when"] == "after_run" and r["btn_cmd"] == "m:svc",
              "after_run preset: after_run + ⚙️ سرویس من button")
        check(len(m.tut_sections()) == 4, "build-all made exactly the missing three")

        with open(M.CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        check([s["preset"] for s in saved["tut_sections"]] == keys,
              "presets persisted to manager_config.json")

        fake_now[0] += 5
        ev = FakeCbEv(ADMIN, "a:secs")
        await m.on_callback(ev)
        check("a:sec_tpl" not in btn_datas(ev.edits[-1][1]),
              "presets button hidden once all four exist")
        check("📝 متن" in ev.edits[-1][0], "sections list shows text-based content")

        # ---------- 2) تحویل به کاربر: متن + متن پایان + دکمه ----------
        fake_now[0] += 5
        bot.text_sends = []
        ok = await m.tut_send_section(USER, w["id"])
        sends = [x for x in bot.text_sends if x[0] == USER]
        check(ok and len(sends) == 2, "wallet section = body text + footer")
        check("آموزش کیف پول" in sends[0][1] and not sends[0][2].get("buttons"),
              "body first, without buttons (footer note carries the button)")
        check("w:topup" in btn_datas(sends[1][2].get("buttons")),
              "footer button goes straight to wallet top-up")
        check(m.db.tut_done(USER, w["id"]), "delivery marked once")

        # ---------- 3) ارسال خودکار بعد از شارژ کیف پول ----------
        m.db.tut_reset_user(USER)
        check([s["id"] for s in m.tut_pending_sections(USER, "after_wallet")] == [w["id"]],
              "after_wallet event fires the wallet preset")
        check([s["id"] for s in m.tut_pending_sections(USER, "after_points")] == [p["id"]],
              "after_points event fires the points preset")
        check([s["id"] for s in m.tut_pending_sections(USER, "after_sub")] == [sb["id"]],
              "after_sub event fires the subscription preset")
        check([s["id"] for s in m.tut_pending_sections(USER, "after_run")] == [r["id"]],
              "after_run event fires the after-activation preset")
        fake_now[0] += 5
        bot.text_sends = []
        check(m.tut_schedule(USER, "after_points", wait=0) is True, "scheduled")
        for _ in range(20):
            await asyncio.sleep(0.05)
            if m.db.tut_done(USER, p["id"]):
                break
        check(m.db.tut_done(USER, p["id"]), "points text delivered automatically")

        # ---------- 4) متن به‌روز با تنظیمات؛ ویرایش دستی؛ برگشت ----------
        m.cfg["cost_per_hour"] = 3
        m.cfg.save()
        check("۳" in m.tut_body_text(m.tut_find(p["id"])),
              "untouched preset text follows the current settings")

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

        ev = FakeCbEv(ADMIN, f"a:sec_txt:{p['id']}")
        await m.on_callback(ev)
        check((m.fsm.get(ADMIN) or {}).get("step") == "sec_text",
              "a:sec_txt starts text entry")
        fake_now[0] += 5
        await handler(FakeMsgEv(ADMIN, 901, "متن دلخواه مدیر برای امتیاز"))
        check(m.tut_find(p["id"])["text"] == "متن دلخواه مدیر برای امتیاز",
              "typed text saved into the section")
        check(m.tut_body_text(m.tut_find(p["id"])) == "متن دلخواه مدیر برای امتیاز",
              "custom text overrides the preset")
        ev = FakeCbEv(ADMIN, f"a:sec:{p['id']}")
        await m.on_callback(ev)
        check(f"a:sec_tpl_rst:{p['id']}" in btn_datas(ev.edits[-1][1]),
              "preset section offers 'back to ready text'")
        ev = FakeCbEv(ADMIN, f"a:sec_tpl_rst:{p['id']}")
        await m.on_callback(ev)
        check(m.tut_find(p["id"])["text"] == "" and
              "آموزش خرید امتیاز" in m.tut_body_text(m.tut_find(p["id"])),
              "reset restores the ready text")

        # حذف متن
        m.fsm[ADMIN] = {"step": "sec_text", "sec_id": p["id"]}
        fake_now[0] += 5
        await handler(FakeMsgEv(ADMIN, 902, "خاموش"))
        check(m.tut_find(p["id"])["text"] == "", "خاموش clears the custom text")

        # ---------- 5) بخش معمولی با متن + پیام ثبت‌شده: ترتیب ----------
        s5 = m.tut_new("ترکیبی")
        bot.msgs[ADMIN] = {701: FakeMsg(701, "ویدیوی آموزش", media=("doc", "v"))}
        m.tut_update(s5["id"], chat=ADMIN, ids=[701], text="توضیح متنی",
                     btn_cmd="m:wallet", btn_label="", note="")
        fake_now[0] += 5
        bot.text_sends, bot.msg_sends = [], []
        await m.tut_send_section(USER, s5["id"], force=True)
        copies = [x for x in bot.msg_sends if x[0] == USER]
        texts = [x for x in bot.text_sends if x[0] == USER]
        check(len(copies) == 1 and not copies[0][2].get("buttons"),
              "media copied first, button not on the media when a text follows")
        check(len(texts) == 1 and texts[0][1] == "توضیح متنی" and
              "m:wallet" in btn_datas(texts[0][2].get("buttons")),
              "text goes after the media and carries the ending button")

        # ---------- 6) پیش‌نمایش مدیر روی بخش فقط-متنی ----------
        fake_now[0] += 5
        bot.text_sends = []
        ev = FakeCbEv(ADMIN, f"a:sec_vw:{w['id']}")
        await m.on_callback(ev)
        check(any("آموزش کیف پول" in (x[1] or "") for x in bot.text_sends if x[0] == ADMIN),
              "a:sec_vw previews a text-only section")

        time.time = real_time

    asyncio.run(main())
    print(f"BUILD {M.BUILD_VERSION}")
    for name, ok in results:
        print(f"CHECK {'PASS' if ok else 'FAIL'} - {name}")
    bad = [name for name, ok in results if not ok]
    print("PRESETS_RESULT", "PASS" if not bad else "FAIL")

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
    print("--- چهار متن آماده‌ی آموزش: کیف پول / خرید امتیاز / اشتراک ماهانه / بعد از فعال‌سازی ---")
    reset()
    out = run_inner(8173)
    checks = [ln for ln in out.splitlines() if ln.startswith("CHECK")]
    print("\n".join(checks) or out[-3000:])
    print("\n".join(ln for ln in out.splitlines()
                    if ln.startswith(("BUILD", "PRESETS_RESULT"))))
    good = "PRESETS_RESULT PASS" in out and not any(
        c.endswith("FAIL") or " FAIL " in c for c in checks)
    print("presets:", "PASS" if good else "FAIL")
    if not good:
        print(out[-6000:])
    sys.exit(0 if good else 1)
