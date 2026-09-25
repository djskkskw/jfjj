#!/usr/bin/env python3
"""رگرسیونِ «درست شدنِ بازیابیِ اطلاعات بعد از دیپلوی» — باگِ «همه‌ش می‌پره».

سناریوی واقعی روی Render/Railway:
  دیپلوی → دیسک پاک می‌شود → بوت با دیتابیس و manager_config.json خالی →
  بازیابی از «تک‌پیامِ پشتیبان» در تلگرام.

چهار چیزی که این تست پوشش می‌دهد (همه رفتاری — کدِ واقعی manager_82.py اجرا
می‌شود، با یک telethon جعلیِ چندچتی):

  ۱) `_reload_cfg_from_disk` بعد از restore_from_backup تنظیمات را از دیسکِ
     تازه‌شده می‌خواند؛ در نتیجه اولین `cfg.save()` (و هر `cfg[...] = ...`)
     فایلِ بازیابی‌شده را با پیش‌فرض‌های حافظه پاک نمی‌کند. این باگِ اصلیِ
     «همه‌ش می‌پره» بود.
  ۲) پیدا کردنِ پیامِ پشتیبان با `prefer_media` (فایل بر متنِ نقل‌قولی مقدم
     است) + جست‌وجوی سراسری `_find_backup_anywhere` در همهٔ چت‌های ربات.
  ۳) در `backup_once` اگر مقصد پیدا نشد/چتِ مقصد پیامِ پشتیبان نداشت، از
     «پیامِ پشتیبانِ قبلی» ادامه می‌دهد (edit همان پیام) — نه پیامِ تازه در
     چتِ اشتباه و نه قطعِ کاملِ پشتیبان.
  ۴) موقع بوت: `startup_restore` یک‌بار تلاشِ دوباره می‌کند و پیامِ وضعیتِ
     بازیابی (موفق/ناموفق) را به پیوی مدیر می‌فرستد؛ و اگر دیتابیس پر باشد
     هیچ کاری نمی‌کند (پیوی شلوغ نمی‌شود).

اجرا: `python3 tests/test_restore_resilience.py` → باید `ALL: PASS` بدهد.
"""
import os, sys, shutil, subprocess, tempfile, textwrap

ROOT = os.path.join(tempfile.gettempdir(), "jafj_restore_resilience_run")
APP = os.path.join(ROOT, "app")
DATA = os.path.join(ROOT, "data")
STORE = os.path.join(ROOT, "fakestore")
KEEP = os.path.join(ROOT, "keep")          # zipهای پایدارِ پیام‌های جعلی
SRC_REPO = os.environ.get("REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ───────────────────────── telethon جعلی (چندچتی) ─────────────────────────
FAKE_INIT = textwrap.dedent('''
import os, shutil

BOT_ID = 111
CHATS = {}            # کلیدِ چت -> [FakeMsg, ...] (تازه‌ترین اول)
SENT = []             # (چت, متن) پیام‌های متنیِ فرستاده‌شده
SEARCH_FAIL = [0]     # چند iter_messages اول خطا بدهند (بوتِ نابالغ/شبکه)
UNREACHABLE = set()   # چت‌هایی که ربات نمی‌تواند entityشان را بگیرد (PeerIdInvalid)
_next_id = [1000]


def _key(target):
    return str(target).strip().lower().lstrip("@")


class FakeDoc:
    """نشانهٔ «این پیام واقعاً فایل دارد»."""
    def __init__(self, name="backup.zip"):
        self.name = name


class FakeMsg:
    def __init__(self, mid, chat, caption="", text="", sender_id=BOT_ID,
                 fpath=None, media=None):
        self.id = mid
        self.chat_id = chat
        self.caption = caption or ""
        self.text = text or ""
        self.sender_id = sender_id
        self._fpath = fpath
        self.document = media
        self.media = media
        self.edits = 0

    @property
    def file(self):
        return self.document


class U:
    username = "fakebot"
    id = BOT_ID


class FakeDialog:
    def __init__(self, chat):
        self.id = chat
        self.entity = chat


class TelegramClient:
    def __init__(self, session, api_id, api_hash, **kw):
        self.session = session
        self.api_id = api_id
        self.api_hash = api_hash

    async def connect(self):
        return

    async def is_user_authorized(self):
        return True

    async def start(self, bot_token=None):
        return self

    async def disconnect(self):
        return

    async def get_me(self):
        return U()

    def on(self, *a, **k):
        def deco(fn):
            return fn
        return deco

    async def run_until_disconnected(self):
        return

    async def get_entity(self, x):
        if _key(x) in UNREACHABLE:
            raise ValueError(f"Could not find the input entity: {x}")
        class E:
            username = None
        return E()

    async def get_dialogs(self, limit=None):
        keys = list(CHATS.keys())
        if limit:
            keys = keys[:limit]
        return [FakeDialog(k) for k in keys]

    def iter_dialogs(self, limit=None):
        async def _gen():
            for d in await self.get_dialogs(limit=limit):
                yield d
        return _gen()

    def iter_messages(self, target, limit=50, **kw):
        async def _gen():
            if SEARCH_FAIL[0] > 0:
                SEARCH_FAIL[0] -= 1
                raise RuntimeError("ConnectionReset (simulated boot flakiness)")
            if _key(target) in UNREACHABLE:
                raise ValueError(f"Could not find the input entity: {target}")
            for m in list(CHATS.get(_key(target), []))[:limit]:
                yield m
        return _gen()

    async def send_message(self, chat, text=None, *a, **k):
        SENT.append((_key(chat), str(text or "")))
        class R:
            id = 1
        return R()

    async def send_file(self, target, fpath, caption=None, **kw):
        _next_id[0] += 1
        mid = _next_id[0]
        dst = os.path.join(os.environ["FAKE_BACKUP_DIR"], f"msg_{mid}.zip")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(str(fpath), dst)
        msg = FakeMsg(mid, _key(target), caption=caption, fpath=dst, media=FakeDoc())
        CHATS.setdefault(_key(target), []).insert(0, msg)
        return msg

    async def edit_message(self, target, message=None, text=None, *a, file=None, **kw):
        for m in CHATS.get(_key(target), []):
            if m.id == message:
                m.caption = text or ""
                m.edits += 1
                if file:
                    dst = os.path.join(os.environ["FAKE_BACKUP_DIR"], f"msg_{m.id}.zip")
                    shutil.copy2(str(file), dst)
                    m._fpath = dst
                    if m.document is None:
                        m.document = FakeDoc()
                return m
        raise RuntimeError("message not found")

    async def delete_messages(self, target, ids, **kw):
        ids = set(ids or ())
        k = _key(target)
        CHATS[k] = [m for m in CHATS.get(k, []) if m.id not in ids]

    async def download_media(self, msg, file=None, **kw):
        src = getattr(msg, "_fpath", None)
        if not src or not os.path.isfile(src):
            # پیامِ متنیِ نقل‌قولی هیچ فایلی ندارد
            raise ValueError("message has no media")
        if file is None:
            return src
        shutil.copy2(str(src), str(file))
        return str(file)


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
''')

FAKE_SESSIONS = textwrap.dedent('''
class StringSession:
    def __init__(self, s=""):
        self._s = s or ""
        self.dc_id = 1
        self.server_address = "127.0.0.1"
        self.port = 443
        self.auth_key = b"fake"
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
class PhoneNumberBannedError(Exception): pass
class PhoneNumberInvalidError(Exception): pass
class SessionPasswordNeededError(Exception): pass
class PhoneCodeInvalidError(Exception): pass
class PhoneCodeExpiredError(Exception): pass
class UserNotParticipantError(Exception): pass
''')

# ───────────────────────── درایور (سناریوها) ─────────────────────────
DRIVER = textwrap.dedent('''
import os, sys, json, shutil, asyncio
sys.path.insert(0, os.getcwd())
import manager_82 as M
from telethon import (TelegramClient, FakeMsg, FakeDoc, CHATS, SENT, SEARCH_FAIL,
                      UNREACHABLE)
from telethon.sessions import StringSession

DATA = os.environ["DATA_DIR"]
KEEP = os.environ["KEEP_DIR"]
CHAT_MAIN = "12345"        # BACKUP_CHAT
CHAT_OTHER = "-100999"     # چتِ دیگری که ربات در آن هست (کانال/پیوی قدیمی)
ADMIN = 555

results = {}


def check(name, cond, extra=""):
    results[name] = bool(cond)
    print(f"{name} {'PASS' if cond else 'FAIL ' + str(extra)}")


def wipe_data():
    """دیپلوی/ری‌استارت Render: هرچه روی دیسک داده است پاک می‌شود."""
    if not os.path.isdir(DATA):
        os.makedirs(DATA, exist_ok=True)
        return
    for name in os.listdir(DATA):
        p = os.path.join(DATA, name)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                os.remove(p)
            except Exception:
                pass


def make_mgr():
    m = M.Manager()
    m.bot = TelegramClient(StringSession("B"), 1, "hash")
    return m


def checkpoint(m):
    for conn in (m.db, m.shop):
        try:
            conn.c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.c.commit()
        except Exception:
            pass


def count(m):
    try:
        r = m.db.x("SELECT COUNT(*) c FROM clients", (), "one")
        return r["c"] if r else 0
    except Exception:
        return -1


def disk_cfg():
    try:
        with open(M.CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


async def main():
    try:
        # ═══ فاز ۱: «قبل از دیپلوی» — داده + تنظیمات + یک پشتیبان در تلگرام ═══
        wipe_data()
        CHATS.clear()
        SENT.clear()
        m = make_mgr()
        m.cfg["admin_ids"] = [ADMIN]
        m.cfg["max_clients"] = 77
        m.cfg["restart_fee"] = 4242
        m.cfg["card_number"] = "6037-9911-MARKER"
        m.db.add(111, "user_one", "User One", 0)
        m.db.set(111, session="SESSION_" + "Y" * 60, phone="+989120000001",
                 status="active", phone_verified=1, tg_id=111)
        m.db.add(222, "user_two", "User Two", 0)
        m.db.set(222, session="SESSION_" + "Z" * 60, phone="+989120000002",
                 status="active", phone_verified=1, tg_id=222)
        checkpoint(m)
        ok1, msg1 = await m.backup_once(force=True)
        msgs = CHATS.get(CHAT_MAIN, [])
        check("S1_backup_created_in_target_chat",
              ok1 and len(msgs) == 1 and msgs[0].document is not None,
              f"ok={ok1} msg={msg1} n={len(msgs)}")
        # zip و کپشنِ همان پیام را برای فازهای بعد نگه دار
        real_zip = os.path.join(KEEP, "phase1.zip")
        shutil.copy2(msgs[0]._fpath, real_zip)
        real_caption = msgs[0].caption

        # ═══ فاز ۲: دیپلوی — دیسک کاملاً پاک می‌شود، تلگرام می‌ماند ═══
        wipe_data()

        # ═══ فاز ۳: بوتِ تازه → startup_restore ═══
        m2 = make_mgr()
        SENT.clear()
        ok3, msg3 = await m2.startup_restore(notify=True, retries=1, wait_sec=0)
        check("S2_restore_after_deploy_wipe", ok3 and count(m2) == 2,
              f"ok={ok3} msg={msg3} n={count(m2)}")
        check("S3_cfg_reloaded_from_disk",
              m2.cfg.get("admin_ids") == [ADMIN]
              and m2.cfg.get("max_clients") == 77
              and m2.cfg.get("restart_fee") == 4242
              and m2.cfg.get("card_number") == "6037-9911-MARKER",
              f"cfg={ {k: m2.cfg.get(k) for k in ('admin_ids','max_clients','restart_fee','card_number')} }")

        # باگِ اصلی: اولین cfg.save() بعد از بوت، فایلِ بازیابی‌شده را می‌پَراند
        m2.cfg["max_clients"] = 9
        d = disk_cfg()
        check("S4_first_cfg_save_keeps_restored_settings",
              d.get("max_clients") == 9 and d.get("admin_ids") == [ADMIN]
              and d.get("restart_fee") == 4242
              and d.get("card_number") == "6037-9911-MARKER",
              f"disk={d.get('max_clients')},{d.get('admin_ids')},{d.get('restart_fee')}")

        # پیامِ وضعیتِ بازیابی در پیوی مدیر (همان admin_idsِ بازیابی‌شده)
        pv = [t for c, t in SENT if c == str(ADMIN)]
        check("S5_boot_status_message_to_admin_pv",
              len(pv) >= 1 and "بازیابی" in pv[0] and "✅" in pv[0]
              and "مشتری" in pv[0],
              f"sent={SENT}")

        # ═══ فاز ۴: prefer_media — فایل بر متنِ نقل‌قولی مقدم است ═══
        wipe_data()
        CHATS[CHAT_MAIN] = [
            # تازه‌تر: پیامِ متنی که فقط نشانه را نقل‌قول کرده (فایل ندارد)
            FakeMsg(9001, CHAT_MAIN,
                    text="یادداشت: پشتیبان JAFJBACKUP1 همین‌جا بود",
                    sender_id=111, media=None),
            # قدیمی‌تر: خودِ تک‌پیامِ پشتیبان با فایل
            FakeMsg(9000, CHAT_MAIN, caption=real_caption, sender_id=111,
                    fpath=real_zip, media=FakeDoc()),
        ]
        m3 = make_mgr()
        found = await m3._find_last_backup_msg(CHAT_MAIN, limit=50)
        check("S6_find_prefers_media_over_quoted_text",
              found is not None and found.id == 9000,
              f"id={getattr(found, 'id', None)}")
        m4 = make_mgr()
        ok4, msg4 = await m4.restore_from_backup(force=False)
        check("S7_restore_uses_media_message", ok4 and count(m4) == 2,
              f"ok={ok4} msg={msg4} n={count(m4)}")
        # کنترل: همان پیامِ متنی واقعاً فایل ندارد (وگرنه سنجه بی‌معنا بود)
        try:
            await m4.bot.download_media(CHATS[CHAT_MAIN][0])
            no_media = False
        except Exception:
            no_media = True
        check("S8_quoted_text_message_has_no_downloadable_file", no_media)

        # ═══ فاز ۵: جست‌وجوی سراسری در همهٔ چت‌های ربات ═══
        wipe_data()
        CHATS[CHAT_MAIN] = []                      # چتِ مقصد خالی شده
        zip2 = os.path.join(KEEP, "phase5.zip")
        shutil.copy2(real_zip, zip2)
        CHATS[CHAT_OTHER] = [FakeMsg(9100, CHAT_OTHER, caption=real_caption,
                                     sender_id=111, fpath=zip2, media=FakeDoc())]
        m5 = make_mgr()
        t5, msg5 = await m5._find_backup_anywhere()
        check("S9_find_backup_anywhere_searches_all_chats",
              msg5 is not None and getattr(msg5, "id", None) == 9100
              and m5._chat_key(t5) == CHAT_OTHER,
              f"t={m5._chat_key(t5)} id={getattr(msg5, 'id', None)}")
        wipe_data()
        m6 = make_mgr()
        ok6, msg6 = await m6.startup_restore(notify=False, retries=0, wait_sec=0)
        check("S10_restore_from_other_chat_when_target_empty",
              ok6 and count(m6) == 2, f"ok={ok6} msg={msg6} n={count(m6)}")

        # ═══ فاز ۶: backup_once از پیامِ پشتیبانِ قبلی ادامه می‌دهد ═══
        # مقصدِ فعلی (BACKUP_CHAT تازه) هیچ پیامی ندارد؛ تک‌پیامِ پشتیبان در
        # CHAT_OTHER است → باید همان edit شود، نه پیامِ تازه در چتِ اشتباه.
        wipe_data()
        os.environ["BACKUP_CHAT"] = "777"
        UNREACHABLE.add("777")          # ربات هرگز این چت را ندیده (PeerIdInvalid)
        m7 = make_mgr()
        m7.db.add(333, "user_three", "User Three", 0)
        checkpoint(m7)
        ok7, msg7 = await m7.backup_once(force=False)
        other = CHATS.get(CHAT_OTHER, [])
        wrong = CHATS.get("777", [])
        check("S11_backup_continues_previous_message_when_target_missing",
              ok7 and len(other) == 1 and other[0].id == 9100 and other[0].edits >= 1
              and len(wrong) == 0,
              f"ok={ok7} msg={msg7} other={len(other)} edits={other[0].edits if other else '-'} wrong={len(wrong)}")
        # کنترلِ رگرسیون: مقصدِ «سالم ولی خالی» (مدیر عمداً BACKUP_CHAT را به
        # چتِ تازه‌ای منتقل کرده) باید پیامِ تازهٔ خودش را بگیرد، نه اینکه
        # پشتیبان به چتِ قدیمی برگردد.
        os.environ["BACKUP_CHAT"] = "888"
        UNREACHABLE.discard("888")
        m7b = make_mgr()
        m7b.db.add(444, "user_four", "User Four", 0)
        checkpoint(m7b)
        ok_new, msg_new = await m7b.backup_once(force=False)
        fresh = CHATS.get("888", [])
        check("S12_reachable_empty_target_gets_its_own_message",
              ok_new and len(fresh) == 1 and fresh[0].document is not None
              and CHATS[CHAT_OTHER][0].id == 9100,
              f"ok={ok_new} msg={msg_new} fresh={len(fresh)}")

        # حالتِ «مقصد اصلاً پیدا نشد» (admin_ids خالی و BACKUP_CHAT نیست)
        os.environ["BACKUP_CHAT"] = CHAT_MAIN
        m7._backup_target = lambda: None
        m7.db.log(333, "change", "data changed again")
        checkpoint(m7)
        ok8, msg8 = await m7.backup_once(force=False)
        check("S13_backup_without_target_resumes_from_previous_chat",
              ok8 and len(CHATS.get(CHAT_OTHER, [])) == 1
              and CHATS[CHAT_OTHER][0].edits >= 2,
              f"ok={ok8} msg={msg8} n={len(CHATS.get(CHAT_OTHER, []))}")

        # ═══ فاز ۷: موقع بوت یک‌بار تلاشِ دوباره + پیامِ وضعیت ═══
        # تلاشِ اول شکست می‌خورد (تلگرام/شبکه موقع بوت آماده نیست)، دومی نه.
        wipe_data()
        zip3 = os.path.join(KEEP, "phase7.zip")
        shutil.copy2(real_zip, zip3)
        CHATS[CHAT_MAIN] = [FakeMsg(9200, CHAT_MAIN, caption=real_caption,
                                    sender_id=111, fpath=zip3, media=FakeDoc())]
        CHATS.pop(CHAT_OTHER, None)
        m8 = make_mgr()
        SENT.clear()
        orig_restore = m8.restore_from_backup
        calls = [0]

        async def flaky(force=False):
            calls[0] += 1
            SEARCH_FAIL[0] = 99 if calls[0] == 1 else 0
            return await orig_restore(force=force)

        m8.restore_from_backup = flaky
        ok9, msg9 = await m8.startup_restore(notify=True, retries=1, wait_sec=0)
        SEARCH_FAIL[0] = 0
        check("S14_boot_retries_once_and_recovers",
              ok9 and calls[0] == 2 and m8._restore_tries == 2 and count(m8) == 2,
              f"ok={ok9} calls={calls[0]} tries={m8._restore_tries} n={count(m8)}")

        # دیتابیس پر است → هیچ کاری نمی‌کند و پیامی هم نمی‌فرستد
        SENT.clear()
        snapshot = {k: len(v) for k, v in CHATS.items()}
        ok10, msg10 = await m8.startup_restore(notify=True, retries=1, wait_sec=0)
        check("S15_boot_restore_noop_when_db_not_empty",
              ok10 and "نیازی به بازیابی" in msg10 and SENT == []
              and snapshot == {k: len(v) for k, v in CHATS.items()},
              f"ok={ok10} msg={msg10} sent={SENT}")

        # هر دو تلاش شکست بخورد → پیامِ وضعیتِ «ناموفق» به پیوی مدیر می‌رود
        wipe_data()
        m9 = make_mgr()
        SENT.clear()
        SEARCH_FAIL[0] = 99
        ok11, msg11 = await m9.startup_restore(notify=True, retries=1, wait_sec=0)
        SEARCH_FAIL[0] = 0
        fail_msgs = [t for c, t in SENT if "بازیابی" in t and "⚠️" in t]
        check("S16_boot_failure_status_message_sent",
              (not ok11) and m9._restore_tries == 2 and len(fail_msgs) >= 1
              and ".restore" in fail_msgs[0],
              f"ok={ok11} tries={m9._restore_tries} sent={SENT}")

        # ═══ فاز ۸: مسیرِ دستی (دستور .restore) هم cfg را از دیسک تازه می‌کند ═══
        # اینجا startup_restore در کار نیست؛ خودِ restore_from_backup باید
        # تنظیمات را از دیسکِ بازیابی‌شده بخواند وگرنه اولین save می‌پَراندشان.
        wipe_data()
        m10 = make_mgr()
        ok12, msg12 = await m10.restore_from_backup(force=True)
        inmem_ok = (m10.cfg.get("admin_ids") == [ADMIN]
                    and m10.cfg.get("restart_fee") == 4242
                    and m10.cfg.get("card_number") == "6037-9911-MARKER")
        m10.cfg["max_clients"] = 3                 # اولین save بعد از بازیابی
        d10 = disk_cfg()
        check("S17_manual_restore_also_reloads_cfg",
              ok12 and count(m10) == 2 and inmem_ok
              and d10.get("admin_ids") == [ADMIN]
              and d10.get("restart_fee") == 4242
              and d10.get("card_number") == "6037-9911-MARKER",
              f"ok={ok12} msg={msg12} inmem={inmem_ok} disk={d10.get('admin_ids')}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        results["EXCEPTION"] = f"{type(e).__name__}: {e}"

    for k in sorted(results):
        if k not in [x for x in results if x.startswith("S")]:
            print(f"{k} {results[k]}")
    good = all(v is True for v in results.values()) and "EXCEPTION" not in results
    print("RESILIENCE_RESULT", "PASS" if good else "FAIL")


asyncio.run(main())
''')


def reset_all():
    shutil.rmtree(ROOT, ignore_errors=True)
    for d in (APP, DATA, STORE, KEEP):
        os.makedirs(d, exist_ok=True)
    for f in ("manager_82.py", "95.py"):
        shutil.copy2(os.path.join(SRC_REPO, f), APP)
    tel = os.path.join(APP, "telethon")
    os.makedirs(tel, exist_ok=True)
    with open(os.path.join(tel, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_INIT)
    with open(os.path.join(tel, "sessions.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_SESSIONS)
    with open(os.path.join(tel, "errors.py"), "w", encoding="utf-8") as f:
        f.write(FAKE_ERRORS)


def main():
    print("--- restore resilience after deploy ---")
    reset_all()
    env = dict(os.environ)
    env["DATA_DIR"] = DATA
    env["KEEP_DIR"] = KEEP
    env["FAKE_BACKUP_DIR"] = STORE
    env["PORT"] = "8231"
    env["JAFJ_PORT"] = "8231"
    env["BACKUP_CHAT"] = "12345"
    for k in ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_ID", "RAILWAY_PROJECT_ID",
              "RENDER", "JAFJ_HOSTED", "JAFJ_LOGIN_RETRY", "BOT_TOKEN", "API_ID",
              "API_HASH", "ADMIN_IDS", "BACKUP_EVERY"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-c", DRIVER], cwd=APP, env=env,
                       capture_output=True, text=True, timeout=300)
    out = p.stdout + p.stderr
    for line in out.splitlines():
        if (line.startswith(("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9",
                             "RESILIENCE", "EXCEPTION", "Traceback"))
                or "Error" in line):
            print(line)
    good = "RESILIENCE_RESULT PASS" in out
    if good:
        print("ALL: PASS")
        return 0
    print("ALL: FAIL")
    print(out[-6000:])
    return 1


if __name__ == "__main__":
    sys.exit(main())
